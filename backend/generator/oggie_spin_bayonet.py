#!/usr/bin/env python3
"""Generate the Oggie Spin R188 + axial-lock bayonet fit-test project.

The project is deliberately a mechanism prototype, not the final spinner:

1. Ø40 five-slot core with an R188 shouldered bearing pocket.
2. M3 cartridge sleeve and two inner-race spacer tubes.
3. Screw-side and captive-nut permanent bayonet hubs.
4. Two removable three-lug thumb pads.

Run from the repository root:

    .venv/bin/python backend/generator/oggie_spin_bayonet.py \
        --out design/modular-spinner/bayonet-fit-test
"""

from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import sys
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET

import manifold3d
import numpy as np
import trimesh
from PIL import Image, ImageDraw
from shapely.geometry import Polygon

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import build_bambu_project as bambu  # noqa: E402

# ---------------------------------------------------------------------------
# Locked concept envelope and first-print tolerances (millimetres)
# ---------------------------------------------------------------------------

CORE_DIAMETER = 40.0
CORE_HEIGHT = 14.0
CORE_SECTIONS = 160
ARM_SLOT_COUNT = 5
ARM_SLOT_BOTTOM_Z = 2.0
ARM_SLOT_INNER_R = 13.8
ARM_SLOT_OUTER_R = 20.8
ARM_SLOT_INNER_HALF_W = 5.0
ARM_SLOT_MOUTH_HALF_W = 3.4

R188_OD = 12.70
R188_ID = 6.35
R188_WIDTH = 4.76
# Physical tests bracketed the fit: Ø12.86 released the R188 under gravity,
# while Ø12.68 and then Ø12.78 would not install easily by hand. The separate
# outer-race retaining ring provides axial capture, so move halfway from the
# tight Ø12.78 result toward the known-loose Ø12.86 result.
#
# 2026-08-06: Ø12.82 still reported slightly tight to insert. Most of that was
# the missing lead-in at the pocket mouth (see BEARING_POCKET_LEAD_IN) -- the
# bore itself measures 12.8197-12.8200 on the exported mesh, so it was never a
# sizing error. Nudged 0.02 as well, which keeps it BELOW the 12.86 that was
# measurably loose. Do not go past 12.86: the pocket sets the bearing's
# concentricity, and a loose one shows up as vibration at speed.
BEARING_POCKET_DIAMETER = 12.84
BEARING_SHOULDER_OPENING = 10.60
BEARING_SEAT_Z = (CORE_HEIGHT - R188_WIDTH) / 2.0
CORE_FACE_TO_RACE = BEARING_SEAT_Z
CAP_TO_CORE_GAP = 0.40

M3_CLEARANCE_DIAMETER = 3.35
M3_HEAD_DIAMETER = 6.20
M3_HEAD_DEPTH = 2.30
M3_NYLOC_AF = 5.70
M3_NYLOC_DEPTH = 4.20
M3_SCREW_LENGTH = 25

SLEEVE_OD = 6.18
SLEEVE_ID = M3_CLEARANCE_DIAMETER
SLEEVE_HEIGHT = R188_WIDTH
SPACER_OD = 8.40
SPACER_ID = M3_CLEARANCE_DIAMETER
SPACER_HEIGHT = CORE_FACE_TO_RACE + CAP_TO_CORE_GAP

HUB_FLANGE_DIAMETER = 14.0
HUB_FLANGE_HEIGHT = 2.40
HUB_BOSS_DIAMETER = 9.60
HUB_BOSS_HEIGHT = 3.80
HUB_TOTAL_HEIGHT = HUB_FLANGE_HEIGHT + HUB_BOSS_HEIGHT
HUB_LUG_INNER_R = 4.65
HUB_LUG_OUTER_R = 5.92
HUB_LUG_ANGLE = 12.0
HUB_LUG_Z = HUB_FLANGE_HEIGHT + 2.10
HUB_LUG_HEIGHT = 0.90
HUB_DETENT_OUTER_R = 6.14
HUB_DETENT_ANGLE = 3.0

CAP_DIAMETER = 20.0
CAP_HEIGHT = 4.80
CAP_CAVITY_R = 5.05
CAP_CAVITY_DEPTH = 3.85
CAP_ENTRY_OUTER_R = 6.25
CAP_ENTRY_ANGLE = 17.0
CAP_TRACK_OUTER_R = 6.08
CAP_TRACK_Z = 1.82
CAP_TRACK_HEIGHT = 1.48
CAP_LOCK_ROTATION_DEG = 30.0
CAP_LOCK_POCKET_OUTER_R = 6.28
CAP_RADIAL_CLEARANCE = CAP_CAVITY_R - HUB_BOSS_DIAMETER / 2.0
CAP_LUG_CLEARANCE = CAP_TRACK_OUTER_R - HUB_LUG_OUTER_R
CAP_AXIAL_CLEARANCE = CAP_TRACK_HEIGHT - HUB_LUG_HEIGHT

