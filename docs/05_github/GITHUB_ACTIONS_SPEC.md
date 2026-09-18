# GitHub Actions Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Aktueller Workflow

Datei: `.github/workflows/inversion_collect.yml`  
Name: `Inversion data collector`  
Runner: `ubuntu-latest`  
Python: 3.11  
Timeout: 45 Minuten  
Permission: `contents: write`  
Concurrency: `inversion-archive-writer`, kein Cancel laufender Jobs.

## 2. Trigger

### Zeitplan

`7,37 * * * *` – zweimal pro Stunde.

### `workflow_dispatch`

| Input | Werte/Default |
|---|---|
| `mode` | `normal`, `scheduled`, `kit-only`; Default `normal` |
| `date` | optional `YYYY-MM-DD` |
| `force` | boolean, Default false |
| `location` | Schlüssel aus `locations.json` oder `ALL`; Default `Viernheim` |

## 3. Aktuelle Steps

1. Checkout (`actions/checkout@v6`, vollständige History).
2. Setup Python (`actions/setup-python@v7`, 3.11).
3. `pip install requests pandas numpy matplotlib bokeh`.
4. Restore Radiosonden-Cache (`actions/cache@v6`).
5. Locations auflösen.
6. Preflight: `--selftest`, `--show-config`, `--verify-archive` pro Ort.
7. globales KIT-Referenzarchiv für schedule/scheduled/kit-only.
8. scheduled collection oder manual collection.
9. Archivänderungen anzeigen.
10. `git add archive`, Commit und Push, falls Änderungen vorliegen.

## 4. Secrets

Aktuell verwendet: `AEMET_API_KEY`.

Supabase-Bewertungssync verwendet `SUPABASE_SECRET_KEY` (bevorzugt) bzw. vorübergehend `SUPABASE_SERVICE_ROLE_KEY` als GitHub Secret. Keine Secrets in YAML-Literalen, Dateien oder Logs.

## 5. PLANNED Steps

Nach Datenvalidierung und vor Commit:

- `Generate inversion products`.
- `Collect/generate seismic products`.
- `Export ratings from Supabase` – **IMPLEMENTED** als separater Workflow seit v0.15.24.
- `Validate generated products and sync state`.

Die Steps müssen einzeln testbar sein. Optional kann später eine Aufteilung in separate Workflows erfolgen.

## 6. Akzeptanzkriterien für Erweiterung

- manueller Dispatch für jede neue Funktion testbar,
- geplante Läufe ohne interaktive Eingaben,
- keine Secrets im Log,
- Fehler in Zusatzprodukten zerstören kein vorhandenes Archiv,
- Wiederholung erzeugt keine Ratings-Duplikate,
- generierte Diagramme besitzen Metadaten und eindeutigen Tagesbezug.


## Workflow `supabase_ratings_sync.yml` (IMPLEMENTED ab v0.15.24)

| Feld | Wert |
|---|---|
| Zweck | Supabase-Bewertungen ins GitHub-Archiv spiegeln |
| Automatischer Trigger | `12,42 * * * *` |
| Manuell | `workflow_dispatch` |
| Manueller Input | `full=true/false` |
| Python | 3.11 |
| Zusätzliche Python-Pakete | keine |
| Secret | `SUPABASE_SECRET_KEY` bevorzugt |
| Legacy Secret | `SUPABASE_SERVICE_ROLE_KEY` |
| Schreibrecht | `contents: write` |
| Output | `archive/ratings/**` |
| Deduplikation | `event_id` |
| Regressionstests | `test_supabase_ratings_sync_v0_15_24.py`, `test_supabase_ratings_workflow_v0_15_24.py` |
| Concurrency | `inversion-archive-writer`, kein Cancel laufender Jobs |

Der Workflow ist bewusst vom meteorologischen Collector getrennt. Wetter/KIT startet bei Minute 07/37, Bewertungen bei 12/42.

### Gemeinsame Schreibsperre ab v0.15.24

`inversion_collect.yml` und `supabase_ratings_sync.yml` verwenden beide `concurrency.group: inversion-archive-writer` mit `cancel-in-progress: false`. Dadurch werden Archivschreibvorgänge im Repository serialisiert. Zusätzlich wird nach dem Commit vor dem Push `git pull --rebase origin main` ausgeführt.
