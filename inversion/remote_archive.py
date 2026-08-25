# -*- coding: utf-8 -*-
from __future__ import annotations
import json, requests
from pathlib import Path
from .config import ARCHIVE_CONFIG, ARCHIVE_DIR, LOCATION_SLUG, REQUEST_TIMEOUT
from .archive import day_dir

def _raw_base(selected_date):
    cfg=ARCHIVE_CONFIG.get("remote_archive",{})
    owner=cfg.get("owner","").strip()
    repo=cfg.get("repository","").strip()
    branch=cfg.get("branch","main").strip() or "main"
    ap=cfg.get("archive_path","archive").strip("/")
    if not owner or not repo: return None
    return (
        f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
        f"{ap}/{LOCATION_SLUG}/{selected_date:%Y/%m/%d}"
    )

def fetch_remote_day(selected_date,log_cb=None):
    cfg=ARCHIVE_CONFIG.get("remote_archive",{})
    if not cfg.get("enabled",False):
        return False,"REMOTE_DISABLED"
    base=_raw_base(selected_date)
    if not base:
        return False,"REMOTE_NOT_CONFIGURED"
    def log(x):
        if log_cb: log_cb(x)
    try:
        r=requests.get(base+"/manifest.json",timeout=REQUEST_TIMEOUT)
        if r.status_code==404:
            log(f"Remote-Archiv: {selected_date} nicht vorhanden.")
            return False,"REMOTE_NOT_FOUND"
        r.raise_for_status()
        manifest=r.json()
        files=["manifest.json"]+[x for x in manifest.get("files",{}).values() if x]
        target=day_dir(selected_date)
        target.mkdir(parents=True,exist_ok=True)
        for fn in sorted(set(files)):
            rr=requests.get(base+"/"+fn,timeout=REQUEST_TIMEOUT)
            rr.raise_for_status()
            (target/fn).write_bytes(rr.content)
        log(f"Remote-Archiv: Tagespaket {selected_date} heruntergeladen.")
        return True,"OK"
    except Exception as exc:
        log(f"Remote-Archiv: Fehler {exc}")
        return False,f"REMOTE_ERROR: {exc}"
