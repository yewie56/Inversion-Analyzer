# Software Requirements Specification (SRS)

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Funktionale Anforderungen – Ist-Stand

| ID | Anforderung | Status |
|---|---|---|
| REQ-DATA-001 | Das System muss Tagesdaten für einen konfigurierten Standort erfassen können. | IMPLEMENTED |
| REQ-DATA-002 | DWD-Bodenmessung und Open-Meteo-Vertikalprofil müssen getrennt erfasst werden. | IMPLEMENTED |
| REQ-DATA-003 | ICON-D2, Radiosonde und KIT dürfen als getrennte Zusatz-/Referenzreihen vorliegen. | IMPLEMENTED |
| REQ-ARCH-001 | Tagesdaten müssen dauerhaft im gemeinsamen Archiv gespeichert werden. | IMPLEMENTED |
| REQ-ARCH-002 | Teil-/Retry-Läufe dürfen nicht angeforderte Quelldateien nicht verändern. | IMPLEMENTED |
| REQ-ARCH-003 | Fehlgeschlagene KIT-Abrufe dürfen vorhandene gute KIT-Profile nicht löschen. | IMPLEMENTED |
| REQ-LOC-001 | Mehrere Orte müssen über `locations.json` unterstützt werden. | IMPLEMENTED |
| REQ-GUI-001 | Ein vorhandener Archivtag muss in der GUI ohne Netzwerkabruf darstellbar sein. | IMPLEMENTED |
| REQ-GUI-002 | Ein explizites Update darf aktivierte Quellen nachladen. | IMPLEMENTED |
| REQ-AUTO-001 | Der Headless-Collector muss zeitgesteuert und manuell ausführbar sein. | IMPLEMENTED |
| REQ-AUTO-002 | GitHub Actions muss alle Orte oder einen ausgewählten Ort verarbeiten können. | IMPLEMENTED |
| REQ-REMOTE-001 | Fehlende Archivdaten können aus einem konfigurierten GitHub-Raw-Archiv nachgeladen werden. | IMPLEMENTED |
| REQ-QA-001 | Die Kernqualität muss unabhängig von optionalen Referenzquellen bestimmt werden. | IMPLEMENTED |

## 2. Geplante Anforderungen – Inversionsdiagramme

| ID | Anforderung | Status |
|---|---|---|
| REQ-DIAG-001 | Actions muss nach erfolgreicher Tagesdatenverarbeitung ein vollständiges Inversionsdiagramm erzeugen können. | PLANNED |
| REQ-DIAG-002 | Diagramme müssen aus archivierten numerischen Daten reproduzierbar sein; PNG allein genügt nicht. | PLANNED |
| REQ-DIAG-003 | Jeder Diagrammoutput benötigt Metadaten mit Softwareversion, Datum, Standort, Eingangsmanifest und Erstellzeit. | PLANNED |
| REQ-DIAG-004 | Bei unzureichender Datenqualität darf kein scheinbar gültiges Diagramm erfunden werden; Status/Fehler muss sichtbar bleiben. | PLANNED |

## 3. Geplante Anforderungen – Seismik

| ID | Anforderung | Status |
|---|---|---|
| REQ-SEIS-001 | Seismische Tagesdiagramme müssen automatisiert pro konfigurierter Station abrufbar sein. | PLANNED |
| REQ-SEIS-002 | Wenn Rohdaten verfügbar und unterstützt sind, muss eine lokale Diagrammerzeugung möglich sein. | PLANNED |
| REQ-SEIS-003 | Quelle, Station, Zeitbasis und Original-/erzeugter Status müssen archiviert werden. | PLANNED |
| REQ-SEIS-004 | HTTP-Fehler oder veraltete Diagramme dürfen nicht als erfolgreicher Tagesabruf gelten. | PLANNED |

## 4. Anforderungen – Supabase → GitHub (Bewertungen Phase 1)

| ID | Anforderung | Status |
|---|---|---|
| REQ-SYNC-001 | Neue Bewertungen müssen inkrementell aus Supabase exportiert werden. | IMPLEMENTED |
| REQ-SYNC-002 | Wiederholte Läufe müssen idempotent sein und dürfen keine Duplikate erzeugen. | IMPLEMENTED |
| REQ-SYNC-003 | Secrets dürfen nicht in Repository, Log oder Exportdatei geschrieben werden. | IMPLEMENTED |
| REQ-SYNC-004 | Nur ausdrücklich freigegebene bzw. pseudonymisierte Felder dürfen nach GitHub gelangen. | IMPLEMENTED |
| REQ-SYNC-005 | Der Transfer muss einen nachvollziehbaren Sync-Zustand und Validierungsbericht erzeugen. | IMPLEMENTED |

## 5. Nichtfunktionale Anforderungen

- **Reproduzierbarkeit:** numerische Eingaben, Parameter und Versionen müssen nachvollziehbar bleiben.
- **Robustheit:** Netzwerkfehler dürfen bestehende gute Daten nicht zerstören.
- **Testbarkeit:** früher behobene Fehler werden als Regressionstest konserviert.
- **Selftest:** wesentliche Parser, Konfigurationen und Archivpfade erhalten automatische PASS/FAIL-Prüfungen.
- **Portabilität:** lokaler Betrieb unter Windows/Python 3.11; Actions unter Ubuntu/Python 3.11.
- **Datenschutz:** Bewertungen/Standortbezug werden nach Datenminimierung behandelt.
- **Nachvollziehbarkeit:** Requirement, Codepfad und Test werden über die Traceability-Matrix verbunden.


## Anforderungen v0.15.24 – Bewertungsimport

- **REQ-RATING-SYNC-001 (IMPLEMENTED):** Das System muss Bewertungen aus Supabase automatisiert abrufen können.
- **REQ-RATING-SYNC-002 (IMPLEMENTED):** `event_id` muss der unveränderliche Deduplikationsschlüssel sein.
- **REQ-RATING-SYNC-003 (IMPLEMENTED):** Ein Wiederholungslauf darf keine doppelten Bewertungen erzeugen.
- **REQ-RATING-SYNC-004 (IMPLEMENTED):** Bewertung `0` und `-1` müssen getrennt bleiben.
- **REQ-RATING-SYNC-005 (IMPLEMENTED):** Archivierung muss entlang einer UTC-Zeitachse tageweise erfolgen.
- **REQ-RATING-SYNC-006 (IMPLEMENTED):** Kommentartext darf in dieser Ausbaustufe nicht nach GitHub exportiert werden.
- **REQ-RATING-SYNC-007 (IMPLEMENTED):** Exakte Beobachtungskoordinaten dürfen im Default nicht exportiert werden; die Defaultdarstellung wird auf zwei Dezimalstellen abgeschnitten.
- **REQ-RATING-SYNC-008 (IMPLEMENTED):** Supabase-Backend-Schlüssel dürfen ausschließlich aus Secret-Umgebungsvariablen gelesen werden.