FILAMENTS = [
    ("Marine Blue Matte", "#3A8FCF"),
    ("Lemon Yellow Matte", "#F0C14A"),
]


@dataclass(frozen=True)
class Plate:
    title: str
    components: tuple[tuple[int, float, float, float], ...]
    position: tuple[float, float, float]


PLATES = [
    Plate("Core + R188 seat", ((1, 0.0, 0.0, 0.0),), (128.0, 128.0, 0.0)),
    Plate(
        "M3 cartridge sleeve + spacers",
        (
            (2, -15.0, 0.0, 0.0),
            (3, 0.0, 0.0, 0.0),
            (4, 15.0, 0.0, 0.0),
        ),
        (440.0, 128.0, 0.0),
    ),
    Plate(
        "Permanent screw + nut hubs",
        ((5, -12.0, 0.0, 0.0), (6, 12.0, 0.0, 0.0)),
        (128.0, -184.0, 0.0),
    ),
    Plate(
        "Axial-lock bayonet thumb pads",
        ((7, -13.0, 0.0, 0.0), (8, 13.0, 0.0, 0.0)),
        (440.0, -184.0, 0.0),
    ),
]


# ---------------------------------------------------------------------------
# Mesh helpers
# ---------------------------------------------------------------------------


def _finish(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    if isinstance(mesh, list):
        mesh = trimesh.util.concatenate(mesh)
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight or not mesh.is_volume:
        raise RuntimeError(f"{name} is not a watertight volume")
    if np.any(mesh.area_faces <= 1e-10):
        source = manifold3d.Mesh(
            vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
            tolerance=1e-6,
        )
        repaired = manifold3d.Manifold(source)
        if repaired.status() != manifold3d.Error.NoError:
            raise RuntimeError(f"{name} cannot be cleaned: {repaired.status()}")
        emitted = repaired.simplify(1e-5).to_mesh64()
        mesh = trimesh.Trimesh(
            vertices=np.asarray(emitted.vert_properties)[:, :3],
            faces=np.asarray(emitted.tri_verts),
            process=False,
        )
        mesh.fix_normals()
    if (
        not mesh.is_watertight
        or not mesh.is_volume
        or np.any(mesh.area_faces <= 1e-10)
    ):
        raise RuntimeError(f"{name} is not serialization-safe")
    mesh.metadata["name"] = name
    return mesh


def _cylinder(radius: float, height: float, z0: float = 0.0, sections: int = 128):
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    mesh.apply_translation([0.0, 0.0, z0 + height / 2.0])
    return mesh


def _extrude(poly: Polygon, height: float, z0: float = 0.0):
    mesh = trimesh.creation.extrude_polygon(poly, height=height, engine="earcut")
    mesh.apply_translation([0.0, 0.0, z0])
    return mesh


def _union(meshes: list[trimesh.Trimesh], name: str) -> trimesh.Trimesh:
    result = trimesh.boolean.union(meshes, engine="manifold")
    return _finish(result, name)


def _difference(
    body: trimesh.Trimesh,
    cutters: list[trimesh.Trimesh],
    name: str,
) -> trimesh.Trimesh:
    result = trimesh.boolean.difference([body, *cutters], engine="manifold")
    return _finish(result, name)


def _annular_sector(
    inner_r: float,
    outer_r: float,
    a0_deg: float,
    a1_deg: float,
    height: float,
    z0: float,
    steps: int = 24,
) -> trimesh.Trimesh:
    if a1_deg <= a0_deg:
        raise ValueError("sector end angle must exceed start angle")
    angles = np.linspace(math.radians(a0_deg), math.radians(a1_deg), steps + 1)
    outer = [(outer_r * math.cos(a), outer_r * math.sin(a)) for a in angles]
    inner = [
        (inner_r * math.cos(a), inner_r * math.sin(a))
        for a in angles[::-1]
    ]
    return _extrude(Polygon(outer + inner), height, z0)


def _hex_prism(across_flats: float, height: float, z0: float) -> trimesh.Trimesh:
    radius = across_flats / math.sqrt(3.0)
    points = [
        (
            radius * math.cos(math.radians(30 + 60 * index)),
            radius * math.sin(math.radians(30 + 60 * index)),
        )
        for index in range(6)
    ]
    return _extrude(Polygon(points), height, z0)


def _annulus(outer_d: float, inner_d: float, height: float, name: str):
    outer = _cylinder(outer_d / 2.0, height)
    inner = _cylinder(inner_d / 2.0, height + 0.4, -0.2)
    return _difference(outer, [inner], name)


def _flip_for_cavity_up(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    flipped = mesh.copy()
    matrix = np.eye(4)
    matrix[2, 2] = -1.0
    matrix[2, 3] = CAP_HEIGHT
    flipped.apply_transform(matrix)
    return _finish(flipped, f"{mesh.metadata.get('name', 'cap')} print orientation")


# ---------------------------------------------------------------------------
# Product geometry
# ---------------------------------------------------------------------------


def build_core() -> trimesh.Trimesh:
    body = _cylinder(CORE_DIAMETER / 2.0, CORE_HEIGHT, sections=CORE_SECTIONS)
    cutters = [
        # Bearing enters from the top and stops on a narrow outer-race shoulder.
        _cylinder(
            BEARING_POCKET_DIAMETER / 2.0,
            CORE_HEIGHT - BEARING_SEAT_Z + 0.2,
            BEARING_SEAT_Z,
            sections=128,
        ),
        _cylinder(
            BEARING_SHOULDER_OPENING / 2.0,
            BEARING_SEAT_Z + 0.2,
            -0.1,
            sections=128,
        ),
    ]
    slot_poly = Polygon(
        [
            (ARM_SLOT_INNER_R, -ARM_SLOT_INNER_HALF_W),
            (ARM_SLOT_OUTER_R, -ARM_SLOT_MOUTH_HALF_W),
            (ARM_SLOT_OUTER_R, ARM_SLOT_MOUTH_HALF_W),
            (ARM_SLOT_INNER_R, ARM_SLOT_INNER_HALF_W),
        ]
    )
    slot = _extrude(slot_poly, CORE_HEIGHT - ARM_SLOT_BOTTOM_Z + 0.2, ARM_SLOT_BOTTOM_Z)
    for index in range(ARM_SLOT_COUNT):
        rotated = slot.copy()
        rotated.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(index * 360.0 / ARM_SLOT_COUNT - 90.0),
                [0.0, 0.0, 1.0],
            )
        )
        cutters.append(rotated)
    return _difference(body, cutters, "Oggie Spin core")


