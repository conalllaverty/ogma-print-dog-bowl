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

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "products" / "dog-bowl" / "generator"))
sys.path.insert(0, str(REPO / "shared"))

import cooper_bowl_design as C  # noqa: E402
import name_fit  # noqa: E402
from pipeline import FONT_STYLES  # noqa: E402

# Ordinary names, the 8-letter worst case in the widest face, and a name wide
# enough to be rejected in every style there is.
CASES = [
    ("MAX", "bold"),
    ("WILLIAMS", "bold"),
    ("WILLIAMS", "slab"),
    ("LUNA", "serif"),
    ("WWWWWWWW", "bold"),
    ("WWWWWWWW", "slab"),
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


# --------------------------------------------------------------------------
# pytest entry points.
#
# This file was named test_*.py but contained only a main(), so `pytest tests`
# collected it and found nothing to run — it reported success while asserting
# nothing. The script form below is kept, because reading its table is how you
# see *which* case drifted; these make it fail a CI run rather than a habit.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name,font_style", CASES)
def test_precheck_agrees_with_the_build(name: str, font_style: str) -> None:
    """The pre-check is only safe while it is identical to the real verdict."""
    pre = name_fit.required_rail_deg(name, font_style)
    real = build_rail_deg(name, font_style)
    assert abs(pre - real) < TOLERANCE_DEG, (
        f"{name}/{font_style}: pre-check says ±{pre:.6f}°, "
        f"the build says ±{real:.6f}° — the designer would be lying"
    )


@pytest.mark.parametrize("style", FONT_STYLES)
def test_every_lettering_style_is_measurable(style: str) -> None:
    """A missing or unreadable face would otherwise surface only when a
    customer happened to pick that style."""
    assert name_fit.required_rail_deg("MAX", style) > 0


def test_the_cache_makes_a_warm_lookup_fast() -> None:
    """The 9 ms claim is what lets validation run on every keystroke."""
    name_fit.required_rail_deg("WWWWWWWW", "bold")  # warm it
    t = time.perf_counter()
    for _ in range(50):
        name_fit.required_rail_deg("WWWWWWWW", "bold")
    warm_ms = (time.perf_counter() - t) / 50 * 1000
    assert warm_ms < 5.0, f"warm lookup took {warm_ms:.2f} ms — cache not working"


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
