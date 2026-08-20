#!/usr/bin/env python3
"""Import every generator module in a fresh interpreter and report failures.

The golden harness exercises only the bowl styles that the designer builds, so
this is the wider net: it globs whatever products exist and imports each module
on its own, catching a break in code no bowl test ever loads.

Discovery is by glob, deliberately — the module list is never written down here.
That is what let the non-bowl products move out to `_other-products/` without
touching this file.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Every product's generator + coupon dir, plus the shared toolkit.
DIRS = sorted(
    [p for p in REPO.glob("products/*/generator")]
    + [p for p in REPO.glob("products/*/coupons")]
    + [REPO / "shared" / "ogma"]
)

SKIP = {
    # Fusion add-in half: imports adsk.* which only exists inside Autodesk Fusion.
    # Lives under _other-products/ now, so this normally matches nothing — kept
    # so the entry travels with the module if the two are reunited.
    "boucle_lamp_fusion",
}


def main() -> int:
    mods = sorted(
        (d, p.stem) for d in DIRS for p in d.glob("*.py") if not p.stem.startswith("_")
    )
    results = {}
    for d, m in mods:
        # Key by <dir>/<module>, not by module name alone.
        #
        # Two modules in this tree share the stem `preview` —
        # products/dog-bowl/generator/preview.py and shared/ogma/preview.py — and
        # a dict keyed on the stem silently kept whichever ran last. A broken
        # ogma.preview would have been reported as ok because the bowl's
        # generator/preview.py overwrote its verdict. The count gave it away:
        # "20 ok, 0 failed, 0 skipped, of 21".
        label = f"{d.relative_to(REPO)}/{m}"
        if m in SKIP:
            results[label] = "SKIP"
            continue
        # ogma is a package: import it as one, not as loose modules on sys.path.
        if d.name == "ogma":
            stmt = (f"import sys; sys.path.insert(0, {str(d.parent)!r}); "
                    f"import ogma.{m}")
        else:
            stmt = (f"import sys; sys.path.insert(0, {str(d)!r}); "
                    f"sys.path.insert(0, {str(REPO / 'shared')!r}); import {m}")
        proc = subprocess.run(
            [sys.executable, "-c", stmt],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode == 0:
            results[label] = "ok"
        else:
            tail = [l for l in proc.stderr.strip().splitlines() if l.strip()]
            results[label] = "FAIL: " + (tail[-1] if tail else "?")

    bad = {k: v for k, v in results.items() if v.startswith("FAIL")}
    skipped = {k for k, v in results.items() if v == "SKIP"}
    for k, v in sorted(results.items()):
        mark = "ok  " if v == "ok" else ("skip" if v == "SKIP" else "FAIL")
        print(f"  [{mark}] {k}" + ("" if v in ("ok", "SKIP") else f"\n         {v}"))
    # Counted, not assumed. This line used to hardcode "1 skipped" and subtract a
    # literal 1, which silently under-reported the ok count the moment the one
    # skipped module was no longer in the tree.
    ok = len(results) - len(bad) - len(skipped)
    print(f"\n{ok} ok, {len(bad)} failed, {len(skipped)} skipped, of {len(mods)}")

    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
