"""
update_dichiarazioni.py
========================
GitHub Actions script — gira lunedì/mercoledì/venerdì.

Per ogni candidato nella lista, cerca dichiarazioni pubbliche recenti
specifiche su Milano 2027, le classifica secondo lo schema (tema, tipo
affermazione, menzioni ad altri candidati), e le aggiunge alla coda di
revisione pending_dichiarazioni.json.

NON pubblica nulla direttamente in dichiarazioni.json — tutto passa
dal backoffice per approvazione manuale.

Dipendenze:
  pip install datapizza-ai datapizza-ai-clients-anthropic datapizza-ai-tools-duckduckgo requests
"""

import os
import json
import time
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from datapizza.clients.anthropic import AnthropicClient
from datapizza.tools.duckduckgo import DuckDuckGoSearchTool

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CANDIDATI_FILE = "candidati.json"
DICHIARAZIONI_FILE = "dichiarazioni.json"
PENDING_FILE = "pending_dichiarazioni.json"
SCARTI_FILE = "scarti_dichiarazioni.json"

LOOKBACK_DAYS = 5  # finestra temporale di ricerca (copre i giorni dall'ultima run)
SIMILARITY_THRESHOLD = 0.75  # soglia per considerare due testi "duplicati"

TEMI = ["mobilita", "verde", "abitazioni", "cultura", "economia", "comunita", "clima", "istituzioni"]

EXTRACTION_SYSTEM_PROMPT = """
Sei un assistente di ricerca per uno strumento pubblico e trasparente di
analisi del dibattito elettorale di Milano 2027 (elezioni comunali).

Il tuo compito: dai risultati di ricerca web forniti, estrai SOLO citazioni
dirette e verificabili rilasciate dal candidato indicato, specificamente
su temi cittadini milanesi (non dichiarazioni su politica nazionale a meno
che non siano esplicitamente legate alla sua candidatura a sindaco).

REGOLE FERREE:
- Riporta SOLO testo tra virgolette nella fonte originale, MAI parafrasare
- Se non trovi citazioni dirette affidabili, restituisci una lista vuota
- Non inventare MAI una dichiarazione o attribuirla senza fonte chiara
- Ogni dichiarazione deve avere una fonte (URL) verificabile

Per ogni dichiarazione trovata, classifica:
1. tema_primario (uno tra): mobilita, verde, abitazioni, cultura, economia,
   comunita, clima, istituzioni
2. tema_secondario (opzionale, stesso elenco, o null)
3. tipo_affermazione: proposta_concreta | posizione_principio | critica
4. menziona: se cita esplicitamente un altro candidato (per nome o perifrasi
   chiara), indica il suo id (vedi lista candidati fornita) e il tono:
   contro | a_favore | neutro_menzione

Rispondi SOLO con JSON in questo formato esatto:
{
  "dichiarazioni": [
    {
      "testo_originale": "citazione esatta tra virgolette",
      "data": "YYYY-MM-DD o stima",
      "fonte": "nome testata",
      "fonte_url": "url completo",
      "tema_primario": "...",
      "tema_secondario": "..." | null,
      "tipo_affermazione": "...",
      "menziona": ["id_candidato"] | [],
      "tono_menzione": "contro|a_favore|neutro_menzione" | null
    }
  ]
}

Se non trovi nulla di affidabile, rispondi: {"dichiarazioni": []}
"""


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def text_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_duplicate(new_text, existing_texts):
    for t in existing_texts:
        if text_similarity(new_text, t) > SIMILARITY_THRESHOLD:
            return True
    return False


def main():
    print("🔍 Milano 2027 — Ricerca dichiarazioni automatica")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    candidati_data = load_json(CANDIDATI_FILE, {"candidati": []})
    candidati = candidati_data["candidati"]

    dichiarazioni_data = load_json(DICHIARAZIONI_FILE, {"dichiarazioni": []})
    pending_data = load_json(PENDING_FILE, {"dichiarazioni": []})

    # Testi esistenti (pubblicati + già in coda) per deduplicazione
    existing_texts = [
        d["testo_originale"] for d in dichiarazioni_data["dichiarazioni"]
    ] + [
        d["testo_originale"] for d in pending_data["dichiarazioni"]
    ]

    # Mappa nome -> id per riferimento nelle menzioni
    name_to_id = {c["nome"].lower(): c["id"] for c in candidati}
    candidati_ref = "\n".join(f"- {c['id']}: {c['nome']}" for c in candidati)

    # Salta i candidati già marcati ritirato
    target_candidati = [c for c in candidati if c["status"] != "ritirato"]

    client = AnthropicClient(api_key=ANTHROPIC_API_KEY, model="claude-sonnet-4-6")
    search_tool = DuckDuckGoSearchTool()

    new_pending = []
    cutoff_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    for i, cand in enumerate(target_candidati):
        nome = cand["nome"]
        cid = cand["id"]
        print(f"\n[{i+1}/{len(target_candidati)}] {nome}...")

        query = f"{nome} Milano sindaco 2027 dichiarazione"
        try:
            results = search_tool.run(query)
        except Exception as e:
            print(f"   ⚠️  search error: {e}")
            continue

        if not results:
            print("   nessun risultato")
            continue

        # Tronca risultati per non esplodere il context
        results_text = str(results)[:6000]

        prompt = f"""CANDIDATO: {nome} (id: {cid})

LISTA CANDIDATI VALIDI per il campo "menziona" (usa solo questi id):
{candidati_ref}

DATA MINIMA: cerca solo dichiarazioni successive a {cutoff_date}

RISULTATI RICERCA WEB:
{results_text}

Estrai le dichiarazioni dirette di {nome} secondo le regole date."""

        try:
            response = client.invoke(prompt, system=EXTRACTION_SYSTEM_PROMPT)
            raw = response.text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw.strip())
        except json.JSONDecodeError as e:
            print(f"   ⚠️  parse error: {e}")
            continue
        except Exception as e:
            print(f"   ⚠️  API error: {e}")
            continue

        found = parsed.get("dichiarazioni", [])
        added = 0

        for d in found:
            testo = d.get("testo_originale", "").strip()
            if not testo or len(testo) < 20:
                continue
            if is_duplicate(testo, existing_texts):
                continue

            entry = {
                "id": f"dich_{cid}_{int(time.time())}_{added}",
                "candidato_id": cid,
                "testo_originale": testo,
                "data": d.get("data", datetime.now().strftime("%Y-%m-%d")),
                "fonte": d.get("fonte", ""),
                "fonte_url": d.get("fonte_url", ""),
                "tema_primario": d.get("tema_primario"),
                "tema_secondario": d.get("tema_secondario"),
                "tipo_affermazione": d.get("tipo_affermazione"),
                "menziona": d.get("menziona", []),
                "tono_menzione": d.get("tono_menzione"),
                "status_revisione": "pending",
                "trovata_il": datetime.now().isoformat(),
            }
            new_pending.append(entry)
            existing_texts.append(testo)
            added += 1

        print(f"   → {added} nuove dichiarazioni trovate")
        time.sleep(1.5)

    # Aggiorna pending
    pending_data["dichiarazioni"].extend(new_pending)
    pending_data["ultimo_aggiornamento"] = datetime.now().isoformat()
    save_json(PENDING_FILE, pending_data)

    print(f"\n✅ Totale nuove dichiarazioni in coda: {len(new_pending)}")
    print(f"   Coda di revisione totale: {len(pending_data['dichiarazioni'])}")
    print(f"   Vai sul backoffice per approvare o scartare.")


if __name__ == "__main__":
    main()
