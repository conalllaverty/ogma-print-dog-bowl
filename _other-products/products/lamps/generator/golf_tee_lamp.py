#!/usr/bin/env python3
"""Print-ready five-plate P2S project for the Golf Tee LED lamp.

All-PLA workflow (no PETG support interface):

1. Golf ball shade — Jade White PLA Basic (translucent solid shell), opening on bed
2. Golf tee — Caramel Matte; Ø5 filleted bayonet pins + spring snap
3. Grass base — Grass Green Matte; 45° ballast seat; tree supports; fuzzy turf
4. Ballast cover — Grass Green Matte; 1.2 mm tapered plug
5. Reflector cup — Ivory White Matte; 0.8 mm liner under the MH001

MH001 seats in the notched reflector inside the tee cup. Its side-exit lead
runs through a radial chase into a 21 × 12 mm keyed controller passage, then
exits under the base. Ball locks with a 3-lug bayonet and end-of-travel detent
(no epoxy).

Run from the repository root:

    .venv/bin/python products/lamps/generator/golf_tee_lamp.py \\
        --out design/golf-tee-lamp/production
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET

import numpy as np
import trimesh
from PIL import Image, ImageDraw

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ogma import assets  # noqa: E402

from ogma import bambu_project as bambu  # noqa: E402
import golf_tee_lamp_config as cfg  # noqa: E402
import golf_tee_lamp_geometry as geo  # noqa: E402
from ogma.filaments import load_palette, resolve_filament  # noqa: E402

TEE_FILAMENT = cfg.TEE_FILAMENT_ID
GRASS_FILAMENT = cfg.BASE_FILAMENT_ID
REFLECTOR_FILAMENT = cfg.REFLECTOR_FILAMENT_ID
MATTE_PROFILE = "Bambu PLA Matte @BBL P2S"

PLATE_PITCH = 312.0
PLATE_COLUMNS = 3


@dataclass
class Part:
    label: str
    filename: str
    mesh: trimesh.Trimesh
    plate: int
    extruder: int
    filament_id: str | None = None
    filament_hex: str | None = None
    filament_profile: str = MATTE_PROFILE
    filament_label: str = ""
    profile: dict = field(default_factory=dict)
    preview_colour: str = "#D6CEBE"
    paint_fuzzy: np.ndarray | None = None


# Solid 1.6 mm shell — 4 walls, 0% sparse infill (no gyroid shadowing).
# Dimple-friendly seams: Arachne + inner→outer + aligned scarf (contour+hole).
# Variable layer height is baked into the 3MF — see SPEC.md.
BALL_PROFILE = {
    "enable_support": "0",
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "wall_sequence": "inner wall/outer wall",
    "wall_loops": "4",
    "sparse_infill_density": "0%",
    "sparse_infill_pattern": "zig-zag",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "outer_wall_speed": "80",
    "inner_wall_speed": "120",
    "brim_type": "outer_only",
    "brim_width": "5",
    # Never "random" on a dimpled sphere — nubs land inside every dimple.
    "seam_position": "back",
    # Scarf joint (Studio 1.9+): "all" = Contour and Hole.
    "has_scarf_joint_seam": "1",
    "override_filament_scarf_seam_setting": "1",
    "seam_slope_type": "all",
    "apply_scarf_seam_on_circles": "1",
    "seam_slope_conditional": "1",
    "seam_slope_inner_walls": "1",
    # Outer walls only — keeps the internal bayonet seat crisp.
    "fuzzy_skin": cfg.BALL_FUZZY_SKIN,
    "fuzzy_skin_thickness": f"{cfg.BALL_FUZZY_THICKNESS:.2f}",
    "fuzzy_skin_point_distance": f"{cfg.BALL_FUZZY_POINT_DISTANCE:.2f}",
    "fuzzy_skin_first_layer": "0",
    "reduce_infill_retraction_mode": "Disabled",
}

TEE_PROFILE = {
    "enable_support": "0",
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "4",
    "outer_wall_speed": "150",
    "inner_wall_speed": "250",
    "bridge_speed": "20",
    "brim_type": "outer_only",
    "brim_width": "8",
    "brim_object_gap": "0.1",
    "seam_position": "aligned",
    "fuzzy_skin": "none",
    "reduce_infill_retraction_mode": "Disabled",
}

BASE_PROFILE = {
    "enable_support": "1",
    "support_type": "tree(auto)",
    "support_threshold_angle": "40",
    "support_on_build_plate_only": "1",
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "3",
    "top_surface_pattern": "monotonic",
    "outer_wall_speed": "150",
    "inner_wall_speed": "250",
    "brim_type": "auto_brim",
    "seam_position": "aligned",
    # none = allow paint; top-face facets carry paint_fuzzy_skin (snap-cleared).
    "fuzzy_skin": "none",
    "fuzzy_skin_thickness": f"{cfg.BASE_FUZZY_THICKNESS:.2f}",
    "fuzzy_skin_point_distance": f"{cfg.BASE_FUZZY_POINT_DISTANCE:.2f}",
    "reduce_infill_retraction_mode": "Disabled",
}

COVER_PROFILE = {
    "enable_support": "0",
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "wall_loops": "3",
    # The 1.2 mm plate is fully occupied by 3 bottom + 3 top layers.
    # Keep sparse infill off: Studio 2.7 rejects gyroid at 100% density.
    "sparse_infill_density": "0%",
    "sparse_infill_pattern": "zig-zag",
    "top_shell_layers": "3",
    "bottom_shell_layers": "3",
    "brim_type": "auto_brim",
    "seam_position": "aligned",
    "fuzzy_skin": "none",
    "reduce_infill_retraction_mode": "Disabled",
}

REFLECTOR_PROFILE = {
    "enable_support": "0",
    "layer_height": "0.16",
    "wall_generator": "arachne",
    "wall_loops": "3",
    # The 0.8 mm floor and wall are entirely shells/perimeters.
    # Keep sparse infill off: Studio 2.7 rejects gyroid at 100% density.
    "sparse_infill_density": "0%",
    "sparse_infill_pattern": "zig-zag",
    "top_shell_layers": "4",
    "bottom_shell_layers": "4",
    "brim_type": "auto_brim",
    "seam_position": "aligned",
    "fuzzy_skin": "none",
    "reduce_infill_retraction_mode": "Disabled",
}


def plate_position(plate: int) -> tuple[float, float, float]:
    index = plate - 1
    return (
        128.0 + PLATE_PITCH * (index % PLATE_COLUMNS),
        128.0 - PLATE_PITCH * (index // PLATE_COLUMNS),
        0.0,
    )


def centre_on_bed(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    centred = mesh.copy()
    low, high = centred.bounds
    centred.apply_translation(
        [-(low[0] + high[0]) / 2.0, -(low[1] + high[1]) / 2.0, -low[2]]
    )
    return centred


def build_parts(include_dimples: bool = True) -> tuple[list[Part], dict]:
    ball, ball_report = geo.build_ball_print(include_dimples=include_dimples)
    ball = centre_on_bed(ball)

    tee, tee_report = geo.build_tee_print()
    tee = centre_on_bed(tee)

    grass, grass_report = geo.build_grass_base()
    grass = centre_on_bed(grass)
    grass_paint = geo.base_top_fuzzy_mask(grass)

    cover, cover_report = geo.build_ballast_cover()
    cover = centre_on_bed(cover)

    reflector, reflector_report = geo.build_reflector_cup()
    reflector = centre_on_bed(reflector)

    palette = load_palette()
    caramel = resolve_filament(TEE_FILAMENT, palette)
    grass_fil = resolve_filament(GRASS_FILAMENT, palette)
    ivory = resolve_filament(REFLECTOR_FILAMENT, palette)

    parts = [
        Part(
            label="Golf ball shade",
            filename="golf_ball.stl",
            mesh=ball,
            plate=1,
            extruder=1,
            filament_id=None,
            filament_hex=cfg.BALL_FILAMENT_HEX,
            filament_profile=cfg.BALL_FILAMENT_PROFILE,
            filament_label=cfg.BALL_FILAMENT_LABEL,
            profile=BALL_PROFILE,
            preview_colour=cfg.BALL_FILAMENT_HEX,
        ),
        Part(
            label="Golf tee",
            filename="golf_tee.stl",
            mesh=tee,
            plate=2,
            extruder=2,
            filament_id=TEE_FILAMENT,
            filament_hex=caramel.hex,
            filament_profile=MATTE_PROFILE,
            filament_label=cfg.TEE_FILAMENT_LABEL_OVERRIDE,
            profile=TEE_PROFILE,
            preview_colour=caramel.hex,
        ),
        Part(
            label="Grass base",
            filename="golf_grass_base.stl",
            mesh=grass,
            plate=3,
            extruder=3,
            filament_id=GRASS_FILAMENT,
            filament_hex=grass_fil.hex,
            filament_profile=MATTE_PROFILE,
            filament_label=f"Bambu PLA Matte · {grass_fil.name}",
            profile=BASE_PROFILE,
            preview_colour=grass_fil.hex,
            paint_fuzzy=grass_paint,
        ),
        Part(
            label="Ballast cover",
            filename="golf_ballast_cover.stl",
            mesh=cover,
            plate=4,
            extruder=3,
            filament_id=GRASS_FILAMENT,
            filament_hex=grass_fil.hex,
            filament_profile=MATTE_PROFILE,
            filament_label=f"Bambu PLA Matte · {grass_fil.name}",
            profile=COVER_PROFILE,
            preview_colour=grass_fil.hex,
        ),
        Part(
            label="LED reflector cup",
            filename="golf_reflector_cup.stl",
            mesh=reflector,
            plate=5,
            extruder=4,
            filament_id=REFLECTOR_FILAMENT,
            filament_hex=ivory.hex,
            filament_profile=MATTE_PROFILE,
            filament_label=f"Bambu PLA Matte · {ivory.name}",
            profile=REFLECTOR_PROFILE,
            preview_colour=ivory.hex,
        ),
    ]

    report = {
        "product": "Golf Tee LED lamp",
        "kit": "Bambu Lab LED Lamp Kit-001 (MH001)",
        "workflow": "all-PLA",
        "summary": cfg.summary(),
        "ball": ball_report,
        "tee": tee_report,
        "grass_base": grass_report,
        "ballast_cover": cover_report,
        "reflector": reflector_report,
        "plates": [
            {
                "plate": part.plate,
                "label": part.label,
                "filament": part.filament_label,
                "profile": part.filament_profile,
                "faces": len(part.mesh.faces),
                "volume_cm3": round(float(part.mesh.volume) / 1000.0, 2),
                "fuzzy_painted_faces": (
                    int(part.paint_fuzzy.sum()) if part.paint_fuzzy is not None else 0
                ),
            }
            for part in parts
        ],
        "slice_notes": [
            "FINAL Plate 1 check: Enable Support = OFF",
            "FINAL Plate 1 check: VLH is baked into the 3MF (0.20 mm → 0.08 mm on top ~20%); confirm in Preview with Layer Height colouring",
            "FINAL Plate 1 check: Sparse Infill = 0%, Wall Loops = 4 (1.6 mm solid shell)",
            "Plate 1 seams: Back + Scarf Contour and Hole; Arachne; Inner/Outer; Wipe 4 mm",
            "Plate 1 fuzzy: Outer walls only, 0.04 mm thick / 0.08 mm point distance",
            "Plate 1 geometry: relaxed equal-area dimple layout with exact centre/profile sampling; nominal 1.4 mm depth is present in the exported mesh",
            "Plate 2: snap foot on bed, 8 mm brim, supports off, 20 mm/s bridges; 21 × 12 mm keyed controller passage and side-lead chase",
            "Base: fuzzy paint already clears the snap entry; do not re-enable global top fuzzy",
            "Plate 3: tree supports stay ON for the ballast pocket roof; cover seat is the inward-narrowing 45° loft",
            "Plate 4: print large face down; insert the tapered cover small-face-first behind the felt",
            "Plates 4–5: fully solid by shells/walls; keep sparse infill at 0% (Studio 2.7 rejects 100% gyroid)",
        ],
        "assembly_notes": [
            "Fill the base ballast pocket with 200–300 g steel washers/shot; drop in the ballast cover (optional CA); fit the 110 mm square felt pad",
            "Feed the USB and controller straight through the tee and base centre before snapping the revised tee foot into the grass base",
            "Align the Ivory reflector notch with the tee chase; seat the MH001 with its side lead in the chase; route only the flexible lead through the underside side trench",
            "Drop the ball onto the tee pins at the entry slots; twist ~60° until the detent clicks (reverse to service the LED)",
        ],
    }
    return parts, report


def model_settings(parts: list[Part]) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for part in parts:
        top_id = 99 + part.plate
        lines.extend(
            [
                f'  <object id="{top_id}">',
                f'    <metadata key="name" value="{escape(part.label)}"/>',
                f'    <metadata key="extruder" value="{part.extruder}"/>',
                *[
                    f'    <metadata key="{key}" value="{value}"/>'
                    for key, value in part.profile.items()
                ],
                f'    <metadata face_count="{len(part.mesh.faces)}"/>',
                f'    <part id="{part.plate}" subtype="normal_part">',
                f'      <metadata key="name" value="{escape(part.label)}"/>',
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'      <metadata key="source_file" value="{escape(part.filename)}"/>',
                f'      <metadata key="source_object_id" value="{part.plate - 1}"/>',
                f'      <metadata key="source_volume_id" value="{part.plate - 1}"/>',
                f'      <metadata key="extruder" value="{part.extruder}"/>',
                f'      <mesh_stat face_count="{len(part.mesh.faces)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                "    </part>",
                "  </object>",
            ]
        )
    for part in parts:
        top_id = 99 + part.plate
        lines.extend(
            [
                "  <plate>",
                f'    <metadata key="plater_id" value="{part.plate}"/>',
                f'    <metadata key="plater_name" value="{escape(part.label)}"/>',
                '    <metadata key="locked" value="false"/>',
                '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
                f'    <metadata key="thumbnail_file" value="Metadata/plate_{part.plate}.png"/>',
                f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{part.plate}.png"/>',
                f'    <metadata key="top_file" value="Metadata/top_{part.plate}.png"/>',
                f'    <metadata key="pick_file" value="Metadata/pick_{part.plate}.png"/>',
                "    <model_instance>",
                f'      <metadata key="object_id" value="{top_id}"/>',
                '      <metadata key="instance_id" value="0"/>',
                f'      <metadata key="identify_id" value="{299 + part.plate}"/>',
                "    </model_instance>",
                "  </plate>",
            ]
        )
    lines.append("  <assemble>")
    for part in parts:
        lines.append(
            f'    <assemble_item object_id="{99 + part.plate}" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def plate_preview(part: Part, size: int = 512) -> bytes:
    image = Image.new("RGBA", (size, size), (244, 241, 234, 255))
    draw = ImageDraw.Draw(image)
    draw.text((24, 22), f"Golf Tee · plate {part.plate}", fill="#252A32")
    draw.text((24, 48), part.label[:40], fill="#5A5248")
    colour = part.preview_colour
    cx = cy = size // 2
    if part.plate == 1:
        r = 150
        draw.ellipse((cx - r, cy - r + 10, cx + r, cy + r + 10), fill=colour, outline="#252A32", width=4)
        for index in range(18):
            angle = math.radians(index * 20)
            dx = 90 * math.cos(angle)
            dy = 90 * math.sin(angle)
            draw.ellipse(
                (cx + dx - 8, cy + dy - 4, cx + dx + 8, cy + dy + 8),
                outline="#B8B0A0",
                width=2,
            )
        draw.ellipse((cx - 55, cy + 50, cx + 55, cy + 120), fill="#F4F1EA", outline="#252A32", width=3)
    elif part.plate == 2:
        draw.polygon(
            [
                (cx - 20, cy + 140),
                (cx + 20, cy + 140),
                (cx + 12, cy + 40),
                (cx + 70, cy - 20),
                (cx + 70, cy - 80),
                (cx - 70, cy - 80),
                (cx - 70, cy - 20),
                (cx - 12, cy + 40),
            ],
            fill=colour,
            outline="#252A32",
        )
        draw.ellipse((cx - 10, cy + 60, cx + 10, cy + 90), fill="#F4F1EA", outline="#252A32", width=2)
        draw.ellipse((cx - 40, cy - 70, cx + 40, cy - 30), fill="#F4F1EA", outline="#252A32", width=2)
    elif part.plate == 3:
        # Rounded-square grass pad
        half = 130
        draw.rounded_rectangle(
            (cx - half, cy - half + 20, cx + half, cy + half + 20),
            radius=28,
            fill=colour,
            outline="#252A32",
            width=4,
        )
        draw.ellipse((cx - 70, cy + 10, cx + 70, cy + 90), fill="#F4F1EA", outline="#252A32", width=3)
        draw.rectangle((cx, cy + 40, cx + 120, cy + 55), fill="#F4F1EA", outline="#252A32", width=2)
    elif part.plate == 4:
        half = 110
        draw.rounded_rectangle(
            (cx - half, cy - half + 10, cx + half, cy + half + 10),
            radius=22,
            fill=colour,
            outline="#252A32",
            width=4,
        )
        draw.ellipse((cx - 55, cy - 35, cx + 55, cy + 55), fill="#F4F1EA", outline="#252A32", width=3)
    else:
        draw.ellipse((cx - 90, cy - 70, cx + 90, cy + 90), fill=colour, outline="#252A32", width=4)
        draw.ellipse((cx - 70, cy - 50, cx + 70, cy + 70), fill="#F4F1EA", outline="#252A32", width=3)
        draw.ellipse((cx - 18, cy - 5, cx + 18, cy + 30), fill=colour, outline="#252A32", width=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def configure_filament_slots(
    settings: dict, filament_slots: list[tuple[str, str]]
) -> None:
    """Expand the stock dual-variant P2S arrays for each filament slot."""
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
        circle_compensation_speed close_additional_fan_first_x_layers
        close_fan_the_first_x_layers complete_print_exhaust_fan_speed
        cool_plate_temp cool_plate_temp_initial_layer
        cooling_perimeter_transition_distance cooling_slowdown_logic
        counter_coef_1 counter_coef_2 counter_coef_3
        counter_limit_max counter_limit_min diameter_limit
        during_print_exhaust_fan_speed eng_plate_temp
        eng_plate_temp_initial_layer fan_cooling_layer_time
        fan_max_speed fan_min_speed first_x_layer_fan_speed
        full_fan_speed_layer hole_coef_2 hole_coef_3
        hole_limit_max hole_limit_min hot_plate_temp
        hot_plate_temp_initial_layer impact_strength_z
        long_retractions_when_ec no_slow_down_for_cooling_on_outwalls
        nozzle_temperature nozzle_temperature_initial_layer
        nozzle_temperature_range_high nozzle_temperature_range_low
        overhang_fan_speed overhang_fan_threshold
        overhang_threshold_participating_cooling
        override_process_overhang_speed reduce_fan_stop_start_freq
        required_nozzle_HRC retraction_distances_when_ec
        slow_down_for_layer_cooling slow_down_layer_time
        slow_down_min_speed temperature_vitrification
        textured_plate_temp textured_plate_temp_initial_layer
        volumetric_speed_coefficients
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
        old_groups = [
            current[index * group_size : (index + 1) * group_size]
            for index in range(old_count)
        ]
        expanded = []
        for _colour, profile in filament_slots:
            source_index = (
                old_profiles.index(profile) if profile in old_profiles else 0
            )
            expanded.extend(old_groups[source_index])
        settings[key] = expanded

    variant_count = len(
        settings.get("print_extruder_variant", ["Direct Drive Standard"])
    )
    settings["filament_extruder_variant"] = [
        variant
        for _slot in filament_slots
        for variant in settings.get(
            "print_extruder_variant",
            ["Direct Drive Standard"],
        )
    ]
    settings["filament_self_index"] = [
        str(index)
        for index in range(1, len(filament_slots) + 1)
        for _variant in range(variant_count)
    ]
    settings["filament_ids"] = ["GFA01" for _slot in filament_slots]
    settings["filament_multi_colour"] = [
        colour for colour, _profile in filament_slots
    ]
    settings["filament_colour"] = [
        colour for colour, _profile in filament_slots
    ]
    settings["filament_settings_id"] = [
        profile for _colour, profile in filament_slots
    ]
    settings["default_filament_colour"] = [""] * len(filament_slots)

    grid = len(filament_slots)
    settings["flush_volumes_matrix"] = [
        "0" if row == column else "280"
        for row in range(grid)
        for column in range(grid)
    ]
    settings["flush_volumes_vector"] = ["140"] * (grid * 2)


def layer_heights_profile_bytes(
    object_profiles: dict[int, list[float]],
) -> bytes:
    """Bambu Studio `Metadata/layer_heights_profile.txt` payload."""
    lines: list[str] = []
    for object_id, profile in sorted(object_profiles.items()):
        if len(profile) < 4 or len(profile) % 2:
            raise ValueError(
                f"VLH profile for object {object_id} must be even and ≥4 values"
            )
        body = ";".join(f"{value:.6f}" for value in profile)
        lines.append(f"object_id={object_id}|{body}")
    return ("\n".join(lines) + "\n").encode()


def content_types_with_txt(template_xml: bytes) -> bytes:
    """Ensure .txt is declared so Studio accepts layer_heights_profile.txt."""
    text = template_xml.decode()
    if 'Extension="txt"' in text:
        return template_xml
    return text.replace(
        '<Default Extension="gcode" ContentType="text/x.gcode"/>',
        (
            '<Default Extension="gcode" ContentType="text/x.gcode"/>\n'
            ' <Default Extension="txt" ContentType="text/plain"/>'
        ),
    ).encode()


def write_project(
    parts: list[Part],
    out_dir: Path,
    output_name: str,
    filament_slots: list[tuple[str, str]],
) -> Path:
    for part in parts:
        x, y, _z = plate_position(part.plate)
        index = part.plate - 1
        local_x = x - PLATE_PITCH * (index % PLATE_COLUMNS)
        local_y = y + PLATE_PITCH * (index // PLATE_COLUMNS)
        low, high = part.mesh.bounds
        if (
            low[0] + local_x - 8.0 < 0.0
            or high[0] + local_x + 8.0 > 256.0
            or low[1] + local_y - 8.0 < 0.0
            or high[1] + local_y + 8.0 > 256.0
        ):
            raise RuntimeError(f"{part.label} plus brim does not fit the P2S plate")

    bambu.OBJECTS = [
        (part.label, out_dir / "meshes" / part.filename, part.extruder)
        for part in parts
    ]
    bambu.BUILD_POSITIONS = [plate_position(part.plate) for part in parts]

    # 1-based ModelObject index (not the 3MF object_N id).
    vlh_profiles: dict[int, list[float]] = {}
    for index, part in enumerate(parts, start=1):
        if part.filename != "golf_ball.stl":
            continue
        height = float(part.mesh.bounds[1, 2] - part.mesh.bounds[0, 2])
        vlh_profiles[index] = cfg.ball_vlh_profile(height)

    output_path = out_dir / output_name
    template_path = assets.BLANK_PROJECT
    with (
        zipfile.ZipFile(template_path) as template,
        zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr(
            "[Content_Types].xml",
            content_types_with_txt(template.read("[Content_Types].xml")),
        )
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr(
            "3D/3dmodel.model",
            bambu.top_model().replace(
                b'<metadata name="Title">Cooper Paw-Lattice Bowl</metadata>',
                (
                    '<metadata name="Title">'
                    "Golf Tee LED lamp - P2S production"
                    "</metadata>"
                ).encode(),
            ),
        )
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, part in enumerate(parts, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(part.mesh, index, paint_fuzzy=part.paint_fuzzy),
            )
        output.writestr("Metadata/model_settings.config", model_settings(parts))
        if vlh_profiles:
            output.writestr(
                "Metadata/layer_heights_profile.txt",
                layer_heights_profile_bytes(vlh_profiles),
            )

        settings = json.loads(template.read("Metadata/project_settings.config"))
        configure_filament_slots(settings, filament_slots)
        for key, value in parts[0].profile.items():
            current = settings.get(key)
            settings[key] = [value] * len(current) if isinstance(current, list) else value
        settings["reduce_infill_retraction_mode"] = "Disabled"
        settings["reduce_crossing_wall"] = "1"
        settings["max_travel_detour_distance"] = "0"
        settings["retract_when_changing_layer"] = ["1", "1"]
        settings["retraction_length"] = ["0.8", "0.8"]
        settings["retraction_speed"] = ["30", "30"]
        # Wipe while retracting — long enough to hide dimple-rim nubs in the 1.6 mm wall.
        settings["wipe"] = ["1", "1"]
        settings["wipe_distance"] = ["4", "4"]
        settings["retract_before_wipe"] = ["70%", "70%"]
        # Scarf seams for the dimpled shade (Contour and Hole). Safe on other plates.
        n_fil = len(filament_slots)
        settings["has_scarf_joint_seam"] = "1"
        settings["override_filament_scarf_seam_setting"] = "1"
        settings["seam_slope_type"] = "all"
        settings["apply_scarf_seam_on_circles"] = "1"
        settings["seam_slope_conditional"] = "1"
        settings["seam_slope_inner_walls"] = "1"
        settings["filament_scarf_seam_type"] = ["all"] * n_fil
        settings["wall_sequence"] = "inner wall/outer wall"
        settings["travel_speed"] = "600"
        settings["print_sequence"] = "by layer"
        settings["curr_bed_type"] = "Textured PEI Plate"
        settings["enable_prime_tower"] = "0"
        settings["min_layer_height"] = [f"{cfg.VLH_APEX_LAYER_H:.2f}"]
        settings["max_layer_height"] = ["0.28"]
        settings["filament_colour"] = [c for c, _ in filament_slots]
        settings["filament_settings_id"] = [p for _, p in filament_slots]
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        output.writestr(
            "Metadata/slice_info.config",
            template.read("Metadata/slice_info.config"),
        )
        sequence = {
            f"plate_{part.plate}": {
                "nozzle_sequence": [],
                "optimal_assignment": [],
                "sequence": [],
            }
            for part in parts
        }
        output.writestr(
            "Metadata/filament_sequence.json",
            json.dumps(sequence, separators=(",", ":")).encode(),
        )
        for part in parts:
            preview = plate_preview(part)
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(f"Metadata/{stem}_{part.plate}.png", preview)

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
        settings_root = ET.fromstring(package.read("Metadata/model_settings.config"))
        plates = settings_root.findall("./plate")
        if len(plates) != len(parts):
            raise RuntimeError(f"expected {len(parts)} plates, found {len(plates)}")
        objects = settings_root.findall("./object")
        for node in objects:
            parts_in_object = node.findall("./part")
            if len(parts_in_object) != 1:
                raise RuntimeError("every plate must contain exactly one object")
        project = json.loads(package.read("Metadata/project_settings.config"))
        grid = len(filament_slots)
        matrix = project.get("flush_volumes_matrix", [])
        if len(matrix) != grid * grid:
            raise RuntimeError(
                f"flush_volumes_matrix has {len(matrix)} entries; "
                f"need {grid * grid} for {grid} filaments"
            )
        variants = project.get("filament_extruder_variant", [])
        self_index = project.get("filament_self_index", [])
        if len(variants) != len(self_index):
            raise RuntimeError(
                "filament_extruder_variant and filament_self_index lengths differ: "
                f"{len(variants)} vs {len(self_index)}"
            )
        if len(project.get("filament_settings_id", [])) != grid:
            raise RuntimeError("filament_settings_id does not match slot count")
        if vlh_profiles and "Metadata/layer_heights_profile.txt" not in package.namelist():
            raise RuntimeError("VLH profile was not written into the 3MF")
    return output_path


def generate(out_dir: Path, include_dimples: bool = True) -> list[Path]:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    for stale in mesh_dir.glob("*.stl"):
        stale.unlink()

    parts, report = build_parts(include_dimples=include_dimples)
    for part in parts:
        path = mesh_dir / part.filename
        part.mesh.export(path)
        reloaded = trimesh.load_mesh(path, process=True)
        if (
            not isinstance(reloaded, trimesh.Trimesh)
            or not reloaded.is_watertight
            or not reloaded.is_volume
        ):
            raise RuntimeError(f"serialized production STL is invalid: {path}")

    palette = load_palette()
    caramel = resolve_filament(TEE_FILAMENT, palette)
    grass_fil = resolve_filament(GRASS_FILAMENT, palette)
    ivory = resolve_filament(REFLECTOR_FILAMENT, palette)
    filament_slots = [
        (cfg.BALL_FILAMENT_HEX, cfg.BALL_FILAMENT_PROFILE),
        (caramel.hex, MATTE_PROFILE),
        (grass_fil.hex, MATTE_PROFILE),
        (ivory.hex, MATTE_PROFILE),
    ]

    plate_dir = out_dir / "plates"
    plate_dir.mkdir(parents=True, exist_ok=True)
    for stale in plate_dir.glob("*.3mf"):
        stale.unlink()

    written = []
    combined = write_project(
        parts,
        out_dir,
        "Golf_Tee_Lamp_All_Plates_P2S.3mf",
        filament_slots,
    )
    written.append(combined)

    for part in parts:
        single_slots = [(part.filament_hex or caramel.hex, part.filament_profile)]
        single = Part(
            label=part.label,
            filename=part.filename,
            mesh=part.mesh,
            plate=1,
            extruder=1,
            filament_id=part.filament_id,
            filament_hex=part.filament_hex,
            filament_profile=part.filament_profile,
            filament_label=part.filament_label,
            profile=part.profile,
            preview_colour=part.preview_colour,
            paint_fuzzy=part.paint_fuzzy,
        )
        path = write_project(
            [single],
            out_dir,
            f"plates/{part.plate:02d}_{part.filename.replace('.stl', '')}_P2S.3mf",
            single_slots,
        )
        written.append(path)

    report["outputs"] = [str(path.relative_to(out_dir)) for path in written]
    (out_dir / "production_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("design/golf-tee-lamp/production"),
    )
    parser.add_argument(
        "--no-dimples",
        action="store_true",
        help="Skip dimple displacement for a fast geometry dry-run",
    )
    args = parser.parse_args()
    paths = generate(args.out, include_dimples=not args.no_dimples)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
