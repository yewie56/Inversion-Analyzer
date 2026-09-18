Inversion Analyzer v0.15.24
===========================

ZWECK
-----
Der Inversion Analyzer sammelt, archiviert und visualisiert Temperatur- und
Vertikalprofildaten fuer die Beurteilung von Inversionslagen. GUI und
Headless-Collector verwenden dasselbe Tagesarchiv. KIT-Mast, Radiosonde und
ICON-D2 werden als getrennte Zusatz-/Referenzreihen dargestellt und nicht
stillschweigend mit dem Hauptmodell vermischt.

START WINDOWS-GUI
-----------------
In Spyder oder aus Python:
    Inversionskurve.py

HEADLESS / SERVER
-----------------
Ein Tagesabruf:
    python Inversion_Server.py --date 2026-08-30

Heute:
    python Inversion_Server.py --today

Alle aktivierten Quellen bewusst neu pruefen:
    python Inversion_Server.py --date 2026-08-30 --force

Scheduled-Modus:
    python Inversion_Server.py --scheduled

Nur zentrales KITMast-Archiv fuer heute + gestern:
    python Inversion_Server.py --kit-only

Selbsttest:
    python Inversion_Server.py --selftest

ARCHIVSTRUKTUR
--------------
Standortbezogene Daten:
    archive/<Ort>/YYYY/MM/DD/

Beispiel Viernheim:
    archive/Viernheim/2026/08/30/manifest.json
    archive/Viernheim/2026/08/30/dwd_ground.csv
    archive/Viernheim/2026/08/30/openmeteo_profile.csv
    archive/Viernheim/2026/08/30/inversion_model.csv
    archive/Viernheim/2026/08/30/icon_d2.csv
    archive/Viernheim/2026/08/30/icon_d2_profile.csv
    archive/Viernheim/2026/08/30/source_status.json

KIT-Mast Karlsruhe seit v0.15.22 zentral und ortsunabhaengig:
    archive/KITMast/YYYY/MM/DD/

Typische Dateien dort:
    manifest.json
    kit_mast.csv
    kit_mast_info.json
    kit_mast_data.json
    source_status.json

KIT wird NICHT mehr fuer jeden Standort dupliziert. Standorte mit
"kit_reference": true lesen dieselbe zentrale KITMast-Tagesreihe.

STANDORTE / KIT-REFERENZ
------------------------
locations.json enthaelt die Ortsprofile.

Aktuell:
- Viernheim: KIT-Referenz aktiv
- Bremerhaven: KIT-Referenz aktiv
- Valencia: KIT-Referenz aus

Die Zuordnung erfolgt explizit ueber:
    "kit_reference": true

KIT bleibt eine Referenzreihe. Es beeinflusst die Kern-Datenqualitaet A/B/C/X
nicht und darf z.B. fuer Bremerhaven nicht als lokales Vertikalprofil
interpretiert werden.

GUI-LADEVERHALTEN v0.15.23
--------------------------
Beim Laden eines Tages:
1. lokales Standortarchiv lesen;
2. bei kit_reference=true die zentrale lokale KITMast-Referenz anhaengen;
3. fehlt nur die lokale KITMast-Referenz, wird dieser zentrale Tagesbestand
   aus dem konfigurierten GitHub-Raw-Archiv nachgeladen;
4. vorhandene Standort-Plotdaten bleiben dabei verwendbar;
5. ist das Standortarchiv selbst nicht brauchbar, wird wie bisher das
   Standort-Tagespaket aus GitHub geprueft und danach ggf. online aktualisiert.

Damit ist der v0.15.22-Regressionsfehler behoben, bei dem Inversionskurve.py
das zentrale KITMast-Archiv auf GitHub nicht nachlud.

EXPLIZITES GUI-UPDATE
---------------------
Der Button "Update" prueft die in den Einstellungen aktivierten Quellen.
Bei einem KIT-Referenzstandort bedeutet aktiviertes KIT seit v0.15.23:
    zentrales archive/KITMast/<Tag> aktualisieren
und NICHT:
    per-Location kit_mast erneut anlegen.

Vorhandene gute Daten werden durch fehlgeschlagene oder leere Abrufe nicht
stillschweigend geloescht.

KIT-RETRY / ROBUSTHEIT
----------------------
Die bestehende Bokeh-Robustheit bleibt erhalten. Standard aus
archive_config.json:
    kit_bokeh_timeout_seconds: 20
    kit_bokeh_max_attempts: 3
    kit_bokeh_retry_delays_seconds: [5, 15]

Weitere Eigenschaften:
- Diagnose-Logging
- fehlende Einzelhoehen werden toleriert, wenn noch >=2 gueltige Hoehen vorliegen
- kumulativer Safe-Merge nach Zeitstempel
- leere/fehlgeschlagene Abrufe loeschen keine vorhandenen KIT-Profile
- GitHub-Raw-Download des zentralen KITMast-Tages erfolgt in v0.15.23 zuerst
  in ein Staging-Verzeichnis und wird erst nach vollstaendigem Erfolg uebernommen

