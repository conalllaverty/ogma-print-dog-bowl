"""Will this name fit on the rail? Answered without building a bowl.

The packing gate — letters must sit inside ±MAX_RAIL_OUTER_DEG — is the one
constraint a customer can actually trip, and until now the only way to discover
it was to run a multi-minute generate and read a NameFitError. This module
answers the same question in milliseconds so the designer can say it while
they're still typing.

It is not an approximation. It calls the same three functions the real build
calls (`glyph_polygon` -> `curved_letter_mesh` -> `letter_angular_half_extent`,
then `pack_letter_arc_centers` -> `required_name_rail_angles`), so its verdict
and the build's verdict cannot drift.

Two properties make it cheap:

- **A letter's angular half-extent depends only on that letter and the font.**
  It is measured with the glyph seated at theta=0; packing then moves letters
  sideways but never changes how wide each one subtends. So the expensive part
  (rasterise, extrude, boolean against the core cylinder — ~0.3 s) is memoised
  per (letter, font_style). "MAX" costs three glyphs once and nothing after.
- **Given the half-extents, packing is arithmetic.** No meshes involved.

Cold, a novel 8-letter name costs ~2-3 s. Warm — which is every keystroke after
the first, every colour change, and every repeat of a common name — it is
instant. 26 letters x 7 fonts is 182 entries, so the cache converges.
"""

from __future__ import annotations

from functools import lru_cache

import cooper_bowl_design as C
from pipeline import FONT_STYLES  # ordered ids; C.FONT_STYLES maps id -> font path

MAX_RAIL_OUTER_DEG = C.MAX_RAIL_OUTER_DEG


@lru_cache(maxsize=512)
def _letter_half_angle(letter: str, font_style: str) -> float:
    """Angular half-extent of one letter, seated at theta=0. Radians.

    Deliberately takes the font by name and passes it down explicitly: a
    generate may be running in another thread, and this must not touch the
    module globals it depends on.
    """
    font_path = str(C.FONT_STYLES[font_style])
    polygon, _mask, _pixel = C.glyph_polygon(
        letter, font_path=font_path, font_style=font_style
    )
    # Mirrored exactly as build_letters does — the visible face prints on the
    # bed. Asymmetric glyphs would measure differently otherwise.
    polygon = C.scale_geometry(polygon, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0))
    mesh = C.curved_letter_mesh(polygon, arc_center=0.0)
    return C.letter_angular_half_extent(mesh)


def required_rail_deg(name: str, font_style: str) -> float:
    """The half-angle this name needs, in degrees. Compare to MAX_RAIL_OUTER_DEG."""
    if font_style not in FONT_STYLES:
        raise ValueError(f"Unknown font style {font_style!r}")
    cleaned = C.normalize_name(name)
    half_angles = [_letter_half_angle(ch, font_style) for ch in cleaned]
    centers = C.pack_letter_arc_centers(half_angles)
    _flat_deg, outer_deg = C.required_name_rail_angles(half_angles, centers)
    return outer_deg


def check(name: str, font_style: str) -> tuple[bool, float]:
    """(fits, required_deg). Raises ValueError if the name isn't buildable at all."""
    outer = required_rail_deg(name, font_style)
    return outer <= MAX_RAIL_OUTER_DEG, outer


def widest_fitting_font(name: str) -> str | None:
    """The style that fits with most room to spare, or None if nothing fits.

    Lets the hint name a font that actually works instead of guessing
    "try condensed" and being wrong.
    """
    best: tuple[float, str] | None = None
    for style in FONT_STYLES:
        try:
            outer = required_rail_deg(name, style)
        except ValueError:
            return None
        if outer <= MAX_RAIL_OUTER_DEG and (best is None or outer < best[0]):
            best = (outer, style)
    return best[1] if best else None


def warm_cache(font_style: str = "bold", letters: str = "") -> int:
    """Pre-measure glyphs so the first customer doesn't pay for them.

    Both cases. The cache is keyed on the character, and names are no longer
    upper-cased on the way in, so a lowercase 'e' is a different entry from 'E'
    and warming only the capitals leaves half the alphabet cold — which the
    customer feels as the fit hint arriving late for exactly the names people
    actually type.
    """
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for ch in letters or (alphabet + alphabet.lower()):
        _letter_half_angle(ch, font_style)
    return _letter_half_angle.cache_info().currsize


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "MAX"
    for style in FONT_STYLES:
        fits, deg = check(name, style)
        print(f"{style:10s} ±{deg:5.1f}°  {'fits' if fits else 'REJECTED'}")
    print(f"limit ±{MAX_RAIL_OUTER_DEG:.0f}°")
