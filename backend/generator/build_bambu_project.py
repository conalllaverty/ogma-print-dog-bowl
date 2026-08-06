#!/usr/bin/env python3
"""Build a native, externally-referenced four-plate Bambu Studio 3MF.

This follows the package structure used by known-good local Bambu projects:
each embedded object has one mesh resource and no nested <build> element.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh

from ogma.paint import FuzzyPainter


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "cooper_dog_bowl"
MESH_DIR = OUT / "meshes"
WORK = OUT / "bambu_work"
TEMPLATE = ROOT / "blank_project.3mf"
OUTPUT = OUT / "Cooper_Paw_Lattice_P2S.3mf"

# Mutated by build_project() for each job.
OBJECTS: list[tuple[str, Path, int]] = []
BUILD_POSITIONS: list[tuple[float, float, float]] = []

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
BAMBU = "http://schemas.bambulab.com/package/2021"


def configure_objects(mesh_dir: Path, name: str) -> None:
    """Build OBJECTS + BUILD_POSITIONS for the Cooper paw-lattice layout."""
    global OBJECTS, BUILD_POSITIONS, MESH_DIR
    MESH_DIR = Path(mesh_dir)
    objects: list[tuple[str, Path, int]] = [
        (f"{name} bowl base", MESH_DIR / "cooper_base.stl", 1),
        (f"{name} paw panel", MESH_DIR / "cooper_paw_panel.stl", 1),
        (f"{name} top seat ring", MESH_DIR / "cooper_top_seat_ring.stl", 1),
    ]
    # Deduplicate display labels when the same letter appears twice.
    seen: dict[str, int] = {}
    for index, ch in enumerate(name, start=1):
        seen[ch] = seen.get(ch, 0) + 1
        label = f"Letter {ch}" if seen[ch] == 1 else f"Letter {ch} {seen[ch]}"
        objects.append((label, MESH_DIR / f"letter_{index}_{ch}.stl", 2))
    OBJECTS = objects

    positions: list[tuple[float, float, float]] = [
        (128.0, 128.0, 0.0),
        (440.0, 128.0, 0.0),
        (128.0, -184.0, 0.0),
    ]
    x0, y0 = 405.0, -196.0
    cols = 4
    for i in range(len(name)):
        positions.append((x0 + (i % cols) * 24.0, y0 + (i // cols) * 32.0, 0.0))
    BUILD_POSITIONS = positions


def configure_wave_objects(mesh_dir: Path, name: str) -> None:
    """Build OBJECTS + BUILD_POSITIONS for the split wave layout."""
    global OBJECTS, BUILD_POSITIONS, MESH_DIR
    MESH_DIR = Path(mesh_dir)
    objects: list[tuple[str, Path, int]] = [
        (f"{name} wave lower", MESH_DIR / "wave_lower.ply", 1),
        (f"{name} wave upper shell — print inverted", MESH_DIR / "wave_upper.ply", 1),
        (f"{name} bowl-seat insert — print inverted", MESH_DIR / "wave_seat_insert.ply", 1),
    ]
    seen: dict[str, int] = {}
    for index, ch in enumerate(name, start=1):
        seen[ch] = seen.get(ch, 0) + 1
        label = f"Letter {ch}" if seen[ch] == 1 else f"Letter {ch} {seen[ch]}"
        objects.append((label, MESH_DIR / f"letter_{index}_{ch}.stl", 2))
    OBJECTS = objects

    positions: list[tuple[float, float, float]] = [
        (128.0, 128.0, 0.0),
        (440.0, 128.0, 0.0),
        (128.0, -184.0, 0.0),
    ]
    # Letters occupy plate 4 on the second row of the 312 mm grid.
    x0, y0 = 392.0, -220.0
    cols = 4
    for i in range(len(name)):
        positions.append((x0 + (i % cols) * 24.0, y0 + (i // cols) * 32.0, 0.0))
    BUILD_POSITIONS = positions


def configure_hex_objects(mesh_dir: Path, name: str) -> None:
    """Build OBJECTS + BUILD_POSITIONS for the solid honeycomb layout."""
    global OBJECTS, BUILD_POSITIONS, MESH_DIR
    MESH_DIR = Path(mesh_dir)
    objects: list[tuple[str, Path, int]] = [
        (f"{name} honeycomb body", MESH_DIR / "honeycomb_body.ply", 1),
    ]
    seen: dict[str, int] = {}
    for index, ch in enumerate(name, start=1):
        seen[ch] = seen.get(ch, 0) + 1
        label = f"Letter {ch}" if seen[ch] == 1 else f"Letter {ch} {seen[ch]}"
        objects.append((label, MESH_DIR / f"letter_{index}_{ch}.stl", 2))
    OBJECTS = objects

    positions: list[tuple[float, float, float]] = [
        (128.0, 128.0, 0.0),
    ]
    x0, y0 = 392.0, 96.0
    cols = 4
    for i in range(len(name)):
        positions.append((x0 + (i % cols) * 24.0, y0 + (i // cols) * 32.0, 0.0))
    BUILD_POSITIONS = positions


def object_uuid(index: int, suffix: int = 0) -> str:
    return f"{index:08x}-89ab-4cde-9012-{suffix:012x}"


def mesh_model(
    mesh: trimesh.Trimesh,
    object_id: int,
    paint_fuzzy: np.ndarray | None = None,
) -> bytes:
    mesh = mesh.copy()
    # When a paint mask is supplied it is index-aligned with the caller's faces;
    # skip cleanup that could reorder topology.
    if paint_fuzzy is None:
        mesh.remove_unreferenced_vertices()
    elif len(paint_fuzzy) != len(mesh.faces):
        raise ValueError("paint mask length must match face count")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}" '
        f'xmlns:BambuStudio="{BAMBU}" xmlns:p="{PROD}" requiredextensions="p">',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        " <resources>",
        f'  <object id="{object_id}" p:UUID="{object_uuid(object_id, 0x123456789ABC)}" type="model">',
        "   <mesh>",
        "    <vertices>",
    ]
    lines.extend(
        f'     <vertex x="{x:.8f}" y="{y:.8f}" z="{z:.8f}"/>'
        for x, y, z in mesh.vertices
    )
    lines.extend(["    </vertices>", "    <triangles>"])
    for face_i, (a, b, c) in enumerate(mesh.faces):
        paint = ""
        if paint_fuzzy is not None and paint_fuzzy[face_i]:
            paint = ' paint_fuzzy_skin="4"'
        lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}"{paint}/>')
    lines.extend(
        [
            "    </triangles>",
            "   </mesh>",
            "  </object>",
            " </resources>",
            "</model>",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def top_model() -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}" '
        f'xmlns:BambuStudio="{BAMBU}" xmlns:p="{PROD}" requiredextensions="p">',
        " <metadata name=\"Application\">BambuStudio-02.07.01.62</metadata>",
        " <metadata name=\"BambuStudio:3mfVersion\">1</metadata>",
        " <metadata name=\"Title\">Cooper Paw-Lattice Bowl</metadata>",
        " <resources>",
    ]
    for index in range(1, len(OBJECTS) + 1):
        top_id = 99 + index
        lines.extend(
            [
                f'  <object id="{top_id}" p:UUID="{object_uuid(top_id, 0xABCDEF123456)}" type="model">',
                "   <components>",
                f'    <component p:path="/3D/Objects/object_{index}.model" objectid="{index}" '
                f'p:UUID="{object_uuid(0x1000 + index, 0xABCDEF123456)}" '
                'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>',
                "   </components>",
                "  </object>",
            ]
        )
    lines.extend([" </resources>", f' <build p:UUID="{object_uuid(9999, 0xABCDEF123456)}">'])
    for index, (x, y, z) in enumerate(BUILD_POSITIONS, start=1):
        top_id = 99 + index
        lines.append(
            f'  <item objectid="{top_id}" p:UUID="{object_uuid(5000 + index, 0xABCDEF123456)}" '
            f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}" printable="1"/>'
        )
    lines.extend([" </build>", "</model>"])
    return ("\n".join(lines) + "\n").encode()


def model_settings(meshes: list[trimesh.Trimesh]) -> bytes:
    wave_mode = "wave lower" in OBJECTS[0][0].lower()
    hex_mode = "honeycomb body" in OBJECTS[0][0].lower()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for index, ((name, source, extruder), mesh) in enumerate(zip(OBJECTS, meshes), start=1):
        top_id = 99 + index
        # Object overrides prioritise steady layer time + solid outer skin:
        # 4 walls (hides infill telegraphing / protects letter sockets), gyroid.
        if wave_mode or hex_mode:
            body_object = index <= 3 if wave_mode else index == 1
            if body_object:
                body_layer = "0.16" if hex_mode else "0.20"
                overrides = {
                    "layer_height": body_layer if index == 1 else "0.16",
                    "wall_loops": "4",
                    "sparse_infill_density": "15%",
                    "sparse_infill_pattern": "gyroid",
                    "outer_wall_speed": "100",
                    "inner_wall_speed": "200",
                    "small_perimeter_speed": "100%",
                    "top_shell_layers": "5",
                    "bottom_surface_pattern": "monotonic",
                    "top_surface_pattern": "monotonicline",
                    "seam_position": "back",
                    "fuzzy_skin": "none",
                }
                if wave_mode and index == 2:
                    overrides.update(
                        {
                            "enable_support": "1",
                            "support_type": "normal(auto)",
                            "support_style": "default",
                            "support_critical_regions_only": "1",
                            "support_on_build_plate_only": "0",
                            "support_interface_top_layers": "2",
                            "support_top_z_distance": "0.20",
                        }
                    )
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
        elif index == 1:
            overrides = {
                "layer_height": "0.20",
                "wall_loops": "4",
                "sparse_infill_density": "15%",
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": "150",
                "inner_wall_speed": "250",
                "small_perimeter_speed": "100%",
                "top_shell_layers": "4",
                "bottom_surface_pattern": "monotonic",
                "top_surface_pattern": "monotonicline",
                "seam_position": "back",
                "fuzzy_skin": "external",
                "fuzzy_skin_thickness": "0.3",
                "fuzzy_skin_point_distance": "0.8",
            }
        elif index == 2:
            overrides = {
                "layer_height": "0.16",
                "wall_loops": "4",
                "sparse_infill_density": "15%",
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": "100",
                "inner_wall_speed": "200",
                "small_perimeter_speed": "100%",
                "top_shell_layers": "5",
                "bottom_surface_pattern": "monotonic",
                "top_surface_pattern": "monotonicline",
                "seam_position": "back",
                # "none" = Studio "None (allow paint)". Painted triangles carry
                # the fuzz; disabled_fuzzy would kill painting entirely.
                "fuzzy_skin": "none",
                "fuzzy_skin_thickness": "0.3",
                "fuzzy_skin_point_distance": "0.8",
            }
        elif index == 3:
            overrides = {
                "layer_height": "0.16",
                "wall_loops": "4",
                "sparse_infill_density": "15%",
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": "100",
                "inner_wall_speed": "200",
                "small_perimeter_speed": "100%",
                "top_shell_layers": "5",
                "bottom_surface_pattern": "monotonic",
                "top_surface_pattern": "monotonicline",
                "seam_position": "back",
                "fuzzy_skin": "none",
            }
        else:
            # Letters: fine layers for edges/curves; slower walls for outline quality.
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
        # Part ids must match component order / local mesh object ids.
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

    def plate(number: int, name: str, object_indices: list[int]) -> list[str]:
        result = [
            "  <plate>",
            f'    <metadata key="plater_id" value="{number}"/>',
            f'    <metadata key="plater_name" value="{escape(name)}"/>',
            '    <metadata key="locked" value="false"/>',
            '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
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

    pet = OBJECTS[0][0].split()[0]
    if wave_mode:
        lines.extend(plate(1, "Wave lower", [1]))
        lines.extend(plate(2, "Wave upper shell — print inverted", [2]))
        lines.extend(plate(3, "Bowl-seat insert — print inverted", [3]))
        letter_indices = list(range(4, len(OBJECTS) + 1))
        lines.extend(plate(4, f"{pet} letters", letter_indices))
    elif hex_mode:
        lines.extend(plate(1, "Solid honeycomb body", [1]))
        letter_indices = list(range(2, len(OBJECTS) + 1))
        lines.extend(plate(2, f"{pet} letters", letter_indices))
    else:
        lines.extend(plate(1, "Base", [1]))
        lines.extend(plate(2, "Paw panel — print upright", [2]))
        lines.extend(plate(3, "Top seat ring — print upright", [3]))
        letter_indices = list(range(4, len(OBJECTS) + 1))
        lines.extend(plate(4, f"{pet} letters", letter_indices))
    lines.append("  <assemble>")
    for index in range(1, len(OBJECTS) + 1):
        lines.append(
            f'    <assemble_item object_id="{99 + index}" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def relationships() -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for index in range(1, len(OBJECTS) + 1):
        lines.append(
            f' <Relationship Target="/3D/Objects/object_{index}.model" Id="rel-{index}" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        )
    lines.append("</Relationships>")
    return ("\n".join(lines) + "\n").encode()


def assert_object_id_hygiene(package: zipfile.ZipFile) -> None:
    """Loader requires object_N.model ↔ local id N, unique across the package."""
    seen: dict[str, str] = {}
    for name in package.namelist():
        if not (name.startswith("3D/Objects/object_") and name.endswith(".model")):
            continue
        expected = name.rsplit("_", 1)[1].removesuffix(".model")
        root = ET.fromstring(package.read(name))
        ids = [obj.get("id") for obj in root.iter(f"{{{CORE}}}object")]
        if ids != [expected]:
            raise ValueError(f"{name} must contain only local object id {expected}, got {ids}")
        for oid in ids:
            if oid in seen:
                raise ValueError(f"object id {oid} appears in both {seen[oid]} and {name}")
            seen[oid] = name


def build_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    name: str,
    stand_hex: str,
    letter_hex: str,
    stand_name: str = "Stand",
    letter_name: str = "Letters",
    work_dir: Path | None = None,
    template_path: Path | None = None,
    dims_root: Path | None = None,
    fuzzy_enabled: bool = True,
    painter: FuzzyPainter | None = None,
) -> Path:
    """Package meshes into a 4-plate Bambu 3MF with Matte PLA filament colours.

    `painter` supplies the fuzzy-skin facet mask and its verification. It is
    required whenever fuzzy_enabled is True — this module deliberately knows
    nothing about paw silhouettes, so it cannot supply a default.
    """
    global OUTPUT, WORK, TEMPLATE
    mesh_dir = Path(mesh_dir)
    output_path = Path(output_path)
    work_dir = Path(work_dir or WORK)
    template_path = Path(template_path or TEMPLATE)
    dims_root = Path(dims_root or mesh_dir.parent)
    OUTPUT = output_path
    WORK = work_dir
    TEMPLATE = template_path

    configure_objects(mesh_dir, name.upper())

    meshes = []
    for _, path, _ in OBJECTS:
        mesh = trimesh.load_mesh(path, process=True)
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold printable mesh: {path}")
        meshes.append(mesh)

    panel = meshes[1]
    panel_paint = None
    if fuzzy_enabled:
        if painter is None:
            # Loud rather than silent: defaulting to "no paint" here would ship a
            # smooth panel that still looks correct in every geometric check.
            raise ValueError(
                "fuzzy_enabled=True requires a painter "
                "(pass paint_fuzzy_skin.COOPER_PAINTER for the Cooper panel)"
            )
        panel_paint = painter.mask(
            np.asarray(panel.vertices),
            np.asarray(panel.faces),
            dims_root,
        )

    with (
        zipfile.ZipFile(TEMPLATE) as template,
        zipfile.ZipFile(WORK / "cooper_base_plate.3mf") as base_preview,
        zipfile.ZipFile(WORK / "cooper_panel_plate.3mf") as panel_preview,
        zipfile.ZipFile(WORK / "cooper_top_ring_plate.3mf") as top_ring_preview,
        zipfile.ZipFile(WORK / "cooper_letters_plate.3mf") as letter_preview,
        zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", relationships())
        for index, mesh in enumerate(meshes, start=1):
            paint = panel_paint if index == 2 else None
            output.writestr(
                f"3D/Objects/object_{index}.model",
                mesh_model(mesh, index, paint_fuzzy=paint),
            )
        # When fuzzy is off, force panel object to fuzzy_skin none without paint attrs.
        settings_bytes = model_settings(meshes)
        if not fuzzy_enabled:
            cfg = settings_bytes.decode()
            # Panel is object id 101; ensure fuzzy stays none (already default for paint mode).
            settings_bytes = cfg.encode()
        output.writestr("Metadata/model_settings.config", settings_bytes)

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["outer_wall_speed"][0] = "150"
        settings["inner_wall_speed"][0] = "250"
        settings["bridge_speed"][0] = "50"
        settings["overhang_1_4_speed"][0] = "50"
        settings["overhang_2_4_speed"][0] = "40"
        settings["overhang_3_4_speed"][0] = "30"
        settings["overhang_4_4_speed"][0] = "10"
        settings["small_perimeter_speed"][0] = "100%"
        settings["bottom_surface_pattern"] = "monotonic"
        settings["top_surface_pattern"] = "monotonicline"
        settings["reduce_crossing_wall"] = "0"
        settings["precise_outer_wall"] = "0"
        settings["no_slow_down_for_cooling_on_outwalls"] = ["0", "0"]
        settings["outer_wall_acceleration"] = ["5000", "5000"]
        settings["inner_wall_acceleration"] = ["0", "0"]
        settings["wall_sequence"] = "inner wall/outer wall"
        settings["seam_position"] = "back"
        settings["retraction_length"] = ["0.8", "0.8"]
        settings["filament_retraction_length"] = ["nil", "nil", "nil", "nil"]
        settings["retraction_speed"] = ["30", "30"]
        settings["filament_retraction_speed"] = ["nil", "nil", "nil", "nil"]
        settings["deretraction_speed"] = ["30", "30"]
        settings["filament_deretraction_speed"] = ["nil", "nil", "nil", "nil"]
        settings["retract_before_wipe"] = ["70%", "70%"]
        settings["filament_retract_before_wipe"] = ["nil", "nil", "nil", "nil"]
        settings["wipe_distance"] = ["2", "2"]
        settings["filament_wipe_distance"] = ["nil", "nil", "nil", "nil"]
        settings["reduce_infill_retraction"] = "1"
        settings["filament_flow_ratio"] = ["0.98", "0.98", "0.98", "0.98"]
        settings["nozzle_temperature"] = ["220", "220", "220", "220"]
        settings["nozzle_temperature_initial_layer"] = ["220", "220", "220", "220"]
        settings["fuzzy_skin"] = "none"
        settings["fuzzy_skin_thickness"] = "0.3"
        settings["fuzzy_skin_point_distance"] = "0.8"
        settings["fuzzy_skin_first_layer"] = "0"
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

        previews = (base_preview, panel_preview, top_ring_preview, letter_preview)
        for plate_number, preview in enumerate(previews, start=1):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )
            if "Metadata/plate_1_small.png" in preview.namelist():
                output.writestr(
                    f"Metadata/plate_{plate_number}_small.png",
                    preview.read("Metadata/plate_1_small.png"),
                )

    with zipfile.ZipFile(OUTPUT) as packaged:
        assert_object_id_hygiene(packaged)
        if fuzzy_enabled and panel_paint is not None:
            obj2 = packaged.read("3D/Objects/object_2.model").decode()
            cfg = packaged.read("Metadata/model_settings.config").decode()
            painter.verify(
                obj2,
                cfg,
                panel_paint,
                np.asarray(panel.vertices),
                np.asarray(panel.faces),
            )

    print(f"{OUTPUT}  (name={name}, stand={stand_hex}, letters={letter_hex})")
    return OUTPUT


def build_wave_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    name: str,
    stand_hex: str,
    letter_hex: str,
    stand_name: str = "Stand",
    letter_name: str = "Letters",
    work_dir: Path | None = None,
    template_path: Path | None = None,
) -> Path:
    """Package wave lower/shell/seat insert + letters into a 4-plate 3MF."""
    global OUTPUT, WORK, TEMPLATE
    mesh_dir = Path(mesh_dir)
    output_path = Path(output_path)
    work_dir = Path(work_dir or WORK)
    template_path = Path(template_path or TEMPLATE)
    OUTPUT = output_path
    WORK = work_dir
    TEMPLATE = template_path

    configure_wave_objects(mesh_dir, name.upper())

    meshes = []
    for _, path, _ in OBJECTS:
        # Wave sector unions keep topology better without process=True.
        # Letters are simple extrusions and expect the usual cleanup.
        process = path.suffix.lower() != ".ply"
        mesh = trimesh.load_mesh(path, process=process)
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold printable mesh: {path}")
        meshes.append(mesh)

    with (
        zipfile.ZipFile(TEMPLATE) as template,
        zipfile.ZipFile(WORK / "cooper_base_plate.3mf") as base_preview,
        zipfile.ZipFile(WORK / "cooper_panel_plate.3mf") as panel_preview,
        zipfile.ZipFile(WORK / "cooper_top_ring_plate.3mf") as seat_preview,
        zipfile.ZipFile(WORK / "cooper_letters_plate.3mf") as letter_preview,
        zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr("Metadata/model_settings.config", model_settings(meshes))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        # Keep travel within printed regions where possible. A zero max detour
        # means unlimited detour length in Bambu Studio, not disabled detours.
        settings["reduce_crossing_wall"] = "1"
        settings["max_travel_detour_distance"] = "0"
        settings["retract_when_changing_layer"] = ["1", "1"]
        settings["retraction_length"] = ["0.8", "0.8"]
        settings["retraction_speed"] = ["30", "30"]
        settings["deretraction_speed"] = ["30", "30"]
        settings["retraction_minimum_travel"] = ["1", "1"]
        settings["retract_before_wipe"] = ["70%", "70%"]
        settings["wipe"] = ["1", "1"]
        settings["wipe_distance"] = ["2", "2"]
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

        previews = (base_preview, panel_preview, seat_preview, letter_preview)
        for plate_number, preview in enumerate(previews, start=1):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )

    with zipfile.ZipFile(OUTPUT) as packaged:
        assert_object_id_hygiene(packaged)

    print(f"{OUTPUT}  (style=wave, name={name}, stand={stand_hex}, letters={letter_hex})")
    return OUTPUT


def build_hex_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    name: str,
    stand_hex: str,
    letter_hex: str,
    stand_name: str = "Stand",
    letter_name: str = "Letters",
    work_dir: Path | None = None,
    template_path: Path | None = None,
) -> Path:
    """Package the solid honeycomb body and letters into a 2-plate 3MF."""
    global OUTPUT, WORK, TEMPLATE
    mesh_dir = Path(mesh_dir)
    output_path = Path(output_path)
    work_dir = Path(work_dir or WORK)
    template_path = Path(template_path or TEMPLATE)
    OUTPUT = output_path
    WORK = work_dir
    TEMPLATE = template_path

    configure_hex_objects(mesh_dir, name.upper())

    meshes = []
    for _, path, _ in OBJECTS:
        process = path.suffix.lower() != ".ply"
        mesh = trimesh.load_mesh(path, process=process)
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold printable mesh: {path}")
        meshes.append(mesh)

    with (
        zipfile.ZipFile(TEMPLATE) as template,
        zipfile.ZipFile(WORK / "cooper_panel_plate.3mf") as body_preview,
        zipfile.ZipFile(WORK / "cooper_letters_plate.3mf") as letter_preview,
        zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr("Metadata/model_settings.config", model_settings(meshes))

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

        previews = (body_preview, letter_preview)
        for plate_number, preview in enumerate(previews, start=1):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )

    with zipfile.ZipFile(OUTPUT) as packaged:
        assert_object_id_hygiene(packaged)

    print(
        f"{OUTPUT}  (style=hex-honeycomb, name={name}, "
        f"stand={stand_hex}, letters={letter_hex})"
    )
    return OUTPUT


def build():
    configure_objects(MESH_DIR, "COOPER")
    return build_project(
        mesh_dir=MESH_DIR,
        output_path=OUTPUT,
        name="COOPER",
        stand_hex="#AE835B",
        letter_hex="#FFFFFF",
        stand_name="Caramel",
        letter_name="Ivory White",
        work_dir=WORK,
        template_path=TEMPLATE,
        dims_root=OUT,
        fuzzy_enabled=True,
    )


if __name__ == "__main__":
    build()
