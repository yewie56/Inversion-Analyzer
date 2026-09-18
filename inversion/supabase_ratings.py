# -*- coding: utf-8 -*-
"""Supabase -> GitHub rating archive synchronization.

The module deliberately uses Supabase's REST endpoint directly and only Python's
standard library.  A backend key is read from environment variables and is never
written to disk or logs.

Archive invariants:
- ``event_id`` is the stable de-duplication key.
- rating ``0`` and ``-1`` remain distinct.
- exact coordinates are not exported by default; coordinates are truncated to a
  configurable number of decimals.
- day files are deterministic JSONL sorted by response timestamp + event_id.
- rerunning the same input does not change day files.
"""
from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "1.0"
DEFAULT_CONFIG = {
    "supabase_url": "",
    "table": "observations",
    "timestamp_column": "response_time",
    "event_id_column": "event_id",
    "page_size": 1000,
    "overlap_hours": 48,
    "archive_dir": "archive/ratings",
    "coordinate_mode": "truncate",
    "coordinate_decimals": 2,
    "include_comment": False,
}


class RatingSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncResult:
    fetched: int
    accepted: int
    rejected: int
    written_days: int
    archive_events: int
    max_response_time_utc: str | None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any, field: str) -> datetime:
    if value is None or str(value).strip() == "":
        raise RatingSyncError(f"Fehlender Zeitstempel: {field}")
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RatingSyncError(f"Ungültiger Zeitstempel {field}={value!r}") from exc
    if dt.tzinfo is None:
        # Supabase timestamptz should be timezone-aware.  Treat a legacy naive
        # value as UTC rather than silently using the runner's local timezone.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_utc(value: Any, field: str) -> str:
    return _parse_datetime(value, field).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _optional_iso_utc(value: Any, field: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _iso_utc(value, field)


def _first(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def truncate_decimal(value: float, decimals: int) -> float:
    factor = 10 ** max(0, int(decimals))
    return math.trunc(float(value) * factor) / factor


def _safe_location(row: Mapping[str, Any], mode: str, decimals: int) -> dict[str, Any]:
    lat = _to_float(_first(row, "latitude", "lat"))
    lon = _to_float(_first(row, "longitude", "lon", "lng"))
    valid = (
        lat is not None
        and lon is not None
        and -90.0 <= lat <= 90.0
        and -180.0 <= lon <= 180.0
        and not (lat == 0.0 and lon == 0.0)
    )
    if not valid:
        return {"available": False, "latitude": None, "longitude": None, "precision": "none"}

    mode = str(mode or "omit").lower()
    if mode == "omit":
        return {"available": True, "latitude": None, "longitude": None, "precision": "omitted"}
    if mode == "exact":
        return {"available": True, "latitude": lat, "longitude": lon, "precision": "exact"}
    if mode != "truncate":
        raise RatingSyncError(f"Unbekannter coordinate_mode: {mode}")

    return {
        "available": True,
        "latitude": truncate_decimal(lat, decimals),
        "longitude": truncate_decimal(lon, decimals),
        "precision": f"truncated_{int(decimals)}dp",
    }


def sanitize_observation(row: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    event_id = str(_first(row, str(config.get("event_id_column", "event_id")), "event_id", default="")).strip()
    if not event_id:
        raise RatingSyncError("Beobachtung ohne event_id")

    raw_rating = _first(row, "rating", "value")
    try:
        rating = int(raw_rating)
    except (TypeError, ValueError) as exc:
        raise RatingSyncError(f"Ungültige Bewertung event_id={event_id}: {raw_rating!r}") from exc
    if rating < -1 or rating > 5:
        raise RatingSyncError(f"Bewertung außerhalb -1..5 event_id={event_id}: {rating}")

    timestamp_column = str(config.get("timestamp_column", "response_time"))
    response_raw = _first(row, timestamp_column, "response_time", "created_at")
    response_time = _iso_utc(response_raw, timestamp_column)
    scheduled_time = _optional_iso_utc(_first(row, "scheduled_time"), "scheduled_time")

    observer_id = str(_first(row, "observer_id", "observer", "participant_id", default="")).strip() or None
    comment = _first(row, "comment", "observation_comment")

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "observer_id": observer_id,
        "scheduled_time_utc": scheduled_time,
        "response_time_utc": response_time,
        "rating": rating,
        "location": _safe_location(
            row,
            str(config.get("coordinate_mode", "truncate")),
            int(config.get("coordinate_decimals", 2)),
        ),
        "app_version": _first(row, "app_version"),
        "has_comment": bool(str(comment).strip()) if comment is not None else False,
        "source": "LFN-Scout/Supabase",
    }
    if bool(config.get("include_comment", False)):
        result["comment"] = None if comment is None else str(comment)
    return result


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise RatingSyncError("ratings_sync_config.json muss ein JSON-Objekt enthalten")
        cfg.update(data)

    if os.environ.get("SUPABASE_URL"):
        cfg["supabase_url"] = os.environ["SUPABASE_URL"].strip()
    if os.environ.get("SUPABASE_RATINGS_TABLE"):
        cfg["table"] = os.environ["SUPABASE_RATINGS_TABLE"].strip()
    if os.environ.get("RATINGS_ARCHIVE_DIR"):
        cfg["archive_dir"] = os.environ["RATINGS_ARCHIVE_DIR"].strip()
    return cfg


def resolve_supabase_key() -> str:
    for name in ("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    raise RatingSyncError(
        "Supabase-Backend-Schlüssel fehlt. GitHub Secret SUPABASE_SECRET_KEY "
        "(bevorzugt sb_secret_...) oder legacy SUPABASE_SERVICE_ROLE_KEY setzen."
    )


def _request_json(url: str, key: str, timeout: int = 45) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "apikey": key,
            "User-Agent": "InversionAnalyzer-RatingsSync/0.15.24",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RatingSyncError(f"Supabase HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RatingSyncError(f"Supabase nicht erreichbar: {exc}") from exc

    try:
        data = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise RatingSyncError("Supabase lieferte kein gültiges JSON") from exc
    if not isinstance(data, list):
        raise RatingSyncError(f"Unerwartete Supabase-Antwort: {type(data).__name__}")
    return [x for x in data if isinstance(x, dict)]


def fetch_observations(
    config: Mapping[str, Any],
    key: str,
    since_utc: str | None = None,
) -> list[dict[str, Any]]:
    base = str(config.get("supabase_url", "")).rstrip("/")
    if not base.startswith("https://"):
        raise RatingSyncError("supabase_url fehlt oder ist keine HTTPS-URL")
    table = str(config.get("table", "observations")).strip()
    if not table or not all(c.isalnum() or c in "_-" for c in table):
        raise RatingSyncError(f"Ungültiger Tabellenname: {table!r}")

    timestamp_column = str(config.get("timestamp_column", "response_time"))
    event_id_column = str(config.get("event_id_column", "event_id"))
    page_size = max(1, min(int(config.get("page_size", 1000)), 1000))

    all_rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        params: list[tuple[str, str]] = [
            ("select", "*"),
            ("order", f"{timestamp_column}.asc,{event_id_column}.asc"),
            ("limit", str(page_size)),
            ("offset", str(offset)),
        ]
        if since_utc:
            params.append((timestamp_column, f"gte.{since_utc}"))
        query = urllib.parse.urlencode(params, safe="*.,:-+T")
        url = f"{base}/rest/v1/{urllib.parse.quote(table, safe='_-')}?{query}"
        rows = _request_json(url, key)
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_rows


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_text_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return True


def _day_key(event: Mapping[str, Any]) -> str:
    return str(event["response_time_utc"])[:10]


def _day_dir(root: Path, day: str) -> Path:
    year, month, _ = day.split("-")
    return root / year / month / day


def _event_sort_key(event: Mapping[str, Any]) -> tuple[str, str]:
    return str(event.get("response_time_utc", "")), str(event.get("event_id", ""))


def _summary(day: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(e.get("rating")) for e in events)
    observers = sorted({str(e.get("observer_id")) for e in events if e.get("observer_id")})
    times = [str(e.get("response_time_utc")) for e in events if e.get("response_time_utc")]
    return {
        "schema_version": SCHEMA_VERSION,
        "day_utc": day,
        "event_count": len(events),
        "observer_count": len(observers),
        "rating_counts": {str(k): int(counts.get(str(k), 0)) for k in (-1, 0, 1, 2, 3, 4, 5)},
        "first_response_time_utc": min(times) if times else None,
        "last_response_time_utc": max(times) if times else None,
        "location_precision": sorted({str(e.get("location", {}).get("precision")) for e in events}),
    }


def merge_into_archive(
    raw_rows: Iterable[Mapping[str, Any]],
    archive_root: Path,
    config: Mapping[str, Any],
) -> tuple[int, int, int, int, str | None]:
    accepted: list[dict[str, Any]] = []
    rejected = 0
    for row in raw_rows:
        try:
            accepted.append(sanitize_observation(row, config))
        except RatingSyncError as exc:
            rejected += 1
            print(f"WARNUNG: Datensatz verworfen: {exc}")

    incoming_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in accepted:
        incoming_by_day[_day_key(event)].append(event)

    written_days = 0
    archive_total = 0
    archive_root.mkdir(parents=True, exist_ok=True)

    for day in sorted(incoming_by_day):
        day_dir = _day_dir(archive_root, day)
        data_path = day_dir / "ratings.jsonl"
        existing = _read_jsonl(data_path)
        merged = {str(e.get("event_id")): e for e in existing if e.get("event_id")}
        for event in incoming_by_day[day]:
            merged[str(event["event_id"])] = event
        events = sorted(merged.values(), key=_event_sort_key)
        text = "".join(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for e in events)
        data_changed = _write_text_if_changed(data_path, text)
        summary_text = json.dumps(_summary(day, events), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        summary_changed = _write_text_if_changed(day_dir / "summary.json", summary_text)
        if data_changed or summary_changed:
            written_days += 1

    # Count the whole archive and determine its latest response timestamp.
    latest: str | None = None
    for path in archive_root.glob("*/*/*/ratings.jsonl"):
        for event in _read_jsonl(path):
            archive_total += 1
            ts = event.get("response_time_utc")
            if ts and (latest is None or str(ts) > latest):
                latest = str(ts)

    return len(accepted), rejected, written_days, archive_total, latest


def compute_since_from_state(archive_root: Path, overlap_hours: int) -> str | None:
    state = _load_json(archive_root / "sync_state.json", {})
    latest = state.get("max_response_time_utc") if isinstance(state, dict) else None
    if not latest:
        return None
    dt = _parse_datetime(latest, "max_response_time_utc") - timedelta(hours=max(0, int(overlap_hours)))
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def write_sync_state(
    archive_root: Path,
    result: SyncResult,
    since_utc: str | None,
    config: Mapping[str, Any],
) -> None:
    path = archive_root / "sync_state.json"
    previous = _load_json(path, {})
    core = {
        "schema_version": SCHEMA_VERSION,
        "query_since_utc": since_utc,
        "max_response_time_utc": result.max_response_time_utc,
        "archive_event_count": result.archive_events,
        "last_fetch_count": result.fetched,
        "last_accepted_count": result.accepted,
        "last_rejected_count": result.rejected,
        "table": str(config.get("table", "observations")),
        "coordinate_mode": str(config.get("coordinate_mode", "truncate")),
        "coordinate_decimals": int(config.get("coordinate_decimals", 2)),
        "comment_exported": bool(config.get("include_comment", False)),
    }
    previous_core = {k: previous.get(k) for k in core} if isinstance(previous, dict) else {}
    if path.exists() and previous_core == core:
        return
    state = dict(core)
    state["last_successful_sync_utc"] = _utc_now_iso()
    _write_text_if_changed(
        path,
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def synchronize(
    config: Mapping[str, Any],
    *,
    full: bool = False,
    archive_root: Path | None = None,
    key: str | None = None,
) -> SyncResult:
    root = archive_root or Path(str(config.get("archive_dir", "archive/ratings")))
    overlap = int(config.get("overlap_hours", 48))
    since = None if full else compute_since_from_state(root, overlap)
    backend_key = key or resolve_supabase_key()
    rows = fetch_observations(config, backend_key, since_utc=since)
    accepted, rejected, written_days, archive_total, latest = merge_into_archive(rows, root, config)
    result = SyncResult(
        fetched=len(rows),
        accepted=accepted,
        rejected=rejected,
        written_days=written_days,
        archive_events=archive_total,
        max_response_time_utc=latest,
    )
    write_sync_state(root, result, since, config)
    return result
