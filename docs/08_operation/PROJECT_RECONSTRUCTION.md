# Project Reconstruction Guide

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Ziel

Neuaufbau auf einem leeren Rechner und in einem neuen/rekonstruierten GitHub-Repository ausschließlich aus Quellstand und Dokumentation.

## 2. Lokaler Neuaufbau

1. Projektdateien bereitstellen.
2. Python 3.11 installieren.
3. `requests pandas numpy matplotlib bokeh` installieren.
4. Projektwurzel als Arbeitsverzeichnis verwenden.
5. `python Inversion_Server.py --selftest`.
6. `python Inversion_Server.py --show-config`.
7. `python Inversion_Server.py --verify-archive`.
8. `python Inversionskurve.py` starten.
9. einen vorhandenen Archivtag ohne Netzwerk laden.
10. einen expliziten Testtag aktualisieren und Manifest prüfen.

## 3. GitHub neu aufbauen

1. Repository anlegen bzw. History wiederherstellen.
2. Quellbaum inklusive `.github/workflows/` pushen.
3. Actions aktivieren.
4. Workflow-Permission für erforderliches `contents: write` konfigurieren.
5. Secret `AEMET_API_KEY` setzen, falls AEMET verwendet wird.
6. `workflow_dispatch` mit einem einzelnen Testort und `mode=normal` starten.
7. danach `mode=kit-only` testen.
8. danach `location=ALL`, `mode=scheduled` testen.
9. Archivcommit und GitHub-Raw-Lesbarkeit prüfen.
10. erst dann Schedule produktiv lassen.

## 4. Geplante Erweiterungen rekonstruieren

Nach Implementierung zusätzlich:

- Diagrammprodukt aus festem Referenztag erzeugen und Hash/Metadaten prüfen.
- Seismik-Teststation abrufen/erzeugen.
- Supabase Secrets setzen.
- Dry-Run/Fixture für Ratings ausführen.
- echten kleinen inkrementellen Export durchführen.
- denselben Export erneut starten und **0 Duplikate** bestätigen.

## 5. Abschluss-PASS

Das System gilt als rekonstruiert, wenn GUI, Headless, Archiv, Remote-Fallback, GitHub Actions und sämtliche implementierten Produktpipelines ihre definierten PASS-Kriterien erfüllen.

## Rekonstruktion der Supabase-Bewertungssynchronisation ab v0.15.24

1. `ratings_sync_config.json` prüfen.
2. In GitHub Actions das Repository Secret `SUPABASE_SECRET_KEY` setzen.
3. Workflow `Supabase ratings sync` manuell mit `full=true` starten.
4. `archive/ratings/sync_state.json` prüfen.
5. Mindestens eine Tagesdatei `ratings.jsonl` gegen den erwarteten Supabase-Bestand prüfen.
6. `summary.json` auf getrennte Zählung von `0` und `-1` prüfen.
7. Den Full-Lauf ein zweites Mal starten und prüfen, dass keine Duplikate entstehen.
8. Danach den normalen zeitgesteuerten Betrieb aktiv lassen.
