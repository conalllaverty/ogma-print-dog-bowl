"""Split wave — four plates: lower, inverted upper shell, seat insert, letters."""
from __future__ import annotations

from pathlib import Path

from ogma import bambu_project as bambu
import wave_bowl_design as wave_design

from .base import BowlStyle


def generate_meshes(job_dir: Path, name: str, font_style: str) -> float:
    report = wave_design.generate_wave_meshes(job_dir, name=name, font_style=font_style)
    return float(report["letters"]["name_rail_outer_deg"])


def build_project(**kwargs) -> Path:
    return bambu.build_wave_project(**kwargs)


STYLE = BowlStyle(
    id="wave",
    name="Split wave",
    description="Sine seam · separate bowl seat · glue-in letters",
    available=True,
    supports_fuzzy=False,
    output_suffix="Wave",
    generate_meshes=generate_meshes,
    build_project=build_project,
)
