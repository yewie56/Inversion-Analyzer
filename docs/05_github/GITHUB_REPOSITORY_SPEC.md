# GitHub Repository Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Repository

Die aktuelle Remote-Archivkonfiguration verweist auf Owner `yewie56`, Repository `Inversion-Analyzer`, Branch `main`, Archivpfad `archive`.

## 2. Verzeichnisrollen

- `.github/workflows/`: Automatisierung.
- `inversion/`: Python-Paket.
- `archive/`: versionierte Laufzeitdaten, die Actions aktualisiert.
- `docs/`: Projektdokumentation.
- `cache/`, `logs/`, `output_inversion/`: grundsätzlich Runtime-/lokale Artefakte gemäß `.gitignore` prüfen.

## 3. Branch/Commit-Prinzip

Der vorhandene Workflow arbeitet direkt auf dem ausgecheckten Branch und besitzt `contents: write`. Archivänderungen werden mit Bot-Identität `inversion-collector` committed und gepusht. Für produktive Erweiterungen sind Branchschutz/Tokenrechte gegen den gewünschten Automationsbetrieb abzugleichen.

## 4. Versionierung

Softwareänderungen benötigen Versionsanhebung, Changelog und Regressionstest. Datenarchive ändern die Softwareversion nicht, tragen aber `app_version` im Manifest.
