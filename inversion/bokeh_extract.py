# -*- coding: utf-8 -*-
"""
Bokeh HTML extractor for KIT Meteomast v0.8.0.

Conservative design:
- Parses only data already delivered in HTML.
- Does not execute JavaScript.
- Does not connect to arbitrary WebSocket endpoints.
- Does not use OCR.
- Extracted ColumnDataSource objects are diagnostic candidates only.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any


def _walk(obj: Any, path="$"):
    """Yield (path, value) recursively for dict/list structures."""
    yield path, obj
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from _walk(value, f"{path}[{i}]")


def _json_loads_loose(text: str):
    """Try ordinary JSON plus HTML-unescaped JSON."""
    for candidate in (text, html_lib.unescape(text)):
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None


def extract_json_script_blocks(html_text: str):
    """
    Extract <script type="application/json">...</script> blocks.
    Bokeh frequently embeds docs/render payloads this way.
    """
    blocks = []
    rx = re.compile(
        r'<script(?P<attrs>[^>]*)type=["\']application/json["\'](?P<attrs2>[^>]*)>'
        r'(?P<body>.*?)</script>',
        re.I | re.S,
    )
    for i, m in enumerate(rx.finditer(html_text)):
        body = m.group("body").strip()
        obj = _json_loads_loose(body)
        blocks.append({
            "index": i,
            "length": len(body),
            "parsed": obj is not None,
            "json": obj,
        })
    return blocks


def extract_bokeh_marker_strings(html_text: str):
    markers = {}
    for marker in (
        "Bokeh.embed",
        "embed_items",
        "docs_json",
        "render_items",
        "ColumnDataSource",
        "Document",
        "roots",
        "server_document",
        "autoload_server",
        "sessionid",
        "websocket_url",
    ):
        markers[marker] = html_text.count(marker)
    return markers


def extract_docs_json_assignments(html_text: str):
    """
    Best-effort extraction of common Bokeh assignments.

    Handles patterns such as:
      const docs_json = {...};
      var docs_json = {...};
      docs_json = {...};

    This deliberately avoids trying to evaluate arbitrary JavaScript.
    """
    results = []
    for name in ("docs_json", "render_items"):
        for m in re.finditer(
            rf'(?:const|let|var)?\s*{name}\s*=\s*',
            html_text,
            re.I,
        ):
            start = m.end()
            obj_text = _balanced_json_fragment(html_text, start)
            obj = _json_loads_loose(obj_text) if obj_text else None
            results.append({
                "name": name,
                "offset": m.start(),
                "length": len(obj_text) if obj_text else 0,
                "parsed": obj is not None,
                "json": obj,
            })
    return results


def _balanced_json_fragment(text: str, start: int):
    """
    Extract one balanced JSON object/array starting at or after start.
    String/escape aware enough for normal embedded JSON.
    """
    i = start
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] not in "[{":
        return None

    opener = text[i]
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_string = False
    escape = False
    begin = i

    for j in range(i, len(text)):
        ch = text[j]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[begin:j + 1]

    return None


def _looks_like_column_data_source(node):
    if not isinstance(node, dict):
        return False

    # Bokeh 2.x/3.x variants.
    name = str(node.get("name", ""))
    typ = str(node.get("type", ""))
    if "ColumnDataSource" in name or "ColumnDataSource" in typ:
        return True

    attrs = node.get("attributes")
    if isinstance(attrs, dict) and isinstance(attrs.get("data"), dict):
        # Require stronger Bokeh-ish context than merely any dict with data.
        if node.get("id") is not None and (
            "selected" in attrs
            or "selection_policy" in attrs
            or "data" in attrs
        ):
            return True

    return False


def extract_column_data_sources(objects):
    """
    Find ColumnDataSource-like objects in parsed JSON payloads.
    Returns only metadata and the contained column arrays.
    """
    found = []
    seen = set()

    for source_name, obj in objects:
        if obj is None:
            continue
        for path, node in _walk(obj):
            if not _looks_like_column_data_source(node):
                continue

            attrs = node.get("attributes", {}) if isinstance(node, dict) else {}
            data = attrs.get("data", {}) if isinstance(attrs, dict) else {}
            if not isinstance(data, dict):
                continue

            source_id = node.get("id")
            key = (source_name, str(source_id), path)
            if key in seen:
                continue
            seen.add(key)

            columns = {}
            max_len = 0
            for col, values in data.items():
                if isinstance(values, list):
                    columns[col] = values
                    max_len = max(max_len, len(values))
                elif isinstance(values, dict):
                    # Bokeh may use ndarray encodings or map-like values.
                    columns[col] = values

            found.append({
                "source": source_name,
                "path": path,
                "id": source_id,
                "name": node.get("name") or node.get("type") or "ColumnDataSource",
                "columns": columns,
                "column_names": sorted(columns.keys()),
                "row_count_estimate": max_len,
            })

    return found


def classify_temperature_like_sources(column_sources):
    """
    Heuristic only. Does NOT assert that a column is temperature.
    Scores names that contain recognizable time/temperature/height tokens.
    """
    out = []
    for src in column_sources:
        names = [str(x) for x in src.get("column_names", [])]
        lower = [x.lower() for x in names]

        time_cols = [
            n for n, l in zip(names, lower)
            if any(t in l for t in ("time", "date", "datetime", "timestamp", "x"))
        ]
        temp_cols = [
            n for n, l in zip(names, lower)
            if any(t in l for t in ("temp", "temperature", "temperatur", "ta", "t_"))
        ]
        height_cols = [
            n for n, l in zip(names, lower)
            if any(t in l for t in ("height", "hoehe", "höhe", "level", "meter", "m_"))
        ]

        score = 0
        if time_cols:
            score += 2
        if temp_cols:
            score += 3
        if height_cols:
            score += 2

        item = dict(src)
        item["heuristic_score"] = score
        item["time_columns"] = time_cols
        item["temperature_columns"] = temp_cols
        item["height_columns"] = height_cols
        out.append(item)

    out.sort(key=lambda x: (-x["heuristic_score"], -x.get("row_count_estimate", 0)))
    return out


def analyze_bokeh_html(html_text: str):
    scripts = extract_json_script_blocks(html_text)
    assignments = extract_docs_json_assignments(html_text)
    markers = extract_bokeh_marker_strings(html_text)

    parsed_objects = []
    for item in scripts:
        if item["parsed"]:
            parsed_objects.append((f"application_json_{item['index']}", item["json"]))
    for item in assignments:
        if item["parsed"]:
            parsed_objects.append((item["name"], item["json"]))

    cds = extract_column_data_sources(parsed_objects)
    ranked = classify_temperature_like_sources(cds)

    return {
        "markers": markers,
        "application_json_blocks": [
            {k: v for k, v in item.items() if k != "json"}
            for item in scripts
        ],
        "assignment_blocks": [
            {k: v for k, v in item.items() if k != "json"}
            for item in assignments
        ],
        "column_data_sources": cds,
        "ranked_column_data_sources": ranked,
        "parsed_payload_count": len(parsed_objects),
    }
