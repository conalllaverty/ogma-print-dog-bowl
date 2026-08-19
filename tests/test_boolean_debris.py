"""A boolean shard must not be able to reach the plate.

manifold occasionally leaves a zero-volume sheet beside the solid it just cut.
It is invisible and weighs nothing, but it makes the exported STL non-manifold,
and the 3MF packaging check rejects the whole part — so a panel that is exactly
right never gets printed. 'WILLIAMS' in Robust Slab is the case that found it.

Run:  .venv/bin/python -m pytest tests/test_boolean_debris.py -q
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "products" / "dog-bowl" / "generator"))
sys.path.insert(0, str(REPO / "shared"))

import cooper_bowl_design as C  # noqa: E402


def sheet(z: float = 31.3) -> trimesh.Trimesh:
    """Two triangles, no thickness — the shape manifold actually leaves."""
    v = np.array([[80.0, 2.0, z], [81.7, 2.0, z], [81.7, 4.56, z], [80.0, 4.56, z]])
    return trimesh.Trimesh(vertices=v, faces=np.array([[0, 1, 2], [0, 2, 3]]), process=False)


def test_a_zero_volume_shard_is_dropped():
    solid = trimesh.creation.box(extents=(10, 10, 10))
    combined = trimesh.util.concatenate([solid, sheet()])
    cleaned = C.drop_boolean_debris(combined)
    assert cleaned.volume == pytest.approx(1000.0)
    welded = cleaned.copy()
    welded.merge_vertices()
    assert welded.is_watertight
    assert len(welded.split(only_watertight=False)) == 1


def test_the_panel_that_found_this_survives_the_round_trip():
    """The real case, end to end, because the synthetic one cannot be faithful.

    As manifold returns it the panel is one body and `is_watertight` is True —
    the shard is hidden until vertices are merged by position, which is what
    `trimesh.load_mesh(..., process=True)` does on the way into the 3MF. So the
    only check that catches it is the one that welds first, which means the only
    honest test is the mesh that produced it.

    Slow (~40 s): it builds eight glyphs and the panel's full boolean stack.
    """
    with tempfile.TemporaryDirectory() as td:
        C.configure_output(td, name="WILLIAMS", font_style="slab")
        panel = C.build_panel(C.build_letters())
        out = Path(td) / "panel.stl"
        panel.export(out)
        # process=True is the point: this is the load the packaging step does.
        assert trimesh.load_mesh(out, process=True).is_watertight


def test_a_clean_mesh_is_returned_untouched():
    """Byte-for-byte the same object, so no existing geometry moves."""
    solid = trimesh.creation.box(extents=(10, 10, 10))
    assert C.drop_boolean_debris(solid) is solid


def test_two_real_solids_both_survive():
    """A letter with a tittle is two bodies on purpose — see glyph_parts."""
    a = trimesh.creation.box(extents=(10, 10, 10))
    b = trimesh.creation.box(extents=(2, 2, 2))
    b.apply_translation([40.0, 0.0, 0.0])
    cleaned = C.drop_boolean_debris(trimesh.util.concatenate([a, b]))
    assert cleaned.volume == pytest.approx(1008.0)
    assert len(cleaned.split(only_watertight=False)) == 2
