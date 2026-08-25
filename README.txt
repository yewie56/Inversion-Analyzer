Inversionskurve v0.15.2
=========================

START WINDOWS-GUI
-----------------
Nur:
    Inversionskurve.py

HEADLESS / SERVER
-----------------
Ein Tagesabruf:
    python Inversion_Server.py --date 2026-08-24

Heute:
    python Inversion_Server.py --today

Alle Quellen bewusst neu:
    python Inversion_Server.py --date 2026-08-24 --force

GitHub-Scheduler-Modus:
    python Inversion_Server.py --scheduled

ARCHITEKTUR
-----------
1. Gemeinsame Quellen- und Rechenmodule
2. Lokales Tagesarchiv
3. Windows-GUI als Archiv-Browser
4. Headless-CLI für Server/GitHub/Windows
5. Optionales Remote-GitHub-Archiv
6. Später kann eine Android-GUI dasselbe Archivformat verwenden.

GUI-ABLAUF
----------
Beim Laden eines Tages:
1. lokales Archiv prüfen
2. wenn nicht vollständig: optional Remote-GitHub-Archiv prüfen
3. fehlen weiterhin Quellen: nur fehlende Quellen online nachladen
4. Tagespaket lokal archivieren
5. anzeigen

Mit "Online neu abrufen" kann bewusst ein kompletter Neuabruf erzwungen werden.

ARCHIV
------
archive/<Ort>/YYYY/MM/DD/

Beispiele:
    manifest.json
    dwd_ground.csv
    openmeteo_profile.csv
    inversion_model.csv
    kit_mast.csv
    icon_d2.csv
    station_info.json
    sonde_profiles.json
    kit_mast_info.json
    source_status.json

manifest.json enthält u.a.:
- Ort und Datum
- Programmversion
- RUN-ID
- Datenqualität
- complete
- missing_sources
- attempts
- last_attempt
- Dateien des Tagespakets

Vorhandene gute Quellen werden bei einem Reparaturlauf nicht stillschweigend
überschrieben. Der Teilabruf ersetzt nur die ausdrücklich fehlenden Quellen.

ORTE
----
locations.json enthält Ortsprofile.
Aktiver Ort:
    "active": "Viernheim"

Alternativ:
    set INVERSION_LOCATION=Viernheim

Damit kann derselbe Code später für mehrere Orte verwendet werden.
KIT kann pro Ort mit kit_mast_enabled ein-/ausgeschaltet werden.

GITHUB ACTIONS
--------------
Workflow:
    .github/workflows/inversion_collect.yml

Er unterstützt:
- manuellen Start über "Run workflow"
- optionales Datum
- Force-Neuabruf
- automatischen Scheduler-Check alle 3 Stunden

Der Scheduler läuft nur kurz. Das Python-Skript entscheidet selbst, ob
wirklich Daten abgerufen werden müssen.

Parameter in archive_config.json:
    daily_fetch_local_hour
    retry_delay_hours
    max_retries
    retry_only_missing
    required_sources

Standard:
    Tages-Erstabruf ab 22 Uhr Ortszeit
    Retry-Abstand 3 h
    maximal 5 Versuche
    nur fehlende Quellen

GitHub Actions benötigt kein GitHub-Passwort im Skript. Der Workflow benutzt
das von GitHub bereitgestellte GITHUB_TOKEN und hat nur contents: write.

REMOTE-ARCHIV IN DER GUI
------------------------
archive_config.json:

"remote_archive": {
  "enabled": true,
  "provider": "github_raw",
  "owner": "DEIN_GITHUB_NAME",
  "repository": "DEIN_REPOSITORY",
  "branch": "main",
  "archive_path": "archive"
}

Diese v0.15.2-Implementierung verwendet dafür GitHub Raw und ist daher für ein
öffentlich lesbares Repository gedacht. Für private Repositories wird später
der geplante laienfreundliche GitHub-Login/Setup-Assistent ergänzt.

