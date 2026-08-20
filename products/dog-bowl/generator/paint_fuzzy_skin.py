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
from scipy.spatial import cKDTree
from shapely.strtree import STRtree

import cooper_bowl_design as design
from cooper_bowl_design import (
    PANEL_BOTTOM_Z,
    PAW_RECESS_DEPTH,
    WALL_OUTER_R,
    paw_paint_silhouettes,
    unwrap_cylinder_u,
)

# Neither NAME_RAIL_OUTER_DEG nor the plaque's Z span is imported by value.
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
#
# NAME_RAIL_FLAT_Z0/Z1 are the same story in the vertical: build_letters() drops
# the flat to cover a descender, and a frozen 29.0 would leave the part of the
# plaque below it outside the exclusion, fuzzing the wall a letter pocket is
# about to be cut into.
from ogma.paint import (
    PAINT_ATTR,
    allow_paint_on_object,
    assert_well_formed,
    paint_triangle_xml,
    painted_area_fraction,
)

R_PAINT_MIN = 79.5
PANEL_TOP_ID = "101"

#: How close to NAME_RAIL_OUTER_R a facet must sit to count as the flat rail
#: face rather than something cut into it. The face is at exactly that radius
#: and the nearest surface below it is a pocket wall; measured on a ROCCO
#: one-piece there is nothing at all between r 85.4 and 85.9, so this sits in
#: open water and does not need to be tuned.
RAIL_FACE_TOL = 0.10

#: Smooth border left between the fuzzed rail face and every letter pocket.
#:
#: The plaque is fuzzed but the pockets are not, and the boundary between them
#: is the glyph outline itself — the one edge on the part that has to stay
#: crisp. Fuzz is placed every fuzzy_skin_point_distance (0.8 mm) and displaces
#: the wall by up to half fuzzy_skin_thickness (0.15 mm), so a pocket edge
#: inside that reach can lose 0.15 mm of an outline whose whole clearance is
#: LETTER_POCKET_CLEARANCE, 0.10 mm a side. That is a letter that binds on its
#: own rim, and a rim that reads ragged where it should read sharp.
#:
#: One point-distance plus a little, so the last displaced point is a full
#: period clear of the edge and the perimeter is back on nominal before it turns
#: into the pocket. Set it to 0.0 to fuzz right up to the glyphs.
LETTER_POCKET_HALO = 1.0

# Acceptance window for the painted fraction of the outer wall. Below this the
# paws have eaten the wall (or the mask inverted); above it the pads or the
# letter pockets are being painted when they must stay smooth. The rail face
# joining the painted side of that line moved this from 0.72 to 0.79.
FUZZY_AREA_MIN = 0.55
FUZZY_AREA_MAX = 0.85

