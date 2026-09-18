# Test Execution Report

> Dokumentationsstand: 2026-09-19  \
> Software-Basis: Inversion Analyzer v0.15.25  \
> Testumgebung: Python 3.13.5 im Erstellungscontainer.

## 1. Ergebnis

**PASS** – der eingebaute Selftest, alle bisherigen Regressionstests sowie die beiden neuen Supabase-Ratings-Tests wurden für v0.15.24 erfolgreich ausgeführt.

## 2. Ausgeführte Prüfungen

| Test | Ergebnis |
|---|---|
| `python Inversion_Server.py --selftest` | PASS |
| `test_kit_github_archive_v0_15_18.py` | PASS (6/6) |
| `test_kit_robustness_v0_15_19.py` | PASS |
| `test_kit_missing_level_v0_15_20.py` | PASS |
| `test_workflow_dispatch_modes_v0_15_21.py` | PASS |
| `test_kit_reference_archive_v0_15_22.py` | PASS |
| `test_workflow_global_kit_v0_15_22.py` | PASS |
| `test_gui_kit_reference_remote_v0_15_23.py` | PASS |
| `test_supabase_ratings_sync_v0_15_24.py` | PASS |
| `test_supabase_ratings_workflow_v0_15_24.py` | PASS |
| YAML-Parse `.github/workflows/inversion_collect.yml` | PASS |
| YAML-Parse `.github/workflows/supabase_ratings_sync.yml` | PASS |

## 3. Baseline und Änderungen

Die ursprüngliche v0.15.23-Baseline bleibt über `docs/09_project/ORIGINAL_SOURCE_SHA256.md` nachweisbar. v0.15.24 verändert gezielt Code, Workflow und Dokumentation für die Bewertungssynchronisation; diese Änderungen sind in `CHANGELOG_0.15.24.txt` beschrieben.

## 4. Noch nicht live verifiziert

Ein realer Abruf aus dem produktiven Supabase wurde in der Erstellungsumgebung **nicht** ausgeführt, weil dort bewusst kein produktiver Backend-Schlüssel hinterlegt ist. Der erste Live-Nachweis erfolgt in GitHub Actions nach Einrichtung von `SUPABASE_SECRET_KEY`; siehe `docs/05_github/SUPABASE_RATINGS_ACTION_SETUP.md`.

## 5. Weiterhin PLANNED

- Audioabruf aus Supabase,
- L50/L90/Leq und weitere Audio-Kennwerte,
- vollständige automatische Inversionsdiagrammerstellung,
- Seismik-Automatisierung.

## v0.15.25 – Live-E2E-Fix für Pending-Bewertungen

Auslöser war der erste produktive Vollabruf: 320 Supabase-Zeilen, davon 265 gültige Bewertungen und 55 Zeilen ohne `response_time`. Die neue Regression bildet diesen Fall nach: **265 accepted, 55 pending_skipped, 0 rejected**. Zusätzlich bleibt der Negativtest aktiv: eine echte Bewertung 0..5 ohne `response_time` wird abgelehnt.

Verifiziert am 2026-09-19:
- alle `test_*.py`: PASS
- `Inversion_Server.py --selftest`: PASS
- `.github/workflows/inversion_collect.yml`: YAML PASS
- `.github/workflows/supabase_ratings_sync.yml`: YAML PASS
