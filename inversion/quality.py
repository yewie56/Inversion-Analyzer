# -*- coding: utf-8 -*-
from .models import DataBundle
from .config import DWD_ENABLED


def determine_quality(bundle: DataBundle):
    dwd = bundle.source_status.get("dwd")
    aemet = bundle.source_status.get("aemet")
    profile = bundle.source_status.get("profile")

    if profile is None or not profile.is_ok():
        bundle.quality_class = "X"
        bundle.quality_text = "Keine belastbare Berechnung möglich: Vertikalprofil fehlt"
        return bundle

    if dwd is not None and dwd.is_ok():
        bundle.quality_class = "B"
        bundle.quality_text = "DWD-Bodenmessung + vertikales Modell-/Archivprofil"
    elif aemet is not None and aemet.is_ok():
        bundle.quality_class = "B"
        bundle.quality_text = "AEMET-Bodenmessung + vertikales Modell-/Archivprofil"
    elif dwd is not None and dwd.state == "STALE":
        bundle.quality_class = "C"
        bundle.quality_text = "Vertikalprofil + veraltete DWD-Bodenmessung"
    else:
        bundle.quality_class = "C"
        if DWD_ENABLED:
            bundle.quality_text = "Vertikalprofil vorhanden; DWD-Bodenmessung für gewählten Tag fehlt"
        else:
            if aemet is not None and aemet.state == "NO_API_KEY":
                bundle.quality_text = "Vertikalprofil vorhanden; AEMET vorbereitet, aber AEMET_API_KEY ist nicht gesetzt"
            else:
                bundle.quality_text = "Vertikalprofil vorhanden; lokale Bodenmessung für diesen Tag fehlt"

    return bundle
