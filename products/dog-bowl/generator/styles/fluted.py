"""Fluted drum — two plates: vertically fluted drum, letters.

Same envelope, seat and letter system as the honeycomb; the flutes are the only
difference. That is the registry working as intended — a new style is a texture
function plus this file.
"""
from __future__ import annotations

from pathlib import Path

import fluted_bowl_design as fluted_design
from ogma import bambu_project as bambu

from .base import BowlStyle


def generate_meshes(job_dir: Path, name: str, font_style: str) -> float:
    report = fluted_design.generate_fluted_meshes(job_dir, name=name, font_style=font_style)
    return float(report["letters"]["name_rail_outer_deg"])


def build_project(**kwargs) -> Path:
    # Identical plate composition to hex: one drum body + one letters plate.
    return bambu.build_hex_project(
        body_mesh="fluted_body.ply", body_label="fluted body", **kwargs
    )


STYLE = BowlStyle(
    id="fluted",
    name="Fluted drum",
    description="Solid drum · vertical flutes · glue-in letters",
    available=True,
    supports_fuzzy=False,
    output_suffix="Fluted",
    generate_meshes=generate_meshes,
    build_project=build_project,
)
