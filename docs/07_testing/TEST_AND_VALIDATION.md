# Test and Validation Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Testebenen

- Parser-/Algorithmus-Unit-Tests.
- Archiv- und Safe-Merge-Regressionstests.
- Remote-GitHub-Downloadtests.
- Workflow-Strukturtests.
- Headless-Selftest.
- End-to-End-Rekonstruktionstest.

## 2. Mindest-Akzeptanz Ist-Stand

1. `python Inversion_Server.py --selftest` → keine FAIL-Zeile.
2. `--show-config` zeigt gültige aktive Location.
3. `--verify-archive` läuft ohne Strukturfehler.
4. vorhandene Regressionstests laufen erfolgreich.
5. GUI startet und kann einen lokalen Archivtag anzeigen.

## 3. PLANNED Inversionsdiagramme

PASS wenn Diagramm + Metadaten aus einem Referenztag erzeugt werden, Datenqualität korrekt angegeben ist und fehlende Kerndaten nicht als Nullkurve erscheinen.

## 4. PLANNED Seismik

PASS pro Station nur bei gültigem Produkt und korrektem Tagesbezug. Tests müssen falsches Bildformat, HTTP-Fehler und veraltetes Produkt abdecken.

## 5. IMPLEMENTED Supabase-Bewertungen / weitere Tests

Implementiert sind Regressionen für Deduplikation, Idempotenz, 0/-1-Trennung, Standortreduktion, Kommentar-Ausschluss, UTC-Tagespartition sowie Workflowstruktur. Noch zu ergänzen sind bei Bedarf ein Live-E2E-Test gegen ein separates Testprojekt, große Pagination-Datensätze, simulierte HTTP-Abbrüche und automatisierter Secret-Leak-Scan.
