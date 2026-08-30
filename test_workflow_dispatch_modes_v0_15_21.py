# -*- coding: utf-8 -*-

from pathlib import Path

WF = Path(__file__).parent / ".github" / "workflows" / "inversion_collect.yml"


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAIL | {name} | {detail}")
    print(f"PASS | {name}")


def main():
    text = WF.read_text(encoding="utf-8")
    check("workflow_dispatch defines mode input", "mode:" in text and "normal" in text and "scheduled" in text and "kit-only" in text)
    check("manual scheduled mode invokes --scheduled", "inputs.mode" in text and "--scheduled" in text and "MANUAL SCHEDULED COLLECTION" in text)
    check("manual kit-only mode invokes --kit-only", "--kit-only" in text and "MANUAL KIT-ONLY COLLECTION" in text)
    check("normal manual mode remains", "MANUAL NORMAL COLLECTION" in text and "--today" in text)
    check("scheduled event remains scheduled", "github.event_name == 'schedule'" in text and "SCHEDULED COLLECTION" in text)
    print("PASS | v0.15.21 workflow dispatch mode regression complete")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
