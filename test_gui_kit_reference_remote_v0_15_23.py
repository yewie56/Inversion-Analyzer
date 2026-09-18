# -*- coding: utf-8 -*-
from __future__ import annotations
import inspect, json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import pandas as pd
import inversion.remote_archive as remote
import inversion.kit_reference_archive as kitref

class FakeResponse:
    def __init__(self,status_code=200,json_data=None,content=b""):
        self.status_code=status_code; self._json=json_data; self.content=content
    def json(self): return self._json
    def raise_for_status(self):
        if self.status_code>=400: raise RuntimeError(f"HTTP {self.status_code}")

def test_fetch_remote_kit_reference_day_downloads_global_archive():
    day=date(2026,8,30)
    manifest={"archive_kind":"KITMast","files":{"kit_mast_metrics":"kit_mast.csv","kit_mast_info":"kit_mast_info.json","source_status":"source_status.json"}}
    payloads={
        "manifest.json":FakeResponse(json_data=manifest,content=json.dumps(manifest).encode()),
        "kit_mast.csv":FakeResponse(content=b"time,inversion_index\n2026-08-30T15:00:00+02:00,1.5\n"),
        "kit_mast_info.json":FakeResponse(content=b"{}"),"source_status.json":FakeResponse(content=b"{}")}
    urls=[]
    def fake_get(url,timeout=None): urls.append(url); return payloads.get(url.rsplit('/',1)[-1],FakeResponse(status_code=404))
    with TemporaryDirectory() as td:
        old_ra,old_ka,old_get=remote.ARCHIVE_DIR,kitref.ARCHIVE_DIR,remote.requests.get
        try:
            root=Path(td)/"archive"; remote.ARCHIVE_DIR=root; kitref.ARCHIVE_DIR=root; remote.requests.get=fake_get
            ok,state=remote.fetch_remote_kit_reference_day(day); assert ok,state
            target=root/"KITMast"/"2026"/"08"/"30"
            assert (target/"manifest.json").exists() and len(pd.read_csv(target/"kit_mast.csv"))==1
            assert any("/archive/KITMast/2026/08/30/manifest.json" in u for u in urls)
        finally: remote.ARCHIVE_DIR,kitref.ARCHIVE_DIR,remote.requests.get=old_ra,old_ka,old_get

def test_archive_service_refreshes_missing_reference_from_remote():
    import inversion.archive_service as svc
    from inversion.models import DataBundle
    day=date(2026,8,30); bundle=DataBundle(); calls=[]
    old_fetch,old_load=remote.fetch_remote_kit_reference_day,svc.load_bundle
    try:
        remote.fetch_remote_kit_reference_day=lambda d,log_cb=None:(calls.append(d) or True,"OK")
        loaded=DataBundle(); loaded.kit_mast_metrics=pd.DataFrame({"time":[pd.Timestamp("2026-08-30T15:00:00+02:00")],"inversion_index":[1.5]})
        svc.load_bundle=lambda d:(loaded,{"saved_at":"x"})
        refreshed,manifest,state=svc.refresh_missing_kit_reference_from_remote(day,bundle)
        assert calls==[day] and refreshed is loaded and len(refreshed.kit_mast_metrics)==1 and state=="OK"
    finally: remote.fetch_remote_kit_reference_day,svc.load_bundle=old_fetch,old_load

def test_explicit_update_refreshes_central_kit_reference():
    import inversion.archive_service as svc
    import inversion.kit_reference_archive as kr
    from inversion.models import DataBundle
    day=date(2026,8,30); old=DataBundle(); old.quality_class="B"; old.quality_text="existing"; calls=[]
    saved=(svc.load_bundle,svc.save_bundle,kr.update_kit_reference_day,kr.attach_kit_reference,svc.load_data_for_date,svc.write_origin_marker)
    try:
        svc.load_bundle=lambda d:(old,{"files":{}}); svc.save_bundle=lambda *a,**k:{"saved_at":"x"}; svc.write_origin_marker=lambda *a,**k:None
        kr.update_kit_reference_day=lambda d,log_cb=None:(calls.append(d) or pd.DataFrame({"time":[pd.Timestamp("2026-08-30T15:00:00+02:00")],"inversion_index":[1.5]}),{},None,{})
        def attach(b,d): b.kit_mast_metrics=pd.DataFrame({"time":[pd.Timestamp("2026-08-30T15:00:00+02:00")],"inversion_index":[1.5]}); return b
        kr.attach_kit_reference=attach
        svc.load_data_for_date=lambda *a,**k: (_ for _ in ()).throw(AssertionError("location pipeline must not fetch KIT in reference mode"))
        merged,_,_=svc.update_day(day,requested_sources={"kit_mast"}); assert calls==[day] and len(merged.kit_mast_metrics)==1
    finally: svc.load_bundle,svc.save_bundle,kr.update_kit_reference_day,kr.attach_kit_reference,svc.load_data_for_date,svc.write_origin_marker=saved

def test_remote_kit_reference_failure_preserves_existing_local_files():
    day=date(2026,8,30); manifest={"archive_kind":"KITMast","files":{"kit_mast_metrics":"kit_mast.csv","kit_mast_info":"kit_mast_info.json"}}
    responses={"manifest.json":FakeResponse(json_data=manifest,content=json.dumps(manifest).encode()),"kit_mast.csv":FakeResponse(content=b"time,inversion_index\n2026-08-30T15:00:00+02:00,9.9\n"),"kit_mast_info.json":FakeResponse(status_code=500)}
    def fake_get(url,timeout=None): return responses[url.rsplit('/',1)[-1]]
    with TemporaryDirectory() as td:
        old_ra,old_get=remote.ARCHIVE_DIR,remote.requests.get
        try:
            root=Path(td)/"archive"; remote.ARCHIVE_DIR=root; target=root/"KITMast"/"2026"/"08"/"30"; target.mkdir(parents=True)
            old_csv=b"time,inversion_index\n2026-08-30T14:00:00+02:00,1.2\n"; (target/"kit_mast.csv").write_bytes(old_csv); remote.requests.get=fake_get
            ok,_=remote.fetch_remote_kit_reference_day(day); assert not ok and (target/"kit_mast.csv").read_bytes()==old_csv
        finally: remote.ARCHIVE_DIR,remote.requests.get=old_ra,old_get

def test_gui_worker_uses_reference_refresh_helper():
    src=Path("inversion/gui.py").read_text(encoding="utf-8")
    marker="refreshed,ref_manifest,ref_state=refresh_missing_kit_reference_from_remote"
    assert marker in src
    worker=src[src.index("    def worker_update(self):"):src.index("    def _normalize_bundle_for_display",src.index("    def worker_update(self):"))]
    assert worker.index("refresh_missing_kit_reference_from_remote") < worker.index("bundle_has_plot_data")

if __name__=="__main__":
    test_fetch_remote_kit_reference_day_downloads_global_archive(); test_archive_service_refreshes_missing_reference_from_remote(); test_explicit_update_refreshes_central_kit_reference(); test_remote_kit_reference_failure_preserves_existing_local_files(); test_gui_worker_uses_reference_refresh_helper()
    print("PASS | v0.15.23 GUI central KITMast reference regressions")
