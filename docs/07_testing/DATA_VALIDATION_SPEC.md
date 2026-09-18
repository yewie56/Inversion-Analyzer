# Data Validation Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Quellvalidierung

Zu validieren sind mindestens: erfolgreiches Parsen, nichtleere erwartete Daten, Zeitstempel im Zieltag, plausible Reihenanzahl/Abdeckung und größte Datenlücke soweit relevant.

## 2. Archivvalidierung

`manifest.json` muss auf tatsächlich vorhandene Dateien zeigen. CSV-Zeitspalten müssen parsebar sein. Safe-Merge darf Zeitstempel nicht unkontrolliert duplizieren.

## 3. Diagrammvalidierung – PLANNED

PNG muss decodierbar und nicht trivial leer sein; Metadaten müssen Standort/Datum/Version enthalten. Der Renderer darf bei fehlendem Profil keinen normalen Inversionsplot als Erfolg melden.

## 4. Seismikvalidierung – PLANNED

Zusätzlich Content-Type/Signatur, Dateigröße, Bilddecodierung, Stationsbezug, Produktdatum/Frische und SHA-256 prüfen.

## 5. Ratings-Validierung – PLANNED

Schema-Version, eindeutige ID, parsebarer UTC-Zeitstempel, zulässiger Bewertungsbereich, Feld-Allowlist, keine verbotenen PII-Felder, keine doppelte ID.