WICHTIG ZU KIT
--------------
Die momentan erschlossene KIT-Bokeh-Profilseite liefert nur einen aktuellen
Ausschnitt. Das Archiv ist deshalb besonders wichtig: einmal gespeicherte
KIT-Daten bleiben lokal/GitHub erhalten. Ein einmaliger Tagesabruf kann jedoch
nur die KIT-Profile sichern, die zu diesem Abrufzeitpunkt auf der Seite
verfügbar sind. Eine vollständigere KIT-Tageshistorie würde einen häufigeren
KIT-Sammellauf oder eine weitere historische KIT-Schnittstelle erfordern.

ABHÄNGIGKEITEN
---------------
pip install requests pandas numpy matplotlib bokeh

v0.15.2 verändert die Berechnung der bestehenden Modell-, KIT- und ICON-D2-
Kurven nicht absichtlich. Schwerpunkt dieser Version ist Archivierung,
Headless-Betrieb, Teil-Reparatur und GitHub-Ausführung.


KORREKTUR v0.15.2
-----------------
GUI:
- -7 / -1 / +1 / +7: nur lokales Archiv
- "Archiv laden": nur lokales Archiv
- kein automatischer Internetabruf
- "Update": expliziter Internetabruf

KIT-ARCHIVSCHUTZ:
Vorhandene KIT-Profile werden niemals durch einen kleineren oder leeren
Neuabruf gelöscht. Neue Profile werden nach Zeitstempel ergänzt.

ARCHIV AUS v0.12.0 WEITERVERWENDEN:
Ja. Das Format bleibt kompatibel.

Wenn v0.15.2 in einen neuen Ordner entpackt wird, bitte den vorhandenen
Ordner "archive" aus dem v0.12.0-Projekt unverändert in den
v0.15.2-Projektordner kopieren.


ICON-D2-KORREKTUR v0.15.2
-------------------------
Die bisherige ICON-D2-Auswertung betrachtete nur Druckflächen untereinander.
Dadurch konnte eine bodennahe Inversion vollständig übersehen werden.

Neu:
- temperature_2m wird als unterster Profilpunkt bei 2 m AGL verwendet.
- Open-Meteo liefert die Punkthöhe über NN.
- geopotential_height_<p>hPa wird in Höhe über Grund umgerechnet:
      height_agl = geopotential_height_msl - elevation
- Druckflächen bei/unter 2 m AGL werden nicht für die Inversionsberechnung
  benutzt.
- Die vollständigen Rohprofile werden zusätzlich archiviert:
      icon_d2_profile.csv

Spalten von icon_d2_profile.csv:
- time
- level_type
- pressure_hPa
- height_msl_m
- height_agl_m
- temperature_C
- usable_for_inversion

Damit kann jede einzelne Stunde physikalisch nachvollzogen werden.

Das bestehende Archiv aus v0.12.0/v0.12.1 bleibt verwendbar.
Für bereits archivierte Tage wird icon_d2_profile.csv erst beim nächsten
expliziten "Update" ergänzt.


KORREKTUR v0.15.2 – ARCHIVANZEIGE
---------------------------------
Beim Steppen wird weiterhin ausschließlich das lokale Archiv gelesen.

Neu:
- CSV-Zeitspalten werden robust eingelesen und auf Europe/Berlin normalisiert.
- Vor dem Plotten werden alle relevanten DataFrames noch einmal validiert.
- Das Diagramm wird VOR Zusammenfassung und Datenquellen-Text aufgebaut.
- Fehler in Summary oder Quellenstatus verhindern den Plot nicht mehr.
- Im Log stehen jetzt:
    Archivdateien gefunden: Modell=... | KIT=... | ICON-D2=...
    Anzeige-Diagnose: Modell=... | KIT=... | ICON-D2=...
    Plotdaten: Modell=... | KIT=... | ICON-D2=...
    Archiv-Plot: PASS/FEHLER
