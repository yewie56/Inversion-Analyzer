# -*- coding: utf-8 -*-
from __future__ import annotations
from .archive import load_bundle,save_bundle,missing_sources,merge_bundles,bundle_diagnostics
from .pipeline import load_data_for_date

def bundle_has_plot_data(bundle):
    if bundle is None:
        return False
    for name in ("result_data","sonde_metrics","kit_mast_metrics","icon_d2_data"):
        df=getattr(bundle,name,None)
        if df is not None and hasattr(df,"empty") and not df.empty:
            return True
    return False

def load_archive_day(selected_date,log_cb=None):
    """GUI-Navigation: ausschließlich lokales Archiv, kein Netzwerk."""
    def log(x):
        if log_cb: log_cb(x)
    old,manifest=load_bundle(selected_date)
    if old is None:
        log(f"Archiv: für {selected_date} sind lokal keine Daten vorhanden.")
        return None,None,"NOT_IN_LOCAL_ARCHIVE"
    diag=bundle_diagnostics(old)
    log(
        f"Archivdateien gefunden: Modell={diag['result_rows']} | "
        f"Radiosonde={diag.get('sonde_rows',0)} | "
f"KIT={diag['kit_rows']} | ICON-D2={diag['icon_rows']} | "
        f"ICON-Rohprofil={diag['icon_profile_rows']} | DWD={diag['dwd_rows']}"
    )

    miss=missing_sources(old)
    if miss:
        log(
            f"Archiv: {selected_date} geladen; unvollständig: {', '.join(miss)}. "
            "Kein automatischer Internetabruf."
        )
        return old,manifest,"LOCAL_ARCHIVE_PARTIAL"

    log(f"Archiv: {selected_date} lokal vollständig geladen.")
    return old,manifest,"LOCAL_ARCHIVE"

def update_day(selected_date,log_cb=None,only_missing=False,requested_sources=None):
    """
    Expliziter Internetabruf.
    Vorhandenes Archiv wird zuerst geladen und danach sicher zusammengeführt.
    """
    def log(x):
        if log_cb: log_cb(x)
    old,old_manifest=load_bundle(selected_date)

    requested=set(requested_sources) if requested_sources is not None else None

    if only_missing and old is not None:
        wanted=set(missing_sources(old))
        if requested is not None:
            wanted &= requested
        if not wanted:
            log(f"Update: {selected_date} ist für die aktivierten Quellen bereits vollständig; kein Abruf nötig.")
            return old,old_manifest,"LOCAL_ARCHIVE_COMPLETE"
        log(f"Update: nur fehlende aktivierte Quellen abrufen: {', '.join(sorted(wanted))}")
    else:
        wanted=requested
        if wanted is None:
            log(f"Update: alle Quellen für {selected_date} neu prüfen.")
        else:
            log(
                f"Update: aktivierte Quellen für {selected_date}: "
                + ", ".join(sorted(wanted))
            )

    fresh=load_data_for_date(selected_date,log_cb=log_cb,only_sources=wanted)
    merge_keys=wanted if wanted is not None else None
    merged=merge_bundles(old,fresh,merge_keys) if old is not None else fresh

    # Nach dem Safe-Merge ist dies die belastbare Qualitätsbewertung des
    # endgültigen Tagesbestands, nicht die des eventuell unvollständigen
    # Teillaufs.
    log(
        f"FINALER TAGESBESTAND | Datenqualität {merged.quality_class}: "
        f"{merged.quality_text}"
    )

    manifest=save_bundle(
        selected_date,
        merged,
        {
            "reason":"EXPLICIT_UPDATE" if not only_missing else "MISSING_REPAIR",
            "increment_attempt":True
        },
        touched_sources=(wanted if wanted is not None else None)
    )
    return merged,manifest,"UPDATED_SAFE_MERGE"

def get_day(selected_date,log_cb=None,allow_network=False,force=False):
    """Kompatibilitätsfunktion mit v0.12.1-Verhalten."""
    if not allow_network and not force:
        return load_archive_day(selected_date,log_cb)
    return update_day(selected_date,log_cb,only_missing=(not force))