def build_sleeve() -> trimesh.Trimesh:
    return _annulus(SLEEVE_OD, SLEEVE_ID, SLEEVE_HEIGHT, "R188 M3 centring sleeve")


def build_spacer(name: str) -> trimesh.Trimesh:
    return _annulus(SPACER_OD, SPACER_ID, SPACER_HEIGHT, name)


def _hub_body(name: str) -> trimesh.Trimesh:
    flange = _cylinder(HUB_FLANGE_DIAMETER / 2.0, HUB_FLANGE_HEIGHT)
    boss = _cylinder(
        HUB_BOSS_DIAMETER / 2.0,
        HUB_BOSS_HEIGHT,
        HUB_FLANGE_HEIGHT,
    )
    lugs = []
    for angle in (0.0, 120.0, 240.0):
        lugs.append(
            _annular_sector(
                HUB_LUG_INNER_R,
                HUB_LUG_OUTER_R,
                angle - HUB_LUG_ANGLE / 2.0,
                angle + HUB_LUG_ANGLE / 2.0,
                HUB_LUG_HEIGHT,
                HUB_LUG_Z,
                steps=8,
            )
        )
        lugs.append(
            _annular_sector(
                HUB_LUG_OUTER_R - 0.10,
                HUB_DETENT_OUTER_R,
                angle - HUB_DETENT_ANGLE / 2.0,
                angle + HUB_DETENT_ANGLE / 2.0,
                HUB_LUG_HEIGHT,
                HUB_LUG_Z,
                steps=4,
            )
        )
    return _union([flange, boss, *lugs], name)


def build_screw_hub() -> trimesh.Trimesh:
    body = _hub_body("screw-side bayonet hub blank")
    through = _cylinder(
        M3_CLEARANCE_DIAMETER / 2.0,
        HUB_TOTAL_HEIGHT + 0.4,
        -0.2,
        sections=64,
    )
    head = _cylinder(
        M3_HEAD_DIAMETER / 2.0,
        M3_HEAD_DEPTH + 0.2,
        HUB_TOTAL_HEIGHT - M3_HEAD_DEPTH,
        sections=64,
    )
    return _difference(body, [through, head], "screw-side permanent bayonet hub")


