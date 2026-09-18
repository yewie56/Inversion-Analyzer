# Data and File Format Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Standort-Tagesarchiv

Pfad: `archive/<LocationSlug>/YYYY/MM/DD/`

Typische CSV-Dateien:

- `dwd_ground.csv`
- `aemet_ground.csv`
- `openmeteo_profile.csv`
- `inversion_model.csv`
- `radiosonde_profile.csv`
- `radiosonde_metrics.csv`
- `icon_d2.csv`
- `icon_d2_profile.csv`

Typische JSON-Dateien:

- `manifest.json`
- `source_status.json`
- `station_info.json`
- `sonde_profiles.json`
- `sonde_flights.json`
- `icon_d2_info.json`

Bei `kit_reference=true` werden KIT-Dateien nicht im Standortordner dupliziert.

## 2. Globales KIT-Referenzarchiv

Pfad: `archive/KITMast/YYYY/MM/DD/`

- `kit_mast.csv`
- `kit_mast_info.json`
- `kit_mast_data.json` (falls vorhanden)
- `source_status.json`
- `manifest.json`

## 3. Manifest

Standortmanifeste verwenden derzeit `schema_version: 1` und enthalten u. a. `app_version`, Location-Metadaten, Datum, `saved_at`, `run_id`, Qualitätsklasse, Vollständigkeit, Kern-/optionale Quellen, Retry-Information und Dateizuordnung.

## 4. PLANNED Datenprodukte

Empfohlene Struktur:

```text
archive/<Ort>/YYYY/MM/DD/products/
  inversion_diagram.png
  inversion_diagram.svg            # optional
  inversion_diagram_metadata.json

archive/Seismic/<Station>/YYYY/MM/DD/
  source_image.png                  # falls Originalprodukt
  seismic_diagram.png               # falls selbst erzeugt
  metadata.json
  raw/...                           # falls Rohdaten zulässig/verfügbar

archive/Ratings/YYYY/MM/DD/
  ratings.jsonl                     # oder CSV; Entscheidung vor Implementierung fixieren
  sync_manifest.json
```

Numerische Daten sind vorrangig; Bilder sind reproduzierbare Ansichten.


## Rating JSONL v1.0 (IMPLEMENTED ab v0.15.24)

Beispielstruktur:

```json
{
  "schema_version": "1.0",
  "event_id": "UUID",
  "observer_id": "BB001",
  "scheduled_time_utc": "2026-09-18T20:00:00.000Z",
  "response_time_utc": "2026-09-18T20:00:12.000Z",
  "rating": 3,
  "location": {
    "available": true,
    "latitude": 49.54,
    "longitude": 8.57,
    "precision": "truncated_2dp"
  },
  "app_version": "0.4.84",
  "has_comment": false,
  "source": "LFN-Scout/Supabase"
}
```

Der Kommentartext wird im Default nicht exportiert. Die genauen Supabase-Koordinaten werden im Default ebenfalls nicht exportiert.
