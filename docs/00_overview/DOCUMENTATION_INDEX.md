# Documentation Index

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Zweck

Dieser Index ist der verbindliche Einstieg in die Projektdokumentation. Der Dokumentationssatz beschreibt den reproduzierbaren Ist-Stand v0.15.24 und trennt ihn von der Zielarchitektur für die geplanten Automatisierungen.

## 2. Verbindliche Dokumente

| Bereich | Dokument | Zweck |
|---|---|---|
| Überblick | `00_overview/STATUS_AND_SCOPE.md` | Geltungsbereich und Statusmodell |
| Anforderungen | `01_requirements/SRS.md` | funktionale und nichtfunktionale Anforderungen |
| Anforderungen | `01_requirements/TRACEABILITY_MATRIX.md` | Requirement → Design → Code → Test |
| Architektur | `02_architecture/SAD.md` | Systemarchitektur |
| Architektur | `02_architecture/SDS.md` | Softwaredesign / Module |
| Architektur | `02_architecture/AUTOMATION_ARCHITECTURE.md` | bestehende und geplante Automatisierung |
| Architektur | `02_architecture/AUTOMATION_DEPENDENCY_GRAPH.md` | Abhängigkeiten der Datenflüsse |
| Daten | `03_data/DATA_SOURCES.md` | externe Quellen |
| Daten | `03_data/DATA_FORMAT_SPECIFICATION.md` | Datei- und Datenformate |
| Daten | `03_data/DATA_PRODUCTS_SPEC.md` | erzeugte Datenprodukte |
| Daten | `03_data/ARCHIVE_SPECIFICATION.md` | Archivstruktur und Safe-Merge-Regeln |
| Verarbeitung | `04_processing/INVERSION_ALGORITHMS.md` | Berechnungslogik |
| Verarbeitung | `04_processing/INVERSION_DIAGRAM_PIPELINE.md` | geplante vollständige Diagrammerstellung in Actions |
| Verarbeitung | `04_processing/SEISMIC_DATA_PIPELINE.md` | geplante Seismik-Pipeline |
| Verarbeitung | `04_processing/SUPABASE_GITHUB_TRANSFER_SPEC.md` | implementierter Bewertungstransfer; Audio geplant |
| Verarbeitung | `04_processing/SYNC_STATE_SPEC.md` | Idempotenz und Synchronisationszustand |
| GitHub | `05_github/GITHUB_REPOSITORY_SPEC.md` | Repository-Regeln |
| GitHub | `05_github/GITHUB_ACTIONS_SPEC.md` | Workflow-Spezifikation |
| GitHub | `05_github/GITHUB_OPERATIONS.md` | Betrieb und Fehlerdiagnose |
| Sicherheit | `06_security/SECURITY_AND_SECRETS.md` | Secrets, Datenschutz, Rechte |
| Test | `07_testing/TEST_AND_VALIDATION.md` | Test- und Validierungsspezifikation |
| Test | `07_testing/REGRESSION_TESTS.md` | vorhandene Regressionstests |
| Test | `07_testing/DATA_VALIDATION_SPEC.md` | Plausibilitäts- und Vollständigkeitsprüfungen |
| Test | `07_testing/SELF_TEST_SPECIFICATION.md` | integrierter Selftest |
| Test | `07_testing/TEST_EXECUTION_REPORT.md` | ausgeführter PASS-Nachweis für v0.15.24 |
| Betrieb | `08_operation/BUILD_AND_DEVELOPMENT.md` | Entwicklungs-/Buildumgebung |
| Betrieb | `08_operation/INSTALLATION_AND_USER_MANUAL.md` | Installation und Bedienung |
| Betrieb | `08_operation/OPERATIONS_AND_MONITORING.md` | laufender Betrieb |
| Betrieb | `08_operation/RETRY_AND_ERROR_HANDLING.md` | Retry- und Fehlermodell |
| Betrieb | `08_operation/BACKUP_AND_RECOVERY.md` | Sicherung und Wiederherstellung |
| Betrieb | `08_operation/PROJECT_RECONSTRUCTION.md` | Neuaufbau aus Null |
| Projekt | `09_project/CONFIGURATION_SPECIFICATION.md` | Konfigurationen und Defaults |
| Projekt | `09_project/DEPENDENCIES_AND_SBOM.md` | Abhängigkeiten/SBOM |
| Projekt | `09_project/KNOWN_ISSUES_AND_LIMITATIONS.md` | bekannte Grenzen |
| Projekt | `09_project/DEVELOPMENT_DIRECTIVES.md` | verbindliche Entwicklungsregeln |
| Projekt | `09_project/ADR.md` | Architekturentscheidungen |
| Projekt | `09_project/CHANGELOG_DOCUMENTATION.md` | Dokumentationsänderungen |
| Projekt | `09_project/SOURCE_PROVENANCE.md` | Herkunft und Integritätsnachweis |

## 3. Rekonstruktionsziel

Ein technisch versierter Entwickler soll mit Quellstand + Dokumentationssatz eine lauffähige lokale Installation und die GitHub-Automatisierung rekonstruieren können, ohne auf den bisherigen Chatverlauf angewiesen zu sein.

## 4. Historische Unterlagen

`docs/superpowers/` bleibt unverändert als interne frühere Design-/Planungsablage erhalten. Die verbindliche neue Projektdokumentation befindet sich in den oben gelisteten Verzeichnissen.

## Änderung durch Projektversion 0.15.24

Die Dokumentation beschreibt die Supabase-Bewertungssynchronisation nun als **IMPLEMENTED**. Maßgebliche Dateien sind `SUPABASE_GITHUB_TRANSFER_SPEC.md`, `SYNC_STATE_SPEC.md`, `GITHUB_ACTIONS_SPEC.md`, `SECURITY_AND_SECRETS.md`, `ARCHIVE_SPECIFICATION.md` und `REGRESSION_TESTS.md`. Audio-Synchronisation bleibt **PLANNED**.


### Zusätzliche Betriebsanleitung v0.15.24

- `docs/05_github/SUPABASE_RATINGS_ACTION_SETUP.md` – Einrichten des Secrets, erster Vollimport, Prüfung und Regelbetrieb der Bewertungssynchronisation.