- Falls ein Archiv vorhanden, aber nicht darstellbar ist, wird dies explizit gemeldet.
- Fehlt ein Tag ganz, bleibt der bisherige Plot zur Orientierung sichtbar.

Das bestehende Archiv aus v0.12.0–v0.12.2 weiterverwenden.
Es ist keine Archivkonvertierung erforderlich.


STEPPING-LOGIK v0.15.2
----------------------
Beim Wechsel eines Tages:

1. Lokales Archiv prüfen.

2. Sind dort darstellbare Plotdaten vorhanden
   (Modell oder KIT oder ICON-D2):
       -> sofort anzeigen
       -> kein automatischer Internetabruf

3. Sind keine darstellbaren Plotdaten vorhanden:
       -> alten Plot sofort löschen
       -> einmal automatisch Update starten
       -> Ergebnis archivieren

4. Wenn auch nach dem Update keine darstellbaren Plotdaten vorhanden sind:
       -> Plot bleibt leer
       -> klare Meldung "Keine Daten für diesen Tag verfügbar"

Teilarchive:
Wenn z.B. Modell + ICON-D2 vorhanden sind, aber DWD/KIT/Sonde fehlen,
werden die vorhandenen Kurven angezeigt. Ein automatisches Update findet
dann NICHT statt. Fehlende Zusatzquellen können über "Update" nachgeladen
werden.

Der KIT-Archivschutz aus v0.12.1 bleibt unverändert aktiv.


KORREKTUR v0.15.2
-----------------
Behoben:
AttributeError:
'_tkinter.tkapp' object has no attribute '_update_source_status'

Die Quellenanzeige aktualisiert wieder:
DWD Boden, Vertikalprofil, Idar-Oberstein, KIT 200-m-Mast und ICON-D2.


NEU v0.15.2
-----------
DATENQUELLEN-LOG IM TAGESARCHIV

Jeder Speichervorgang ergänzt im Archiv des betreffenden Tages die Datei:

    sources.log

Bestehende Einträge bleiben erhalten. Neue Einträge werden angehängt und mit
langen ========-Trennzeilen abgegrenzt.

Pro Eintrag werden DWD Boden, Vertikalprofil, Idar-Oberstein, KIT 200-m-Mast
und ICON-D2 Historical mit Status, Meldung, Details, Zeilenanzahl, letztem
Versuch und letztem Erfolg gespeichert. Datenqualität und Qualitätstext werden
ebenfalls protokolliert.

FESTE KURVENFARBEN

    KIT 200-m-Mast : orange
    ICON-D2        : grün

Für KIT und ICON-D2 wird keine automatische Matplotlib-Farbe mehr verwendet.


NEU v0.15.2 – RADIOSONDE ALS MESSKURVE
--------------------------------------
Quelle:
DWD CDC Radiosonden, high_resolution
Idar-Oberstein: DWD Stations-ID 02385, WMO 10618.

Aktuelle Daten:
radiosondes/high_resolution/recent/sekundenwerte_aero_02385_akt.zip

Historische Daten:
radiosondes/high_resolution/historical/<Jahr>/
Das konkrete Jahres-ZIP wird aus dem offiziellen DWD-Verzeichnis ermittelt.

Verarbeitung:
- große ZIP-Datei wird streamingbasiert in den lokalen Cache geladen;
- aus dem ZIP wird nur der ausgewählte lokale Tag übernommen;
- Zeit, Temperatur und Höhe werden tolerant anhand der DWD-Spalten erkannt;
- einzelne Aufstiege werden durch Zeitlücken getrennt;
- niedrigstes plausibles Startniveau wird je Aufstieg als AGL-Referenz verwendet;
- Auswertung bis 2500 m AGL;
- 25-m-Höhenklassen;
- 3-Bin-Median zur Unterdrückung von Sekundenrauschen;
- positiver Temperaturgradient, ΔT, Inversionstiefe, Basis/Obergrenze;
- separater empirischer Radiosondenindex 0–5.