def build_nut_hub() -> trimesh.Trimesh:
    body = _hub_body("nut-side bayonet hub blank")
    through = _cylinder(
        M3_CLEARANCE_DIAMETER / 2.0,
        HUB_TOTAL_HEIGHT + 0.4,
        -0.2,
        sections=64,
    )
    nut = _hex_prism(
        M3_NYLOC_AF,
        M3_NYLOC_DEPTH + 0.2,
        HUB_TOTAL_HEIGHT - M3_NYLOC_DEPTH,
    )
    return _difference(body, [through, nut], "nut-side permanent bayonet hub")


def build_thumb_pad(name: str) -> trimesh.Trimesh:
    body = _cylinder(CAP_DIAMETER / 2.0, CAP_HEIGHT, sections=160)
    cutters = [
        _cylinder(CAP_CAVITY_R, CAP_CAVITY_DEPTH + 0.1, -0.1, sections=128)
    ]
    for angle in (0.0, 120.0, 240.0):
        # Vertical entry gate.
        cutters.append(
            _annular_sector(
                HUB_LUG_INNER_R - 0.05,
                CAP_ENTRY_OUTER_R,
                angle - CAP_ENTRY_ANGLE / 2.0,
                angle + CAP_ENTRY_ANGLE / 2.0,
                CAP_CAVITY_DEPTH + 0.1,
                -0.1,
                steps=10,
            )
        )
        # Cap turns +30°; the fixed hub lug therefore travels -30° in cap space.
        cutters.append(
            _annular_sector(
                HUB_LUG_INNER_R - 0.05,
                CAP_TRACK_OUTER_R,
                angle - CAP_LOCK_ROTATION_DEG - 5.0,
                angle + CAP_ENTRY_ANGLE / 2.0,
                CAP_TRACK_HEIGHT,
                CAP_TRACK_Z,
                steps=24,
            )
        )
        # Wider terminal pocket gives the lug-tip detent somewhere to settle.
        cutters.append(
            _annular_sector(
                HUB_LUG_INNER_R - 0.05,
                CAP_LOCK_POCKET_OUTER_R,
                angle - CAP_LOCK_ROTATION_DEG - CAP_ENTRY_ANGLE / 2.0,
                angle - CAP_LOCK_ROTATION_DEG + CAP_ENTRY_ANGLE / 2.0,
                CAP_TRACK_HEIGHT,
                CAP_TRACK_Z,
                steps=10,
            )
        )
    pad = _difference(body, cutters, name)
    return _flip_for_cavity_up(pad)


def build_meshes() -> list[tuple[str, trimesh.Trimesh, int]]:
    return [
        ("Oggie Spin five-slot core", build_core(), 1),
        ("R188 M3 centring sleeve", build_sleeve(), 1),
        ("Lower inner-race spacer", build_spacer("lower inner-race spacer"), 1),
        ("Upper inner-race spacer", build_spacer("upper inner-race spacer"), 1),
        ("Screw-side permanent bayonet hub", build_screw_hub(), 1),
        ("Nut-side permanent bayonet hub", build_nut_hub(), 1),
        ("Lower removable thumb pad", build_thumb_pad("lower removable thumb pad"), 2),
        ("Upper removable thumb pad", build_thumb_pad("upper removable thumb pad"), 2),
    ]


# ---------------------------------------------------------------------------
# Bambu Studio project
# ---------------------------------------------------------------------------


def _top_model() -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{bambu.CORE}" '
        f'xmlns:BambuStudio="{bambu.BAMBU}" xmlns:p="{bambu.PROD}" requiredextensions="p">',
        ' <metadata name="Application">BambuStudio-02.07.01.62</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        ' <metadata name="Title">Oggie Spin Bayonet Fit Test</metadata>',
        " <resources>",
    ]
    for plate_number, plate in enumerate(PLATES, start=1):
        top_id = 99 + plate_number
        lines.extend(
            [
                f'  <object id="{top_id}" p:UUID="{bambu.object_uuid(top_id, 0xABCDEF123456)}" type="model">',
                "   <components>",
            ]
        )
        for object_index, x, y, z in plate.components:
            lines.append(
                f'    <component p:path="/3D/Objects/object_{object_index}.model" '
                f'objectid="{object_index}" '
                f'p:UUID="{bambu.object_uuid(0x1000 + object_index, 0xABCDEF123456)}" '
                f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}"/>'
            )
        lines.extend(["   </components>", "  </object>"])
    lines.extend(
        [
            " </resources>",
            f' <build p:UUID="{bambu.object_uuid(9999, 0xABCDEF123456)}">',
        ]
    )
    for plate_number, plate in enumerate(PLATES, start=1):
        top_id = 99 + plate_number
        x, y, z = plate.position
        lines.append(
            f'  <item objectid="{top_id}" '
            f'p:UUID="{bambu.object_uuid(5000 + plate_number, 0xABCDEF123456)}" '
            f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}" printable="1"/>'
        )
    lines.extend([" </build>", "</model>"])
    return ("\n".join(lines) + "\n").encode()


