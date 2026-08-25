# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib,os,sys
from .location_service import set_active_location

_RELOAD_ORDER=(
    "inversion.config","inversion.archive","inversion.weather_sources",
    "inversion.inversion_engine","inversion.radiosonde","inversion.kit_mast",
    "inversion.kit_inversion","inversion.icon_d2_source","inversion.pipeline",
    "inversion.archive_service","inversion.remote_archive",
)

def activate_runtime_location(key:str):
    set_active_location(key)
    os.environ["INVERSION_LOCATION"]=key
    mods={}
    for name in _RELOAD_ORDER:
        mods[name]=importlib.reload(sys.modules[name]) if name in sys.modules else importlib.import_module(name)
    c=mods["inversion.config"]
    if c.ACTIVE_LOCATION_KEY!=key:
        raise RuntimeError(f"Ortswechsel fehlgeschlagen: {key!r} != {c.ACTIVE_LOCATION_KEY!r}")
    return {
        "config":c,"archive":mods["inversion.archive"],
        "weather_sources":mods["inversion.weather_sources"],
        "inversion_engine":mods["inversion.inversion_engine"],
        "pipeline":mods["inversion.pipeline"],
        "archive_service":mods["inversion.archive_service"],
        "remote_archive":mods["inversion.remote_archive"],
    }
