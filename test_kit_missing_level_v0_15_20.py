# -*- coding: utf-8 -*-
"""Network-free regression test for KIT missing-level handling in v0.15.20."""
from datetime import date
import math

from inversion.config import VERSION
from inversion.kit_inversion import extract_kit_temperature_profiles


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAIL | {name} | {detail}")
    print(f"PASS | {name}")


def make_source():
    levels = [2, 10, 30, 60, 100, 130, 160, 200]
    temps = [21.919, 23.014, 22.027, 21.260, 20.799, 20.355, 20.390, None]
    return {
        "id": "fixture_0900",
        "data": {
            "variable": [f"PT_T_AIR_{z:03d}_AVG" for z in levels],
            "altitude": levels,
            "value": temps,
            "localtime_iso": ["2026-08-30T09:00:00+02:00"] * len(levels),
            "localtime": [1788073200000] * len(levels),
        },
    }


def main():
    check("Version >= 0.15.20", tuple(map(int, VERSION.split("."))) >= (0,15,20), VERSION)

    logs = []
    df, meta = extract_kit_temperature_profiles(
        [make_source()], date(2026, 8, 30), logs.append
    )

    check("Profil trotz fehlendem 200-m-Wert erkannt", df is not None and len(df) == 1)
    row = df.iloc[0]
    check("7 gültige Höhen verwendet", int(row["kit_profile_levels"]) == 7, row["kit_profile_levels"])
    check("200 m als fehlend markiert", str(row["kit_missing_levels"]) == "200", row["kit_missing_levels"])
    check("160-m-Temperatur vorhanden", abs(float(row["kit_temperature_160m_C"]) - 20.390) < 1e-9)
    check("keine 200-m-Temperatur erzeugt", "kit_temperature_200m_C" not in df.columns)
    check("Index endlich", math.isfinite(float(row["kit_mast_index"])), row["kit_mast_index"])
    check("Metadaten erkennen unvollständiges Profil", meta["incomplete_profiles"] == 1, meta)
    check("Log nennt fehlende Höhe", any("200 m" in x and "gültigen Höhen" in x for x in logs), logs)

    # Also verify NaN behaves like missing.
    s = make_source()
    s["data"]["value"][-1] = float("nan")
    df2, _ = extract_kit_temperature_profiles([s], date(2026, 8, 30), None)
    check("NaN wird wie fehlender Wert toleriert", df2 is not None and len(df2) == 1)

    # But fewer than two valid levels must still fail.
    s = make_source()
    s["data"]["value"] = [21.0] + [None] * 7
    df3, meta3 = extract_kit_temperature_profiles([s], date(2026, 8, 30), None)
    check("Profil mit nur einer gültigen Höhe verworfen", df3 is None)
    check("Ungültig-Zähler erhöht", meta3["rejected_invalid_temperature_sources"] == 1, meta3)

    print("PASS | v0.15.20 KIT missing-level regression complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
