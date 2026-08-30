# -*- coding: utf-8 -*-
"""
Measured KIT 200-m mast inversion processing.

v0.15.20:
- einzelne fehlende/NaN-Sensorwerte verwerfen nicht mehr das Gesamtprofil
- zusätzliche Nicht-Temperaturzeilen in einer CDS werden ignoriert
- mindestens zwei gültige Temperaturhöhen reichen für die Profilberechnung
- Diagnose protokolliert verwendete/fehlende Höhen je unvollständigem Profil

Only variables matching
    PT_T_AIR_<height>_AVG
are interpreted as mast temperature values.

The KIT mast index is an empirical diagnostic 0..5 score and is kept
strictly separate from the existing location model index.
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd

from .config import TIMEZONE


TEMP_RX = re.compile(r"^PT_T_AIR_(\d{3})_AVG$")


def _finite_float(value):
    """Return finite float or None for None/NaN/inf/non-numeric values."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _temperature_source_to_profile(source):
    data = source.get("data", {}) or {}
    variables = data.get("variable", [])
    values = data.get("value", [])
    altitudes = data.get("altitude", [])
    local_iso = data.get("localtime_iso", [])
    local_raw = data.get("localtime", [])

    if not all(isinstance(x, list) for x in (variables, values, altitudes)):
        return None
    if not variables or not (len(variables) == len(values) == len(altitudes)):
        return None

    parsed = []
    missing_levels = []
    ignored_non_temperature_rows = 0
    invalid_level_rows = 0

    for var, value, altitude in zip(variables, values, altitudes):
        m = TEMP_RX.match(str(var))
        if not m:
            # A Bokeh ColumnDataSource may contain auxiliary rows.  They must
            # not invalidate otherwise valid temperature measurements.
            ignored_non_temperature_rows += 1
            continue

        h_from_name = int(m.group(1))
        h = _finite_float(altitude)
        if h is None or abs(h_from_name - h) > 0.1:
            invalid_level_rows += 1
            continue

        v = _finite_float(value)
        if v is None:
            missing_levels.append(h_from_name)
            continue

        parsed.append((h, v, str(var)))

    # Need at least two valid levels to calculate a vertical gradient.
    if len(parsed) < 2:
        return None

    # One source represents one vertical profile. All available timestamps
    # should match.  Empty timestamps are ignored.
    iso_values = [str(x) for x in local_iso if x]
    if iso_values:
        if len(set(iso_values)) != 1:
            return None
        time = pd.Timestamp(iso_values[0])
    elif local_raw:
        raw_values = [x for x in local_raw if x is not None]
        if not raw_values:
            return None
        time = pd.to_datetime(raw_values[0], unit="ms").tz_localize(TIMEZONE)
    else:
        return None

    if time.tzinfo is None:
        time = time.tz_localize(TIMEZONE)
    else:
        time = time.tz_convert(TIMEZONE)

    parsed.sort(key=lambda x: x[0])
    return {
        "time": time,
        "levels": parsed,
        "source_id": source.get("id"),
        "missing_levels": sorted(set(missing_levels)),
        "ignored_non_temperature_rows": ignored_non_temperature_rows,
        "invalid_level_rows": invalid_level_rows,
    }


def _profile_metrics(profile):
    levels = profile["levels"]
    if len(levels) < 2:
        return None

    positive_dt = 0.0
    positive_depth = 0.0
    max_gradient = 0.0
    strongest_layer = None
    positive_layers = []

    for (z1, t1, _), (z2, t2, _) in zip(levels[:-1], levels[1:]):
        dz = z2 - z1
        if dz <= 0:
            continue
        dt = t2 - t1
        grad = dt / dz * 100.0
        if dt > 0:
            positive_dt += dt
            positive_depth += dz
            positive_layers.append((z1, z2, dt, grad))
            if grad > max_gradient:
                max_gradient = grad
                strongest_layer = (z1, z2, dt, grad)

    # Determine continuous inversion layer with largest total positive ΔT.
    best_layer = None
    current = None
    for z1, z2, dt, grad in positive_layers:
        if current is None:
            current = [z1, z2, dt]
        elif abs(current[1] - z1) < 0.1:
            current[1] = z2
            current[2] += dt
        else:
            if best_layer is None or current[2] > best_layer[2]:
                best_layer = current
            current = [z1, z2, dt]
    if current is not None and (best_layer is None or current[2] > best_layer[2]):
        best_layer = current

    if best_layer:
        inv_base, inv_top, layer_delta = best_layer
        layer_depth = inv_top - inv_base
    else:
        inv_base = inv_top = layer_delta = layer_depth = 0.0

    # Empirical mast-specific 0..5 diagnostic index.
    grad_score = np.clip(max_gradient / 5.0, 0.0, 1.0)
    dt_score = np.clip(layer_delta / 3.0, 0.0, 1.0)
    depth_score = np.clip(layer_depth / 100.0, 0.0, 1.0)
    index = 5.0 * (0.40 * grad_score + 0.40 * dt_score + 0.20 * depth_score)

    row = {
        "time": profile["time"],
        "kit_mast_index": float(index),
        "kit_max_positive_gradient_K_per_100m": float(max_gradient),
        "kit_positive_deltaT_K": float(positive_dt),
        "kit_inversion_base_m": float(inv_base),
        "kit_inversion_top_m": float(inv_top),
        "kit_inversion_depth_m": float(layer_depth),
        "kit_inversion_deltaT_K": float(layer_delta),
        "kit_source_id": profile.get("source_id"),
        "kit_profile_levels": len(levels),
        "kit_missing_levels": ",".join(str(x) for x in profile.get("missing_levels", [])),
    }

    for z, t, _ in levels:
        if abs(z - round(z)) < 1e-9:
            row[f"kit_temperature_{int(round(z))}m_C"] = float(t)

    return row


