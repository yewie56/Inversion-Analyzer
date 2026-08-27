AEMET-INTEGRATION – Inversion Analyzer v0.15.9

Valencia nutzt AEMET Station 8416 (València) als reale Bodenmessung.

PowerShell:
  $env:AEMET_API_KEY = "DEIN_API_KEY"
  $env:INVERSION_LOCATION = "Valencia"

Prüfen:
  python Inversion_Server.py --selftest
  python Inversion_Server.py --show-config
  python Inversion_Server.py --today --force

Erwartet in --show-config:
  aemet: true
  aemet_station_id: 8416
  aemet_api_key_present: true

AEMET liefert über die Beobachtungs-API nur aktuelle/recent Stundenwerte.
Daher sammelt der Scheduled-Lauf alle 3 Stunden heute und gestern und merged
die Werte kumulativ nach Zeitstempel in aemet_ground.csv.

Ohne API-Key:
- Open-Meteo funktioniert weiter.
- AEMET wird als NO_API_KEY protokolliert.
- Valencia bleibt Qualität C.

Mit AEMET-Daten:
- Qualität B: AEMET-Bodenmessung + vertikales Modell-/Archivprofil.

GitHub:
Repository -> Settings -> Secrets and variables -> Actions
Neues Repository Secret:
  AEMET_API_KEY

Der Key wird nicht in Archiv oder Konfigurationsdateien gespeichert.
