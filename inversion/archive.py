# -*- coding: utf-8 -*-
# =============================================================================
# Modul-History
# 0.15.18 - KIT-Tagesvollständigkeitsprüfung als GitHub-Sicherheitskriterium genutzt
# 0.15.7  - KIT-Coverage: Takt, Sollprofile, Rand-/Maximallücken
# =============================================================================

from __future__ import annotations
import json, hashlib, shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dataclasses import asdict
import numpy as np
import pandas as pd

from .config import (ARCHIVE_DIR, LOCATION_NAME, LOCATION_SLUG, TIMEZONE, VERSION, ARCHIVE_CONFIG, LAT, LON, LOCATION_ELEVATION_M, LOCATION_COMPLETION_SOURCES, LOCATION_OPTIONAL_SOURCES, KIT_REFERENCE_ENABLED)
from .models import DataBundle, SourceStatus
from .quality import determine_quality

SOURCE_KEYS=("dwd","aemet","profile","sonde","kit_mast","icon_d2")

def _json_default(obj):
    if isinstance(obj,(datetime,pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj,(np.integer,)): return int(obj)
    if isinstance(obj,(np.floating,)): return float(obj)
    if isinstance(obj,np.ndarray): return obj.tolist()
    if isinstance(obj,Path): return str(obj)
    if pd.isna(obj): return None
    return str(obj)

def day_dir(selected_date):
    return ARCHIVE_DIR / LOCATION_SLUG / f"{selected_date:%Y}" / f"{selected_date:%m}" / f"{selected_date:%d}"

def manifest_path(selected_date):
    return day_dir(selected_date)/"manifest.json"

def origin_marker_path(selected_date):
    return day_dir(selected_date)/"_origin.json"

def write_origin_marker(selected_date,origin,detail="",source_map=None):
    d=day_dir(selected_date);d.mkdir(parents=True,exist_ok=True)
    payload={
        "origin":str(origin),"detail":str(detail or ""),
        "recorded_at":datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
        "source_map":dict(source_map or {})
    }
    origin_marker_path(selected_date).write_text(
        json.dumps(payload,indent=2,ensure_ascii=False,default=_json_default),
        encoding="utf-8"
    )
    return payload

def read_origin_marker(selected_date):
    p=origin_marker_path(selected_date)
    if not p.exists(): return None
    try:
        x=json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x,dict) else None
    except Exception:
        return None

def archive_exists(selected_date):
    return manifest_path(selected_date).exists()

def _write_df(path, df):
    if df is not None and hasattr(df,"empty") and not df.empty:
        df.to_csv(path,index=False,encoding="utf-8")
        return path.name
    return None

def _read_df(path):
    if not path.exists():
        return None
    try:
        df=pd.read_csv(path)
    except Exception:
        return None

    if "time" in df.columns:
        # Archive CSVs may contain timezone-aware ISO strings or naive values.
        # Parse robustly and normalize all plotting data to Europe/Berlin.
        parsed=pd.to_datetime(df["time"],errors="coerce",utc=True)
        if parsed.notna().any():
            try:
                df["time"]=parsed.dt.tz_convert(TIMEZONE)
            except Exception:
                df["time"]=parsed
        else:
            parsed2=pd.to_datetime(df["time"],errors="coerce")
            try:
                if getattr(parsed2.dt,"tz",None) is None:
                    parsed2=parsed2.dt.tz_localize(TIMEZONE,ambiguous="infer",nonexistent="shift_forward")
                else:
                    parsed2=parsed2.dt.tz_convert(TIMEZONE)
            except Exception:
                pass
            df["time"]=parsed2

        # Invalid time rows cannot be plotted reproducibly.
        df=df[df["time"].notna()].copy()
        if not df.empty:
            df=df.sort_values("time").reset_index(drop=True)

    return df

def _status_dict(s):
    if s is None: return None
    d=asdict(s)
    return d

def _status_from_dict(d):
    if not d: return None
    for k in ("last_attempt","last_success"):
        if d.get(k):
            try: d[k]=datetime.fromisoformat(d[k])
            except Exception: d[k]=None
    allowed=set(SourceStatus.__dataclass_fields__.keys())
    return SourceStatus(**{k:v for k,v in d.items() if k in allowed})

