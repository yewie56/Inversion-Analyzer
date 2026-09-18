# Archive Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Prinzipien

- Das Archiv ist die gemeinsame Wahrheit für GUI und Headless-Betrieb.
- Standorttage und globale KIT-Referenz sind getrennt.
- Teilabrufe dürfen nicht angeforderte Dateien nicht verändern.
- Ein fehlgeschlagener/leer zurückgegebener Abruf löscht keine gute bestehende Quelle.
- `manifest.json` und `source_status.json` dürfen nach Retry aktualisiert werden.

## 2. Vollständigkeit

Standard-Kernquellen aus `archive_config.json`: `dwd`, `profile`, `icon_d2`. Optionale Quellen: `sonde`, `kit_mast`. Standorte können dies überschreiben; Valencia nutzt beispielsweise nur `profile` als Completion-Source und `aemet` optional.

## 3. KIT

Seit v0.15.22: `archive/KITMast/...` ist global. `kit_reference=true` bindet dieses Referenzarchiv an einen Ort an, ohne per-Location-Duplikation.

## 4. Remote-Fallback

Fehlende Tage können aus GitHub Raw nachgeladen werden. Der KIT-Referenzdownload wird seit v0.15.23 zunächst in ein Staging-Verzeichnis geladen und erst bei vollständigem Erfolg übernommen.

## 5. Geplante Archive

Seismik und Ratings erhalten eigene Namespaces, damit sie nicht mit standortbezogenen meteorologischen Kerndaten verwechselt werden.


## Bewertungsarchiv ab v0.15.24 (IMPLEMENTED)

```text
archive/ratings/
├── sync_state.json
└── YYYY/MM/YYYY-MM-DD/
    ├── ratings.jsonl
    └── summary.json
```

`ratings.jsonl` enthält pro Zeile genau eine kanonische Bewertung. `event_id` ist eindeutig. Die Datei ist deterministisch nach `response_time_utc`, danach `event_id`, sortiert. `summary.json` enthält Tag, Anzahl Bewertungen, Anzahl pseudonymer Beobachter sowie getrennte Häufigkeiten für `-1,0,1,2,3,4,5`.
