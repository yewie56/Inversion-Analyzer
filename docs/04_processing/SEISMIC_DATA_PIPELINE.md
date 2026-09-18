# Seismic Data Pipeline

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Status

**PLANNED.** Seismik ist im Quellstand v0.15.23 noch kein Bestandteil der Pythonmodule oder Actions.

## 2. Unterstützte Betriebsarten

**Mode A – fertiges Diagramm abrufen:** HTTP-Download eines offiziellen Stationsprodukts, Prüfung auf HTTP-Erfolg, Bildformat, Mindestgröße, Datum/Frische und Hash; danach unveränderte Archivierung als Original.

**Mode B – Diagramm selbst erzeugen:** Rohdaten laden, Zeitbasis/Einheit normalisieren, definierte Plotparameter anwenden, Rohdaten + Plot + Metadaten archivieren.

## 3. Stationskonfiguration

Pflichtfelder: `station_id`, `name`, `operator`, `timezone`, `source_type`, `url`, `expected_update`, `archive_slug`, optionale Parser-/Plotparameter.

## 4. Zielablage

`archive/Seismic/<Station>/YYYY/MM/DD/` mit `metadata.json`, Originalprodukt und/oder generiertem Plot sowie optionalen Rohdaten.

## 5. Validierung

Ein HTTP-200 allein reicht nicht. Zu prüfen sind Content-Type, decodierbares Bild/Format, plausible Größe, erwarteter Stationsbezug, Datum/Frische und unveränderte Übernahme des Originals per SHA-256.

## 6. Actions

Seismik soll als isolierter Step/Job laufen. Ausfall einer Station soll andere Stationen und den meteorologischen Collector nicht zerstören. Der Workflow muss im Log pro Station PASS/FAIL/STALE ausgeben.
