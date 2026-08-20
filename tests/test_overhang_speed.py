"""No overhang bucket prints slower than a bridge.

The letters are cut as straight glyph prisms, so the top edge of every stroke is
a LETTER_POCKET_DEPTH ledge with nothing under it. Bambu buckets that 4/4, and
every template ships 10 mm/s for it — a 10x drop from the paw wall's 100 and 20x
from the drum styles' 200. The flow lag either side of each of those transitions
is what draws the horizontal lines across a printed name plaque, which is the one
outer surface the fuzzy skin does not cover.

The failure this file exists for is not the number. It is that `bambu_project`
has three project builders and the overhang speeds used to be written in exactly
one of them, so the paw lattice could be fixed while the honeycomb, fluted drum
and split wave silently kept the cliff. `every_builder_...` is the real test
here; the rest pin the behaviour of the helper it checks for.

Run:  .venv/bin/python -m pytest tests/test_overhang_speed.py -q
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "shared"))

from ogma.bambu_project import _apply_overhang_speeds  # noqa: E402

#: Everything that writes a Bambu project file. Discovered rather than listed,
#: because the miss this test exists for was a settings block nobody remembered:
#: `bambu_project` had three builders and only one wrote overhang speeds, and
#: then the letter-fit coupon turned out to be a fourth writer with a fourth
#: copy — which matters more than the others, because a coupon sliced unlike the
#: part it stands in for answers a question nobody asked.
SEARCH_ROOTS = (REPO / "shared" / "ogma", REPO / "products" / "dog-bowl")


def project_settings_writers() -> list[Path]:
    out = []
    for root in SEARCH_ROOTS:
        for f in sorted(root.rglob("*.py")):
            if "node_modules" in f.parts or ".venv" in f.parts:
                continue
            if "Metadata/project_settings.config" in f.read_text():
                out.append(f)
    return out
BUCKETS = (
    "overhang_1_4_speed",
    "overhang_2_4_speed",
    "overhang_3_4_speed",
    "overhang_4_4_speed",
    "overhang_totally_speed",
)


def settings(bridge: str = "50", **buckets: str) -> dict:
    base = {"bridge_speed": [bridge, bridge]}
    for key in BUCKETS:
        base[key] = [buckets.get(key, "10"), "10"]
    return base


def test_a_bucket_slower_than_the_bridge_comes_up_to_it():
    s = settings()
    _apply_overhang_speeds(s)
    assert [s[k][0] for k in BUCKETS] == ["50"] * len(BUCKETS)


def test_a_bucket_already_faster_is_left_alone():
    # Raising only. Slowing a bucket down would be a regression dressed as a fix.
    s = settings(overhang_1_4_speed="80", overhang_2_4_speed="50")
    _apply_overhang_speeds(s)
    assert s["overhang_1_4_speed"][0] == "80"
    assert s["overhang_2_4_speed"][0] == "50"


def test_zero_is_left_alone():
    # 0 is Bambu for "no slowdown, use the outer wall speed" — already faster
    # than a bridge. The drum templates ship it on the 1/4 bucket.
    s = settings(overhang_1_4_speed="0")
    _apply_overhang_speeds(s)
    assert s["overhang_1_4_speed"][0] == "0"


def test_only_the_first_nozzle_entry_moves():
    # The P2S is single-nozzle multi-material; index 1 is not a second hot end
    # and nothing else in this module writes it.
    s = settings()
    _apply_overhang_speeds(s)
    assert all(s[k][1] == "10" for k in BUCKETS)


def test_the_floor_follows_bridge_speed():
    s = settings(bridge="30")
    _apply_overhang_speeds(s)
    assert [s[k][0] for k in BUCKETS] == ["30"] * len(BUCKETS)


def test_every_builder_that_writes_project_settings_applies_them():
    sources = project_settings_writers()
    assert len(sources) >= 4, f"expected to find the writers, found {sources}"
    missing = []
    for src in sources:
        for node in ast.parse(src.read_text()).body:
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.dump(node)
            if "Metadata/project_settings.config" not in body:
                continue
            if "_apply_overhang_speeds" not in body:
                missing.append(f"{src.relative_to(REPO)}::{node.name}")
    assert not missing, (
        f"{missing} write project_settings.config without calling "
        "_apply_overhang_speeds — they ship the 10 mm/s cliff"
    )
