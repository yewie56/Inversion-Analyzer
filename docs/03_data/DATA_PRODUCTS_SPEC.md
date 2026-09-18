# Data Products Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Bestehende Datenprodukte

- archivierte Roh-/Quelltabellen,
- `inversion_model.csv`,
- GUI-Plot sowie manueller PNG-/CSV-Export,
- Quellstatus und Tagesmanifest.

## 2. PLANNED: automatisches Inversionsdiagramm

Ein vollständiges Tagesprodukt muss enthalten:

- Standort und Datum,
- Haupt-Inversionskurve/Index,
- lokale Stratifikationsinformation soweit vorhanden,
- getrennte Referenz-/Zusatzreihen (KIT, Radiosonde, ICON-D2) nur wenn verfügbar,
- Qualitätsklasse und Datenherkunft,
- Software-/Schema-Version,
- Hinweis auf fehlende Daten statt künstlicher Nullkurve.

## 3. PLANNED: Seismikprodukt

Metadaten müssen Originalquelle, Station, Produktzeitraum, Abrufzeit, Original-vs-generated, Content-Hash, Validierungsergebnis und ggf. Rohdatenreferenz enthalten.

## 4. PLANNED: Bewertungsprodukt

Bewertungsexporte müssen schema-versioniert, deterministisch sortierbar und deduplizierbar sein. Persönliche oder präzise Standortdaten werden nur nach expliziter Freigabe und definierter Datenschutzstrategie exportiert.
