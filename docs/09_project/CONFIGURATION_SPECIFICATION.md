# Configuration Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. `locations.json`

Steuert aktive Location und pro Ort u. a. Koordinaten, Zeitzone, Höhe, Land, DWD-Distanz, Radiosonden-WMO, KIT-Referenz, ICON-D2/DWD/AEMET-Aktivierung sowie Completion-/Optional-Sources.

Aktive Location kann zur Laufzeit über `INVERSION_LOCATION` überschrieben werden; unbekannte Schlüssel führen zu einem Fehler.

## 2. `archive_config.json`

Wesentliche Werte v0.15.23:

- `archive_dir = archive`
- `auto_fetch_missing = true`
- GitHub Raw: `yewie56/Inversion-Analyzer`, Branch `main`, Pfad `archive`
- `daily_fetch_local_hour = 22`
- `retry_delay_hours = 3`
- `max_retries = 5`
- `completion_sources = [dwd, profile, icon_d2]`
- `optional_sources = [sonde, kit_mast]`
- `retry_optional_sources = false`
- KIT continuous archive = true
- Bokeh Timeout 20 s, Versuche 3, Delays 5/15 s.

## 3. `settings.json`

Enthält GUI-Geometrie, User-Mode, sichtbare Reihen, Update-Quellen und Advanced-Anzeigen. Auffälligkeit im gelieferten Stand: das Feld `version` steht auf `0.14.0`, obwohl die Softwareversion `0.15.23` ist. Vor einer Nutzung als Migrationsschema muss geklärt werden, ob dieses Feld App-Version oder Settings-Schema meint.

## 4. PLANNED

Seismikstationen und spätere Audioanalyse sollen in eigenen versionierten Konfigurationsblöcken/-dateien liegen. Der Bewertungssync verwendet `ratings_sync_config.json`; Secret-Werte gehören ausdrücklich nicht in diese Datei.