def _model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    overrides = {
        "layer_height": "0.16",
        "wall_loops": "5",
        "top_shell_layers": "6",
        "bottom_shell_layers": "6",
        "sparse_infill_density": "25%",
        "sparse_infill_pattern": "gyroid",
        "outer_wall_speed": "50",
        "inner_wall_speed": "100",
        "small_perimeter_speed": "50%",
        "enable_support": "0",
        "brim_type": "no_brim",
        "seam_position": "back",
        "fuzzy_skin": "none",
    }
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for plate_number, plate in enumerate(PLATES, start=1):
        top_id = 99 + plate_number
        indices = [component[0] for component in plate.components]
        primary_extruder = objects[indices[0] - 1][2]
        face_count = sum(len(meshes[index - 1].faces) for index in indices)
        lines.extend(
            [
                f'  <object id="{top_id}">',
                f'    <metadata key="name" value="{escape(plate.title)}"/>',
                f'    <metadata key="extruder" value="{primary_extruder}"/>',
                *[
                    f'    <metadata key="{key}" value="{value}"/>'
                    for key, value in overrides.items()
                ],
                f'    <metadata face_count="{face_count}"/>',
            ]
        )
        for object_index in indices:
            name, source, extruder = objects[object_index - 1]
            mesh = meshes[object_index - 1]
            lines.extend(
                [
                    f'    <part id="{object_index}" subtype="normal_part">',
                    f'      <metadata key="name" value="{escape(name)}"/>',
                    '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                    f'      <metadata key="source_file" value="{escape(source.name)}"/>',
                    f'      <metadata key="source_object_id" value="{object_index - 1}"/>',
                    f'      <metadata key="source_volume_id" value="{object_index - 1}"/>',
                    f'      <metadata key="extruder" value="{extruder}"/>',
                    f'      <mesh_stat face_count="{len(mesh.faces)}" edges_fixed="0" '
                    'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                    "    </part>",
                ]
            )
        lines.append("  </object>")
    for plate_number, plate in enumerate(PLATES, start=1):
        top_id = 99 + plate_number
        lines.extend(
            [
                "  <plate>",
                f'    <metadata key="plater_id" value="{plate_number}"/>',
                f'    <metadata key="plater_name" value="{escape(plate.title)}"/>',
                '    <metadata key="locked" value="false"/>',
                '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
                f'    <metadata key="thumbnail_file" value="Metadata/plate_{plate_number}.png"/>',
                f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{plate_number}.png"/>',
                f'    <metadata key="top_file" value="Metadata/top_{plate_number}.png"/>',
                f'    <metadata key="pick_file" value="Metadata/pick_{plate_number}.png"/>',
                "    <model_instance>",
                f'      <metadata key="object_id" value="{top_id}"/>',
                '      <metadata key="instance_id" value="0"/>',
                f'      <metadata key="identify_id" value="{299 + plate_number}"/>',
                "    </model_instance>",
                "  </plate>",
            ]
        )
    lines.append("  <assemble>")
    for plate_number in range(1, len(PLATES) + 1):
        lines.append(
            f'    <assemble_item object_id="{99 + plate_number}" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def _preview_png(plate_number: int, size: int = 512) -> bytes:
    image = Image.new("RGBA", (size, size), (244, 241, 234, 255))
    draw = ImageDraw.Draw(image)
    draw.text((28, 24), f"Oggie Spin · plate {plate_number}", fill="#252A32")
    colour = FILAMENTS[0][1] if plate_number < 4 else FILAMENTS[1][1]
    if plate_number == 1:
        draw.ellipse((118, 118, 394, 394), fill=colour, outline="#252A32", width=5)
        draw.ellipse((210, 210, 302, 302), fill="#FFFFFF", outline="#252A32", width=4)
        for index in range(5):
            angle = math.radians(index * 72 - 90)
            cx = 256 + 126 * math.cos(angle)
            cy = 256 + 126 * math.sin(angle)
            draw.rounded_rectangle((cx - 18, cy - 28, cx + 18, cy + 28), radius=5, fill="#FFFFFF")
    elif plate_number == 2:
        for cx, radius in ((150, 46), (256, 58), (362, 58)):
            draw.ellipse((cx - radius, 256 - radius, cx + radius, 256 + radius), fill=colour, outline="#252A32", width=4)
            draw.ellipse((cx - 18, 238, cx + 18, 274), fill="#FFFFFF")
    elif plate_number == 3:
        for cx in (174, 338):
            draw.ellipse((cx - 72, 184, cx + 72, 328), fill=colour, outline="#252A32", width=4)
            for angle in (0, 120, 240):
                x = cx + 58 * math.cos(math.radians(angle))
                y = 256 + 58 * math.sin(math.radians(angle))
                draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill="#FFB089")
    else:
        for cx in (174, 338):
            draw.ellipse((cx - 78, 178, cx + 78, 334), fill=colour, outline="#252A32", width=5)
            draw.ellipse((cx - 38, 218, cx + 38, 294), fill="#FFFFFF", outline="#252A32", width=3)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _configure_filament_slots(settings: dict) -> None:
    """Expand the stock two-slot P2S template to the requested Matte colours."""
    old_profiles = settings.get("filament_settings_id")
    if not isinstance(old_profiles, list) or not old_profiles:
        raise RuntimeError("template has no filament profiles")
    old_count = len(old_profiles)
    slot_keys = {
        key
        for key in settings
        if key.startswith("filament_")
        and key not in {"filament_map", "filament_nozzle_map"}
    }
    slot_keys.update(
        """
        activate_air_filtration additional_cooling_fan_speed
        additional_fan_full_speed_layer chamber_temperatures
        close_additional_fan_first_x_layers close_fan_the_first_x_layers
        cool_plate_temp cool_plate_temp_initial_layer
        fan_max_speed fan_min_speed full_fan_speed_layer
        hot_plate_temp hot_plate_temp_initial_layer
        no_slow_down_for_cooling_on_outwalls nozzle_temperature
        nozzle_temperature_initial_layer nozzle_temperature_range_high
        nozzle_temperature_range_low slow_down_layer_time slow_down_min_speed
        supertack_plate_temp supertack_plate_temp_initial_layer
        textured_plate_temp textured_plate_temp_initial_layer
        """.split()
    )
    for key in slot_keys:
        current = settings.get(key)
        if (
            not isinstance(current, list)
            or not current
            or len(current) % old_count
        ):
            continue
        group_size = len(current) // old_count
        source = current[:group_size]
        settings[key] = source * len(FILAMENTS)

    variant_count = len(settings.get("print_extruder_variant", ["standard"]))
    settings["filament_extruder_variant"] = [
        variant
        for _slot in FILAMENTS
        for variant in settings.get(
            "print_extruder_variant",
            ["Direct Drive Standard"],
        )
    ]
    settings["filament_self_index"] = [
        str(index)
        for index in range(1, len(FILAMENTS) + 1)
        for _variant in range(variant_count)
    ]
    settings["filament_nozzle_map"] = ["0"] * len(FILAMENTS)
    settings["filament_extruder_compatibility"] = ["0"] * len(FILAMENTS)
    settings["filament_colour"] = [colour for _, colour in FILAMENTS]
    settings["default_filament_colour"] = [""] * len(FILAMENTS)
    settings["filament_settings_id"] = ["Bambu PLA Matte @BBL P2S"] * len(
        FILAMENTS
    )
    settings["filament_ids"] = ["GFA01"] * len(FILAMENTS)
    settings["filament_vendor"] = ["Bambu Lab"] * len(FILAMENTS)
    settings["filament_type"] = ["PLA"] * len(FILAMENTS)
    settings["flush_volumes_matrix"] = ["0"] * (
        len(FILAMENTS) * len(FILAMENTS)
    )
    settings["flush_volumes_vector"] = ["140"] * (len(FILAMENTS) * 2)