def source_ok(key,status):
    if status is None: return False
    state=status.state
    if key=="kit_mast":
        return state=="KIT_TEMP_OK"
    if key=="icon_d2":
        return state in ("OK","OK_CORE_RETRY")
    return state=="OK"

def completion_sources():
    """Quellen, die den Tagesbestand für GitHub/Retry als vollständig definieren.

    Seit v0.15.8 kann jeder Ort eigene completion_sources definieren.
    Das verhindert z.B., dass Valencia wegen Deutschland-spezifischer
    DWD-/ICON-D2-Quellen dauerhaft als unvollständig gilt.
    """
    if isinstance(LOCATION_COMPLETION_SOURCES,list) and LOCATION_COMPLETION_SOURCES:
        return [x for x in LOCATION_COMPLETION_SOURCES if x in SOURCE_KEYS]

    ga=ARCHIVE_CONFIG.get("github_actions",{})
    configured=ga.get("completion_sources")
    if isinstance(configured,list) and configured:
        return [x for x in configured if x in SOURCE_KEYS]

    legacy=ga.get("required_sources")
    if isinstance(legacy,list) and legacy:
        core=[x for x in legacy if x in SOURCE_KEYS and x not in ("sonde","kit_mast")]
        if core:
            return core
    return ["dwd","profile","icon_d2"]


def optional_sources():
    """Zusatzquellen, die dokumentiert, aber nicht für complete benötigt werden."""
    if isinstance(LOCATION_OPTIONAL_SOURCES,list):
        return [x for x in LOCATION_OPTIONAL_SOURCES if x in SOURCE_KEYS]

    ga=ARCHIVE_CONFIG.get("github_actions",{})
    configured=ga.get("optional_sources")
    if isinstance(configured,list):
        return [x for x in configured if x in SOURCE_KEYS]
    return ["sonde","kit_mast"]


def missing_sources(bundle, required=None):
    """
    Fehlende Kernquellen.

    Seit v0.15.6 bestimmen KIT-Mast und Radiosonde standardmäßig NICHT mehr,
    ob ein Tagesbestand vollständig ist.
    """
    required=completion_sources() if required is None else required
    result=[]
    for k in required:
        if not source_ok(k,bundle.source_status.get(k)):
            result.append(k)
    return result


def missing_optional_sources(bundle):
    result=[]
    for k in optional_sources():
        if not source_ok(k,bundle.source_status.get(k)):
            result.append(k)
    return result

def _df_has_rows(df):
    return df is not None and hasattr(df, "empty") and not df.empty

def _merge_time_df(old_df, new_df, time_col="time"):
    """Kumulative Zeitreihen: vorhandene Daten bleiben erhalten."""
    if not _df_has_rows(old_df):
        return new_df.copy() if _df_has_rows(new_df) else old_df
    if not _df_has_rows(new_df):
        return old_df
    a=old_df.copy()
    b=new_df.copy()
    if time_col in a.columns and time_col in b.columns:
        a[time_col]=pd.to_datetime(a[time_col],errors="coerce")
        b[time_col]=pd.to_datetime(b[time_col],errors="coerce")
        out=pd.concat([a,b],ignore_index=True,sort=False)
        out=out.drop_duplicates(subset=[time_col],keep="last")
        return out.sort_values(time_col).reset_index(drop=True)
    return pd.concat([a,b],ignore_index=True,sort=False).drop_duplicates().reset_index(drop=True)

def _fresh_source_success(key,new):
    return source_ok(key,new.source_status.get(key))


