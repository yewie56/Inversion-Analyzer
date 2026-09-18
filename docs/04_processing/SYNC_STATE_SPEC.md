# Synchronization State Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Ziel

Der Supabase→GitHub-Transfer muss exakt nachvollziehbar und idempotent sein.

## 2. Empfohlener Zustand

`archive/Ratings/sync_state.json` oder ein äquivalentes Manifest enthält:

- `schema_version`,
- `last_successful_sync_at_utc`,
- `high_water_mark` (z. B. monotoner Schlüssel/Zeit + ID),
- `exported_record_count`,
- Hash der zuletzt geschriebenen Exportdatei,
- letzte erfolgreiche Workflow-Run-ID,
- optional letzte geprüfte ID.

## 3. Idempotenz

Ein identischer Workflow-Lauf darf denselben GitHub-Stand erzeugen wie ein einzelner Lauf. Dazu wird nicht nur auf Zeitstempel, sondern auf stabile Datensatz-IDs dedupliziert.

## 4. Fehlerfall

Der Sync-State wird **erst nach** erfolgreicher Exportvalidierung und erfolgreichem Schreibvorgang fortgeschrieben. Bei Abbruch bleibt die letzte bestätigte High-Water-Mark erhalten.


## Rating-Sync-State v0.15.24 (IMPLEMENTED)

Datei: `archive/ratings/sync_state.json`. Sie enthält u. a. `last_successful_sync_utc`, `query_since_utc`, `max_response_time_utc`, `archive_event_count`, letzte Fetch-/Reject-Zahlen, Tabellenname und Datenschutzmodus.

Der State ist nur ein Beschleuniger. Konsistenz wird durch die eindeutige `event_id` und das idempotente Merge der Tagesdateien gesichert.
