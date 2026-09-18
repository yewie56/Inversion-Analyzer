# Self-Test Specification

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.25  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Aktueller Selftest

`python Inversion_Server.py --selftest` prüft zentrale interne Funktionen/Parser; der Actions-Workflow führt den Selftest für jede ausgewählte Location vor dem Collector aus.

## 2. Erweiterung des Selftests

Bei Implementierung ergänzen:

- Diagrammrenderer importierbar und kann synthetischen Minimaldatensatz rendern.
- Seismik-Konfiguration syntaktisch vollständig; Parser kann eingebettetes Testfixture lesen.
- Supabase-Exportmodul kann Schema validieren, ohne echtes Secret zu benötigen.
- Sync-State kann schreiben/lesen und Idempotenzfixture besteht.

Selftests dürfen keine produktiven Remote-Daten verändern.
