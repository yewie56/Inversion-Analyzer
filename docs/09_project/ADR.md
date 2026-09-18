# Architecture Decision Records (ADR)

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## ADR-001 – Gemeinsames Tagesarchiv

**Entscheidung:** GUI und Headless-Collector verwenden dasselbe Archiv.  
**Grund:** reproduzierbare Anzeige und keine getrennten Wahrheiten.

## ADR-002 – Globales KIT-Referenzarchiv

**Entscheidung:** KIT seit v0.15.22 unter `archive/KITMast`, nicht pro Location dupliziert.  
**Grund:** identische Referenzdaten sollen zentral archiviert werden.

## ADR-003 – Referenzdaten bleiben getrennt

**Entscheidung:** KIT, Radiosonde und ICON-D2 werden nicht stillschweigend mit dem Hauptmodell vermischt.  
**Grund:** Herkunft und Interpretation müssen sichtbar bleiben.

## ADR-004 – Safe-Merge / NO-TOUCH

**Entscheidung:** Teil-/Retry-Läufe verändern nicht angeforderte Quellen nicht und löschen gute Daten nicht bei Fehlabfragen.  
**Grund:** robuste Langzeitarchivierung.

## ADR-005 – Neue Actions-Produkte nachgelagert

**Status:** PLANNED/accepted design direction.  
**Entscheidung:** Inversionsdiagramme, Seismik und Ratings-Export werden nachgelagert und dürfen den Primärcollector nicht korrumpieren.
