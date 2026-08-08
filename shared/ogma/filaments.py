"""Bambu filament palette lookup.

Moved out of the dog bowl's `pipeline.py`, which nine unrelated modules — five
Bouclé lamp modules, two Golf Tee lamp modules and two bowl coupon generators —
were importing purely to resolve a colour swatch. Reading a filament colour
should not drag in the bowl geometry, the paw silhouettes and the 3MF builder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ogma import assets

PALETTE_PATH = assets.PALETTE

DEFAULT_STAND = "matte-caramel"
DEFAULT_LETTERS = "matte-ivory-white"


@dataclass(frozen=True)
class Filament:
    id: str
    name: str
    hex: str


def load_palette(path: Path = PALETTE_PATH) -> dict[str, Filament]:
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
