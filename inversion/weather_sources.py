# -*- coding: utf-8 -*-
from __future__ import annotations
import io, math, re, zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests
from .config import (
    LAT, LON, TIMEZONE, REQUEST_TIMEOUT, DWD_MAX_STATION_DISTANCE_KM,
    DWD_STATION_LIST_URL, DWD_NOW_BASE,
    OPEN_METEO_URL, OPEN_METEO_ARCHIVE_URL, OPEN_METEO_HISTORICAL_FORECAST_URL,
    PRESSURE_LEVELS, DWD_RADIOSONDE_TRAJ_URL,
    IDAR_OBERSTEIN_WMO,
)
from .models import SourceStatus
from .logger import LOGGER

class DataSourceError(RuntimeError):
    def __init__(self, source, category, message, detail=""):
        super().__init__(message)
        self.source = source
        self.category = category
        self.detail = detail

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))

def _request(url, *, params=None, source="Internet"):
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT,
                         headers={"User-Agent": "Inversion-Analyzer/0.15.0"})
    except requests.Timeout as exc:
        raise DataSourceError(source, "TIMEOUT", f"{source}: Zeitueberschreitung", str(exc))
    except requests.ConnectionError as exc:
        raise DataSourceError(source, "NETWORK", f"{source}: Netzwerk-/Verbindungsfehler", str(exc))
    except requests.RequestException as exc:
        raise DataSourceError(source, "REQUEST", f"{source}: HTTP-Abruffehler", str(exc))
    if r.status_code != 200:
        raise DataSourceError(source, "HTTP", f"{source}: HTTP-Fehler {r.status_code}", f"URL: {r.url}")
    if not r.content:
        raise DataSourceError(source, "EMPTY", f"{source}: Leere Antwort")
    return r

def parse_dwd_station_list(text):
    rows=[]
    for line in text.splitlines():
        m=re.match(r"\s*(\d+)\s+(\d{8})\s+(\d{8})\s+(-?\d+)\s+([0-9.]+)\s+([0-9.]+)\s+(.+?)\s{2,}(.+?)\s*$", line)
        if not m: continue
        sid,von,bis,hoehe,lat,lon,name,land=m.groups()
        rows.append(dict(station_id=int(sid),von=von,bis=bis,hoehe_m=float(hoehe),lat=float(lat),lon=float(lon),name=name.strip(),land=land.strip()))
    return pd.DataFrame(rows)