__all__ = [
    "PAINT_ATTR",
    "PANEL_TOP_ID",
    "R_PAINT_MIN",
    "CooperPaintMask",
    "COOPER_PAINTER",
    "allow_paint_on_panel",
    "DISH_PAINTED_MAX",
    "POCKET_PAINTED_MAX",
    "assert_paint_ok",
    "on_name_rail_plaque",
    "letter_pocket_facets",
    "rail_face_paint",
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
            data = json.loads(dims.read_text(encoding="utf-8"))
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
    z_lo = design.NAME_RAIL_FLAT_Z0 - z_offset - 2.0
    z_hi = design.NAME_RAIL_FLAT_Z1 - z_offset + 2.0
    return (
        (cr >= WALL_OUTER_R + 0.35)
        & (np.abs(theta_deg) <= rail_deg + 1.0)
        & (z >= z_lo)
        & (z <= z_hi)
    )


def _rail_uz(centroids: np.ndarray) -> np.ndarray:
    """Plaque-local (arc length, height) for measuring across the rail face.

    Deliberately not `unwrap_cylinder_u`: that one's seam is placed at
    PAW_PAINT_SEAM_DEG, which is -90 — straight through the plaque, chosen
    because the plaque arc is the one stretch of wall with no pads to split.
    Right through the middle of the surface this has to measure distances on.
    Nothing goes wrong loudly; the letters either side of the seam simply come
    out a full circumference apart and their halo never lands.

    The rail spans well under half a turn, so a plain arc from the design front
    is continuous over it and needs no seam at all.
    """
    x, y, z = centroids[:, 0], centroids[:, 1], centroids[:, 2]
    return np.column_stack((design.NAME_RAIL_OUTER_R * np.arctan2(x, -y), z))


def letter_pocket_facets(centroids: np.ndarray, on_rail: np.ndarray) -> np.ndarray:
    """Rail facets cut below the flat face: pocket floors, walls and ceilings.

    Also catches the chamfer round the panel's own edge, which is on the rail
    and below full radius too. That is wanted rather than tolerated — a chamfer
    is a sloped surface a millimetre wide, and fuzz on it reads as a chewed
    border rather than a texture.
    """
    cr = np.hypot(centroids[:, 0], centroids[:, 1])
    return on_rail & (cr < design.NAME_RAIL_OUTER_R - RAIL_FACE_TOL)


def rail_face_paint(centroids: np.ndarray, on_rail: np.ndarray) -> np.ndarray:
    """Which rail facets take fuzz: the flat face, less a border round each pocket.

    The rail used to be excluded whole, because the letters seat in it and the
    pockets have to stay crisp. Only the pockets have to stay crisp — the face
    between them is wall like any other, and left smooth it was the one surface
    on the stand with nothing to hide behind.
    """
    cut = letter_pocket_facets(centroids, on_rail)
    face = on_rail & ~cut
    if LETTER_POCKET_HALO <= 0.0 or not cut.any() or not face.any():
        return face
    uz = _rail_uz(centroids)
    distance, _ = cKDTree(uz[cut]).query(uz[face])
    keep = np.zeros(len(face), dtype=bool)
    keep[np.flatnonzero(face)] = distance >= LETTER_POCKET_HALO
    return keep


def paint_mask_for_mesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    root: Path,
    z_offset: float | None = None,
) -> np.ndarray:
    """Which outer-wall facets get fuzzy skin: everything but the pads and pockets.

    The name rail is fuzzed across its flat face and left smooth where the
    letters slot in — see `rail_face_paint`.

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
    on_rail = on_name_rail_plaque(centroids, rail_deg, z_offset=z_offset)
    # Off the rail, unchanged. On it, only the flat face minus its pocket border.
    return (cr >= R_PAINT_MIN) & ~in_pad & (~on_rail | rail_face_paint(centroids, on_rail))


def allow_paint_on_panel(cfg_xml: str) -> str:
    """fuzzy_skin none = Studio 'None (allow paint)'; keep thickness/distance."""
    return allow_paint_on_object(cfg_xml, PANEL_TOP_ID)


#: Painted share of paw-dish facets above which the mask is in the wrong frame.
#: A correctly registered mask leaves 0% (one-piece) to 3.8% (three-part, whose
#: panel has radial detail just above the topmost pad row); handing the mask the
#: wrong frame entirely — the bug that fuzzed 59.8% of a one-piece stand's pads —
#: paints ~42%. This catches that class with ~5x margin and does NOT catch a
#: sub-millimetre drift: the silhouettes are padded outwards, so a 1 mm shift
#: still covers every dish facet. Nothing else covers that finer line either —
#: golden_compare deliberately ignores the 3MF sha256s — so a drift small enough
#: to pass here is a drift you will first see in the slicer.
DISH_PAINTED_MAX = 0.08


def _paw_dish(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Facets on the flank of a paw recess, measured off the mesh alone.

    Unlike the pad silhouettes this cannot be fooled by a wrong z_offset, which
    is the point: every check recomputed from the same offset the mask used
    agrees with itself no matter how wrong that offset is.

    Both bounds earn their place. The radius bound is the full recess depth
    rather than "inboard of the wall" because chamfers and tongue edges also sit
    inboard. The normal bound drops the flat cut faces at the part's ends, which
    are inboard too and differ between the two layouts — leaving them in made the
    three-part and one-piece populations disagree by 848 facets.
    """
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    nz = np.abs(normals[:, 2]) / np.where(lengths > 0, lengths, 1.0)
    radius = np.hypot(tri.mean(axis=1)[:, 0], tri.mean(axis=1)[:, 1])
    return (
        (radius >= R_PAINT_MIN)
        & (radius < WALL_OUTER_R - PAW_RECESS_DEPTH + 0.15)
        & (nz < 0.5)
    )


#: A painted letter-pocket floor is never right, so the bar is zero rather than
#: a fraction. It is also the sharpest frame check on the part: the rail box is
#: placed from `z_offset`, and a mask handed the wrong frame leaves the pockets
#: outside it and paints them, while `_letter_pocket_floor` — measured off the
#: mesh alone — still knows where they are.
POCKET_PAINTED_MAX = 0.0

#: How far, across the unwrapped rail, a pocket floor may sit from rail-face
#: material before it is something else at the same radius.
#:
#: A pocket is a hole in the face, so the face is never far away: measured
#: across MAX, ROCCO and WILLIAMS the furthest any real floor facet sits from it
#: is 2.25 mm. The chamfer under the plaque runs through the same radius band
#: with the same outward normal and no face above it at all — the single facet
#: this rejects sat 5.61 mm out, and rejecting it on radius alone would have
#: meant a window too tight to hold the real floors.
POCKET_FLOOR_REACH = 3.0


