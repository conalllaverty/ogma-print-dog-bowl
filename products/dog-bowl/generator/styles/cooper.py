"""Paw lattice — the default style. Four plates: base, panel, top ring, letters."""
from __future__ import annotations

import json
from pathlib import Path

from ogma import bambu_project as bambu
import cooper_bowl_design as design
from paint_fuzzy_skin import COOPER_PAINTER

from .base import BowlStyle


def generate_meshes(
    job_dir: Path, name: str, font_style: str,
    bowl_rim_od_mm: float | None = None,
    bowl_body_od_mm: float | None = None,
    one_piece: bool = False,
) -> float:
    design.configure_output(job_dir, name=name, font_style=font_style,
                            bowl_rim_od_mm=bowl_rim_od_mm,
                            bowl_body_od_mm=bowl_body_od_mm)
    design.main(one_piece=one_piece)
    dims = json.loads((job_dir / "dimensions_and_validation.json").read_text())
    return float(dims["letters"]["name_rail_outer_deg"])


def build_project(**kwargs) -> Path:
    # Only Cooper paints fuzzy skin, so only Cooper supplies a painter.
    return bambu.build_project(painter=COOPER_PAINTER, **kwargs)


STYLE = BowlStyle(
    id="cooper",
    name="Paw lattice",
    description="Recessed paws + curved name rail (default)",
    available=True,
    supports_fuzzy=True,
    # Only the paw lattice is currently three parts; the drums are already one
    # body plus letters, and the wave's seam makes it inherently split.
    supports_one_piece=True,
    output_suffix="Paw_Lattice",
    generate_meshes=generate_meshes,
    build_project=build_project,
)
