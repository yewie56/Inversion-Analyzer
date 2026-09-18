# Security and Secrets

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Aktuelle Secrets

`AEMET_API_KEY` wird aus GitHub Actions Secrets in die Job-Umgebung gegeben. Zugangstoken dürfen nicht in Projektdateien oder Logs gespeichert werden.

## 2. Supabase-Bewertungssync – IMPLEMENTED

- Secret-Schlüssel ausschließlich über GitHub Actions Secrets.
- Backend-Secret nur im serverseitigen GitHub-Runner; aktuelle `sb_secret_...`-Keys werden bevorzugt.
- Keine Ausgabe von Headern, Token, Connection Strings oder kompletten Response-Objekten mit sensitiven Feldern.
- Der Export wird durch `sanitize_observation()` auf das dokumentierte Ausgabeschema reduziert; Rohantworten werden nicht archiviert.

## 3. Bewertungen und Standortdaten

Vor GitHub-Export ist festzulegen, ob das Zielrepository öffentlich oder privat ist. Klarnamen, E-Mail-Adressen, Gerätekennungen und präzise Koordinaten sind standardmäßig nicht Teil eines öffentlichen Bewertungsexports. Pseudonymisierung darf nicht mit Verschlüsselung verwechselt werden.

## 4. Supply Chain

GitHub Actions sind versionsgebunden (`checkout@v6`, `setup-python@v7`, `cache@v6`). Für besonders strenge Reproduzierbarkeit können Actions zukünftig auf Commit-SHAs gepinnt werden.


## Supabase Rating Sync v0.15.24

Der Workflow darf niemals einen Backend-Key in Quellcode, Konfigurationsdateien, Logs oder Archivdateien schreiben.

GitHub Repository Secret:

```text
SUPABASE_SECRET_KEY
```

Bevorzugt wird der aktuelle Supabase-Secret-Key-Typ `sb_secret_...`. Der ältere `SUPABASE_SERVICE_ROLE_KEY` wird ausschließlich als Übergangskompatibilität akzeptiert. Der REST-Client sendet den Backend-Key im `apikey`-Header.

Datenschutz-Default des GitHub-Archivs:
- kein Klartext-App-/Teilnehmerschlüssel,
- keine exakten GPS-Koordinaten,
- kein Kommentartext,
- keine Audiodatei.
