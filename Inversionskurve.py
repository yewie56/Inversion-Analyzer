#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inversionskurve.py
Version: 0.15.2
Datum: 2026-08-24

STARTDATEI: In Spyder nur diese Datei starten.

Versionshistorie
----------------
0.15.2 - Server-/GitHub-Testversion:
         Inversion_Server.py erhält --selftest, --show-config und
         --verify-archive. Der Selbsttest ist netzwerkfrei und schreibt keine
         Archivdaten. Explizit unbekannte INVERSION_LOCATION-Werte führen nun
         sofort zu einem Fehler statt unbemerkt auf einen anderen Ort
         zurückzufallen.
         GitHub Actions führt vor jedem Abruf für jeden ausgewählten Ort
         Selftest, Konfigurationsanzeige und Archivprüfung aus.
         Scheduled Runs arbeiten automatisch alle Orte aus locations.json ab.
         Manuelle Runs unterstützen einen einzelnen Ort oder ALL.
         Archivänderungen werden vor dem Commit als status/stat/name-status
         sichtbar ausgegeben. Der Commit nennt die bearbeiteten Orte.
         Concurrency verhindert überlappende Collector-Läufe.

0.15.1 - Ortsname im Diagrammtitel:
         Der aktive Orts-/Städtename wird jetzt direkt im Diagrammtitel
         angezeigt, z. B.:
         "Inversionsverlauf – Bremerhaven – 25.08.2026".
         Das gilt auch für Leer-/Hinweisplots, damit exportierte PNGs sofort
         den zugehörigen Ort erkennen lassen.

0.15.0 - Mehrere frei konfigurierbare Orte:
         Programmnamen und Code-Dateinamen sind ortsneutral.
         Startdatei heißt Inversionskurve.py.
         Headless-Datei heißt Inversion_Server.py.
         locations.json enthält Viernheim unverändert und Bremerhaven als
         ersten zweiten Testort.
         Im ⋮-Panel genügt künftig die Eingabe eines Ortsnamens.
         Koordinaten, Höhe und Zeitzone werden per Geocoding ergänzt.
         Jeder Ort erhält automatisch seinen eigenen Archiv-Unterordner:
         archive/<Ort>/YYYY/MM/DD.
         Keine weit entfernte DWD-Bodenstation wird still als lokal verwendet:
         Standardradius 50 km; außerhalb davon bleibt die Modellberechnung
         verfügbar, aber ohne lokale DWD-Korrektur und mit reduzierter Qualität.
         KIT und Radiosonde bleiben optionale Zusatzquellen und können auch
         bei weiteren Orten weiter abgerufen/angezeigt werden.
         Bestehendes Viernheim-Archiv bleibt unverändert erhalten.

0.14.1 - Mausrad und Long-Press-Navigation:
         Das ⋮-Einstellungsfenster kann unter Windows mit dem Mausrad
         gescrollt werden; zusätzlich sind Linux/X11 Button-4/5 berücksichtigt.
         ◀/▶ unterstützen jetzt Kurz- und Langdruck:
         kurzer Druck = -1/+1 Tag,
         langer Druck ab 650 ms = -7/+7 Tage.
         Ein Langdruck löst nicht zusätzlich den 1-Tages-Schritt aus.
         Die Logik ist absichtlich Maus- und Touch-kompatibel und bereitet
         das spätere Android-Bedienkonzept vor.

0.14.0 - GUI auf Normal/Advanced und Touch-Bedienung umgestellt:
         Normal-Modus zeigt keinen rechten Diagnosebereich.
         Advanced User kann den rechten Status-/Quellen-/Logbereich einblenden.
         Fingerfreundliche Hauptleiste: ◀, HEUTE, ▶, UPDATE, PNG, ⋮.
         Seltenere Aktionen liegen im ⋮-Panel.
         Display-Schalter für Modell, Gradient, ICON-D2, KIT, Radiosonde,
         Legende und Figure-Info.
         Getrennte Abrufschalter für ICON-D2, KIT und Radiosonde.
         Deaktivierter Abruf löscht keine vorhandenen Archivdaten.
         settings.json speichert Modus und Anzeige-/Abrufeinstellungen.
         Rechte Achse erhält wieder festen ausreichenden Rand.
         PNG bleibt auch während eines Updates aktiv.
         Figure-Layout bleibt fest; längere Footertexte verkleinern primär
         ihre Schrift statt den Plot weiter zu schrumpfen.

