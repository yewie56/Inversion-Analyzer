# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from pathlib import Path

import requests

from .config import (
    LOCATIONS_FILE, GEOCODING_URL, REQUEST_TIMEOUT, _slug
)

USER_AGENT="Inversion-Analyzer/0.15.8"


class LocationError(RuntimeError):
    pass


def _load():
    try:
        data=json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data,dict):
            raise ValueError("locations.json root must be object")
        if not isinstance(data.get("locations"),dict):
            data["locations"]={}
        return data
    except FileNotFoundError:
        return {"active":"", "locations":{}}
    except Exception as exc:
        raise LocationError(f"locations.json konnte nicht gelesen werden: {exc}") from exc


def _save(data):
    LOCATIONS_FILE.write_text(
        json.dumps(data,indent=2,ensure_ascii=False),
        encoding="utf-8"
    )


def list_locations():
    data=_load()
    return data.get("active",""), data.get("locations",{})


def geocode_location_name(name, country_code="DE"):
    query=str(name or "").strip()
    if len(query) < 2:
        raise LocationError("Bitte mindestens zwei Zeichen als Ortsnamen eingeben.")

    params={
        "name":query,
        "count":10,
        "format":"json",
        "language":"de",
    }
    if country_code:
        params["countryCode"]=country_code

    try:
        r=requests.get(
            GEOCODING_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent":USER_AGENT}
        )
        r.raise_for_status()
        payload=r.json()
    except Exception as exc:
        raise LocationError(f"Ortsauflösung fehlgeschlagen: {exc}") from exc

    results=payload.get("results") if isinstance(payload,dict) else None
    if not results:
        raise LocationError(f"Kein Ort für „{query}“ gefunden.")

    qnorm=query.casefold()

    def score(item):
        name_score=0 if str(item.get("name","")).casefold()==qnorm else 1
        country_score=0 if (not country_code or item.get("country_code")==country_code) else 1
        feature=item.get("feature_code","")
        feature_score=0 if str(feature).startswith("PPL") else 1
        population=-(int(item.get("population") or 0))
        return (name_score,country_score,feature_score,population)

    results=sorted(results,key=score)
    best=results[0]

    for required in ("name","latitude","longitude"):
        if best.get(required) is None:
            raise LocationError(
                f"Geocoding-Ergebnis ist unvollständig: Feld {required} fehlt."
            )

    cc=str(best.get("country_code") or country_code or "").upper()
    is_de=(cc=="DE")
    return {
        "name":str(best["name"]),
        "latitude":float(best["latitude"]),
        "longitude":float(best["longitude"]),
        "timezone":str(best.get("timezone") or "Europe/Berlin"),
        "elevation_m":float(best.get("elevation") or 0.0),
        "country_code":cc,
        "country":str(best.get("country") or ""),
        "admin1":str(best.get("admin1") or ""),
        "admin2":str(best.get("admin2") or ""),
        "geocoding_id":best.get("id"),
        "geocoding_source":"Open-Meteo / GeoNames",
        "dwd_max_distance_km":50.0,
        "dwd_enabled":is_de,
        "radiosonde_enabled":is_de,
        "radiosonde_wmo":"10618" if is_de else None,
        "kit_mast_enabled":is_de,
        "icon_d2_enabled":is_de,
        "completion_sources":["dwd","profile","icon_d2"] if is_de else ["profile"],
        "optional_sources":["sonde","kit_mast"] if is_de else [],
    }


def add_and_activate_location(name, country_code="DE"):
    resolved=geocode_location_name(name,country_code=country_code)
    data=_load()
    locations=data.setdefault("locations",{})

    base_key=resolved["name"].strip() or _slug(name)
    key=base_key
    if key in locations:
        old=locations[key]
        # Same place: update its geocoded coordinate metadata.
        same=(
            abs(float(old.get("latitude",999))-resolved["latitude"]) < 0.05
            and abs(float(old.get("longitude",999))-resolved["longitude"]) < 0.05
        )
        if not same:
            suffix=resolved.get("admin1") or resolved.get("country_code") or "2"
            key=f"{base_key}_{_slug(suffix)}"

    # Preserve source-specific user options for existing location.
    if key in locations:
        existing=locations[key]
        for option in (
            "dwd_enabled","kit_mast_enabled","radiosonde_enabled",
            "radiosonde_wmo","icon_d2_enabled","dwd_max_distance_km",
            "completion_sources","optional_sources"
        ):
            if option in existing:
                resolved[option]=existing[option]

    locations[key]=resolved
    data["active"]=key
    _save(data)
    return key,resolved


def set_active_location(key):
    data=_load()
    if key not in data.get("locations",{}):
        raise LocationError(f"Unbekannter Ort: {key}")
    data["active"]=key
    _save(data)
    return data["locations"][key]
