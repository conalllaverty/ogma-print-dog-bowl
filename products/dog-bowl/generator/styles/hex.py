"""Honeycomb — two plates: solid recessed-hex drum, letters."""
from __future__ import annotations

from pathlib import Path

from ogma import bambu_project as bambu
import hex_bowl_design as hex_design

from .base import BowlStyle


def generate_meshes(job_dir: Path, name: str, font_style: str) -> float:
    report = hex_design.generate_hex_meshes(job_dir, name=name, font_style=font_style)
    return float(report["letters"]["name_rail_outer_deg"])


def build_project(**kwargs) -> Path:
    return bambu.build_hex_project(**kwargs)


STYLE = BowlStyle(
    id="hex",
    name="Honeycomb",
    description="Solid drum · recessed hex pattern · glue-in letters",
    available=True,
    supports_fuzzy=False,
    output_suffix="Honeycomb",
    generate_meshes=generate_meshes,
    build_project=build_project,
)
