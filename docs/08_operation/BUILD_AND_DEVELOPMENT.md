# Build and Development Guide

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Zielumgebungen

- lokal: Windows 11, Python 3.11 geeignet; Start aus Spyder oder Konsole.
- GitHub Actions: `ubuntu-latest`, Python 3.11.

## 2. Python-Abhängigkeiten

```powershell
python -m pip install requests pandas numpy matplotlib bokeh
```

## 3. Start

GUI:

```powershell
python Inversionskurve.py
```

Headless:

```powershell
python Inversion_Server.py --today
python Inversion_Server.py --date 2026-08-30
python Inversion_Server.py --scheduled
python Inversion_Server.py --kit-only
python Inversion_Server.py --selftest
```

## 4. Update-Batch

`Update_Inversion_Analyzer_v0.15.24.bat` ist Bestandteil des Quellstands. Laut README sucht er das Git-Repository, führt Fetch/Rebase und Regressionstests aus, staged keine Runtime-Archive/Logs/Cache-Dateien und verwendet keinen Force-Push.

## 5. Entwicklungsregel

Vor Release: Selftest + Regressionstests + Versions-/Changelog-Abgleich. Für neue Actions-Funktionen zusätzlich headless Tests unter Linux-kompatibler Umgebung.
