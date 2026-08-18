"""Bambu filament palette lookup.

Moved out of the dog bowl's `pipeline.py`, which nine unrelated modules — five
Bouclé lamp modules, two Golf Tee lamp modules and two bowl coupon generators —
were importing purely to resolve a colour swatch. Reading a filament colour
should not drag in the bowl geometry, the paw silhouettes and the 3MF builder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ogma import assets

PALETTE_PATH = assets.PALETTE

# Nardo Gray, chosen on measured luminance rather than taste.
#
# The default's job is to show the wall pattern — paw lattice, honeycomb,
# flutes — as clearly as possible, because that is what a customer is choosing
# between. Surface relief reads as a shading gradient, so it needs a mid-tone:
# light colours (Ivory White at 1.00 relative luminance, Desert Tan at 0.71)
# blow out under the key and flatten the grooves, and dark ones (Charcoal 0.00,
# Plum 0.07) crush the shadow side until the pattern disappears.
#
# Of the mid band, Nardo Gray sits at 0.178 with **zero** saturation. Neutral
# matters as much as the value: with no hue of its own there is no chroma
# competing with the shading, which is why it is the reference grey for
# evaluating form. Caramel (0.260, 0.48 saturation) is the better-looking
# default and a worse informative one — its hue shifts under a warm key.
DEFAULT_STAND = "matte-nardo-gray"

# Ivory White against a mid grey is the strongest value contrast the palette
# offers, and the letters are the personalised part — they should read first.
DEFAULT_LETTERS = "matte-ivory-white"

# The second body colour, for styles whose body prints as two parts — currently
# only the split wave, whose sine seam divides it into a lower and an upper.
#
# Deliberately *different* from DEFAULT_STAND. A two-tone product that defaults
# to one colour hides the only thing that makes it two-tone, and the customer
# never learns the second control exists. Caramel against Nardo Gray is a warm/
# cool split at similar value, so the seam reads as a deliberate join rather
# than as one part looking wrong.
#
# It also has to sit under the letters: the wave's name rail is on the upper
# shell (letters at z 44-60, upper spanning 27-76), so this is the colour Ivory
# White letters are read against, and caramel gives them ample contrast.
DEFAULT_STAND_UPPER = "matte-caramel"


@dataclass(frozen=True)
class Filament:
    id: str
    name: str
    hex: str


@lru_cache(maxsize=4)
def load_palette(path: Path = PALETTE_PATH) -> dict[str, Filament]:
    """The palette, memoised — it is a read-only asset and validation reads it
    on every keystroke."""
    data = json.loads(Path(path).read_text())
    return {
        item["id"]: Filament(id=item["id"], name=item["name"], hex=item["hex"].upper())
        for item in data["filaments"]
    }


def resolve_filament(
    filament_id: str, palette: dict[str, Filament] | None = None
) -> Filament:
    palette = palette or load_palette()
    if filament_id not in palette:
        raise ValueError(
            f"Unknown filament '{filament_id}'. Use a Bambu PLA Matte swatch id."
        )
    return palette[filament_id]
