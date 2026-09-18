# Supabase Ratings Action – Einrichtung und erster Lauf

Projektstand: Inversion Analyzer v0.15.25  
Status: IMPLEMENTED

## 1. Zweck

Der Workflow `.github/workflows/supabase_ratings_sync.yml` holt subjektive Bewertungen aus der Supabase-Tabelle `observations` und schreibt eine datenschutzreduzierte Archivkopie nach GitHub.

## 2. Einmalig erforderliches GitHub Secret

Im GitHub-Repository:

1. `Settings` öffnen.
2. `Secrets and variables` → `Actions` öffnen.
3. `New repository secret` wählen.
4. Name: `SUPABASE_SECRET_KEY`.
5. Als Wert einen aktuellen Supabase-Backend-Secret-Key (`sb_secret_...`) eintragen.
6. Secret speichern.

Der Secret-Key darf niemals in `ratings_sync_config.json`, YAML, Python-Code, Logs oder Dokumentation eingetragen werden.

Ein vorhandener alter `service_role`-Key kann über das Secret `SUPABASE_SERVICE_ROLE_KEY` vorübergehend weiterverwendet werden. `SUPABASE_SECRET_KEY` ist der bevorzugte Weg.

## 3. Supabase-Projekt und Tabelle

Default in `ratings_sync_config.json`:

```json
{
  "supabase_url": "https://kbejualnruiwtnmeytif.supabase.co",
  "table": "observations"
}
```

Die URL kann bei Bedarf durch die Actions-Umgebungsvariable bzw. das GitHub Secret `SUPABASE_URL` überschrieben werden.

## 4. Erster Vollimport

1. GitHub-Repository öffnen.
2. `Actions` öffnen.
3. Workflow `Supabase ratings sync` wählen.
4. `Run workflow` anklicken.
5. `full = true` einstellen.
6. Workflow starten.
7. Nach erfolgreichem Lauf prüfen, ob `archive/ratings/` angelegt wurde.

Erwartet:

```text
archive/ratings/
├── sync_state.json
└── YYYY/MM/YYYY-MM-DD/
    ├── ratings.jsonl
    └── summary.json
```

## 5. Automatischer Betrieb

Der Workflow startet bei Minute 12 und 42 jeder Stunde. Der Wetter-/KIT-Collector startet bei Minute 07 und 37. Beide verwenden die gemeinsame Concurrency-Gruppe `inversion-archive-writer`, sodass niemals zwei Archivschreiber gleichzeitig laufen.

## 6. Inkrementeller Betrieb

Nach dem ersten Import liest der Sync nicht bei jedem Lauf die gesamte Tabelle. Er verwendet `max_response_time_utc` aus `sync_state.json` und geht standardmäßig 48 Stunden zurück. Danach werden alle gefundenen Datensätze über `event_id` idempotent in die Tagesdateien gemerged.

Dadurch werden insbesondere verspätete Offline-Uploads nachgeholt.

## 7. Datenschutz im Default

Nach GitHub werden übertragen:

- `event_id`,
- pseudonyme `observer_id`,
- `scheduled_time_utc`,
- `response_time_utc`,
- `rating`,
- auf zwei Dezimalstellen abgeschnittene Koordinaten,
- `app_version`,
- `has_comment`.

Nicht übertragen werden:

- Teilnehmerschlüssel,
- exakte GPS-Koordinaten,
- Kommentartext,
- Audio.

## 8. Manuelle lokale Prüfung

Ohne Secret kann der Regressionstest ausgeführt werden:

```text
python test_supabase_ratings_sync_v0_15_24.py
```

Für einen realen lokalen Supabase-Abruf muss `SUPABASE_SECRET_KEY` nur für den aktuellen Prozess gesetzt sein. Er darf nicht in eine Projektdatei geschrieben werden.

## 9. Erfolgskriterien

Der erste reale GitHub-Lauf gilt als erfolgreich, wenn:

- der Regressionstest PASS meldet,
- der Supabase-Abruf keine verworfenen Datensätze meldet,
- `ratings.jsonl` erzeugt wird,
- `summary.json` zur Anzahl der importierten Bewertungen passt,
- ein zweiter Full-Lauf keine Duplikate erzeugt,
- ein normaler Folgelauf nur notwendige Änderungen committed.
