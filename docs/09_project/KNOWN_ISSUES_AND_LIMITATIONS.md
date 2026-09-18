# Known Issues and Limitations

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. KIT-Rolling Window

Der öffentliche KIT-Bokeh-Profilserver liefert nur einen begrenzten rollierenden Ausschnitt. Nicht rechtzeitig archivierte Profile können später fehlen; daher läuft der Collector zweimal pro Stunde.

## 2. Settings-Version

`settings.json` enthält im gelieferten v0.15.23-Stand `"version": "0.14.0"`. Bedeutung/Migrationsverwendung ist zu klären.

## 3. Datenqualität

Das Hauptprofil basiert teilweise auf Modell-/Archivdaten. KIT und Radiosonde sind getrennte Mess-/Referenzreihen und dürfen nicht als lokale Messung eines entfernten Standortes interpretiert werden.

## 4. Paketversionen

Python-Abhängigkeiten sind nicht auf exakte Versionen gepinnt; zukünftige Bibliotheksänderungen können Verhalten verändern.

## 5. Geplante Erweiterungen

Seismik sowie Supabase-Audioabruf/-analyse sind noch nicht implementiert. Der Bewertungstransfer ist seit v0.15.24 implementiert; ein produktiver Live-E2E-Lauf muss nach Einrichtung des GitHub-Secrets noch verifiziert werden. Die gewünschte Repository-Sichtbarkeit (öffentlich/privat) bleibt für die Datenschutzbewertung relevant.
