# MILANO 2027 — Schema Dati & Metodologia
## Mappa del Dibattito Elettorale

| **Versione** | 1.0 — Giugno 2026 |
|---|---|
| **Stato** | Schema definito, pronto per prima raccolta dati |
| **Principio guida** | Trasparenza totale: metodologia pubblica, nessun giudizio di qualità, solo classificazione descrittiva |

---

## 1. Cosa misura questo strumento (e cosa NON misura)

**Misura:**
- Su quali temi si concentra ogni candidato/attore del dibattito
- Quanto le posizioni di due candidati si somigliano (vicinanza tematica)
- Quanto due candidati si confrontano pubblicamente, e con che segno (conflitto/alleanza)
- Che tipo di affermazione fa un candidato (proposta concreta / principio / critica)

**NON misura:**
- Se una posizione è "giusta" o "sbagliata"
- Se un candidato è "migliore" di un altro
- "Profondità" o "qualità" delle dichiarazioni
- Non assegna punteggi di merito a nessun individuo

La classificazione è applicata in modo identico e cieco a tutti i soggetti, secondo la griglia pubblicata di seguito. Chiunque può verificare o contestare una singola classificazione confrontandola con il testo originale della dichiarazione, sempre linkato come fonte.

---

## 2. Griglia tematica (8 categorie)

| Categoria | Perimetro |
|---|---|
| **Mobilità** | Trasporto pubblico, ciclabili, traffico, ZTL, parcheggi |
| **Verde** | Parchi, alberature, biodiversità urbana, aree verdi pubbliche |
| **Abitazioni** | Affitti, casa popolare, gentrificazione, edilizia residenziale |
| **Cultura** | Musei, eventi, vita notturna, identità cittadina, sport |
| **Economia** | Lavoro, imprese, turismo, commercio, attrattività economica |
| **Comunità** | Welfare, periferie, integrazione, terzo settore, scuole di quartiere |
| **Clima** | Politiche energetiche, emissioni, resilienza climatica (dimensione infrastrutturale, distinta da Verde) |
| **Istituzioni** | Governance comunale, municipi, partecipazione, trasparenza amministrativa |

Una dichiarazione può toccare più temi — si assegna un tema primario e, se rilevante, un tema secondario.

---

## 3. Asse descrittivo — Tipo di affermazione

Puramente descrittivo, non valutativo:

| Tipo | Definizione |
|---|---|
| `proposta_concreta` | Azione specifica e misurabile ("estendere la M4 a...") |
| `posizione_principio` | Visione o valore dichiarato, senza azione specifica |
| `critica` | Rivolta a situazione esistente, governo uscente, o altro candidato |

---

## 4. I due assi di relazione tra candidati

### Asse A — Vicinanza ideologica (posizione nello spazio)

Calcolata come similarità delle posizioni tematiche aggregate. **Non è un arco esplicito**: è una forza nella simulazione del grafo che attrae candidati con posizioni simili e allontana quelli divergenti.

```
vicinanza_ideologica(A, B) = similarità coseno tra
  vettore_temi(A) e vettore_temi(B)

dove vettore_temi(X) = [score_mobilità, score_verde, score_abitazioni, ...]
  calcolato come distribuzione percentuale delle dichiarazioni di X per tema
```

### Asse B — Intensità di confronto (arco esplicito)

Tracciato quando una dichiarazione di A nomina esplicitamente B (per nome o riferimento chiaro: "il sindaco uscente", "la destra cittadina", ecc.)

```json
{
  "source": "candidato_A",
  "target": "candidato_B",
  "tipo_relazione": "contro | a_favore | neutro_menzione",
  "n_menzioni": 7,
  "weight": 7,
  "temi_della_menzione": ["mobilità", "istituzioni"]
}
```

Lo spessore dell'arco cresce con `n_menzioni`. Il colore segnala il segno prevalente (rosso=conflitto, verde=appoggio, grigio=neutro).

---

## 5. Schema dati completo

### Nodo Candidato

```json
{
  "id": "candidato_id",
  "label": "Nome Cognome",
  "type": "candidato",
  "coalizione": "Centrosinistra | Centrodestra | Terzo polo | Indipendente | ...",
  "color": "#hex",
  "n_dichiarazioni_totali": 12,
  "vettore_temi": {
    "mobilita": 0.25, "verde": 0.10, "abitazioni": 0.30,
    "cultura": 0.05, "economia": 0.15, "comunita": 0.10,
    "clima": 0.05, "istituzioni": 0.0
  },
  "tema_dominante": "abitazioni"
}
```

