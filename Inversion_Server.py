# -*- coding: utf-8 -*-
"""
Inversion_Server.py – v0.15.7

Headless collector / archive repair tool.

Wichtige Testoptionen:
  --selftest       Netzwerkfreier PASS/FAIL-Selbsttest der aktiven Ortskonfiguration.
  --show-config    Zeigt die tatsächlich aktive Orts-/Archivkonfiguration.
  --verify-archive Prüft vorhandene Manifeste des aktiven Orts auf Lesbarkeit
                   und Ortszuordnung, ohne Daten zu verändern.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from inversion.config import (
    TIMEZONE, LOCATION_NAME, LOCATION_SLUG, ARCHIVE_CONFIG, VERSION,
    PROJECT_DIR, ARCHIVE_DIR, LOCATIONS_FILE, ARCHIVE_CONFIG_FILE,
    ACTIVE_LOCATION_KEY, LAT, LON, LOCATION_ELEVATION_M,
    DWD_MAX_STATION_DISTANCE_KM, _LOCATIONS
)
from inversion.archive import (load_bundle,missing_sources,missing_optional_sources,
                               completion_sources,optional_sources,kit_archive_coverage,save_bundle,day_dir)
from inversion.archive_service import update_day


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
    allowed={"dwd","profile","sonde","kit_mast","icon_d2"}
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
    check(
        bool(ARCHIVE_CONFIG.get("github_actions",{}).get(
            "kit_continuous_archive",True
        )),
        "kontinuierliche KIT-Archivierung aktiviert",
        "bei jedem Scheduled-Lauf; unabhängig von core-complete/Retry"
    )

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
    """Sichert KIT bei jedem Scheduled-Lauf kumulativ, ohne Retry-Zähler/-Uhr."""
    cfg=ARCHIVE_CONFIG.get("github_actions",{})
    if not bool(cfg.get("kit_continuous_archive",True)):
        log("KIT-Archiv: kontinuierliche Sicherung deaktiviert.")
        return False
    day=now.date()
    log(
        f"KIT-ARCHIV: kontinuierlicher Abruf {day}; "
        "kumulativer Merge, kein Einfluss auf core-complete/Retry."
    )
    b,m,origin=update_day(
        day,log_cb=log,only_missing=False,
        requested_sources={"kit_mast"},
        reason="KIT_CONTINUOUS_ARCHIVE",
        increment_attempt=False,
        affects_retry_clock=False
    )
    cov=kit_archive_coverage(b,day) if b is not None else {"status":"NO_DATA"}
    log(
        "KIT-ARCHIV ERGEBNIS | "
        f"status={cov.get('status')} | "
        f"profile={cov.get('profile_count')}/{cov.get('expected_profiles')} | "
        f"coverage={cov.get('coverage_percent')}% | "
        f"cadence={cov.get('cadence_minutes')} min | "
        f"largest_gap={cov.get('largest_gap_minutes')} min"
    )
    return True


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

    scheduled_kit_archive(now)

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

    day=(
        parse_date(args.date)
        if args.date
        else datetime.now(ZoneInfo(TIMEZONE)).date()
    )
    return run_one(day,args.force)


if __name__=="__main__":
    raise SystemExit(main())
