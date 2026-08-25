# -*- coding: utf-8 -*-
"""
KIT Meteomast Bokeh client v0.9.0

Uses the official Bokeh Python client to pull the current server-side
document and inventories all ColumnDataSource models.

Important:
- Retrieved sources are diagnostics until meteorologically validated.
- No source is used for the inversion index in v0.9.0.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .config import LOG_DIR, TIMEZONE
from .logger import LOGGER
from .timestamp_validation import convert_kit_localtime_ms



def _convert_localtime_column(data):
    """
    Preserve the raw KIT localtime value and add timezone-aware ISO local time.
    KIT 'localtime' is empirically a local wall-clock millisecond value.
    """
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

    time_cols = [
        n for n, l in zip(names, lower)
        if any(t in l for t in ("time", "date", "datetime", "timestamp"))
    ]
    temp_cols = [
        n for n, l in zip(names, lower)
        if any(t in l for t in ("temp", "temperature", "temperatur", "ta", "t_"))
    ]
    height_cols = [
        n for n, l in zip(names, lower)
        if any(t in l for t in ("height", "höhe", "hoehe", "level", "meter"))
    ]

    score = 0
    if time_cols:
        score += 2
    if temp_cols:
        score += 3
    if height_cols:
        score += 2

    return {
        "heuristic_score": score,
        "time_columns": time_cols,
        "temperature_columns": temp_cols,
        "height_columns": height_cols,
    }


def _save_sources(run_id, sources):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    json_path = LOG_DIR / f"kit_bokeh_sources_{run_id}.json"
    json_path.write_text(
        json.dumps(sources, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

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


def pull_bokeh_document(url, run_id, log_cb=None):
    def log(msg):
        LOGGER.info(msg)
        if log_cb:
            log_cb(msg)

    try:
        from bokeh.client import pull_session
        from bokeh.models import ColumnDataSource
    except Exception as exc:
        return {
            "ok": False,
            "state": "BOKEH_CLIENT_MISSING",
            "message": (
                "Bokeh-Pythonpaket nicht verfügbar oder Client-Import fehlgeschlagen"
            ),
            "detail": str(exc),
            "sources": [],
            "json_file": None,
            "csv_files": [],
        }

    session = None
    try:
        log(f"KIT-Bokeh-Client: Session öffnen: {url}")
        session = pull_session(url=url)
        doc = session.document

        roots = list(doc.roots)
        root_info = [
            {
                "id": getattr(root, "id", None),
                "type": root.__class__.__name__,
                "name": getattr(root, "name", None),
            }
            for root in roots
        ]

        sources = []
        for model in doc.select({"type": ColumnDataSource}):
            item = _source_dict(model)
            item.update(_classify_columns(item["columns"]))
            sources.append(item)

        sources.sort(
            key=lambda x: (
                -x.get("heuristic_score", 0),
                -x.get("row_count_estimate", 0),
            )
        )

        json_file, csv_files = _save_sources(run_id, sources)

        log(
            f"KIT-Bokeh-Client: Verbindung erfolgreich | "
            f"{len(roots)} Root(s) | {len(sources)} ColumnDataSource-Objekt(e)"
        )

        for i, src in enumerate(sources[:10], start=1):
            data=src.get("data",{}) or {}
            local_iso=data.get("localtime_iso",[])
            sample_time=local_iso[0] if isinstance(local_iso,list) and local_iso else "–"
            log(
                f"KIT-Bokeh-Client CDS {i}: "
                f"id={src.get('id')} | "
                f"Score={src.get('heuristic_score')} | "
                f"Zeilen≈{src.get('row_count_estimate')} | "
                f"Zeit={sample_time} | "
                f"Spalten={src.get('columns')}"
            )

        return {
            "ok": True,
            "state": "BOKEH_CLIENT_DATA" if sources else "BOKEH_CLIENT_EMPTY",
            "message": (
                f"{len(sources)} ColumnDataSource-Objekt(e) aus Bokeh-Dokument geladen"
                if sources
                else "Bokeh-Dokument geladen, aber keine ColumnDataSource gefunden"
            ),
            "detail": (
                f"Roots={len(roots)}; Rohdaten JSON={json_file}; "
                f"CSV-Dateien={len(csv_files)}"
            ),
            "roots": root_info,
            "sources": sources,
            "json_file": json_file,
            "csv_files": csv_files,
        }

    except Exception as exc:
        LOGGER.exception("KIT-Bokeh-Client fehlgeschlagen")
        return {
            "ok": False,
            "state": "BOKEH_CLIENT_ERROR",
            "message": "Bokeh-Session konnte nicht geladen werden",
            "detail": str(exc),
            "sources": [],
            "json_file": None,
            "csv_files": [],
        }
    finally:
        try:
            if session is not None:
                session.close()
        except Exception:
            pass
