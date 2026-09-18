# Software Design Specification (SDS)

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Modulübersicht



## 2. Verantwortlichkeiten

| Modul | Verantwortung |
|---|---|
| `inversion/config.py` | Laufzeitkonfiguration, aktive Location, URLs, Archiveinstellungen |
| `inversion/models.py` | `SourceStatus`, `DataBundle` |
| `inversion/pipeline.py` | Orchestrierung der Quellen pro Datum |
| `inversion/inversion_engine.py` | Profilmetriken und lokaler Stratifikationsindex |
| `inversion/archive.py` | Tagesarchiv, Merge, Manifest, Quellstatus |
| `inversion/archive_service.py` | GUI-/Servicezugriff auf Archiv und Updates |
| `inversion/remote_archive.py` | GitHub-Raw-Nachladen |
| `inversion/kit_reference_archive.py` | globales KIT-Referenzarchiv und Safe-Merge |
| `inversion/gui.py` | Tkinter-/Matplotlib-GUI |
| `Inversion_Server.py` | CLI, Selftest, Scheduled/Retry-Logik |
| `inversion/supabase_ratings.py` | Supabase-REST-Abruf, Datenschutzabbildung, Deduplikation, Tagesarchiv und Sync-State |
| `sync_supabase_ratings.py` | headless CLI für Bewertungssynchronisation |

## 3. Zentrale Datenobjekte

`SourceStatus` hält Zustand, Meldung, Zeitpunkte, HTTP-Status, Zeilenanzahl und Abdeckungsdiagnosen. `DataBundle` bündelt alle Quellen- und Ergebnis-DataFrames sowie Qualitätsklasse/-text.

## 4. Erweiterungsdesign

Neue Automatisierungsfunktionen sollen **nicht** in `gui.py` implementiert werden. Empfohlen sind klar getrennte headless-fähige Module für:

- Diagrammexport,
- Seismikquelle/-plot,
- Supabase-Audioimport und Audio-Kennwerte; **der Bewertungsimport und Sync-State sind seit v0.15.24 bereits als headless Module implementiert**.

Diese Module müssen unabhängig von Tkinter importierbar und in Actions testbar sein.
