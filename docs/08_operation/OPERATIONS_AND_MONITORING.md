# Operations and Monitoring

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Betriebsindikatoren

- GitHub Actions Run-Status.
- `source_status.json` pro Tag.
- `manifest.json` mit `complete`, `missing_sources`, Retry-Informationen.
- KIT `profile_count` und Coverage.
- Logs im lokalen `logs/`-Verzeichnis.

## 2. Regelbetrieb

Der Zeitplan läuft zweimal pro Stunde, vor allem um das kurze rollierende KIT-Profilfenster regelmäßig zu archivieren. Der Python-Server entscheidet, welche Quellen fällig sind.

## 3. Geplantes Monitoring

Actions soll nach Erweiterung eine kompakte Abschlussübersicht ausgeben: Archivtage aktualisiert, Diagramme erzeugt, Seismikstationen PASS/STALE/FAIL, Ratings neu/exportiert/ungültig, Commit ja/nein.


## Betrieb – Supabase Ratings

Normalbetrieb: Action `Supabase ratings sync` zweimal pro Stunde. Für den erstmaligen Import oder eine Reparatur kann `Run workflow` mit `full=true` gestartet werden. Ein Full-Lauf ist wegen der `event_id`-Deduplikation sicher wiederholbar.

Zu überwachen sind insbesondere: Action-Status, `archive/ratings/sync_state.json`, `last_rejected_count` und auffällige Lücken in `max_response_time_utc`.