def kit_archive_coverage(bundle,selected_date):
    """Bewertet die zeitliche Vollständigkeit des kumulativen KIT-Tagesarchivs."""
    result={
        "status":"NO_DATA",
        "profile_count":0,
        "expected_profiles":None,
        "coverage_percent":None,
        "cadence_minutes":None,
        "first_timestamp":None,
        "last_timestamp":None,
        "largest_gap_minutes":None,
        "start_gap_minutes":None,
        "end_gap_minutes":None,
        "day_minutes":None,
        "complete":False,
    }
    df=getattr(bundle,"kit_mast_metrics",None)
    if not _df_has_rows(df) or "time" not in df.columns:
        return result

    times=pd.to_datetime(df["time"],errors="coerce",utc=True).dropna()
    if len(times)==0:
        return result
    local=times.dt.tz_convert(TIMEZONE)
    local=local[local.dt.date==selected_date].drop_duplicates().sort_values()
    n=int(len(local))
    result["profile_count"]=n
    if n==0:
        return result

    result["first_timestamp"]=local.iloc[0].isoformat()
    result["last_timestamp"]=local.iloc[-1].isoformat()

    zone=ZoneInfo(TIMEZONE)
    start=datetime(selected_date.year,selected_date.month,selected_date.day,tzinfo=zone)
    nd=selected_date+timedelta(days=1)
    end=datetime(nd.year,nd.month,nd.day,tzinfo=zone)
    su=start.astimezone(timezone.utc); eu=end.astimezone(timezone.utc)
    day_minutes=(eu-su).total_seconds()/60.0
    result["day_minutes"]=round(day_minutes,3)

    min_n=int(ARCHIVE_CONFIG.get("github_actions",{}).get(
        "kit_coverage_min_profiles_for_cadence",3
    ))
    if n<max(2,min_n):
        result["status"]="INSUFFICIENT_FOR_CADENCE"
        return result

    utc=[x.to_pydatetime().astimezone(timezone.utc) for x in local]
    diffs=[(utc[i]-utc[i-1]).total_seconds()/60.0 for i in range(1,len(utc))
           if (utc[i]-utc[i-1]).total_seconds()>0]
    if not diffs:
        result["status"]="INSUFFICIENT_FOR_CADENCE"
        return result

    cadence=float(pd.Series(diffs).median())
    if cadence<=0:
        result["status"]="INSUFFICIENT_FOR_CADENCE"
        return result

    expected=max(1,int(round(day_minutes/cadence)))
    coverage=min(100.0,100.0*n/expected)
    start_gap=(utc[0]-su).total_seconds()/60.0
    end_gap=(eu-utc[-1]).total_seconds()/60.0
    largest=max([max(0.0,start_gap),max(0.0,end_gap)]+diffs)
    gap_factor=float(ARCHIVE_CONFIG.get("github_actions",{}).get(
        "kit_complete_gap_factor",1.5
    ))
    complete=(n>=expected and largest<=cadence*gap_factor)

    result.update({
        "status":"COMPLETE" if complete else "PARTIAL",
        "expected_profiles":expected,
        "coverage_percent":round(coverage,1),
        "cadence_minutes":round(cadence,2),
        "largest_gap_minutes":round(largest,2),
        "start_gap_minutes":round(start_gap,2),
        "end_gap_minutes":round(end_gap,2),
        "complete":bool(complete),
    })
    return result


def apply_kit_archive_coverage(bundle,selected_date):
    cov=kit_archive_coverage(bundle,selected_date)
    if not isinstance(getattr(bundle,"kit_mast_info",None),dict):
        bundle.kit_mast_info={}
    bundle.kit_mast_info["archive_coverage"]=cov

    status=(getattr(bundle,"source_status",{}) or {}).get("kit_mast")
    if status is not None:
        status.rows=cov.get("profile_count")
        status.expected_rows=cov.get("expected_profiles")
        status.coverage_percent=cov.get("coverage_percent")
        status.first_timestamp=cov.get("first_timestamp")
        status.last_timestamp=cov.get("last_timestamp")
        status.largest_gap_minutes=cov.get("largest_gap_minutes")
        base=(status.detail or "").split(" | KIT-Archiv:")[0]
        cs=cov.get("status")
        if cs=="COMPLETE":
            extra=(f"KIT-Archiv: VOLLSTÄNDIG; {cov['profile_count']}/{cov['expected_profiles']} "
                   f"Profile, {cov['coverage_percent']:.1f} %, Takt≈{cov['cadence_minutes']:.1f} min, "
                   f"größte Lücke {cov['largest_gap_minutes']:.1f} min")
        elif cs=="PARTIAL":
            extra=(f"KIT-Archiv: UNVOLLSTÄNDIG; {cov['profile_count']}/{cov['expected_profiles']} "
                   f"Profile, {cov['coverage_percent']:.1f} %, Takt≈{cov['cadence_minutes']:.1f} min, "
                   f"größte Lücke {cov['largest_gap_minutes']:.1f} min")
        elif cs=="INSUFFICIENT_FOR_CADENCE":
            extra=(f"KIT-Archiv: {cov['profile_count']} Profil(e); "
                   "noch zu wenig Daten zur sicheren Takt-/24h-Bewertung")
        else:
            extra="KIT-Archiv: keine Profile für diesen Tag"
        status.detail=(base+" | "+extra).strip(" |")
    return cov