Archiv:
radiosonde_profile.csv  = gemessene Rohprofile des Tages
radiosonde_metrics.csv  = Inversionskennwerte je Aufstieg

Die Radiosonde liegt in Idar-Oberstein und ist deshalb eine räumlich entfernte
Messreferenz. Sie wird NICHT mit dem ortsbezogenen Viernheim-Modell oder
ICON-D2 gemittelt.

Feste Farben:
Modell-/DWD-Inversionsindex  = blau
Modellgradient               = grau
KIT-Mast                     = orange
ICON-D2                      = grün
Radiosonde Idar-Oberstein    = rot


KORREKTUR v0.15.2 – RADIOSONDEN-PARSER/DIAGNOSE
-----------------------------------------------
Der DWD-Download selbst funktionierte in v0.13.0, aber ein reales ZIP konnte
ohne sichtbare Parserdiagnose zu 0 Radiosondenprofilen führen.

v0.15.2 protokolliert deshalb beim Radiosondenimport ausdrücklich:

- Anzahl und Namen der ZIP-Member
- Größe der Kandidaten
- kurze Headerprobe
- erkanntes Encoding
- erkannten Separator
- erkannte Header-Spalten
- Zuordnung Zeit / Temperatur / Höhe / Druck
- tatsächlich gewählte Messdatei
- Gesamtzahl gelesener Datenzeilen
- Zahl der Zeilen des ausgewählten lokalen Tages
- gültige Messzeilen
- erkannte Aufstiege und Rohpunkte je Aufstieg
- abschließenden Radiosondenstatus

Der Parser akzeptiert nun Semikolon, Tab, Komma, Pipe und
Whitespace-separierte DWD-Dateien und ist nicht mehr auf .txt/.csv/.dat
als Dateiendung beschränkt.

Kann kein echtes Zeit-/Temperatur-/Höhenprofil erkannt werden, wird dies als
FORMAT_CHANGED im Hauptlog sichtbar. Es wird keine Nullkurve erzeugt.

WICHTIG:
Der bereits vorhandene lokale Radiosonden-ZIP-Cache wird weiter benutzt.
Beim Wechsel in einen neuen Projektordner kann der vorhandene cache-Ordner
mit übernommen werden, damit die rund 100-MB-Datei nicht erneut geladen
werden muss.


KORREKTUR v0.15.2 – REALES DWD HIGH-RESOLUTION-FORMAT
-----------------------------------------------------
Die Diagnose aus v0.13.1 zeigte den echten DWD-Header:

STATIONS_ID
BEZUGSDATUM_SYNOP
MESSZEITPUNKT
QN_1
AE_GB_POS
AE_GL_POS
AE_GPM
AE_P
AE_TT
AE_TD
AE_FF
AE_DD
AE_RF

v0.15.2 verwendet deshalb explizit:

AE_TT   = Lufttemperatur
AE_P    = Luftdruck
AE_GPM  = geopotentielle Höhe

ZEITBILDUNG:
BEZUGSDATUM_SYNOP enthält die synoptische Startzeit in UTC,
z.B. 2026010106 = 01.01.2026 06:00 UTC.

MESSZEITPUNKT enthält die Sekunden seit Start:
0, 2, 4, ...

Der reale Messzeitpunkt wird daher gebildet als:

BEZUGSDATUM_SYNOP + MESSZEITPUNKT Sekunden

und anschließend nach Europe/Berlin umgerechnet.

DATEINAMEN-KURZSCHLUSS:
Bei Dateien der Form

produkt_sec_aero_20260101_20260824_02385.txt

wird der enthaltene Datenzeitraum bereits aus dem Dateinamen gelesen.
Wird z.B. 2026-08-25 angefordert, meldet das Programm sofort:

NO_DATA_DATE