def build_bambu_project(
    output_path: Path,
    objects: list[tuple[str, Path, int]],
) -> Path:
    meshes = [trimesh.load_mesh(path, process=True) for _, path, _ in objects]
    for (name, _, _), mesh in zip(objects, meshes):
        _finish(mesh, name)
    bambu.OBJECTS = objects
    template_path = GENERATOR_DIR / "blank_project.3mf"
    with (
        zipfile.ZipFile(template_path) as template,
        zipfile.ZipFile(
            output_path,
            "w",
            zipfile.ZIP_DEFLATED,
            compresslevel=7,
        ) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", _top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr("Metadata/model_settings.config", _model_settings(objects, meshes))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["layer_height"] = "0.16"
        settings["initial_layer_print_height"] = "0.20"
        settings["wall_loops"] = "5"
        settings["top_shell_layers"] = "6"
        settings["bottom_shell_layers"] = "6"
        settings["wall_sequence"] = "inner wall/outer wall"
        settings["sparse_infill_density"] = "25%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        settings["outer_wall_speed"] = ["50", "50"]
        settings["inner_wall_speed"] = ["100", "100"]
        settings["small_perimeter_speed"] = "50%"
        settings["precise_outer_wall"] = "1"
        _configure_filament_slots(settings)
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=2, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))
        for plate_number in range(1, len(PLATES) + 1):
            preview = _preview_png(plate_number)
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(f"Metadata/{stem}_{plate_number}.png", preview)

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
    return output_path


