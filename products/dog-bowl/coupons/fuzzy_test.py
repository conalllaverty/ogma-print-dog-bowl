#!/usr/bin/env python3
"""Fuzzy-skin test coupon: a cropped slice of the real paw wall, painted.

Fuzzy skin cannot be tested from an STL. The texture is not geometry — it is
per-facet paint carried in the 3MF plus slicer settings, so a coupon has to be a
project file or it prints perfectly smooth and proves nothing.

What this is for, in order:

1.  **The pad boundary.** The paint mask excludes each paw so the pads stay
    crisp, and that exclusion was sitting 1 mm below where the pads actually are
    — a fuzzed strip along one edge of every paw and a smooth strip along the
    other. It is fixed, and this is the first print that can show it.
2.  **The plaque boundary**, where fuzz meets the smooth name rail.
3.  **The texture itself** at 0.3 mm / 0.8 mm, which is the only way to judge
    whether those numbers are right.

The crop keeps the lowest paw row and the bottom of the plaque, in the same
orientation the wall prints in, so what comes off the plate is what the wall
does — not an approximation of it.

    .venv/bin/python products/dog-bowl/coupons/fuzzy_test.py
"""

from __future__ import annotations

import math
import sys
import zipfile
from pathlib import Path

COUPON_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in COUPON_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (COUPON_DIR, COUPON_DIR.parent / "generator", _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

import cooper_bowl_design as design  # noqa: E402
import paint_fuzzy_skin as fuzzy  # noqa: E402
from ogma import assets  # noqa: E402
from ogma import bambu_project as bambu  # noqa: E402
from ogma.paint import paint_triangle_xml  # noqa: E402

OUT = _REPO / "out" / "coupons"

# Assembly-frame crop. Wide enough to cross the plaque's edge, tall enough for
# the lowest paw row plus the bottom of the plaque — the two boundaries worth
# looking at — and no taller, because this is meant to be a quick print.
CROP_Z0, CROP_Z1 = 13.0, 40.0
CROP_FROM_DEG, CROP_TO_DEG = 6.0, 66.0


def _crop(panel: trimesh.Trimesh) -> trimesh.Trimesh:
    keep = design.annular_sector(
        design.WALL_INNER_R - 2.0,
        design.NAME_RAIL_OUTER_R + 4.0,
        CROP_Z0,
        CROP_Z1,
        math.radians(CROP_FROM_DEG),
        math.radians(CROP_TO_DEG),
        segments=96,
    )
    piece = trimesh.boolean.intersection([panel, keep], engine="manifold")
    if piece is None or piece.is_empty:
        raise RuntimeError("fuzzy-test crop produced an empty mesh")
    piece.metadata["name"] = "Fuzzy_Test_Wall_Coupon"
    return piece


def build() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    design.configure_output(OUT / "_fuzzy_scratch", name="AB", font_style="bold")
    letters = design.build_letters()
    panel = design.build_panel(letters)
    piece = _crop(panel)

    # Painted in ASSEMBLY coordinates, with the offset stated rather than
    # derived. The mask normally infers its frame from the mesh's lowest point,
    # which is the panel's bottom — true for the whole panel, false for a slice
    # cut out of the middle of it. Deriving it here would reintroduce exactly the
    # misalignment this coupon exists to check.
    vertices = np.asarray(piece.vertices)
    faces = np.asarray(piece.faces)
    paint = fuzzy.paint_mask_for_mesh(vertices, faces, OUT / "_fuzzy_scratch", z_offset=0.0)

    outer = np.hypot(
        vertices[faces].mean(axis=1)[:, 0], vertices[faces].mean(axis=1)[:, 1]
    ) >= fuzzy.R_PAINT_MIN
    print(f"  painted {int(paint.sum())} of {int(outer.sum())} outer-wall facets")

    # Stand it up the way the wall prints, on its lower cut face.
    piece.apply_translation([0.0, 0.0, -float(piece.bounds[0, 2])])

    bambu.MESH_DIR = OUT
    bambu.OBJECTS = [("Fuzzy test wall", OUT / "fuzzy_test.stl", 1)]
    bambu.BUILD_POSITIONS = [(128.0, 128.0, 0.0)]
    bambu.BODY_COUNT = 1
    output = OUT / "fuzzy_test.3mf"

    with (
        zipfile.ZipFile(assets.BLANK_PROJECT) as template,
        zipfile.ZipFile(assets.PLATE_PREVIEWS / "cooper_panel_plate.3mf") as preview,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as out,
    ):
        out.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        out.writestr("_rels/.rels", template.read("_rels/.rels"))
        out.writestr("3D/3dmodel.model", bambu.top_model())
        out.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())

        model_xml = bambu.mesh_model(piece, 1, paint_fuzzy=None).decode()
        out.writestr("3D/Objects/object_1.model", paint_triangle_xml(model_xml, paint).encode())

        cfg = bambu.model_settings([piece]).decode()
        # "none" is Studio's *None (allow paint)* — it is what lets the painted
        # facets fuzz while the rest of the object stays smooth. Set to anything
        # else and the paint is ignored.
        cfg = cfg.replace('key="fuzzy_skin" value="external"', 'key="fuzzy_skin" value="none"')
        out.writestr("Metadata/model_settings.config", cfg.encode())

        import json as _json

        settings = _json.loads(template.read("Metadata/project_settings.config"))
        settings["fuzzy_skin"] = "none"
        settings["fuzzy_skin_thickness"] = "0.3"
        settings["fuzzy_skin_point_distance"] = "0.8"
        settings["fuzzy_skin_first_layer"] = "0"
        settings["wall_loops"] = "4"
        settings["filament_colour"] = ["#757575", "#757575"]
        out.writestr(
            "Metadata/project_settings.config",
            _json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for name in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            out.writestr(name, template.read(name))
        for stem in ("plate", "plate_no_light", "top", "pick"):
            out.writestr(f"Metadata/{stem}_1.png", preview.read(f"Metadata/{stem}_1.png"))

    bambu.assert_object_id_hygiene(zipfile.ZipFile(output))
    lo, hi = piece.bounds
    print(f"  {output.relative_to(_REPO)}")
    print(f"    {hi[0]-lo[0]:.0f} x {hi[1]-lo[1]:.0f} x {hi[2]-lo[2]:.0f} mm, "
          f"{piece.volume/1000:.1f} cm3, watertight={piece.is_watertight}")
    return output


if __name__ == "__main__":
    build()
