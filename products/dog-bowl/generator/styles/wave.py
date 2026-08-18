"""Split wave — four plates: lower, inverted upper shell, seat insert, letters."""
from __future__ import annotations

from pathlib import Path

from ogma import bambu_project as bambu
import wave_bowl_design as wave_design

from .base import BowlStyle


def generate_meshes(
    job_dir: Path, name: str, font_style: str,
    bowl_rim_od_mm: float | None = None,
    bowl_body_od_mm: float | None = None,
    # Accepted and ignored: only the paw lattice is multi-part, but the
    # StyleImpl protocol is one signature for every style.
    one_piece: bool = False,
) -> float:
    report = wave_design.generate_wave_meshes(job_dir, name=name, font_style=font_style,
                                              bowl_rim_od_mm=bowl_rim_od_mm,
                            bowl_body_od_mm=bowl_body_od_mm)
    return float(report["letters"]["name_rail_outer_deg"])


def build_project(**kwargs) -> Path:
    return bambu.build_wave_project(**kwargs)


STYLE = BowlStyle(
    id="wave",
    name="Split wave",
    description="Sine seam · two-tone body · glue-in letters",
    available=True,
    supports_fuzzy=False,
    # The seam splits the drum into two printed bodies, so they can be two
    # colours. Nothing else here is two-part in a way the customer sees.
    two_tone_body=True,
    output_suffix="Wave",
    generate_meshes=generate_meshes,
    build_project=build_project,
)
