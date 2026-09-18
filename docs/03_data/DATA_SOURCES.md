# Data Sources

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Implementierte Quellen

| Quelle | Verwendung | Endpunkt/Quelle im Code | Status |
|---|---|---|---|
| DWD 10-min Lufttemperatur | Bodenmessung DE | `opendata.dwd.de/.../10_minutes/air_temperature/now/` | IMPLEMENTED |
| Open-Meteo Forecast/Archive | Vertikalprofil | `api.open-meteo.com`, `archive-api.open-meteo.com`, historical forecast | IMPLEMENTED |
| ICON-D2 via Open-Meteo | separates Modellprodukt | `historical-forecast-api.open-meteo.com`, Modell `icon_d2` | IMPLEMENTED |
| DWD Radiosonde | hochaufgelöste Sondenprofile | DWD CDC high_resolution recent/historical | IMPLEMENTED |
| KIT 200-m-Mast Karlsruhe | gemessene Referenzprofile | `tsm.atmohub.kit.edu` Bokeh-Plotserver | IMPLEMENTED |
| AEMET | optionale Bodenmessung Spanien | API-Key über `AEMET_API_KEY` | IMPLEMENTED optional |
| Open-Meteo Geocoding | Ortsauflösung | `geocoding-api.open-meteo.com/v1/search` | IMPLEMENTED |
| GitHub Raw | Remote-Archiv-Fallback | owner/repository/branch aus `archive_config.json` | IMPLEMENTED |

## 2. Konfigurierte Orte (unverändert in v0.15.24)

- Viernheim: DE, KIT-Referenz aktiv.
- Bremerhaven: DE, KIT-Referenz aktiv.
- Valencia: Open-Meteo Kernprofil, AEMET optional, KIT/ICON-D2/DWD/Radiosonde deaktiviert.

## 3. PLANNED Seismik

Seismik wird als eigene Quellklasse dokumentiert. Pro Station sind mindestens zu konfigurieren: Betreiber, Station-ID, URL/API, Produktart (fertiges Bild/Rohdaten), Zeitzone, Aktualisierungsintervall, erwartetes Tagesdatum, Format, Hash/Größe und Fallback. Konkrete Stationslisten sind bei Implementierung in Konfiguration + Testdaten festzuschreiben.

## 4. IMPLEMENTED Supabase-Bewertungen

Supabase ist keine Messdatenquelle der Inversionsberechnung, sondern die Intake-/Pufferquelle für subjektive Bewertungen. v0.15.24 liest die Tabelle `observations` serverseitig über den Actions-Workflow `supabase_ratings_sync.yml`; Zugang erfolgt ausschließlich über GitHub Secrets. Exportfelder und Datenschutzabbildung sind in `SUPABASE_GITHUB_TRANSFER_SPEC.md` definiert. Audio bleibt in dieser Version außerhalb des Imports.
