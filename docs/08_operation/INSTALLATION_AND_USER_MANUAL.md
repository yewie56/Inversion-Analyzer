# Installation and User Manual

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Installation

1. ZIP entpacken.
2. Python 3.11 bereitstellen.
3. Abhängigkeiten installieren.
4. `locations.json`, `archive_config.json`, optional `settings.json` prüfen.
5. `python Inversion_Server.py --selftest` ausführen.
6. `python Inversionskurve.py` starten.

## 2. GUI-Hauptfunktionen

Oben stehen Tagesnavigation, HEUTE, UPDATE, PNG und Menü. Das Menü enthält Ort, Bedienmodus, Display-Quellen, Datenabruf-Quellen, Advanced-Optionen, Archiv laden, CSV, Selbsttest, Radiosonden- und KIT-Details sowie ±7-Tage-Navigation.

## 3. Bedienprinzip

Tagesnavigation lädt lokale Archive. UPDATE ist der bewusste Netzwerkabruf. Bei KIT-Referenzstandorten aktualisiert KIT das zentrale `archive/KITMast` statt per-Location-Daten zu duplizieren.

## 4. Export

PNG/CSV sind GUI-Exporte. Die geplante Actions-Diagrammerstellung ist davon getrennt und erzeugt serverseitige reproduzierbare Tagesprodukte.
