# Status and Scope

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Systemzweck

Der Inversion Analyzer sammelt, archiviert, bewertet und visualisiert Temperatur- und Vertikalprofildaten zur Beurteilung von Inversionslagen. GUI und Headless-Collector verwenden dasselbe Tagesarchiv.

## 2. Nachweisbarer Ist-Stand

**IMPLEMENTED v0.15.24:**

- Windows-/Python-GUI über `Inversionskurve.py` und `inversion/gui.py`.
- Headless-Collector `Inversion_Server.py`.
- standortbezogene Tagesarchive unter `archive/<Ort>/YYYY/MM/DD/`.
- globales KIT-Referenzarchiv unter `archive/KITMast/YYYY/MM/DD/`.
- Datenquellen DWD, Open-Meteo-Vertikalprofil, ICON-D2, Radiosonde, KIT-Mast und optional AEMET.
- GitHub Actions Workflow `.github/workflows/inversion_collect.yml` mit `normal`, `scheduled`, `kit-only`.
- Remote-GitHub-Raw-Nachladen einschließlich transaktionalem KIT-Referenzdownload.
- Safe-Merge/NO-TOUCH bei Teilläufen; vorhandene gute Daten werden bei Fehlabfragen nicht gelöscht.
- Regressionstests für zentrale KIT-/Workflow-Funktionen.

## 3. Geplante Erweiterungen

**PLANNED:**

1. GitHub Actions erzeugt vollständige Inversionsdiagramme als reproduzierbare Datenprodukte.
2. GitHub Actions ruft seismische Diagramme ab und/oder erzeugt sie aus Rohdaten; genaue Quellen-/Stationsliste ist konfigurierbar.
3. Audioaufnahmen werden aus Supabase abgerufen und daraus definierte akustische Kennwerte (u. a. L50/L90/Leq) berechnet und zeitbezogen archiviert.
4. Für die verbleibenden Erweiterungen werden automatische Validierungs- und Regressionstests ergänzt.

## 4. Nicht behauptet

Die Bewertungssynchronisation ist seit v0.15.24 **IMPLEMENTED**. Automatische vollständige Inversionsdiagramme, Seismik-Automatisierung und Audioanalyse sind weiterhin **PLANNED**. Für diese Bereiche beschreibt die Dokumentation Zielarchitektur und Akzeptanzkriterien, nicht bereits vorhandenen Code.


## v0.15.24 – Supabase-Bewertungen (IMPLEMENTED)

- IMPLEMENTED: separater Supabase→GitHub-Import für subjektive Bewertungen aus `observations`.
- IMPLEMENTED: automatische GitHub Action bei Minute 12 und 42 jeder Stunde.
- IMPLEMENTED: idempotente Deduplikation über `event_id`.
- IMPLEMENTED: Tagesarchiv `archive/ratings/YYYY/MM/YYYY-MM-DD/ratings.jsonl` plus `summary.json`.
- IMPLEMENTED: inkrementeller Sync-State mit 48-h-Überlappung gegen verspätete Uploads.
- IMPLEMENTED: Datenschutz-Default ohne Kommentartext und ohne exakte GPS-Koordinaten.
- PLANNED: Audioabruf und Ableitung von L50/L90/Leq und weiteren Kennwerten.
