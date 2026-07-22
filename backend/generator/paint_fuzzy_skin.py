#!/usr/bin/env python3
"""Paint fuzzy skin onto the Cooper paw panel — no modifiers, no new objects.

Outer-wall facets outside the paw silhouettes get `paint_fuzzy_skin="4"`
(TriangleSelector leaf, state 1). The panel object's fuzzy_skin is set to
"none" ("None (allow paint)"); thickness / point-distance still drive the
painted fuzz. Inner skin (r < 79.5) is left unpainted.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from shapely.geometry import Point
from shapely.strtree import STRtree

from cooper_bowl_design import (
    LATTICE_BOTTOM,
    NAME_RAIL_FLAT_Z0,
    NAME_RAIL_FLAT_Z1,
    NAME_RAIL_OUTER_DEG,
    WALL_OUTER_R,
    paw_paint_silhouettes,
    unwrap_cylinder_u,
)

CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
OBJ_FILE = "3D/Objects/object_2.model"
CFG_FILE = "Metadata/model_settings.config"
R_PAINT_MIN = 79.5
PAINT_ATTR = ' paint_fuzzy_skin="4"'
PANEL_TOP_ID = "101"


def rail_outer_deg(root: Path) -> float:
    candidates = [
        root / "dimensions_and_validation.json",
        root / "cooper_dog_bowl" / "dimensions_and_validation.json",
    ]
    for dims in candidates:
        if dims.is_file():
            data = json.loads(dims.read_text())
            return float(data["letters"]["name_rail_outer_deg"])
    return float(NAME_RAIL_OUTER_DEG)


def on_name_rail_plaque(centroids: np.ndarray, rail_deg: float) -> np.ndarray:
    """True for facets on the proud name-rail face (keep smooth for letter pockets)."""
    x, y, z = centroids[:, 0], centroids[:, 1], centroids[:, 2]
    cr = np.hypot(x, y)
    # Design front is -Y; plaque angles match build_panel / beveled_name_rail.
    theta_deg = np.degrees(np.arctan2(x, -y))
    z_lo = NAME_RAIL_FLAT_Z0 - LATTICE_BOTTOM - 2.0
    z_hi = NAME_RAIL_FLAT_Z1 - LATTICE_BOTTOM + 2.0
    return (
        (cr >= WALL_OUTER_R + 0.35)
        & (np.abs(theta_deg) <= rail_deg + 1.0)
        & (z >= z_lo)
        & (z <= z_hi)
    )


def paint_mask_for_mesh(vertices: np.ndarray, faces: np.ndarray, root: Path) -> np.ndarray:
    rail_deg = rail_outer_deg(root)
    polys = paw_paint_silhouettes(
        z_offset=LATTICE_BOTTOM,
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
    on_plaque = on_name_rail_plaque(centroids, rail_deg)
    return (cr >= R_PAINT_MIN) & ~in_pad & ~on_plaque


def paint_triangle_xml(model_xml: str, paint: np.ndarray) -> str:
    lines = model_xml.split("\n")
    t0 = next(i for i, line in enumerate(lines) if "<triangles>" in line) + 1
    t1 = next(i for i, line in enumerate(lines) if "</triangles>" in line)
    if t1 - t0 != len(paint):
        raise ValueError(f"triangle/paint length mismatch: {t1 - t0} vs {len(paint)}")
    for k in range(t0, t1):
        if paint[k - t0]:
            if "paint_fuzzy_skin" not in lines[k]:
                lines[k] = lines[k].replace("/>", PAINT_ATTR + "/>")
    return "\n".join(lines)


def allow_paint_on_panel(cfg_xml: str) -> str:
    """fuzzy_skin none = Studio 'None (allow paint)'; keep thickness/distance."""
    a = cfg_xml.index(f'<object id="{PANEL_TOP_ID}">')
    b = cfg_xml.index("</object>", a)
    blk = cfg_xml[a:b].replace(
        'key="fuzzy_skin" value="external"',
        'key="fuzzy_skin" value="none"',
        1,
    )
    if 'key="fuzzy_skin" value="none"' not in blk:
        # Already none, or write path set it — ensure thickness keys remain.
        pass
    return cfg_xml[:a] + blk + cfg_xml[b:]


def assert_paint_ok(model_xml: str, cfg_xml: str, paint: np.ndarray, vertices, faces) -> None:
    ET.fromstring(model_xml)
    ET.fromstring(cfg_xml)
    if int(paint.sum()) <= 0:
        raise ValueError("painted-facet count must be > 0")
    centroids = vertices[faces].mean(axis=1)
    cr = np.hypot(centroids[:, 0], centroids[:, 1])
    outer = cr >= R_PAINT_MIN
    a = vertices[faces[:, 0]]
    b = vertices[faces[:, 1]]
    c = vertices[faces[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    oa = area[outer]
    op = paint[outer]
    fuzzy_frac = float(oa[op].sum() / oa.sum())
    if not (0.55 <= fuzzy_frac <= 0.85):
        raise ValueError(f"outer fuzzy area fraction out of range: {fuzzy_frac:.3f}")


def paint_object_model_bytes(
    model_xml: bytes,
    vertices: np.ndarray,
    faces: np.ndarray,
    root: Path,
) -> tuple[bytes, np.ndarray]:
    paint = paint_mask_for_mesh(vertices, faces, root)
    txt = paint_triangle_xml(model_xml.decode(), paint)
    return txt.encode(), paint
