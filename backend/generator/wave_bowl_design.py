#!/usr/bin/env python3
"""Three-piece wave bowl stand — Cooper metal bowl size.

Lower + upper halves join on a sine seam with a 0.5 mm/side collar sleeve.
The bowl seat is a separate inverted-printing insert hung from the shell rim.
Letters use recessed glyph pockets and cone-matched backs on the upper front.
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
    WAVE,
    wave_derived,
)


def _largest_body(mesh: trimesh.Trimesh, *, min_volume: float = 500.0) -> trimesh.Trimesh:
    """Drop boolean dust; keep the primary solid shell."""
    parts = mesh.split(only_watertight=False)
    keep = [p for p in parts if abs(float(p.volume)) >= min_volume]
    if not keep:
        raise RuntimeError("Wave boolean produced no usable solid body")
    body = max(keep, key=lambda p: abs(float(p.volume)))
    body = body.copy()
    body.remove_unreferenced_vertices()
    return body


def _ro(y: float, p=WAVE) -> float:
    return p.rb_out + (p.rt_out - p.rb_out) * (y / p.h)


def _ri(y: float, p=WAVE, d=None) -> float:
    """Lower outer-wall inner radius at the locked wall thickness."""
    return _ro(y, p) - p.wall_thick


def _seam_z(theta: float, p=WAVE, d=None) -> float:
    d = d or wave_derived(p)
    return d["seam_y"] - p.amp * math.cos(p.waves * (theta - math.pi / 2.0))


def _wave_letter_center_z(p=WAVE) -> float:
    """Vertical mid-point of the large (low-seam) upper face."""
    d = wave_derived(p)
    face_bottom = d["seam_y"] - p.amp + p.seam_gap
    face_top = d["seat_z"]
    return 0.5 * (face_bottom + face_top)


def _configure_wave_letters() -> None:
    """Point curved-back letters at a large Wave lobe, vertically centred."""
    p = WAVE
    center_z = _wave_letter_center_z(p)
    half_h = 0.5 * design.LETTER_HEIGHT
    design.LETTER_CENTER_Z = center_z
    design.NAME_RAIL_FLAT_Z0 = center_z - half_h - 2.0
    design.NAME_RAIL_FLAT_Z1 = center_z + half_h + 2.0
    wall_r = _ro(center_z)
    design.NAME_RAIL_OUTER_R = wall_r
    design.LETTER_FACE_R = wall_r + design.LETTER_THICKNESS


def _wave_cone_core(radial_offset: float, p=WAVE) -> trimesh.Trimesh:
    """Solid cone following the Wave outer taper with a radial offset."""
    profile = np.array(
        [
            [0.0, 0.0],
            [p.rb_out + radial_offset, 0.0],
            [p.rt_out + radial_offset, p.h],
            [0.0, p.h],
            [0.0, 0.0],
        ],
        dtype=float,
    )
    return trimesh.creation.revolve(profile, sections=256)


def _wave_letter_transform(
    arc_center: float,
    normal_offset: float,
    p=WAVE,
) -> np.ndarray:
    """Map print-space letters to a plane tangent to the Wave cone."""
    # Offset packing so the name sits on a large (low-seam) lobe, not a small one.
    theta = arc_center / design.LETTER_FACE_R + p.letter_azimuth
    tangent = np.array([math.cos(theta), math.sin(theta), 0.0])
    radial = np.array([math.sin(theta), -math.cos(theta), 0.0])
    vertical = np.array([0.0, 0.0, 1.0])
    slope = (p.rt_out - p.rb_out) / p.h
    scale = math.sqrt(1.0 + slope * slope)
    surface_vertical = (vertical + slope * radial) / scale
    outward_normal = (radial - slope * vertical) / scale
    center_z = design.LETTER_CENTER_Z

    transform = np.eye(4)
    transform[:3, :3] = np.column_stack(
        (-tangent, surface_vertical, -outward_normal)
    )
    surface_center = (
        radial * _ro(center_z, p)
        + vertical * center_z
    )
    transform[:3, 3] = surface_center + outward_normal * normal_offset
    return transform


def _wave_letter_mesh(polygon, arc_center: float, p=WAVE) -> trimesh.Trimesh:
    """Flat-printing letter with a back scooped to the Wave cone."""
    extrude_h = (
        design.LETTER_THICKNESS
        + design.LETTER_POCKET_DEPTH
        + 1.2
    )
    body = trimesh.creation.extrude_polygon(
        polygon, height=extrude_h, engine="earcut"
    )
    transform = _wave_letter_transform(
        arc_center,
        design.LETTER_THICKNESS,
        p,
    )
    body.apply_transform(transform)
    body = design.boolean_difference(
        body,
        [
            _wave_cone_core(
                -design.LETTER_POCKET_DEPTH
                * math.sqrt(1.0 + ((p.rt_out - p.rb_out) / p.h) ** 2),
                p,
            )
        ],
    )
    body.apply_transform(np.linalg.inv(transform))
    body.apply_translation([0.0, 0.0, -float(body.bounds[0, 2])])
    body.remove_unreferenced_vertices()
    return body


def _wave_letter_pocket_cutter(polygon, arc_center: float, p=WAVE) -> trimesh.Trimesh:
    """Glyph pocket cutter with a constant-depth conical floor."""
    poly = polygon.buffer(design.LETTER_POCKET_CLEARANCE)
    if poly.is_empty:
        raise ValueError("Wave letter pocket vanished after clearance buffer")
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda geometry: geometry.area)

    outer_offset = 0.55
    floor_normal_offset = (
        -design.LETTER_POCKET_DEPTH
        - design.LETTER_POCKET_FLOOR_GAP
    )
    cone_scale = math.sqrt(
        1.0 + ((p.rt_out - p.rb_out) / p.h) ** 2
    )
    body = trimesh.creation.extrude_polygon(
        poly,
        height=outer_offset - floor_normal_offset + 0.4,
        engine="earcut",
    )
    body.apply_transform(_wave_letter_transform(arc_center, outer_offset, p))
    return design.boolean_difference(
        body,
        [_wave_cone_core(floor_normal_offset * cone_scale, p)],
    )


def _wave_assembly_letter(item, p=WAVE) -> trimesh.Trimesh:
    """Place a print-ready Wave letter back on its tangent cone plane."""
    assembled = item["mesh"].copy()
    assembled.apply_transform(
        _wave_letter_transform(
            item["arc_center"],
            design.LETTER_THICKNESS,
            p,
        )
    )
    return assembled


def _wrapped_profile_mesh(profile_at_theta, *, sections: int = 256) -> trimesh.Trimesh:
    """Wrap one closed radial/Z profile continuously around the stand axis.

    Every angular column has the same profile-point count. Adjacent columns
    share faces directly, avoiding the radial boolean seams produced by the old
    independent-sector construction.
    """
    profiles = [
        profile_at_theta(2.0 * math.pi * section / sections)
        for section in range(sections)
    ]
    point_count = len(profiles[0])
    if point_count < 3 or any(len(profile) != point_count for profile in profiles):
        raise ValueError("Wrapped profiles must have one consistent point count")
    for section, profile in enumerate(profiles):
        cross_section = Polygon(profile)
        if not cross_section.is_valid or cross_section.area <= 0.0:
            theta_deg = 360.0 * section / sections
            raise ValueError(
                f"Wrapped profile self-intersects at {theta_deg:.2f} degrees"
            )

    vertices: list[list[float]] = []
    for section, profile in enumerate(profiles):
        theta = 2.0 * math.pi * section / sections
        for radius, z in profile:
            vertices.append(
                [radius * math.sin(theta), -radius * math.cos(theta), z]
            )

    def idx(section: int, profile_index: int) -> int:
        return (section % sections) * point_count + profile_index

    faces: list[list[int]] = []
    for section in range(sections):
        next_section = (section + 1) % sections
        for profile_index in range(point_count):
            next_profile = (profile_index + 1) % point_count
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

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices),
        faces=np.asarray(faces),
        process=False,
    )
    mesh.fix_normals()
    mesh.remove_unreferenced_vertices()
    if not mesh.is_watertight or not mesh.is_volume:
        raise RuntimeError("Continuous wrapped profile is not a watertight volume")
    return mesh


def build_wave_lower(p=WAVE) -> trimesh.Trimesh:
    """Lower half as one continuous wall/floor/collar wrapped profile."""
    d = wave_derived(p)
    channel_z = 0.5 * (3.0 + d["y2"])

    def profile(theta: float) -> list[list[float]]:
        seam = _seam_z(theta, p, d)
        wall_top = seam - p.seam_gap
        points: list[list[float]] = []
        for row in range(17):
            z = wall_top * row / 16.0
            points.append([_ro(z, p), z])

        # Continuous shadow chamfer up to the true sine seam.
        points.append([_ro(seam, p) - p.shadow_chamfer, seam])
        points.append([_ri(seam, p, d), seam])

        # Inner wall descends to the 3 mm annular floor.
        for row in range(1, 5):
            z = seam + (3.0 - seam) * row / 4.0
            points.append([_ri(z, p, d), z])

        # Floor and hollow collar are part of this same closed profile.
        points.extend(
            [
                [d["rc"], 3.0],
                [d["rc"], channel_z - 1.0],
                [d["rc"] - 0.8, channel_z - 1.0],
                [d["rc"] - 0.8, channel_z + 1.0],
                [d["rc"], channel_z + 1.8],
                [d["rc"], d["y2"] - 1.2],
                [d["rc"] - 1.2, d["y2"]],
                [d["rc"] - 2.4, d["y2"]],
                [d["rc"] - 2.4, 0.0],
            ]
        )
        return points

    body = _wrapped_profile_mesh(profile, sections=max(256, p.sectors * 4))
    body.metadata["name"] = "Wave_Lower"
    return body


def _wave_upper_dimensions(p=WAVE) -> dict[str, float]:
    """Shared shell/seat-insert interface dimensions."""
    d = wave_derived(p)
    seat_z = d["seat_z"]
    seat_r = BOWL_SEAT_D / 2.0
    bore_r = BOWL_OPENING_D / 2.0
    support_z = seat_z - (seat_r - bore_r)
    shell_top_z = seat_z
    shell_top_outer_r = _ro(shell_top_z, p)
    shell_top_inner_r = shell_top_outer_r - p.min_upper_wall
    insert_locator_outer_r = shell_top_inner_r - p.seat_insert_clearance
    insert_flange_outer_r = shell_top_outer_r - p.seat_flange_edge_inset
    sleeve_inner = d["rc"] + p.collar_clearance
    sleeve_top_z = d["y2"] + 1.0
    support_bridge_z = d["y2"] + 6.0
    support_bridge_r = _ro(support_bridge_z, p) - p.min_upper_wall

    if insert_locator_outer_r <= seat_r:
        raise ValueError("Wave seat insert has no outer locating flange")
    if insert_flange_outer_r <= shell_top_inner_r:
        raise ValueError("Wave seat flange does not overlap the shell rim")
    if insert_flange_outer_r >= shell_top_outer_r:
        raise ValueError("Wave seat flange must remain inside the exterior rim")
    if sleeve_inner >= _ro(sleeve_top_z, p) - p.min_upper_wall:
        raise ValueError("Wave receiver wall violates the upper wall envelope")
    if support_bridge_r <= bore_r or support_bridge_r >= _ro(support_bridge_z, p):
        raise ValueError("Wave support bridge violates the upper wall envelope")
    return {
        "seat_z": seat_z,
        "seat_r": seat_r,
        "bore_r": bore_r,
        "support_z": support_z,
        "shell_top_z": shell_top_z,
        "shell_top_outer_r": shell_top_outer_r,
        "shell_top_inner_r": shell_top_inner_r,
        "insert_locator_outer_r": insert_locator_outer_r,
        "insert_flange_outer_r": insert_flange_outer_r,
        "sleeve_inner": sleeve_inner,
        "sleeve_top_z": sleeve_top_z,
        "support_bridge_z": support_bridge_z,
        "support_bridge_r": support_bridge_r,
    }


def build_wave_upper(letter_data, p=WAVE) -> trimesh.Trimesh:
    """Cosmetic upper shell with no internal seat or floating ledge."""
    d = wave_derived(p)
    u = _wave_upper_dimensions(p)

    def profile(theta: float) -> list[list[float]]:
        seam = _seam_z(theta, p, d)
        points: list[list[float]] = [
            [_ro(seam, p) - p.shadow_chamfer, seam],
            [_ro(seam + p.seam_gap, p), seam + p.seam_gap],
        ]
        for row in range(1, 21):
            z = seam + p.seam_gap + (
                u["shell_top_z"] - seam - p.seam_gap
            ) * row / 20.0
            points.append([_ro(z, p), z])

        # Keep the top open and the inverted print continuously supported. The
        # separate seat insert hangs from the finished top rim.
        points.extend(
            [
                [u["shell_top_inner_r"], u["shell_top_z"]],
                [u["support_bridge_r"], u["support_bridge_z"]],
                [u["sleeve_inner"], u["sleeve_top_z"]],
                [u["sleeve_inner"], seam],
            ]
        )
        return points

    body = _wrapped_profile_mesh(profile, sections=max(256, p.sectors * 4))

    # No plaque on Wave: pockets are cut directly into the smooth upper cone.
    pocket_cutters = [
        _wave_letter_pocket_cutter(item["polygon"], item["arc_center"], p)
        for item in letter_data
    ]
    if pocket_cutters:
        body = design.boolean_difference(body, pocket_cutters)

    body = _largest_body(body)
    body.metadata["name"] = "Wave_Upper"
    return body


def build_wave_seat_insert(p=WAVE) -> trimesh.Trimesh:
    """Top-hanging bowl seat that prints inverted on its broad flange."""
    u = _wave_upper_dimensions(p)

    def profile(_theta: float) -> list[list[float]]:
        return [
            [u["insert_locator_outer_r"], u["support_z"]],
            [u["insert_locator_outer_r"], u["seat_z"]],
            [u["insert_flange_outer_r"], u["seat_z"]],
            [u["insert_flange_outer_r"], p.h],
            [u["seat_r"], p.h],
            [u["seat_r"], u["seat_z"]],
            [u["bore_r"], u["support_z"]],
        ]

    insert = _wrapped_profile_mesh(profile, sections=max(256, p.sectors * 4))
    insert.metadata["name"] = "Wave_Bowl_Seat_Insert"
    return insert


def _export_print_ready(mesh: trimesh.Trimesh, path: Path, *, invert_y180: bool = False) -> None:
    out = mesh.copy()
    if invert_y180:
        rot = trimesh.transformations.rotation_matrix(math.pi, [0.0, 1.0, 0.0])
        out.apply_transform(rot)
    out.apply_translation([0.0, 0.0, -float(out.bounds[0, 2])])
    # PLY preserves shared topology for Bambu packaging; STL is also emitted
    # for inspection and interoperability.
    out.export(path.with_suffix(".ply"))
    out.export(path.with_suffix(".stl"))


def generate_wave_meshes(out_dir: Path, name: str, font_style: str = "bold") -> dict:
    """Build wave STLs + dimension report into out_dir."""
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    design.configure_output(out_dir, name=name, font_style=font_style)
    _configure_wave_letters()
    letters = design.build_letters()
    for item in letters:
        item["mesh"] = _wave_letter_mesh(
            item["polygon"],
            item["arc_center"],
        )

    lower = build_wave_lower()
    upper = build_wave_upper(letters)
    seat_insert = build_wave_seat_insert()

    if not lower.is_watertight or not lower.is_volume:
        raise RuntimeError("Wave lower mesh is not a watertight volume")
    if not upper.is_watertight or not upper.is_volume:
        raise RuntimeError("Wave upper mesh is not a watertight volume")
    if not seat_insert.is_watertight or not seat_insert.is_volume:
        raise RuntimeError("Wave bowl-seat insert is not a watertight volume")

    lower.export(mesh_dir / "assembly_wave_lower.stl")
    upper.export(mesh_dir / "assembly_wave_upper.stl")
    seat_insert.export(mesh_dir / "assembly_wave_seat_insert.stl")
    _export_print_ready(lower, mesh_dir / "wave_lower.stl", invert_y180=False)
    _export_print_ready(upper, mesh_dir / "wave_upper.stl", invert_y180=True)
    _export_print_ready(
        seat_insert,
        mesh_dir / "wave_seat_insert.stl",
        invert_y180=True,
    )

    for index, item in enumerate(letters, start=1):
        item["mesh"].export(mesh_dir / f"letter_{index}_{item['character']}.stl")
        assembled = _wave_assembly_letter(item)
        assembled.export(mesh_dir / f"assembly_letter_{index}_{item['character']}.stl")

    d = wave_derived()
    u = _wave_upper_dimensions()
    report = {
        "design": "Ogma Three-Piece Wave Bowl Stand",
        "style": "wave",
        "units": "mm",
        "bowl": {
            "rim_outer_diameter": design.BOWL_RIM_OD,
            "opening": BOWL_OPENING_D,
            "seat_diameter": BOWL_SEAT_D,
            "rim_recess": BOWL_RIM_RECESS,
            "note": "Locked to Cooper metal bowl size",
        },
        "wave": {
            **{k: float(v) for k, v in d.items()},
            "h": WAVE.h,
            "amp": WAVE.amp,
            "waves": WAVE.waves,
            "collar_clearance": WAVE.collar_clearance,
            "collar_outer_radius": d["rc"],
            "sleeve_inner_radius": d["rc"] + WAVE.collar_clearance,
            "receiver_outer_radius_at_transition": _ro(
                u["sleeve_top_z"],
                WAVE,
            ),
            "receiver_wall_at_transition": (
                _ro(u["sleeve_top_z"], WAVE) - u["sleeve_inner"]
            ),
            "receiver_profile": "continuous taper; no horizontal shoulder",
            "minimum_upper_wall": WAVE.min_upper_wall,
            "rb_out": WAVE.rb_out,
            "rt_out": WAVE.rt_out,
            "surface_construction": "continuous_wrapped_profile",
            "surface_sections": max(256, WAVE.sectors * 4),
            "profile_validation": "all radial/Z cross-sections simple and positive-area",
            "seat_insert_clearance": WAVE.seat_insert_clearance,
            "seat_insert_locator_outer_radius": u["insert_locator_outer_r"],
            "seat_insert_flange_outer_radius": u["insert_flange_outer_r"],
            "seat_insert_flange_overlap": (
                u["insert_flange_outer_r"] - u["shell_top_inner_r"]
            ),
            "seat_insert_flange_thickness": BOWL_RIM_RECESS,
        },
        "stand": {
            "lower_watertight": bool(lower.is_watertight),
            "upper_watertight": bool(upper.is_watertight),
            "seat_insert_watertight": bool(seat_insert.is_watertight),
            "lower_volume_mm3": float(lower.volume),
            "upper_volume_mm3": float(upper.volume),
            "seat_insert_volume_mm3": float(seat_insert.volume),
            "lower_triangles": int(len(lower.faces)),
            "upper_triangles": int(len(upper.faces)),
            "seat_insert_triangles": int(len(seat_insert.faces)),
            "collar_wall_thickness": 2.4,
            "assembly": (
                "sine seam collar sleeve 0.5 mm/side + CA glue channel; "
                "separate bowl-seat insert glued over upper-shell top rim"
            ),
        },
        "letters": {
            "text": design.NAME,
            "font_style": design.FONT_STYLE,
            "height": design.LETTER_HEIGHT,
            "proud_thickness": design.LETTER_THICKNESS,
            "pocket_depth": design.LETTER_POCKET_DEPTH,
            "mount": "direct glyph pockets in upper cone; no plaque",
            "back_surface": "concave cone matching Wave wall taper",
            "packing_outer_deg": design.NAME_RAIL_OUTER_DEG,
            # Retained for the shared pipeline's fit-gate report schema.
            "name_rail_outer_deg": design.NAME_RAIL_OUTER_DEG,
            "letter_center_z": design.LETTER_CENTER_Z,
            "letter_azimuth_deg": math.degrees(WAVE.letter_azimuth),
            "letter_face": "large low-seam lobe",
            "face_radius": design.LETTER_FACE_R,
            "arc_centers": [float(item["arc_center"]) for item in letters],
        },
    }
    dims_path = out_dir / "dimensions_and_validation.json"
    dims_path.write_text(json.dumps(report, indent=2) + "\n")
    return report