### Nodo Dichiarazione

```json
{
  "id": "dich_001",
  "candidato_id": "candidato_A",
  "testo_originale": "...",
  "data": "2026-09-15",
  "fonte": "url",
  "tema_primario": "abitazioni",
  "tema_secondario": "economia",
  "tipo_affermazione": "proposta_concreta",
  "menziona": ["candidato_B"],
  "tono_menzione": "contro"
}
```

### Arco Vicinanza (Asse A — forza posizionale)

```json
{
  "source": "candidato_A",
  "target": "candidato_B",
  "type": "vicinanza_ideologica",
  "similarity_score": 0.72
}
```

### Arco Confronto (Asse B — relazione esplicita)

```json
{
  "source": "candidato_A",
  "target": "candidato_B",
  "type": "confronto",
  "tipo_relazione": "contro",
  "n_menzioni": 7,
  "weight": 7
}
```

---

## 6. Prompt di classificazione (per Claude)

```
Sei un classificatore di dichiarazioni politiche per uno strumento di
analisi pubblica e trasparente del dibattito elettorale di Milano 2027.

Il tuo compito è SOLO descrittivo: classifica, non giudicare.
Non esprimere opinioni su qualità, correttezza o validità delle posizioni.

Per ogni dichiarazione classifica:

1. TEMA PRIMARIO (uno tra): mobilita, verde, abitazioni, cultura,
   economia, comunita, clima, istituzioni

2. TEMA SECONDARIO (opzionale, stesso elenco, o null)

3. TIPO AFFERMAZIONE (uno tra):
   - proposta_concreta: azione specifica e misurabile
   - posizione_principio: visione o valore, senza azione specifica
   - critica: rivolta a situazione esistente o altro soggetto

4. MENZIONI: se la dichiarazione nomina esplicitamente un altro
   candidato o si riferisce chiaramente a lui/lei (anche con perifrasi
   tipo "il sindaco uscente"), indica:
   - chi viene menzionato
   - tono: contro | a_favore | neutro_menzione

Rispondi SOLO con JSON:
{
  "tema_primario": "...",
  "tema_secondario": "..." | null,
  "tipo_affermazione": "...",
  "menziona": ["nome_candidato"] | [],
  "tono_menzione": "contro|a_favore|neutro_menzione" | null
}
```

---

## 7. Calcolo vicinanza ideologica

```python
import numpy as np

def cosine_similarity(vec_a, vec_b):
    a = np.array(list(vec_a.values()))
    b = np.array(list(vec_b.values()))
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# Per ogni coppia di candidati con almeno N dichiarazioni classificate
for cand_a, cand_b in candidate_pairs:
    sim = cosine_similarity(cand_a.vettore_temi, cand_b.vettore_temi)
    if sim > 0.3:  # soglia minima per disegnare la forza
        links.append({
            "source": cand_a.id, "target": cand_b.id,
            "type": "vicinanza_ideologica",
            "similarity_score": round(sim, 3)
        })
```

---

## 8. Nota metodologica pubblica (da pubblicare sul sito)

> Questo strumento classifica dichiarazioni pubbliche dei candidati alle
> elezioni comunali di Milano 2027 secondo una griglia tematica fissa e
> dichiarata (vedi sopra). La classificazione è effettuata da un modello
> linguistico (Claude, Anthropic) secondo istruzioni pubblicate
> integralmente in questa pagina. Non esprimiamo giudizi di merito sulle
> posizioni politiche: il sistema descrive temi, tipologia di affermazione
> e relazioni esplicite tra candidati, sempre con link alla fonte
> originale. Segnalazioni di errori di classificazione sono benvenute.

---

## 9. Prossimi passi tecnici

1. **Raccolta dichiarazioni** — definire fonti (siti candidati, comunicati,
   interviste, social) e formato di raccolta (manuale o scraping mirato)
2. **Script di classificazione** — batch processing con il prompt sopra
3. **Calcolo vettori e similarità** — aggregazione per candidato
4. **Frontend** — stesso framework D3.js già collaudato, due strati:
   forza di posizionamento (Asse A) + archi espliciti (Asse B)
5. **Pagina metodologia** — sempre visibile e linkata dalla home

---

*— fine documento v1.0 —*