# ---------------------------------------------------------------------------
# Validation and CLI
# ---------------------------------------------------------------------------


def _validate_package(path: Path) -> dict:
    with zipfile.ZipFile(path) as package:
        names = set(package.namelist())
        expected_objects = {
            f"3D/Objects/object_{index}.model" for index in range(1, 9)
        }
        missing = expected_objects - names
        if missing:
            raise RuntimeError(f"3MF is missing object models: {sorted(missing)}")
        settings_root = ET.fromstring(package.read("Metadata/model_settings.config"))
        plates = settings_root.findall("./plate")
        if len(plates) != len(PLATES):
            raise RuntimeError(f"3MF contains {len(plates)} plates, expected {len(PLATES)}")
        project = json.loads(package.read("Metadata/project_settings.config"))
        if project.get("printer_settings_id") != "Bambu Lab P2S 0.4 nozzle":
            raise RuntimeError("3MF lost the Bambu Lab P2S printer profile")
        if project.get("filament_settings_id") != ["Bambu PLA Matte @BBL P2S"] * 2:
            raise RuntimeError("3MF lost the Bambu PLA Matte profiles")
        return {
            "archive_entries": len(names),
            "objects": len(expected_objects),
            "plates": len(plates),
            "printer_profile": project["printer_settings_id"],
            "filament_profiles": project["filament_settings_id"],
            "layer_height": project["layer_height"],
        }


def _validate_bayonet_path(
    hub: trimesh.Trimesh,
    print_oriented_cap: trimesh.Trimesh,
) -> dict:
    cap = _flip_for_cavity_up(print_oriented_cap)
    cap.apply_translation([0.0, 0.0, HUB_FLANGE_HEIGHT])
    samples = {}
    for angle in range(0, int(CAP_LOCK_ROTATION_DEG) + 1, 5):
        rotated = cap.copy()
        rotated.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(angle),
                [0.0, 0.0, 1.0],
            )
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            intersection = trimesh.boolean.intersection(
                [hub, rotated],
                engine="manifold",
            )
            volume = 0.0 if intersection is None else float(intersection.volume)
        samples[str(angle)] = round(volume, 6)
    entry = samples["0"]
    locked = samples[str(int(CAP_LOCK_ROTATION_DEG))]
    maximum = max(samples.values())
    if entry > 0.001 or locked > 0.001:
        raise RuntimeError(
            "bayonet entry or terminal lock pocket contains hard interference"
        )
    if maximum < 0.01 or maximum > 0.35:
        raise RuntimeError(
            f"bayonet detent interference {maximum:.6f} mm³ is outside target"
        )
    return {
        "sampled_rotation_deg": list(range(0, int(CAP_LOCK_ROTATION_DEG) + 1, 5)),
        "intersection_volume_mm3": samples,
        "maximum_intersection_volume_mm3": maximum,
        "entry_clear": entry <= 0.001,
        "locked_clear": locked <= 0.001,
        "detent_flex_interference_present": maximum >= 0.01,
    }


