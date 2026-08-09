"""The fit pre-check must agree with the build exactly, or it is a lie.

name_fit answers "will this name pack?" in milliseconds so the designer can say
it while the customer types. That is only safe while its verdict is identical to
what the generator would decide minutes later. This test builds the letters for
real and compares the two numbers.

Run:  .venv/bin/python tests/test_name_fit.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "products" / "dog-bowl" / "generator"))
sys.path.insert(0, str(REPO / "shared"))

import cooper_bowl_design as C  # noqa: E402
import name_fit  # noqa: E402
from pipeline import FONT_STYLES  # noqa: E402

# Ordinary names, the 8-letter worst case, and a name wide enough to be
# rejected in six of the seven styles.
CASES = [
    ("MAX", "bold"),
    ("WILLIAMS", "bold"),
    ("WILLIAMS", "condensed"),
    ("LUNA", "serif"),
    ("WWWWWWWW", "bold"),
    ("WWWWWWWW", "condensed"),
    ("IIII", "slab"),
    ("BELLA", "playful"),
    ("MOLLY", "rounded"),
    ("ZZ", "clean"),
]

TOLERANCE_DEG = 1e-9


def build_rail_deg(name: str, font_style: str) -> float:
    """What the generator itself concludes, by actually building the letters."""
    with tempfile.TemporaryDirectory() as td:
        C.configure_output(td, name, font_style)
        try:
            C.build_letters(name)
        except C.NameFitError:
            pass  # the angle is still recorded; that IS the rejection
        return C.NAME_RAIL_OUTER_DEG


def main() -> int:
    failures = 0
    for name, font_style in CASES:
        pre = name_fit.required_rail_deg(name, font_style)
        real = build_rail_deg(name, font_style)
        ok = abs(pre - real) < TOLERANCE_DEG
        failures += not ok
        verdict = "match" if ok else "*** MISMATCH ***"
        print(
            f"  {name:9s} {font_style:10s} "
            f"pre=±{pre:6.2f}°  build=±{real:6.2f}°  {verdict}"
        )

    # Every style must be measurable; a missing font would otherwise only show
    # up when a customer picked it.
    for style in FONT_STYLES:
        name_fit.required_rail_deg("MAX", style)

    # The cache is the whole point — assert it, don't assume it.
    t = time.perf_counter()
    for _ in range(50):
        name_fit.required_rail_deg("WWWWWWWW", "bold")
    warm_ms = (time.perf_counter() - t) / 50 * 1000
    print(f"\n  warm lookup: {warm_ms:.2f} ms")
    if warm_ms > 5.0:
        print("  *** cache not working — a live validate would be too slow ***")
        failures += 1

    print(f"\n{len(CASES) - failures}/{len(CASES)} agree" if failures else "\nall agree")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
