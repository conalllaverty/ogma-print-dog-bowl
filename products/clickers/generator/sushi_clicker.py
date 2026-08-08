#!/usr/bin/env python3
"""Generate the Happy Salmon Nigiri fidget clicker.

The output is a three-plate Bambu Studio project:
1. Ivory rice body with Charcoal face and Sakura Pink cheeks.
2. Mandarin Orange salmon button with Sakura Pink stripes.
3. Switch opening and MX-stem tolerance coupons.

All dimensions are millimetres.  The switch mount follows the supplied
Outemu/Gaote drawing and intentionally leaves the two electrical pins and
central locating pin unobstructed.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from shapely import union_all
from shapely.geometry import LineString, Point, box

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ogma import assets  # noqa: E402

from ogma import bambu_project as bambu  # noqa: E402


# Finished envelope and printer-facing tolerances.
BODY_LENGTH = 54.0
BODY_WIDTH = 30.0
BODY_HEIGHT = 19.5
CAP_LENGTH = 58.0
CAP_WIDTH = 34.0
CAP_HEIGHT = 10.3
CAP_LOWER_WALL = 1.3
CAP_OUTER_EXPONENT = 4.2
CAP_CAVITY_EXPONENT = 4.2
CAP_VERTICAL_CLEARANCE_HEIGHT = 7.2
CAP_STRIPE_DEPTH = 0.60
CAP_STRIPE_MIN_Z = 8.00
MIN_RESIDUAL_WALL = 0.60

SWITCH_UPPER = 15.60
SWITCH_LOWER = 13.95
SWITCH_OPENING = 14.10
SWITCH_HOUSING_HEIGHT = 11.60
SWITCH_LOWER_BODY_HEIGHT = 5.00
SWITCH_CENTRE_PIN_D = 3.85
SWITCH_CONTACT_SPACING = 5.08
SWITCH_PIN_CLEARANCE_FLOOR = 1.8
SWITCH_SHOULDER_DROP = 1.0
SWITCH_MOUNT_WIDE = 16.40
SWITCH_MOUNT_NARROW_Z = 10.8 - SWITCH_SHOULDER_DROP
SWITCH_MOUNT_WIDE_Z = 12.2 - SWITCH_SHOULDER_DROP

MX_CROSS_MAJOR = 4.20
MX_CROSS_MINOR = 1.55
MX_SOCKET_DEPTH = 5.00
MX_SOCKET_BOSS_D = 5.86
MX_STEM_HEIGHT = 3.60
MX_SOCKET_OPENING_Z = 0.65

SWITCH_SEAT_Z = SWITCH_MOUNT_NARROW_Z + (
    (SWITCH_UPPER - SWITCH_OPENING)
    / (SWITCH_MOUNT_WIDE - SWITCH_OPENING)
    * (SWITCH_MOUNT_WIDE_Z - SWITCH_MOUNT_NARROW_Z)
)
CAP_REST_RIM_Z = (
    SWITCH_SEAT_Z
    + SWITCH_HOUSING_HEIGHT
    - SWITCH_LOWER_BODY_HEIGHT
    - MX_SOCKET_OPENING_Z
)
MIN_SWITCH_SIDE_HIDE = 2.0
EYE_TOP_Z = 11.30
TARGET_OVERALL_HEIGHT = CAP_REST_RIM_Z + CAP_HEIGHT + 0.60

FILAMENTS = [
    ("Ivory White", "#FFFFFF"),
    ("Mandarin Orange", "#F99963"),
    ("Sakura Pink", "#E8AFCF"),
    ("Charcoal", "#000000"),
]
PLATE_GROUPS = [
    ("Rice body - AMS face", [1, 2, 3], (128.0, 128.0, 0.0)),
    ("Salmon button - AMS stripes", [4, 5], (440.0, 128.0, 0.0)),
    ("Switch fit coupon - print first", [6], (128.0, -184.0, 0.0)),
]


def _boolean_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    result = trimesh.boolean.union(meshes, engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    return result


def _boolean_difference(
    mesh: trimesh.Trimesh,
    cutters: list[trimesh.Trimesh],
) -> trimesh.Trimesh:
    result = trimesh.boolean.difference([mesh, *cutters], engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    return result


def _boolean_intersection(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    result = trimesh.boolean.intersection(meshes, engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    return result


def _rounded_rectangle(width: float, depth: float, radius: float):
    if radius <= 0:
        return box(-width / 2, -depth / 2, width / 2, depth / 2)
    core = box(
        -width / 2 + radius,
        -depth / 2 + radius,
        width / 2 - radius,
        depth / 2 - radius,
    )
    return core.buffer(radius, resolution=12)


def _rounded_prism(
    width: float,
    depth: float,
    height: float,
    radius: float,
    *,
    z0: float = 0.0,
) -> trimesh.Trimesh:
    mesh = trimesh.creation.extrude_polygon(
        _rounded_rectangle(width, depth, radius),
        height=height,
        engine="earcut",
    )
    mesh.apply_translation([0, 0, z0])
    return mesh


def _box(
    size: tuple[float, float, float],
    centre: tuple[float, float, float],
) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation(centre)
    return mesh


def _cylinder(
    radius: float,
    height: float,
    centre: tuple[float, float, float],
    *,
    sections: int = 48,
    axis: str = "z",
) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    if axis == "y":
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
        )
    mesh.apply_translation(centre)
    return mesh


def _superellipse_ring(
    width: float,
    depth: float,
    exponent: float,
    count: int,
) -> np.ndarray:
    theta = np.linspace(0, 2 * math.pi, count, endpoint=False)
    c = np.cos(theta)
    s = np.sin(theta)
    x = (width / 2) * np.sign(c) * np.abs(c) ** (2.0 / exponent)
    y = (depth / 2) * np.sign(s) * np.abs(s) ** (2.0 / exponent)
    return np.column_stack([x, y])


def _lofted_solid(
    levels: list[tuple[float, float, float]],
    *,
    exponent: float = 4.0,
    sections: int = 128,
) -> trimesh.Trimesh:
    """Create a capped solid from (z, width, depth) superellipse levels."""
    vertices: list[list[float]] = []
    for z, width, depth in levels:
        ring = _superellipse_ring(width, depth, exponent, sections)
        vertices.extend([[x, y, z] for x, y in ring])
    faces: list[list[int]] = []
    for level in range(len(levels) - 1):
        a0 = level * sections
        b0 = (level + 1) * sections
        for i in range(sections):
            j = (i + 1) % sections
            faces.extend([[a0 + i, a0 + j, b0 + j], [a0 + i, b0 + j, b0 + i]])
    bottom_i = len(vertices)
    vertices.append([0, 0, levels[0][0]])
    top_i = len(vertices)
    vertices.append([0, 0, levels[-1][0]])
    top_start = (len(levels) - 1) * sections
    for i in range(sections):
        j = (i + 1) % sections
        faces.append([bottom_i, j, i])
        faces.append([top_i, top_start + i, top_start + j])
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    return mesh


def _salmon_outer_levels(*, top_offset: float = 0.0) -> list[tuple[float, float, float]]:
    """Nigiri dome with a broad, support-free top-down printing surface."""
    return [
        (0.0, CAP_LENGTH, CAP_WIDTH),
        (1.2, CAP_LENGTH, CAP_WIDTH),
        (CAP_VERTICAL_CLEARANCE_HEIGHT, 56.8, 32.8),
        (8.8, 54.0, 30.0),
        (CAP_HEIGHT - top_offset, 51.0, 27.0),
    ]


def _salmon_cavity_levels(*, grow: float = 0.0) -> list[tuple[float, float, float]]:
    """Inner void of the cap; `grow` dilates it to reserve a wall allowance."""
    cavity_length = CAP_LENGTH - 2.0 * CAP_LOWER_WALL
    cavity_width = CAP_WIDTH - 2.0 * CAP_LOWER_WALL
    levels = [
        (-1.0, cavity_length, cavity_width),
        (1.2, cavity_length, cavity_width),
        (CAP_VERTICAL_CLEARANCE_HEIGHT, 54.6, 30.6),
        (8.7, 46.0, 24.5),
    ]
    if grow == 0.0:
        return levels
    return [
        (z + grow if z > 0.0 else z - grow, length + 2.0 * grow, width + 2.0 * grow)
        for z, length, width in levels
    ]


def _salmon_shell(*, top_offset: float = 0.0) -> trimesh.Trimesh:
    """Hollow cap with a squarer cavity clear through the full switch stroke."""
    outer = _lofted_solid(
        _salmon_outer_levels(top_offset=top_offset),
        exponent=CAP_OUTER_EXPONENT,
    )

    cavity = _lofted_solid(_salmon_cavity_levels(), exponent=CAP_CAVITY_EXPONENT)
    return _boolean_difference(outer, [cavity])


def _mx_cross_cutter(
    major: float,
    minor: float,
    depth: float,
    *,
    z0: float,
) -> trimesh.Trimesh:
    vertical = _box((minor, major, depth), (0, 0, z0 + depth / 2))
    horizontal = _box((major, minor, depth), (0, 0, z0 + depth / 2))
    return _boolean_union([vertical, horizontal])


def _front_feature(polygon, depth: float = 0.75) -> trimesh.Trimesh:
    """Extrude an X/Z face polygon along negative Y."""
    polygons = list(polygon.geoms) if hasattr(polygon, "geoms") else [polygon]
    meshes = []
    for component in polygons:
        mesh = trimesh.creation.extrude_polygon(
            component,
            height=depth,
            engine="earcut",
        )
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
        )
        # Embed most of each colour volume while leaving only a subtle raised
        # face, closer to the clean CritterCRAFT Dumpling treatment.
        mesh.apply_translation([0, -14.25, 0])
        meshes.append(mesh)
    return trimesh.util.concatenate(meshes)


def _capsule_2d(
    centre_x: float,
    centre_z: float,
    width: float,
    height: float,
):
    radius = width / 2
    if height <= width:
        return Point(centre_x, centre_z).buffer(width / 2, resolution=12)
    return box(
        centre_x - radius,
        centre_z - height / 2 + radius,
        centre_x + radius,
        centre_z + height / 2 - radius,
    ).buffer(radius, resolution=12)


def _face_meshes() -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    eyes = []
    for centre_x in (-4.3, 4.3):
        # A rounded rectangle leaves a short flat base instead of beginning at
        # a single point, preventing the tiny overextruded droplet seen under
        # the first prototype's circular eyes.
        eye_width = 2.50
        eye_height = 2.80
        eye_radius = 0.55
        eye = box(
            centre_x - eye_width / 2 + eye_radius,
            9.9 - eye_height / 2 + eye_radius,
            centre_x + eye_width / 2 - eye_radius,
            9.9 + eye_height / 2 - eye_radius,
        ).buffer(eye_radius, resolution=20)
        highlight = Point(centre_x - 0.38, 10.38).buffer(0.28, resolution=16)
        eyes.append(eye.difference(highlight))
    mouth_points = []
    for x in np.linspace(-1.45, 1.45, 19):
        # Smile corners are high and centre is low.
        z = 7.05 + 0.13 * x * x
        mouth_points.append((float(x), float(z)))
    mouth = LineString(mouth_points).buffer(
        0.28,
        cap_style="round",
        join_style="round",
        resolution=12,
    )
    black = _front_feature(union_all([*eyes, mouth]))
    cheeks = _front_feature(
        union_all(
            [
                Point(-8.4, 7.55).buffer(0.55, resolution=20),
                Point(8.4, 7.55).buffer(0.55, resolution=20),
            ]
        )
    )
    return black, cheeks


def build_rice_body() -> tuple[trimesh.Trimesh, trimesh.Trimesh, trimesh.Trimesh]:
    outer = _lofted_solid(
        [
            (0.0, BODY_LENGTH, BODY_WIDTH),
            (1.2, BODY_LENGTH, BODY_WIDTH),
            (4.0, BODY_LENGTH, BODY_WIDTH),
            (12.8, 53.7, 29.7),
            (16.0, 51.5, 28.3),
            (BODY_HEIGHT, 48.0, 26.0),
        ],
        exponent=4.2,
    )

    # The pocket widens at a support-safe slope instead of creating a horizontal
    # internal ledge. The switch is glued against this transition.
    switch_cavity = _lofted_solid(
        [
            (SWITCH_PIN_CLEARANCE_FLOOR, SWITCH_OPENING, SWITCH_OPENING),
            (SWITCH_MOUNT_NARROW_Z, SWITCH_OPENING, SWITCH_OPENING),
            (SWITCH_MOUNT_WIDE_Z, SWITCH_MOUNT_WIDE, SWITCH_MOUNT_WIDE),
            (BODY_HEIGHT + 2.0, SWITCH_MOUNT_WIDE, SWITCH_MOUNT_WIDE),
        ],
        exponent=30.0,
    )
    shell = _boolean_difference(
        outer,
        [switch_cavity],
    )
    body = shell

    black, cheeks = _face_meshes()
    # Keep one-layer-deep overlap between the parent body and AMS face parts.
    # Bambu resolves grouped multipart overlap by part/extruder and therefore
    # recognises the colour regions as supported instead of floating islands.
    # Clipping to the body keeps the flat-extruded features flush with the
    # curved front instead of leaving slivers hanging off the surface.
    black = _boolean_intersection([black, body])
    cheeks = _boolean_intersection([cheeks, body])
    body.metadata["name"] = "Ivory rice body"
    black.metadata["name"] = "Charcoal smile and eyes"
    cheeks.metadata["name"] = "Sakura Pink cheeks"
    return body, black, cheeks


def build_salmon_button() -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    outer = _salmon_shell()

    # Projecting keycap-style boss into the hollow cavity, open toward the bed
    # so it can press onto the MX stem. Dimensions match the proven coupon.
    boss_bottom = MX_SOCKET_OPENING_Z + 0.05
    boss_top = CAP_HEIGHT - 0.40
    boss = _cylinder(
        MX_SOCKET_BOSS_D / 2,
        boss_top - boss_bottom,
        (0, 0, (boss_top + boss_bottom) / 2),
        sections=96,
    )
    button = _boolean_union([outer, boss])
    socket = _mx_cross_cutter(
        MX_CROSS_MAJOR,
        MX_CROSS_MINOR,
        MX_SOCKET_DEPTH,
        z0=boss_bottom - 0.05,
    )
    button = _boolean_difference(button, [socket])

    # Colour stripes must be an inlay carved out of the finished cap. Deriving
    # them from an enlarged shell left ribs standing proud of the real surface,
    # which printed as floating walls with open gaps beside them.
    eroded = _lofted_solid(
        [
            (z - CAP_STRIPE_DEPTH, length - 2.0 * CAP_STRIPE_DEPTH, width - 2.0 * CAP_STRIPE_DEPTH)
            for z, length, width in _salmon_outer_levels()
        ],
        exponent=CAP_OUTER_EXPONENT,
    )
    stripe_skin = _boolean_difference(button, [eroded])

    stripe_slabs = []
    for x, width in ((-20.0, 2.2), (-10.0, 2.4), (0.0, 2.5), (10.0, 2.4), (20.0, 2.2)):
        stripe = _box((width, 40.0, 20.0), (x, 0, CAP_HEIGHT * 0.55))
        stripe.apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(-18.0), [0, 0, 1])
        )
        stripe_slabs.append(stripe)
    stripe_region = _boolean_intersection(
        [
            _boolean_union(stripe_slabs),
            _box((CAP_LENGTH + 4.0, CAP_WIDTH + 4.0, 20.0), (0, 0, CAP_STRIPE_MIN_Z + 10.0)),
        ]
    )
    # Reserve a solid orange wall behind the inlay. Without this the stripe
    # breaks through into the cavity on the sloped shoulder, where an offset
    # measured along Z and XY exceeds the true surface-normal distance.
    cavity_guard = _lofted_solid(
        _salmon_cavity_levels(grow=MIN_RESIDUAL_WALL),
        exponent=CAP_CAVITY_EXPONENT,
    )
    stripes = _boolean_difference(
        _boolean_intersection([stripe_skin, stripe_region]),
        [cavity_guard],
    )

    button.metadata["name"] = "Mandarin Orange salmon button"
    stripes.metadata["name"] = "Sakura Pink salmon stripes"
    return button, stripes


def build_switch_coupon() -> trimesh.Trimesh:
    """Plate-opening gauge plus a reference-matched MX socket gauge."""
    plate = _rounded_prism(70.0, 28.0, 2.4, 4.0, z0=0.0)
    hole_sizes = (13.95, 14.10, 14.25)
    holes = []
    for x, size in zip((-24.0, -7.0, 10.0), hole_sizes):
        holes.append(_box((size, size, 4.0), (x, 0, 1.2)))
    plate = _boolean_difference(plate, holes)

    # Tactile identifiers next to the openings: one, two, and three dots.
    dots = []
    for index, x in enumerate((-24.0, -7.0, 10.0), start=1):
        for dot_i in range(index):
            dots.append(
                _cylinder(
                    0.65,
                    0.45,
                    (x + (dot_i - (index - 1) / 2) * 2.0, -11.0, 2.625),
                    sections=24,
                )
            )
    plate = _boolean_union([plate, *dots])

    # Reproduce the projecting round boss measured from the user's known-working
    # CritterCRAFT Dumpling STL.
    x = 43.0
    handle = _rounded_prism(9.0, 9.0, 2.0, 1.3, z0=0.0)
    boss = _cylinder(MX_SOCKET_BOSS_D / 2, 5.55, (0, 0, 4.725), sections=96)
    socket = _boolean_union([handle, boss])
    socket.apply_translation([x, 0, 0])
    cutter = _mx_cross_cutter(
        MX_CROSS_MAJOR,
        MX_CROSS_MINOR,
        MX_SOCKET_DEPTH + 0.20,
        z0=2.40,
    )
    cutter.apply_translation([x, 0, 0])
    reference_socket = _boolean_difference(socket, [cutter])

    coupon = trimesh.util.concatenate([plate, reference_socket])
    coupon.metadata["name"] = "Outemu switch and MX socket fit coupon"
    return coupon


def _stl_safe_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Discard zero-volume boolean sheets exposed by STL float quantisation."""
    encoded = mesh.export(file_type="stl")
    reloaded = trimesh.load_mesh(io.BytesIO(encoded), file_type="stl", process=True)
    solids = [
        component
        for component in reloaded.split(only_watertight=False)
        if component.is_volume and abs(component.volume) > 1e-5
    ]
    if not solids:
        raise ValueError("STL round-trip removed every positive-volume component")
    cleaned = solids[0] if len(solids) == 1 else trimesh.util.concatenate(solids)
    cleaned.metadata.update(mesh.metadata)
    return cleaned


