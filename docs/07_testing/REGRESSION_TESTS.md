# Regression Tests

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Vorhandene Regressionstests bis v0.15.24

| Datei | Zweck |
|---|---|
| `test_kit_github_archive_v0_15_18.py` | GitHub-/KIT-Archivstruktur |
| `test_kit_robustness_v0_15_19.py` | Bokeh-Timeout/Retry-Robustheit |
| `test_kit_missing_level_v0_15_20.py` | fehlende KIT-Einzelhöhe tolerieren |
| `test_workflow_dispatch_modes_v0_15_21.py` | Dispatch-Modi |
| `test_kit_reference_archive_v0_15_22.py` | globales KIT-Referenzarchiv |
| `test_workflow_global_kit_v0_15_22.py` | globaler KIT-Step im Workflow |
| `test_gui_kit_reference_remote_v0_15_23.py` | GUI-/Remote-KIT-Referenz-Fix inkl. transaktionalem Download |

## 2. Regel

Jeder künftig behobene Fehler erhält, soweit automatisierbar, einen Regressionstest. Bestehende Tests werden nicht ohne dokumentierten Ersatz entfernt.

## 3. Neue Testgruppen

- `test_diagram_export_*` für Actions-Diagramme.
- `test_seismic_*` für Quelle/Frische/Plot.
- `test_supabase_export_*` für Schema, Pagination, Deduplikation, Idempotenz.


## v0.15.24

`test_supabase_ratings_sync_v0_15_24.py` prüft:
- `0` bleibt von `-1` getrennt,
- Koordinaten werden auf zwei Dezimalstellen abgeschnitten,
- `0.0/0.0` wird als fehlender Standort behandelt,
- Kommentartext bleibt aus dem Export, `has_comment` bleibt erhalten,
- doppelte `event_id` erzeugt nur einen Archivdatensatz,
- Wiederholung desselben Imports verändert die Tagesdatei nicht,
- UTC-Tageswechsel erzeugt getrennte Tagesarchive,
- unveränderter Sync-State wird nicht bei jedem Lauf neu geschrieben.

`test_supabase_ratings_workflow_v0_15_24.py` prüft zusätzlich Schedule, Secrets, gemeinsame Concurrency-Gruppe, `--full`, ratings-only Staging sowie Rebase vor Push für beide Archiv-Writer.