weil diese konkrete Datei nur bis 2026-08-24 reicht.
Dadurch muss die entpackte, sehr große Messdatei nicht unnötig vollständig
durchlaufen werden.

METADATEN:
Wenn eine echte produkt_sec_aero-Datei vorhanden ist, wird diese direkt
verwendet. Metadaten-Dateien werden dann nicht mehr als mögliche Messdateien
durchprobiert.

Der bestehende große Radiosonden-ZIP-Cache kann weiterverwendet werden.


NEU v0.15.2 – DATENQUALITÄTSKLASSEN IM PLOT UND IN DER GUI
----------------------------------------------------------
Die Definition der Datenqualitätsklassen ist jetzt direkt in die Anzeige
integriert.

GUI:
- eigener Bereich "Datenqualität"
- aktuelle Klasse (A/B/C/X)
- aktueller Tages-/Statuskommentar
- darunter die vollständige Definition von A/B/C/X
- klarer Hinweis:
  KIT und Radiosonde sind nur Zusatzinformationen und unabhängig von A/B/C/X

PLOT:
- im Plot links oben eine kompakte Infobox mit
  "Qualität A/B/C/X" + Kurzdefinition der aktuellen Klasse
- unter dem Plot innerhalb der Figure eine vollständige Legende:
  A = ...
  B = ...
  C = ...
  X = ...
  KIT und Radiosonde: Zusatzinformationen

RÜCKSETZUNG:
Wenn kein Archiv vorhanden ist oder nach einem Update weiterhin keine
Plotdaten verfügbar sind, wird die Datenqualitätsanzeige sauber auf X mit
passender Erklärung zurückgesetzt, damit keine alte Qualitätsanzeige
irreführend stehen bleibt.


NEU v0.15.2 – DATENQUALITÄT UNTER DER GRAFIK, KLASSENINFO PER KLICK
-------------------------------------------------------------------
ÄNDERUNGEN:
- Keine Legende mehr in der Grafik
- Keine ausführliche Qualitätslegende mehr im Plot
- Aktuelle Datenqualitätsbewertung jetzt unter der Grafik
- Vollständige Klassendefinition nur noch per Klick in die Grafik

VERHALTEN:
- Unterhalb der Grafik steht nun:
  - Qualitätsklasse A/B/C/X
  - aktueller Bewertungstext
  - Hinweis: für Klassendefinition in die Grafik klicken
- Ein Klick in die Grafik öffnet ein neues Fenster mit:
  - A — sehr gute Datenbasis
  - B — gute Datenbasis
  - C — eingeschränkte Datenbasis
  - X — nicht ausreichend
  - Hinweis, dass KIT und Radiosonde nur Zusatzinformationen sind

RÜCKSETZUNG:
- Wenn kein Archiv vorhanden ist oder keine Plotdaten verfügbar sind,
  wird die Anzeige unter der Grafik wieder auf X mit passender Meldung gesetzt.


NEU v0.15.2 – QUALITÄTSBEWERTUNG IN DER GESPEICHERTEN GRAFIK
-------------------------------------------------------------
Die aktuelle Datenqualitätsbewertung befindet sich jetzt INNERHALB der
Matplotlib-Figure unterhalb der X-Achse.

Beispiel:

    Datenqualität B — DWD-Bodenmessung + vertikales Modell-/Archivprofil
    Klick in die Grafik: Definition der Qualitätsklassen A/B/C/X

Dadurch wird dieser Text bei "PNG speichern" automatisch zusammen mit der
Grafik gespeichert.

Nicht mehr vorhanden:
- separater Qualitätsbereich unterhalb des Canvas
- Kurvenlegende in der Grafik
- vollständige A/B/C/X-Erklärung dauerhaft in der Grafik

Die vollständige Klassendefinition öffnet sich weiterhin ausschließlich
durch einen Klick in die Grafik in einem eigenen Fenster.


