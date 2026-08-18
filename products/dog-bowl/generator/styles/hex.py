"""Honeycomb — two plates: solid recessed-hex drum, letters."""
from __future__ import annotations

from pathlib import Path

from ogma import bambu_project as bambu
import hex_bowl_design as hex_design

from .base import BowlStyle


def generate_meshes(
    job_dir: Path, name: str, font_style: str,
    bowl_rim_od_mm: float | None = None,
    bowl_body_od_mm: float | None = None,
    # Accepted and ignored: only the paw lattice is multi-part, but the
    # StyleImpl protocol is one signature for every style.
    one_piece: bool = False,
) -> float:
    report = hex_design.generate_hex_meshes(job_dir, name=name, font_style=font_style,
                                            bowl_rim_od_mm=bowl_rim_od_mm,
                            bowl_body_od_mm=bowl_body_od_mm)
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