def merge_bundles(old,new, replace_sources):
    """
    Sicheres Zusammenführen.
    - Fehlschlag/leerer Neuabruf löscht keine guten Archivdaten.
    - KIT-Mastwerte werden immer kumulativ nach Zeitstempel vereinigt.
    """
    if old is None:
        return new
    replace=set(replace_sources or SOURCE_KEYS)

    if "dwd" in replace:
        if _fresh_source_success("dwd",new) and _df_has_rows(new.dwd_data):
            old.station_info=new.station_info
            old.dwd_data=new.dwd_data
            old.source_status["dwd"]=new.source_status["dwd"]

    if "aemet" in replace:
        fresh_ok=_fresh_source_success("aemet",new) and _df_has_rows(new.aemet_data)
        if fresh_ok:
            old.aemet_data=_merge_time_df(old.aemet_data,new.aemet_data,"time")
            old.aemet_station_info=new.aemet_station_info or old.aemet_station_info
            old.source_status["aemet"]=new.source_status["aemet"]
            old.source_status["aemet"].rows=len(old.aemet_data)
            old.source_status["aemet"].message=f"{len(old.aemet_data)} archivierte AEMET-Stundenwert(e) für den Tag (kumulativ)"
        elif not _df_has_rows(old.aemet_data) and "aemet" in new.source_status:
            old.source_status["aemet"]=new.source_status["aemet"]

    if "profile" in replace:
        if _fresh_source_success("profile",new) and _df_has_rows(new.profile_data):
            old.profile_data=new.profile_data
            if _df_has_rows(new.result_data):
                old.result_data=new.result_data
            old.source_status["profile"]=new.source_status["profile"]

    if "sonde" in replace:
        fresh_sonde=(
            _fresh_source_success("sonde",new)
            and _df_has_rows(new.sonde_metrics)
            and _df_has_rows(new.sonde_profile_data)
        )
        if fresh_sonde:
            old.sonde_metrics=new.sonde_metrics
            old.sonde_profile_data=new.sonde_profile_data
            old.sonde_profiles=new.sonde_profiles
            old.sonde_flights=new.sonde_flights
            old.source_status["sonde"]=new.source_status["sonde"]
        elif not _df_has_rows(old.sonde_metrics):
            if "sonde" in new.source_status:
                old.source_status["sonde"]=new.source_status["sonde"]
        # Existing measured radiosonde data are protected from failed/empty refreshes.

    if "kit_mast" in replace:
        fresh_ok=_fresh_source_success("kit_mast",new) and _df_has_rows(new.kit_mast_metrics)
        if fresh_ok:
            old.kit_mast_metrics=_merge_time_df(old.kit_mast_metrics,new.kit_mast_metrics,"time")
            if new.kit_mast_info:
                old.kit_mast_info=new.kit_mast_info
            if new.kit_mast_data:
                old.kit_mast_data=new.kit_mast_data
            old.source_status["kit_mast"]=new.source_status["kit_mast"]
            old.source_status["kit_mast"].rows=len(old.kit_mast_metrics)
            old.source_status["kit_mast"].message=(
                f"{len(old.kit_mast_metrics)} archivierte KIT-Temperaturprofil(e) "
                "für den Tag (kumulativ)"
            )
            old.source_status["kit_mast"].detail=(
                (old.source_status["kit_mast"].detail or "")+
                " | ARCHIVSCHUTZ: vorhandene KIT-Profile werden nicht durch "
                "einen kleineren oder leeren Abruf gelöscht."
            )
        elif not _df_has_rows(old.kit_mast_metrics):
            if "kit_mast" in new.source_status:
                old.source_status["kit_mast"]=new.source_status["kit_mast"]
        # Wenn alte KIT-Daten vorhanden sind und neu nichts kommt: nichts ändern.

    if "icon_d2" in replace:
        if _fresh_source_success("icon_d2",new) and _df_has_rows(new.icon_d2_data):
            old.icon_d2_data=new.icon_d2_data
            if _df_has_rows(new.icon_d2_profile_data):
                old.icon_d2_profile_data=new.icon_d2_profile_data
            old.icon_d2_info=new.icon_d2_info
            old.source_status["icon_d2"]=new.source_status["icon_d2"]

    old.run_id=new.run_id or old.run_id
    determine_quality(old)
    if old.source_status.get("sonde") and old.source_status["sonde"].is_ok():
        old.quality_text += " | DWD-Radiosonde Idar-Oberstein gemessen separat"
    if source_ok("kit_mast",old.source_status.get("kit_mast")):
        old.quality_text += " | KIT-Mast gemessen separat"
    if source_ok("icon_d2",old.source_status.get("icon_d2")):
        old.quality_text += " | ICON-D2 Historical Forecast separat"
    return old