NEU v0.15.2 – STATUSINFO MIT IN DER GRAFIK
------------------------------------------
Unterhalb der X-Achse werden jetzt innerhalb der Matplotlib-Figure zwei
Informationsbereiche mit abgespeichert:

1. Datenqualität:
   Datenqualität B — ...

2. Status:
   Status: ...
   DWD-Station: 05906 Mannheim (4.1 km) | ...

WICHTIG:
- Das eigentliche Diagramm behält einen festen reservierten Plotbereich.
- Wenn Qualitäts- oder Statusinfo länger werden, wird der Info-Text
  verkleinert, statt das Diagramm wesentlich kleiner zu machen.
- Die vollständige Klassendefinition A/B/C/X bleibt weiterhin nur über
  Klick in die Grafik in einem separaten Fenster verfügbar.

Zusätzlich:
- Die DWD-Station wird jetzt wieder zuverlässig aus bundle.station_info
  in die GUI-/Figure-Anzeige übernommen.


NEU v0.15.2 – TAGESWERTE AUCH IN DER GRAFIK, LINKSBÜNDIG
--------------------------------------------------------
Unterhalb der X-Achse werden jetzt linksbündig in der Figure angezeigt:

- Datenqualität
- Status
- DWD-Station
- Aktuell
- Maximum
- Minimum
- Hinweis auf Klick für Klassendefinition

WICHTIG:
- Diese Informationen werden beim PNG-Speichern mitgespeichert.
- Die Darstellung ist linksbündig.
- Das eigentliche Diagramm behält einen festen reservierten Plotbereich.
- Wenn der Infotext länger wird, wird die Schrift kleiner, statt das
  Diagramm wesentlich kleiner zu machen.


NEU v0.15.2 – PNG IMMER AKTIV
-----------------------------
"PNG speichern" ist jetzt bewusst immer aktiv.

Das gilt auch:
- direkt nach Programmstart
- wenn noch keine Daten geladen wurden
- wenn für einen Tag keine Daten existieren
- wenn ein Plot-/Datenfehler aufgetreten ist

Damit kann der sichtbare Zustand des Programms jederzeit als Diagnosebild
gesichert werden.

CSV bleibt dagegen datenabhängig:
- aktiviert, sobald mindestens eine exportierbare Datenreihe vorhanden ist
- deaktiviert, wenn keine exportierbaren Daten vorhanden sind

Zusätzlich werden Fehler beim PNG-Speichern in das Protokoll geschrieben
und als Fehlermeldung angezeigt.


NEU v0.15.2 – KURVENLEGENDE WIEDER DA + BREITERER INFOBEREICH
-------------------------------------------------------------
ÄNDERUNGEN:
- Die Kurvenlegende ist wieder sichtbar.
- Position: oben rechts im Diagramm.
- Der Footerbereich unterhalb der X-Achse ist etwas breiter ausgelegt.

Die Legende zeigt – je nach Datenverfügbarkeit –:
- Modell-/DWD-Inversionsindex
- Modell: max. positiver Gradient
- Radiosonde Idar-Oberstein gemessen
- KIT-Mast gemessen (separater Index)
- ICON-D2 Historical Forecast (separater Index)

Der Footerbereich für:
- Datenqualität
- Status
- DWD-Station
- Aktuell
- Maximum
- Minimum

wurde etwas verbreitert, damit die Informationen ruhiger und besser lesbar
dargestellt werden können.


NEU v0.15.2 – NORMAL / ADVANCED + ⋮-PANEL + TOUCH-GUI
------------------------------------------------------
NORMAL:
- rechter Diagnosebereich ist vollständig ausgeblendet
- große Hauptansicht für das Diagramm
- fingerfreundliche Hauptbuttons:
  ◀  HEUTE  ▶  UPDATE  PNG  ⋮

ADVANCED USER:
- rechter Bereich mit Status, Tageswerten, Datenquellen und Protokoll
- zusätzliche Diagnose- und Exportfunktionen über ⋮

