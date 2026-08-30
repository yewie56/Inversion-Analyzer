# Central KITMast Reference Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize KIT mast archival and transparently reuse it as a reference for configured German locations.

**Architecture:** Add a focused `kit_reference_archive` module responsible for global pathing, safe timestamp merge, legacy migration, network refresh, and bundle attachment. The GitHub workflow refreshes this global archive once per scheduled-mode run before location loops; location archives continue to store only local/core data.

**Tech Stack:** Python 3.11, pandas, GitHub Actions YAML, existing Bokeh/KIT source pipeline.

**Spec:** `docs/superpowers/specs/2026-08-30-central-kitmast-archive-design.md`

## Global Constraints
- Preserve KIT Bokeh timeout/retry configuration and diagnostics.
- MacroDroid request remains `mode=scheduled`, `location=ALL`, `force=false`, `date=""`.
- KIT reference never changes core completeness.
- Existing archive data must not be deleted by failed/empty refreshes.
- Update batch must be inside the ZIP and also available separately.

---

### Task 1: Global KIT archive behavior
**Files:** Create `inversion/kit_reference_archive.py`; create `test_kit_reference_archive_v0_15_22.py`.
- [ ] Write tests for `archive/KITMast/YYYY/MM/DD`, timestamp-safe merge, and legacy per-location migration.
- [ ] Run tests and verify they fail because the module does not exist.
- [ ] Implement minimal global archive functions and migration.
- [ ] Run tests and verify PASS.

### Task 2: Location reference attachment and no duplicate writes
**Files:** Modify `inversion/config.py`, `locations.json`, `inversion/archive.py`, `inversion/pipeline.py`; extend `test_kit_reference_archive_v0_15_22.py`.
- [ ] Write tests for DE reference configuration and central-reference attachment.
- [ ] Verify tests fail before production changes.
- [ ] Add `KIT_REFERENCE_ENABLED`, attach global KIT data on load, and suppress local KIT file writes for reference locations.
- [ ] Run tests and verify PASS.

### Task 3: Scheduled workflow collects KIT once
**Files:** Modify `Inversion_Server.py`, `.github/workflows/inversion_collect.yml`; create `test_workflow_global_kit_v0_15_22.py`.
- [ ] Write a workflow regression test requiring one global KIT step and unchanged scheduled dispatch semantics.
- [ ] Verify RED.
- [ ] Change `--kit-only` to global today+yesterday update, remove per-location scheduled KIT fetch, and add the global workflow step.
- [ ] Verify GREEN and existing v0.15.21 workflow mode test remains PASS.

### Task 4: Versioning, changelog, updater, verification
**Files:** Modify version/history headers; create `CHANGELOG_0.15.22.txt`; create `Update_Inversion_Analyzer_v0.15.22.bat`.
- [ ] Bump version to 0.15.22 and document behavior.
- [ ] Build uploader with SHA verification, regression suite, safe rebase/push, and optional scheduled-mode Action test.
- [ ] Run all regression tests and `Inversion_Server.py --selftest` for Viernheim, Bremerhaven, Valencia.
- [ ] Build clean ZIP excluding runtime archive/log/cache data while including the updater batch.
- [ ] Recompute SHA-256 and verify ZIP contents.