def _fmt_log_dt(value):
    if value is None:
        return "–"
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def append_source_log(selected_date,bundle,reason="SAVE"):
    """Append all source information to the corresponding day's sources.log."""
    d=day_dir(selected_date)
    d.mkdir(parents=True,exist_ok=True)
    p=d/"sources.log"
    sep="="*78
    now=datetime.now(ZoneInfo(TIMEZONE)).isoformat()

    lines=[
        sep,
        f"DATENQUELLEN-STATUS | Datum: {selected_date} | Eintrag: {now} | Anlass: {reason}",
        sep,
    ]

    labels=[
        ("dwd","DWD Boden"),
        ("aemet","AEMET Boden"),
        ("profile","Vertikalprofil"),
        ("sonde","Idar-Oberstein"),
        ("kit_mast","KIT 200-m-Mast"),
        ("icon_d2","ICON-D2 Historical"),
    ]

    status_map=getattr(bundle,"source_status",{}) or {}
    for key,label in labels:
        s=status_map.get(key)
        lines.append(f"[{label}]")
        if s is None:
            lines.append("Status: KEIN STATUSOBJEKT")
        else:
            lines.append(f"Status: {getattr(s,'state','–')}")
            message=getattr(s,'message','') or ''
            detail=getattr(s,'detail','') or ''
            rows=getattr(s,'rows',None)
            if message:
                lines.append(f"Meldung: {message}")
            if detail:
                lines.append(f"Details: {detail}")
            if rows is not None:
                lines.append(f"Zeilen: {rows}")
            lines.append(f"Letzter Versuch: {_fmt_log_dt(getattr(s,'last_attempt',None))}")
            lines.append(f"Letzter Erfolg: {_fmt_log_dt(getattr(s,'last_success',None))}")
        lines.append("-"*78)

    kit_cov=kit_archive_coverage(bundle,selected_date)
    lines.append("[KIT-Archiv-Abdeckung]")
    lines.append(
        f"Status: {kit_cov.get('status')} | "
        f"Profile: {kit_cov.get('profile_count')}/"
        f"{kit_cov.get('expected_profiles') if kit_cov.get('expected_profiles') is not None else '–'} | "
        f"Abdeckung: {kit_cov.get('coverage_percent') if kit_cov.get('coverage_percent') is not None else '–'}% | "
        f"Takt: {kit_cov.get('cadence_minutes') if kit_cov.get('cadence_minutes') is not None else '–'} min | "
        f"größte Lücke: {kit_cov.get('largest_gap_minutes') if kit_cov.get('largest_gap_minutes') is not None else '–'} min"
    )
    lines.append("-"*78)
    lines.append(f"Datenqualität: {getattr(bundle,'quality_class','–')}")
    lines.append(f"Qualitätstext: {getattr(bundle,'quality_text','') or ''}")
    lines.append(sep)
    lines.append("")

    with p.open("a",encoding="utf-8",newline="\n") as f:
        f.write("\n".join(lines))
    return p


