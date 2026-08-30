# -*- coding: utf-8 -*-
# =============================================================================
# Inversion Analyzer
# Version: 0.15.22
# Datum: 2026-08-30
#
# History:
# 0.15.22 - zentrales KITMast-Referenzarchiv; ein Abruf pro Scheduled-Lauf
# 0.15.21 - GitHub workflow_dispatch unterstützt normal/scheduled/kit-only
# 0.15.20 - KIT-Parser toleriert fehlende Höhenwerte; neuer --kit-only-Schalter
# 0.15.19 - KIT robuster: 30-min GitHub-Takt, Bokeh-Timeout 20 s, 3 Versuche
# 0.15.18 - KIT-GitHub-Abruf stündlich; heute+gestern; Tagesvollständigkeit
# 0.15.17 - Unteres Temperatur-/Schichtungsdiagramm abschaltbar
# 0.15.16 - Eindeutige Quellenkennzeichnung in Diagrammlegenden
# 0.15.15 - Schichtungsdiagramm auch ohne AEMET sichtbar
# 0.15.14 - Lokaler Schichtungsindex aus Vollprofil bis 600 m AGL
# 0.15.13 - Adaptiver lokaler Schichtungsindex
# 0.15.12 - Lokaler Schichtungsindex 0..5 eingeführt
# 0.15.11 - Temperaturschichtung AEMET + 100/200/500 m
# 0.15.10 - AEMET-Bodentemperatur im Diagramm
# 0.15.9  - AEMET OpenData Valencia integriert
# 0.15.8  - Valencia + standortabhängige Quellenlogik
# 0.15.7  - Kontinuierliche KIT-Archivierung
# =============================================================================

"""
Inversion_Server.py – v0.15.22

Headless collector / archive repair tool.

Wichtige Testoptionen:
  --selftest       Netzwerkfreier PASS/FAIL-Selbsttest der aktiven Ortskonfiguration.
  --show-config    Zeigt die tatsächlich aktive Orts-/Archivkonfiguration.
  --verify-archive Prüft vorhandene Manifeste des aktiven Orts auf Lesbarkeit
                   und Ortszuordnung, ohne Daten zu verändern.
  --kit-only       Ruft ausschließlich KIT für heute und gestern ab und merged kumulativ.
"""
from __future__ import annotations

import argparse
import os
import json
import sys
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from inversion.config import (
    TIMEZONE, LOCATION_NAME, LOCATION_SLUG, ARCHIVE_CONFIG, VERSION,
    PROJECT_DIR, ARCHIVE_DIR, LOCATIONS_FILE, ARCHIVE_CONFIG_FILE,
    ACTIVE_LOCATION_KEY, LAT, LON, LOCATION_ELEVATION_M,
    DWD_MAX_STATION_DISTANCE_KM, _LOCATIONS,
    DWD_ENABLED, RADIOSONDE_ENABLED, KIT_MAST_ENABLED, KIT_REFERENCE_ENABLED, ICON_D2_ENABLED,
    AEMET_ENABLED, AEMET_STATION_ID
)
from inversion.archive import (load_bundle,missing_sources,missing_optional_sources,
                               completion_sources,optional_sources,kit_archive_coverage,save_bundle,day_dir)
from inversion.archive_service import update_day
from inversion.aemet_source import selftest_aemet_parser


def log(msg):
    print(
        f"[{datetime.now(ZoneInfo(TIMEZONE)):%Y-%m-%d %H:%M:%S}] {msg}",
        flush=True
    )


def passline(name, detail=""):
    suffix=f" – {detail}" if detail else ""
    print(f"PASS | {name}{suffix}", flush=True)


def failline(name, detail=""):
    suffix=f" – {detail}" if detail else ""
    print(f"FAIL | {name}{suffix}", flush=True)


def parse_date(s):
    return datetime.strptime(s,"%Y-%m-%d").date()


def active_archive_root():
    return ARCHIVE_DIR / LOCATION_SLUG


