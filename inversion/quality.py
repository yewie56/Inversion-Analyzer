# -*- coding: utf-8 -*-
from .models import DataBundle


def determine_quality(bundle: DataBundle):
    dwd = bundle.source_status.get("dwd")
    profile = bundle.source_status.get("profile")

    if profile is None or not profile.is_ok():
        bundle.quality_class = "X"
        bundle.quality_text = "Keine belastbare Berechnung möglich: Vertikalprofil fehlt"
        return bundle

    if dwd is not None and dwd.is_ok():
        bundle.quality_class = "B"
        bundle.quality_text = "DWD-Bodenmessung + vertikales Modell-/Archivprofil"
    elif dwd is not None and dwd.state == "STALE":
        bundle.quality_class = "C"
        bundle.quality_text = "Vertikalprofil + veraltete DWD-Bodenmessung"
    else:
        bundle.quality_class = "C"
        bundle.quality_text = "Vertikalprofil vorhanden; DWD-Bodenmessung für gewählten Tag fehlt"

    return bundle
