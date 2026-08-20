"""A letter is as thick as the wall behind it will allow.

LETTER_POCKET_DEPTH_MAX is what we want the letters to be; what they end up is
whatever leaves LETTER_POCKET_MIN_WEB behind the pocket floor. The paw lattice
cuts into a plaque that stands proud for exactly this purpose and takes the full
depth; the other three cut into the 4.0 mm wall that holds the bowl up, and
cannot. Getting this backwards does not fail loudly — it prints a stand whose
name you can see light through.

Run:  .venv/bin/python -m pytest tests/test_pocket_depth.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "products" / "dog-bowl" / "generator"))
sys.path.insert(0, str(REPO / "shared"))

import cooper_bowl_design as C  # noqa: E402
import fluted_bowl_design  # noqa: E402
import hex_bowl_design  # noqa: E402
import wave_bowl_design  # noqa: E402

CONFIGURE = {
    "cooper": lambda: None,
    "hex": hex_bowl_design._configure_hex_letters,
    "fluted": fluted_bowl_design._configure_fluted_letters,
    "wave": wave_bowl_design._configure_wave_letters,
}


def resolved(style: str, tmp_path) -> tuple[float, float]:
    """(depth, web) for one style, from a clean slate."""
    C.configure_output(tmp_path / style, name="MAX", font_style="bold")
    CONFIGURE[style]()
    depth = C.resolve_letter_pocket_depth()
    web = (
        (C.LETTER_FACE_R - C.LETTER_PROUD)
        - C.LETTER_MAX_GLYPH_BULGE
        - C.LETTER_POCKET_FLOOR_GAP
        - depth
        - C.LETTER_POCKET_BACKING_R
    )
    return depth, web


@pytest.mark.parametrize("style", sorted(CONFIGURE))
def test_every_style_keeps_its_wall(style, tmp_path):
    depth, web = resolved(style, tmp_path)
    assert web >= C.LETTER_POCKET_MIN_WEB - 1e-9, f"{style} left {web:.3f} mm"
    assert depth <= C.LETTER_POCKET_DEPTH_MAX + 1e-9
    assert round(depth * 10) == pytest.approx(depth * 10)  # whole 0.10 mm layers


def test_the_plaque_takes_the_full_depth(tmp_path):
    """The paw lattice is the one style with material to spare."""
    depth, web = resolved("cooper", tmp_path)
    assert depth == pytest.approx(C.LETTER_POCKET_DEPTH_MAX)
    assert web > 4.0


@pytest.mark.parametrize("style", ["hex", "fluted", "wave"])
def test_the_drum_styles_are_not_thinned_by_this(style, tmp_path):
    """2.2 mm is what they print today, and this must not take any of it away.

    They are the reason the depth is derived at all: a flat 2.7 would leave
    0.50 mm of wall, which is a single 0.42 mm extrusion and no infill.
    """
    depth, _web = resolved(style, tmp_path)
    assert depth == pytest.approx(2.2)


def test_the_backing_radius_does_not_leak_between_styles(tmp_path):
    """The wave sets its own; the next job must not inherit it.

    This is the dangerous direction: the wave's backing radius is ~2.6 mm
    smaller, so a honeycomb built after a wave would measure its pocket against
    a wall that is not behind it and cut deeper than its own allows.
    """
    C.configure_output(tmp_path / "wave", name="MAX", font_style="bold")
    wave_bowl_design._configure_wave_letters()
    assert C.LETTER_POCKET_BACKING_R != C.WALL_INNER_R
    C.configure_output(tmp_path / "after", name="MAX", font_style="bold")
    assert C.LETTER_POCKET_BACKING_R == C.WALL_INNER_R


def test_build_letters_resolves_before_it_builds_any(tmp_path):
    """curved_letter_mesh reads the depth, so it has to be right first."""
    C.configure_output(tmp_path / "job", name="MAX", font_style="bold")
    C.LETTER_POCKET_DEPTH = 999.0  # what a stale value would look like
    letters = C.build_letters()
    assert C.LETTER_POCKET_DEPTH == pytest.approx(C.LETTER_POCKET_DEPTH_MAX)
    # The letter is as thick as the pocket it goes into: extruded to the depth,
    # then its back scooped by the pocket-floor cylinder.
    thickness = float(letters[0]["mesh"].bounds[1][2] - letters[0]["mesh"].bounds[0][2])
    assert thickness == pytest.approx(C.LETTER_POCKET_DEPTH, abs=0.35)


def test_a_rail_with_no_room_is_refused(tmp_path):
    """Better a build that stops than a pocket cut through the wall."""
    C.configure_output(tmp_path / "job", name="MAX", font_style="bold")
    C.LETTER_POCKET_BACKING_R = C.LETTER_FACE_R - 1.0
    try:
        with pytest.raises(ValueError, match="no room"):
            C.resolve_letter_pocket_depth()
    finally:
        C.LETTER_POCKET_BACKING_R = C.WALL_INNER_R
