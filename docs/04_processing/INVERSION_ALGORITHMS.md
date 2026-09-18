# Inversion Algorithms and Derivations

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Hauptprofil

`calculate_profile_metrics()` verarbeitet Temperaturwerte auf 2 m und den Druckniveaus 1000, 975, 950, 925, 900 und 850 hPa. Geopotentialhöhen werden von MSL in AGL umgerechnet, indem die konfigurierte Standorthöhe abgezogen wird.

Zwischen vorhandenen Profilpunkten werden Darstellungstemperaturen bei 100, 200 und 500 m linear interpoliert. **Keine Extrapolation** außerhalb der verfügbaren Profilhöhe.

## 2. Positive Temperaturgradienten

Für benachbarte Schichten mit ausreichendem Höhenabstand werden Temperaturdifferenz und Gradient in K/100 m berechnet. Positive Temperaturzunahme mit Höhe trägt zur Inversionsmetrik bei.

## 3. Lokaler Stratifikationsindex

Der Code v0.15.14 ff. bewertet das vollständige verfügbare Profil bis 600 m AGL. Bevorzugter Bodenanker ist eine gemessene Oberflächentemperatur, sonst Modell-2-m.

Normierungen:

- `gradient_score = max positive gradient / 0.5 K je 100 m`, auf 0..1 begrenzt,
- `deltaT_score = Summe positive ΔT / 2.0 K`, auf 0..1 begrenzt,
- `depth_score = positive Schichttiefe / 300 m`, auf 0..1 begrenzt.

Index:

`5 * (0.45*gradient_score + 0.35*deltaT_score + 0.20*depth_score)`

Ergebnisbereich 0..5.

## 4. Datenqualität

Ohne auswertbares Vertikalprofil: Klasse X. Mit DWD- oder AEMET-Bodenmessung + Vertikalprofil: Klasse B. Mit Profil aber fehlender/veralteter Bodenmessung: Klasse C. KIT/Radiosonde bleiben separate Referenzreihen und verändern die Kernklasse nicht.

## 5. Validierungsanforderung

Änderungen an Gewichtungen, Höhen, Druckniveaus oder Interpolation benötigen eine neue Algorithmusversion, Changelog-Eintrag und Regressionstest mit festem Eingabedatensatz.
