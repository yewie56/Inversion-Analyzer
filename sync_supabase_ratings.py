# -*- coding: utf-8 -*-
"""CLI for the Inversion Analyzer Supabase rating synchronization."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from inversion.supabase_ratings import RatingSyncError, load_config, synchronize


def main() -> int:
    parser = argparse.ArgumentParser(description="Supabase-Bewertungen in das GitHub-Archiv synchronisieren")
    parser.add_argument("--config", default="ratings_sync_config.json", help="Pfad zur JSON-Konfiguration")
    parser.add_argument("--archive-root", default=None, help="Archivpfad überschreiben")
    parser.add_argument("--full", action="store_true", help="Vollständigen Supabase-Bestand erneut lesen und idempotent mergen")
    args = parser.parse_args()

    try:
        config = load_config(Path(args.config))
        archive_root = Path(args.archive_root) if args.archive_root else None
        result = synchronize(config, full=args.full, archive_root=archive_root)
    except RatingSyncError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"FEHLER: Unerwarteter Sync-Fehler: {exc}", file=sys.stderr)
        return 3

    print("SUPABASE RATINGS SYNC: PASS")
    print(f"  fetched      : {result.fetched}")
    print(f"  accepted       : {result.accepted}")
    print(f"  pending_skipped: {result.pending_skipped}")
    print(f"  rejected       : {result.rejected}")
    print(f"  written_days : {result.written_days}")
    print(f"  archive_total: {result.archive_events}")
    print(f"  latest_utc   : {result.max_response_time_utc or '-'}")
    if result.rejected:
        print("FEHLER: Mindestens ein ungültiger Supabase-Datensatz wurde verworfen; Archiv-Commit wird verhindert.", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
