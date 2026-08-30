# -*- coding: utf-8 -*-
"""
KIT Meteomast Bokeh client v0.15.20

Robust client for the short rolling KIT/ATMOHub Bokeh profile window.

v0.15.20:
- unveränderte Timeout/Retry-Logik; Parser-Fix liegt in kit_inversion.py

v0.15.19:
- hard per-attempt timeout in an isolated child process
- up to three Bokeh attempts
- configurable retry delays (default 5 s, 15 s)
- explicit timeout/connect/empty/error states
- no replacement of archive data here; cumulative safe merge remains in archive.py

Important timestamp rule:
KIT ``localtime`` is an empirically validated Europe/Berlin wall-clock
millisecond value.  It must NOT be interpreted as UTC and converted again.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import queue
import time
from pathlib import Path

import pandas as pd

from .config import (
    LOG_DIR,
    KIT_BOKEH_TIMEOUT,
    KIT_BOKEH_MAX_ATTEMPTS,
    KIT_BOKEH_RETRY_DELAYS_SEC,
)
from .logger import LOGGER
from .timestamp_validation import convert_kit_localtime_ms


def _convert_localtime_column(data):
    if "localtime" not in data:
        return data
    values = data.get("localtime")
    if not isinstance(values, list):
        return data
    converted = []
    for value in values:
        try:
            converted.append(convert_kit_localtime_ms(value).isoformat())
        except Exception:
            converted.append(None)
    out = dict(data)
    out["localtime_iso"] = converted
    return out


def _model_name(model):
    try:
        return model.name or model.__class__.__name__
    except Exception:
        return model.__class__.__name__


def _safe_jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_safe_jsonable(x) for x in value]
    if isinstance(value, tuple):
        return [_safe_jsonable(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _safe_jsonable(v) for k, v in value.items()}
    try:
        if hasattr(value, "tolist"):
            return value.tolist()
    except Exception:
        pass
    return str(value)


def _source_dict(source):
    data = {}
    for key, value in getattr(source, "data", {}).items():
        data[str(key)] = _safe_jsonable(value)
    data = _convert_localtime_column(data)
    row_count = 0
    for value in data.values():
        if isinstance(value, list):
            row_count = max(row_count, len(value))
    return {
        "id": getattr(source, "id", None),
        "name": _model_name(source),
        "columns": sorted(data.keys()),
        "row_count_estimate": row_count,
        "data": data,
    }


def _classify_columns(columns):
    names = [str(x) for x in columns]
    lower = [x.lower() for x in names]
    time_cols = [n for n, l in zip(names, lower) if any(t in l for t in ("time", "date", "datetime", "timestamp"))]
    temp_cols = [n for n, l in zip(names, lower) if any(t in l for t in ("temp", "temperature", "temperatur", "ta", "t_"))]
    height_cols = [n for n, l in zip(names, lower) if any(t in l for t in ("height", "höhe", "hoehe", "level", "meter"))]
    score = (2 if time_cols else 0) + (3 if temp_cols else 0) + (2 if height_cols else 0)
    return {
        "heuristic_score": score,
        "time_columns": time_cols,
        "temperature_columns": temp_cols,
        "height_columns": height_cols,
    }


def _save_sources(run_id, sources):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    json_path = LOG_DIR / f"kit_bokeh_sources_{run_id}.json"
    json_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    csv_paths = []
    for i, src in enumerate(sources, start=1):
        data = src.get("data", {})
        if not data:
            continue
        try:
            frame = pd.DataFrame(data)
        except Exception:
            continue
        if frame.empty:
            continue
        csv_path = LOG_DIR / f"kit_bokeh_source_{run_id}_{i:02d}.csv"
        frame.to_csv(csv_path, index=False)
        csv_paths.append(str(csv_path))
    return str(json_path), csv_paths


def _classify_exception(exc):
    name = exc.__class__.__name__.upper()
    text = str(exc)
    low = text.lower()
    if "timeout" in name or "timeout" in low or "timed out" in low:
        return "BOKEH_CLIENT_TIMEOUT"
    if any(x in low for x in ("connect", "connection", "websocket", "socket", "network", "dns", "name or service")):
        return "BOKEH_CLIENT_CONNECT_ERROR"
    return "BOKEH_CLIENT_ERROR"


def _pull_once(url, run_id):
    """One normal Bokeh pull. Executed inside a killable child process."""
    try:
        from bokeh.client import pull_session
        from bokeh.models import ColumnDataSource
    except Exception as exc:
        return {
            "ok": False,
            "state": "BOKEH_CLIENT_MISSING",
            "message": "Bokeh-Pythonpaket nicht verfügbar oder Client-Import fehlgeschlagen",
            "detail": str(exc),
            "sources": [], "json_file": None, "csv_files": [],
        }

    session = None
    try:
        session = pull_session(url=url)
        doc = session.document
        roots = list(doc.roots)
        root_info = [
            {"id": getattr(root, "id", None), "type": root.__class__.__name__, "name": getattr(root, "name", None)}
            for root in roots
        ]
        sources = []
        for model in doc.select({"type": ColumnDataSource}):
            item = _source_dict(model)
            item.update(_classify_columns(item["columns"]))
            sources.append(item)
        sources.sort(key=lambda x: (-x.get("heuristic_score", 0), -x.get("row_count_estimate", 0)))
        json_file, csv_files = _save_sources(run_id, sources)
        return {
            "ok": bool(sources),
            "state": "BOKEH_CLIENT_DATA" if sources else "BOKEH_CLIENT_EMPTY",
            "message": (
                f"{len(sources)} ColumnDataSource-Objekt(e) aus Bokeh-Dokument geladen"
                if sources else "Bokeh-Dokument geladen, aber keine ColumnDataSource gefunden"
            ),
            "detail": f"Roots={len(roots)}; Rohdaten JSON={json_file}; CSV-Dateien={len(csv_files)}",
            "roots": root_info,
            "sources": sources,
            "json_file": json_file,
            "csv_files": csv_files,
        }
    except Exception as exc:
        return {
            "ok": False,
            "state": _classify_exception(exc),
            "message": "Bokeh-Session konnte nicht geladen werden",
            "detail": f"{exc.__class__.__name__}: {exc}",
            "sources": [], "json_file": None, "csv_files": [],
        }
    finally:
        try:
            if session is not None:
                session.close()
        except Exception:
            pass


def _worker(out_queue, url, run_id):
    try:
        out_queue.put(_pull_once(url, run_id))
    except BaseException as exc:
        out_queue.put({
            "ok": False,
            "state": "BOKEH_CLIENT_ERROR",
            "message": "Bokeh-Worker ist fehlgeschlagen",
            "detail": f"{exc.__class__.__name__}: {exc}",
            "sources": [], "json_file": None, "csv_files": [],
        })


def _pull_with_hard_timeout(url, run_id, timeout_sec):
    """Run one pull in a separate process so a hung websocket can be killed."""
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_worker, args=(out_queue, url, run_id), daemon=True)
    proc.start()
    proc.join(timeout=max(1.0, float(timeout_sec)))
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=2.0)
        try:
            out_queue.close()
        except Exception:
            pass
        return {
            "ok": False,
            "state": "BOKEH_CLIENT_TIMEOUT",
            "message": f"Bokeh-Session nach {timeout_sec:g} s abgebrochen",
            "detail": "Harter Timeout: isolierter Bokeh-Prozess wurde beendet",
            "sources": [], "json_file": None, "csv_files": [],
        }
    try:
        result = out_queue.get(timeout=1.0)
    except queue.Empty:
        result = {
            "ok": False,
            "state": "BOKEH_CLIENT_ERROR",
            "message": "Bokeh-Worker endete ohne Ergebnis",
            "detail": f"exitcode={proc.exitcode}",
            "sources": [], "json_file": None, "csv_files": [],
        }
    finally:
        try:
            out_queue.close()
        except Exception:
            pass
    return result


def pull_bokeh_document(url, run_id, log_cb=None, timeout_sec=None, max_attempts=None, retry_delays=None):
    """Pull KIT Bokeh data with hard timeout and bounded retries."""
    def log(msg):
        LOGGER.info(msg)
        if log_cb:
            log_cb(msg)

    timeout_sec = float(KIT_BOKEH_TIMEOUT if timeout_sec is None else timeout_sec)
    max_attempts = int(KIT_BOKEH_MAX_ATTEMPTS if max_attempts is None else max_attempts)
    max_attempts = max(1, max_attempts)
    retry_delays = list(KIT_BOKEH_RETRY_DELAYS_SEC if retry_delays is None else retry_delays)

    attempts = []
    last = None
    for attempt in range(1, max_attempts + 1):
        attempt_run_id = run_id if attempt == 1 else f"{run_id}_retry{attempt}"
        log(f"KIT-Bokeh-Client: Versuch {attempt}/{max_attempts} | harter Timeout {timeout_sec:g} s | Session öffnen: {url}")
        started = time.monotonic()
        result = _pull_with_hard_timeout(url, attempt_run_id, timeout_sec)
        elapsed = round(time.monotonic() - started, 3)
        result["attempt"] = attempt
        result["elapsed_sec"] = elapsed
        attempts.append({
            "attempt": attempt,
            "state": result.get("state"),
            "ok": bool(result.get("ok")),
            "elapsed_sec": elapsed,
            "detail": result.get("detail", ""),
        })
        last = result

        if result.get("ok") and (result.get("sources") or []):
            roots = result.get("roots", []) or []
            sources = result.get("sources", []) or []
            log(f"KIT-Bokeh-Client: Verbindung erfolgreich | Versuch {attempt}/{max_attempts} | {len(roots)} Root(s) | {len(sources)} ColumnDataSource-Objekt(e) | {elapsed:.1f} s")
            for i, src in enumerate(sources[:10], start=1):
                data = src.get("data", {}) or {}
                local_iso = data.get("localtime_iso", [])
                sample_time = local_iso[0] if isinstance(local_iso, list) and local_iso else "–"
                log(f"KIT-Bokeh-Client CDS {i}: id={src.get('id')} | Score={src.get('heuristic_score')} | Zeilen≈{src.get('row_count_estimate')} | Zeit={sample_time} | Spalten={src.get('columns')}")
            result["attempts"] = attempts
            return result

        state = result.get("state", "BOKEH_CLIENT_ERROR")
        log(f"KIT-Bokeh-Client: Versuch {attempt}/{max_attempts} fehlgeschlagen | {state} | {result.get('message')} | {elapsed:.1f} s")
        if state == "BOKEH_CLIENT_MISSING":
            break
        if attempt < max_attempts:
            delay = float(retry_delays[min(attempt - 1, len(retry_delays) - 1)]) if retry_delays else 0.0
            if delay > 0:
                log(f"KIT-Bokeh-Client: nächster Versuch in {delay:g} s")
                time.sleep(delay)

    last = dict(last or {})
    last.setdefault("ok", False)
    last.setdefault("state", "BOKEH_CLIENT_ERROR")
    last.setdefault("message", "Bokeh-Session konnte nicht geladen werden")
    last.setdefault("detail", "Kein Bokeh-Ergebnis")
    last.setdefault("sources", [])
    last.setdefault("json_file", None)
    last.setdefault("csv_files", [])
    last["attempts"] = attempts
    last["attempt_count"] = len(attempts)
    return last