⋮ EINSTELLUNGEN:
Display:
- Modell-/DWD-Kurve
- Modellgradient / rechte Achse
- ICON-D2
- KIT-Mast
- Radiosonde
- Kurvenlegende
- Status/Qualität/Tageswerte im Figure-Footer

Datenabruf:
- ICON-D2 beim Update abrufen
- KIT beim Update abrufen
- Radiosonde beim Update abrufen

WICHTIG:
Abruf und Anzeige sind voneinander getrennt.
Eine Quelle kann weiter archiviert, aber nicht angezeigt werden – oder
vorhandene Archivdaten können angezeigt werden, obwohl neue Abrufe
deaktiviert sind. Deaktivieren löscht keine bestehenden Archivdaten.

RECHTE ACHSE:
Der rechte Figure-Rand ist wieder fest ausreichend groß, damit
"Modell-Inversionsgradient [K/100 m]" lesbar bleibt.

ANDROID-VORBEREITUNG:
Die Hauptaktionen sind auf große Touch-Ziele reduziert. Seltene Funktionen
liegen im ⋮-Panel. Die Einstellungen werden unabhängig von der konkreten
Tkinter-Oberfläche in settings.json gehalten und können später von einer
Android-Oberfläche semantisch übernommen werden.


NEU v0.15.2 – MAUSRAD + LONG-PRESS FÜR TAGESNAVIGATION
-------------------------------------------------------
⋮ EINSTELLUNGEN:
- Unter Windows kann das Einstellungsfenster jetzt mit dem Mausrad gescrollt
  werden.
- Linux/X11 Button-4/Button-5 werden ebenfalls unterstützt.

TAGESNAVIGATION:
- kurzer Druck auf ◀ = 1 Tag zurück
- kurzer Druck auf ▶ = 1 Tag vor
- langer Druck auf ◀ (ab ca. 650 ms) = 7 Tage zurück
- langer Druck auf ▶ (ab ca. 650 ms) = 7 Tage vor

WICHTIG:
Ein langer Druck löst nicht zusätzlich noch den normalen 1-Tages-Schritt aus.

Die Implementierung nutzt Press/Release-Events und ist damit bewusst bereits
für spätere Touch-/Android-Bedienung vorbereitet.


NEU v0.15.2 – ORTSNEUTRAL / MEHRERE ORTE
-----------------------------------------
CODE-DATEINAMEN:
- Inversionskurve.py
- Inversion_Server.py
- keine Ortsnamen mehr in den eigentlichen Code-Dateinamen

ORTE:
locations.json enthält zunächst:
- Viernheim
- Bremerhaven

Viernheim bleibt standardmäßig aktiv, damit bestehende Arbeitsabläufe und
das vorhandene Archiv unverändert weiterlaufen.

NEUEN ORT ANLEGEN:
⋮ -> Ort -> Ortsname eingeben -> "Ort hinzufügen / aktivieren"

Es genügt beispielsweise:
    Bremerhaven

Das Programm ergänzt automatisch:
- Breiten-/Längengrad
- Höhe
- Zeitzone
- Land/Region

Nach dem Anlegen eines neuen aktiven Ortes ist derzeit EIN Programmneustart
erforderlich, damit alle Python-Module mit den neuen Koordinaten geladen
werden. Das wird ausdrücklich angezeigt.

ARCHIV:
Die bestehende Struktur ist bereits ortsgetrennt und wird weiterverwendet:

    archive/
      Viernheim/
        2026/08/25/...
      Bremerhaven/
        2026/08/25/...

Das Viernheim-Archiv wird weder verschoben noch gelöscht.

DWD-ABFANGSTRATEGIE:
Standardmäßig wird nur eine DWD-Bodenstation innerhalb 50 km als lokale
Bodenbeobachtung akzeptiert.