0.13.9 - Kurvenlegende wiederhergestellt und Footerbereich verbreitert:
         Die Kurvenlegende ist jetzt wieder oben rechts im Diagramm sichtbar.
         Enthalten sind – je nach vorhandenen Daten – Modell-/DWD-Inversionsindex,
         Modellgradient, Radiosonde, KIT-Mast und ICON-D2.
         Der untere Figure-Footer für Datenqualität, Status, DWD-Station sowie
         Aktuell/Maximum/Minimum erhält einen etwas breiteren Darstellungsbereich.
         Dafür werden größere Zeilenbreiten genutzt und die reservierte Fußzone
         leicht vergrößert.
         Regressionstest sichert die Kurvenlegende künftig ab.

0.13.8 - Export-Buttons korrigiert:
         PNG speichern ist jetzt absichtlich IMMER aktiv.
         Auch Leer-, Fehler- und Noch-nicht-geladen-Darstellungen können als
         Diagnosebild gespeichert werden.
         save_png() benötigt deshalb kein geladenes Datenbundle mehr.
         Fehler beim PNG-Speichern werden geloggt und sichtbar gemeldet.
         CSV speichern bleibt datenabhängig und wird nur aktiviert, wenn
         tatsächlich exportierbare Modell-/KIT-/ICON-/Radiosondendaten vorliegen.
         Regressionstest schützt dieses Verhalten künftig ab.

0.13.7 - Tageswerte ebenfalls in Figure-Footer integriert:
         Unterhalb der X-Achse werden jetzt linksbündig dargestellt:
         Datenqualität, Status, DWD-Station sowie die Tageswerte
         Aktuell, Maximum und Minimum.
         Diese Informationen werden dadurch beim PNG-Export mitgespeichert.
         Der Info-Text ist linksbündig ausgerichtet.
         Das Diagramm behält einen festen reservierten Plotbereich; bei längeren
         Informationen wird bevorzugt die Schrift verkleinert.
         Die Tageswerte werden vor dem Zeichnen des Plots aktualisiert, damit sie
         sicher im gespeicherten Bild erscheinen.

0.13.6 - Statusinfo ebenfalls in die Figure integriert:
         Unterhalb der X-Achse werden jetzt sowohl die aktuelle
         Datenqualitätsbewertung als auch die Statusinformation mit DWD-Station
         in die Matplotlib-Figure geschrieben.
         Diese Zusatzinformationen werden dadurch beim PNG-Export mitgespeichert.
         Der reservierte Diagrammbereich bleibt dabei fest; wenn der Text länger
         wird, wird bevorzugt die Schrift verkleinert statt das eigentliche
         Diagramm wesentlich kleiner zu machen.
         Die ausführliche A/B/C/X-Klassendefinition bleibt weiterhin nur
         per Klick in die Grafik in einem separaten Fenster verfügbar.
         Zusätzlich wird die DWD-Station aus bundle.station_info zuverlässig
         in station_var gespiegelt.

0.13.5 - Aktuelle Datenqualitätsbewertung wieder in die Figure integriert:
         Die aktuelle Qualitätsklasse und der Bewertungstext stehen nun
         innerhalb der Matplotlib-Figure unterhalb der X-Achse.
         Dadurch werden sie bei PNG speichern automatisch mitgespeichert.
         Der separate GUI-Qualitätsbereich unter dem Canvas wurde entfernt.
         Die vollständige A/B/C/X-Klassendefinition bleibt ausschließlich
         im separaten Fenster, das sich per Klick in die Grafik öffnet.
         Keine Kurvenlegende in der Grafik.