GITHUB ACTIONS
--------------
Workflow:
    .github/workflows/inversion_collect.yml

workflow_dispatch unterstuetzt:
    mode=normal
    mode=scheduled
    mode=kit-only

Fuer den regulaeren externen Collector wird empfohlen:
    location=ALL
    mode=scheduled
    force=false
    date=""

Scheduled bedeutet:
- zentrales KITMast-Archiv kontinuierlich aktualisieren;
- Standortarchive pruefen;
- fehlende/faellige Kernquellen gemaess Retry-Regeln nachladen;
- optionale KIT-/Sonden-Luecken loesen standardmaessig keinen Kern-Retry aus.

MACRODROID
----------
Fuer v0.15.23 ist KEINE Aenderung gegenueber v0.15.21/v0.15.22 erforderlich.
Der JSON-Body bleibt:

{
  "ref": "main",
  "inputs": {
    "location": "ALL",
    "mode": "scheduled",
    "force": "false",
    "date": ""
  }
}

Der GitHub-API-Endpunkt und die bereits eingerichteten Header bleiben
unveraendert. Zugangstoken nicht in Projektdateien oder Logs speichern.

REMOTE-GITHUB-ARCHIV IN DER GUI
-------------------------------
archive_config.json:

"remote_archive": {
  "enabled": true,
  "provider": "github_raw",
  "owner": "yewie56",
  "repository": "Inversion-Analyzer",
  "branch": "main",
  "archive_path": "archive"
}

Das Repository muss fuer GitHub Raw ohne interaktiven Login lesbar sein.
Fehler werden protokolliert und nicht durch erfundene Ersatzdaten kaschiert.

DATENQUALITAET
--------------
Kernquellen und optionale Referenzen bleiben getrennt. Fuer deutsche
Standorte sind DWD/Vertikalprofil/ICON-D2 die Kernlogik entsprechend der
aktuellen Konfiguration. KIT-Mast und Radiosonde sind Zusatz-/Referenzquellen
und machen einen sonst vollstaendigen Tag nicht unvollstaendig.

UPDATE / RELEASE
----------------
Der passende Update-Batch ist seit v0.15.22 Bestandteil jedes Versions-ZIPs.
Fuer diese Version:
    Update_Inversion_Analyzer_v0.15.24.bat

ZIP und Batch koennen z.B. in folgendem Upload-Ordner liegen:
    C:\Users\user\AnacondaProjects\InversionsTrendUpload

Start:
    .\Update_Inversion_Analyzer_v0.15.24.bat

Der Batch sucht das eigentliche Git-Repository automatisch, prueft Repo und
Branch, fuehrt Fetch/Rebase und Regressionstests aus, staged keine Runtime-
Archive/Logs/Cache-Dateien und verwendet keinen Force-Push.

ABHAENGIGKEITEN
---------------
    pip install requests pandas numpy matplotlib bokeh

WICHTIG
-------
Der oeffentliche KIT-Bokeh-Profilserver liefert nur einen begrenzten rollenden
Ausschnitt. Profile, die nicht rechtzeitig archiviert wurden, koennen spaeter
nicht mehr ueber diese Quelle rekonstruierbar sein. Deshalb ist die haeufige
kumulative KITMast-Archivierung wesentlich.

SUPABASE-BEWERTUNGEN v0.15.24
-----------------------------

Neu ist ein separater GitHub-Actions-Workflow:

    .github/workflows/supabase_ratings_sync.yml

Er liest subjektive Bewertungen aus der Supabase-Tabelle observations und
archiviert sie idempotent entlang der UTC-Zeitachse unter:

    archive/ratings/JJJJ/MM/JJJJ-MM-TT/ratings.jsonl
    archive/ratings/JJJJ/MM/JJJJ-MM-TT/summary.json
    archive/ratings/sync_state.json

Automatischer Start: Minute 12 und 42 jeder Stunde. Damit liegt der Lauf jeweils
fuenf Minuten hinter dem Wetter/KIT-Collector (:07/:37).

GitHub Repository Secret erforderlich:

    SUPABASE_SECRET_KEY

Bevorzugt wird ein aktueller Supabase Secret Key (sb_secret_...). Als
Kompatibilitaetsfallback wird SUPABASE_SERVICE_ROLE_KEY unterstuetzt. Der Key
wird nur zur Laufzeit aus der GitHub-Secrets-Umgebung gelesen und nie
archiviert.

Datenschutz-Default:
- kein Klartext-Teilnehmerschluessel im GitHub-Archiv
- observer_id bleibt als pseudonyme Kennung erhalten
- GPS wird auf zwei Nachkommastellen abgeschnitten
- Kommentartext wird nicht exportiert; nur has_comment
- Audio bleibt vorerst in Supabase

Erster Testlauf in GitHub:
Actions -> Supabase ratings sync -> Run workflow -> full=true

Ein Full-Lauf liest den gesamten Bestand, merged aber weiterhin ueber event_id
idempotent. Spaetere regulaere Laeufe verwenden ein 48-h-Ueberlappungsfenster.

