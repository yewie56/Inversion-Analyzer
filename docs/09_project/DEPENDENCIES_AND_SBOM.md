# Dependencies and SBOM

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Direkt installierte Python-Pakete

Der aktuelle README/Workflow installiert:

- `requests`
- `pandas`
- `numpy`
- `matplotlib`
- `bokeh`

Python-Version in Actions: 3.11.

## 2. Standardbibliothek

U. a. `tkinter`, `pathlib`, `json`, `datetime`, `zoneinfo`, `argparse`, `logging`, `multiprocessing`, `zipfile`, `hashlib`, `shutil`.

## 3. GitHub Actions

- `actions/checkout@v6`
- `actions/setup-python@v7`
- `actions/cache@v6`

## 4. Reproduzierbarkeit

Aktuell sind Python-Paketversionen nicht gepinnt. Für vollständig deterministische Neuinstallationen ist eine zukünftig geprüfte `requirements.txt` mit Versionen empfehlenswert; Versionsupdates müssen über Regressionstests validiert werden.