0.13.4 - Darstellung der Datenqualität neu organisiert:
         Keine Legende mehr in der Grafik.
         Keine Qualitäts-Infobox mehr in der Grafik.
         Die aktuelle Datenqualitätsbewertung steht nun unter der Grafik
         in einem eigenen GUI-Bereich.
         Die vollständige Klassendefinition A/B/C/X wird nicht dauerhaft
         angezeigt, sondern öffnet sich nur noch beim Klick in die Grafik
         in einem eigenen Fenster.
         Hinweistext unter der Grafik macht auf die Klickfunktion aufmerksam.

0.13.3 - Datenqualitätsklassen in GUI und Graph integriert:
         Seitliche Datenqualitätsbox zeigt aktuelle Klasse, aktuellen Detailtext
         und die vollständige Klassendefinition A/B/C/X dauerhaft an.
         Im Plot wird zusätzlich eine Qualitäts-Infobox eingeblendet:
         Qualität + Kurzdefinition der aktuellen Klasse.
         Unter dem Plot steht die vollständige Klassendefinition A/B/C/X
         einschließlich Hinweis, dass KIT und Radiosonde nur Zusatzinformationen
         und unabhängig von A/B/C/X sind.
         Bei fehlendem Archiv bzw. fehlenden Plotdaten wird die
         Datenqualitätsanzeige auf X mit passender Meldung zurückgesetzt.

0.13.2 - DWD-Radiosondenformat konkret unterstützt:
         AE_TT als Temperatur, AE_P als Druck und AE_GPM als Höhe erkannt.
         Zeit wird für High-Resolution-Daten aus BEZUGSDATUM_SYNOP
         plus MESSZEITPUNKT (Sekunden seit Start) gebildet.
         Zeitbasis wird als UTC interpretiert und nach Europe/Berlin konvertiert.
         Produktdateiname produkt_sec_aero_YYYYMMDD_YYYYMMDD_... wird
         vor dem Parse auf seinen Datenzeitraum geprüft.
         Liegt der gewählte Tag außerhalb, wird sofort NO_DATA_DATE gemeldet,
         ohne die sehr große Produktdatei vollständig zu parsen.
         Canonical produkt_sec_aero wird direkt gewählt; Metadaten werden nicht
         mehr unnötig als Messdateien untersucht.
         Lokaler ZIP-Cache bleibt unverändert nutzbar.

0.13.1 - Radiosonden-Parser und Fehlerdiagnose robust gemacht:
         ZIP-Inhalte werden protokolliert.
         Dateiendungen werden nicht mehr vorausgesetzt.
         Encoding und Separator werden aus einer Headerprobe erkannt.
         Unterstützt Semikolon, Tab, Komma, Pipe und Whitespace.
         Mehrere ZIP-Member werden auf echte Zeit-/Temperatur-/Höhenspalten geprüft.
         Header, erkannte Spalten, gewählte Messdatei, Gesamtzeilen,
         Tageszeilen und erkannte Aufstiege werden im Hauptlog ausgegeben.
         Parser-/Formatfehler werden sichtbar als Radiosonde-Status protokolliert.
         Keine künstliche Nullkurve bei Parserfehlern.
         Lokaler ZIP-Cache bleibt erhalten.

0.13.0 - Radiosondendaten werden fachlich verwendet:
         DWD High-Resolution Radiosonde Idar-Oberstein 02385 / WMO 10618.
         Gemessene Temperatur-Höhen-Profile werden eingelesen und archiviert.
         Eigener separater Radiosonden-Inversionsindex 0–5.
         Rohprofile: radiosonde_profile.csv.
         Kennwerte: radiosonde_metrics.csv.
         Eigene rote Messkurve in der GUI.
         Radiosonde wird nicht mit Viernheim-Modell/ICON-D2 gemittelt.
         Große aktuelle DWD-ZIP-Datei wird streamingbasiert auf Platte gecacht.
         Schutz vorhandener Radiosondendaten vor leerem/fehlerhaftem Neuabruf.
         Alle Plotfarben fest: Modell blau, Gradient grau, KIT orange,
         ICON-D2 grün, Radiosonde rot.

