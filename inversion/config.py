# -*- coding: utf-8 -*-
from pathlib import Path
import json, os, re

APP_NAME = "Inversionskurve"
VERSION = "0.15.7"
PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_DIR / "output_inversion"
LOG_DIR = PROJECT_DIR / "logs"
SETTINGS_FILE = PROJECT_DIR / "settings.json"
LOCATIONS_FILE = PROJECT_DIR / "locations.json"
ARCHIVE_CONFIG_FILE = PROJECT_DIR / "archive_config.json"
REQUEST_TIMEOUT = 30

def _slug(text):
    s=re.sub(r"[^A-Za-z0-9._-]+","_",str(text).strip())
    return s.strip("_") or "location"

def _load_locations():
    default={
        "active":"Viernheim",
        "locations":{
            "Viernheim":{
                "name":"Viernheim",
                "latitude":49.5412,
                "longitude":8.5785,
                "timezone":"Europe/Berlin",
                "elevation_m":100.0,
                "country_code":"DE",
                "admin1":"Hessen",
                "geocoding_source":"legacy/manual",
                "dwd_max_distance_km":50.0,
                "radiosonde_wmo":"10618",
                "kit_mast_enabled":True
            },
            "Bremerhaven":{
                "name":"Bremerhaven",
                "latitude":53.545833,
                "longitude":8.58,
                "timezone":"Europe/Berlin",
                "elevation_m":2.6,
                "country_code":"DE",
                "admin1":"Bremen",
                "geocoding_source":"Bremerhaven city reference",
                "dwd_max_distance_km":50.0,
                "radiosonde_wmo":"10618",
                "kit_mast_enabled":True
            }
        }
    }
    try:
        data=json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data,dict) or not isinstance(data.get("locations"),dict):
            return default
        return data
    except Exception:
        return default

_LOCATIONS=_load_locations()
_ENV_LOCATION=os.environ.get("INVERSION_LOCATION")
if _ENV_LOCATION and _ENV_LOCATION not in _LOCATIONS.get("locations",{}):
    available=", ".join(sorted(_LOCATIONS.get("locations",{}).keys()))
    raise RuntimeError(
        f"INVERSION_LOCATION='{_ENV_LOCATION}' ist nicht in locations.json vorhanden. "
        f"Verfügbar: {available}"
    )

ACTIVE_LOCATION_KEY=_ENV_LOCATION or _LOCATIONS.get("active","Viernheim")
if ACTIVE_LOCATION_KEY not in _LOCATIONS.get("locations",{}):
    ACTIVE_LOCATION_KEY=next(iter(_LOCATIONS["locations"].keys()))
LOCATION=_LOCATIONS["locations"][ACTIVE_LOCATION_KEY]
LOCATION_NAME=str(LOCATION.get("name",ACTIVE_LOCATION_KEY))
LOCATION_SLUG=_slug(LOCATION_NAME)
LAT=float(LOCATION.get("latitude",49.5412))
LON=float(LOCATION.get("longitude",8.5785))
TIMEZONE=str(LOCATION.get("timezone","Europe/Berlin"))
LOCATION_ELEVATION_M=float(LOCATION.get("elevation_m",100.0))
DWD_MAX_STATION_DISTANCE_KM=float(LOCATION.get("dwd_max_distance_km",50.0))
LOCATION_COUNTRY_CODE=str(LOCATION.get("country_code","DE"))
LOCATION_ADMIN1=str(LOCATION.get("admin1",""))
KIT_MAST_ENABLED=bool(LOCATION.get("kit_mast_enabled",True))
GEOCODING_URL="https://geocoding-api.open-meteo.com/v1/search"

