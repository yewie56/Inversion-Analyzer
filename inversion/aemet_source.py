# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests

from .config import TIMEZONE, AEMET_STATION_ID, REQUEST_TIMEOUT
from .models import SourceStatus

AEMET_ENDPOINT = (
    "https://opendata.aemet.es/opendata/api/observacion/"
    "convencional/datos/estacion/{station}"
)

def parse_aemet_observations(payload, selected_date, timezone_name, station_id):
    if not isinstance(payload, list):
        raise ValueError("AEMET-Datensatz ist keine JSON-Liste.")
    tz=ZoneInfo(timezone_name)
    rows=[]
    for item in payload:
        if not isinstance(item,dict): continue
        if str(item.get("idema","")).strip()!=str(station_id).strip(): continue
        if item.get("fint") is None or item.get("ta") is None: continue
        try:
            ts=pd.to_datetime(item["fint"],utc=True)
            if pd.isna(ts): continue
            ts=ts.tz_convert(tz)
            temp=float(item["ta"])
        except Exception:
            continue
        if ts.date()!=selected_date: continue
        rows.append({
            "time":ts,
            "temperature_obs":temp,
            "temperature_source":"AEMET",
            "station_id":str(item.get("idema",station_id)),
            "station_name":str(item.get("ubi","")),
            "station_altitude_m":item.get("alt"),
            "latitude":item.get("lat"),
            "longitude":item.get("lon"),
            "humidity_percent":item.get("hr"),
            "pressure_hpa":item.get("pres"),
            "pressure_sea_level_hpa":item.get("pres_nmar"),
            "wind_speed_ms":item.get("vv"),
            "wind_direction_deg":item.get("dv"),
            "precip_mm":item.get("prec"),
        })
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
            .drop_duplicates(subset=["time"],keep="last")
            .sort_values("time").reset_index(drop=True))

def fetch_aemet_temperature(selected_date, log_cb=None):
    station=str(AEMET_STATION_ID or "").strip()
    now=datetime.now(ZoneInfo(TIMEZONE))
    s=SourceStatus(name="AEMET-Bodenmessung",last_attempt=now)
    if not station:
        s.state="CONFIG_ERROR";s.message="Keine AEMET-Stationskennung konfiguriert."
        return None,pd.DataFrame(),s

    key=os.environ.get("AEMET_API_KEY","").strip()
    if not key:
        s.state="NO_API_KEY";s.message="AEMET_API_KEY ist nicht gesetzt."
        s.detail="AEMET wird übersprungen; Open-Meteo bleibt nutzbar."
        if log_cb: log_cb("AEMET: kein API-Key gesetzt; Abruf übersprungen.")
        return {"station_id":station},pd.DataFrame(),s

    if log_cb: log_cb(f"AEMET: Station {station} abrufen ...")
    try:
        r=requests.get(AEMET_ENDPOINT.format(station=station),
                       headers={"accept":"application/json","api_key":key},
                       timeout=REQUEST_TIMEOUT)
        s.http_status=r.status_code
        r.raise_for_status()
        env=r.json()
    except requests.Timeout as exc:
        s.state="TIMEOUT";s.message="AEMET-Anfrage Timeout";s.detail=str(exc)
        return {"station_id":station},pd.DataFrame(),s
    except requests.RequestException as exc:
        s.state="HTTP_ERROR";s.message="AEMET-Anfrage fehlgeschlagen";s.detail=str(exc)
        return {"station_id":station},pd.DataFrame(),s
    except ValueError as exc:
        s.state="PARSE_ERROR";s.message="AEMET-Antwort kein gültiges JSON";s.detail=str(exc)
        return {"station_id":station},pd.DataFrame(),s

    if not isinstance(env,dict) or not env.get("datos"):
        s.state="API_ERROR";s.message="AEMET liefert keine Daten-URL"
        s.detail=str(env.get("descripcion","")) if isinstance(env,dict) else repr(env)
        return {"station_id":station},pd.DataFrame(),s

    try:
        r2=requests.get(env["datos"],timeout=REQUEST_TIMEOUT)
        r2.raise_for_status()
        payload=r2.json()
    except requests.Timeout as exc:
        s.state="TIMEOUT_DATA";s.message="AEMET-Datendownload Timeout";s.detail=str(exc)
        return {"station_id":station},pd.DataFrame(),s
    except requests.RequestException as exc:
        s.state="HTTP_ERROR_DATA";s.message="AEMET-Datendownload fehlgeschlagen";s.detail=str(exc)
        return {"station_id":station},pd.DataFrame(),s
    except ValueError as exc:
        s.state="PARSE_ERROR_DATA";s.message="AEMET-Daten kein gültiges JSON";s.detail=str(exc)
        return {"station_id":station},pd.DataFrame(),s

    info={"station_id":station,"provider":"AEMET"}
    if isinstance(payload,list):
        for item in payload:
            if isinstance(item,dict) and str(item.get("idema",""))==station:
                info.update({"name":item.get("ubi"),"latitude":item.get("lat"),
                             "longitude":item.get("lon"),"elevation_m":item.get("alt")})
                break

    try:
        df=parse_aemet_observations(payload,selected_date,TIMEZONE,station)
    except Exception as exc:
        s.state="FORMAT_ERROR_DATA";s.message="AEMET-Datenformat unerwartet";s.detail=repr(exc)
        return info,pd.DataFrame(),s

    if df.empty:
        s.state="NO_DATE_DATA";s.message=f"Keine AEMET-Stundenwerte für {selected_date}"
        s.detail="Die Beobachtungs-API liefert nur aktuelle/recent Daten; Archivierung erfolgt kumulativ."
        if log_cb: log_cb(f"AEMET: keine Werte für {selected_date} im aktuellen API-Fenster.")
        return info,df,s

    s.state="OK";s.message=f"{len(df)} AEMET-Stundenwert(e) für {selected_date}"
    s.rows=len(df);s.last_success=now
    s.first_timestamp=df["time"].iloc[0].isoformat()
    s.last_timestamp=df["time"].iloc[-1].isoformat()
    s.detail=f"Station {info.get('name') or station}; reale AEMET-Bodenmessung."
    if log_cb: log_cb(f"AEMET: {len(df)} Stundenwert(e) für {selected_date}")
    return info,df,s

def selftest_aemet_parser():
    sample=[{"idema":"8416","fint":"2026-08-25T20:00:00+0000","ta":27.6,
             "ubi":"VALENCIA","alt":13.0,"lat":39.480556,"lon":-0.366389}]
    day=pd.Timestamp("2026-08-25").date()
    df=parse_aemet_observations(sample,day,"Europe/Madrid","8416")
    ok=(len(df)==1 and abs(float(df.iloc[0]["temperature_obs"])-27.6)<1e-9
        and df.iloc[0]["time"].hour==22)
    return {"pass":bool(ok),"rows":len(df),
            "time":df.iloc[0]["time"].isoformat() if len(df) else None}
