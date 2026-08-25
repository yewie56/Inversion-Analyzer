# -*- coding: utf-8 -*-
"""
Open-Meteo Historical Forecast / DWD ICON-D2 comparison source v0.12.2

Key correction:
- temperature_2m is now part of the vertical profile
- pressure-level geopotential heights are converted from MSL to AGL using
  the returned Open-Meteo point elevation
- only physically valid pressure levels above ground are used
- raw hourly vertical profiles are exported for traceability
- no fallback to another weather model
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from .config import (
    LAT, LON, TIMEZONE, REQUEST_TIMEOUT,
    OPEN_METEO_ICON_D2_HISTORICAL_URL,
    OPEN_METEO_ICON_D2_MODEL,
)
from .models import SourceStatus

PRESSURE_LEVELS_FULL = (1000, 975, 950, 925, 900, 850)
PRESSURE_LEVELS_CORE = (1000, 975, 950, 850)


class IconD2RequestError(RuntimeError):
    def __init__(self, code, message, response_text=None):
        super().__init__(f"{code}: {message}")
        self.code=code
        self.message=message
        self.response_text=response_text or ""


def _request_json(url, params):
    try:
        r=requests.get(
            url, params=params, timeout=REQUEST_TIMEOUT,
            headers={"User-Agent":"Inversion-Analyzer/0.12.2"}
        )
    except requests.Timeout as exc:
        raise IconD2RequestError("TIMEOUT","Zeitüberschreitung") from exc
    except requests.ConnectionError as exc:
        raise IconD2RequestError("NETWORK","Netzwerk-/DNS-Fehler") from exc
    except requests.RequestException as exc:
        raise IconD2RequestError("REQUEST",str(exc)) from exc

    if r.status_code != 200:
        body=r.text[:1200]
        raise IconD2RequestError(f"HTTP_{r.status_code}",body or "HTTP-Fehler",body)
    try:
        data=r.json()
    except Exception as exc:
        raise IconD2RequestError("PARSING","Antwort ist kein gültiges JSON") from exc
    if not isinstance(data,dict):
        raise IconD2RequestError("FORMAT_CHANGED","JSON-Wurzel ist kein Objekt")
    return data


def _build_hourly_variables(levels):
    out=["temperature_2m"]
    for p in levels:
        out += [f"temperature_{p}hPa", f"geopotential_height_{p}hPa"]
    return out


def _make_params(selected_date, levels):
    return {
        "latitude":LAT,
        "longitude":LON,
        "start_date":selected_date.isoformat(),
        "end_date":selected_date.isoformat(),
        "timezone":TIMEZONE,
        "models":OPEN_METEO_ICON_D2_MODEL,
        "hourly":",".join(_build_hourly_variables(levels)),
    }


def _to_frame(data):
    hourly=data.get("hourly")
    if not isinstance(hourly,dict):
        raise IconD2RequestError("FORMAT_CHANGED","hourly fehlt")
    times=hourly.get("time")
    if not isinstance(times,list) or not times:
        raise IconD2RequestError("NO_DATA_DATE","keine hourly-Zeitwerte")
    frame=pd.DataFrame(hourly)
    frame["time"]=pd.to_datetime(frame["time"])
    if frame["time"].dt.tz is None:
        frame["time"]=frame["time"].dt.tz_localize(TIMEZONE)
    else:
        frame["time"]=frame["time"].dt.tz_convert(TIMEZONE)
    return frame,hourly


def _summarize_hourly(hourly):
    result={}
    if not isinstance(hourly,dict):
        return result
    for key,values in hourly.items():
        result[key]=sum(v is not None for v in values) if isinstance(values,list) else None
    return result


def _usable_pairs(frame,levels):
    usable=[]
    missing=[]
    for p in levels:
        tk=f"temperature_{p}hPa"
        hk=f"geopotential_height_{p}hPa"
        if tk not in frame.columns or hk not in frame.columns:
            missing.append((p,"Spalte fehlt"))
            continue
        n=int((frame[tk].notna() & frame[hk].notna()).sum())
        if n:
            usable.append((p,n))
        else:
            missing.append((p,"keine gültigen Werte"))
    return usable,missing


def _build_raw_profile_table(frame, levels, surface_elevation_m):
    """
    Long-form table, one row per hour/vertical level.
    height_agl_m:
      2 m for temperature_2m
      geopotential_height - returned surface elevation for pressure levels
    Pressure surfaces below/at ground are retained in raw table but marked
    usable_for_inversion=False.
    """
    rows=[]
    for _,r in frame.iterrows():
        t=r["time"]

        if pd.notna(r.get("temperature_2m")):
            rows.append({
                "time":t,
                "level_type":"surface",
                "pressure_hPa":np.nan,
                "height_msl_m":surface_elevation_m + 2.0,
                "height_agl_m":2.0,
                "temperature_C":float(r["temperature_2m"]),
                "usable_for_inversion":True,
            })

        for p in levels:
            tk=f"temperature_{p}hPa"
            hk=f"geopotential_height_{p}hPa"
            if tk not in frame.columns or hk not in frame.columns:
                continue
            if pd.isna(r.get(tk)) or pd.isna(r.get(hk)):
                continue
            z_msl=float(r[hk])
            z_agl=z_msl-float(surface_elevation_m)
            rows.append({
                "time":t,
                "level_type":"pressure",
                "pressure_hPa":float(p),
                "height_msl_m":z_msl,
                "height_agl_m":z_agl,
                "temperature_C":float(r[tk]),
                "usable_for_inversion":bool(z_agl > 2.0),
            })

    return pd.DataFrame(rows)


def _metrics_from_raw_profiles(raw):
    rows=[]
    if raw is None or raw.empty:
        return pd.DataFrame()

    for t,g in raw.groupby("time",sort=True):
        prof=g[g["usable_for_inversion"]==True].copy()
        prof=prof.dropna(subset=["height_agl_m","temperature_C"])
        prof=prof.sort_values("height_agl_m")
        prof=prof.drop_duplicates(subset=["height_agl_m"],keep="last")

        if len(prof) < 2:
            rows.append({
                "time":t,
                "icon_d2_index":np.nan,
                "icon_d2_max_positive_gradient_K_per_100m":np.nan,
                "icon_d2_inversion_deltaT_K":np.nan,
                "icon_d2_inversion_depth_m":np.nan,
                "icon_d2_inversion_base_m":np.nan,
                "icon_d2_inversion_top_m":np.nan,
                "icon_d2_level_count":len(prof),
            })
            continue

        z=prof["height_agl_m"].to_numpy(dtype=float)
        temp=prof["temperature_C"].to_numpy(dtype=float)

        segments=[]
        for i in range(len(z)-1):
            dz=z[i+1]-z[i]
            if dz <= 0:
                continue
            dt=temp[i+1]-temp[i]
            grad=dt/dz*100.0
            if dt > 0:
                segments.append((z[i],z[i+1],dt,grad))

        max_grad=max((s[3] for s in segments),default=0.0)

        best=None
        cur=None
        for z1,z2,dt,grad in segments:
            if cur is None:
                cur=[z1,z2,dt]
            elif abs(cur[1]-z1) < 0.01:
                cur[1]=z2
                cur[2]+=dt
            else:
                if best is None or cur[2] > best[2]:
                    best=cur
                cur=[z1,z2,dt]
        if cur is not None and (best is None or cur[2] > best[2]):
            best=cur

        if best:
            base,top,delta=best
            depth=top-base
        else:
            base=top=delta=depth=0.0

        # Keep same displayed 0..5 scale as before for comparability.
        grad_score=np.clip(max_grad/1.5,0,1)
        dt_score=np.clip(delta/4.0,0,1)
        depth_score=np.clip(depth/500.0,0,1)
        index=5.0*(0.55*grad_score + 0.30*dt_score + 0.15*depth_score)

        rows.append({
            "time":t,
            "icon_d2_index":float(index),
            "icon_d2_max_positive_gradient_K_per_100m":float(max_grad),
            "icon_d2_inversion_deltaT_K":float(delta),
            "icon_d2_inversion_depth_m":float(depth),
            "icon_d2_inversion_base_m":float(base),
            "icon_d2_inversion_top_m":float(top),
            "icon_d2_level_count":int(len(prof)),
        })

    return pd.DataFrame(rows)


def _attempt(selected_date,levels,log):
    params=_make_params(selected_date,levels)
    log(
        f"ICON-D2 {selected_date}: Historical Forecast, "
        f"models={OPEN_METEO_ICON_D2_MODEL}, Ebenen={','.join(map(str,levels))} hPa"
    )
    data=_request_json(OPEN_METEO_ICON_D2_HISTORICAL_URL,params)
    frame,hourly=_to_frame(data)

    summary=_summarize_hourly(hourly)
    log("ICON-D2 Antwortfelder: " + ", ".join(
        f"{k}={v if v is not None else '?'}" for k,v in summary.items()
    ))

    usable,missing=_usable_pairs(frame,levels)
    if missing:
        log("ICON-D2 fehlende/unbrauchbare Ebenen: " + ", ".join(
            f"{p}hPa({why})" for p,why in missing
        ))
    if len(usable) < 2:
        raise IconD2RequestError(
            "INCOMPLETE",
            "weniger als zwei nutzbare Temperatur/Geopotential-Paare"
        )

    elevation=data.get("elevation")
    if elevation is None:
        raise IconD2RequestError(
            "INCOMPLETE",
            "Open-Meteo lieferte keine Punkthöhe; sichere AGL-Berechnung nicht möglich"
        )
    elevation=float(elevation)

    raw=_build_raw_profile_table(
        frame,
        [p for p,_ in usable],
        elevation
    )
    metrics=_metrics_from_raw_profiles(raw)

    n_valid=int(metrics["icon_d2_index"].notna().sum()) if not metrics.empty else 0
    if n_valid == 0:
        raise IconD2RequestError(
            "INCOMPLETE",
            "keine berechenbaren ICON-D2-Inversionswerte"
        )

    n_pos=int((metrics["icon_d2_index"]>0).sum())
    log(
        f"ICON-D2 Profilaufbau: 2-m-Wert + Druckflächen über Grund, "
        f"Geländehöhe={elevation:.1f} m MSL, "
        f"{n_valid} Stunden berechnet, {n_pos} Stunde(n) mit Index > 0."
    )

    return data,frame,raw,metrics,usable,missing,summary


def fetch_icon_d2_historical(selected_date,log_cb=None):
    status=SourceStatus(
        name="Open-Meteo ICON-D2 Historical Forecast",
        last_attempt=datetime.now(ZoneInfo(TIMEZONE)),
    )

    def log(msg):
        if log_cb:
            log_cb(msg)

    info={
        "selected_date":selected_date.isoformat(),
        "model_requested":OPEN_METEO_ICON_D2_MODEL,
        "endpoint":OPEN_METEO_ICON_D2_HISTORICAL_URL,
        "pressure_levels_requested_hPa":list(PRESSURE_LEVELS_FULL),
        "used_for_primary_index":False,
        "used_for_kit_index":False,
        "fallback_to_other_model":False,
        "algorithm_version":"ICON_D2_PROFILE_AGL_2M_v1",
    }

    errors=[]
    for attempt_name,levels in (
        ("FULL",PRESSURE_LEVELS_FULL),
        ("CORE_RETRY",PRESSURE_LEVELS_CORE),
    ):
        try:
            data,frame,raw,metrics,usable,missing,summary=_attempt(
                selected_date,levels,log
            )

            n_valid=int(metrics["icon_d2_index"].notna().sum())
            n_pos=int((metrics["icon_d2_index"]>0).sum())
            info.update({
                "attempt_used":attempt_name,
                "pressure_levels_used_hPa":[p for p,_ in usable],
                "missing_pressure_levels":missing,
                "returned_hourly_non_null_counts":summary,
                "latitude_returned":data.get("latitude"),
                "longitude_returned":data.get("longitude"),
                "elevation_returned":data.get("elevation"),
                "timezone_returned":data.get("timezone"),
                "hourly_rows":len(frame),
                "valid_metric_rows":n_valid,
                "positive_index_rows":n_pos,
                "raw_profile_rows":len(raw),
                "attempt_errors":errors,
            })

            status.state="OK" if attempt_name=="FULL" else "OK_CORE_RETRY"
            status.message=(
                f"ICON-D2 {selected_date}: {n_valid} Stunden, "
                f"{n_pos} mit Inversion > 0"
            )
            status.rows=n_valid
            status.last_success=datetime.now(ZoneInfo(TIMEZONE))
            status.detail=(
                f"Modell: {OPEN_METEO_ICON_D2_MODEL}; Abruf: {attempt_name}; "
                f"2-m-Temperatur + Druckflächen, AGL aus Geländehöhe "
                f"{float(data.get('elevation')):.1f} m; verwendete Ebenen: "
                f"{', '.join(str(p) for p,_ in usable)} hPa. "
                "Kein anderes Modell verwendet."
            )
            return metrics,raw,info,status

        except IconD2RequestError as exc:
            errors.append({
                "attempt":attempt_name,
                "levels":list(levels),
                "code":exc.code,
                "message":exc.message,
            })
            log(
                f"ICON-D2 {selected_date}: Versuch {attempt_name} FEHLER "
                f"{exc.code} | {exc.message}"
            )
        except Exception as exc:
            errors.append({
                "attempt":attempt_name,
                "levels":list(levels),
                "code":"ERROR",
                "message":str(exc),
            })
            log(
                f"ICON-D2 {selected_date}: Versuch {attempt_name} "
                f"UNERWARTETER FEHLER | {exc}"
            )

    last=errors[-1] if errors else {"code":"ERROR","message":"unbekannt"}
    info["attempt_errors"]=errors
    status.state=last["code"]
    status.message=f"ICON-D2 {selected_date} nicht auswertbar: {last['message']}"
    status.detail=(
        "FULL und CORE_RETRY ohne verwertbares Ergebnis. "
        "Keine Ersatzdaten und kein anderes Wettermodell eingesetzt."
    )
    return None,None,info,status