def load_archive_config():
    default={
        "archive_dir":"archive",
        "auto_fetch_missing":True,
        "remote_archive":{"enabled":False,"provider":"github_raw","owner":"","repository":"","branch":"main","archive_path":"archive"},
        "github_actions":{
            "daily_fetch_local_hour":22,
            "retry_delay_hours":3,
            "max_retries":5,
            "retry_only_missing":True,
            "completion_sources":["dwd","profile","icon_d2"],
            "optional_sources":["sonde","kit_mast"],
            "retry_optional_sources":False,
            "kit_continuous_archive":True,
            "kit_coverage_min_profiles_for_cadence":3,
            "kit_complete_gap_factor":1.5
        }
    }
    try:
        data=json.loads(ARCHIVE_CONFIG_FILE.read_text(encoding="utf-8"))
        for k,v in default.items():
            if k not in data: data[k]=v

        # v0.15.6: alte Konfigurationen mit "required_sources" werden
        # kompatibel auf Kern- und optionale Quellen abgebildet.
        ga=data.setdefault("github_actions",{})
        dga=default["github_actions"]
        legacy=ga.get("required_sources")
        if "completion_sources" not in ga:
            if isinstance(legacy,list):
                ga["completion_sources"]=[
                    x for x in legacy if x not in ("sonde","kit_mast")
                ] or list(dga["completion_sources"])
            else:
                ga["completion_sources"]=list(dga["completion_sources"])
        if "optional_sources" not in ga:
            ga["optional_sources"]=list(dga["optional_sources"])
        if "retry_optional_sources" not in ga:
            ga["retry_optional_sources"]=False
        if "kit_continuous_archive" not in ga:
            ga["kit_continuous_archive"]=True
        if "kit_coverage_min_profiles_for_cadence" not in ga:
            ga["kit_coverage_min_profiles_for_cadence"]=3
        if "kit_complete_gap_factor" not in ga:
            ga["kit_complete_gap_factor"]=1.5
        return data
    except Exception:
        return default

ARCHIVE_CONFIG=load_archive_config()
ARCHIVE_DIR=PROJECT_DIR / str(ARCHIVE_CONFIG.get("archive_dir","archive"))

DWD_STATION_LIST_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
    "climate/10_minutes/air_temperature/now/"
    "zehn_now_tu_Beschreibung_Stationen.txt"
)
DWD_NOW_BASE = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
    "climate/10_minutes/air_temperature/now/"
)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PRESSURE_LEVELS = [1000, 975, 950, 925, 900, 850]
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_HISTORICAL_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

DWD_RADIOSONDE_TRAJ_URL = "https://opendata.dwd.de/weather/weather_reports/radiosonde/trajectories/"
IDAR_OBERSTEIN_WMO = str(LOCATION.get("radiosonde_wmo","10618"))

CACHE_DIR = PROJECT_DIR / "cache"

KIT_MAST_INFO_URL = "https://www.imktro.kit.edu/13440.php"
KIT_MAST_DASHBOARD_URL = "https://tsm.atmohub.kit.edu/wm/plotserver/all-plots-weekly"
KIT_MAST_PROFILE_URL = "https://tsm.atmohub.kit.edu/wm/plotserver/profile-plots"
KIT_MAST_MONTHLY_URL = "https://tsm.atmohub.kit.edu/wm/plotserver/monthly"
KIT_MAST_LAT = 49.0925
KIT_MAST_LON = 8.4258333333
KIT_MAST_ALT_M = 110.4
KIT_MAST_TEMP_HEIGHTS_M = [2,10,30,60,100,130,160,200]

OPEN_METEO_ICON_D2_HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
OPEN_METEO_ICON_D2_MODEL = "icon_d2"


# DWD CDC Radiosonden – hochaufgelöste Sekundenwerte.
# Idar-Oberstein ist DWD-Stations-ID 02385; WMO-Kennung 10618.
DWD_RADIOSONDE_STATION_ID = "02385"
DWD_RADIOSONDE_HIGHRES_RECENT_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
    "radiosondes/high_resolution/recent/"
)
DWD_RADIOSONDE_HIGHRES_HIST_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
    "radiosondes/high_resolution/historical/"
)
