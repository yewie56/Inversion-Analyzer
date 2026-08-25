# -*- coding: utf-8 -*-
"""
DWD Radiosonde Idar-Oberstein – measured temperature-height profiles.

v0.13.0
- Uses official DWD CDC high-resolution radiosonde archives.
- Idar-Oberstein: DWD station 02385, WMO 10618.
- Current/recent dates: recent/sekundenwerte_aero_02385_akt.zip
- Older years: historical/<year>/ station-specific annual ZIP found by listing.
- Streams large ZIP files to disk cache instead of holding them wholly in RAM.
- Parses the selected local day only.
- Splits rows into individual soundings by time gaps.
- Converts height to AGL from each sounding's lowest valid altitude.
- Bins temperature in 25 m altitude bins and applies a 3-bin centered median.
- Calculates a separate radiosonde inversion index 0..5.
- Raw measured profile and derived metrics are returned for daily archiving.

Important:
The radiosonde is measured at Idar-Oberstein, not Viernheim. Its index therefore
remains a separate measured reference and is NOT averaged into the primary
location model index.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from .config import (
    REQUEST_TIMEOUT, TIMEZONE, IDAR_OBERSTEIN_WMO,
    DWD_RADIOSONDE_STATION_ID,
    DWD_RADIOSONDE_HIGHRES_RECENT_URL,
    DWD_RADIOSONDE_HIGHRES_HIST_URL,
)
from .models import SourceStatus
from .logger import LOGGER
from .cache import cache_path


USER_AGENT = "Inversion-Analyzer/0.13.2"
MAX_AGL_M = 2500.0
HEIGHT_BIN_M = 25.0
SOUNDING_GAP_MIN = 30.0

_TIME_ALIASES = (
    "MESS_DATUM", "MESS_DATUM_BEGINN", "DATUM", "DATE", "TIME",
    "TIMESTAMP", "ZEIT", "MESSZEIT"
)
_TEMP_ALIASES = (
    "AE_TT", "TTT", "TT", "TEMPERATUR", "TEMPERATURE", "TEMP", "T"
)
_HEIGHT_ALIASES = (
    "AE_GPM", "H", "HOEHE", "HÖHE", "HEIGHT", "GEO_HOEHE",
    "GEOPOTENTIAL_HEIGHT", "ALTITUDE", "ALT", "GPH"
)
_PRESSURE_ALIASES = (
    "AE_P", "PPPP", "P", "PRESSURE", "LUFTDRUCK", "DRUCK"
)


def _norm(s):
    return re.sub(r"[^A-Z0-9ÄÖÜ]+", "_", str(s).strip().upper()).strip("_")


def _find_column(columns, aliases, contains=()):
    norm_map={_norm(c):c for c in columns}
    for a in aliases:
        if _norm(a) in norm_map:
            return norm_map[_norm(a)]
    for nc,c in norm_map.items():
        if any(token in nc for token in contains):
            return c
    return None


def _download_to_cache(url, log_cb=None):
    """Streaming download; large DWD ZIPs are cached on disk."""
    p=cache_path("radiosonde_highres",url,suffix=".zip")
    if p.exists() and p.stat().st_size > 1024:
        if log_cb:
            log_cb(f"Radiosonde Cache: {p.name} ({p.stat().st_size/1024/1024:.1f} MB)")
        return p,True

    tmp=p.with_suffix(".part")
    try:
        with requests.get(
            url,stream=True,timeout=(REQUEST_TIMEOUT, max(180,REQUEST_TIMEOUT)),
            headers={"User-Agent":USER_AGENT}
        ) as r:
            r.raise_for_status()
            total=int(r.headers.get("Content-Length") or 0)
            got=0
            with tmp.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    got += len(chunk)
                    if log_cb and total and got % (20*1024*1024) < 1024*1024:
                        log_cb(
                            f"Radiosonde Download: {got/1024/1024:.0f}/"
                            f"{total/1024/1024:.0f} MB"
                        )
        if not tmp.exists() or tmp.stat().st_size < 1024:
            raise RuntimeError("EMPTY: Radiosonden-ZIP leer")
        tmp.replace(p)
        return p,False
    except requests.Timeout as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"TIMEOUT: {url}") from exc
    except requests.RequestException as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"HTTP/NETWORK: {url}: {exc}") from exc
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _get_text(url):
    try:
        r=requests.get(url,timeout=REQUEST_TIMEOUT,headers={"User-Agent":USER_AGENT})
        r.raise_for_status()
        return r.text
    except requests.Timeout as exc:
        raise RuntimeError(f"TIMEOUT: {url}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"HTTP/NETWORK: {url}: {exc}") from exc


def _source_zip_url(selected_date, log_cb=None):
    """
    Use recent for the current year. For earlier years, discover the exact
    annual historical filename from the DWD directory listing.
    """
    now_year=datetime.now(ZoneInfo(TIMEZONE)).year
    if selected_date.year >= now_year:
        return urljoin(
            DWD_RADIOSONDE_HIGHRES_RECENT_URL,
            f"sekundenwerte_aero_{DWD_RADIOSONDE_STATION_ID}_akt.zip"
        ),"RECENT"

    year_url=urljoin(DWD_RADIOSONDE_HIGHRES_HIST_URL,f"{selected_date.year}/")
    html=_get_text(year_url)
    rx=re.compile(
        rf'href="([^"]*sekundenwerte_aero_{re.escape(DWD_RADIOSONDE_STATION_ID)}_'
        rf'\d{{8}}_\d{{8}}_hist[^"]*\.zip)"',
        re.I
    )
    hits=rx.findall(html)
    if not hits:
        raise RuntimeError(
            f"NO_DATA_DATE: kein historisches DWD-Radiosonden-ZIP "
            f"für Station {DWD_RADIOSONDE_STATION_ID} im Jahr {selected_date.year}"
        )
    return urljoin(year_url,hits[-1]),"HISTORICAL"


def _parse_dwd_sounding_time(base_series, offset_series=None):
    """
    DWD high-resolution radiosonde time model:
      BEZUGSDATUM_SYNOP = launch synoptic time, e.g. 2026010106 (UTC)
      MESSZEITPUNKT     = seconds since launch, e.g. 0, 2, 4, ...
    """
    base_txt=base_series.astype(str).str.strip()

    base=pd.to_datetime(
        base_txt,
        format="%Y%m%d%H",
        errors="coerce",
        utc=True
    )

    if base.notna().sum() == 0:
        # Fallback for other DWD products / historical variations.
        return _parse_datetime_series(base_series)

    if offset_series is None:
        return base

    offsets=pd.to_numeric(
        offset_series.astype(str).str.strip().str.replace(",",".",regex=False),
        errors="coerce"
    ).fillna(0.0)

    return base + pd.to_timedelta(offsets,unit="s")


def _parse_datetime_series(s):
    text=s.astype(str).str.strip()
    # DWD commonly uses YYYYMMDDhhmmss or YYYYMMDDhhmm.
    out=pd.to_datetime(text,format="%Y%m%d%H%M%S",errors="coerce",utc=True)
    if out.notna().sum() == 0:
        out=pd.to_datetime(text,format="%Y%m%d%H%M",errors="coerce",utc=True)
    if out.notna().sum() == 0:
        out=pd.to_datetime(text,errors="coerce",utc=True)
    return out


def _numeric(series):
    s=series.astype(str).str.strip().str.replace(",",".",regex=False)
    return pd.to_numeric(s,errors="coerce")


def _normalize_temperature(series):
    x=_numeric(series)
    valid=x[(x>-200) & (x<500)]
    if not valid.empty and float(valid.median()) > 100:
        x=x-273.15
    # Physical sanity window adequate for tropospheric radiosonde data.
    return x.where((x>-100) & (x<60))


def _normalize_height(series):
    x=_numeric(series)
    return x.where((x>-500) & (x<60000))


def _normalize_pressure(series):
    x=_numeric(series)
    valid=x[(x>0) & (x<200000)]
    if not valid.empty and float(valid.median()) > 2000:
        x=x/100.0
    return x.where((x>0) & (x<1200))


def _product_member_date_range(member_name):
    """
    Parse DWD product filename:
      produkt_sec_aero_YYYYMMDD_YYYYMMDD_02385.txt
    Returns (start_date, end_date) or (None, None).
    """
    m=re.search(
        r"produkt_sec_aero_(\d{8})_(\d{8})_\d+",
        member_name,
        re.I
    )
    if not m:
        return None,None
    try:
        start=pd.to_datetime(m.group(1),format="%Y%m%d").date()
        end=pd.to_datetime(m.group(2),format="%Y%m%d").date()
        return start,end
    except Exception:
        return None,None


def _select_product_member(zf, selected_date, log_cb=None):
    """
    Prefer the real product_sec_aero file immediately.
    Also short-circuit when its filename proves that selected_date is outside
    the contained date range.
    """
    products=[
        n for n in zf.namelist()
        if not n.endswith("/")
        and "produkt_sec_aero_" in n.lower()
    ]
    if not products:
        return None

    # Prefer station-specific member, then newest lexical name.
    station_token=f"_{DWD_RADIOSONDE_STATION_ID}"
    products.sort(
        key=lambda n:(station_token not in n, n),
        reverse=False
    )
    product=products[-1] if len(products)>1 else products[0]

    start,end=_product_member_date_range(product)
    if log_cb:
        log_cb(
            f"Radiosonde Produktdatei: {product}"
            + (
                f" | Datenbereich {start} bis {end}"
                if start and end else
                " | Datenbereich aus Dateiname nicht bestimmbar"
            )
        )

    if start and end and not (start <= selected_date <= end):
        raise RuntimeError(
            f"NO_DATA_DATE: DWD-Radiosondenprodukt enthält {start} bis {end}; "
            f"gewählter Tag {selected_date} ist nicht enthalten"
        )

    return product


def _member_candidates(zf):
    """
    Return likely textual DWD data members.

    v0.13.1 no longer relies on a fixed .txt/.csv/.dat extension because
    DWD archive member naming can vary. Binary-looking metadata files are
    rejected later by the text probe.
    """
    files=[]
    for n in zf.namelist():
        if n.endswith("/"):
            continue
        low=n.lower()
        score=0
        if any(k in low for k in ("produkt","product","sekunden","sec_aero","aero")):
            score += 20
        if any(low.endswith(ext) for ext in (".txt",".csv",".dat",".asc",".tsv")):
            score += 10
        if any(k in low for k in ("beschreibung","station","meta","readme")):
            score -= 30
        files.append((score,n))
    files.sort(key=lambda x:(-x[0],len(x[1]),x[1]))
    return [n for _,n in files]


def _decode_probe(raw):
    for enc in ("utf-8-sig","utf-8","cp1252","latin1"):
        try:
            return raw.decode(enc),enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1",errors="replace"),"latin1"


def _detect_separator(sample_text):
    """Return separator name/value from the first useful lines."""
    lines=[ln for ln in sample_text.splitlines() if ln.strip()]
    if not lines:
        return None,None

    # Prefer delimiters with a stable multi-column count.
    candidates=[("semicolon",";"),("tab","\t"),("comma",","),("pipe","|")]
    probe=lines[:8]
    best=None
    for name,sep in candidates:
        counts=[len(x.split(sep)) for x in probe]
        score=(sum(c>2 for c in counts), min(counts), max(counts))
        if score[0] and (best is None or score > best[0]):
            best=(score,name,sep)
    if best:
        return best[1],best[2]

    # DWD legacy products can also be whitespace separated.
    ws_counts=[len(re.split(r"\s+",x.strip())) for x in probe]
    if sum(c>2 for c in ws_counts) >= max(1,len(probe)//2):
        return "whitespace",r"\s+"

    return None,None


def _probe_member(zf,member,log_cb=None):
    """Inspect only a small prefix and return parser information."""
    with zf.open(member) as fh:
        raw=fh.read(32768)
    text,enc=_decode_probe(raw)
    sep_name,sep=_detect_separator(text)
    lines=[ln for ln in text.splitlines() if ln.strip()]
    sample=lines[:5]
    if log_cb:
        log_cb(
            f"Radiosonde ZIP-Member Probe: {member} | "
            f"{len(raw)} Probe-Bytes | Encoding={enc} | "
            f"Separator={sep_name or 'NICHT ERKANNT'}"
        )
        for i,line in enumerate(sample[:3],1):
            # avoid flooding the normal log
            log_cb(f"Radiosonde Headerprobe {i}: {line[:350]}")
    return {
        "member":member,
        "encoding":enc,
        "sep_name":sep_name,
        "sep":sep,
        "sample":sample,
    }


def _read_header_columns(zf,probe):
    sep=probe["sep"]
    if not sep:
        return []
    with zf.open(probe["member"]) as fh:
        kwargs=dict(
            nrows=0,
            encoding=probe["encoding"],
            dtype=str,
            comment=None,
        )
        if probe["sep_name"]=="whitespace":
            kwargs["sep"]=sep
            kwargs["engine"]="python"
        else:
            kwargs["sep"]=sep
        try:
            df=pd.read_csv(fh,**kwargs)
        except Exception:
            return []
    return [str(c).strip() for c in df.columns]



def _read_selected_day(zip_path, selected_date, log_cb=None):
    """
    v0.13.2:
    - select produkt_sec_aero directly when available
    - reject selected dates outside filename date range before reading 1.6 GB
    - recognize AE_TT / AE_GPM / AE_P explicitly
    - compose timestamp from BEZUGSDATUM_SYNOP + MESSZEITPUNKT seconds
    """
    keep=[]
    total_rows=0
    matched_rows=0

    with zipfile.ZipFile(zip_path) as zf:
        if log_cb:
            log_cb(f"Radiosonde ZIP: {len(zf.namelist())} Member insgesamt.")

        selected=_select_product_member(zf,selected_date,log_cb)

        # If there is no canonical product member, fall back to v0.13.1 probing.
        candidates=[selected] if selected else _member_candidates(zf)[:20]

        chosen=None
        probe=None
        detected=None

        for member in candidates:
            if member is None:
                continue

            try:
                if log_cb:
                    info=zf.getinfo(member)
                    log_cb(
                        f"Radiosonde ZIP-Member: {member} | "
                        f"{info.file_size} Byte"
                    )

                pr=_probe_member(zf,member,log_cb)
                cols=_read_header_columns(zf,pr)
                if not cols:
                    continue

                tc=_find_column(
                    cols,_TIME_ALIASES,
                    ("BEZUGSDATUM_SYNOP","MESS_DATUM","DATUM","TIMESTAMP","DATE","TIME","ZEIT")
                )
                tempc=_find_column(
                    cols,_TEMP_ALIASES,
                    ("AE_TT","TEMPER","TEMP","TTT","T_C","AIR_TEMP")
                )
                hc=_find_column(
                    cols,_HEIGHT_ALIASES,
                    ("AE_GPM","GEO","GEOP","HEIGHT","HOEHE","HÖHE","ALT","GP")
                )
                pc=_find_column(
                    cols,_PRESSURE_ALIASES,
                    ("AE_P","PRESS","DRUCK","PPPP","P_HPA")
                )
                offsetc=_find_column(
                    cols,
                    ("MESSZEITPUNKT","TIME_OFFSET","OFFSET_SECONDS"),
                    ("MESSZEITPUNKT","OFFSET")
                )

                if log_cb:
                    log_cb(
                        f"Radiosonde Header-Spalten ({member}): "
                        + ", ".join(cols[:40])
                    )
                    log_cb(
                        "Radiosonde Erkennung: "
                        f"Zeitbasis={tc or 'FEHLT'} | "
                        f"Zeitoffset={offsetc or 'nicht vorhanden'} | "
                        f"Temperatur={tempc or 'FEHLT'} | "
                        f"Höhe={hc or 'FEHLT'} | "
                        f"Druck={pc or 'optional/fehlt'}"
                    )

                if tc and tempc and hc:
                    chosen=member
                    probe=pr
                    detected=(tc,offsetc,tempc,hc,pc)
                    break
            except RuntimeError:
                raise
            except Exception as exc:
                if log_cb:
                    log_cb(
                        f"Radiosonde Probe-Fehler {member}: "
                        f"{type(exc).__name__}: {exc}"
                    )

        if chosen is None or probe is None or detected is None:
            raise RuntimeError(
                "FORMAT_CHANGED: kein ZIP-Member mit Zeit/Temperatur/Höhe erkannt"
            )

        tc,offsetc,tempc,hc,pc=detected

        if log_cb:
            log_cb(f"Radiosonde Messdatei gewählt: {chosen}")
            log_cb(
                f"Radiosonde Parser: Encoding={probe['encoding']} | "
                f"Separator={probe['sep_name']}"
            )

        with zf.open(chosen) as fh:
            kwargs=dict(
                encoding=probe["encoding"],
                dtype=str,
                chunksize=150000,
            )
            if probe["sep_name"]=="whitespace":
                kwargs["sep"]=probe["sep"]
                kwargs["engine"]="python"
            else:
                kwargs["sep"]=probe["sep"]
                kwargs["low_memory"]=False

            try:
                reader=pd.read_csv(fh,**kwargs)
            except Exception as exc:
                raise RuntimeError(
                    f"FORMAT_CHANGED: Messdatei kann nicht gelesen werden: {exc}"
                ) from exc

            for chunk in reader:
                total_rows += len(chunk)
                chunk.columns=[str(c).strip() for c in chunk.columns]

                if tc not in chunk.columns or tempc not in chunk.columns or hc not in chunk.columns:
                    raise RuntimeError(
                        "FORMAT_CHANGED: erkannte Pflichtspalten fehlen in Datenchunks"
                    )

                offset_series=chunk[offsetc] if offsetc and offsetc in chunk.columns else None

                # Canonical DWD high-resolution time handling
                if _norm(tc)=="BEZUGSDATUM_SYNOP":
                    t=_parse_dwd_sounding_time(chunk[tc],offset_series)
                else:
                    t=_parse_datetime_series(chunk[tc])

                local=t.dt.tz_convert(TIMEZONE)
                mask=local.notna() & (local.dt.date == selected_date)
                nmatch=int(mask.sum())
                if not nmatch:
                    continue

                matched_rows += nmatch

                out=pd.DataFrame({
                    "time":local[mask],
                    "temperature_C":_normalize_temperature(chunk.loc[mask,tempc]),
                    "height_msl_m":_normalize_height(chunk.loc[mask,hc]),
                })

                if pc and pc in chunk.columns:
                    out["pressure_hPa"]=_normalize_pressure(chunk.loc[mask,pc])
                else:
                    out["pressure_hPa"]=np.nan

                keep.append(out)

    if log_cb:
        log_cb(
            f"Radiosonde Parser-Bilanz: {total_rows} Datenzeilen gelesen | "
            f"{matched_rows} Zeilen für {selected_date} ({TIMEZONE})."
        )

    if not keep:
        return pd.DataFrame()

    df=pd.concat(keep,ignore_index=True)
    before=len(df)
    df=df.dropna(subset=["time","temperature_C","height_msl_m"])
    dropped=before-len(df)

    df=df.sort_values("time").drop_duplicates(
        subset=["time","height_msl_m"],keep="last"
    ).reset_index(drop=True)

    if log_cb:
        log_cb(
            f"Radiosonde gültige Messzeilen: {len(df)} | "
            f"wegen Zeit/Temperatur/Höhe verworfen: {dropped}"
        )
        if not df.empty:
            log_cb(
                f"Radiosonde Zeitraum Tagesfilter: "
                f"{df['time'].min().isoformat()} bis "
                f"{df['time'].max().isoformat()}"
            )

    return df



def _split_soundings(df):
    if df is None or df.empty:
        return df
    out=df.copy().sort_values("time").reset_index(drop=True)
    gaps=out["time"].diff().dt.total_seconds().div(60)
    out["sounding_id"]=(gaps.isna() | (gaps>SOUNDING_GAP_MIN)).cumsum().astype(int)
    return out


def _prepare_profiles(df):
    """Add AGL per sounding and keep the boundary-layer portion."""
    if df is None or df.empty:
        return df
    parts=[]
    for sid,g in _split_soundings(df).groupby("sounding_id",sort=True):
        g=g.copy().sort_values("time")
        base=float(g["height_msl_m"].quantile(0.02))
        # Quantile is more robust than an isolated erroneous minimum.
        g["height_agl_m"]=g["height_msl_m"]-base
        g["height_agl_m"]=g["height_agl_m"].clip(lower=0)
        g["sounding_start"]=g["time"].iloc[0]
        g["station_id"]=DWD_RADIOSONDE_STATION_ID
        g["wmo"]=IDAR_OBERSTEIN_WMO
        parts.append(g)
    return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()


def _metric_for_sounding(g):
    g=g.dropna(subset=["height_agl_m","temperature_C"]).copy()
    g=g[(g["height_agl_m"]>=0) & (g["height_agl_m"]<=MAX_AGL_M)]
    if len(g)<5:
        return None,None

    # 25 m bins reduce one-second sensor noise and balloon oscillation effects.
    g["height_bin_m"]=(g["height_agl_m"]/HEIGHT_BIN_M).round()*HEIGHT_BIN_M
    b=(g.groupby("height_bin_m",as_index=False)
         .agg(temperature_C=("temperature_C","median"),
              pressure_hPa=("pressure_hPa","median")))
    b=b.sort_values("height_bin_m")
    b["temperature_smoothed_C"]=(
        b["temperature_C"].rolling(3,center=True,min_periods=1).median()
    )
    if len(b)<3:
        return None,b

    z=b["height_bin_m"].to_numpy(float)
    t=b["temperature_smoothed_C"].to_numpy(float)

    positive=[]
    for i in range(len(z)-1):
        dz=z[i+1]-z[i]
        if dz<=0:
            continue
        dt=t[i+1]-t[i]
        grad=dt/dz*100.0
        if dt>0:
            positive.append((z[i],z[i+1],dt,grad))

    max_grad=max((x[3] for x in positive),default=0.0)

    best=None
    cur=None
    for z1,z2,dt,grad in positive:
        if cur is None:
            cur=[z1,z2,dt]
        elif abs(cur[1]-z1)<=0.1:
            cur[1]=z2
            cur[2]+=dt
        else:
            if best is None or cur[2]>best[2]:
                best=cur
            cur=[z1,z2,dt]
    if cur is not None and (best is None or cur[2]>best[2]):
        best=cur

    if best:
        base,top,delta=best
        depth=top-base
    else:
        base=top=delta=depth=0.0

    grad_score=np.clip(max_grad/1.5,0,1)
    dt_score=np.clip(delta/4.0,0,1)
    depth_score=np.clip(depth/500.0,0,1)
    index=5.0*(0.55*grad_score + 0.30*dt_score + 0.15*depth_score)

    start=g["sounding_start"].iloc[0]
    row={
        "time":start,
        "radiosonde_index":float(index),
        "radiosonde_max_positive_gradient_K_per_100m":float(max_grad),
        "radiosonde_inversion_deltaT_K":float(delta),
        "radiosonde_inversion_depth_m":float(depth),
        "radiosonde_inversion_base_m":float(base),
        "radiosonde_inversion_top_m":float(top),
        "radiosonde_profile_points":int(len(g)),
        "radiosonde_binned_levels":int(len(b)),
    }
    b=b.copy()
    b["time"]=start
    b["sounding_id"]=int(g["sounding_id"].iloc[0])
    return row,b


def calculate_radiosonde_metrics(profile_df):
    if profile_df is None or profile_df.empty:
        return pd.DataFrame(),pd.DataFrame()

    metrics=[]
    binned=[]
    for sid,g in profile_df.groupby("sounding_id",sort=True):
        row,b=_metric_for_sounding(g)
        if row is not None:
            metrics.append(row)
        if b is not None and not b.empty:
            binned.append(b)

    m=pd.DataFrame(metrics)
    if not m.empty:
        m=m.sort_values("time").reset_index(drop=True)
    bp=pd.concat(binned,ignore_index=True) if binned else pd.DataFrame()
    return m,bp


def fetch_idar_oberstein_profiles(selected_date, log_cb=None):
    status=SourceStatus(
        name="Radiosonde Idar-Oberstein 10618 / DWD 02385",
        last_attempt=datetime.now(ZoneInfo(TIMEZONE))
    )
    info=[]

    try:
        url,archive_kind=_source_zip_url(selected_date,log_cb)
        if log_cb:
            log_cb(
                f"Radiosonde Messprofil: DWD High Resolution {archive_kind} | "
                f"Station {DWD_RADIOSONDE_STATION_ID} / WMO {IDAR_OBERSTEIN_WMO}"
            )
        path,from_cache=_download_to_cache(url,log_cb)
        raw=_read_selected_day(path,selected_date,log_cb)

        if raw is None or raw.empty:
            status.state="NO_DATA_DATE"
            status.message=(
                f"Keine hochaufgelösten DWD-Radiosondenmesswerte für "
                f"{selected_date} in Station {DWD_RADIOSONDE_STATION_ID}"
            )
            status.detail=(
                f"Quelle: {archive_kind}; ZIP: {url.rsplit('/',1)[-1]}. "
                "Es werden keine Werte eines anderen Tages verwendet."
            )
            return pd.DataFrame(),pd.DataFrame(),info,status

        profiles=_prepare_profiles(raw)
        if log_cb and profiles is not None and not profiles.empty:
            counts=profiles.groupby("sounding_id").size().to_dict()
            starts=profiles.groupby("sounding_id")["sounding_start"].first().to_dict()
            log_cb(f"Radiosonde erkannte Aufstiege: {len(counts)}")
            for sid in sorted(counts)[:12]:
                log_cb(
                    f"Radiosonde Aufstieg {sid}: Start={pd.Timestamp(starts[sid]).isoformat()} | "
                    f"{counts[sid]} Rohpunkte"
                )

        metrics,binned=calculate_radiosonde_metrics(profiles)

        if metrics.empty:
            status.state="INCOMPLETE"
            status.message=(
                f"Radiosondenmesswerte für {selected_date} vorhanden, "
                "aber kein Profil ausreichend auswertbar"
            )
            status.detail=(
                f"{len(profiles)} Rohzeilen; Temperatur/Höhe wurden erkannt. "
                "Keine künstliche Nullkurve erzeugt."
            )
            return profiles,pd.DataFrame(),info,status

        for _,r in metrics.iterrows():
            info.append({
                "launch_time":pd.Timestamp(r["time"]).isoformat(),
                "profile_points":int(r["radiosonde_profile_points"]),
                "binned_levels":int(r["radiosonde_binned_levels"]),
                "index":float(r["radiosonde_index"]),
                "deltaT_K":float(r["radiosonde_inversion_deltaT_K"]),
                "depth_m":float(r["radiosonde_inversion_depth_m"]),
                "used_for_inversion_index":True,
                "source":"DWD CDC high_resolution",
            })

        positive=int((metrics["radiosonde_index"]>0).sum())
        status.state="OK"
        status.message=(
            f"{len(metrics)} gemessene Radiosondenprofil(e) ausgewertet; "
            f"{positive} mit Inversionsindex > 0"
        )
        status.rows=len(metrics)
        status.last_success=datetime.now(ZoneInfo(TIMEZONE))
        status.detail=(
            f"DWD High Resolution {archive_kind}; Station 02385 / WMO 10618. "
            f"Rohmesswerte: {len(profiles)}; separate gemessene Referenzkurve. "
            "25-m-Höhenbins + 3-Bin-Median. Nicht mit dem Standortmodell "
            "oder ICON-D2 gemittelt."
        )
        if from_cache:
            status.detail += " ZIP aus lokalem Cache."
        if log_cb:
            for _,r in metrics.iterrows():
                log_cb(
                    f"Radiosonde {r['time']:%H:%M}: Index "
                    f"{r['radiosonde_index']:.2f}/5 | "
                    f"ΔT {r['radiosonde_inversion_deltaT_K']:.2f} K | "
                    f"Tiefe {r['radiosonde_inversion_depth_m']:.0f} m"
                )
        return profiles,metrics,info,status

    except Exception as exc:
        msg=str(exc)
        if msg.startswith("TIMEOUT"):
            state="TIMEOUT"
        elif msg.startswith("HTTP/NETWORK"):
            state="NETWORK"
        elif msg.startswith("NO_DATA_DATE"):
            state="NO_DATA_DATE"
        elif msg.startswith("FORMAT_CHANGED"):
            state="FORMAT_CHANGED"
        elif msg.startswith("EMPTY"):
            state="EMPTY"
        else:
            state="ERROR"
        status.state=state
        status.message=msg
        status.detail=(
            "Radiosonden-Messkanal ausgefallen. Vorhandene archivierte "
            "Radiosondendaten dürfen dadurch nicht gelöscht werden."
        )
        if log_cb:
            log_cb(f"Radiosonde: {state} | {msg}")
            log_cb(
                "Radiosonde: keine künstliche Nullkurve erzeugt; "
                "vorhandenes Archiv wird bei Fehler geschützt."
            )
        LOGGER.exception("Radiosonden-Messprofil fehlgeschlagen")
        return pd.DataFrame(),pd.DataFrame(),info,status


# Backward-compatible name for older callers. It now returns measured profile
# metadata rather than trajectory-only diagnostics.
def fetch_idar_oberstein_diagnostics(selected_date, log_cb=None):
    profiles,metrics,info,status=fetch_idar_oberstein_profiles(selected_date,log_cb)
    return info,status
