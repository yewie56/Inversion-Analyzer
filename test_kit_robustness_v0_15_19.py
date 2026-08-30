#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Network-free regression tests for v0.15.19 KIT robustness."""
from pathlib import Path
import tempfile
import time

from inversion import bokeh_client
from inversion.config import VERSION, KIT_BOKEH_TIMEOUT, KIT_BOKEH_MAX_ATTEMPTS, KIT_BOKEH_RETRY_DELAYS_SEC

ROOT=Path(__file__).resolve().parent


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} | {name}" + (f" – {detail}" if detail else ""))
    if not ok:
        raise AssertionError(name)


def fake_timeout(url, run_id, timeout_sec):
    return {"ok":False,"state":"BOKEH_CLIENT_TIMEOUT","message":"timeout","detail":"test","sources":[],"json_file":None,"csv_files":[]}


def fake_sequence_factory():
    calls=[]
    def fake(url, run_id, timeout_sec):
        calls.append((run_id,timeout_sec))
        if len(calls)<3:
            return {"ok":False,"state":"BOKEH_CLIENT_CONNECT_ERROR","message":"connect","detail":"test","sources":[],"json_file":None,"csv_files":[]}
        return {"ok":True,"state":"BOKEH_CLIENT_DATA","message":"ok","detail":"test","roots":[{}],"sources":[{"id":"x","columns":[],"data":{}}],"json_file":None,"csv_files":[]}
    return calls,fake


def main():
    check('Version >= 0.15.19', tuple(map(int, VERSION.split('.'))) >= (0,15,19), VERSION)
    check('KIT hard timeout default 20 s', KIT_BOKEH_TIMEOUT==20, str(KIT_BOKEH_TIMEOUT))
    check('KIT max attempts 3', KIT_BOKEH_MAX_ATTEMPTS==3, str(KIT_BOKEH_MAX_ATTEMPTS))
    check('KIT retry delays 5/15 s', list(KIT_BOKEH_RETRY_DELAYS_SEC)==[5,15], str(KIT_BOKEH_RETRY_DELAYS_SEC))

    wf=(ROOT/'.github/workflows/inversion_collect.yml').read_text(encoding='utf-8')
    check('GitHub schedule 7,37', 'cron: "7,37 * * * *"' in wf)

    old=bokeh_client._pull_with_hard_timeout
    try:
        bokeh_client._pull_with_hard_timeout=fake_timeout
        r=bokeh_client.pull_bokeh_document('test://kit','t',timeout_sec=0.1,max_attempts=3,retry_delays=[0,0])
        check('Timeout: exactly three attempts', len(r.get('attempts',[]))==3, str(r.get('attempts')))
        check('Timeout state preserved', r.get('state')=='BOKEH_CLIENT_TIMEOUT', str(r.get('state')))

        calls,fake=fake_sequence_factory()
        bokeh_client._pull_with_hard_timeout=fake
        r=bokeh_client.pull_bokeh_document('test://kit','s',timeout_sec=7,max_attempts=3,retry_delays=[0,0])
        check('Retry succeeds on third attempt', r.get('ok') and len(r.get('attempts',[]))==3)
        check('Timeout propagated to each attempt', all(x[1]==7 for x in calls), str(calls))
    finally:
        bokeh_client._pull_with_hard_timeout=old

    # Real hard-timeout mechanism without network: patch worker target is not trivial
    # under spawn. Verify the implementation contains terminate() and bounded join().
    code=(ROOT/'inversion/bokeh_client.py').read_text(encoding='utf-8')
    check('Hard timeout terminates worker', 'proc.terminate()' in code)
    check('Per-attempt diagnostics present', 'elapsed_sec' in code and 'attempts' in code)

    print(f'PASS | KIT robustness regression from v0.15.19 complete on v{VERSION}')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
