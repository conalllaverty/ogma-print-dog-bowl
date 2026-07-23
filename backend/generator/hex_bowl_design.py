#!/usr/bin/env python3
"""Solid honeycomb bowl stand — Cooper metal bowl size.

The wall remains continuous. One-millimetre recessed grooves leave a field of
proud hexagonal tiles, with the pattern faded to a smooth name area. Letters
seat in shallow glyph pockets directly in the curved drum wall.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

import cooper_bowl_design as design
from geometry_config import (
    BOWL_OPENING_D,
    BOWL_RIM_RECESS,
    BOWL_SEAT_D,
    HEX,
)


def _wall_radius(z: float, p=HEX) -> float:
    radius = p.rb_out + (p.rt_out - p.rb_out) * (z / p.h)
    edge_distance = min(z, p.h - z)
    if edge_distance < p.edge_bevel_height:
        radius += p.edge_bevel * (
            1.0 - _smoothstep(edge_distance / p.edge_bevel_height)
        )
    return radius


def _configure_hex_letters() -> None:
    design.LETTER_CENTER_Z = HEX.letter_center_z
    design.NAME_RAIL_OUTER_R = _wall_radius(HEX.letter_center_z)
    design.LETTER_FACE_R = design.NAME_RAIL_OUTER_R + design.LETTER_THICKNESS


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _pattern_border_offset(z: float, p=HEX) -> float:
    """Shallow V-ring that cleanly terminates the top and bottom cell fields."""
    edge_distance = min(z, p.h - z)
    half_width = p.pattern_border_width * 0.5
    distance = abs(edge_distance - p.pattern_edge_band)
    if distance >= half_width:
        return 0.0
    return -p.pattern_border_depth * (
        1.0 - _smoothstep(distance / half_width)
    )


def _honeycomb_params(p=HEX) -> dict[str, float | int]:
    reference_r = 0.5 * (p.rb_out + p.rt_out)
    ncols = 2 * max(
        6,
        round(math.pi * reference_r / (1.5 * p.target_cell_radius)),
    )
    radius = 2.0 * math.pi * reference_r / (1.5 * ncols)
    return {
        "reference_r": reference_r,
        "ncols": ncols,
        "radius": radius,
        "pitch_u": 1.5 * radius,
        "pitch_z": math.sqrt(3.0) * radius,
        "apothem": math.sqrt(3.0) * 0.5 * radius,
    }


def _honeycomb_offset(
    theta: float,
    z: float,
    *,
    smooth_half_u: float,
    smooth_half_z: float,
    params: dict[str, float | int],
    p=HEX,
) -> float:
    """Return radial groove offset: 0 on tiles, negative in chamfered gaps."""
    reference_r = float(params["reference_r"])
    pitch_u = float(params["pitch_u"])
    pitch_z = float(params["pitch_z"])
    apothem = float(params["apothem"])
    u = theta * reference_r

    col = round(u / pitch_u)
    nearby_cells: list[tuple[float, float, float]] = []
    for c in range(col - 1, col + 2):
        center_z0 = pitch_z * 0.5 if c % 2 else 0.0
        row = round((z - center_z0) / pitch_z)
        for r in range(row - 1, row + 2):
            center_u = c * pitch_u
            center_z = center_z0 + r * pitch_z
            du = abs(u - center_u)
            dz = abs(z - center_z)
            distance = max(dz, dz * 0.5 + du * math.sqrt(3.0) * 0.5)
            nearby_cells.append((distance, center_u, center_z))
    nearby_cells.sort(key=lambda cell: cell[0])
    nearest = nearby_cells[0][0]

    edge = (apothem - p.groove_gap * 0.5) - nearest
    groove = 0.0
    if edge < 0.0:
        groove = -p.groove_depth * _smoothstep(
            min(1.0, -edge / p.groove_chamfer)
        )

    # Suppress only edges shared by two name-area cells. This creates a smooth
    # patch bounded by complete honeycomb edges instead of clipped ghost cells.
    def is_name_cell(cell: tuple[float, float, float]) -> bool:
        _distance, center_u, center_z = cell
        return (
            abs(center_u) <= smooth_half_u + float(params["radius"])
            and abs(center_z - p.letter_center_z)
            <= smooth_half_z + float(params["apothem"])
        )

    suppression = 0.0 if all(is_name_cell(cell) for cell in nearby_cells[:2]) else 1.0

    edge_distance = min(z, p.h - z)
    vertical_fade = 1.0 if edge_distance >= p.pattern_edge_band else 0.0
    return groove * suppression * vertical_fade


def build_honeycomb_body(letter_data, p=HEX) -> tuple[trimesh.Trimesh, dict]:
    """Build the solid textured drum, Cooper seat, and direct glyph pockets."""
    params = _honeycomb_params(p)
    smooth_half_u = (
        float(params["reference_r"]) * math.radians(design.NAME_RAIL_OUTER_DEG) + 3.0
    )
    smooth_half_z = design.LETTER_HEIGHT * 0.5 + 3.0

    profile_columns: list[list[list[float]]] = []
    for section in range(p.sections):
        theta = -math.pi + 2.0 * math.pi * section / p.sections
        column: list[list[float]] = []
        cross_section: list[tuple[float, float]] = []
        for row in range(p.rows + 1):
            z = p.h * row / p.rows
            honeycomb_offset = _honeycomb_offset(
                theta,
                z,
                smooth_half_u=smooth_half_u,
                smooth_half_z=smooth_half_z,
                params=params,
                p=p,
            )
            texture_offset = min(
                honeycomb_offset,
                _pattern_border_offset(z, p),
            )
            radius = _wall_radius(z, p) + texture_offset
            column.append(
                [radius * math.sin(theta), -radius * math.cos(theta), z]
            )
            cross_section.append((radius, z))

        seat_r = BOWL_SEAT_D * 0.5
        bore_r = BOWL_OPENING_D * 0.5
        seat_z = p.h - BOWL_RIM_RECESS
        inner_profile = (
            (seat_r, p.h),
            (seat_r, seat_z),
            (bore_r, seat_z - (seat_r - bore_r)),
            (p.wall_inner_r, p.support_start_z),
            (p.wall_inner_r, 0.0),
        )
        for radius, z in inner_profile:
            column.append(
                [radius * math.sin(theta), -radius * math.cos(theta), z]
            )
            cross_section.append((radius, z))
        section_polygon = Polygon(cross_section)
        if not section_polygon.is_valid or section_polygon.area <= 0.0:
            raise ValueError(
                f"Honeycomb radial profile self-intersects at {math.degrees(theta):.2f} degrees"
            )
        profile_columns.append(column)

    points_per_column = len(profile_columns[0])
    vertices = np.asarray(
        [point for column in profile_columns for point in column],
        dtype=float,
    )

    def idx(section: int, profile_index: int) -> int:
        return (section % p.sections) * points_per_column + profile_index

    faces: list[list[int]] = []
    for section in range(p.sections):
        next_section = (section + 1) % p.sections
        for profile_index in range(points_per_column):
            next_profile = (profile_index + 1) % points_per_column
            faces.extend(
                [
                    [
                        idx(section, profile_index),
                        idx(next_section, next_profile),
                        idx(next_section, profile_index),
                    ],
                    [
                        idx(section, profile_index),
                        idx(section, next_profile),
                        idx(next_section, next_profile),
                    ],
                ]
            )

    body = trimesh.Trimesh(
        vertices=vertices,
        faces=np.asarray(faces),
        process=False,
    )
    body.fix_normals()
    if not body.is_watertight or not body.is_volume:
        raise RuntimeError("Honeycomb drum shell is not a watertight volume")

    pocket_cutters = [
        design.letter_pocket_cutter(item["polygon"], item["arc_center"])
        for item in letter_data
    ]
    body = design.boolean_difference(body, pocket_cutters)
    parts = body.split(only_watertight=False)
    bodies = [part for part in parts if part.is_watertight and abs(float(part.volume)) > 1000]
    if not bodies:
        raise RuntimeError("Honeycomb pocket boolean produced no usable body")
    body = max(bodies, key=lambda part: abs(float(part.volume))).copy()
    body.remove_unreferenced_vertices()
    body.metadata["name"] = "Honeycomb_Body"

    return body, {
        **params,
        "smooth_name_width": 2.0 * (
            smooth_half_u + float(params["radius"])
        ),
        "smooth_name_height": 2.0 * (
            smooth_half_z + float(params["apothem"])
        ),
    }


def generate_hex_meshes(out_dir: Path, name: str, font_style: str = "bold") -> dict:
    """Build the solid honeycomb body, letters, and validation report."""
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    design.configure_output(out_dir, name=name, font_style=font_style)
    _configure_hex_letters()
    letters = design.build_letters()
    body, honeycomb = build_honeycomb_body(letters)
    if not body.is_watertight or not body.is_volume:
        raise RuntimeError("Honeycomb body mesh is not a watertight volume")

    body.export(mesh_dir / "honeycomb_body.ply")
    body.export(mesh_dir / "honeycomb_body.stl")
    body.export(mesh_dir / "assembly_honeycomb_body.stl")

    for index, item in enumerate(letters, start=1):
        item["mesh"].export(mesh_dir / f"letter_{index}_{item['character']}.stl")
        design.assembly_letter(item).export(
            mesh_dir / f"assembly_letter_{index}_{item['character']}.stl"
        )

    report = {
        "design": "Ogma Solid Honeycomb Bowl Stand",
        "style": "hex",
        "units": "mm",
        "bowl": {
            "rim_outer_diameter": design.BOWL_RIM_OD,
            "opening": BOWL_OPENING_D,
            "seat_diameter": BOWL_SEAT_D,
            "rim_recess": BOWL_RIM_RECESS,
            "note": "Locked to Cooper metal bowl size",
        },
        "honeycomb": {
            **{key: float(value) for key, value in honeycomb.items()},
            "groove_depth": HEX.groove_depth,
            "groove_gap": HEX.groove_gap,
            "groove_chamfer": HEX.groove_chamfer,
            "pattern_edge_band": HEX.pattern_edge_band,
            "pattern_border_width": HEX.pattern_border_width,
            "pattern_border_depth": HEX.pattern_border_depth,
            "edge_bevel": HEX.edge_bevel,
            "construction": "solid continuous wall with recessed grooves",
            "name_keepout": "whole honeycomb cells; complete boundary edges",
            "profile_validation": "all radial/Z cross-sections simple and positive-area",
        },
        "stand": {
            "body_watertight": bool(body.is_watertight),
            "body_volume_mm3": float(body.volume),
            "body_triangles": int(len(body.faces)),
            "wall_thickness": HEX.rb_out - HEX.wall_inner_r,
            "minimum_groove_web": (
                HEX.rb_out - HEX.wall_inner_r - HEX.groove_depth
            ),
            "support_start_z": HEX.support_start_z,
            "support_overhang_deg": math.degrees(
                math.atan2(
                    HEX.wall_inner_r - BOWL_OPENING_D * 0.5,
                    (
                        HEX.h
                        - BOWL_RIM_RECESS
                        - (BOWL_SEAT_D - BOWL_OPENING_D) * 0.5
                    )
                    - HEX.support_start_z,
                )
            ),
            "parts": "single-piece drum plus separate glue-in letters",
        },
        "letters": {
            "text": design.NAME,
            "font_style": design.FONT_STYLE,
            "height": design.LETTER_HEIGHT,
            "proud_thickness": design.LETTER_THICKNESS,
            "pocket_depth": design.LETTER_POCKET_DEPTH,
            "name_rail_outer_deg": design.NAME_RAIL_OUTER_DEG,
            "name_rail_flat_deg": design.NAME_RAIL_FLAT_DEG,
            "letter_center_z": design.LETTER_CENTER_Z,
            "face_radius": design.LETTER_FACE_R,
            "arc_centers": [float(item["arc_center"]) for item in letters],
        },
    }
    (out_dir / "dimensions_and_validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return report