def parse_dwd_zip(zip_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names=[n for n in zf.namelist() if n.lower().endswith('.txt')]
            preferred=[n for n in names if 'produkt_zehn_min_tu' in n.lower()]
            if preferred: names=preferred
            if not names:
                raise DataSourceError("DWD-Bodentemperatur","FORMAT","DWD-ZIP enthaelt keine Textdatendatei")
            raw=zf.read(names[0])
    except zipfile.BadZipFile as exc:
        raise DataSourceError("DWD-Bodentemperatur","FORMAT","DWD-Antwort ist keine gueltige ZIP-Datei",str(exc))
    text=raw.decode('latin-1',errors='replace')
    try:
        df=pd.read_csv(io.StringIO(text),sep=';',skipinitialspace=True)
    except Exception as exc:
        raise DataSourceError("DWD-Bodentemperatur","PARSING","DWD-Tabelle konnte nicht gelesen werden",str(exc))
    df.columns=[c.strip() for c in df.columns]
    if 'MESS_DATUM' not in df.columns:
        raise DataSourceError("DWD-Bodentemperatur","FORMAT","Erwartetes Feld MESS_DATUM fehlt",f"Felder: {list(df.columns)}")
    temp_col=next((c for c in ('TT_10','TT_TU','TT') if c in df.columns),None)
    if temp_col is None:
        raise DataSourceError("DWD-Bodentemperatur","FORMAT","Keine erwartete Temperaturspalte gefunden",f"Felder: {list(df.columns)}")
    df['time_utc']=pd.to_datetime(df['MESS_DATUM'].astype(str).str.strip(),format='%Y%m%d%H%M',utc=True,errors='coerce')
    df['temperature_obs']=pd.to_numeric(df[temp_col],errors='coerce')
    df.loc[(df['temperature_obs']<-60)|(df['temperature_obs']>60),'temperature_obs']=np.nan
    df=df.dropna(subset=['time_utc','temperature_obs'])
    df['time']=df['time_utc'].dt.tz_convert(TIMEZONE)
    return df[['time','temperature_obs']].sort_values('time')


def _time_series_completeness(df, selected_date=None, interval_minutes=10):
    result = {
        "expected_rows": None,
        "rows": 0,
        "coverage_percent": None,
        "first_timestamp": None,
        "last_timestamp": None,
        "largest_gap_minutes": None,
        "missing_expected": None,
        "leading_gap_minutes": None,
        "trailing_gap_minutes": None,
        "internal_series_regular": None,
    }
    if df is None or df.empty or "time" not in df.columns:
        return result

    times = df["time"].dropna().sort_values().drop_duplicates()
    result["rows"] = int(len(times))
    if len(times):
        result["first_timestamp"] = times.iloc[0].isoformat()
        result["last_timestamp"] = times.iloc[-1].isoformat()
    if len(times) >= 2:
        gaps = times.diff().dropna().dt.total_seconds() / 60.0
        if len(gaps):
            result["largest_gap_minutes"] = float(gaps.max())

    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    if selected_date is not None and selected_date < today:
        expected = int(24 * 60 / interval_minutes)
    elif selected_date is not None and selected_date == today:
        now = datetime.now(ZoneInfo(TIMEZONE))
        elapsed = now.hour * 60 + now.minute
        expected = max(1, int(elapsed // interval_minutes) + 1)
    else:
        expected = None

    if expected:
        result["expected_rows"] = expected
        result["coverage_percent"] = min(100.0, 100.0 * len(times) / expected)
        result["missing_expected"] = max(0, expected - len(times))

        if selected_date is not None and len(times):
            day_start = pd.Timestamp(selected_date, tz=TIMEZONE)
            day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(minutes=interval_minutes)

            first = times.iloc[0]
            last = times.iloc[-1]

            result["leading_gap_minutes"] = max(
                0.0, (first - day_start).total_seconds() / 60.0
            )
            result["trailing_gap_minutes"] = max(
                0.0, (day_end - last).total_seconds() / 60.0
            )

            largest = result["largest_gap_minutes"]
            result["internal_series_regular"] = (
                largest is None or largest <= interval_minutes + 0.1
            )
    return result

def fetch_dwd_temperature(selected_date=None, log_cb=None):
    source='DWD-Bodentemperatur'
    status=SourceStatus(name=source,last_attempt=datetime.now(ZoneInfo(TIMEZONE)))
    def log(msg):
        LOGGER.info(msg)
        if log_cb: log_cb(msg)
    try:
        log('DWD: Stationsliste abrufen ...')
        r=_request(DWD_STATION_LIST_URL,source='DWD-Stationsliste')
        stations=parse_dwd_station_list(r.content.decode('latin-1',errors='replace'))
        if stations.empty:
            raise DataSourceError(source,'PARSING','DWD-Stationsliste konnte nicht interpretiert werden','Moeglicherweise hat sich das Dateiformat geaendert.')
        stations['dist_km']=stations.apply(
            lambda row:haversine_km(LAT,LON,row['lat'],row['lon']),axis=1
        )
        stations=stations.sort_values('dist_km')

        nearest=stations.iloc[0].to_dict() if not stations.empty else None
        local_stations=stations[
            stations['dist_km'] <= DWD_MAX_STATION_DISTANCE_KM
        ].copy()

        if local_stations.empty:
            status.state='NO_NEARBY_STATION'
            if nearest:
                status.message=(
                    f"Keine geeignete DWD-Bodenstation innerhalb "
                    f"{DWD_MAX_STATION_DISTANCE_KM:.0f} km"
                )
                status.detail=(
                    f"Nächstgelegene DWD-Station: "
                    f"{int(nearest['station_id']):05d} {nearest['name']} "
                    f"({nearest['dist_km']:.1f} km). "
                    "Sie wird NICHT stillschweigend als lokale Bodenmessung "
                    "verwendet. Das ortsbezogene Modellprofil bleibt nutzbar; "
                    "die Qualitätsklasse wird entsprechend reduziert."
                )
                log(
                    f"DWD: keine lokale Station <= "
                    f"{DWD_MAX_STATION_DISTANCE_KM:.0f} km; nächstgelegen "
                    f"{int(nearest['station_id']):05d} {nearest['name']} "
                    f"({nearest['dist_km']:.1f} km) – nicht verwendet."
                )
                return nearest,None,status
            status.message='Keine DWD-Bodenstation gefunden'
            status.detail='Stationsliste enthält keine auswertbare Station.'
            return None,None,status

        last_error=None
        for _,st in local_stations.head(30).iterrows():
            sid=int(st['station_id'])
            try:
                rr=_request(f"{DWD_NOW_BASE}10minutenwerte_TU_{sid:05d}_now.zip",source=source)
                data=parse_dwd_zip(rr.content)
                if data.empty:
                    raise DataSourceError(source,'EMPTY','DWD-Datendatei enthaelt keine gueltigen Messwerte')

                # Fuer ein ausgewaehltes Datum nur Messwerte genau dieses Tages verwenden.
                if selected_date is not None:
                    data_day=data[data['time'].dt.date == selected_date].copy()
                    if data_day.empty:
                        status.state='NO_DATA_DATE'
                        status.message=f'Keine DWD-Bodenmesswerte fuer {selected_date} im NOW-Datensatz'
                        status.detail=(
                            'Die Station ist erreichbar, aber der aktuelle NOW-Datensatz enthaelt '
                            'den ausgewaehlten Tag nicht mehr. Es werden keine fremden Tageswerte verwendet.'
                        )
                        status.rows=0
                        return st.to_dict(),None,status
                    data=data_day

                today=datetime.now(ZoneInfo(TIMEZONE)).date()
                if selected_date is not None and selected_date < today:
                    status.state='OK'
                    status.message=f'Messdaten fuer {selected_date} verfuegbar'
                    status.data_age_minutes=None
                    age_text='historischer Tag'
                else:
                    age_min=(pd.Timestamp.now(tz=TIMEZONE)-data['time'].max()).total_seconds()/60.0
                    status.state='OK' if age_min<=180 else 'STALE'
                    status.message='Messdaten verfuegbar' if status.state=='OK' else f'Messdaten veraltet ({age_min:.0f} min)'
                    status.data_age_minutes=age_min
                    age_text=f'Alter {age_min:.0f} min'

                completeness=_time_series_completeness(data, selected_date, 10)
                status.last_success=datetime.now(ZoneInfo(TIMEZONE))
                status.rows=len(data)
                status.expected_rows=completeness["expected_rows"]
                status.coverage_percent=completeness["coverage_percent"]
                status.first_timestamp=completeness["first_timestamp"]
                status.last_timestamp=completeness["last_timestamp"]
                status.largest_gap_minutes=completeness["largest_gap_minutes"]

                coverage_text=""
                if completeness["expected_rows"]:
                    coverage_text=(
                        f", Abdeckung {len(data)}/{completeness['expected_rows']} "
                        f"= {completeness['coverage_percent']:.1f}%"
                    )
                    gap_text=(
                        f"{completeness['largest_gap_minutes']:.0f} min"
                        if completeness["largest_gap_minutes"] is not None else "–"
                    )
                    lead=completeness.get("leading_gap_minutes")
                    trail=completeness.get("trailing_gap_minutes")
                    edge_text=""
                    if lead and lead > 0:
                        edge_text+=f" Tagesanfang fehlt {lead:.0f} min."
                    if trail and trail > 0:
                        edge_text+=f" Tagesende fehlt {trail:.0f} min."
                    if completeness.get("internal_series_regular") and (lead or trail):
                        edge_text+=" Vorhandener Abschnitt intern vollständig/regelmäßig."

                    status.detail=(
                        f"Tagesabdeckung {len(data)}/{completeness['expected_rows']} "
                        f"({completeness['coverage_percent']:.1f}%), "
                        f"fehlend {completeness['missing_expected']}. "
                        f"Erster Wert {completeness['first_timestamp']}; "
                        f"letzter Wert {completeness['last_timestamp']}; "
                        f"größte Zeitlücke {gap_text}."
                        f"{edge_text}"
                    )

                log(
                    f"DWD: Station {sid:05d} {st['name']} ({st['dist_km']:.1f} km), "
                    f"{len(data)} Werte, {age_text}{coverage_text}"
                )
                if completeness["largest_gap_minutes"] is not None:
                    log(
                        f"DWD-Vollständigkeit: erster={completeness['first_timestamp']}, "
                        f"letzter={completeness['last_timestamp']}, "
                        f"größte Lücke={completeness['largest_gap_minutes']:.0f} min"
                    )
                return st.to_dict(),data,status
            except DataSourceError as exc:
                last_error=exc
                LOGGER.warning('DWD-Kandidat %05d fehlgeschlagen: %s',sid,exc)
        raise last_error or DataSourceError(source,'NO_DATA','Keine geeignete DWD-Station erreichbar')
    except DataSourceError as exc:
        status.state=exc.category; status.message=str(exc); status.detail=exc.detail
        LOGGER.exception('DWD-Abruf fehlgeschlagen')
        return None,None,status

def fetch_open_meteo_profile(selected_date=None, log_cb=None):
    source = "Vertikalprofil"
    status = SourceStatus(name=source, last_attempt=datetime.now(ZoneInfo(TIMEZONE)))

    def log(msg):
        LOGGER.info(msg)
        if log_cb:
            log_cb(msg)

    if selected_date is None:
        selected_date = datetime.now(ZoneInfo(TIMEZONE)).date()

    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    is_today = selected_date == today

    hourly_vars = [
        "temperature_2m", "surface_pressure",
        "wind_speed_10m", "wind_direction_10m", "cloud_cover",
    ]
    for p in PRESSURE_LEVELS:
        hourly_vars += [
            f"temperature_{p}hPa",
            f"geopotential_height_{p}hPa",
            f"wind_speed_{p}hPa",
            f"wind_direction_{p}hPa",
        ]

    if is_today:
        url = OPEN_METEO_URL
        params = {
            "latitude": LAT,
            "longitude": LON,
            "hourly": ",".join(hourly_vars),
            "timezone": TIMEZONE,
            "forecast_days": 1,
            "wind_speed_unit": "ms",
        }
        mode_text = "aktuelles Modellprofil"
    else:
        url = OPEN_METEO_HISTORICAL_FORECAST_URL
        ds = selected_date.isoformat()
        params = {
            "latitude": LAT,
            "longitude": LON,
            "hourly": ",".join(hourly_vars),
            "timezone": TIMEZONE,
            "start_date": ds,
            "end_date": ds,
            "wind_speed_unit": "ms",
        }
        mode_text = "historisches Forecast-Archivprofil mit Druckflächen"

    try:
        log(f"Vertikalprofil {selected_date}: {mode_text} abrufen ...")
        r = _request(url, params=params, source=source)
        try:
            data = r.json()
        except ValueError as exc:
            raise DataSourceError(source, "PARSING", "Vertikalprofil: Antwort ist kein gültiges JSON", str(exc))

        if "hourly" not in data:
            reason = data.get("reason", "") if isinstance(data, dict) else ""
            raise DataSourceError(
                source, "FORMAT",
                "Vertikalprofil: erwarteter Bereich 'hourly' fehlt",
                reason or "Möglicherweise hat sich die API-Struktur geändert."
            )

        df = pd.DataFrame(data["hourly"])
        required = {"time", "temperature_2m"}
        missing = required - set(df.columns)
        if missing:
            raise DataSourceError(source, "FORMAT", f"Vertikalprofil: Pflichtfelder fehlen: {sorted(missing)}")

        if len(df) < 12:
            raise DataSourceError(source, "INCOMPLETE", f"Vertikalprofil: ungewöhnlich wenige Stundenwerte ({len(df)})")

        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        if df["time"].isna().all():
            raise DataSourceError(source, "PARSING", "Vertikalprofil: Zeitstempel konnten nicht gelesen werden")
        df["time"] = df["time"].dt.tz_localize(TIMEZONE)

        # v0.5.1: Vertikalprofil MUSS tatsächlich Druckflächendaten enthalten.
        # 24 Zeitstempel allein genügen nicht.
        pressure_pairs = []
        for p in PRESSURE_LEVELS:
            tc = f"temperature_{p}hPa"
            zc = f"geopotential_height_{p}hPa"
            if tc in df.columns and zc in df.columns:
                valid = df[tc].notna() & df[zc].notna()
                pressure_pairs.append((p, int(valid.sum())))

        usable_pairs = [(p, n) for p, n in pressure_pairs if n > 0]
        if not usable_pairs:
            raise DataSourceError(
                source,
                "INCOMPLETE",
                "Vertikalprofil enthält keine auswertbaren Druckflächendaten",
                "Zeitachse ist vorhanden, aber Temperatur/Geopotentialhöhe der Druckflächen fehlen. "
                "Eine Null-Inversionskurve wäre in diesem Fall falsch."
            )

        # Mindestens eine Druckfläche muss für einen großen Teil des Tages verfügbar sein.
        best_count = max(n for _, n in usable_pairs)
        if best_count < 12:
            raise DataSourceError(
                source,
                "INCOMPLETE",
                f"Vertikalprofil nur unvollständig: beste Druckfläche hat {best_count}/24 gültige Werte",
                f"Gültige Druckflächen: {usable_pairs}"
            )

        status.state = "OK"
        status.message = f"{mode_text} verfügbar"
        status.last_success = datetime.now(ZoneInfo(TIMEZONE))
        status.rows = len(df)
        status.detail = "Quelle wird für die Inversionsberechnung verwendet."
        log(f"Vertikalprofil {selected_date}: {len(df)} Stundenwerte verfügbar")
        return df, status

    except DataSourceError as exc:
        status.state = exc.category
        status.message = str(exc)
        status.detail = exc.detail
        LOGGER.exception("Vertikalprofil-Abruf fehlgeschlagen")
        return None, status


def fetch_idar_oberstein_availability(selected_date=None, log_cb=None):
    """
    Prüft die offizielle DWD-Trajektorienseite auf Radiosondenflüge der
    Station Idar-Oberstein (WMO 10618) am gewählten Datum.

    v0.4 verwendet die Sonde NOCH NICHT numerisch im Inversionsindex.
    Sie wird als unabhängiger Mess-/Plausibilisierungskanal protokolliert.
    """
    source = "Radiosonde Idar-Oberstein 10618"
    status = SourceStatus(name=source, last_attempt=datetime.now(ZoneInfo(TIMEZONE)))

    def log(msg):
        LOGGER.info(msg)
        if log_cb:
            log_cb(msg)

    if selected_date is None:
        selected_date = datetime.now(ZoneInfo(TIMEZONE)).date()

    try:
        log(f"Radiosonde Idar-Oberstein: Verfügbarkeit für {selected_date} prüfen ...")
        r = _request(DWD_RADIOSONDE_TRAJ_URL, source=source)
        html = r.content.decode("utf-8", errors="replace")
        date_token = selected_date.strftime("%Y%m%d")

        pattern = re.compile(
            rf'Sondenflug_({date_token}\d{{6}})_{re.escape(IDAR_OBERSTEIN_WMO)}_[^"<> ]+?\.kmz'
        )
        flights = sorted(set(pattern.findall(html)))

        if not flights:
            status.state = "NO_DATA_DATE"
            status.message = f"Keine veröffentlichte Sonde 10618 für {selected_date} im aktuellen Trajektorienindex"
            status.rows = 0
            status.detail = (
                "Die DWD-Trajektorienseite ist ein aktuelles Verzeichnis und kein vollständiges Langzeitarchiv. "
                "Ein fehlender Treffer bedeutet deshalb nicht zwingend, dass an diesem historischen Tag keine Sonde gestartet wurde."
            )
            return [], status

        status.state = "OK"
        status.message = f"{len(flights)} Sondenflug/-flüge gefunden"
        status.rows = len(flights)
        status.last_success = datetime.now(ZoneInfo(TIMEZONE))
        status.detail = (
            "Verfügbarkeit verifiziert; v0.4 nutzt die Radiosonde noch nicht numerisch im Index."
        )
        log(f"Radiosonde Idar-Oberstein: {len(flights)} Flug/Flüge gefunden: {', '.join(flights)}")
        return flights, status

    except DataSourceError as exc:
        status.state = exc.category
        status.message = str(exc)
        status.detail = exc.detail
        LOGGER.exception("Radiosonden-Prüfung fehlgeschlagen")
        return [], status