def _letter_pocket_floor(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """The floors of the glyph pockets, measured off the mesh alone.

    A pocket floor is a cylinder LETTER_POCKET_DEPTH inside the rail face, so it
    is the only outward-facing surface on the whole stand at that radius: on a
    ROCCO one-piece this is 18,534 facets, every one of them inside the rail arc
    and inside the letter band, and nothing anywhere else on the part.

    Deliberately independent of `rail_outer_deg` and `z_offset`, for the reason
    `_paw_dish` is: a check recomputed from the same offset the mask used agrees
    with it however wrong that offset is.
    """
    tri = np.asarray(vertices)[np.asarray(faces)]
    centre = tri.mean(axis=1)
    radius = np.hypot(centre[:, 0], centre[:, 1])
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    outward = (normals[:, 0] * centre[:, 0] + normals[:, 1] * centre[:, 1]) / (
        np.where(lengths > 0, lengths, 1.0) * np.where(radius > 0, radius, 1.0)
    )
    # letter_pocket_cutter drops each floor by that glyph's own bulge, so the
    # band spans the widest glyph (LETTER_MAX_GLYPH_BULGE) to a notional zero.
    # Derived rather than measured: a fixed +/-0.5 mm window reached up to
    # r 83.6 and swept in one facet of the chamfer above the rail flat.
    deepest = (
        design.NAME_RAIL_OUTER_R
        - design.LETTER_MAX_GLYPH_BULGE
        - design.LETTER_POCKET_DEPTH
        - design.LETTER_POCKET_FLOOR_GAP
    )
    shallowest = (
        design.NAME_RAIL_OUTER_R
        - design.LETTER_POCKET_DEPTH
        - design.LETTER_POCKET_FLOOR_GAP
    )
    candidate = (
        (radius >= deepest - 0.05)
        & (radius <= shallowest + 0.05)
        & (outward > 0.9)
    )
    face = radius >= design.NAME_RAIL_OUTER_R - RAIL_FACE_TOL
    if not candidate.any() or not face.any():
        return np.zeros(len(candidate), dtype=bool)
    uz = _rail_uz(centre)
    distance, _ = cKDTree(uz[face]).query(uz[candidate])
    candidate[np.flatnonzero(candidate)] = distance <= POCKET_FLOOR_REACH
    return candidate


def assert_paint_ok(model_xml: str, cfg_xml: str, paint: np.ndarray, vertices, faces) -> None:
    assert_well_formed(model_xml, cfg_xml)
    if int(paint.sum()) <= 0:
        raise ValueError("painted-facet count must be > 0")
    centroids = vertices[faces].mean(axis=1)
    outer = np.hypot(centroids[:, 0], centroids[:, 1]) >= R_PAINT_MIN
    fuzzy_frac = painted_area_fraction(vertices, faces, paint, outer)
    if not (FUZZY_AREA_MIN <= fuzzy_frac <= FUZZY_AREA_MAX):
        raise ValueError(f"outer fuzzy area fraction out of range: {fuzzy_frac:.3f}")

    dish = _paw_dish(np.asarray(vertices), np.asarray(faces))
    n_dish = int(dish.sum())
    if n_dish:
        dish_frac = float((paint & dish).sum()) / n_dish
        if dish_frac > DISH_PAINTED_MAX:
            raise ValueError(
                f"{dish_frac:.1%} of paw-dish facets are painted (limit "
                f"{DISH_PAINTED_MAX:.0%}) — the pad exclusions are in a different "
                f"frame from the mesh; check the z_offset handed to the mask"
            )

    pocket = _letter_pocket_floor(np.asarray(vertices), np.asarray(faces))
    n_pocket = int(pocket.sum())
    if n_pocket:
        pocket_frac = float((paint & pocket).sum()) / n_pocket
        if pocket_frac > POCKET_PAINTED_MAX:
            raise ValueError(
                f"{pocket_frac:.1%} of letter-pocket floor facets are painted — "
                f"fuzz inside a pocket eats the {design.LETTER_POCKET_CLEARANCE} mm "
                f"clearance the letter slides on; check the rail exclusion"
            )


class CooperPaintMask:
    """The `ogma.paint.FuzzyPainter` implementation for the Cooper paw panel."""

    def mask(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        root: Path,
        z_offset: float | None = None,
    ) -> np.ndarray:
        return paint_mask_for_mesh(vertices, faces, root, z_offset=z_offset)

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