def save_bundle(selected_date,bundle,attempt_meta=None,touched_sources=None):
    d=day_dir(selected_date)
    d.mkdir(parents=True,exist_ok=True)

    mp=d/"manifest.json"
    previous={}

    # v0.15.22: configured locations consume the global KITMast reference archive.
    if KIT_REFERENCE_ENABLED:
        from .kit_reference_archive import attach_kit_reference
        attach_kit_reference(bundle,selected_date)
    # v0.15.7: Coverage auf dem finalen kumulativen KIT-Bestand bestimmen.
    kit_coverage=apply_kit_archive_coverage(bundle,selected_date)
    if mp.exists():
        try:
            previous=json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            previous={}

    # v0.15.3 NO-TOUCH:
    # Bei einem Teil-/Retry-Lauf bleiben Dateien nicht angeforderter Quellen
    # bytegenau unangetastet. Das Manifest übernimmt deren bisherige Dateinamen.
    touched=set(touched_sources) if touched_sources is not None else set(SOURCE_KEYS)
    files=dict(previous.get("files",{}) or {})

    def write_source_df(source_key,file_key,filename,df):
        if source_key not in touched:
            return
        written=_write_df(d/filename,df)
        if written:
            files[file_key]=written
        elif file_key not in files:
            files[file_key]=None

    write_source_df("dwd","dwd_data","dwd_ground.csv",bundle.dwd_data)
    write_source_df("aemet","aemet_data","aemet_ground.csv",bundle.aemet_data)
    write_source_df("profile","profile_data","openmeteo_profile.csv",bundle.profile_data)
    write_source_df("profile","result_data","inversion_model.csv",bundle.result_data)
    write_source_df("sonde","sonde_profile_data","radiosonde_profile.csv",bundle.sonde_profile_data)
    write_source_df("sonde","sonde_metrics","radiosonde_metrics.csv",bundle.sonde_metrics)
    if KIT_REFERENCE_ENABLED:
        # v0.15.22: KIT is read from archive/KITMast, never duplicated per location.
        files.pop("kit_mast_metrics",None)
        files.pop("kit_mast_info",None)
        files.pop("kit_mast_data",None)
    else:
        write_source_df("kit_mast","kit_mast_metrics","kit_mast.csv",bundle.kit_mast_metrics)
    write_source_df("icon_d2","icon_d2_data","icon_d2.csv",bundle.icon_d2_data)
    write_source_df("icon_d2","icon_d2_profile_data","icon_d2_profile.csv",bundle.icon_d2_profile_data)

    # Source-specific JSON is only rewritten when its source was touched.
    source_json_items={
        "dwd":{
            "station_info":bundle.station_info,
        },
        "sonde":{
            "sonde_profiles":bundle.sonde_profiles,
            "sonde_flights":bundle.sonde_flights,
        },
        "kit_mast":({} if KIT_REFERENCE_ENABLED else {
            "kit_mast_info":bundle.kit_mast_info,
            "kit_mast_data":bundle.kit_mast_data,
        }),
        "icon_d2":{
            "icon_d2_info":bundle.icon_d2_info,
        },
    }
    for source_key,items in source_json_items.items():
        if source_key not in touched:
            continue
        for key,val in items.items():
            fn=f"{key}.json"
            (d/fn).write_text(
                json.dumps(val,indent=2,ensure_ascii=False,default=_json_default),
                encoding="utf-8"
            )
            files[key]=fn

    # source_status and manifest are intentionally global daily metadata and
    # therefore may change after every retry.
    status_fn="source_status.json"
    (d/status_fn).write_text(
        json.dumps(
            {k:_status_dict(v) for k,v in bundle.source_status.items()},
            indent=2,ensure_ascii=False,default=_json_default
        ),
        encoding="utf-8"
    )
    files["source_status"]=status_fn

    miss=missing_sources(bundle)
    optional_miss=missing_optional_sources(bundle)
    now=datetime.now(ZoneInfo(TIMEZONE))
    attempts=int(previous.get("attempts",0))
    if attempt_meta and attempt_meta.get("increment_attempt",True):
        attempts += 1

    affects_retry_clock=bool((attempt_meta or {}).get("affects_retry_clock",True))
    retry_last_attempt=(
        now.isoformat()
        if attempt_meta and affects_retry_clock
        else previous.get("last_attempt")
    )
    aux_last_attempt=previous.get("last_auxiliary_attempt")
    if attempt_meta and not affects_retry_clock:
        aux_last_attempt=now.isoformat()

    manifest={
        "schema_version":1,
        "app_version":VERSION,
        "location":{
            "name":LOCATION_NAME,
            "slug":LOCATION_SLUG,
            "latitude":LAT,
            "longitude":LON,
            "elevation_m":LOCATION_ELEVATION_M,
            "timezone":TIMEZONE
        },
        "date":selected_date.isoformat(),
        "saved_at":now.isoformat(),
        "run_id":bundle.run_id,
        "quality_class":bundle.quality_class,
        "quality_text":bundle.quality_text,
        "complete":len(miss)==0,
        "completion_sources":completion_sources(),
        "missing_sources":miss,
        "optional_sources":optional_sources(),
        "optional_missing_sources":optional_miss,
        "kit_archive":kit_coverage,
        "kit_reference":({
            "enabled":True,
            "archive":"archive/KITMast",
            "station":"KIT 200-m-Mast Karlsruhe"
        } if KIT_REFERENCE_ENABLED else {"enabled":False}),
        "attempts":attempts,
        "last_attempt":retry_last_attempt,
        "last_auxiliary_attempt":aux_last_attempt,
        "attempt_reason": (attempt_meta or {}).get("reason"),
        "files":files,
    }
    mp.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=_json_default),encoding="utf-8")
    append_source_log(
        selected_date,
        bundle,
        reason=(attempt_meta or {}).get("reason") or "SAVE"
    )
    return manifest

