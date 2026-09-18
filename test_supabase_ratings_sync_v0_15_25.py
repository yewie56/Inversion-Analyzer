# -*- coding: utf-8 -*-
"""Regression tests for v0.15.25 Supabase rating archive sync."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from inversion.supabase_ratings import (
    SyncResult, merge_into_archive, sanitize_observation, truncate_decimal, write_sync_state
)


CFG = {
    "timestamp_column": "response_time",
    "event_id_column": "event_id",
    "coordinate_mode": "truncate",
    "coordinate_decimals": 2,
    "include_comment": False,
}


def row(event_id, response, rating, lat=49.54129, lon=8.57859, observer="BB001", comment=None):
    return {
        "event_id": event_id,
        "observer_id": observer,
        "scheduled_time": response,
        "response_time": response,
        "rating": rating,
        "latitude": lat,
        "longitude": lon,
        "app_version": "0.4.84",
        "comment": comment,
    }


def main() -> int:
    assert truncate_decimal(49.549, 2) == 49.54
    assert truncate_decimal(-8.579, 2) == -8.57

    zero = sanitize_observation(row("e0", "2026-09-18T20:00:00Z", 0), CFG)
    missed = sanitize_observation(row("em", "2026-09-18T20:01:00Z", -1), CFG)
    assert zero["rating"] == 0
    assert missed["rating"] == -1
    assert zero["location"]["latitude"] == 49.54
    assert zero["location"]["longitude"] == 8.57
    assert "comment" not in sanitize_observation(row("ec", "2026-09-18T20:02:00Z", 2, comment="privat"), CFG)
    assert sanitize_observation(row("ec2", "2026-09-18T20:03:00Z", 2, comment="privat"), CFG)["has_comment"] is True

    no_loc = sanitize_observation(row("en", "2026-09-18T20:04:00Z", 3, 0.0, 0.0), CFG)
    assert no_loc["location"]["available"] is False
    assert no_loc["location"]["latitude"] is None

    # v0.15.25: unanswered/missed rows without response_time are pending,
    # while a real rating without response_time remains invalid.
    pending_row = row("ep", None, -1)
    invalid_row = row("ei", None, 3)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "ratings"
        rows = [
            row("a", "2026-09-18T20:10:00Z", 1),
            row("b", "2026-09-18T20:20:00Z", 0),
            row("a", "2026-09-18T20:10:00Z", 1),  # duplicate event_id
            row("c", "2026-09-19T00:01:00Z", -1),
        ]
        accepted, pending, rejected, written, total, latest = merge_into_archive(rows, root, CFG)
        assert accepted == 4
        assert pending == 0
        assert rejected == 0
        assert written == 2
        assert total == 3
        assert latest.startswith("2026-09-19T00:01:00")

        d18 = root / "2026" / "09" / "2026-09-18" / "ratings.jsonl"
        before = d18.read_bytes()
        _, _, _, written2, total2, _ = merge_into_archive(rows, root, CFG)
        after = d18.read_bytes()
        assert written2 == 0, "Idempotenter Zweitlauf darf Tagesdateien nicht ändern"
        assert total2 == 3
        assert before == after

        pending_root = Path(td) / "pending_ratings"
        a2, p2, r2, w2, t2, latest2 = merge_into_archive(
            [pending_row, row("valid", "2026-09-19T01:00:00Z", 2)], pending_root, CFG
        )
        assert (a2, p2, r2) == (1, 1, 0)
        assert w2 == 1 and t2 == 1 and latest2.startswith("2026-09-19T01:00:00")

        invalid_root = Path(td) / "invalid_ratings"
        a3, p3, r3, _, _, _ = merge_into_archive([invalid_row], invalid_root, CFG)
        assert (a3, p3, r3) == (0, 0, 1)

        summary = json.loads((root / "2026" / "09" / "2026-09-18" / "summary.json").read_text(encoding="utf-8"))
        assert summary["rating_counts"]["0"] == 1
        assert summary["rating_counts"]["1"] == 1
        assert summary["rating_counts"]["-1"] == 0

        result = SyncResult(fetched=3, accepted=3, pending_skipped=0, rejected=0, written_days=2, archive_events=3, max_response_time_utc=latest)
        write_sync_state(root, result, None, CFG)
        state_path = root / "sync_state.json"
        state_before = state_path.read_bytes()
        write_sync_state(root, result, None, CFG)
        assert state_before == state_path.read_bytes(), "Unveränderter Sync-State darf nicht bei jedem Lauf neu geschrieben werden"

    print("test_supabase_ratings_sync_v0_15_25: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
