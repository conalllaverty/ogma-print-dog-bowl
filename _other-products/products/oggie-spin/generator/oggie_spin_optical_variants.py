#!/usr/bin/env python3
"""Generate separate two-plate optical-effect Oggie Spin projects.

Every project reuses the current matched three-rail + underside-clip mechanism and Ø12.82
R188 pocket. Only the core and five arms are included; reuse the retaining ring,
Tough+ cartridge and thumb pads from the complete project. All five arms share
one batch-optimised by-layer plate.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from shapely import union_all
from shapely.affinity import rotate as rotate_geometry
from shapely.geometry import LineString, Point, Polygon, box

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402


OUT_SUBDIR = "optical-variants"
REPORT_NAME = "optical_variants_validation.json"
INLAY_DEPTH = 0.32
INLAY_OVERTRAVEL = 0.10
LINE_WIDTH = 1.10
ORIGINAL_MODEL_SETTINGS = base._model_settings
ORIGINAL_CONFIGURE_FILAMENTS = base._configure_filament_slots

IVORY = ("Ivory White Matte", "#FFFFFF")
MARINE = ("Marine Blue Matte", "#3A8FCF")
DARK_CHOCOLATE = ("Dark Chocolate Matte", "#4D3324")
LEMON = ("Lemon Yellow Matte", "#F7D959")
SCARLET = ("Scarlet Red Matte", "#DE4343")
MANDARIN = ("Mandarin Orange Matte", "#F99963")
BATCH_POSITIONS = [
    (0.0, 0.0),
    (-70.0, -70.0),
    (70.0, -70.0),
    (70.0, 70.0),
    (-70.0, 70.0),
]
INVALID_BAMBU_NAME_CHARS = frozenset('<>:/\\|?*"')

VARIANTS = [
    {
        "key": "full_body_vortex",
        "title": "Full-body five-track vortex",
        "identifier": "VX",
        "output": "Oggie_Spin_Optical_Full_Body_Vortex_P2S.3mf",
        "effect": "vortex",
        "filaments": [DARK_CHOCOLATE, IVORY],
        "arm_extruders": [1, 1, 1, 1, 1],
        "recommended": "Dark Chocolate base + Ivory White vortex",
        "alternatives": [
            "Marine Blue base + Ivory White vortex",
            "Scarlet Red base + Lemon Yellow vortex",
        ],
    },
    {
        "key": "spiral_wave",
        "title": "Five-phase travelling spiral / wave",
        "identifier": "SP",
        "output": "Oggie_Spin_Optical_Spiral_Wave_P2S.3mf",
        "effect": "spiral",
        "filaments": [MARINE, IVORY],
        "arm_extruders": [1, 1, 1, 1, 1],
        "recommended": "Marine Blue base + Ivory White inlay",
        "alternatives": [
            "Dark Chocolate base + Lemon Yellow inlay",
            "Scarlet Red base + Ivory White inlay",
        ],
    },
    {
        "key": "chevron",
        "title": "Chevron reversal / barber-pole band",
        "identifier": "CH",
        "output": "Oggie_Spin_Optical_Chevron_Barber_Pole_P2S.3mf",
        "effect": "chevron",
        "filaments": [DARK_CHOCOLATE, LEMON],
        "arm_extruders": [1, 1, 1, 1, 1],
        "recommended": "Dark Chocolate base + Lemon Yellow inlay",
        "alternatives": [
            "Marine Blue base + Ivory White inlay",
            "Scarlet Red base + Ivory White inlay",
        ],
    },
    {
        "key": "strobe",
        "title": "Phone / LED strobe animation disk",
        "identifier": "ST",
        "output": "Oggie_Spin_Optical_Strobe_Animation_P2S.3mf",
        "effect": "strobe",
        "filaments": [MARINE, IVORY],
        "arm_extruders": [1, 1, 1, 1, 1],
        "recommended": "Marine Blue base + Ivory White animation marks",
        "alternatives": [
            "Dark Chocolate base + Lemon Yellow marks",
            "Scarlet Red base + Ivory White marks",
        ],
    },
    {
        "key": "opposing_drift",
        "title": "Dual-radius opposing drift rings",
        "identifier": "OD",
        "output": "Oggie_Spin_Optical_Opposing_Drift_P2S.3mf",
        "effect": "opposing",
        "filaments": [DARK_CHOCOLATE, IVORY],
        "arm_extruders": [1, 1, 1, 1, 1],
        "recommended": "Dark Chocolate base + Ivory White inlays",
        "alternatives": [
            "Marine Blue base + Ivory White inlays",
            "Scarlet Red base + Lemon Yellow inlays",
        ],
    },
    {
        "key": "colour_pulse",
        "title": "High-contrast colour pulse sequence",
        "identifier": "CP",
        "output": "Oggie_Spin_Optical_Colour_Pulse_P2S.3mf",
        "effect": "pulse",
        "filaments": [MARINE, IVORY, LEMON],
        "arm_extruders": [2, 1, 2, 1, 3],
        "recommended": "Ivory White / Marine Blue / Ivory White / Marine Blue / Lemon Yellow",
        "alternatives": [
            "Ivory White / Dark Chocolate / Ivory White / Dark Chocolate / Mandarin Orange",
            "Ivory White / Scarlet Red / Ivory White / Scarlet Red / Lemon Yellow",
        ],
    },
    {
        "key": "dashed_ladder",
        "title": "Expanding / contracting dashed ladder",
        "identifier": "LD",
        "output": "Oggie_Spin_Optical_Dashed_Ladder_P2S.3mf",
        "effect": "ladder",
        "filaments": [SCARLET, IVORY],
        "arm_extruders": [1, 1, 1, 1, 1],
        "recommended": "Scarlet Red base + Ivory White inlay",
        "alternatives": [
            "Marine Blue base + Lemon Yellow inlay",
            "Dark Chocolate base + Ivory White inlay",
        ],
    },
]

BITMAP_FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
}


def _safe_bambu_name(value: str) -> str:
    return "".join(
        "-" if character in INVALID_BAMBU_NAME_CHARS else character
        for character in value
    )


def _plate_position(number: int) -> tuple[float, float, float]:
    index = number - 1
    return (
        128.0 + (index % 3) * 312.0,
        128.0 - (index // 3) * 312.0,
        0.0,
    )


def _finish_components(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    components = [
        component
        for component in mesh.split(only_watertight=True)
        if abs(float(component.volume)) >= 0.002
    ]
    if not components:
        raise RuntimeError(f"{name} has no printable components")
    return base._finish(trimesh.util.concatenate(components), name)


def _extrude_geometry(
    geometry,
    height: float,
    z0: float,
    name: str,
) -> trimesh.Trimesh:
    polygons = (
        [geometry]
        if geometry.geom_type == "Polygon"
        else list(geometry.geoms)
    )
    meshes = [
        base._extrude(Polygon(polygon.exterior.coords), height, z0)
        for polygon in polygons
        if polygon.area > 0.001
    ]
    return _finish_components(trimesh.util.concatenate(meshes), name)


def _annular_sector(
    inner_r: float,
    outer_r: float,
    start_deg: float,
    end_deg: float,
    steps: int = 12,
) -> Polygon:
    angles = np.linspace(
        math.radians(start_deg),
        math.radians(end_deg),
        steps + 1,
    )
    outer = [(outer_r * math.cos(a), outer_r * math.sin(a)) for a in angles]
    inner = [
        (inner_r * math.cos(a), inner_r * math.sin(a))
        for a in angles[::-1]
    ]
    return Polygon(outer + inner)


def _dash_ring_geometry(
    radius: float,
    count: int,
    phase_deg: float,
    duty: float = 0.52,
    width: float = LINE_WIDTH,
):
    pitch = 360.0 / count
    dash_angle = pitch * duty
    return union_all(
        [
            _annular_sector(
                radius - width / 2.0,
                radius + width / 2.0,
                phase_deg + index * pitch - dash_angle / 2.0,
                phase_deg + index * pitch + dash_angle / 2.0,
            )
            for index in range(count)
        ]
    )


def _top_volume(geometry, name: str) -> trimesh.Trimesh:
    return _extrude_geometry(
        geometry,
        INLAY_DEPTH + INLAY_OVERTRAVEL,
        base.CORE_HEIGHT - INLAY_DEPTH,
        name,
    )


def _identifier_geometry(code: str):
    pixel = 0.62
    gap = 0.12
    letter_gap = 0.62
    letter_width = 5 * pixel + 4 * gap
    text_width = len(code) * letter_width + (len(code) - 1) * letter_gap
    x0 = -text_width / 2.0
    y0 = -14.15
    cells = []
    for letter_index, letter in enumerate(code):
        bitmap = BITMAP_FONT[letter]
        letter_x = x0 + letter_index * (letter_width + letter_gap)
        for row, bits in enumerate(bitmap):
            for column, bit in enumerate(bits):
                if bit != "1":
                    continue
                x = letter_x + column * (pixel + gap)
                y = y0 + (6 - row) * (pixel + gap)
                cells.append(box(x, y, x + pixel, y + pixel))
    return union_all(cells)


def _identifier_volume(code: str) -> trimesh.Trimesh:
    return _extrude_geometry(
        _identifier_geometry(code),
        INLAY_DEPTH + INLAY_OVERTRAVEL,
        -INLAY_OVERTRAVEL,
        f"{code} underside identifier",
    )


def _spiral_geometry():
    points = []
    for index in range(40):
        t = index / 39.0
        radius = 20.65 + 3.15 * t
        angle = math.radians(-16.0 + 32.0 * t + 7.0 * math.sin(math.pi * t))
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return LineString(points).buffer(0.65, cap_style="round", join_style="round")


def _vortex_geometry(phase_deg: float = 0.0):
    tracks = []
    for track_index in range(5):
        points = []
        for sample in range(96):
            t = sample / 95.0
            radius = 10.6 + 13.9 * t
            angle = math.radians(
                phase_deg
                + track_index * 72.0
                - 53.0
                + 70.0 * (t**0.90)
            )
            points.append(
                (
                    radius * math.cos(angle),
                    radius * math.sin(angle),
                )
            )
        tracks.append(
            LineString(points).buffer(
                0.90,
                cap_style="round",
                join_style="round",
            )
        )
    return union_all(tracks)


def _chevron_geometry():
    paths = []
    for radius_offset in (0.0, 1.15):
        points = [
            (
                (21.0 + radius_offset) * math.cos(math.radians(-15.0)),
                (21.0 + radius_offset) * math.sin(math.radians(-15.0)),
            ),
            (23.65 * math.cos(0.0), 0.0),
            (
                (21.0 + radius_offset) * math.cos(math.radians(15.0)),
                (21.0 + radius_offset) * math.sin(math.radians(15.0)),
            ),
        ]
        paths.append(
            LineString(points).buffer(0.48, cap_style="round", join_style="round")
        )
    return union_all(paths)


def _strobe_geometry():
    marks = []
    for index in range(10):
        angle = math.radians(index * 36.0)
        radius = 15.0 + 1.8 * math.sin(index * 2.0 * math.pi / 10.0)
        centre = (radius * math.cos(angle), radius * math.sin(angle))
        marks.append(Point(*centre).buffer(0.95, resolution=16))
        tail_angle = angle - math.radians(10.0)
        tail = (
            (radius - 2.2) * math.cos(tail_angle),
            (radius - 2.2) * math.sin(tail_angle),
        )
        marks.append(
            LineString([tail, centre]).buffer(
                0.38,
                cap_style="round",
                join_style="round",
            )
        )
    return union_all(marks)


def _opposing_core_geometry():
    return _dash_ring_geometry(17.2, 12, 0.0, duty=0.50)


def _opposing_arm_geometry():
    return _dash_ring_geometry(22.5, 30, 6.0, duty=0.42)


def _ladder_geometry():
    bars = []
    for index in range(20):
        angle = math.radians(index * 18.0)
        outer = 21.0 + 3.0 * (0.5 + 0.5 * math.sin(index * math.pi / 5.0))
        inner = 14.6
        start = (inner * math.cos(angle), inner * math.sin(angle))
        end = (outer * math.cos(angle), outer * math.sin(angle))
        bars.append(
            LineString([start, end]).buffer(
                0.46,
                cap_style="round",
                join_style="round",
            )
        )
    return union_all(bars)


def _effect_geometries(effect: str):
    if effect == "vortex":
        # The first installed arm is clocked at -90°. Fivefold symmetry means
        # every subsequent 72° arm uses the same local mesh while the core
        # needs the matching -90° phase for seamless core-to-arm tracks.
        return _vortex_geometry(-90.0), _vortex_geometry()
    if effect == "spiral":
        return None, _spiral_geometry()
    if effect == "chevron":
        return None, _chevron_geometry()
    if effect == "strobe":
        return _strobe_geometry(), None
    if effect == "opposing":
        return _opposing_core_geometry(), _opposing_arm_geometry()
    if effect == "pulse":
        return None, None
    if effect == "ladder":
        geometry = _ladder_geometry()
        return geometry, geometry
    raise ValueError(f"unknown optical effect {effect!r}")


def _split_inlay(
    source: trimesh.Trimesh,
    pattern_volume: trimesh.Trimesh,
    name: str,
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        inlay = trimesh.boolean.intersection(
            [source, pattern_volume],
            engine="manifold",
        )
        body = trimesh.boolean.difference(
            [source, pattern_volume],
            engine="manifold",
        )
    if inlay is None or inlay.is_empty or body is None or body.is_empty:
        raise RuntimeError(f"{name} flush-inlay boolean failed")
    return (
        _finish_components(body, f"{name} base"),
        _finish_components(inlay, f"{name} inlay"),
    )


def _combine_volumes(
    volumes: list[trimesh.Trimesh],
    name: str,
) -> trimesh.Trimesh:
    return _finish_components(trimesh.util.concatenate(volumes), name)


def _build_variant(variant: dict):
    safe_title = _safe_bambu_name(variant["title"])
    core_source = complete.build_complete_core()
    arm_source = complete._arm_installed_orientation(
        complete.build_arm(f"{variant['key']} reference arm")
    )
    core_geometry, arm_geometry = _effect_geometries(variant["effect"])

    core_volumes = [_identifier_volume(variant["identifier"])]
    if core_geometry is not None:
        core_volumes.append(
            _top_volume(core_geometry, f"{variant['key']} core optical pattern")
        )
    core_pattern = _combine_volumes(
        core_volumes,
        f"{variant['key']} combined core inlays",
    )
    core_base, core_inlay = _split_inlay(
        core_source,
        core_pattern,
        f"{variant['key']} core",
    )

    arm_base_print = complete._flip_arm_for_print(
        arm_source,
        f"{variant['key']} arm",
    )
    arm_inlay_print = None
    if arm_geometry is not None:
        arm_pattern = _top_volume(
            arm_geometry,
            f"{variant['key']} arm optical pattern",
        )
        arm_base_installed, arm_inlay_installed = _split_inlay(
            arm_source,
            arm_pattern,
            f"{variant['key']} arm",
        )
        arm_base_print = complete._flip_arm_for_print(
            arm_base_installed,
            f"{variant['key']} arm base",
        )
        arm_inlay_print = complete._flip_arm_for_print(
            arm_inlay_installed,
            f"{variant['key']} arm inlay",
        )

    built: list[tuple[str, trimesh.Trimesh, int]] = [
        (f"{safe_title} core", core_base, 1),
        (
            f"{variant['identifier']} core marks and underside identifier",
            core_inlay,
            2,
        ),
    ]
    plates = [
        base.Plate(
            f"{variant['identifier']} core · {safe_title}",
            ((1, 0.0, 0.0, 0.0), (2, 0.0, 0.0, 0.0)),
            _plate_position(1),
        )
    ]
    batch_components = []
    arm_groups: list[tuple[int, ...]] = []
    arm_base_ids: set[int] = set()
    arm_inlay_ids: set[int] = set()
    for index in range(5):
        x, y = BATCH_POSITIONS[index]
        base_id = len(built) + 1
        built.append(
            (
                f"{variant['identifier']} arm {index + 1}",
                arm_base_print.copy(),
                variant["arm_extruders"][index],
            )
        )
        arm_base_ids.add(base_id)
        group = [base_id]
        batch_components.append((base_id, x, y, 0.0))
        if arm_inlay_print is not None:
            inlay_id = len(built) + 1
            built.append(
                (
                    f"{variant['identifier']} arm inlay {index + 1}",
                    arm_inlay_print.copy(),
                    2,
                )
            )
            arm_inlay_ids.add(inlay_id)
            group.append(inlay_id)
            batch_components.append((inlay_id, x, y, 0.0))
        arm_groups.append(tuple(group))
    plates.append(
        base.Plate(
            f"{variant['identifier']} five-arm optical batch",
            tuple(batch_components),
            _plate_position(2),
        )
    )
    return built, plates, arm_base_ids, arm_inlay_ids, arm_groups


def _set_metadata(node: ET.Element, key: str, value: str) -> None:
    for item in node.findall("./metadata"):
        if item.get("key") == key:
            item.set("value", value)
            return
    ET.SubElement(node, "metadata", {"key": key, "value": value})


def _model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
    arm_base_ids: set[int],
    arm_inlay_ids: set[int],
) -> bytes:
    root = ET.fromstring(ORIGINAL_MODEL_SETTINGS(objects, meshes))
    for part_id in arm_base_ids:
        part = root.find(f".//part[@id='{part_id}']")
        if part is None:
            raise RuntimeError(f"missing arm base part {part_id}")
        _set_metadata(part, "wall_loops", "2")
        _set_metadata(part, "sparse_infill_density", "100%")
        _set_metadata(part, "sparse_infill_pattern", "gyroid")
    for part_id in arm_inlay_ids:
        part = root.find(f".//part[@id='{part_id}']")
        if part is None:
            raise RuntimeError(f"missing arm inlay part {part_id}")
        _set_metadata(part, "wall_loops", "2")
    for obj in root.findall("./object"):
        ids = {int(part.get("id")) for part in obj.findall("./part")}
        if ids & (arm_base_ids | arm_inlay_ids):
            _set_metadata(obj, "wall_loops", "2")
            _set_metadata(obj, "sparse_infill_density", "100%")
            _set_metadata(obj, "sparse_infill_pattern", "gyroid")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _preview_png(variant: dict, plate_number: int, size: int = 512) -> bytes:
    image = Image.new("RGBA", (size, size), (244, 241, 234, 255))
    draw = ImageDraw.Draw(image)
    draw.text(
        (24, 20),
        f"{variant['identifier']} · {variant['title']} · plate {plate_number}",
        fill="#252A32",
    )
    base_colour = variant["filaments"][0][1]
    mark_colour = variant["filaments"][1][1]
    if plate_number == 1:
        draw.ellipse(
            (116, 116, 396, 396),
            fill=base_colour,
            outline="#252A32",
            width=4,
        )
        draw.ellipse(
            (212, 212, 300, 300),
            fill="#F4F1EA",
            outline="#252A32",
            width=3,
        )
        draw.text((238, 360), variant["identifier"], fill=mark_colour)
    else:
        positions = ((256, 256), (135, 135), (377, 135), (377, 377), (135, 377))
        for index, (cx, cy) in enumerate(positions):
            draw.pieslice(
                (cx - 62, cy - 62, cx + 62, cy + 62),
                start=250,
                end=290,
                fill=variant["filaments"][
                    variant["arm_extruders"][index] - 1
                ][1],
                outline="#252A32",
                width=3,
            )
            if variant["effect"] not in {"strobe", "pulse"}:
                draw.arc(
                    (cx - 51, cy - 51, cx + 51, cy + 51),
                    start=250,
                    end=290,
                    fill=mark_colour,
                    width=6,
                )
        draw.text((134, 462), "BY LAYER · 0.6 SLOPE · 100% GYROID", fill="#252A32")
    buffer = __import__("io").BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _split_arm_batch_model_settings(
    data: bytes,
    variant: dict,
    arm_groups: list[tuple[int, ...]],
) -> tuple[bytes, int, list[int]]:
    root = ET.fromstring(data)
    plates = root.findall("./plate")
    if len(plates) != 2:
        raise RuntimeError("optical batch settings must start with two plates")
    core_instance = plates[0].find("./model_instance")
    arm_instance = plates[1].find("./model_instance")
    if core_instance is None or arm_instance is None:
        raise RuntimeError("optical batch plate lost its source instance")
    core_top_id = int(
        next(
            item.get("value")
            for item in core_instance.findall("./metadata")
            if item.get("key") == "object_id"
        )
    )
    source_arm_id = int(
        next(
            item.get("value")
            for item in arm_instance.findall("./metadata")
            if item.get("key") == "object_id"
        )
    )
    source_object = root.find(f"./object[@id='{source_arm_id}']")
    if source_object is None:
        raise RuntimeError("optical batch source arm object is missing")
    source_index = list(root).index(source_object)
    source_parts = {
        int(part.get("id")): part
        for part in source_object.findall("./part")
    }
    root.remove(source_object)

    arm_top_ids = [200 + index for index in range(5)]
    for index, (top_id, group) in enumerate(
        zip(arm_top_ids, arm_groups, strict=True),
        start=1,
    ):
        obj = copy.deepcopy(source_object)
        obj.set("id", str(top_id))
        for part in list(obj.findall("./part")):
            obj.remove(part)
        for part_id in group:
            obj.append(copy.deepcopy(source_parts[part_id]))
        _set_metadata(
            obj,
            "name",
            f"{variant['identifier']} optical arm {index}",
        )
        base_extruder = next(
            item.get("value")
            for item in source_parts[group[0]].findall("./metadata")
            if item.get("key") == "extruder"
        )
        _set_metadata(obj, "extruder", base_extruder)
        root.insert(source_index + index - 1, obj)

    for instance in list(plates[1].findall("./model_instance")):
        plates[1].remove(instance)
    for index, top_id in enumerate(arm_top_ids, start=1):
        instance = ET.SubElement(plates[1], "model_instance")
        ET.SubElement(
            instance,
            "metadata",
            {"key": "object_id", "value": str(top_id)},
        )
        ET.SubElement(
            instance,
            "metadata",
            {"key": "instance_id", "value": "0"},
        )
        ET.SubElement(
            instance,
            "metadata",
            {"key": "identify_id", "value": str(600 + index)},
        )

    assemble = root.find("./assemble")
    if assemble is None:
        raise RuntimeError("optical batch settings lost its assembly section")
    for item in list(assemble):
        if item.get("object_id") == str(source_arm_id):
            assemble.remove(item)
    for top_id in arm_top_ids:
        ET.SubElement(
            assemble,
            "assemble_item",
            {
                "object_id": str(top_id),
                "instance_id": "0",
                "transform": "1 0 0 0 1 0 0 0 1 0 0 0",
                "offset": "0 0 0",
            },
        )
    return (
        ET.tostring(root, encoding="utf-8", xml_declaration=True),
        core_top_id,
        arm_top_ids,
    )


def _batch_top_model(
    plates: list,
    core_top_id: int,
    arm_top_ids: list[int],
    arm_groups: list[tuple[int, ...]],
) -> bytes:
    bambu = base.bambu
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{bambu.CORE}" '
        f'xmlns:BambuStudio="{bambu.BAMBU}" xmlns:p="{bambu.PROD}" requiredextensions="p">',
        ' <metadata name="Application">BambuStudio-02.07.01.62</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        ' <metadata name="Title">Oggie Spin Optical Variant</metadata>',
        " <resources>",
        f'  <object id="{core_top_id}" '
        f'p:UUID="{bambu.object_uuid(core_top_id, 0x0F71CA1)}" type="model">',
        "   <components>",
    ]
    for object_index, x, y, z in plates[0].components:
        lines.append(
            f'    <component p:path="/3D/Objects/object_{object_index}.model" '
            f'objectid="{object_index}" '
            f'p:UUID="{bambu.object_uuid(0x1000 + object_index, 0x0F71CA1)}" '
            f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}"/>'
        )
    lines.extend(["   </components>", "  </object>"])

    component_positions = {
        object_index: (x, y, z)
        for object_index, x, y, z in plates[1].components
    }
    for top_id, group in zip(arm_top_ids, arm_groups, strict=True):
        lines.extend(
            [
                f'  <object id="{top_id}" '
                f'p:UUID="{bambu.object_uuid(top_id, 0x0F71CA1)}" type="model">',
                "   <components>",
            ]
        )
        for object_index in group:
            x, y, z = component_positions[object_index]
            lines.append(
                f'    <component p:path="/3D/Objects/object_{object_index}.model" '
                f'objectid="{object_index}" '
                f'p:UUID="{bambu.object_uuid(0x2000 + object_index, 0x0F71CA1)}" '
                f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}"/>'
            )
        lines.extend(["   </components>", "  </object>"])

    lines.extend(
        [
            " </resources>",
            f' <build p:UUID="{bambu.object_uuid(9999, 0x0F71CA1)}">',
        ]
    )
    core_x, core_y, core_z = plates[0].position
    lines.append(
        f'  <item objectid="{core_top_id}" '
        f'p:UUID="{bambu.object_uuid(5000, 0x0F71CA1)}" '
        f'transform="1 0 0 0 1 0 0 0 1 '
        f'{core_x:.3f} {core_y:.3f} {core_z:.3f}" printable="1"/>'
    )
    arm_x, arm_y, arm_z = plates[1].position
    for index, top_id in enumerate(arm_top_ids, start=1):
        lines.append(
            f'  <item objectid="{top_id}" '
            f'p:UUID="{bambu.object_uuid(5000 + index, 0x0F71CA1)}" '
            f'transform="1 0 0 0 1 0 0 0 1 '
            f'{arm_x:.3f} {arm_y:.3f} {arm_z:.3f}" printable="1"/>'
        )
    lines.extend([" </build>", "</model>"])
    return ("\n".join(lines) + "\n").encode()


def _rewrite_project_settings(
    path: Path,
    variant: dict,
    plates: list,
    arm_groups: list[tuple[int, ...]],
) -> None:
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
        rewritten_model_settings, core_top_id, arm_top_ids = (
            _split_arm_batch_model_settings(
                source.read("Metadata/model_settings.config"),
                variant,
                arm_groups,
            )
        )
        rewritten_top_model = _batch_top_model(
            plates,
            core_top_id,
            arm_top_ids,
            arm_groups,
        )
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "3D/3dmodel.model":
                data = rewritten_top_model
            elif item.filename == "Metadata/model_settings.config":
                data = rewritten_model_settings
            elif item.filename == "Metadata/project_settings.config":
                settings = json.loads(data)
                settings["print_sequence"] = (
                    "by object"
                    if variant["effect"] == "pulse"
                    else "by layer"
                )
                settings["enable_prime_tower"] = "1"
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
                settings["reduce_crossing_wall"] = "1"
                settings["max_travel_detour_distance"] = "0"
                data = json.dumps(
                    settings,
                    indent=2,
                    ensure_ascii=False,
                ).encode()
            target.writestr(item, data)
    temp_path.replace(path)


def _write_meshes(
    variant_dir: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> list[tuple[str, Path, int]]:
    mesh_dir = variant_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_').replace('/', '_')}.stl"
        mesh.export(path)
        reloaded = trimesh.load_mesh(path, process=True)
        base._finish(reloaded, f"serialized {name}")
        objects.append((name, path, extruder))
    return objects


def _build_project(
    variant: dict,
    variant_dir: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
    plates: list,
    arm_base_ids: set[int],
    arm_inlay_ids: set[int],
    arm_groups: list[tuple[int, ...]],
) -> tuple[Path, list[tuple[str, Path, int]]]:
    objects = _write_meshes(variant_dir, built)
    output = variant_dir / variant["output"]
    previous = (
        base.PLATES,
        base.FILAMENTS,
        base._preview_png,
        base._model_settings,
        base._configure_filament_slots,
    )
    try:
        base.PLATES = plates
        base.FILAMENTS = variant["filaments"]
        base._preview_png = lambda plate_number, size=512: _preview_png(
            variant,
            plate_number,
            size,
        )
        base._model_settings = (
            lambda project_objects, meshes: _model_settings(
                project_objects,
                meshes,
                arm_base_ids,
                arm_inlay_ids,
            )
        )
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
    _rewrite_project_settings(output, variant, plates, arm_groups)
    return output, objects


def _validate_variant(
    variant: dict,
    output: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
    plates: list,
    arm_base_ids: set[int],
    arm_inlay_ids: set[int],
    arm_groups: list[tuple[int, ...]],
) -> dict:
    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError(f"{variant['key']} 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = ET.fromstring(
            package.read("Metadata/model_settings.config")
        )
        unsafe_names = [
            item.get("value", "")
            for item in settings.findall(".//metadata")
            if item.get("key") == "name"
            and any(
                character in INVALID_BAMBU_NAME_CHARS
                for character in item.get("value", "")
            )
        ]
        if unsafe_names:
            raise RuntimeError(
                f"{variant['key']} contains invalid Bambu names: {unsafe_names}"
            )
        if len(settings.findall("./plate")) != 2:
            raise RuntimeError(f"{variant['key']} lost its two-plate layout")
        project = json.loads(
            package.read("Metadata/project_settings.config")
        )
        if len(project.get("filament_settings_id", [])) != len(
            variant["filaments"]
        ):
            raise RuntimeError(f"{variant['key']} lost a filament slot")
        expected_sequence = (
            "by object" if variant["effect"] == "pulse" else "by layer"
        )
        if project.get("print_sequence") != expected_sequence:
            raise RuntimeError(
                f"{variant['key']} lost {expected_sequence} sequencing"
            )
        if set(project.get("z_hop", [])) != {"0.6"}:
            raise RuntimeError(f"{variant['key']} lost 0.6 mm Z hop")
        if set(project.get("z_hop_types", [])) != {"Slope Lift"}:
            raise RuntimeError(f"{variant['key']} lost Slope Lift")
        if project.get("enable_prime_tower") != "1":
            raise RuntimeError(f"{variant['key']} lost its prime tower")
        for part_id in arm_base_ids:
            part = settings.find(f".//part[@id='{part_id}']")
            metadata = {
                item.get("key"): item.get("value")
                for item in part.findall("./metadata")
            }
            if (
                metadata.get("wall_loops") != "2"
                or metadata.get("sparse_infill_density") != "100%"
                or metadata.get("sparse_infill_pattern") != "gyroid"
            ):
                raise RuntimeError(
                    f"{variant['key']} arm {part_id} lost batch overrides"
                )
        arm_plate_instances = settings.findall(
            "./plate[2]/model_instance"
        )
        if len(arm_plate_instances) != len(arm_groups):
            raise RuntimeError(
                f"{variant['key']} arm plate does not contain five objects"
            )
        arm_top_ids = [
            int(
                next(
                    item.get("value")
                    for item in instance.findall("./metadata")
                    if item.get("key") == "object_id"
                )
            )
            for instance in arm_plate_instances
        ]
        arm_object_extruders = [
            int(
                next(
                    item.get("value")
                    for item in settings.find(
                        f"./object[@id='{top_id}']"
                    ).findall("./metadata")
                    if item.get("key") == "extruder"
                )
            )
            for top_id in arm_top_ids
        ]
        if arm_object_extruders != variant["arm_extruders"]:
            raise RuntimeError(
                f"{variant['key']} arm object colours changed"
            )

    original_core = complete.build_complete_core()
    core_total = built[0][1].volume + built[1][1].volume
    if abs(core_total - original_core.volume) > 0.01:
        raise RuntimeError(f"{variant['key']} core partition changed volume")
    original_arm = complete.build_arm("optical validation arm")
    arm_totals = []
    cursor = 2
    for _index in range(5):
        total = built[cursor][1].volume
        cursor += 1
        if arm_inlay_ids:
            total += built[cursor][1].volume
            cursor += 1
        arm_totals.append(float(total))
    if max(abs(total - original_arm.volume) for total in arm_totals) > 0.01:
        raise RuntimeError(f"{variant['key']} arm partition changed volume")
    if max(arm_totals) - min(arm_totals) > 1e-6:
        raise RuntimeError(f"{variant['key']} arms are not mass matched")

    identifier_volume = built[1][1]
    if identifier_volume.bounds[0, 2] > 0.001:
        raise RuntimeError(f"{variant['key']} identifier is not on core underside")
    vortex_phase_error = None
    if variant["effect"] == "vortex":
        core_geometry, arm_geometry = _effect_geometries("vortex")
        vortex_phase_error = core_geometry.symmetric_difference(
            rotate_geometry(
                arm_geometry,
                -90.0,
                origin=(0.0, 0.0),
            )
        ).area
        if vortex_phase_error > 1e-6:
            raise RuntimeError(
                f"vortex core-to-arm phase error is {vortex_phase_error:.9f} mm²"
            )
    return {
        "key": variant["key"],
        "title": variant["title"],
        "project": output.name,
        "identifier": variant["identifier"],
        "identifier_side": "core underside / bed face",
        "plates": len(plates),
        "objects": len(built),
        "arm_plate": "five arms on one plate",
        "arm_plate_print_sequence": expected_sequence,
        "arm_plate_z_hop_mm": 0.6,
        "arm_plate_z_hop_type": "Slope Lift",
        "arm_plate_infill": "100% gyroid",
        "arm_plate_wall_loops": 2,
        "recommended_matte_colours": variant["recommended"],
        "alternative_matte_colours": variant["alternatives"],
        "filament_slots": [
            {"slot": index, "name": name, "hex": colour}
            for index, (name, colour) in enumerate(
                variant["filaments"],
                start=1,
            )
        ],
        "arm_volume_spread_mm3": round(max(arm_totals) - min(arm_totals), 9),
        **(
            {
                "vortex_core_to_arm_phase_error_mm2": round(
                    vortex_phase_error,
                    9,
                )
            }
            if vortex_phase_error is not None
            else {}
        ),
        "mechanical_geometry": "Ø12.82 core; detent-free 0.02 mm friction-rib arms",
        "physical_status": "optical and fit testing pending",
    }


def generate(out_dir: Path) -> list[Path]:
    root = Path(out_dir) / OUT_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    outputs = []
    reports = []
    for variant in VARIANTS:
        variant_dir = root / variant["key"]
        variant_dir.mkdir(parents=True, exist_ok=True)
        (
            built,
            plates,
            arm_base_ids,
            arm_inlay_ids,
            arm_groups,
        ) = _build_variant(variant)
        output, _objects = _build_project(
            variant,
            variant_dir,
            built,
            plates,
            arm_base_ids,
            arm_inlay_ids,
            arm_groups,
        )
        reports.append(
            _validate_variant(
                variant,
                output,
                built,
                plates,
                arm_base_ids,
                arm_inlay_ids,
                arm_groups,
            )
        )
        outputs.append(output)
    (root / REPORT_NAME).write_text(
        json.dumps({"variants": reports}, indent=2) + "\n",
        encoding="utf-8",
    )
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in generate(args.out):
        print(path)
