#!/usr/bin/env python3
"""Fluted drum bowl stand — Cooper metal bowl size.

Vertical flutes cut into a continuous drum wall. Same envelope, seat and
letter treatment as the honeycomb; only the surface texture differs, which is
the whole point of the style registry.

Flute profile is taken from the archived Named Bowl v4.5 generator:

    offset(theta) = flute_depth * (0.5 + 0.5 * sin(flute_count * theta))

with one deliberate change of sign. v4.5 *added* that offset to the radius,
growing the outside diameter by 2*fa. Here it is subtracted, so flutes are
recessed: the 170 mm envelope holds, the letter pockets still land on a known
radius, and the remaining web is simply wall - flute_depth.

Why no supports are needed: the flutes are purely radial and constant in Z, so
every layer has the identical footprint. There is no overhang anywhere on the
wall, and — unlike the honeycomb — no layer-time variation, which is the main
driver of banding on a cylinder.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import cooper_bowl_design as design  # noqa: E402
from geometry_config import (  # noqa: E402
    BOWL_OPENING_D,
    BOWL_RIM_RECESS,
    BOWL_SEAT_D,
    FLUTED,
)
from hex_bowl_design import (  # noqa: E402
    _pattern_border_offset,
    _smoothstep,
    _wall_radius,
)


def _configure_fluted_letters(p=FLUTED) -> None:
    design.LETTER_CENTER_Z = p.letter_center_z
    design.NAME_RAIL_OUTER_R = _wall_radius(p.letter_center_z, p)
    design.LETTER_FACE_R = design.NAME_RAIL_OUTER_R + design.LETTER_THICKNESS


def flute_offset(
    theta: float,
    z: float,
    *,
    smooth_half_u: float,
    smooth_half_z: float,
    p=FLUTED,
) -> float:
    """Inward radial offset (<= 0) for the flute at this angle.

    Fades to zero across `name_fade` around the name so letter pockets are cut
    into flat wall. The fade is a smoothstep, not a step: a hard edge would read
    as a seam running down both sides of the name.
    """
    if p.flute_count <= 0 or p.flute_depth <= 0.0:
        return 0.0

    depth = p.flute_depth * (0.5 + 0.5 * math.sin(p.flute_count * theta))

    # Distance outside the name keepout box, in mm, in each axis.
    reference_r = _wall_radius(p.letter_center_z, p)
    u = reference_r * theta
    du = abs(u) - smooth_half_u
    dz = abs(z - p.letter_center_z) - smooth_half_z
    if du < 0.0 and dz < 0.0:
        return 0.0
    # Outside in either axis: ramp back up over name_fade.
    fade_u = 1.0 if du >= p.name_fade else _smoothstep(max(du, 0.0) / p.name_fade)
    fade_z = 1.0 if dz >= p.name_fade else _smoothstep(max(dz, 0.0) / p.name_fade)
    fade = max(fade_u, fade_z)
    return -depth * fade


def build_fluted_body(letter_data, p=FLUTED) -> tuple[trimesh.Trimesh, dict]:
    """Build the fluted drum, Cooper seat, and direct glyph pockets."""
    web = (p.rb_out - p.wall_inner_r) - p.flute_depth
    if web < p.min_web:
        raise ValueError(
            f"flute_depth {p.flute_depth} leaves only {web:.2f} mm of web; "
            f"minimum is {p.min_web} mm"
        )

    reference_r = _wall_radius(p.letter_center_z, p)
    letter_face_r = float(design.LETTER_FACE_R)
    angular_edges = [
        edge
        for item in letter_data
        for edge in (
            item["arc_center"] / letter_face_r - item["half_angle"],
            item["arc_center"] / letter_face_r + item["half_angle"],
        )
    ]
    smooth_half_u = (
        reference_r * max(abs(edge) for edge in angular_edges) + p.name_keepout_margin
    )
    glyph_half_z = max(
        max(abs(float(item["polygon"].bounds[1])), abs(float(item["polygon"].bounds[3])))
        for item in letter_data
    )
    smooth_half_z = glyph_half_z + p.name_keepout_margin

    profile_columns: list[list[list[float]]] = []
    for section in range(p.sections):
        theta = -math.pi + 2.0 * math.pi * section / p.sections
        column: list[list[float]] = []
        cross_section: list[tuple[float, float]] = []
        for row in range(p.rows + 1):
            z = p.h * row / p.rows
            texture_offset = min(
                flute_offset(
                    theta,
                    z,
                    smooth_half_u=smooth_half_u,
                    smooth_half_z=smooth_half_z,
                    p=p,
                ),
                _pattern_border_offset(z, p),
            )
            radius = _wall_radius(z, p) + texture_offset
            column.append([radius * math.sin(theta), -radius * math.cos(theta), z])
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
            column.append([radius * math.sin(theta), -radius * math.cos(theta), z])
            cross_section.append((radius, z))

        section_polygon = Polygon(cross_section)
        if not section_polygon.is_valid or section_polygon.area <= 0.0:
            raise ValueError(
                f"Fluted radial profile self-intersects at "
                f"{math.degrees(theta):.2f} degrees"
            )
        profile_columns.append(column)

    points_per_column = len(profile_columns[0])
    vertices = np.asarray(
        [point for column in profile_columns for point in column], dtype=float
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

    body = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
    body.fix_normals()
    if not body.is_watertight or not body.is_volume:
        raise RuntimeError("Fluted drum shell is not a watertight volume")

    pocket_cutters = [
        design.letter_pocket_cutter(item["polygon"], item["arc_center"])
        for item in letter_data
    ]
    body = design.boolean_difference(body, pocket_cutters)
    parts = body.split(only_watertight=False)
    bodies = [
        part for part in parts if part.is_watertight and abs(float(part.volume)) > 1000
    ]
    if not bodies:
        raise RuntimeError("Fluted pocket boolean produced no usable body")
    body = max(bodies, key=lambda part: abs(float(part.volume))).copy()
    body.remove_unreferenced_vertices()
    body.metadata["name"] = "Fluted_Body"

    pitch = 2.0 * math.pi * reference_r / p.flute_count
    return body, {
        "flute_count": p.flute_count,
        "flute_depth": p.flute_depth,
        "flute_pitch": pitch,
        "remaining_web": web,
        "reference_r": reference_r,
        "smooth_name_width": 2.0 * smooth_half_u,
        "smooth_name_height": 2.0 * smooth_half_z,
        "name_fade": p.name_fade,
    }


def generate_fluted_meshes(out_dir: Path, name: str, font_style: str = "bold") -> dict:
    """Build the fluted drum, letters, and validation report."""
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    design.configure_output(out_dir, name=name, font_style=font_style)
    _configure_fluted_letters()
    letters = design.build_letters()
    body, flute = build_fluted_body(letters)
    if not body.is_watertight or not body.is_volume:
        raise RuntimeError("Fluted body mesh is not a watertight volume")

    body.export(mesh_dir / "fluted_body.ply")
    body.export(mesh_dir / "fluted_body.stl")
    body.export(mesh_dir / "assembly_fluted_body.stl")

    for index, item in enumerate(letters, start=1):
        item["mesh"].export(mesh_dir / f"letter_{index}_{item['character']}.stl")
        design.assembly_letter(item).export(
            mesh_dir / f"assembly_letter_{index}_{item['character']}.stl"
        )

    report = {
        "design": "Ogma Fluted Drum Bowl Stand",
        "style": "fluted",
        "units": "mm",
        "bowl": {
            "rim_outer_diameter": design.BOWL_RIM_OD,
            "opening": BOWL_OPENING_D,
            "seat_diameter": BOWL_SEAT_D,
            "rim_recess": BOWL_RIM_RECESS,
            "note": "Locked to Cooper metal bowl size",
        },
        "fluted": {
            **{key: float(value) for key, value in flute.items()},
            "construction": "solid continuous wall with inward-cut vertical flutes",
            "flute_profile": "depth * (0.5 + 0.5 * sin(count * theta)), subtracted",
            "provenance": "profile from the archived Named Bowl v4.5 generator; sign inverted so the OD is unchanged",
            "name_keepout": "smoothstep fade over name_fade mm; no hard edge",
            "supports": "none — flutes are constant in Z, so every layer footprint is identical",
            "profile_validation": "all radial/Z cross-sections simple and positive-area",
        },
        "stand": {
            "body_watertight": bool(body.is_watertight),
            "body_volume_mm3": float(body.volume),
            "body_triangles": int(len(body.faces)),
            "wall_thickness": FLUTED.rb_out - FLUTED.wall_inner_r,
            "minimum_flute_web": flute["remaining_web"],
            "support_start_z": FLUTED.support_start_z,
            "support_overhang_deg": math.degrees(
                math.atan2(
                    FLUTED.wall_inner_r - BOWL_OPENING_D * 0.5,
                    (
                        FLUTED.h
                        - BOWL_RIM_RECESS
                        - (BOWL_SEAT_D - BOWL_OPENING_D) * 0.5
                    )
                    - FLUTED.support_start_z,
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
