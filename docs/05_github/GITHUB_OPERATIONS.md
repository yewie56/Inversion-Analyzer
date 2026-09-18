# GitHub Operations Guide

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Manueller Datenlauf

GitHub → Actions → `Inversion data collector` → Run workflow. Ort/ALL, Modus, optional Datum und Force wählen.

## 2. Diagnose

Bei Fehlern in dieser Reihenfolge prüfen:

1. Preflight-Selftest.
2. aktive Location und `locations.json`.
3. Netzwerk-/HTTP-Fehler einzelner Quellen.
4. KIT-Bokeh-Retrylog.
5. `git status`/Commit-Step.
6. Berechtigungen `contents: write` und Branchschutz.
7. benötigte Secrets.

## 3. Geplanter Betrieb nach Erweiterung

Neue Produktsteps müssen im Actions-Log pro Produkt eine kurze Statuszeile liefern: `PASS`, `NO_DATA`, `STALE`, `FAILED`, plus Pfad. Bei Supabase zusätzlich: Anzahl gelesen, neu, verworfen/ungültig, geschrieben; keine vertraulichen Inhalte.

## 4. Recovery eines fehlgeschlagenen Laufs

Actions-Lauf erneut starten oder `workflow_dispatch` mit dem betroffenen Datum ausführen. Safe-Merge und Idempotenz sind Voraussetzung dafür, dass Wiederholung zulässig ist.
