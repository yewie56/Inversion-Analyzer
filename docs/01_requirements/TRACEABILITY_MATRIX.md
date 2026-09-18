# Traceability Matrix

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Ist-Stand

| Requirement | Design/Komponente | Implementierung | Test/Nachweis |
|---|---|---|---|
| REQ-DATA-001 | Pipeline | `inversion/pipeline.py` | Headless-Selftest + manuelle Tagesläufe |
| REQ-ARCH-001 | Archivschicht | `inversion/archive.py` | `--verify-archive` |
| REQ-ARCH-002 | Safe-Merge/NO-TOUCH | `archive.merge_bundles`, `save_bundle` | bestehende KIT-/Archivtests |
| REQ-ARCH-003 | KIT Safe-Merge | `inversion/kit_reference_archive.py` | `test_kit_reference_archive_v0_15_22.py`, `test_gui_kit_reference_remote_v0_15_23.py` |
| REQ-LOC-001 | Standortkonfiguration | `locations.json`, `config.py`, `runtime_location.py` | Workflow Preflight für jeden Ort |
| REQ-AUTO-001 | Headless CLI | `Inversion_Server.py` | `--selftest`, `--show-config`, `--verify-archive` |
| REQ-AUTO-002 | Actions | `.github/workflows/inversion_collect.yml` | `test_workflow_dispatch_modes_v0_15_21.py`, `test_workflow_global_kit_v0_15_22.py` |
| REQ-REMOTE-001 | Remote-Archiv | `remote_archive.py`, `archive_service.py` | `test_gui_kit_reference_remote_v0_15_23.py` |

## 2. Ziel-Traceability für die Erweiterungen

| Requirement | Zielkomponente | Zieltest |
|---|---|---|
| REQ-DIAG-001..004 | `diagram_export.py` oder äquivalentes Modul + Actions-Step | Golden-file/Metadaten-Test, fehlende-Daten-Test |
| REQ-SEIS-001..004 | `seismic_source.py`, `seismic_plot.py` + Workflow/Step | HTTP-/Stale-/Format-/Plot-Regressionstests |
| REQ-SYNC-001..005 | `inversion/supabase_ratings.py`, `sync_supabase_ratings.py`, Sync-State + `supabase_ratings_sync.yml` | `test_supabase_ratings_sync_v0_15_24.py`, `test_supabase_ratings_workflow_v0_15_24.py` |

Bei Implementierung ist diese Matrix **im selben Commit** zu aktualisieren.

## v0.15.24 Bewertungs-Synchronisation

| Requirement | Design/Code | Workflow | Test | Status |
|---|---|---|---|---|
| REQ-RATING-SYNC-001 | `inversion/supabase_ratings.py`, `sync_supabase_ratings.py` | `supabase_ratings_sync.yml` | `test_supabase_ratings_sync_v0_15_24.py` | IMPLEMENTED |
| REQ-RATING-SYNC-002/003 | Merge über `event_id` | `supabase_ratings_sync.yml` | Idempotenztest | IMPLEMENTED |
| REQ-RATING-SYNC-004 | Ratingvalidierung -1..5 | `supabase_ratings_sync.yml` | 0/-1-Test | IMPLEMENTED |
| REQ-RATING-SYNC-005 | UTC-Day-Partition | `supabase_ratings_sync.yml` | Tageswechseltest | IMPLEMENTED |
| REQ-RATING-SYNC-006/007 | Sanitization/Privacy | `supabase_ratings_sync.yml` | Kommentar-/GPS-Test | IMPLEMENTED |
| REQ-RATING-SYNC-008 | `resolve_supabase_key()` | GitHub Secrets | Workflow-Preflight | IMPLEMENTED |

