# Backup and Recovery

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Zu sichernde Bestandteile

- Git-Repository inklusive vollständiger History.
- `archive/` einschließlich globalem KITMast.
- `locations.json`, `archive_config.json`.
- GitHub Actions Workflow(s).
- dokumentierte Liste der GitHub Secrets (nur Namen/Zweck, **nicht Secret-Werte**).
- Supabase-Datenbank separat über geeigneten Supabase-Backupweg; GitHub-Export ersetzt kein Datenbankbackup.

## 2. Recovery-Reihenfolge

1. Repository wiederherstellen/klonen.
2. Python-Umgebung herstellen.
3. Konfiguration prüfen.
4. Archivintegrität prüfen.
5. Actions aktivieren und Secrets neu setzen.
6. manuellen Selftest/Dispatch ausführen.
7. erst danach Schedule freigeben.

## 3. Datenschutz

Backupmedien mit Bewertungs-/Nutzerdaten sind entsprechend ihrer Sensitivität zu schützen. Öffentliche Git-Repositories sind kein Backupziel für geheime oder personenbezogene Rohdaten.