Wenn keine geeignete Station im Radius vorhanden ist:
1. keine weit entfernte Station wird stillschweigend verwendet;
2. die nächstgelegene bekannte Station wird im Status mit Entfernung genannt;
3. das ortsbezogene Vertikal-/2-m-Modell bleibt nutzbar;
4. es gibt keine lokale DWD-Korrektur;
5. die Qualitätsbewertung fällt entsprechend auf C statt B.

Der Radius kann pro Ort in locations.json über
    dwd_max_distance_km
angepasst werden.

KIT / RADIOSONDE:
Beide bleiben optionale Zusatzinformationen und sind nicht Teil der
ortsunabhängigen A/B/C/X-Qualitätsgrundlage. Sie können auch bei Bremerhaven
aktiv bleiben. Ihre räumliche Entfernung muss bei der Interpretation
berücksichtigt werden.


NEU v0.15.2 – ORTSNAME IM DIAGRAMMTITEL
----------------------------------------
Im Diagrammtitel wird jetzt der aktive Ort mit angezeigt.

Beispiel:
    Inversionsverlauf – Bremerhaven – 25.08.2026

Das gilt auch für Leer-/Hinweisplots, damit ein gespeichertes PNG sofort
erkennen lässt, für welchen Ort es erzeugt wurde.


NEU v0.15.2 – SERVER- UND GITHUB-TESTSTUFE
==========================================

Diese Version dient bewusst zuerst der Prüfung des Headless-Servers und der
GitHub-Archivaktualisierung, bevor weitere Länderquellen implementiert werden.

SERVER-TESTOPTIONEN
-------------------
Netzwerkfreier Selbsttest:
    python Inversion_Server.py --selftest

Aktive Konfiguration anzeigen:
    python Inversion_Server.py --show-config

Vorhandenes Archiv des aktiven Orts nur lesend prüfen:
    python Inversion_Server.py --verify-archive

Heute sammeln / nur Fehlendes nachholen:
    python Inversion_Server.py --today

Alle Quellen für heute neu anfordern:
    python Inversion_Server.py --today --force

ORT AUSWÄHLEN (Windows Anaconda Prompt / cmd.exe)
--------------------------------------------------
Viernheim:
    set INVERSION_LOCATION=Viernheim

Bremerhaven:
    set INVERSION_LOCATION=Bremerhaven

Danach wird jeder Aufruf von Inversion_Server.py in diesem Fenster für den
gesetzten Ort ausgeführt.

Um die Variable wieder zu löschen:
    set INVERSION_LOCATION=

WICHTIG:
Ein unbekannter Ortsname in INVERSION_LOCATION führt jetzt absichtlich zu
einem Fehler. Es gibt keinen stillen Rückfall auf Viernheim.

ARCHIVTRENNUNG
--------------
Viernheim:
    archive/Viernheim/YYYY/MM/DD/

Bremerhaven:
    archive/Bremerhaven/YYYY/MM/DD/

Der Selftest prüft zusätzlich, dass die Slugs aller konfigurierten Orte
eindeutig sind und keine zwei Orte denselben Archivpfad erhalten.

GITHUB ACTIONS
--------------
Der Workflow:
    .github/workflows/inversion_collect.yml

führt vor dem eigentlichen Abruf automatisch aus:
    --selftest
    --show-config
    --verify-archive

Bei einem geplanten schedule-Lauf werden ALLE Einträge aus locations.json
nacheinander verarbeitet.

Bei einem manuellen workflow_dispatch:
- location = Viernheim  -> nur Viernheim
- location = Bremerhaven -> nur Bremerhaven
- location = ALL -> alle Orte aus locations.json

Vor dem Commit zeigt der Workflow:
- git status --short archive
- git diff --stat -- archive
- git diff --name-status -- archive

So ist sichtbar, welcher Ortsordner wirklich verändert wurde.

Der GitHub-Workflow schläft nicht zwischen Retries. Er startet weiterhin
periodisch; Inversion_Server.py entscheidet anhand archive_config.json, ob
für einen Tag ein Retry bereits fällig ist.