def show_config():
    data={
        "version":VERSION,
        "active_location_key":ACTIVE_LOCATION_KEY,
        "location_name":LOCATION_NAME,
        "location_slug":LOCATION_SLUG,
        "latitude":LAT,
        "longitude":LON,
        "elevation_m":LOCATION_ELEVATION_M,
        "timezone":TIMEZONE,
        "dwd_max_station_distance_km":DWD_MAX_STATION_DISTANCE_KM,
        "source_enabled":{
            "dwd":DWD_ENABLED,
            "aemet":AEMET_ENABLED,
            "profile":True,
            "sonde":RADIOSONDE_ENABLED,
            "kit_mast":(KIT_MAST_ENABLED or KIT_REFERENCE_ENABLED),
            "kit_mast_fetch_local":KIT_MAST_ENABLED,
            "kit_reference":KIT_REFERENCE_ENABLED,
            "icon_d2":ICON_D2_ENABLED
        },
        "aemet_station_id":AEMET_STATION_ID,
        "aemet_api_key_present":bool(os.environ.get("AEMET_API_KEY","").strip()),
        "project_dir":str(PROJECT_DIR),
        "archive_dir":str(ARCHIVE_DIR),
        "active_archive_root":str(active_archive_root()),
        "completion_sources":completion_sources(),
        "optional_sources":optional_sources(),
        "retry_optional_sources":bool(
            ARCHIVE_CONFIG.get("github_actions",{}).get(
                "retry_optional_sources",False
            )
        ),
        "kit_continuous_archive":bool(
            ARCHIVE_CONFIG.get("github_actions",{}).get(
                "kit_continuous_archive",True
            )
        ),
    }
    print(json.dumps(data,indent=2,ensure_ascii=False))
    return 0


def selftest():
    """
    Netzwerkfreier Test. Es werden keine Wetterdaten abgerufen und keine
    Archivdaten geschrieben.
    """
    print(f"Inversion Server Selftest v{VERSION}")
    print(f"Aktiver Ort: {ACTIVE_LOCATION_KEY} / {LOCATION_NAME}")
    failures=[]

    def check(condition,name,detail=""):
        if condition:
            passline(name,detail)
        else:
            failline(name,detail)
            failures.append(name)

    check(
        sys.version_info >= (3,11),
        "Python >= 3.11",
        sys.version.split()[0]
    )
    check(
        LOCATIONS_FILE.exists(),
        "locations.json vorhanden",
        str(LOCATIONS_FILE)
    )
    check(
        ARCHIVE_CONFIG_FILE.exists(),
        "archive_config.json vorhanden",
        str(ARCHIVE_CONFIG_FILE)
    )

    locations=_LOCATIONS.get("locations",{})
    check(
        ACTIVE_LOCATION_KEY in locations,
        "aktiver Ort existiert in locations.json",
        ACTIVE_LOCATION_KEY
    )

    loc=locations.get(ACTIVE_LOCATION_KEY,{})
    check(
        isinstance(loc.get("latitude"),(int,float)),
        "Breitengrad vorhanden",
        str(loc.get("latitude"))
    )
    check(
        isinstance(loc.get("longitude"),(int,float)),
        "Längengrad vorhanden",
        str(loc.get("longitude"))
    )
    check(
        bool(str(loc.get("timezone","")).strip()),
        "Zeitzone vorhanden",
        str(loc.get("timezone"))
    )

    try:
        ZoneInfo(TIMEZONE)
        tz_ok=True
    except Exception as exc:
        tz_ok=False
        tz_detail=str(exc)
    else:
        tz_detail=TIMEZONE
    check(tz_ok,"Zeitzone ist verwendbar",tz_detail)

    check(
        -90.0 <= LAT <= 90.0 and -180.0 <= LON <= 180.0,
        "Koordinaten plausibel",
        f"{LAT:.6f}, {LON:.6f}"
    )
    check(
        DWD_MAX_STATION_DISTANCE_KM > 0,
        "DWD-Maximalradius plausibel",
        f"{DWD_MAX_STATION_DISTANCE_KM:.1f} km"
    )

    # Every configured location must map to a unique archive slug. Otherwise
    # two locations could accidentally write into the same archive directory.
    slugs={}
    collisions=[]
    from inversion.config import _slug
    for key,item in locations.items():
        slug=_slug(item.get("name",key))
        if slug in slugs and slugs[slug] != key:
            collisions.append((slug,slugs[slug],key))
        slugs[slug]=key
    check(
        not collisions,
        "Archiv-Slugs aller Orte eindeutig",
        "keine Kollision" if not collisions else str(collisions)
    )

    expected=ARCHIVE_DIR / LOCATION_SLUG
    check(
        active_archive_root() == expected,
        "aktiver Archivpfad korrekt",
        str(expected)
    )

    # Ensure the day path contains the active location slug.
    probe=datetime(2000,1,2).date()
    probe_path=day_dir(probe)
    expected_probe=ARCHIVE_DIR / LOCATION_SLUG / "2000" / "01" / "02"
    check(
        probe_path == expected_probe,
        "Tagesarchiv ist ortsgetrennt",
        str(probe_path)
    )

    core=completion_sources()
    optional=optional_sources()
    allowed={"dwd","aemet","profile","sonde","kit_mast","icon_d2"}
    check(
        isinstance(core,list) and bool(core),
        "completion_sources konfiguriert",
        ", ".join(core) if isinstance(core,list) else str(core)
    )
    check(
        isinstance(core,list) and set(core).issubset(allowed),
        "completion_sources bekannt",
        ", ".join(core) if isinstance(core,list) else str(core)
    )
    check(
        isinstance(optional,list) and set(optional).issubset(allowed),
        "optional_sources bekannt",
        ", ".join(optional) if isinstance(optional,list) else str(optional)
    )
    check(
        not (set(core) & set(optional)),
        "Kern- und optionale Quellen getrennt",
        f"Kern={core} | Optional={optional}"
    )
    check(
        "sonde" not in core and "kit_mast" not in core,
        "KIT/Radiosonde beeinflussen complete nicht",
        f"Kern={core}"
    )
    kit_global=bool(ARCHIVE_CONFIG.get("github_actions",{}).get(
        "kit_continuous_archive",True
    ))
    check(
        kit_global,
        "globale KIT-Archivierungsoption konfiguriert",
        "aktiv" if kit_global else "deaktiviert"
    )
    if KIT_REFERENCE_ENABLED:
        passline("KIT-Referenz für aktiven Ort aktiviert", "liest globales archive/KITMast")
    else:
        passline("KIT-Referenz für aktiven Ort deaktiviert", "keine KIT-Referenz für diesen Ort")

    if KIT_REFERENCE_ENABLED:
        passline(
            "KIT-Tagesarchivstrategie",
            "global einmal pro Scheduled-Lauf: heute + gestern, Safe-Merge, Vollständigkeitskontrolle"
        )

    at=selftest_aemet_parser()
    check(bool(at.get("pass")),"AEMET-Parser-Selbsttest",
          f"rows={at.get('rows')} | time={at.get('time')}")

    # Imports needed for the real collection pipeline.
    import requests
    import pandas
    import numpy
    import matplotlib
    import bokeh
    check(True,"Abhängigkeiten importierbar",
          f"requests={requests.__version__}, pandas={pandas.__version__}, "
          f"numpy={numpy.__version__}")

    print()
    if failures:
        print(
            f"SELFTEST RESULT: FAIL ({len(failures)} Fehler) | "
            + ", ".join(failures),
            flush=True
        )
        return 3

    print(
        f"SELFTEST RESULT: PASS | Ort={LOCATION_NAME} | "
        f"Archiv={active_archive_root()}",
        flush=True
    )
    return 0


