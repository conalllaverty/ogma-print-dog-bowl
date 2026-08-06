"""Paw lattice — the default style. Four plates: base, panel, top ring, letters."""
from __future__ import annotations

import json
from pathlib import Path

import build_bambu_project as bambu
import cooper_bowl_design as design
from paint_fuzzy_skin import COOPER_PAINTER

from .base import BowlStyle


def generate_meshes(job_dir: Path, name: str, font_style: str) -> float:
    design.configure_output(job_dir, name=name, font_style=font_style)
    design.main()
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
    output_suffix="Paw_Lattice",
    generate_meshes=generate_meshes,
    build_project=build_project,
)
