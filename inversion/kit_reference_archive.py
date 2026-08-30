# -*- coding: utf-8 -*-
"""Central, location-independent KIT 200-m mast reference archive.

v0.15.22
- one global archive: archive/KITMast/YYYY/MM/DD
- safe cumulative merge by timestamp
- idempotent migration from legacy per-location kit_mast.csv files
- network refresh reuses the existing KIT/Bokeh timeout+retry implementation
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import numpy as np
import pandas as pd

from .config import ARCHIVE_DIR, VERSION
from .models import SourceStatus
from .kit_mast import fetch_kit_mast_diagnostics
from .kit_inversion import extract_kit_temperature_profiles

KIT_TIMEZONE="Europe/Berlin"
KIT_ARCHIVE_SLUG="KITMast"


def _json_default(obj):
    if isinstance(obj,(datetime,pd.Timestamp)): return obj.isoformat()
    if isinstance(obj,(np.integer,)): return int(obj)
    if isinstance(obj,(np.floating,)): return float(obj)
    if isinstance(obj,np.ndarray): return obj.tolist()
    if isinstance(obj,Path): return str(obj)
    try:
        if pd.isna(obj): return None
    except Exception:
        pass
    return str(obj)


def kit_reference_day_dir(selected_date):
    return ARCHIVE_DIR / KIT_ARCHIVE_SLUG / f"{selected_date:%Y}" / f"{selected_date:%m}" / f"{selected_date:%d}"


def _read_df(path):
    if not path.exists(): return None
    try:
        df=pd.read_csv(path)
    except Exception:
        return None
    if "time" in df.columns:
        parsed=pd.to_datetime(df["time"],errors="coerce",utc=True)
        df=df[parsed.notna()].copy()
        if not df.empty:
            df["time"]=parsed[parsed.notna()].dt.tz_convert(KIT_TIMEZONE)
            df=df.sort_values("time").reset_index(drop=True)
    return df


def _merge_time_df(old_df,new_df):
    if old_df is None or getattr(old_df,"empty",True):
        return new_df.copy() if new_df is not None and not new_df.empty else old_df
    if new_df is None or getattr(new_df,"empty",True):
        return old_df.copy()
    a=old_df.copy(); b=new_df.copy()
    a["time"]=pd.to_datetime(a["time"],errors="coerce",utc=True)
    b["time"]=pd.to_datetime(b["time"],errors="coerce",utc=True)
    out=pd.concat([a,b],ignore_index=True,sort=False)
    out=out[out["time"].notna()].drop_duplicates(subset=["time"],keep="last")
    out["time"]=out["time"].dt.tz_convert(KIT_TIMEZONE)
    return out.sort_values("time").reset_index(drop=True)


def _status_dict(status):
    if status is None: return {}
    if isinstance(status,dict): return dict(status)
    d=asdict(status)
    return {k:_json_default(v) if isinstance(v,datetime) else v for k,v in d.items()}


def load_kit_reference(selected_date):
    d=kit_reference_day_dir(selected_date)
    mp=d/"manifest.json"
    manifest={}
    if mp.exists():
        try: manifest=json.loads(mp.read_text(encoding="utf-8"))
        except Exception: manifest={}
    metrics=_read_df(d/"kit_mast.csv")
    def load_json(name,default):
        p=d/name
        if not p.exists(): return default
        try: return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return default
    info=load_json("kit_mast_info.json",{})
    status=load_json("source_status.json",{})
    data=load_json("kit_mast_data.json",None)
    if isinstance(info,dict):
        info.setdefault("reference_archive",str(d))
        info.setdefault("archive_kind",KIT_ARCHIVE_SLUG)
        info["_kit_mast_data"]=data
    return metrics,info,status,manifest


def save_kit_reference(selected_date,metrics,info=None,data=None,status=None,status_state=None,source="NETWORK",migration_sources=None):
    """Safe merge. Empty/failed refresh never deletes existing good metrics."""
    d=kit_reference_day_dir(selected_date); d.mkdir(parents=True,exist_ok=True)
    old_metrics,old_info,old_status,old_manifest=load_kit_reference(selected_date)
    merged=_merge_time_df(old_metrics,metrics)
    fresh_ok=metrics is not None and hasattr(metrics,"empty") and not metrics.empty

    if merged is not None and not merged.empty:
        merged.to_csv(d/"kit_mast.csv",index=False,encoding="utf-8")

    final_info=dict(old_info or {})
    final_info.pop("_kit_mast_data",None)
    if fresh_ok and isinstance(info,dict): final_info.update(info)
    final_info["reference_archive"]=str(d)
    final_info["archive_kind"]=KIT_ARCHIVE_SLUG
    (d/"kit_mast_info.json").write_text(json.dumps(final_info,indent=2,ensure_ascii=False,default=_json_default),encoding="utf-8")

    old_data=(old_info or {}).get("_kit_mast_data")
    final_data=data if fresh_ok and data is not None else old_data
    if final_data is not None:
        (d/"kit_mast_data.json").write_text(json.dumps(final_data,indent=2,ensure_ascii=False,default=_json_default),encoding="utf-8")

    incoming=_status_dict(status)
    if status_state: incoming["state"]=status_state
    final_status=dict(old_status or {})
    if fresh_ok:
        final_status.update(incoming)
        final_status["state"]="KIT_TEMP_OK"
        final_status["rows"]=int(len(merged)) if merged is not None else 0
        final_status["message"]=f"{final_status['rows']} archivierte KIT-Temperaturprofile im globalen Referenzarchiv"
    elif not final_status:
        final_status.update(incoming)
        final_status.setdefault("state",status_state or "NO_DATA")
    final_status["last_archive_attempt"]=datetime.now(ZoneInfo(KIT_TIMEZONE)).isoformat()
    final_status["last_archive_attempt_source"]=source
    (d/"source_status.json").write_text(json.dumps(final_status,indent=2,ensure_ascii=False,default=_json_default),encoding="utf-8")

    migrated=list(old_manifest.get("migrated_from",[]) or [])
    for item in migration_sources or []:
        s=str(item)
        if s not in migrated: migrated.append(s)
    now=datetime.now(ZoneInfo(KIT_TIMEZONE)).isoformat()
    manifest={
        "schema_version":1,
        "app_version":VERSION,
        "archive_kind":KIT_ARCHIVE_SLUG,
        "reference_station":"KIT 200-m-Mast Karlsruhe",
        "timezone":KIT_TIMEZONE,
        "date":selected_date.isoformat(),
        "saved_at":now,
        "profile_count":0 if merged is None else int(len(merged)),
        "last_update_source":source,
        "migrated_from":migrated,
        "files":{
            "kit_mast_metrics":"kit_mast.csv" if merged is not None and not merged.empty else None,
            "kit_mast_info":"kit_mast_info.json",
            "kit_mast_data":"kit_mast_data.json" if final_data is not None else None,
            "source_status":"source_status.json",
        }
    }
    (d/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=_json_default),encoding="utf-8")
    return merged,manifest


def migrate_legacy_kit_archives(log_cb=None):
    """Merge all legacy archive/<location>/YYYY/MM/DD/kit_mast.csv into KITMast."""
    count=0
    if not ARCHIVE_DIR.exists(): return 0
    for p in sorted(ARCHIVE_DIR.glob("*/????/??/??/kit_mast.csv")):
        try:
            rel=p.relative_to(ARCHIVE_DIR)
            if rel.parts[0]==KIT_ARCHIVE_SLUG: continue
            y,m,d=map(int,rel.parts[1:4])
            from datetime import date
            selected_date=date(y,m,d)
        except Exception:
            continue
        _,_,_,existing_manifest=load_kit_reference(selected_date)
        if str(rel) in list(existing_manifest.get("migrated_from",[]) or []):
            continue
        df=_read_df(p)
        if df is None or df.empty: continue
        save_kit_reference(selected_date,df,source="LEGACY_MIGRATION",migration_sources=[str(rel)])
        count+=1
        if log_cb: log_cb(f"KIT-REFERENZ MIGRATION: {rel} -> {kit_reference_day_dir(selected_date)}")
    return count


def update_kit_reference_day(selected_date,log_cb=None):
    """Fetch KIT using existing Bokeh retry logic and safe-merge globally."""
    run_id=datetime.now(ZoneInfo(KIT_TIMEZONE)).strftime("%Y%m%d_%H%M%S")
    info,data,status=fetch_kit_mast_diagnostics(selected_date,log_cb,run_id=run_id)
    client_sources=(data or {}).get("client_sources",[]) if isinstance(data,dict) else []
    metrics,analysis=extract_kit_temperature_profiles(client_sources,selected_date,log_cb=log_cb)
    if not isinstance(info,dict): info={}
    info["temperature_profile_analysis"]=analysis
    if metrics is not None and not metrics.empty:
        status.state="KIT_TEMP_OK"
        status.message=f"{len(metrics)} gemessene Temperaturprofile für {selected_date} ausgewertet"
        status.rows=len(metrics)
    elif getattr(status,"state","")=="BOKEH_CLIENT_DATA":
        status.state="KIT_TEMP_NO_DATE"
        status.message=f"Temperaturdaten erkannt, aber kein KIT-Profil für {selected_date}"
    merged,manifest=save_kit_reference(selected_date,metrics,info=info,data=data,status=status,source="NETWORK")
    return merged,info,status,manifest


def attach_kit_reference(bundle,selected_date):
    metrics,info,status,manifest=load_kit_reference(selected_date)
    if metrics is None or metrics.empty:
        bundle.kit_mast_metrics=None
        bundle.kit_mast_info={"reference_archive":str(kit_reference_day_dir(selected_date)),"archive_kind":KIT_ARCHIVE_SLUG}
        bundle.kit_mast_data=None
        bundle.source_status["kit_mast"]=SourceStatus(
            name="KIT-Mast Referenz Karlsruhe",state="KIT_REFERENCE_NO_DATA",
            message=f"Kein globales KIT-Referenzprofil für {selected_date}",
            detail=f"Globales Archiv: {kit_reference_day_dir(selected_date)}"
        )
        return bundle
    bundle.kit_mast_metrics=metrics
    bundle.kit_mast_info=info or {}
    bundle.kit_mast_data=(info or {}).pop("_kit_mast_data",None)
    st=SourceStatus(
        name="KIT-Mast Referenz Karlsruhe",state="KIT_TEMP_OK",
        message=f"{len(metrics)} KIT-Referenzprofil(e) aus globalem Tagesarchiv",
        rows=len(metrics),detail=f"Globales Referenzarchiv: {kit_reference_day_dir(selected_date)}"
    )
    for key in ("last_attempt","last_success"):
        val=(status or {}).get(key)
        if val:
            try: setattr(st,key,datetime.fromisoformat(val))
            except Exception: pass
    bundle.source_status["kit_mast"]=st
    if "KIT-Mast" not in (bundle.quality_text or ""):
        bundle.quality_text=(bundle.quality_text or "")+" | KIT-Mast Karlsruhe Referenz separat"
    return bundle