def verify_archive():
    """
    Read-only validation of manifests under archive/<active-location>.
    Existing legacy manifests without a location block are reported as WARN,
    not modified.
    """
    root=active_archive_root()
    print(f"Archivprüfung: {root}")
    if not root.exists():
        print("ARCHIVE VERIFY: PASS | Noch kein Archiv für diesen Ort vorhanden.")
        return 0

    manifests=sorted(root.rglob("manifest.json"))
    if not manifests:
        print("ARCHIVE VERIFY: PASS | Archivordner vorhanden, noch keine Manifeste.")
        return 0

    errors=[]
    warnings=[]
    for mf in manifests:
        try:
            data=json.loads(mf.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{mf}: JSON-Fehler: {exc}")
            continue

        loc=data.get("location")
        if not isinstance(loc,dict):
            warnings.append(f"{mf}: Legacy-Manifest ohne location-Block")
            continue

        manifest_slug=str(loc.get("slug",""))
        manifest_name=str(loc.get("name",""))
        if manifest_slug and manifest_slug != LOCATION_SLUG:
            errors.append(
                f"{mf}: location.slug={manifest_slug!r}, erwartet {LOCATION_SLUG!r}"
            )
        elif manifest_name and manifest_name != LOCATION_NAME:
            errors.append(
                f"{mf}: location.name={manifest_name!r}, erwartet {LOCATION_NAME!r}"
            )

    for item in warnings:
        print(f"WARN | {item}")
    for item in errors:
        print(f"FAIL | {item}")

    if errors:
        print(
            f"ARCHIVE VERIFY: FAIL | {len(errors)} Fehler, "
            f"{len(warnings)} Warnungen, {len(manifests)} Manifeste"
        )
        return 4

    print(
        f"ARCHIVE VERIFY: PASS | {len(manifests)} Manifeste, "
        f"{len(warnings)} Legacy-Warnungen"
    )
    return 0


def run_one(day,force=False):
    before=active_archive_root()
    log(
        f"START | Ort={LOCATION_NAME} | Datum={day} | "
        f"force={force} | Archivwurzel={before}"
    )

    b,m,origin=update_day(
        day,
        log_cb=log,
        only_missing=(not force)
    )

    miss=missing_sources(b) if b else ["ALL"]
    optional_miss=missing_optional_sources(b) if b else []
    log(
        f"ERGEBNIS | Ort={LOCATION_NAME} | Datum={day} | "
        f"origin={origin} | complete={not miss} | missing={miss} | "
        f"optional_missing={optional_miss}"
    )
    log(f"ARCHIV | {day_dir(day)}")
    return 0 if b else 2


def scheduled_kit_archive(now):
    """Update the global KITMast reference archive for today and yesterday.

    The existing Bokeh client keeps its configured hard timeout, retry count and
    retry delays. This wrapper only changes the storage target to archive/KITMast.
    """
    cfg=ARCHIVE_CONFIG.get("github_actions",{})
    if not bool(cfg.get("kit_continuous_archive",True)):
        log("KIT-REFERENZ: kontinuierliche Sicherung deaktiviert.")
        return False

    from inversion.kit_reference_archive import (
        migrate_legacy_kit_archives, update_kit_reference_day, load_kit_reference
    )
    from inversion.models import DataBundle

    migrated=migrate_legacy_kit_archives(log_cb=log)
    log(f"KIT-REFERENZ: Legacy-Migration geprüft | Dateien verarbeitet={migrated}")

    did=False
    for day in (now.date(),now.date()-timedelta(days=1)):
        log(f"KIT-REFERENZ: globaler Abruf {day}; Safe-Merge nach Zeitstempel.")
        merged,info,status,manifest=update_kit_reference_day(day,log_cb=log)
        b=DataBundle(); b.kit_mast_metrics=merged
        cov=kit_archive_coverage(b,day)
        log(
            "KIT-REFERENZ ERGEBNIS | "
            f"Datum={day} | status={cov.get('status')} | "
            f"profile={cov.get('profile_count')}/{cov.get('expected_profiles')} | "
            f"coverage={cov.get('coverage_percent')}% | "
            f"cadence={cov.get('cadence_minutes')} min | "
            f"largest_gap={cov.get('largest_gap_minutes')} min | "
            f"first={cov.get('first_timestamp')} | last={cov.get('last_timestamp')}"
        )
        if day < now.date() and cov.get("status") != "COMPLETE":
            log(
                "WARNUNG KIT-REFERENZ-TAGESARCHIV: "
                f"{day} nach Tagesende nicht vollständig "
                f"(Status={cov.get('status')}, Profile={cov.get('profile_count')}/"
                f"{cov.get('expected_profiles')}, größte Lücke={cov.get('largest_gap_minutes')} min)."
            )
        elif day < now.date():
            log(
                f"KIT-REFERENZ-TAGESARCHIV BESTÄTIGT: {day} vollständig "
                f"({cov.get('profile_count')}/{cov.get('expected_profiles')} Profile)."
            )
        did=True
    return did



def scheduled_aemet_archive(now):
    if not AEMET_ENABLED:
        return False
    if not os.environ.get("AEMET_API_KEY","").strip():
        log("AEMET-Archiv: AEMET_API_KEY fehlt; kein Abruf.")
        return False
    did=False
    for day in (now.date(),now.date()-timedelta(days=1)):
        log(f"AEMET-ARCHIV: kumulativer Abruf {day}; kein Einfluss auf core-complete/Retry.")
        b,m,origin=update_day(
            day,log_cb=log,only_missing=False,requested_sources={"aemet"},
            reason="AEMET_CONTINUOUS_ARCHIVE",increment_attempt=False,
            affects_retry_clock=False
        )
        rows=0 if b is None or getattr(b,"aemet_data",None) is None else len(b.aemet_data)
        state="NO_STATUS" if b is None or b.source_status.get("aemet") is None else b.source_status["aemet"].state
        log(f"AEMET-ARCHIV ERGEBNIS | Datum={day} | status={state} | rows={rows}")
        did=True
    return did


def scheduled():
    cfg=ARCHIVE_CONFIG.get("github_actions",{})
    hour=int(cfg.get("daily_fetch_local_hour",22))
    delay=float(cfg.get("retry_delay_hours",3))
    max_retries=int(cfg.get("max_retries",5))
    now=datetime.now(ZoneInfo(TIMEZONE))

    log(
        f"SCHEDULED START | Ort={LOCATION_NAME} | lokale Zeit={now.isoformat()} | "
        f"Erstabruf ab {hour:02d}:00"
    )

    # KIT is updated globally once by the GitHub workflow before location loops.
    scheduled_aemet_archive(now)

    candidates=[]
    if now.hour>=hour:
        candidates.append(now.date())
    candidates += [
        now.date()-timedelta(days=1),
        now.date()-timedelta(days=2)
    ]

    did=False
    for day in dict.fromkeys(candidates):
        b,m=load_bundle(day)
        if b is None:
            if day==now.date() and now.hour>=hour:
                log(f"Scheduled: Erstabruf {day}.")
                run_one(day)
                did=True
            continue

        miss=missing_sources(b)
        optional_miss=missing_optional_sources(b)
        if not miss:
            if optional_miss:
                log(
                    f"Scheduled: {day} vollständig (Kernquellen); "
                    f"optionale Zusatzquellen fehlen: {optional_miss}. "
                    "Kein Retry nur wegen optionaler Quellen."
                )
            else:
                log(f"Scheduled: {day} vollständig.")
            continue

        attempts=int((m or {}).get("attempts",0))
        if attempts>=max_retries:
            log(
                f"Scheduled: {day} unvollständig, aber max_retries="
                f"{max_retries} erreicht: {miss}"
            )
            continue

        last=(m or {}).get("last_attempt")
        due=True
        if last:
            try:
                ld=datetime.fromisoformat(last)
                if ld.tzinfo is None:
                    ld=ld.replace(tzinfo=ZoneInfo(TIMEZONE))
                due=(now-ld).total_seconds()>=delay*3600
            except Exception as exc:
                log(f"Scheduled: last_attempt nicht lesbar ({last}): {exc}")

        if due:
            log(
                f"Scheduled: Retry {day}, Versuch {attempts+1}/"
                f"{max_retries}, fehlend={miss}"
            )
            run_one(day)
            did=True
        else:
            log(
                f"Scheduled: Retry {day} noch nicht fällig, fehlend={miss}"
            )

    if not did:
        log("Scheduled: kein Kernquellen-Abruf fällig.")
    return 0


def main():
    ap=argparse.ArgumentParser(
        description="Headless collector for the multi-location inversion archive"
    )
    g=ap.add_mutually_exclusive_group()
    g.add_argument("--date",help="JJJJ-MM-TT")
    g.add_argument("--today",action="store_true")
    g.add_argument("--scheduled",action="store_true")
    g.add_argument("--kit-only",action="store_true",help="nur KIT für heute und gestern aktualisieren")
    g.add_argument("--selftest",action="store_true")
    g.add_argument("--show-config",action="store_true")
    g.add_argument("--verify-archive",action="store_true")
    ap.add_argument(
        "--force",
        action="store_true",
        help="alle Quellen neu abrufen"
    )
    args=ap.parse_args()

    print(
        f"Inversions-Headless v{VERSION} | "
        f"Ort={LOCATION_NAME} | Key={ACTIVE_LOCATION_KEY}"
    )

    if args.selftest:
        return selftest()
    if args.show_config:
        return show_config()
    if args.verify_archive:
        return verify_archive()
    if args.scheduled:
        return scheduled()
    if args.kit_only:
        now=datetime.now(ZoneInfo(TIMEZONE))
        log(f"KIT-ONLY START | globales KITMast-Archiv | lokale Zeit={now.isoformat()}")
        return 0 if scheduled_kit_archive(now) else 1

    day=(
        parse_date(args.date)
        if args.date
        else datetime.now(ZoneInfo(TIMEZONE)).date()
    )
    return run_one(day,args.force)


if __name__=="__main__":
    raise SystemExit(main())
