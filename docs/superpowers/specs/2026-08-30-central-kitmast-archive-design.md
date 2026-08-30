# Central KITMast Reference Archive Design

Version target: 0.15.22

## Goal
Store KIT 200-m mast measurements once in a global daily archive under `archive/KITMast/YYYY/MM/DD/` and let configured German locations consume that archive as an optional reference series.

## Requirements
- Preserve the existing KIT Bokeh retry behavior: hard timeout, three attempts by default, configured retry delays, diagnostics, and no destructive overwrite after empty/failed fetches.
- `workflow_dispatch` with `mode=scheduled` remains unchanged for MacroDroid.
- Scheduled/Manual-Scheduled GitHub Actions update the global KIT archive once before processing locations.
- Viernheim and Bremerhaven use `kit_reference: true`; Valencia uses `false`.
- KIT remains optional/reference-only and never affects A/B/C/X core completeness.
- Existing per-location `kit_mast.csv` files are migrated idempotently into the global archive before new network data are merged.
- Location bundle loading transparently attaches matching global KIT data when `kit_reference` is enabled.
- New per-location saves do not create or reference duplicate KIT CSV/JSON files.
- Existing legacy per-location KIT files are not destructively deleted by the release.
- `--kit-only` updates the global KIT archive for today and yesterday.
- The version-specific update batch is shipped both separately and inside the release ZIP.
