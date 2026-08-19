"""Paw lattice — the default style. Four plates: base, panel, top ring, letters."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

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


def fuzzy_mask_for(mesh_name: str, dims_root: Path):
    """Which faces of a preview part the slicer textures, or None for smooth.

    Mirrors what build_project writes into the 3MF, and has to keep mirroring it
    by hand: the base takes fuzzy_skin "external" so every wall of it is
    textured, the paw wall takes "none" plus a painted mask, and the top seat
    ring takes "none" with nothing painted at all.

    A preview that textures what the printer leaves smooth is worse than one
    with no texture, because it is the picture the customer buys from — which is
    how the paw pads came to be shown fuzzy while the whole generator went to
    some trouble to keep them clean.

    Says nothing about which faces are *wall*. Fuzzy skin perturbs the outer wall
    perimeter and never the top and bottom surfaces, so the underside the stand
    rests on and the rim the bowl drops into stay smooth — but that is a question
    about the angle of a surface, and the viewer answers it per fragment from the
    normal it already has. Answering it here instead put it through a per-vertex
    average, and on the base — 3,072 triangles, so every vertex touches both a
    wall and a cap — it came out between 0.28 and 0.80 everywhere: no face fully
    textured, none fully smooth.
    """
    if "top_seat_ring" in mesh_name:
        return None
    if "base" in mesh_name:
        return lambda mesh: np.ones(len(mesh.faces), dtype=bool)
    if "paw_panel" in mesh_name or "one_piece" in mesh_name:
        def mask(mesh):
            # Assembly coordinates: the pad specs are already in this frame, so
            # the offset is zero and is stated rather than derived. Deriving it
            # from the mesh works here and silently would not on a part whose
            # lowest point is not the panel's — see paint_mask_for_mesh.
            return COOPER_PAINTER.mask(
                np.asarray(mesh.vertices), np.asarray(mesh.faces),
                dims_root, z_offset=0.0,
            )
        return mask
    return None


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
    fuzzy_mask_for=fuzzy_mask_for,
)
