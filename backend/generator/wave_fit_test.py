#!/usr/bin/env python3
"""Print-ready Wave collar/sleeve fit test.

Produces two short full rings using the production Wave radii:
1. Lower collar with its 1.2 mm locating chamfer.
2. Upper sleeve with the locked 0.5 mm/side radial clearance.

The full circumference captures real circular shrinkage while using far less
filament than either complete body half.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh

GENERATOR_DIR = Path(__file__).resolve().parent
BACKEND_DIR = GENERATOR_DIR.parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import build_bambu_project as bambu  # noqa: E402
from geometry_config import WAVE, wave_derived  # noqa: E402
from pipeline import DEFAULT_STAND, load_palette, resolve_filament  # noqa: E402


COUPON_HEIGHT = 12.0
COLLAR_WALL = 2.4
SLEEVE_WALL = 2.2


def _revolved_ring(profile: list[list[float]], name: str) -> trimesh.Trimesh:
    mesh = trimesh.creation.revolve(np.asarray(profile), sections=192)
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight or not mesh.is_volume:
        raise RuntimeError(f"{name} coupon is not a watertight volume")
    mesh.metadata["name"] = name
    return mesh


def build_fit_coupons() -> tuple[trimesh.Trimesh, trimesh.Trimesh, dict]:
    """Return lower collar, upper sleeve, and dimensional report."""
    derived = wave_derived()
    collar_outer = float(derived["rc"])
    collar_inner = collar_outer - COLLAR_WALL

    lower = _revolved_ring(
        [
            [collar_inner, 0.0],
            [collar_outer, 0.0],
            [collar_outer, COUPON_HEIGHT - 1.2],
            [collar_outer - 1.2, COUPON_HEIGHT],
            [collar_inner, COUPON_HEIGHT],
            [collar_inner, 0.0],
        ],
        "Wave_Lower_Collar_Fit_Coupon",
    )

    sleeve_inner = collar_outer + WAVE.collar_clearance
    sleeve_outer = sleeve_inner + SLEEVE_WALL
    upper = _revolved_ring(
        [
            [sleeve_inner, 0.0],
            [sleeve_outer, 0.0],
            [sleeve_outer, COUPON_HEIGHT],
            [sleeve_inner, COUPON_HEIGHT],
            [sleeve_inner, 0.0],
        ],
        "Wave_Upper_Sleeve_Fit_Coupon",
    )

    report = {
        "test": "Wave collar radial fit",
        "units": "mm",
        "coupon_height": COUPON_HEIGHT,
        "lower": {
            "outer_radius": collar_outer,
            "inner_radius": collar_inner,
            "wall": COLLAR_WALL,
            "top_chamfer": 1.2,
            "volume_mm3": float(lower.volume),
        },
        "upper": {
            "inner_radius": sleeve_inner,
            "outer_radius": sleeve_outer,
            "wall": SLEEVE_WALL,
            "volume_mm3": float(upper.volume),
        },
        "nominal_clearance_per_side": WAVE.collar_clearance,
        "diametral_clearance": 2.0 * WAVE.collar_clearance,
        "acceptance": (
            "Upper sleeve starts over the chamfer by hand, seats without tools, "
            "has no visible rocking, and can be separated before gluing."
        ),
    }
    return lower, upper, report


def _model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    overrides = {
        "layer_height": "0.16",
        "wall_loops": "4",
        "sparse_infill_density": "15%",
        "sparse_infill_pattern": "gyroid",
        "outer_wall_speed": "60",
        "inner_wall_speed": "100",
        "small_perimeter_speed": "50%",
        "bottom_surface_pattern": "monotonic",
        "top_surface_pattern": "monotonicline",
        "seam_position": "back",
        "fuzzy_skin": "none",
    }
    for index, ((name, source, extruder), mesh) in enumerate(
        zip(objects, meshes), start=1
    ):
        top_id = 99 + index
        lines.extend(
            [
                f'  <object id="{top_id}">',
                f'    <metadata key="name" value="{escape(name)}"/>',
                f'    <metadata key="extruder" value="{extruder}"/>',
                *[
                    f'    <metadata key="{key}" value="{value}"/>'
                    for key, value in overrides.items()
                ],
                f'    <metadata face_count="{len(mesh.faces)}"/>',
                f'    <part id="{index}" subtype="normal_part">',
                f'      <metadata key="name" value="{escape(name)}"/>',
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'      <metadata key="source_file" value="{escape(source.name)}"/>',
                f'      <metadata key="source_object_id" value="{index - 1}"/>',
                f'      <metadata key="source_volume_id" value="{index - 1}"/>',
                f'      <metadata key="extruder" value="{extruder}"/>',
                f'      <mesh_stat face_count="{len(mesh.faces)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                "    </part>",
                "  </object>",
            ]
        )

    for plate_number, (title, object_index) in enumerate(
        (("Lower collar fit coupon", 1), ("Upper sleeve fit coupon", 2)),
        start=1,
    ):
        lines.extend(
            [
                "  <plate>",
                f'    <metadata key="plater_id" value="{plate_number}"/>',
                f'    <metadata key="plater_name" value="{title}"/>',
                '    <metadata key="locked" value="false"/>',
                '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
                f'    <metadata key="thumbnail_file" value="Metadata/plate_{plate_number}.png"/>',
                f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{plate_number}.png"/>',
                f'    <metadata key="top_file" value="Metadata/top_{plate_number}.png"/>',
                f'    <metadata key="pick_file" value="Metadata/pick_{plate_number}.png"/>',
                "    <model_instance>",
                f'      <metadata key="object_id" value="{99 + object_index}"/>',
                '      <metadata key="instance_id" value="0"/>',
                f'      <metadata key="identify_id" value="{299 + object_index}"/>',
                "    </model_instance>",
                "  </plate>",
            ]
        )
    lines.extend(
        [
            "  <assemble>",
            '    <assemble_item object_id="100" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>',
            '    <assemble_item object_id="101" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>',
            "  </assemble>",
            "</config>",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def build_fit_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    stand_hex: str,
    stand_name: str,
) -> Path:
    """Package the two full-ring coupons as separate Bambu plates."""
    objects: list[tuple[str, Path, int]] = [
        ("Wave lower collar fit coupon", mesh_dir / "wave_lower_collar_coupon.stl", 1),
        ("Wave upper sleeve fit coupon", mesh_dir / "wave_upper_sleeve_coupon.stl", 1),
    ]
    bambu.OBJECTS = objects
    bambu.BUILD_POSITIONS = [(128.0, 128.0, 0.0), (440.0, 128.0, 0.0)]

    meshes = [trimesh.load_mesh(path, process=True) for _, path, _ in objects]
    for (_, path, _), mesh in zip(objects, meshes):
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold fit coupon: {path}")

    template_path = GENERATOR_DIR / "blank_project.3mf"
    work = GENERATOR_DIR / "bambu_work"
    with (
        zipfile.ZipFile(template_path) as template,
        zipfile.ZipFile(work / "cooper_base_plate.3mf") as lower_preview,
        zipfile.ZipFile(work / "cooper_top_ring_plate.3mf") as upper_preview,
        zipfile.ZipFile(
            output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7
        ) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", bambu.top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr(
            "Metadata/model_settings.config",
            _model_settings(objects, meshes),
        )

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["layer_height"] = "0.16"
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        settings["filament_colour"] = [stand_hex]
        settings["default_filament_colour"] = [""]
        settings["filament_settings_id"] = [
            f"Bambu PLA Matte @Ogma {stand_name}",
        ]
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))

        for plate_number, preview in enumerate(
            (lower_preview, upper_preview), start=1
        ):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
    return output_path


def generate_fit_test(job_dir: Path, stand_filament_id: str = DEFAULT_STAND) -> Path:
    """Generate STL coupons, report, and two-plate 3MF."""
    job_dir = Path(job_dir)
    mesh_dir = job_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    lower, upper, report = build_fit_coupons()
    lower.export(mesh_dir / "wave_lower_collar_coupon.stl")
    upper.export(mesh_dir / "wave_upper_sleeve_coupon.stl")
    (job_dir / "dimensions_and_acceptance.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    stand = resolve_filament(stand_filament_id, load_palette())
    output = job_dir / "Wave_Collar_Fit_Test_P2S.3mf"
    build_fit_project(
        mesh_dir=mesh_dir,
        output_path=output,
        stand_hex=stand.hex,
        stand_name=stand.name,
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Wave collar fit test")
    parser.add_argument("--stand", default=DEFAULT_STAND)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(generate_fit_test(args.out, stand_filament_id=args.stand))
