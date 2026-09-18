# Automation Architecture

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. IMPLEMENTED v0.15.24

Ein Workflow `inversion_collect.yml` führt auf `ubuntu-latest` aus. Er besitzt:

- `workflow_dispatch` mit `mode`, `date`, `force`, `location`,
- Zeitplan `7,37 * * * *`,
- `contents: write`,
- gemeinsame Archiv-Concurrency-Gruppe `inversion-archive-writer`,
- Python 3.11,
- Preflight pro Standort,
- globalen KIT-Referenzschritt,
- scheduled/manual Collect,
- Commit/Push von `archive/`.

## 2. PLANNED – Erweiterungsstufen

Empfohlene logische Stufen:

1. **Collect:** bestehende Wetter-/Profil-/KIT-Daten aktualisieren.
2. **Validate:** Manifest, Quellenstatus, zeitliche Abdeckung prüfen.
3. **Create inversion products:** vollständige Diagramme/Metadaten erzeugen.
4. **Collect/Create seismic products:** Stationsprodukte holen/erzeugen.
5. **Transfer ratings:** **IMPLEMENTED v0.15.24** als separater Workflow; neue freigegebene Bewertungen aus Supabase exportieren.
6. **Validate products:** Schema, Dateigrößen, Zeitstempel und Deduplikation prüfen.
7. **Commit:** ausschließlich validierte Artefakte committen.

## 3. Workflow-Aufteilung

Wetter/KIT und Bewertungen sind seit v0.15.24 in getrennten Workflows realisiert und durch `inversion-archive-writer` serialisiert. Weitere Funktionen können als eigene Workflows oder klar getrennte Steps ergänzt werden; verbindlich ist die logische Trennung.

## 4. Fehlerisolation

Ein Seismik- oder Supabase-Fehler darf vorhandene Inversionsarchivdaten nicht löschen. Ein fehlgeschlagener Diagrammexport darf den erfolgreichen Rohdatenabruf nicht rückgängig machen. Commit-Regeln müssen Teilprodukte eindeutig markieren.
