# Development Directives

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Versionsdisziplin

- keine Funktionsänderung ohne Versions-/Changelog-Prüfung,
- vollständige Dateien statt unvollständiger Patchfragmente ausliefern,
- dokumentierte Konfigurationen kompatibel halten oder Migration definieren.

## 2. Regression

Jeder behobene reproduzierbare Fehler wird als Regressionstest konserviert. Vor Release laufen bestehende Tests erneut.

## 3. Selftest

Neue externe Parser/Produktgeneratoren erhalten einen offline-fähigen Selftest mit Fixture oder synthetischen Daten, soweit möglich.

## 4. Datenintegrität

- kein Löschen guter Daten wegen leerer/fehlgeschlagener Remoteantwort,
- keine erfundenen Ersatzdaten,
- keine Nullkurve bei fehlendem Vertikalprofil,
- Safe-Merge und Idempotenz bei wiederholten Automationsläufen.

## 5. Dokumentation

Requirement → Design → Implementierung → Test → Changelog muss für neue Funktionsblöcke nachvollziehbar sein. `IMPLEMENTED` und `PLANNED` dürfen nicht vermischt werden.

## 6. Secrets

Secrets nie in Code, ZIP-Beispieldaten, Logs, Screenshots oder Dokumentation mit echtem Wert ablegen.
