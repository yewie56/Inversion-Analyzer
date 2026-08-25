# -*- coding: utf-8 -*-
"""
KIT timestamp validation v0.9.1

Important:
The KIT field is named "localtime". Empirical validation against the actual
retrieval time shows that the millisecond number represents LOCAL wall-clock
time encoded on an epoch-like millisecond scale, not a true UTC Unix timestamp.

Example observed during a run at about 00:34 CEST:
  1787617800000 -> 00:30 local time

If interpreted as UTC and converted to Europe/Berlin, it would become 02:30,
which was still in the future at retrieval time and is therefore implausible.
"""
from __future__ import annotations

import pandas as pd
from .config import TIMEZONE

KNOWN_KIT_TEST_EPOCH_MS = 1787617800000
KNOWN_KIT_TEST_LOCAL_ISO = "2026-08-25T00:30:00+02:00"


def convert_kit_localtime_ms(value, timezone=TIMEZONE):
    """
    Interpret KIT 'localtime' as local wall-clock milliseconds.

    Do NOT parse with utc=True and tz_convert().
    Instead:
      1. decode milliseconds to a naive datetime
      2. localize that wall-clock time to Europe/Berlin
    """
    naive = pd.to_datetime(value, unit="ms")
    return naive.tz_localize(timezone)


def selftest_kit_timestamp():
    ts = convert_kit_localtime_ms(KNOWN_KIT_TEST_EPOCH_MS)
    actual = ts.isoformat()
    return {
        "pass": actual == KNOWN_KIT_TEST_LOCAL_ISO,
        "input_ms": KNOWN_KIT_TEST_EPOCH_MS,
        "expected": KNOWN_KIT_TEST_LOCAL_ISO,
        "actual": actual,
        "interpretation": "KIT local wall-clock time",
    }
