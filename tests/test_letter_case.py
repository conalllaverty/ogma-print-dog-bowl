"""Names are set the way they are typed, in the font that was picked.

Every glyph used to be stretched to fill LETTER_HEIGHT on its own, which is
invisible while names are forced to capitals — they are all the same height
anyway — and wrong the moment one is lowercase: an 'e' would be blown up to the
size of a 'C'. Cap height is now the ruler and the baseline is shared, so these
tests are mostly about the two things that follow from that: a capital lands
exactly where it always did, and everything else lands in proportion to it.

Run:  .venv/bin/python -m pytest tests/test_letter_case.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "products" / "dog-bowl" / "generator"))
sys.path.insert(0, str(REPO / "shared"))

import cooper_bowl_design as C  # noqa: E402
from pipeline import FONT_STYLES  # noqa: E402

# The raster grid is 0.12 mm, so nothing here can be tighter than one cell.
CELL = C.GLYPH_PIXEL_MM


@pytest.fixture(scope="module")
def job(tmp_path_factory):
    """A configured job, because glyph_polygon reads the font off the globals."""
    C.configure_output(tmp_path_factory.mktemp("case"), name="Chloe", font_style="serif")
    return C.NAME


def polygon(letter: str, font_style: str = "serif"):
    poly, _mask, _pixel = C.glyph_polygon(
        letter, font_path=str(C.FONT_STYLES[font_style]), font_style=font_style
    )
    return poly


@pytest.mark.parametrize("font_style", sorted(FONT_STYLES))
def test_a_capital_is_exactly_cap_height_in_every_face(font_style):
    """'H' runs from the baseline to +LETTER_HEIGHT/2, in all seven faces.

    This is the compatibility test: cap height is the scale for the whole word,
    so if it drifts, every all-caps bowl already shipped changes size.

    The cap line is exact; the foot is a tolerance because two of these faces
    (Fredoka, Baloo 2) round the ends of their stems and overshoot the baseline
    by 0.2 mm doing it. That overshoot is the font's, and it now survives into
    the print instead of being squashed out.
    """
    bounds = polygon("H", font_style).bounds
    assert bounds[3] == pytest.approx(C.LETTER_HEIGHT / 2, abs=CELL)
    assert -C.LETTER_HEIGHT / 2 - 0.3 <= bounds[1] <= -C.LETTER_HEIGHT / 2 + CELL


def test_lowercase_is_smaller_than_a_capital_and_shares_its_baseline(job):
    cap = polygon("H").bounds
    ex = polygon("x").bounds
    # x-height is roughly two thirds of cap height across these faces; the point
    # is only that it is clearly smaller, not stretched to match.
    assert 0.5 < (ex[3] - ex[1]) / (cap[3] - cap[1]) < 0.85
    # Same baseline. Round and pointed letters overshoot it slightly by design,
    # which is why this is a tolerance and not equality.
    assert ex[1] == pytest.approx(cap[1], abs=0.4)


def test_an_ascender_reaches_above_the_cap_line(job):
    assert polygon("l").bounds[3] > polygon("H").bounds[3] + 0.5


def test_a_descender_hangs_below_the_baseline(job):
    drop = polygon("H").bounds[1] - polygon("p").bounds[1]
    # Every shipping face puts it between 4.4 and 5.8 mm at cap height 15.
    assert 4.0 < drop < 6.5


def test_the_dot_on_an_i_reaches_the_letter_and_its_pocket(job):
    """A tittle is a second piece, and both consumers have to build it.

    Dropping it is silent: the letter still prints, the stand still has a
    pocket, and the name reads 'Bailev' with a dot loose in the bag.
    """
    poly = polygon("i")
    assert len(C.glyph_parts(poly)) == 2

    mirrored = C.scale_geometry(poly, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0))
    letter = C.curved_letter_mesh(mirrored, arc_center=0.0)
    assert len(letter.split(only_watertight=False)) == 2
    pocket = C.letter_pocket_cutter(mirrored, arc_center=0.0)
    assert len(pocket.split(only_watertight=False)) == 2


def test_raster_specks_are_not_mistaken_for_a_tittle():
    """The threshold has to separate a dot from a stray cell, not just >1 part."""
    from shapely.geometry import box as shapely_box
    from shapely.geometry import MultiPolygon

    stem = shapely_box(-1.0, -7.5, 1.0, 7.5)
    speck = shapely_box(5.0, 5.0, 5.0 + CELL, 5.0 + CELL)
    assert C.glyph_parts(MultiPolygon([stem, speck])) == [stem]


def test_the_name_keeps_the_case_it_was_typed():
    assert C.normalize_name("Chloe") == "Chloe"
    assert C.normalize_name("mr. bean") == "mrbean"
    with pytest.raises(ValueError):
        C.normalize_name("2")


def test_the_plaque_follows_a_descender_and_leaves_capitals_alone(tmp_path):
    """Cooper's flat has to reach under the ink, or the pocket cuts the blend."""
    C.configure_output(tmp_path / "caps", name="MAX", font_style="serif")
    C.build_letters()
    assert C.NAME_RAIL_FLAT_Z0 == 29.0  # the shipping band, untouched
    assert C.NAME_RAIL_FLAT_Z1 == 52.0

    C.configure_output(tmp_path / "descender", name="Poppy", font_style="serif")
    letters = C.build_letters()
    ink_bottom = C.LETTER_CENTER_Z + min(
        float(item["polygon"].bounds[1]) for item in letters
    )
    assert C.NAME_RAIL_FLAT_Z0 < 29.0
    assert C.NAME_RAIL_FLAT_Z0 <= ink_bottom - C.LETTER_PLAQUE_MARGIN + 1e-9


def test_the_widened_plaque_does_not_leak_into_the_next_job(tmp_path):
    """The API server builds every name in one process — see reset_letter_geometry."""
    C.configure_output(tmp_path / "descender", name="Poppy", font_style="serif")
    C.build_letters()
    assert C.NAME_RAIL_FLAT_Z0 < 29.0
    C.configure_output(tmp_path / "caps", name="MAX", font_style="serif")
    assert C.NAME_RAIL_FLAT_Z0 == 29.0


def test_the_name_field_no_longer_rewrites_what_is_typed():
    sys.path.insert(0, str(REPO / "products" / "dog-bowl"))
    import designer  # noqa: E402

    values = designer.SPEC.coerce({"name": "Chloe"})
    assert values["name"] == "Chloe"