def extract_kit_temperature_profiles(client_sources, selected_date, log_cb=None):
    """Extract, date-filter, sort and calculate measured KIT mast metrics."""

    def log(msg):
        if log_cb:
            log_cb(msg)

    profiles = []
    rejected_non_temp = 0
    rejected_invalid = 0
    incomplete_profiles = 0

    for source in client_sources or []:
        variables = (source.get("data", {}) or {}).get("variable", [])

        # Require at least one recognizable mast-temperature variable.  Other
        # rows in the same CDS are allowed and ignored by the parser.
        if not variables or not any(TEMP_RX.match(str(v)) for v in variables):
            rejected_non_temp += 1
            continue

        profile = _temperature_source_to_profile(source)
        if profile is None:
            rejected_invalid += 1
            continue

        if profile.get("missing_levels"):
            incomplete_profiles += 1
        profiles.append(profile)

    profiles.sort(key=lambda x: x["time"])
    all_count = len(profiles)
    selected = [p for p in profiles if p["time"].date() == selected_date]

    rows = []
    for profile in selected:
        missing = profile.get("missing_levels", [])
        if missing:
            log(
                f"KIT {profile['time']:%H:%M}: "
                f"fehlende Höhe(n) {','.join(str(x) + ' m' for x in missing)}; "
                f"Profil mit {len(profile['levels'])} gültigen Höhen verwendet."
            )

        row = _profile_metrics(profile)
        if row is not None:
            rows.append(row)

    if not rows:
        log(
            f"KIT-Mast Temperatur: {all_count} verwendbare Temperaturprofil(e) erkannt, "
            f"aber 0 für ausgewähltes Datum {selected_date}. "
            f"Ungültig verworfen={rejected_invalid}, Nicht-Temperatur-CDS={rejected_non_temp}."
        )
        return None, {
            "recognized_profiles": all_count,
            "selected_profiles": 0,
            "incomplete_profiles": incomplete_profiles,
            "rejected_non_temperature_sources": rejected_non_temp,
            "rejected_invalid_temperature_sources": rejected_invalid,
        }

    df = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)

    log(
        f"KIT-Mast Temperatur: {all_count} verwendbare Temperaturprofil(e) erkannt, "
        f"{len(df)} für {selected_date} verwendet; "
        f"davon {sum(bool(p.get('missing_levels')) for p in selected)} mit fehlender Höhe."
    )
    log(
        "KIT-Mast Zeitraum: "
        f"{df['time'].iloc[0].strftime('%Y-%m-%d %H:%M %Z')} bis "
        f"{df['time'].iloc[-1].strftime('%Y-%m-%d %H:%M %Z')}."
    )

    for _, row in df.iterrows():
        log(
            f"KIT-Inversion {row['time']:%H:%M}: "
            f"Index={row['kit_mast_index']:.2f}/5 | "
            f"Schicht={row['kit_inversion_base_m']:.0f}-"
            f"{row['kit_inversion_top_m']:.0f} m | "
            f"ΔT={row['kit_inversion_deltaT_K']:.2f} K | "
            f"maxGrad={row['kit_max_positive_gradient_K_per_100m']:.2f} K/100m | "
            f"Höhen={int(row['kit_profile_levels'])}"
        )

    return df, {
        "recognized_profiles": all_count,
        "selected_profiles": len(df),
        "incomplete_profiles": incomplete_profiles,
        "rejected_non_temperature_sources": rejected_non_temp,
        "rejected_invalid_temperature_sources": rejected_invalid,
    }
