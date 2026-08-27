# -*- coding: utf-8 -*-
"""
Regressionstest v0.15.18:
- GitHub cron hourly
- scheduled KIT archive queries today and yesterday
- previous-day incompleteness gets an explicit warning
- cumulative KIT merge and completeness logic stay present
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
workflow=(ROOT/".github/workflows/inversion_collect.yml").read_text(encoding="utf-8")
server=(ROOT/"Inversion_Server.py").read_text(encoding="utf-8")
archive=(ROOT/"inversion/archive.py").read_text(encoding="utf-8")

checks=[
    ('hourly_cron', 'cron: "17 * * * *"' in workflow),
    ('today_yesterday', 'days=(now.date(), now.date()-timedelta(days=1))' in server),
    ('kit_warning', 'WARNUNG KIT-TAGESARCHIV' in server),
    ('kit_complete_confirmation', 'KIT-TAGESARCHIV BESTÄTIGT' in server),
    ('timestamp_merge', '_merge_time_df' in archive and '"kit_mast" in replace' in archive),
    ('coverage_complete', 'complete=(n>=expected and largest<=cadence*gap_factor)' in archive),
]
failed=[]
for name,ok in checks:
    print(f"{'PASS' if ok else 'FAIL'} | {name}")
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit("SELFTEST FAIL: "+", ".join(failed))
print(f"SELFTEST PASS | {len(checks)}/{len(checks)}")