def generate(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    if mesh_dir.exists():
        shutil.rmtree(mesh_dir)
    mesh_dir.mkdir(parents=True, exist_ok=True)

    built = build_meshes()
    objects: list[tuple[str, Path, int]] = []
    mesh_validation = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        filename = (
            name.lower()
            .replace(" + ", "_")
            .replace(" ", "_")
            .replace("-", "_")
        )
        path = mesh_dir / f"{index:02d}_{filename}.stl"
        mesh.export(path)
        reloaded = trimesh.load_mesh(path, process=True)
        _finish(reloaded, name)
        objects.append((name, path, extruder))
        mesh_validation.append(
            {
                "object": index,
                "name": name,
                "vertices": len(reloaded.vertices),
                "faces": len(reloaded.faces),
                "watertight": bool(reloaded.is_watertight),
                "volume_mm3": round(float(reloaded.volume), 3),
                "bounds_mm": np.round(reloaded.extents, 3).tolist(),
            }
        )

    output_path = out_dir / "Oggie_Spin_Bayonet_Fit_Test_P2S.3mf"
    build_bambu_project(output_path, objects)
    package_validation = _validate_package(output_path)
    bayonet_path_validation = _validate_bayonet_path(
        built[4][1],
        built[6][1],
    )

    report = {
        "project": "Oggie Spin R188 + axial-lock bayonet fit test",
        "status": "printable prototype; physical fit not yet approved",
        "units": "mm",
        "printer": "Bambu Lab P2S, 0.4 mm nozzle",
        "material": "Bambu PLA Matte",
        "core": {
            "diameter": CORE_DIAMETER,
            "height": CORE_HEIGHT,
            "arm_slots": ARM_SLOT_COUNT,
            "slot_pitch_deg": 360.0 / ARM_SLOT_COUNT,
            "slot_bottom_shelf": ARM_SLOT_BOTTOM_Z,
        },
        "bearing": {
            "type": "R188",
            "nominal": {
                "outer_diameter": R188_OD,
                "inner_diameter": R188_ID,
                "width": R188_WIDTH,
            },
            "pocket_diameter": BEARING_POCKET_DIAMETER,
            "signed_diametral_fit": round(
                BEARING_POCKET_DIAMETER - R188_OD,
                3,
            ),
            "diametral_interference": round(
                max(0.0, R188_OD - BEARING_POCKET_DIAMETER),
                3,
            ),
            "seat_z": round(BEARING_SEAT_Z, 3),
            "shoulder_opening": BEARING_SHOULDER_OPENING,
            "retention": "coupon transition fit; final outer-race retainer pending print result",
        },
        "cartridge": {
            "fastener": (
                f"M3 x {M3_SCREW_LENGTH} mm low-profile/button-head screw "
                "+ M3 nyloc nut"
            ),
            "sleeve": {"od": SLEEVE_OD, "id": SLEEVE_ID, "height": SLEEVE_HEIGHT},
            "spacer": {
                "od": SPACER_OD,
                "id": SPACER_ID,
                "height": round(SPACER_HEIGHT, 3),
            },
            "hub_to_core_gap_each_side": CAP_TO_CORE_GAP,
        },
        "bayonet": {
            "lug_count": 3,
            "rotation_deg": CAP_LOCK_ROTATION_DEG,
            "boss_diameter": HUB_BOSS_DIAMETER,
            "cap_cavity_diameter": 2 * CAP_CAVITY_R,
            "boss_radial_clearance_per_side": round(CAP_RADIAL_CLEARANCE, 3),
            "lug_radial_clearance": round(CAP_LUG_CLEARANCE, 3),
            "lug_axial_clearance": round(CAP_AXIAL_CLEARANCE, 3),
            "detent_radial_interference": round(
                HUB_DETENT_OUTER_R - CAP_TRACK_OUTER_R,
                3,
            ),
            "retention": "three undercut tracks + flex nubs + widened terminal pockets",
            "release": "twist 30 degrees back past the detents, then lift",
        },
        "print": {
            "plates": len(PLATES),
            "layer_height": 0.16,
            "wall_loops": 5,
            "infill": "25% gyroid",
            "supports": False,
            "cap_orientation": "finished top face on bed; bayonet cavity upward",
        },
        "physical_gates": [
            "R188 seats fully against the shoulder without cracking the core",
            "inner race spins freely after M3 cartridge is tightened",
            "both hub flanges retain at least 0.4 mm clearance from the core",
            "pads insert through all three gates and rotate 30 degrees to the stop",
            "locked pads have no visible axial lift and cannot pull straight off",
            "pads release by reverse twist and lift without whitening or chipped lugs",
            "repeat 100 lock/unlock cycles before production approval",
        ],
        "meshes": mesh_validation,
        "package": package_validation,
        "bayonet_path_validation": bayonet_path_validation,
    }
    (out_dir / "dimensions_and_validation.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("design/modular-spinner/bayonet-fit-test"),
    )
    args = parser.parse_args()
    generate(args.out)


if __name__ == "__main__":
    main()