def _validate_mesh(name: str, mesh: trimesh.Trimesh) -> dict:
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight:
        raise ValueError(f"{name} is not watertight")
    if not mesh.is_volume:
        raise ValueError(f"{name} is not a positive volume")
    bounds = mesh.bounds
    return {
        "name": name,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "volume_mm3": round(float(mesh.volume), 3),
        "bounds_mm": {
            "min": [round(float(value), 3) for value in bounds[0]],
            "max": [round(float(value), 3) for value in bounds[1]],
            "size": [round(float(value), 3) for value in bounds[1] - bounds[0]],
        },
    }


def _flip_cap_for_print(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Place the salmon cap top-down with its cavity open upward."""
    flipped = mesh.copy()
    flipped.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0])
    )
    flipped.apply_translation((0.0, 0.0, -float(flipped.bounds[0][2])))
    return flipped


def _validate_inlay_containment(
    name: str,
    inlay: trimesh.Trimesh,
    parent: trimesh.Trimesh,
) -> dict:
    """AMS colour parts must sit wholly inside their host solid.

    Any volume outside the host prints as an unsupported floating wall with an
    open gap beside it, which is what produced the holes in the striped cap.
    """
    stray = trimesh.boolean.difference([inlay, parent], engine="manifold")
    stray_volume = 0.0 if stray is None else abs(float(stray.volume))
    if stray_volume > 1e-3:
        raise ValueError(
            f"{name} has {stray_volume:.3f} mm3 outside its host solid"
        )
    return {
        "name": name,
        "volume_mm3": round(float(inlay.volume), 3),
        "volume_outside_host_mm3": round(stray_volume, 6),
    }


def _validate_assembly_envelope(
    body: trimesh.Trimesh,
    button: trimesh.Trimesh,
) -> dict:
    """Reject cap geometry that exposes the switch or clashes through travel."""
    switch_side_hide = BODY_HEIGHT - CAP_REST_RIM_Z
    eye_clearance_rest = CAP_REST_RIM_Z - EYE_TOP_Z
    eye_clearance_pressed = CAP_REST_RIM_Z - 4.0 - EYE_TOP_Z
    if switch_side_hide < MIN_SWITCH_SIDE_HIDE:
        raise ValueError(
            f"Switch side hide {switch_side_hide:.3f} mm is below "
            f"{MIN_SWITCH_SIDE_HIDE:.3f} mm"
        )
    if eye_clearance_rest < 2.0:
        raise ValueError(
            f"Resting cap-to-eye clearance {eye_clearance_rest:.3f} mm is too small"
        )

    max_collision = 0.0
    worst_case: tuple[float, float, float] | None = None
    for offset_x in (-0.5, 0.0, 0.5):
        for offset_y in (-0.5, 0.0, 0.5):
            for travel in (4.0, 4.3):
                positioned = button.copy()
                positioned.apply_translation(
                    [offset_x, offset_y, CAP_REST_RIM_Z - travel]
                )
                overlap = trimesh.boolean.intersection(
                    [body, positioned],
                    engine="manifold",
                )
                collision = 0.0 if overlap is None else abs(float(overlap.volume))
                if collision > max_collision:
                    max_collision = collision
                    worst_case = (offset_x, offset_y, travel)
    if max_collision > 1e-4:
        raise ValueError(
            f"Cap/body collision {max_collision:.6f} mm3 at {worst_case}"
        )

    return {
        "switch_seat_z": round(SWITCH_SEAT_Z, 3),
        "cap_rest_rim_z": round(CAP_REST_RIM_Z, 3),
        "switch_side_hide": round(switch_side_hide, 3),
        "minimum_switch_side_hide": MIN_SWITCH_SIDE_HIDE,
        "eye_top_z": EYE_TOP_Z,
        "eye_clearance_rest": round(eye_clearance_rest, 3),
        "eye_clearance_pressed": round(eye_clearance_pressed, 3),
        "validated_travel": 4.3,
        "validated_xy_offset": 0.5,
        "maximum_collision_mm3": round(max_collision, 6),
    }


def _model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    overrides = {
        "layer_height": "0.16",
        "wall_loops": "4",
        "wall_sequence": "inner wall/outer wall",
        "sparse_infill_density": "15%",
        "sparse_infill_pattern": "gyroid",
        "outer_wall_speed": "60",
        "inner_wall_speed": "120",
        "small_perimeter_speed": "50%",
        "top_shell_layers": "5",
        "bottom_shell_layers": "5",
        "bottom_surface_pattern": "monotonic",
        "top_surface_pattern": "monotonicline",
        "seam_position": "back",
        "fuzzy_skin": "none",
    }
    for group_index, (group_name, object_indices, _) in enumerate(
        PLATE_GROUPS,
        start=1,
    ):
        top_id = 99 + group_index
        primary_extruder = objects[object_indices[0] - 1][2]
        face_count = sum(len(meshes[index - 1].faces) for index in object_indices)
        group_overrides = dict(overrides)
        if group_index == 2:
            group_overrides.update(
                {
                    "enable_support": "0",
                    "brim_type": "no_brim",
                    "brim_width": "0",
                    "outer_wall_speed": "40",
                }
            )
        lines.extend(
            [
                f'  <object id="{top_id}">',
                f'    <metadata key="name" value="{escape(group_name)}"/>',
                f'    <metadata key="extruder" value="{primary_extruder}"/>',
                *[
                    f'    <metadata key="{key}" value="{value}"/>'
                    for key, value in group_overrides.items()
                ],
                f'    <metadata face_count="{face_count}"/>',
            ]
        )
        for object_index in object_indices:
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

    for number, (title, _, _) in enumerate(PLATE_GROUPS, start=1):
        top_id = 99 + number
        lines.extend(
            [
                "  <plate>",
                f'    <metadata key="plater_id" value="{number}"/>',
                f'    <metadata key="plater_name" value="{escape(title)}"/>',
                '    <metadata key="locked" value="false"/>',
                '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
                f'    <metadata key="thumbnail_file" value="Metadata/plate_{number}.png"/>',
                f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{number}.png"/>',
                f'    <metadata key="top_file" value="Metadata/top_{number}.png"/>',
                f'    <metadata key="pick_file" value="Metadata/pick_{number}.png"/>',
                "    <model_instance>",
                f'      <metadata key="object_id" value="{top_id}"/>',
                '      <metadata key="instance_id" value="0"/>',
                f'      <metadata key="identify_id" value="{299 + number}"/>',
                "    </model_instance>",
                "  </plate>",
            ]
        )

    lines.append("  <assemble>")
    for group_index in range(1, len(PLATE_GROUPS) + 1):
        lines.append(
            f'    <assemble_item object_id="{99 + group_index}" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def _top_model() -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{bambu.CORE}" '
        f'xmlns:BambuStudio="{bambu.BAMBU}" xmlns:p="{bambu.PROD}" requiredextensions="p">',
        ' <metadata name="Application">BambuStudio-02.07.01.62</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        ' <metadata name="Title">Happy Salmon Nigiri Clicker</metadata>',
        " <resources>",
    ]
    for group_index, (_, object_indices, _) in enumerate(PLATE_GROUPS, start=1):
        top_id = 99 + group_index
        lines.extend(
            [
                f'  <object id="{top_id}" p:UUID="{bambu.object_uuid(top_id, 0xABCDEF123456)}" type="model">',
                "   <components>",
            ]
        )
        for object_index in object_indices:
            lines.append(
                f'    <component p:path="/3D/Objects/object_{object_index}.model" '
                f'objectid="{object_index}" '
                f'p:UUID="{bambu.object_uuid(0x1000 + object_index, 0xABCDEF123456)}" '
                'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
            )
        lines.extend(["   </components>", "  </object>"])
    lines.extend(
        [
            " </resources>",
            f' <build p:UUID="{bambu.object_uuid(9999, 0xABCDEF123456)}">',
        ]
    )
    for group_index, (_, _, (x, y, z)) in enumerate(PLATE_GROUPS, start=1):
        top_id = 99 + group_index
        lines.append(
            f'  <item objectid="{top_id}" '
            f'p:UUID="{bambu.object_uuid(5000 + group_index, 0xABCDEF123456)}" '
            f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}" printable="1"/>'
        )
    lines.extend([" </build>", "</model>"])
    return ("\n".join(lines) + "\n").encode()


def _preview_png(plate_number: int, size: int = 512) -> bytes:
    colours = {
        1: ("#FFFFFF", "#000000", "#E8AFCF"),
        2: ("#F99963", "#E8AFCF", "#F99963"),
        3: ("#FFFFFF", "#F99963", "#FFFFFF"),
    }
    image = Image.new("RGBA", (size, size), (246, 240, 231, 255))
    draw = ImageDraw.Draw(image)
    primary, accent, tertiary = colours[plate_number]
    draw.rounded_rectangle((68, 148, 444, 360), radius=82, fill=primary, outline="#3F3634", width=6)
    if plate_number == 1:
        draw.ellipse((175, 235, 195, 269), fill=accent)
        draw.ellipse((317, 235, 337, 269), fill=accent)
        draw.arc((220, 230, 292, 304), 20, 160, fill=accent, width=8)
        draw.ellipse((135, 270, 175, 310), fill=tertiary)
        draw.ellipse((337, 270, 377, 310), fill=tertiary)
    elif plate_number == 2:
        for x in (140, 220, 300, 380):
            draw.rounded_rectangle((x, 160, x + 18, 348), radius=9, fill=accent)
    elif plate_number == 3:
        for x, side in ((120, 80), (226, 86), (338, 92)):
            draw.rectangle((x, 214, x + side, 214 + side), outline="#756A65", width=5)
    draw.text((24, 24), f"Happy Salmon Nigiri - plate {plate_number}", fill="#3F3634")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _expand_project_to_four_filaments(settings: dict) -> None:
    """Expand the two-filament P2S template without altering machine arrays."""
    for key, value in list(settings.items()):
        if not key.startswith("filament_") or not isinstance(value, list):
            continue
        if len(value) == 2:
            settings[key] = [value[0], value[1], value[0], value[1]]
        elif len(value) == 4:
            # Template stores Standard/High-Flow pairs for each filament.
            pair = value[:2]
            settings[key] = pair * 4

    settings["filament_self_index"] = [
        str(index)
        for index in range(1, 5)
        for _ in range(2)
    ]
    settings["filament_nozzle_map"] = ["0", "0", "0", "0"]
    settings["filament_extruder_compatibility"] = ["0", "0", "0", "0"]
    settings["nozzle_temperature"] = ["220", "220"] * 4
    settings["nozzle_temperature_initial_layer"] = ["220", "220"] * 4
    # Source rows / target columns: Ivory, Orange, Pink, Charcoal.
    # Pink/Charcoal → Ivory must purge hard; residual pigment shows through
    # translucent Matte white as a horizontal band across the face layers.
    settings["flush_volumes_matrix"] = [
        "0", "140", "140", "140",
        "520", "0", "220", "160",
        "700", "280", "0", "160",
        "900", "620", "620", "0",
    ]
    settings["flush_volumes_vector"] = ["140"] * 8
    settings["flush_multiplier"] = ["1.4"]
    settings["flush_into_infill"] = "0"
    settings["flush_into_objects"] = "0"
    settings["flush_into_support"] = "0"
    settings["filament_prime_volume"] = ["60", "60", "60", "60"]
    settings["filament_minimal_purge_on_wipe_tower"] = ["25", "25", "25", "25"]


def build_bambu_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    objects: list[tuple[str, Path, int]],
) -> Path:
    meshes = [trimesh.load_mesh(path, process=True) for _, path, _ in objects]
    for (name, _, _), mesh in zip(objects, meshes):
        _validate_mesh(name, mesh)

    bambu.OBJECTS = objects

    template_path = assets.BLANK_PROJECT
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
        _expand_project_to_four_filaments(settings)
        settings["layer_height"] = "0.16"
        settings["initial_layer_print_height"] = "0.20"
        settings["wall_loops"] = "4"
        # P2S / current Bambu Studio rejects Inner/Outer/Inner and silently
        # replaces it; Inner/Outer is the supported option that still prints the
        # visible outer wall after some white has already left the nozzle.
        settings["wall_sequence"] = "inner wall/outer wall"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        settings["flush_into_infill"] = "0"
        settings["flush_into_objects"] = "0"
        settings["flush_into_support"] = "0"
        settings["filament_colour"] = [colour for _, colour in FILAMENTS]
        settings["default_filament_colour"] = ["", "", "", ""]
        # Use the stock Bambu Matte PLA P2S profile for every AMS slot. Custom
        # "@Happy Salmon ..." names were phantom overrides and hid the real
        # defaults for temperature, flow, and flush behaviour.
        settings["filament_settings_id"] = ["Bambu PLA Matte @BBL P2S"] * 4
        settings["filament_ids"] = ["GFA01", "GFA01", "GFA01", "GFA01"]
        settings["filament_vendor"] = ["Bambu Lab"] * 4
        settings["filament_type"] = ["PLA", "PLA", "PLA", "PLA"]
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=2, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))
        for plate_number in range(1, len(PLATE_GROUPS) + 1):
            preview = _preview_png(plate_number)
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(f"Metadata/{stem}_{plate_number}.png", preview)

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
    return output_path


def generate(job_dir: Path) -> Path:
    job_dir = Path(job_dir)
    mesh_dir = job_dir / "meshes"
    if mesh_dir.exists():
        shutil.rmtree(mesh_dir)
    mesh_dir.mkdir(parents=True, exist_ok=True)

    body, face, cheeks = build_rice_body()
    button, stripes = build_salmon_button()
    button = _stl_safe_mesh(button)
    coupon = build_switch_coupon()
    assembly_validation = _validate_assembly_envelope(body, button)
    inlay_validation = [
        _validate_inlay_containment("Sakura Pink salmon stripes", stripes, button),
        _validate_inlay_containment("Charcoal face", face, body),
        _validate_inlay_containment("Sakura Pink cheeks", cheeks, body),
    ]
    button_for_print = _flip_cap_for_print(button)
    stripes_for_print = _flip_cap_for_print(stripes)

    named_meshes = [
        ("rice_body", body),
        ("charcoal_face", face),
        ("sakura_cheeks", cheeks),
        ("salmon_button", button_for_print),
        ("sakura_stripes", stripes_for_print),
        ("switch_fit_coupon", coupon),
    ]
    validation = []
    for filename, mesh in named_meshes:
        validation.append(_validate_mesh(filename, mesh))
        mesh.export(mesh_dir / f"{filename}.stl")

    objects = [
        ("Ivory rice body", mesh_dir / "rice_body.stl", 1),
        ("Charcoal smile and eyes", mesh_dir / "charcoal_face.stl", 4),
        ("Sakura Pink cheeks", mesh_dir / "sakura_cheeks.stl", 3),
        ("Mandarin Orange salmon button", mesh_dir / "salmon_button.stl", 2),
        ("Sakura Pink salmon stripes", mesh_dir / "sakura_stripes.stl", 3),
        ("Outemu switch fit coupon", mesh_dir / "switch_fit_coupon.stl", 1),
    ]
    output = job_dir / "Happy_Salmon_Nigiri_Clicker_P2S.3mf"
    build_bambu_project(mesh_dir=mesh_dir, output_path=output, objects=objects)

    report = {
        "project": "Happy Salmon Nigiri Clicker",
        "units": "mm",
        "printer_profile": "Bambu Lab P2S 0.4 nozzle",
        "material": "Bambu PLA Matte",
        "filaments": [
            {"slot": index, "name": name, "hex": colour}
            for index, (name, colour) in enumerate(FILAMENTS, start=1)
        ],
        "finished_target": {
            "length": CAP_LENGTH,
            "width": CAP_WIDTH,
            "height_unpressed": round(TARGET_OVERALL_HEIGHT, 2),
        },
        "switch": {
            "type": "Outemu (Gaote) Blue, 3-pin, 50 gf",
            "upper_body_width": SWITCH_UPPER,
            "lower_body_width": SWITCH_LOWER,
            "housing_height": SWITCH_HOUSING_HEIGHT,
            "lower_body_height": SWITCH_LOWER_BODY_HEIGHT,
            "mount_opening": SWITCH_OPENING,
            "mount_transition": (
                f"{SWITCH_OPENING:.2f} to {SWITCH_MOUNT_WIDE:.2f} mm "
                "support-safe tapered shoulder"
            ),
            "mount_shoulder_drop": SWITCH_SHOULDER_DROP,
            "calculated_seat_z": round(SWITCH_SEAT_Z, 3),
            "centre_pin_diameter": SWITCH_CENTRE_PIN_D,
            "contact_spacing": SWITCH_CONTACT_SPACING,
            "pin_clearance_floor_z": SWITCH_PIN_CLEARANCE_FLOOR,
            "retention": "Glue switch flange to tapered shoulder after coupon fit",
        },
        "moving_fit": {
            "mx_socket_major": MX_CROSS_MAJOR,
            "mx_socket_minor": MX_CROSS_MINOR,
            "mx_socket_depth": MX_SOCKET_DEPTH,
            "mx_socket_boss_diameter": MX_SOCKET_BOSS_D,
            "mx_stem_height": MX_STEM_HEIGHT,
            "salmon_lower_wall_thickness": CAP_LOWER_WALL,
            "salmon_cavity_opening": [
                CAP_LENGTH - 2.0 * CAP_LOWER_WALL,
                CAP_WIDTH - 2.0 * CAP_LOWER_WALL,
            ],
            "salmon_outer_exponent": CAP_OUTER_EXPONENT,
            "salmon_cavity_exponent": CAP_CAVITY_EXPONENT,
            "vertical_clearance_height": CAP_VERTICAL_CLEARANCE_HEIGHT,
            "collision_free_travel": 4.0,
            "bottom_out": "provided by switch travel; rice body remains clear",
            "lateral_guides": "none; intentional playful cap wobble",
        },
        "assembly_envelope": assembly_validation,
        "ams_inlays": inlay_validation,
        "coupon": {
            "plate_openings": [13.95, 14.10, 14.25],
            "reference_socket": {
                "boss_diameter": MX_SOCKET_BOSS_D,
                "cross_major": MX_CROSS_MAJOR,
                "cross_minor": MX_CROSS_MINOR,
                "depth": MX_SOCKET_DEPTH,
                "source": "measured from known-working CritterCRAFT Dumpling STL",
            },
            "acceptance": (
                "Choose the smallest switch opening that admits the lower housing "
                "without force. The projecting socket reproduces the known-working "
                "reference geometry supplied by the user."
            ),
        },
        "assembly": [
            "Print plate 3 first and confirm the switch opening and stem socket.",
            "Press the switch down through the rice top and glue its flange to the tapered shoulder.",
            "Keep both electrical pins and the centre locating pin straight in the sealed cavity.",
            "Push the salmon button directly onto the MX stem.",
        ],
        "validation": validation,
    }
    (job_dir / "dimensions_and_validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Happy Salmon Nigiri fidget clicker 3MF"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.out))
