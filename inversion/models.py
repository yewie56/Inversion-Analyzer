# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

@dataclass
class SourceStatus:
    name: str
    state: str = "UNKNOWN"
    message: str = "Noch nicht geprueft"
    last_attempt: Optional[datetime] = None
    last_success: Optional[datetime] = None
    http_status: Optional[int] = None
    data_age_minutes: Optional[float] = None
    rows: Optional[int] = None
    detail: str = ""
    expected_rows: Optional[int] = None
    coverage_percent: Optional[float] = None
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    largest_gap_minutes: Optional[float] = None
    def is_ok(self):
        return self.state == "OK"

@dataclass
class DataBundle:
    run_id: str = ""
    station_info: Optional[dict] = None
    dwd_data: Any = None
    profile_data: Any = None
    result_data: Any = None
    sonde_flights: list = field(default_factory=list)
    sonde_profiles: list = field(default_factory=list)
    sonde_profile_data: Any = None
    sonde_metrics: Any = None
    kit_mast_info: dict = field(default_factory=dict)
    kit_mast_data: Any = None
    kit_mast_metrics: Any = None
    icon_d2_data: Any = None
    icon_d2_profile_data: Any = None
    icon_d2_info: dict = field(default_factory=dict)
    source_status: dict = field(default_factory=dict)
    quality_class: str = "X"
    quality_text: str = "Keine belastbare Berechnung moeglich"