def bundle_diagnostics(bundle):
    def nrows(x):
        return int(len(x)) if x is not None and hasattr(x,"__len__") else 0
    return {
        "dwd_rows":nrows(bundle.dwd_data),
        "aemet_rows":nrows(bundle.aemet_data),
        "profile_rows":nrows(bundle.profile_data),
        "result_rows":nrows(bundle.result_data),
        "sonde_rows":nrows(bundle.sonde_metrics),
        "sonde_profile_rows":nrows(bundle.sonde_profile_data),
        "kit_rows":nrows(bundle.kit_mast_metrics),
        "icon_rows":nrows(bundle.icon_d2_data),
        "icon_profile_rows":nrows(bundle.icon_d2_profile_data),
    }

def load_bundle(selected_date):
    d=day_dir(selected_date)
    mp=d/"manifest.json"
    if not mp.exists(): return None,None
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    b=DataBundle()
    b.run_id=manifest.get("run_id","")
    b.quality_class=manifest.get("quality_class","X")
    b.quality_text=manifest.get("quality_text","")
    files=manifest.get("files",{})
    b.dwd_data=_read_df(d/files["dwd_data"]) if files.get("dwd_data") else None
    b.aemet_data=_read_df(d/files["aemet_data"]) if files.get("aemet_data") else None
    b.profile_data=_read_df(d/files["profile_data"]) if files.get("profile_data") else None
    b.result_data=_read_df(d/files["result_data"]) if files.get("result_data") else None
    b.sonde_profile_data=_read_df(d/files["sonde_profile_data"]) if files.get("sonde_profile_data") else None
    b.sonde_metrics=_read_df(d/files["sonde_metrics"]) if files.get("sonde_metrics") else None
    b.kit_mast_metrics=_read_df(d/files["kit_mast_metrics"]) if files.get("kit_mast_metrics") else None
    b.icon_d2_data=_read_df(d/files["icon_d2_data"]) if files.get("icon_d2_data") else None
    b.icon_d2_profile_data=_read_df(d/files["icon_d2_profile_data"]) if files.get("icon_d2_profile_data") else None
    def j(key,default):
        fn=files.get(key)
        if not fn or not (d/fn).exists(): return default
        try: return json.loads((d/fn).read_text(encoding="utf-8"))
        except Exception: return default
    b.station_info=j("station_info",None)
    b.aemet_station_info=j("aemet_station_info",None)
    b.sonde_profiles=j("sonde_profiles",[])
    b.sonde_flights=j("sonde_flights",[])
    b.kit_mast_info=j("kit_mast_info",{})
    b.kit_mast_data=j("kit_mast_data",None)
    b.icon_d2_info=j("icon_d2_info",{})
    raw_status=j("source_status",{})
    b.source_status={k:_status_from_dict(v) for k,v in raw_status.items() if v}
    if KIT_REFERENCE_ENABLED:
        from .kit_reference_archive import attach_kit_reference
        attach_kit_reference(b,selected_date)
    return b,manifest
