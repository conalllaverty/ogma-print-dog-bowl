#!/usr/bin/env python3
"""Letter-fit test coupon: cropped name-rail panel + letters only.

Cuts the tall paw panel down to the name-rail Z band and a front angular
sector so you can print pockets + letters without the full cylinder.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

GENERATOR_DIR = Path(__file__).resolve().parent
BACKEND_DIR = GENERATOR_DIR.parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import numpy as np
import trimesh

import build_bambu_project as bambu
import cooper_bowl_design as design
from pipeline import (
    DEFAULT_LETTERS,
    DEFAULT_STAND,
    FONT_STYLES,
    GenerateResult,
    load_palette,
    resolve_filament,
)


def _letter_test_bounds() -> tuple[float, float, float]:
    """Return (z0, z1, half_angle_rad) for the coupon keep-region."""
    z0 = design.NAME_RAIL_FLAT_Z0 - 2.5
    z1 = design.NAME_RAIL_FLAT_Z1 + 2.5
    half = math.radians(design.NAME_RAIL_OUTER_DEG + 14.0)
    return z0, z1, half


def crop_panel_letter_coupon(panel: trimesh.Trimesh) -> trimesh.Trimesh:
    """Keep only the name-rail band (drop top/bottom cylinder) and front arc."""
    z0, z1, half = _letter_test_bounds()
    keep = design.annular_sector(
        design.WALL_INNER_R - 2.5,
        design.NAME_RAIL_OUTER_R + 8.0,
        z0,
        z1,
        -half,
        half,
        segments=72,
    )
    cropped = trimesh.boolean.intersection([panel, keep], engine="manifold")
    if cropped is None or cropped.is_empty:
        raise RuntimeError("Letter-test crop produced an empty mesh")
    cropped = cropped.copy()
    cropped.remove_unreferenced_vertices()
    # Print upright on the lower cut face (same wall orientation as full panel).
    cropped.apply_translation([0.0, 0.0, -float(cropped.bounds[0, 2])])
    if not cropped.is_watertight:
        cropped.fill_holes()
        cropped.remove_unreferenced_vertices()
    cropped.metadata["name"] = "Letter_Test_Rail_Coupon"
    return cropped


def build_letter_test_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    name: str,
    stand_hex: str,
    letter_hex: str,
    stand_name: str,
    letter_name: str,
    coupon_filename: str = "letter_test_rail_coupon.stl",
    coupon_label: str = "letter-test rail",
) -> Path:
    """Two-plate 3MF: rail coupon + letters."""
    mesh_dir = Path(mesh_dir)
    output_path = Path(output_path)
    name = name.upper()

    coupon_path = mesh_dir / coupon_filename
    objects: list[tuple[str, Path, int]] = [
        (f"{name} {coupon_label}", coupon_path, 1),
    ]
    seen: dict[str, int] = {}
    for index, ch in enumerate(name, start=1):
        seen[ch] = seen.get(ch, 0) + 1
        label = f"Letter {ch}" if seen[ch] == 1 else f"Letter {ch} {seen[ch]}"
        objects.append((label, mesh_dir / f"letter_{index}_{ch}.stl", 2))

    bambu.OBJECTS = objects
    # Plate 1 ~(128,128); plate 2 to the right ~(440,128).
    positions: list[tuple[float, float, float]] = [(128.0, 128.0, 0.0)]
    x0, y0 = 392.0, 96.0
    cols = 4
    for i in range(len(name)):
        positions.append((x0 + (i % cols) * 24.0, y0 + (i // cols) * 32.0, 0.0))
    bambu.BUILD_POSITIONS = positions
    bambu.OUTPUT = output_path
    bambu.WORK = GENERATOR_DIR / "bambu_work"
    bambu.TEMPLATE = GENERATOR_DIR / "blank_project.3mf"
    bambu.MESH_DIR = mesh_dir

    meshes = []
    for _, path, _ in objects:
        mesh = trimesh.load_mesh(path, process=True)
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold printable mesh: {path}")
        meshes.append(mesh)

    work = bambu.WORK
    with (
        zipfile.ZipFile(bambu.TEMPLATE) as template,
        zipfile.ZipFile(work / "cooper_panel_plate.3mf") as panel_preview,
        zipfile.ZipFile(work / "cooper_letters_plate.3mf") as letter_preview,
        zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
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

        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
        for index, ((obj_name, source, extruder), mesh) in enumerate(
            zip(objects, meshes), start=1
        ):
            top_id = 99 + index
            if index == 1:
                overrides = {
                    "layer_height": "0.16",
                    "wall_loops": "4",
                    "sparse_infill_density": "15%",
                    "sparse_infill_pattern": "gyroid",
                    "outer_wall_speed": "100",
                    "inner_wall_speed": "200",
                    "seam_position": "back",
                    "fuzzy_skin": "none",
                }
            else:
                overrides = {
                    "layer_height": "0.10",
                    "wall_loops": "4",
                    "sparse_infill_density": "15%",
                    "sparse_infill_pattern": "gyroid",
                    "outer_wall_speed": "50",
                    "inner_wall_speed": "100",
                    "small_perimeter_speed": "50%",
                    "top_shell_layers": "6",
                    "bottom_shell_layers": "5",
                    "seam_position": "back",
                    "fuzzy_skin": "none",
                }
            lines.extend(
                [
                    f'  <object id="{top_id}">',
                    f'    <metadata key="name" value="{escape(obj_name)}"/>',
                    f'    <metadata key="extruder" value="{extruder}"/>',
                    *[
                        f'    <metadata key="{key}" value="{value}"/>'
                        for key, value in overrides.items()
                    ],
                    f'    <metadata face_count="{len(mesh.faces)}"/>',
                    f'    <part id="{index}" subtype="normal_part">',
                    f'      <metadata key="name" value="{escape(obj_name)}"/>',
                    '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                    f'      <metadata key="source_file" value="{escape(source.name)}"/>',
                    f'      <metadata key="extruder" value="{extruder}"/>',
                    f'      <mesh_stat face_count="{len(mesh.faces)}" edges_fixed="0" '
                    'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                    "    </part>",
                    "  </object>",
                ]
            )

        def plate(number: int, title: str, object_indices: list[int]) -> list[str]:
            result = [
                "  <plate>",
                f'    <metadata key="plater_id" value="{number}"/>',
                f'    <metadata key="plater_name" value="{title}"/>',
                '    <metadata key="locked" value="false"/>',
                f'    <metadata key="thumbnail_file" value="Metadata/plate_{number}.png"/>',
                f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{number}.png"/>',
                f'    <metadata key="top_file" value="Metadata/top_{number}.png"/>',
                f'    <metadata key="pick_file" value="Metadata/pick_{number}.png"/>',
            ]
            for object_index in object_indices:
                result.extend(
                    [
                        "    <model_instance>",
                        f'      <metadata key="object_id" value="{99 + object_index}"/>',
                        '      <metadata key="instance_id" value="0"/>',
                        f'      <metadata key="identify_id" value="{299 + object_index}"/>',
                        "    </model_instance>",
                    ]
                )
            result.append("  </plate>")
            return result

        lines.extend(plate(1, f"{name} {coupon_label}", [1]))
        lines.extend(plate(2, f"{name} letters", list(range(2, len(objects) + 1))))
        lines.append("  <assemble>")
        for index in range(1, len(objects) + 1):
            lines.append(
                f'    <assemble_item object_id="{99 + index}" instance_id="0" '
                'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
            )
        lines.extend(["  </assemble>", "</config>"])
        output.writestr("Metadata/model_settings.config", ("\n".join(lines) + "\n").encode())

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        settings["filament_colour"] = [stand_hex, letter_hex]
        settings["default_filament_colour"] = ["", ""]
        settings["filament_settings_id"] = [
            f"Bambu PLA Matte @Ogma {stand_name}",
            f"Bambu PLA Matte @Ogma {letter_name}",
        ]
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))

        for plate_number, preview in enumerate((panel_preview, letter_preview), start=1):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )

    bambu.assert_object_id_hygiene(zipfile.ZipFile(output_path))
    return output_path


def generate_letter_test(
    name: str,
    job_dir: Path,
    *,
    font_style: str = "bold",
    stand_filament_id: str = DEFAULT_STAND,
    letter_filament_id: str = DEFAULT_LETTERS,
) -> GenerateResult:
    """Build a fast letter-fit test 3MF (cropped rail + letters)."""
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    meshes = job_dir / "meshes"
    if meshes.exists():
        shutil.rmtree(meshes)
    meshes.mkdir(parents=True)

    palette = load_palette()
    stand = resolve_filament(stand_filament_id, palette)
    letters_fil = resolve_filament(letter_filament_id, palette)

    design.configure_output(job_dir, name=name, font_style=font_style)
    cleaned = design.NAME

    letter_data = design.build_letters()
    panel = design.build_panel(letter_data)
    coupon = crop_panel_letter_coupon(panel)
    coupon.export(meshes / "letter_test_rail_coupon.stl")

    for index, item in enumerate(letter_data, start=1):
        item["mesh"].export(meshes / f"letter_{index}_{item['character']}.stl")

    dims = {
        "test": "letter_fit_coupon",
        "name": cleaned,
        "font_style": font_style,
        "z_band_mm": [_letter_test_bounds()[0], _letter_test_bounds()[1]],
        "half_angle_deg": math.degrees(_letter_test_bounds()[2]),
        "coupon_bounds": coupon.bounds.round(3).tolist(),
        "letters": {
            "height": design.LETTER_HEIGHT,
            "proud_thickness": design.LETTER_THICKNESS,
            "pocket_outline_clearance": design.LETTER_POCKET_CLEARANCE,
            "name_rail_outer_deg": design.NAME_RAIL_OUTER_DEG,
        },
    }
    dims_path = job_dir / "dimensions_and_validation.json"
    dims_path.write_text(json.dumps(dims, indent=2) + "\n")

    output = job_dir / f"{cleaned}_Letter_Test_P2S.3mf"
    build_letter_test_project(
        mesh_dir=meshes,
        output_path=output,
        name=cleaned,
        stand_hex=stand.hex,
        letter_hex=letters_fil.hex,
        stand_name=stand.name,
        letter_name=letters_fil.name,
    )

    meta = {
        "name": cleaned,
        "font_style": font_style,
        "stand_filament_id": stand.id,
        "letter_filament_id": letters_fil.id,
        "threemf": output.name,
        "kind": "letter_test",
    }
    (job_dir / "job.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(output)
    return GenerateResult(
        name=cleaned,
        font_style=font_style,
        stand=stand,
        letters=letters_fil,
        job_dir=job_dir,
        threemf_path=output,
        dimensions_path=dims_path,
        rail_outer_deg=float(design.NAME_RAIL_OUTER_DEG),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a letter-fit test 3MF")
    parser.add_argument("--name", default="COOPER")
    parser.add_argument("--font-style", default="bold", choices=FONT_STYLES)
    parser.add_argument("--stand", default="matte-ash-gray")
    parser.add_argument("--letters", default="matte-ivory-white")
    parser.add_argument("--out", type=Path, default=Path("data/jobs/letter-test"))
    args = parser.parse_args()
    generate_letter_test(
        args.name,
        args.out,
        font_style=args.font_style,
        stand_filament_id=args.stand,
        letter_filament_id=args.letters,
    )
