#!/usr/bin/env python3
"""Import every generator module in a fresh interpreter and report failures.

The golden harness only exercises the three bowl styles. The seam cuts touch
lamps, spinners and clickers too, so this is the net that catches a broken
import in code no bowl test ever loads.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

GEN = Path(__file__).resolve().parent.parent / "backend" / "generator"

SKIP = {
    # Fusion add-in half: imports adsk.* which only exists inside Autodesk Fusion.
    "boucle_lamp_fusion",
}


def main() -> int:
    mods = sorted(p.stem for p in GEN.glob("*.py") if not p.stem.startswith("_"))
    results = {}
    for m in mods:
        if m in SKIP:
            results[m] = "SKIP"
            continue
        proc = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {str(GEN)!r}); import {m}"],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode == 0:
            results[m] = "ok"
        else:
            tail = [l for l in proc.stderr.strip().splitlines() if l.strip()]
            results[m] = "FAIL: " + (tail[-1] if tail else "?")

    bad = {k: v for k, v in results.items() if v.startswith("FAIL")}
    for k, v in sorted(results.items()):
        mark = "ok  " if v == "ok" else ("skip" if v == "SKIP" else "FAIL")
        print(f"  [{mark}] {k}" + ("" if v in ("ok", "SKIP") else f"\n         {v}"))
    print(f"\n{len(results)-len(bad)-1} ok, {len(bad)} failed, 1 skipped, of {len(mods)}")

    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
