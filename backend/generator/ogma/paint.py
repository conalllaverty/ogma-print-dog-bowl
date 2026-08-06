"""Fuzzy-skin triangle painting for Bambu 3MF projects.

Generic half of what used to be `paint_fuzzy_skin.py`. This module manipulates
3MF XML and measures painted area; it knows nothing about paws, name rails or
any particular product. A product supplies a `FuzzyPainter` describing which
facets to paint and what a correct result looks like.

Why this exists: `build_bambu_project` imported `paint_fuzzy_skin`, which
imported `cooper_bowl_design`. Every lamp, spinner and clicker that built a 3MF
therefore imported the dog bowl transitively.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Protocol

import numpy as np

PAINT_ATTR = ' paint_fuzzy_skin="4"'


class FuzzyPainter(Protocol):
    """What a product must provide to have facets painted."""

    def mask(self, vertices: np.ndarray, faces: np.ndarray, root: Path) -> np.ndarray:
        """Boolean array, one entry per face, True = paint fuzzy skin here."""
        ...

    def verify(
        self,
        model_xml: str,
        cfg_xml: str,
        paint: np.ndarray,
        vertices: np.ndarray,
        faces: np.ndarray,
    ) -> None:
        """Raise if the painted result is wrong. Called on the packaged 3MF."""
        ...


def paint_triangle_xml(model_xml: str, paint: np.ndarray) -> str:
    """Add the paint attribute to each triangle whose mask entry is True."""
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


def allow_paint_on_object(cfg_xml: str, object_id: str) -> str:
    """fuzzy_skin "none" = Studio's "None (allow paint)".

    Keeps thickness / point-distance, which still drive the painted fuzz.
    "disabled_fuzzy" would kill painting entirely.
    """
    a = cfg_xml.index(f'<object id="{object_id}">')
    b = cfg_xml.index("</object>", a)
    blk = cfg_xml[a:b].replace(
        'key="fuzzy_skin" value="external"',
        'key="fuzzy_skin" value="none"',
        1,
    )
    return cfg_xml[:a] + blk + cfg_xml[b:]


def face_areas(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    a, b, c = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def painted_area_fraction(
    vertices: np.ndarray, faces: np.ndarray, paint: np.ndarray, subset: np.ndarray
) -> float:
    """Fraction of `subset`'s area that is painted. Area-weighted, not face-counted:
    a mesh with many tiny facets in one region would otherwise skew the count."""
    area = face_areas(vertices, faces)
    sa, sp = area[subset], paint[subset]
    return float(sa[sp].sum() / sa.sum())


def assert_well_formed(model_xml: str, cfg_xml: str) -> None:
    """Both payloads must still parse as XML after string surgery."""
    ET.fromstring(model_xml)
    ET.fromstring(cfg_xml)


def paint_object_model_bytes(
    model_xml: bytes,
    vertices: np.ndarray,
    faces: np.ndarray,
    root: Path,
    painter: FuzzyPainter,
) -> tuple[bytes, np.ndarray]:
    paint = painter.mask(vertices, faces, root)
    return paint_triangle_xml(model_xml.decode(), paint).encode(), paint
