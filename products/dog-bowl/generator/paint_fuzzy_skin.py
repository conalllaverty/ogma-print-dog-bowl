#!/usr/bin/env python3
"""Cooper paw-panel fuzzy skin — the dog-bowl-specific half.

Outer-wall facets outside the paw silhouettes get `paint_fuzzy_skin="4"`
(TriangleSelector leaf, state 1). The panel object's fuzzy_skin is set to
"none" ("None (allow paint)"); thickness / point-distance still drive the
painted fuzz. Inner skin (r < 79.5) is left unpainted.

The generic XML/area machinery now lives in `ogma.paint`. What remains here is
only what a paw panel knows: where the pads are, where the name rail sits, and
what a correct painted result looks like for this part.

`build_bambu_project` no longer imports this module — it takes a `FuzzyPainter`
as an argument instead. That inversion is what stops every lamp and spinner
importing the dog bowl just to write a 3MF.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import Point
from shapely.strtree import STRtree

import cooper_bowl_design as design
from cooper_bowl_design import (
    NAME_RAIL_FLAT_Z0,
    NAME_RAIL_FLAT_Z1,
    PANEL_BOTTOM_Z,
    WALL_OUTER_R,
    paw_paint_silhouettes,
    unwrap_cylinder_u,
)

# NAME_RAIL_OUTER_DEG is deliberately NOT imported by value.
#
# build_letters() computes it from the name being built and writes it back to
# the module, so a by-value import freezes it at the 32° placeholder set at
# import time. The rail angle decides which paw pads are skipped, so a stale one
# means pads that exist in the mesh have no exclusion polygon and get fuzzed
# through. On a two-letter name the live value is 12.3° against that frozen 32°,
# and every pad between them came out painted.
#
# Masked in the normal pipeline because dimensions_and_validation.json is
# written before painting and takes precedence — this only bites a caller that
# paints without building the full job, which is exactly what a coupon is.
from ogma.paint import (
    PAINT_ATTR,
    allow_paint_on_object,
    assert_well_formed,
    paint_triangle_xml,
    painted_area_fraction,
)

R_PAINT_MIN = 79.5
PANEL_TOP_ID = "101"

# Acceptance window for the painted fraction of the outer wall. Below this the
# paws have eaten the wall (or the mask inverted); above it the pads and plaque
# are being painted when they must stay smooth for the letter pockets.
FUZZY_AREA_MIN = 0.55
FUZZY_AREA_MAX = 0.85

__all__ = [
    "PAINT_ATTR",
    "PANEL_TOP_ID",
    "R_PAINT_MIN",
    "CooperPaintMask",
    "COOPER_PAINTER",
    "allow_paint_on_panel",
    "assert_paint_ok",
    "on_name_rail_plaque",
    "paint_mask_for_mesh",
    "paint_object_model_bytes",
    "paint_triangle_xml",
    "rail_outer_deg",
]


def rail_outer_deg(root: Path) -> float:
    candidates = [
        root / "dimensions_and_validation.json",
        root / "cooper_dog_bowl" / "dimensions_and_validation.json",
    ]
    for dims in candidates:
        if dims.is_file():
            data = json.loads(dims.read_text())
            return float(data["letters"]["name_rail_outer_deg"])
    return float(design.NAME_RAIL_OUTER_DEG)


def on_name_rail_plaque(
    centroids: np.ndarray, rail_deg: float, z_offset: float = PANEL_BOTTOM_Z
) -> np.ndarray:
    """True for facets on the proud name-rail face (keep smooth for letter pockets)."""
    x, y, z = centroids[:, 0], centroids[:, 1], centroids[:, 2]
    cr = np.hypot(x, y)
    # Design front is -Y; plaque angles match build_panel / beveled_name_rail.
    theta_deg = np.degrees(np.arctan2(x, -y))
    z_lo = NAME_RAIL_FLAT_Z0 - z_offset - 2.0
    z_hi = NAME_RAIL_FLAT_Z1 - z_offset + 2.0
    return (
        (cr >= WALL_OUTER_R + 0.35)
        & (np.abs(theta_deg) <= rail_deg + 1.0)
        & (z >= z_lo)
        & (z <= z_hi)
    )


def paint_mask_for_mesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    root: Path,
    z_offset: float | None = None,
) -> np.ndarray:
    """Which outer-wall facets get fuzzy skin: everything but the pads and plaque.

    The pad specs are in *assembly* coordinates and this is normally handed the
    *print*-orientation panel, so the two frames have to be reconciled. That is
    what `z_offset` is, and it is measured from the mesh rather than assumed:
    `PANEL_BOTTOM_Z` is where the panel's bottom sits in assembly space, so the
    difference against the mesh's own lowest point is the shift, whichever frame
    the caller passed. Handed the assembly mesh it comes out zero, which is also
    correct — and that self-consistency is the point.

    It used to be the constant `LATTICE_BOTTOM`, which is 1 mm above the panel's
    real bottom (the locating tongue hangs below the lattice). Every pad's
    exclusion was therefore 1 mm low: a fuzzed strip along one edge of each paw,
    a smooth strip along the other, visible in Studio and on the print.

    `z_offset` can be given explicitly for a mesh whose lowest point is *not* the
    panel's bottom — a cropped coupon, say, where deriving it would silently
    reintroduce exactly the misalignment described above.
    """
    rail_deg = rail_outer_deg(root)
    if z_offset is None:
        z_offset = PANEL_BOTTOM_Z - float(np.asarray(vertices)[:, 2].min())
    polys = paw_paint_silhouettes(
        z_offset=z_offset,
        rail_outer_deg=rail_deg,
    )
    tree = STRtree(polys)
    centroids = vertices[faces].mean(axis=1)
    cu = unwrap_cylinder_u(centroids[:, 0], centroids[:, 1])
    cz = centroids[:, 2]
    cr = np.hypot(centroids[:, 0], centroids[:, 1])
    in_pad = np.array(
        [
            any(polys[j].contains(Point(u, z)) for j in tree.query(Point(u, z)))
            for u, z in zip(cu, cz)
        ]
    )
    on_plaque = on_name_rail_plaque(centroids, rail_deg, z_offset=z_offset)
    return (cr >= R_PAINT_MIN) & ~in_pad & ~on_plaque


def allow_paint_on_panel(cfg_xml: str) -> str:
    """fuzzy_skin none = Studio 'None (allow paint)'; keep thickness/distance."""
    return allow_paint_on_object(cfg_xml, PANEL_TOP_ID)


def assert_paint_ok(model_xml: str, cfg_xml: str, paint: np.ndarray, vertices, faces) -> None:
    assert_well_formed(model_xml, cfg_xml)
    if int(paint.sum()) <= 0:
        raise ValueError("painted-facet count must be > 0")
    centroids = vertices[faces].mean(axis=1)
    outer = np.hypot(centroids[:, 0], centroids[:, 1]) >= R_PAINT_MIN
    fuzzy_frac = painted_area_fraction(vertices, faces, paint, outer)
    if not (FUZZY_AREA_MIN <= fuzzy_frac <= FUZZY_AREA_MAX):
        raise ValueError(f"outer fuzzy area fraction out of range: {fuzzy_frac:.3f}")


class CooperPaintMask:
    """The `ogma.paint.FuzzyPainter` implementation for the Cooper paw panel."""

    def mask(self, vertices: np.ndarray, faces: np.ndarray, root: Path) -> np.ndarray:
        return paint_mask_for_mesh(vertices, faces, root)

    def verify(self, model_xml, cfg_xml, paint, vertices, faces) -> None:
        assert_paint_ok(model_xml, cfg_xml, paint, vertices, faces)


COOPER_PAINTER = CooperPaintMask()


def paint_object_model_bytes(
    model_xml: bytes,
    vertices: np.ndarray,
    faces: np.ndarray,
    root: Path,
) -> tuple[bytes, np.ndarray]:
    paint = paint_mask_for_mesh(vertices, faces, root)
    return paint_triangle_xml(model_xml.decode(), paint).encode(), paint
