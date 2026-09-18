# Retry and Error Handling

> Dokumentationsstand: 2026-09-19  \n> Software-Basis: Inversion Analyzer v0.15.24  \n> Statusbegriffe: **IMPLEMENTED** = im Quellstand nachweisbar; **PLANNED** = beschlossen/geplant, noch nicht implementiert; **OPEN** = Detailentscheidung fehlt.

## 1. Aktuelle Parameter

Aus `archive_config.json`:

- Retry-Delay: 3 Stunden,
- max. Retries: 5,
- nur fehlende Kernquellen nachladen,
- optionale Quellen lösen standardmäßig keinen Kern-Retry aus,
- KIT Bokeh Timeout 20 s,
- max. 3 KIT-Versuche,
- KIT Retry-Delays 5 s und 15 s.

## 2. Safe-Merge

Frische Teildaten werden in den vorhandenen Tagesbestand gemergt. Nicht angeforderte Quellen bleiben unangetastet. Fehlgeschlagene/leer zurückgegebene KIT-Daten löschen keine guten Bestände.

## 3. Neue Funktionen

- Diagrammfehler: Rohdatenarchiv bleibt gültig; Produktstatus FAIL.
- Seismikfehler: nur betroffene Station FAIL/STALE; keine Löschung des letzten guten Originalprodukts ohne explizite Regel.
- Supabasefehler: Sync-State nicht fortschreiben; nächster Lauf darf wiederholen.
