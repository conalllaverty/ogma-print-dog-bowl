#!/usr/bin/env python3
"""Generate the stationary-shutter / exposed-core-infill Oggie Spin project.

The project contains a modified complete core, a grooved socketed upper thumb
pad, a separate snap-on stationary shutter ring and five standard arms. The
bearing ring, cartridge and lower pad are reused from the complete spinner.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import trimesh
from PIL import Image, ImageDraw
from shapely import union_all
from shapely.affinity import rotate
from shapely.geometry import LineString, box

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
import oggie_spin_optical_variants as optical  # noqa: E402


OUTPUT_SUBDIR = "optical-variants/shutter_infill"
OUTPUT_NAME = "Oggie_Spin_Optical_Shutter_Exposed_Core_Infill_P2S.3mf"
REPORT_NAME = "shutter_infill_validation.json"

CORE_RECESS_INNER_R = 10.60
CORE_RECESS_OUTER_R = 19.40
CORE_RECESS_DEPTH = 1.60
CORE_RECESS_Z0 = base.CORE_HEIGHT - CORE_RECESS_DEPTH
INFILL_RIB_COUNT = 13
INFILL_RIB_WIDTH = 1.20
INFILL_CAP_DEPTH = 0.32
INFILL_CAP_WIDTH = 0.80
INFILL_CAP_END_MARGIN = 0.20

SHUTTER_OUTER_R = 23.00
SHUTTER_BODY_INNER_R = 10.05
SHUTTER_HEIGHT = 1.80
SHUTTER_OUTER_RIM = 1.60
SHUTTER_SLOT_COUNT = 12
SHUTTER_SLOT_ANGLE_DEG = 6.0
SHUTTER_SLOT_INNER_R = 10.70
SHUTTER_SLOT_OUTER_R = SHUTTER_OUTER_R - SHUTTER_OUTER_RIM
SHUTTER_SPLIT_WIDTH = 0.80
SHUTTER_SPLIT_PHASE_DEG = 15.0

PAD_GROOVE_INNER_R = 9.75
PAD_GROOVE_OUTER_R = 10.20
PAD_GROOVE_Z0 = 0.55
PAD_GROOVE_HEIGHT = 0.90
SHUTTER_BEAD_INNER_R = 9.90
SHUTTER_BEAD_OUTER_R = 10.10
SHUTTER_BEAD_Z0 = 0.75
SHUTTER_BEAD_HEIGHT = 0.50
PAD_GROOVE_MIN_WALL = PAD_GROOVE_INNER_R - complete.PRINTED_CAP_ENTRY_OUTER_R

FILAMENTS = [
    ("Dark Chocolate Matte", "#4D3324"),
    ("Ivory White Matte", "#FFFFFF"),
]
ORIGINAL_MODEL_SETTINGS = base._model_settings
ORIGINAL_CONFIGURE_FILAMENTS = base._configure_filament_slots


def _plate_position(number: int) -> tuple[float, float, float]:
    index = number - 1
    return (
        128.0 + (index % 2) * 312.0,
        128.0 - (index // 2) * 312.0,
        0.0,
    )


PLATES = [
    base.Plate(
        "SH exposed radial-infill core",
        ((1, 0.0, 0.0, 0.0), (2, 0.0, 0.0, 0.0)),
        _plate_position(1),
    ),
    base.Plate(
        "SH grooved upper pad and shutter ring",
        ((3, 30.0, 0.0, 0.0), (4, -30.0, 0.0, 0.0)),
        _plate_position(2),
    ),
    base.Plate(
        "SH five standard clip-lock arms",
        (
            (5, 0.0, 0.0, 0.0),
            (6, -70.0, -70.0, 0.0),
            (7, 70.0, -70.0, 0.0),
            (8, 70.0, 70.0, 0.0),
            (9, -70.0, 70.0, 0.0),
        ),
        _plate_position(3),
    ),
]


def _translated_annulus(
    outer_diameter: float,
    inner_diameter: float,
    height: float,
    z0: float,
    name: str,
) -> trimesh.Trimesh:
    mesh = base._annulus(outer_diameter, inner_diameter, height, name)
    mesh.apply_translation([0.0, 0.0, z0])
    return base._finish(mesh, name)


def _radial_infill_geometry(
    *,
    inner_r: float | None = None,
    outer_r: float | None = None,
    width: float = INFILL_RIB_WIDTH,
):
    # Cross the annulus boundaries rather than ending exactly on them. This
    # avoids STL T-junctions where a rib, recess wall and flush cap converge.
    boundary_overlap = 0.30
    inner_r = (
        CORE_RECESS_INNER_R - boundary_overlap
        if inner_r is None
        else inner_r
    )
    outer_r = (
        CORE_RECESS_OUTER_R + boundary_overlap
        if outer_r is None
        else outer_r
    )
    radial_bar = LineString(
        [
            (inner_r, 0.0),
            (outer_r, 0.0),
        ]
    ).buffer(
        width / 2.0,
        cap_style="flat",
        join_style="round",
    )
    return union_all(
        [
            rotate(
                radial_bar,
                index * 360.0 / INFILL_RIB_COUNT,
                origin=(0.0, 0.0),
            )
            for index in range(INFILL_RIB_COUNT)
        ]
    )


def build_exposed_infill_core() -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    source = complete.build_complete_core()
    recess = _translated_annulus(
        2.0 * CORE_RECESS_OUTER_R,
        2.0 * CORE_RECESS_INNER_R,
        CORE_RECESS_DEPTH + 0.2,
        CORE_RECESS_Z0,
        "exposed infill recess volume",
    )
    rib_geometry = _radial_infill_geometry()
    ribs = optical._extrude_geometry(
        rib_geometry,
        CORE_RECESS_DEPTH + 0.4,
        CORE_RECESS_Z0 - 0.1,
        "radial exposed-infill ribs",
    )
    gaps = trimesh.boolean.difference([recess, ribs], engine="manifold")
    if gaps is None or gaps.is_empty:
        raise RuntimeError("failed to create exposed-infill core gaps")
    recessed_core = trimesh.boolean.difference([source, gaps], engine="manifold")
    if recessed_core is None or recessed_core.is_empty:
        raise RuntimeError("failed to recess exposed-infill core")
    recessed_core = optical._finish_components(
        recessed_core,
        "SH recessed radial-infill core",
    )

    cap_geometry = _radial_infill_geometry(
        inner_r=CORE_RECESS_INNER_R + INFILL_CAP_END_MARGIN,
        outer_r=CORE_RECESS_OUTER_R - INFILL_CAP_END_MARGIN,
        width=INFILL_CAP_WIDTH,
    )
    cap_volume = optical._extrude_geometry(
        cap_geometry,
        INFILL_CAP_DEPTH + 0.1,
        base.CORE_HEIGHT - INFILL_CAP_DEPTH,
        "radial infill contrast caps",
    )
    inlay_volume = optical._combine_volumes(
        [
            cap_volume,
            optical._identifier_volume("SH"),
        ],
        "SH core contrast volumes",
    )
    return optical._split_inlay(
        recessed_core,
        inlay_volume,
        "SH exposed radial-infill core",
    )


def _installed_socketed_pad() -> trimesh.Trimesh:
    printed = complete.build_printed_thumb_pad(
        "SH socketed upper pad",
        height=complete.RECEIVER_CAP_HEIGHT,
        central_socket_depth=complete.RECEIVER_CAP_SOCKET_DEPTH,
    )
    return complete._flip_cap_for_print(
        printed,
        complete.RECEIVER_CAP_HEIGHT,
        "SH socketed upper pad installed orientation",
    )


def build_grooved_upper_pad() -> trimesh.Trimesh:
    installed = _installed_socketed_pad()
    groove = _translated_annulus(
        2.0 * PAD_GROOVE_OUTER_R,
        2.0 * PAD_GROOVE_INNER_R,
        PAD_GROOVE_HEIGHT,
        PAD_GROOVE_Z0,
        "SH shutter retention groove cutter",
    )
    grooved = base._difference(
        installed,
        [groove],
        "SH grooved socketed upper pad",
    )
    return complete._flip_cap_for_print(
        grooved,
        complete.RECEIVER_CAP_HEIGHT,
        "SH grooved socketed upper pad",
    )


def build_shutter_ring() -> trimesh.Trimesh:
    body = base._annulus(
        2.0 * SHUTTER_OUTER_R,
        2.0 * SHUTTER_BODY_INNER_R,
        SHUTTER_HEIGHT,
        "SH stationary shutter annulus",
    )
    bead = _translated_annulus(
        2.0 * SHUTTER_BEAD_OUTER_R,
        2.0 * SHUTTER_BEAD_INNER_R,
        SHUTTER_BEAD_HEIGHT,
        SHUTTER_BEAD_Z0,
        "SH snap bead",
    )
    blank = base._union([body, bead], "SH stationary shutter blank")
    cutters = [
        base._annular_sector(
            SHUTTER_SLOT_INNER_R,
            SHUTTER_SLOT_OUTER_R,
            index * 360.0 / SHUTTER_SLOT_COUNT - SHUTTER_SLOT_ANGLE_DEG / 2.0,
            index * 360.0 / SHUTTER_SLOT_COUNT + SHUTTER_SLOT_ANGLE_DEG / 2.0,
            SHUTTER_HEIGHT + 0.4,
            -0.2,
            steps=10,
        )
        for index in range(SHUTTER_SLOT_COUNT)
    ]
    split_polygon = rotate(
        box(
            SHUTTER_BODY_INNER_R - 0.6,
            -SHUTTER_SPLIT_WIDTH / 2.0,
            SHUTTER_OUTER_R + 0.6,
            SHUTTER_SPLIT_WIDTH / 2.0,
        ),
        SHUTTER_SPLIT_PHASE_DEG,
        origin=(0.0, 0.0),
    )
    cutters.append(
        base._extrude(
            split_polygon,
            SHUTTER_HEIGHT + 0.4,
            -0.2,
        )
    )
    return base._difference(
        blank,
        cutters,
        "SH split snap-on stationary shutter ring",
    )


def _set_metadata(node: ET.Element, key: str, value: str) -> None:
    for item in node.findall("./metadata"):
        if item.get("key") == key:
            item.set("value", value)
            return
    ET.SubElement(node, "metadata", {"key": key, "value": value})


def _model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    root = ET.fromstring(ORIGINAL_MODEL_SETTINGS(objects, meshes))
    inlay = root.find(".//part[@id='2']")
    shutter = root.find(".//part[@id='4']")
    if inlay is None or shutter is None:
        raise RuntimeError("SH project lost an expected part")
    _set_metadata(inlay, "wall_loops", "2")
    _set_metadata(shutter, "wall_loops", "3")
    _set_metadata(shutter, "sparse_infill_density", "100%")
    _set_metadata(shutter, "sparse_infill_pattern", "gyroid")
    for part_id in range(5, 10):
        arm = root.find(f".//part[@id='{part_id}']")
        if arm is None:
            raise RuntimeError(f"SH project lost arm part {part_id}")
        _set_metadata(arm, "wall_loops", "2")
        _set_metadata(arm, "sparse_infill_density", "100%")
        _set_metadata(arm, "sparse_infill_pattern", "gyroid")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _preview_png(plate_number: int, size: int = 512) -> bytes:
    image = Image.new("RGBA", (size, size), (244, 241, 234, 255))
    draw = ImageDraw.Draw(image)
    draw.text(
        (24, 20),
        f"Oggie Spin SH shutter infill · plate {plate_number}",
        fill="#252A32",
    )
    if plate_number == 1:
        draw.ellipse(
            (116, 116, 396, 396),
            fill=FILAMENTS[0][1],
            outline="#252A32",
            width=4,
        )
        for index in range(INFILL_RIB_COUNT):
            angle = math.radians(index * 360.0 / INFILL_RIB_COUNT)
            draw.line(
                (
                    256 + 75 * math.cos(angle),
                    256 + 75 * math.sin(angle),
                    256 + 132 * math.cos(angle),
                    256 + 132 * math.sin(angle),
                ),
                fill=FILAMENTS[1][1],
                width=7,
            )
        draw.ellipse((196, 196, 316, 316), fill="#F4F1EA")
    elif plate_number == 2:
        draw.ellipse(
            (74, 98, 350, 374),
            fill=FILAMENTS[0][1],
            outline="#252A32",
            width=4,
        )
    else:
        for cx, cy in (
            (256, 256),
            (132, 132),
            (380, 132),
            (380, 380),
            (132, 380),
        ):
            draw.pieslice(
                (cx - 54, cy - 54, cx + 54, cy + 54),
                start=250,
                end=290,
                fill=FILAMENTS[0][1],
                outline="#252A32",
                width=3,
            )
        draw.ellipse((132, 156, 292, 316), fill="#F4F1EA")
        for index in range(SHUTTER_SLOT_COUNT):
            angle = math.radians(index * 360.0 / SHUTTER_SLOT_COUNT)
            draw.line(
                (
                    212 + 68 * math.cos(angle),
                    236 + 68 * math.sin(angle),
                    212 + 124 * math.cos(angle),
                    236 + 124 * math.sin(angle),
                ),
                fill="#F4F1EA",
                width=6,
            )
        draw.ellipse(
            (372, 196, 468, 292),
            fill=FILAMENTS[0][1],
            outline="#252A32",
            width=4,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _rewrite_project_settings(path: Path) -> None:
    temp_path = path.with_suffix(".tmp.3mf")
    with (
        zipfile.ZipFile(path, "r") as source,
        zipfile.ZipFile(
            temp_path,
            "w",
            zipfile.ZIP_DEFLATED,
            compresslevel=7,
        ) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "Metadata/project_settings.config":
                settings = json.loads(data)
                settings["print_sequence"] = "by layer"
                settings["enable_prime_tower"] = "1"
                settings["reduce_crossing_wall"] = "1"
                settings["max_travel_detour_distance"] = "0"
                for key, value in (
                    ("z_hop", "0.6"),
                    ("z_hop_types", "Slope Lift"),
                    ("retract_when_changing_layer", "1"),
                    ("retraction_length", "0.8"),
                    ("retraction_speed", "30"),
                    ("deretraction_speed", "30"),
                    ("retraction_minimum_travel", "1"),
                    ("retract_before_wipe", "70%"),
                    ("wipe", "1"),
                    ("wipe_distance", "2"),
                ):
                    current = settings.get(key)
                    settings[key] = [value] * (
                        len(current) if isinstance(current, list) and current else 2
                    )
                data = json.dumps(
                    settings,
                    indent=2,
                    ensure_ascii=False,
                ).encode()
            target.writestr(item, data)
    temp_path.replace(path)


def _write_meshes(
    output_dir: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> list[tuple[str, Path, int]]:
    mesh_dir = output_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_')}.stl"
        mesh.export(path)
        base._finish(
            trimesh.load_mesh(path, process=True),
            f"serialized {name}",
        )
        objects.append((name, path, extruder))
    return objects


def _build_project(
    output_dir: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> Path:
    objects = _write_meshes(output_dir, built)
    output = output_dir / OUTPUT_NAME
    previous = (
        base.PLATES,
        base.FILAMENTS,
        base._preview_png,
        base._model_settings,
        base._configure_filament_slots,
    )
    try:
        base.PLATES = PLATES
        base.FILAMENTS = FILAMENTS
        base._preview_png = _preview_png
        base._model_settings = _model_settings
        base._configure_filament_slots = ORIGINAL_CONFIGURE_FILAMENTS
        base.build_bambu_project(output, objects)
    finally:
        (
            base.PLATES,
            base.FILAMENTS,
            base._preview_png,
            base._model_settings,
            base._configure_filament_slots,
        ) = previous
    _rewrite_project_settings(output)
    return output


def _validate(
    output: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> dict:
    core_body, core_inlay, pad, shutter, *arms = [
        item[1] for item in built
    ]
    if PAD_GROOVE_MIN_WALL < 1.20:
        raise RuntimeError("SH pad groove leaves less than 1.20 mm material")
    if SHUTTER_OUTER_R >= complete.WRAP_OUTER_R:
        raise RuntimeError("SH shutter does not remain inside the arm tips")
    if complete.HUB_TO_CORE_GAP < 1.60:
        raise RuntimeError("SH shutter has insufficient axial clearance")
    if abs(core_body.bounds[1, 2] - base.CORE_HEIGHT) > 1e-6:
        raise RuntimeError("SH core body lost its top datum")
    if abs(core_inlay.bounds[1, 2] - base.CORE_HEIGHT) > 1e-6:
        raise RuntimeError("SH infill caps are not flush")
    if core_inlay.bounds[0, 2] > 0.001:
        raise RuntimeError("SH core identifier is not on the underside")
    if abs(2.0 * max(abs(shutter.bounds[:, 0]).max(), abs(shutter.bounds[:, 1]).max()) - 46.0) > 0.05:
        raise RuntimeError("SH shutter outer diameter changed")
    if len(arms) != 5:
        raise RuntimeError("SH project must contain five arms")
    arm_volumes = [float(arm.volume) for arm in arms]
    if max(arm_volumes) - min(arm_volumes) > 1e-6:
        raise RuntimeError("SH arms are not volume matched")
    reference_arm_volume = complete.build_arm("SH validation arm").volume
    if max(abs(volume - reference_arm_volume) for volume in arm_volumes) > 0.01:
        raise RuntimeError("SH project arms differ from the standard arm")

    overlap = trimesh.boolean.intersection(
        [core_body, core_inlay],
        engine="manifold",
    )
    if overlap is not None and not overlap.is_empty and overlap.volume > 1e-6:
        raise RuntimeError("SH core body and contrast caps overlap")

    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("SH project failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        model_settings = ET.fromstring(
            package.read("Metadata/model_settings.config")
        )
        if len(model_settings.findall("./plate")) != 3:
            raise RuntimeError("SH project lost its three-plate layout")
        for part_id in range(5, 10):
            arm = model_settings.find(f".//part[@id='{part_id}']")
            metadata = {
                item.get("key"): item.get("value")
                for item in arm.findall("./metadata")
            } if arm is not None else {}
            if (
                metadata.get("wall_loops") != "2"
                or metadata.get("sparse_infill_density") != "100%"
                or metadata.get("sparse_infill_pattern") != "gyroid"
            ):
                raise RuntimeError(f"SH arm {part_id - 4} lost batch overrides")
        project = json.loads(
            package.read("Metadata/project_settings.config")
        )
        if project.get("print_sequence") != "by layer":
            raise RuntimeError("SH project lost by-layer sequencing")
        if len(project.get("filament_settings_id", [])) != 2:
            raise RuntimeError("SH project lost a filament slot")

    slot_width_at_midpoint = (
        2.0
        * ((SHUTTER_SLOT_INNER_R + SHUTTER_SLOT_OUTER_R) / 2.0)
        * math.sin(math.radians(SHUTTER_SLOT_ANGLE_DEG / 2.0))
    )
    report = {
        "project": output.name,
        "plates": 3,
        "identifier": "SH on core underside",
        "rotating_infill_ribs": INFILL_RIB_COUNT,
        "stationary_shutter_slots": SHUTTER_SLOT_COUNT,
        "shutter_slot_width_midpoint_mm": round(slot_width_at_midpoint, 3),
        "core_recess_depth_mm": CORE_RECESS_DEPTH,
        "contrast_cap_depth_mm": INFILL_CAP_DEPTH,
        "shutter_outer_diameter_mm": 2.0 * SHUTTER_OUTER_R,
        "shutter_thickness_mm": SHUTTER_HEIGHT,
        "shutter_to_arm_tip_radial_margin_mm": round(
            complete.WRAP_OUTER_R - SHUTTER_OUTER_R,
            3,
        ),
        "shutter_to_rotating_face_clearance_mm": complete.HUB_TO_CORE_GAP,
        "pad_groove_min_wall_mm": round(PAD_GROOVE_MIN_WALL, 3),
        "snap_bead_pass_interference_per_side_mm": round(
            base.CAP_DIAMETER / 2.0 - SHUTTER_BEAD_INNER_R,
            3,
        ),
        "arm_plate": "five standard arms in centre-plus-four-corners layout",
        "arm_plate_wall_loops": 2,
        "arm_plate_infill": "100% gyroid",
        "arm_plate_z_hop_mm": 0.6,
        "arm_volume_spread_mm3": round(
            max(arm_volumes) - min(arm_volumes),
            9,
        ),
        "recommended_matte_colours": {
            "slot_1": "Dark Chocolate Matte core, shutter and five arms",
            "slot_2": "Ivory White Matte infill caps and identifier",
        },
        "reused_parts": [
            "R188 retaining ring",
            "Tough+ cartridge",
            "standard lower thumb pad",
        ],
        "physical_status": (
            "untested; check shutter snap, 1.6 mm running clearance, "
            "deflection, free spin and naked-eye moire before extended use"
        ),
    }
    (output.parent / REPORT_NAME).write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def generate(out_dir: Path) -> Path:
    output_dir = Path(out_dir) / OUTPUT_SUBDIR
    output_dir.mkdir(parents=True, exist_ok=True)
    core_body, core_inlay = build_exposed_infill_core()
    built = [
        ("SH exposed radial-infill core", core_body, 1),
        ("SH Ivory radial-infill caps and underside identifier", core_inlay, 2),
        ("SH grooved socketed upper pad", build_grooved_upper_pad(), 1),
        ("SH split snap-on stationary shutter ring", build_shutter_ring(), 1),
        *[
            (
                f"SH standard clip-lock arm {index}",
                complete.build_arm(f"SH standard clip-lock arm {index}"),
                1,
            )
            for index in range(1, 6)
        ],
    ]
    output = _build_project(output_dir, built)
    _validate(output, built)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.out))