0.12.6 - Datenquellen-Archivlog und feste Plotfarben:
         Jeder Speichervorgang ergänzt sources.log im Tagesarchiv.
         Jeder Eintrag enthält alle Datenquelleninformationen und wird mit
         ========-Trennzeilen vom vorherigen Eintrag getrennt.
         KIT-Mast ist fest orange.
         ICON-D2 ist fest grün.
         Diese beiden Kurven verwenden keine automatische Farbvergabe mehr.

0.12.5 - GUI-Regression behoben:
         _update_source_status() wieder in der GUI-Klasse vorhanden.
         Quellenanzeige aktualisiert wieder DWD, Vertikalprofil, Radiosonde,
         KIT-Mast und ICON-D2.
         Regressionstest prüft die Klassenmethode ausdrücklich.

0.12.4 - Stepping-Logik weiter verfeinert:
         Zuerst wird ausschließlich das lokale Archiv geprüft.
         Enthält der Tag darstellbare Plotdaten, werden diese sofort angezeigt,
         ohne Netzwerkzugriff.
         Fehlen darstellbare Plotdaten vollständig, wird der alte Plot gelöscht
         und genau ein automatischer Update-Abruf gestartet.
         Liefert auch dieser keine Plotdaten, bleibt die Anzeige leer und meldet
         "Keine Daten für diesen Tag verfügbar".
         Teilarchive mit vorhandenen Modell/KIT/ICON-D2-Plotdaten werden sofort
         angezeigt; fehlende Zusatzquellen lösen keinen automatischen Abruf aus.
         Manueller Update-Button und KIT-Archivschutz bleiben erhalten.

0.12.3 - Archiv-/GUI-Anzeige beim Steppen robuster gemacht:
         Archiv-Zeitspalten werden vor der Anzeige normalisiert.
         Plot wird vor Summary und Quellenstatus aufgebaut.
         Fehler in Summary/Quellenstatus können den Plot nicht mehr verhindern.
         Archiv-/Plot-Zeilen werden im Log diagnostiziert.
         Bei nicht darstellbaren Archivdaten erscheint eine klare Meldung.
         Bestehender Plot bleibt sichtbar, wenn ein Tag gar nicht archiviert ist.
         Archivformat bleibt unverändert kompatibel.

0.12.2 - ICON-D2 fachlich korrigiert:
         2-m-Temperatur wird in das Vertikalprofil einbezogen.
         Druckflächenhöhen werden aus MSL auf AGL bezogen.
         Nur Ebenen oberhalb des Bodens werden für die Inversion verwendet.
         Rohprofile werden als icon_d2_profile.csv archiviert.
         Bestehendes Archiv bleibt kompatibel.

0.12.1 - GUI-Tagesnavigation liest ausschließlich das lokale Archiv.
         Internetabruf nur noch explizit über "Update".
         Sicheres Zusammenführen vorhandener Archivdaten.
         KIT-Mastprofile werden kumulativ archiviert und niemals durch
         kleinere/leere Neuabrufe gelöscht.
         Archivformat bleibt mit v0.12.0 kompatibel.

0.12.0 - Archiv-/Headless-Architektur, Tagesmanifest, konfigurierbare Orte,
         GitHub-Actions-Workflow und Teilabrufe.

0.3.0 - Modulare Architektur, detaillierte Fehleranalyse und Logging,
        Quellenstatus und Datenqualitaet sichtbar in der GUI.
0.2.0 - Tkinter-GUI, Diagramm, CSV/PNG, Selbsttest.
0.1.0 - Erste Konsolenversion.
"""
from inversion.gui import InversionApp

def main():
    app = InversionApp()
    app.mainloop()

if __name__ == "__main__":
    main()
