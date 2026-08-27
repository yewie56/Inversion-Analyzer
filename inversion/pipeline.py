# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo
from .models import DataBundle, SourceStatus
from .weather_sources import fetch_dwd_temperature, fetch_open_meteo_profile
from .aemet_source import fetch_aemet_temperature
from .radiosonde import fetch_idar_oberstein_profiles
from .kit_mast import fetch_kit_mast_diagnostics
from .timestamp_validation import selftest_kit_timestamp
from .kit_inversion import extract_kit_temperature_profiles
from .icon_d2_source import fetch_icon_d2_historical
from .inversion_engine import calculate_profile_metrics, merge_surface_observation
from .quality import determine_quality
from .logger import LOGGER
from .config import (TIMEZONE, KIT_MAST_ENABLED, DWD_ENABLED, RADIOSONDE_ENABLED, ICON_D2_ENABLED, AEMET_ENABLED)

ALL_SOURCES={"dwd","aemet","profile","sonde","kit_mast","icon_d2"}

def _not_requested(name):
    return SourceStatus(name=name,state="NOT_REQUESTED",message="In diesem Teillauf nicht angefordert")

def load_data_for_date(selected_date, log_cb=None, only_sources=None):
    wanted=set(only_sources or ALL_SOURCES)
    run_id=datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y%m%d_%H%M%S")
    bundle=DataBundle(run_id=run_id)
    separator="="*72
    def log(msg):
        LOGGER.info(msg)
        if log_cb: log_cb(msg)
    log(separator); log(f"RUN {run_id} | Datum {selected_date} | START"); log(separator)

    if KIT_MAST_ENABLED:
        ts_test=selftest_kit_timestamp()
        log(f"KIT-localtime-Selbsttest: {'PASS' if ts_test['pass'] else 'FAIL'} | "
            f"{ts_test['input_ms']} -> {ts_test['actual']} | erwartet {ts_test['expected']}")

    if "dwd" in wanted and DWD_ENABLED:
        station,dwd,s=fetch_dwd_temperature(selected_date,log_cb)
        bundle.station_info=station; bundle.dwd_data=dwd; bundle.source_status["dwd"]=s
    elif "dwd" in wanted:
        bundle.source_status["dwd"]=SourceStatus(
            name="DWD-Bodentemperatur", state="DISABLED_FOR_LOCATION",
            message="Für diesen Ort deaktiviert"
        )
    else:
        bundle.source_status["dwd"]=_not_requested("DWD-Bodentemperatur")

    if "aemet" in wanted and AEMET_ENABLED:
        station,aemet,s=fetch_aemet_temperature(selected_date,log_cb)
        bundle.aemet_station_info=station
        bundle.aemet_data=aemet
        bundle.source_status["aemet"]=s
    elif "aemet" in wanted:
        bundle.source_status["aemet"]=SourceStatus(
            name="AEMET-Bodenmessung",state="DISABLED_FOR_LOCATION",
            message="Für diesen Ort deaktiviert")
    else:
        bundle.source_status["aemet"]=_not_requested("AEMET-Bodenmessung")

    if "profile" in wanted:
        profile,s=fetch_open_meteo_profile(selected_date,log_cb)
        bundle.profile_data=profile; bundle.source_status["profile"]=s
        if profile is not None and not profile.empty:
            metrics=calculate_profile_metrics(profile)
            if metrics is None or "inversion_index" not in metrics.columns or metrics["inversion_index"].notna().sum()==0:
                bundle.result_data=None
                s.state="INCOMPLETE"; s.message="Keine auswertbare vertikale Temperaturdifferenz"
                s.detail="Es wird ausdrücklich keine Nullkurve dargestellt."
            else:
                surface_obs=bundle.dwd_data
                if (surface_obs is None or getattr(surface_obs,"empty",True)) and AEMET_ENABLED:
                    surface_obs=bundle.aemet_data
                bundle.result_data=merge_surface_observation(metrics,surface_obs)
    else:
        bundle.source_status["profile"]=_not_requested("Vertikalprofil")

    if "sonde" in wanted and RADIOSONDE_ENABLED:
        raw_profile,metrics,info,s=fetch_idar_oberstein_profiles(selected_date,log_cb)
        bundle.sonde_profile_data=raw_profile
        bundle.sonde_metrics=metrics
        bundle.sonde_profiles=info
        bundle.sonde_flights=[x.get("launch_time","") for x in info]
        bundle.source_status["sonde"]=s
        if log_cb:
            log_cb(f"Radiosonde Status: {s.state} | {s.message}")
            if s.detail:
                log_cb(f"Radiosonde Details: {s.detail}")
    elif "sonde" in wanted:
        bundle.source_status["sonde"]=SourceStatus(
            name="Radiosonde", state="DISABLED_FOR_LOCATION",
            message="Für diesen Ort deaktiviert"
        )
    else:
        bundle.source_status["sonde"]=_not_requested("Radiosonde")

    if "kit_mast" in wanted and KIT_MAST_ENABLED:
        info,data,s=fetch_kit_mast_diagnostics(selected_date,log_cb,run_id=run_id)
        bundle.kit_mast_info=info; bundle.kit_mast_data=data; bundle.source_status["kit_mast"]=s
        client_sources=(data or {}).get("client_sources",[]) if isinstance(data,dict) else []
        km,ki=extract_kit_temperature_profiles(client_sources,selected_date,log_cb=log_cb)
        bundle.kit_mast_metrics=km; bundle.kit_mast_info["temperature_profile_analysis"]=ki
        if km is not None and not km.empty:
            s.state="KIT_TEMP_OK"
            s.message=f"{len(km)} gemessene Temperaturprofil(e) für {selected_date} ausgewertet"
            s.rows=len(km)
            s.detail=(f"Gemessene KIT-Inversionskurve separat verfügbar. Zeitraum "
                      f"{km['time'].iloc[0]:%H:%M}–{km['time'].iloc[-1]:%H:%M}. "
                      "Nicht mit dem Modellindex vermischt.")
        elif s.state=="BOKEH_CLIENT_DATA":
            s.state="KIT_TEMP_NO_DATE"
            s.message=f"Temperaturdaten erkannt, aber kein KIT-Profil für {selected_date}"
    elif "kit_mast" in wanted:
        bundle.source_status["kit_mast"]=SourceStatus(name="KIT-Mast",state="DISABLED_FOR_LOCATION",
                                                       message="Für diesen Ort deaktiviert")
    else: bundle.source_status["kit_mast"]=_not_requested("KIT-Mast")

    if "icon_d2" in wanted and ICON_D2_ENABLED:
        data,raw_profile,info,s=fetch_icon_d2_historical(selected_date,log_cb=log_cb)
        bundle.icon_d2_data=data
        bundle.icon_d2_profile_data=raw_profile
        bundle.icon_d2_info=info
        bundle.source_status["icon_d2"]=s
    elif "icon_d2" in wanted:
        bundle.source_status["icon_d2"]=SourceStatus(
            name="ICON-D2", state="DISABLED_FOR_LOCATION",
            message="Für diesen Ort deaktiviert"
        )
    else:
        bundle.source_status["icon_d2"]=_not_requested("ICON-D2")

    determine_quality(bundle)
    if bundle.source_status.get("sonde") and bundle.source_status["sonde"].is_ok():
        bundle.quality_text += " | DWD-Radiosonde Idar-Oberstein gemessen separat"
    if bundle.source_status.get("kit_mast") and bundle.source_status["kit_mast"].state=="KIT_TEMP_OK":
        bundle.quality_text += " | KIT-Mast gemessen separat"
    if bundle.source_status.get("icon_d2") and bundle.source_status["icon_d2"].state in ("OK","OK_CORE_RETRY"):
        bundle.quality_text += " | ICON-D2 Historical Forecast separat"

    is_partial=(wanted != ALL_SOURCES)
    if is_partial:
        log(
            f"TEILLAUF-DATENQUALITÄT {bundle.quality_class} (NICHT FINAL): "
            f"{bundle.quality_text}"
        )
        log(
            f"RUN {run_id} | ENDE | Teillauf; finale Qualität erst nach Safe-Merge"
        )
    else:
        log(f"Datenqualität {bundle.quality_class}: {bundle.quality_text}")
        log(f"RUN {run_id} | ENDE | Datenqualität {bundle.quality_class}")
    log(separator)
    return bundle

def load_current_data(log_cb=None):
    return load_data_for_date(datetime.now(ZoneInfo(TIMEZONE)).date(),log_cb)
