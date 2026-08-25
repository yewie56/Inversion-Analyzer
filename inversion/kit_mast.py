# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests

from .config import (
    LAT, LON, TIMEZONE, REQUEST_TIMEOUT, LOG_DIR,
    KIT_MAST_INFO_URL, KIT_MAST_DASHBOARD_URL,
    KIT_MAST_PROFILE_URL, KIT_MAST_MONTHLY_URL,
    KIT_MAST_LAT, KIT_MAST_LON, KIT_MAST_ALT_M,
    KIT_MAST_TEMP_HEIGHTS_M,
)
from .models import SourceStatus
from .logger import LOGGER
from .bokeh_extract import analyze_bokeh_html
from .bokeh_client import pull_bokeh_document


def haversine_km(lat1,lon1,lat2,lon2):
    r=6371.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))


def _request(url):
    try:
        r=requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent":"Inversion-Analyzer/0.8.0"},
        )
    except requests.Timeout as exc:
        raise RuntimeError(f"TIMEOUT: {url}") from exc
    except requests.ConnectionError as exc:
        raise RuntimeError(f"NETWORK: {url}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"REQUEST: {url}: {exc}") from exc

    if r.status_code!=200:
        raise RuntimeError(f"HTTP_{r.status_code}: {url}")
    if not r.content:
        raise RuntimeError(f"EMPTY: {url}")
    return r


def _dashboard_version(text):
    m=re.search(r"\bv(\d+\.\d+\.\d+)\s*(?:\((\d{4}-\d{2}-\d{2})\))?",text)
    return {"version":m.group(1),"date":m.group(2)} if m else None


def _save_html_snapshot(name,text,run_id):
    LOG_DIR.mkdir(parents=True,exist_ok=True)
    path=LOG_DIR/f"kit_{name}_{run_id}.html"
    path.write_text(text,encoding="utf-8")
    return str(path)


def _write_report(info,run_id):
    LOG_DIR.mkdir(parents=True,exist_ok=True)
    path=LOG_DIR/f"kit_diagnostic_{run_id}.json"
    path.write_text(
        json.dumps(info,ensure_ascii=False,indent=2,default=str),
        encoding="utf-8",
    )
    return str(path)


def _summarize_bokeh(name,analysis):
    markers=analysis.get("markers",{})
    return {
        "page":name,
        "parsed_payload_count":analysis.get("parsed_payload_count",0),
        "application_json_blocks":analysis.get("application_json_blocks",[]),
        "assignment_blocks":analysis.get("assignment_blocks",[]),
        "column_data_source_count":len(analysis.get("column_data_sources",[])),
        "markers":markers,
        "ranked_column_data_sources":analysis.get("ranked_column_data_sources",[])[:25],
    }


def fetch_kit_mast_diagnostics(selected_date,log_cb=None,run_id="unknown"):
    status=SourceStatus(
        name="KIT 200-m-Meteomast",
        last_attempt=datetime.now(ZoneInfo(TIMEZONE)),
    )

    def log(msg):
        LOGGER.info(msg)
        if log_cb:
            log_cb(msg)

    info={
        "run_id":run_id,
        "station":"KIT Campus Nord 200-m-Meteomast",
        "lat":KIT_MAST_LAT,
        "lon":KIT_MAST_LON,
        "alt_m":KIT_MAST_ALT_M,
        "distance_to_viernheim_km":haversine_km(
            LAT,LON,KIT_MAST_LAT,KIT_MAST_LON
        ),
        "temperature_heights_m":list(KIT_MAST_TEMP_HEIGHTS_M),
        "selected_date":selected_date.isoformat(),
        "dashboard_version":None,
        "html_snapshots":{},
        "bokeh":{},
        "bokeh_column_sources":[],
        "best_bokeh_candidates":[],
        "diagnostic_file":None,
        "used_for_inversion_index":False,
        "numeric_data_verified":False,
        "bokeh_payload_detected":False,
        "bokeh_client":{},
    }

    errors=[]

    # Official information page
    try:
        log("KIT-Mast: offizielle Informationsseite prüfen ...")
        r=_request(KIT_MAST_INFO_URL)
        info["info_page_ok"]=True
        info["heights_confirmed_in_page"]=all(
            str(h) in r.text for h in (2,10,30,60,100,130,160,200)
        )
    except Exception as exc:
        info["info_page_ok"]=False
        errors.append(f"Infoseite: {exc}")

    pages=(
        ("dashboard",KIT_MAST_DASHBOARD_URL),
        ("profile",KIT_MAST_PROFILE_URL),
        ("monthly",KIT_MAST_MONTHLY_URL),
    )

    all_sources=[]
    all_ranked=[]

    for name,url in pages:
        try:
            if name=="dashboard":
                log("KIT-Mast: Dashboard/Bokeh-Dokument prüfen ...")
            elif name=="profile":
                log("KIT-Mast: 10-min-Profilseite/Bokeh-Dokument prüfen ...")
            else:
                log("KIT-Mast: 30-Tage-Seite/Bokeh-Dokument prüfen ...")

            r=_request(url)
            text=r.text
            info[f"{name}_page_ok"]=True

            try:
                info["html_snapshots"][name]=_save_html_snapshot(name,text,run_id)
            except Exception as exc:
                errors.append(f"HTML-Snapshot {name}: {exc}")

            if not info["dashboard_version"]:
                v=_dashboard_version(text)
                if v:
                    info["dashboard_version"]=v
                    log(
                        f"KIT-Mast: {name} meldet v{v['version']}"
                        + (f" ({v['date']})" if v.get("date") else "")
                    )

            analysis=analyze_bokeh_html(text)
            summary=_summarize_bokeh(name,analysis)
            info["bokeh"][name]=summary

            source_count=summary["column_data_source_count"]
            payload_count=summary["parsed_payload_count"]
            marker_hits=sum(summary["markers"].values())

            log(
                f"KIT-Bokeh {name}: {payload_count} JSON-Payload(s), "
                f"{source_count} ColumnDataSource-Kandidat(en), "
                f"{marker_hits} Bokeh-Marker."
            )

            for source in analysis.get("column_data_sources",[]):
                item=dict(source)
                item["page"]=name
                all_sources.append(item)

            for source in analysis.get("ranked_column_data_sources",[]):
                item=dict(source)
                item["page"]=name
                all_ranked.append(item)

        except Exception as exc:
            info[f"{name}_page_ok"]=False
            errors.append(f"{name}: {exc}")

    info["bokeh_column_sources"]=all_sources[:100]
    all_ranked.sort(
        key=lambda x:(-x.get("heuristic_score",0),-x.get("row_count_estimate",0))
    )
    info["best_bokeh_candidates"]=all_ranked[:30]

    any_payload=any(
        page.get("parsed_payload_count",0)>0
        for page in info["bokeh"].values()
    )
    any_cds=bool(all_sources)

    info["bokeh_payload_detected"]=any_payload
    info["numeric_data_verified"]=any_cds

    if any_cds:
        log(
            f"KIT-Bokeh: insgesamt {len(all_sources)} "
            "ColumnDataSource-Kandidat(en) aus eingebettetem HTML extrahiert."
        )
        top=all_ranked[0] if all_ranked else None
        if top:
            log(
                "KIT-Bokeh: bester Kandidat "
                f"Seite={top.get('page')}, "
                f"Score={top.get('heuristic_score')}, "
                f"Spalten={top.get('column_names')}, "
                f"Zeilen≈{top.get('row_count_estimate')}."
            )
    elif any_payload:
        log(
            "KIT-Bokeh: eingebettete JSON-Payloads gefunden, "
            "aber noch keine ColumnDataSource-Struktur erkannt."
        )
    else:
        log(
            "KIT-Bokeh: keine eingebettete JSON-Datenstruktur erkannt; "
            "möglicherweise serverseitige Bokeh-Session."
        )

    # v0.9: pull the actual server-side Bokeh document.
    client_result = pull_bokeh_document(
        KIT_MAST_PROFILE_URL,
        run_id=run_id,
        log_cb=log_cb,
    )
    info["bokeh_client"] = client_result

    if client_result.get("ok"):
        client_sources = client_result.get("sources", []) or []
        if client_sources:
            log(
                f"KIT-Mast: Bokeh-Client lieferte {len(client_sources)} "
                "ColumnDataSource-Objekt(e)."
            )
    else:
        log(
            f"KIT-Mast: Bokeh-Client Status {client_result.get('state')}: "
            f"{client_result.get('message')}"
        )

    try:
        info["diagnostic_file"]=_write_report(info,run_id)
        log(f"KIT-Mast: Diagnosebericht gespeichert: {info['diagnostic_file']}")
    except Exception as exc:
        errors.append(f"Diagnosebericht: {exc}")

    if not info.get("dashboard_page_ok") and not info.get("profile_page_ok"):
        status.state="NETWORK"
        status.message="KIT-Dashboard/Profilseite nicht erreichbar"
        status.detail=" | ".join(errors[:4])
        return info,None,status

    client_result=info.get("bokeh_client",{}) or {}
    client_sources=client_result.get("sources",[]) or []

    if client_result.get("ok") and client_sources:
        status.state="BOKEH_CLIENT_DATA"
        status.message=(
            f"{len(client_sources)} ColumnDataSource-Objekt(e) "
            "über Bokeh-Client geladen"
        )
        status.detail=(
            "Serverseitiges Bokeh-Dokument erfolgreich geladen. "
            "Rohdaten wurden als JSON/CSV gespeichert. "
            "Meteorologische Zuordnung noch nicht validiert; "
            "noch kein Einfluss auf den Inversionsindex. "
            f"Diagnose: {info.get('diagnostic_file') or '–'}"
        )
    elif client_result.get("state")=="BOKEH_CLIENT_MISSING":
        status.state="BOKEH_CLIENT_MISSING"
        status.message="Python-Paket bokeh fehlt"
        status.detail=(
            "Für v0.9 wird das Paket bokeh benötigt. "
            "Installation z. B. mit: pip install bokeh. "
            f"Details: {client_result.get('detail','')}"
        )
    elif client_result.get("state")=="BOKEH_CLIENT_ERROR":
        status.state="BOKEH_CLIENT_ERROR"
        status.message="Bokeh-Server-Session konnte nicht geladen werden"
        status.detail=(
            f"{client_result.get('detail','')}. "
            f"Diagnose: {info.get('diagnostic_file') or '–'}"
        )
    elif any_cds:
        status.state="BOKEH_DATA_FOUND"
        status.message=(
            f"{len(all_sources)} eingebettete Bokeh-ColumnDataSource-"
            "Kandidat(en) gefunden"
        )
        status.detail=(
            "Daten sind aus dem gelieferten HTML extrahiert, aber ihre "
            "meteorologische Bedeutung ist noch nicht vollständig validiert. "
            "Noch kein Einfluss auf den Inversionsindex. "
            f"Diagnose: {info.get('diagnostic_file') or '–'}"
        )
    elif any_payload:
        status.state="BOKEH_PAYLOAD"
        status.message="Bokeh-JSON im HTML gefunden; Datenstruktur noch nicht zugeordnet"
        status.detail=(
            "HTML enthält Session-/Renderinformationen; "
            "der eigentliche Datenweg wird über den Bokeh-Client geprüft. "
            f"Diagnose: {info.get('diagnostic_file') or '–'}"
        )
    else:
        status.state="BOKEH_SERVER"
        status.message="Bokeh-Seite erreichbar; keine eingebetteten Messdaten gefunden"
        status.detail=(
            "Serverseitige Bokeh-Session erforderlich. "
            f"Diagnose: {info.get('diagnostic_file') or '–'}"
        )

    if errors:
        status.detail+=" Teilfehler: "+" | ".join(errors[:3])

    status.last_success=datetime.now(ZoneInfo(TIMEZONE))
    status.rows=len(all_sources)

    # Return only diagnostic extracted data, never as trusted mast measurement.
    kit_data={
        "column_sources":all_sources,
        "ranked_candidates":all_ranked[:30],
        "client_sources":(info.get("bokeh_client",{}) or {}).get("sources",[]),
        "client_json_file":(info.get("bokeh_client",{}) or {}).get("json_file"),
        "client_csv_files":(info.get("bokeh_client",{}) or {}).get("csv_files",[]),
        "validated":False,
        "used_for_inversion_index":False,
    }
    return info,kit_data,status
