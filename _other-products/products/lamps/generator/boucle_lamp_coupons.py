#!/usr/bin/env python3
"""Print-ready coupons for the Bouclé Stack table lamp.

Four print stages have to pass before any full-size shell is worth printing:

1. **Glow coupon** — a 150° arc of wall at the production radius, stepping
   1.2 / 1.6 / 2.0 mm around the arc, with the upper half fuzzy-painted and the
   lower half smooth. Settles wall thickness, whether Bone White transmits
   enough light, and whether fuzzy skin thins the wall into pinholes.
2. **A→B joint coupon** — 100° arcs of shell A, its halo ring and shell B.
3. **B→C joint coupon** — the second real joint; its angle, radii and ring are
   different enough that the first coupon cannot validate it.
4. **Base interface** — the production LED cradle and plinth top seat, plus a
   shell A base arc. Settles the hardware pocket, cable, retained cradle fit,
   and the shade's actual bearing surface.

Geometry comes from `boucle_lamp_config`, which is also what the 2D concept
sheet draws, so the coupons cannot drift from the drawing.

Run from the repository root:

    .venv/bin/python products/lamps/generator/boucle_lamp_coupons.py --out out/boucle-lamp-coupons
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET

import numpy as np
import trimesh
import manifold3d
from PIL import Image, ImageDraw
from shapely.geometry import MultiPoint, Polygon

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ogma import assets  # noqa: E402

from ogma import bambu_project as bambu  # noqa: E402
import boucle_lamp_config as cfg  # noqa: E402
from ogma.filaments import load_palette, resolve_filament  # noqa: E402

SHELL_FILAMENT = "matte-bone-white"
BASE_FILAMENT = "matte-dark-chocolate"

SECTIONS = 288
COUPON_WEDGE_PHASE_DEG = 180.0 / SECTIONS

# Solids that only touch along a line union into a non-manifold seam, so give
# neighbours a sliver of real overlap instead.
SEAM_OVERLAP_DEG = 0.05

# Glow coupon
GLOW_RADIUS = 72.0
GLOW_HEIGHT = 50.0
GLOW_FOOT_H = 3.0
GLOW_FOOT_OUT = 2.0
GLOW_SECTOR_DEG = 50.0
GLOW_WALLS = (1.2, 1.6, 2.0)
GLOW_DOT_R = 1.3

# Joint coupon
JOINT_ARC_DEG = 100.0
JOINT_LOWER_H = 26.0
JOINT_UPPER_H = 26.0
UPPER_REGISTER_W = cfg.RING_REGISTER_W
UPPER_REGISTER_H = 4.0
COUPON_FOOT_H = 2.0
COUPON_FOOT_IN = 3.0
COUPON_FOOT_OUT = 1.5
BASE_SEAT_ARC_DEG = 50.0
BASE_SEAT_H = 12.0

# Cradle coupon — full production height so the floor thickness is honest
CRADLE_COUPON_H = cfg.CRADLE_Z1 - cfg.CRADLE_Z0

# Plinth interface gauge: full production height because a short ring cannot
# reveal binding down the 28 mm bore or prove the cradle's retention shoulder.
GAUGE_H = cfg.PLINTH_Z1 - cfg.PLINTH_Z0


# --------------------------------------------------------------------------
# Mesh helpers
# --------------------------------------------------------------------------


def _finish(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight or not mesh.is_volume:
        raise RuntimeError(f"{name} is not a watertight volume")
    mesh.metadata["name"] = name
    return mesh


def _serialization_safe(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    """Validate the geometry at the same precision written into the 3MF.

    Boolean output can be watertight in float64 but collapse into zero-area
    triangles when vertices are formatted to eight decimals. Clean at that
    precision now, before metadata and paint masks are generated.
    """
    working = trimesh.Trimesh(
        vertices=np.round(mesh.vertices, 8), faces=mesh.faces, process=False
    )
    working.merge_vertices(digits_vertex=8)
    vertices = working.vertices.astype(np.float32)
    source = manifold3d.Mesh(
        vert_properties=vertices,
        tri_verts=working.faces.astype(np.uint32),
        tolerance=1e-6,
    )
    repaired = manifold3d.Manifold(source)
    if repaired.status() != manifold3d.Error.NoError:
        raise RuntimeError(
            f"{name} cannot be reconstructed at serialization precision: "
            f"{repaired.status()}"
        )
    # Manifold can preserve zero-length topology even when the solid itself is
    # valid. A 1 nm simplification removes those edges without changing any
    # printable or fit dimension, preventing Studio from auto-repairing them.
    emitted = repaired.simplify(1e-6).to_mesh64()
    cleaned = trimesh.Trimesh(
        vertices=np.round(np.asarray(emitted.vert_properties)[:, :3], 8),
        faces=np.asarray(emitted.tri_verts),
        process=False,
    )
    return _finish(cleaned, name)


def _split_surface_at_z(mesh: trimesh.Trimesh, split_z: float) -> trimesh.Trimesh:
    """Insert real triangle edges where the fuzzy/smooth boundary crosses."""

    def clip(poly: list[np.ndarray], keep_above: bool) -> list[np.ndarray]:
        output: list[np.ndarray] = []

        def inside(point):
            return point[2] >= split_z if keep_above else point[2] <= split_z

        for start, end in zip(poly, poly[1:] + poly[:1]):
            start_in, end_in = inside(start), inside(end)
            if start_in:
                output.append(start)
            if start_in != end_in:
                t = (split_z - start[2]) / (end[2] - start[2])
                output.append(start + (end - start) * t)
        return output

    vertices: list[np.ndarray] = []
    faces: list[list[int]] = []
    for triangle in mesh.triangles:
        low, high = float(triangle[:, 2].min()), float(triangle[:, 2].max())
        polygons = (
            [list(triangle)]
            if not (low < split_z - 1e-9 and high > split_z + 1e-9)
            else [clip(list(triangle), False), clip(list(triangle), True)]
        )
        for polygon in polygons:
            if len(polygon) < 3:
                continue
            first = len(vertices)
            vertices.extend(polygon)
            for index in range(1, len(polygon) - 1):
                faces.append([first, first + index, first + index + 1])

    split = trimesh.Trimesh(
        vertices=np.asarray(vertices), faces=np.asarray(faces), process=False
    )
    # Do not run this mesh through `_serialization_safe`: Manifold correctly
    # reconstructs the solid but removes the deliberately collinear split edges
    # while retriangulating each flat wall. Those edges are required so fuzzy
    # paint can stop exactly at `split_z`.
    split.vertices = np.round(split.vertices, 8)
    split.merge_vertices(digits_vertex=8)
    split.remove_unreferenced_vertices()
    split.fix_normals()
    if np.any(split.area_faces <= 1e-10):
        raise RuntimeError("glow coupon split created zero-area faces")
    source = manifold3d.Mesh(
        vert_properties=split.vertices.astype(np.float32),
        tri_verts=split.faces.astype(np.uint32),
        tolerance=1e-6,
    )
    reconstructed = manifold3d.Manifold(source)
    if reconstructed.status() != manifold3d.Error.NoError:
        raise RuntimeError(
            "glow coupon split is invalid at serialization precision: "
            f"{reconstructed.status()}"
        )
    return _finish(split, "glow coupon split at fuzzy boundary")


def _union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.union(meshes, engine="manifold")


def _difference(mesh: trimesh.Trimesh, cutters: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.difference([mesh, *cutters], engine="manifold")


def _intersection(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.intersection(meshes, engine="manifold")


def annular_sector(
    r_inner: float,
    r_outer: float,
    height: float,
    a0_deg: float,
    a1_deg: float,
    z0: float = 0.0,
    steps: int = 96,
) -> trimesh.Trimesh:
    """A solid annular sector, extruded in +z from `z0`.

    A full 360° span has to be built as a polygon with a hole; concatenating the
    outer and inner rings would produce a self-touching boundary that Manifold
    rejects.
    """
    full = abs((a1_deg - a0_deg) % 360.0) < 1e-9 and abs(a1_deg - a0_deg) > 1e-9
    a0, a1 = math.radians(a0_deg), math.radians(a1_deg)

    def ring(radius, count):
        return [
            (radius * math.cos(t), radius * math.sin(t))
            for t in np.linspace(a0, a1, count, endpoint=not full)
        ]

    outer = ring(r_outer, steps)
    if full:
        poly = Polygon(outer, [ring(r_inner, steps)] if r_inner > 1e-9 else None)
    elif r_inner > 1e-9:
        poly = Polygon(outer + list(reversed(ring(r_inner, steps))))
    else:
        poly = Polygon([(0.0, 0.0)] + outer)

    mesh = trimesh.creation.extrude_polygon(poly, height)
    mesh.apply_translation([0.0, 0.0, z0])
    return mesh


def wedge(a0_deg: float, a1_deg: float, radius: float = 400.0, half_h: float = 500.0):
    """A pie-slice prism used to cut arcs out of full solids of revolution."""
    a0, a1 = math.radians(a0_deg), math.radians(a1_deg)
    angles = np.linspace(a0, a1, 128)
    pts = [(0.0, 0.0)] + [(radius * math.cos(t), radius * math.sin(t)) for t in angles]
    mesh = trimesh.creation.extrude_polygon(Polygon(pts), 2 * half_h)
    mesh.apply_translation([0.0, 0.0, -half_h])
    return mesh


def shell_wall_solid(
    shell: cfg.Shell,
    sections: int = SECTIONS,
    stride: int = 1,
    wall: float = cfg.WALL,
) -> trimesh.Trimesh:
    """The full shell as printed: base plane on z=0, cut by its own oblique plane.

    `stride` thins the profile for preview meshes; leave it at 1 for anything
    that gets printed or measured.
    """
    if wall <= 0.0:
        raise ValueError("shell wall thickness must be positive")
    flat = shell.as_printed()
    limit = flat.long_side + 1.0
    pts = [(r, s) for s, r in flat.samples if s <= limit]
    if stride > 1:
        thinned = pts[::stride]
        if thinned[-1] != pts[-1]:
            thinned.append(pts[-1])
        pts = thinned
    profile = pts + [(r - wall, s) for r, s in reversed(pts)]
    profile.append(profile[0])

    mesh = trimesh.creation.revolve(np.asarray(profile), sections=sections)
    mesh = _finish(mesh, f"{shell.key}_revolve")

    deg, high = shell.local_cut()
    beta = math.radians(deg)
    # Normal points down through the cut plane, so the lower part is kept.
    normal = (high * math.sin(beta), 0.0, -math.cos(beta))
    mesh = mesh.slice_plane(
        plane_origin=(0.0, 0.0, shell.axis_length),
        plane_normal=normal,
        cap=True,
    )
    return _finish(mesh, f"{shell.key}_wall")


# --------------------------------------------------------------------------
# Coupon 1 — glow wall
# --------------------------------------------------------------------------


def build_glow_coupon() -> tuple[trimesh.Trimesh, np.ndarray, dict]:
    total = GLOW_SECTOR_DEG * len(GLOW_WALLS)
    a0 = -total / 2.0

    parts = [
        annular_sector(
            GLOW_RADIUS - max(GLOW_WALLS) - GLOW_FOOT_OUT,
            GLOW_RADIUS + GLOW_FOOT_OUT,
            GLOW_FOOT_H,
            a0,
            a0 + total,
        )
    ]
    sectors = []
    for i, wall in enumerate(GLOW_WALLS):
        s0 = a0 + i * GLOW_SECTOR_DEG
        s1 = s0 + GLOW_SECTOR_DEG
        # Neighbouring bands overlap slightly. Butting them edge to edge leaves a
        # vertical non-manifold seam where four faces meet on one line.
        parts.append(
            annular_sector(
                GLOW_RADIUS - wall,
                GLOW_RADIUS,
                GLOW_HEIGHT,
                s0 - (SEAM_OVERLAP_DEG if i else 0.0),
                s1 + (0.0 if i == len(GLOW_WALLS) - 1 else SEAM_OVERLAP_DEG),
                z0=GLOW_FOOT_H,
            )
        )
        sectors.append({"wall_mm": wall, "start_deg": s0, "end_deg": s1, "dots": i + 1})

        # i+1 identification dots on the outer face of the foot
        mid = math.radians((s0 + s1) / 2.0)
        for d in range(i + 1):
            offset = (d - i / 2.0) * math.radians(6.0)
            t = mid + offset
            dot = trimesh.creation.icosphere(subdivisions=2, radius=GLOW_DOT_R)
            dot.apply_translation(
                [
                    (GLOW_RADIUS + GLOW_FOOT_OUT) * math.cos(t),
                    (GLOW_RADIUS + GLOW_FOOT_OUT) * math.sin(t),
                    GLOW_FOOT_H / 2.0,
                ]
            )
            parts.append(dot)

    mesh = _finish(_union(parts), "Boucle_Glow_Coupon")
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0, 2]])
    split_z = GLOW_FOOT_H + GLOW_HEIGHT / 2.0
    mesh = _split_surface_at_z(mesh, split_z)

    centres = mesh.triangles_center
    triangles = mesh.vertices[mesh.faces]
    normals = mesh.face_normals
    radial = np.hypot(centres[:, 0], centres[:, 1])
    radial_direction = np.zeros_like(normals)
    radial_direction[:, 0] = centres[:, 0]
    radial_direction[:, 1] = centres[:, 1]
    radial_length = np.linalg.norm(radial_direction, axis=1)
    radial_direction[radial_length > 1e-9] /= radial_length[radial_length > 1e-9, None]
    outward_side = (
        np.einsum("ij,ij->i", normals, radial_direction) > 0.8
    ) & (np.abs(normals[:, 2]) < 0.2)
    paint = (
        (radial >= GLOW_RADIUS - 0.8)
        & (radial <= GLOW_RADIUS + 0.4)
        & outward_side
        & (triangles[:, :, 2].min(axis=1) >= split_z - 1e-8)
    )
    outer_wall = (
        (radial >= GLOW_RADIUS - 0.8)
        & (radial <= GLOW_RADIUS + 0.4)
        & outward_side
    )
    if np.any(
        paint
        & (triangles[:, :, 2].min(axis=1) < split_z - 1e-8)
    ):
        raise RuntimeError("a fuzzy-painted face crosses below the split boundary")
    if np.any(paint & (np.abs(normals[:, 2]) >= 0.2)):
        raise RuntimeError("horizontal glow-coupon faces were fuzzy-painted")
    painted_area = float(mesh.area_faces[paint].sum())
    outer_area = float(mesh.area_faces[outer_wall].sum())
    if not 0.35 <= painted_area / max(outer_area, 1e-9) <= 0.65:
        raise RuntimeError(
            f"glow coupon paint covers {painted_area / outer_area:.0%} of the outer "
            "wall; expected roughly half"
        )

    report = {
        "coupon": "glow wall",
        "radius": GLOW_RADIUS,
        "panel_height": GLOW_HEIGHT,
        "foot_height": GLOW_FOOT_H,
        "arc_deg": total,
        "sectors": sectors,
        "fuzzy_above_z": split_z,
        "painted_fraction_of_outer_wall": round(painted_area / outer_area, 3),
        "volume_mm3": round(float(mesh.volume), 1),
        "acceptance": (
            "Lit from inside in a dark room: pick the thinnest sector with an even "
            "glow, no visible pinholes in the fuzzy half, and no layer banding."
        ),
    }
    return mesh, paint, report


def build_baffle() -> tuple[trimesh.Trimesh, dict]:
    """Production diffuser baffle in its support-free print orientation.

    The diffuser disc lies on the bed and the three posts grow upward. It is
    flipped for assembly, putting the disc 30 mm above the cradle.
    """
    disc = trimesh.creation.cylinder(
        radius=cfg.BAFFLE_DIA / 2.0,
        height=cfg.BAFFLE_WALL,
        sections=SECTIONS,
    )
    disc.apply_translation([0.0, 0.0, cfg.BAFFLE_WALL / 2.0])
    parts = [disc]
    locator_phases = []
    for index in range(cfg.BAFFLE_LOCATOR_COUNT):
        angle_deg = (
            cfg.BAFFLE_LOCATOR_PHASE_DEG
            + 360.0 * index / cfg.BAFFLE_LOCATOR_COUNT
        ) % 360.0
        locator_phases.append(angle_deg)
        angle = math.radians(angle_deg)
        post = trimesh.creation.cylinder(
            radius=cfg.BAFFLE_POST_DIA / 2.0,
            height=cfg.BAFFLE_POST_H + 0.4,
            sections=64,
        )
        post.apply_translation(
            [
                cfg.BAFFLE_POST_R * math.cos(angle),
                cfg.BAFFLE_POST_R * math.sin(angle),
                cfg.BAFFLE_WALL + cfg.BAFFLE_POST_H / 2.0 - 0.2,
            ]
        )
        parts.append(post)
        locator = trimesh.creation.cylinder(
            radius=cfg.BAFFLE_LOCATOR_DIA / 2.0,
            height=cfg.BAFFLE_LOCATOR_H + 0.2,
            sections=48,
        )
        locator.apply_translation(
            [
                cfg.BAFFLE_POST_R * math.cos(angle),
                cfg.BAFFLE_POST_R * math.sin(angle),
                (
                    cfg.BAFFLE_WALL
                    + cfg.BAFFLE_POST_H
                    + cfg.BAFFLE_LOCATOR_H / 2.0
                    - 0.1
                ),
            ]
        )
        parts.append(locator)
    mesh = _finish(_union(parts), "Boucle_LED_Baffle")
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0, 2]])
    mesh = _serialization_safe(mesh, "Boucle_LED_Baffle")
    return mesh, {
        "coupon": "production LED diffuser baffle",
        "disc_diameter": cfg.BAFFLE_DIA,
        "disc_thickness": cfg.BAFFLE_WALL,
        "post_count": cfg.BAFFLE_LOCATOR_COUNT,
        "post_height": cfg.BAFFLE_POST_H,
        "locator_pegs": {
            "count": cfg.BAFFLE_LOCATOR_COUNT,
            "diameter": cfg.BAFFLE_LOCATOR_DIA,
            "engagement": cfg.BAFFLE_LOCATOR_H,
            "phases_deg": locator_phases,
        },
        "print_orientation": (
            "diffuser disc on bed, posts and reduced locator tips up; "
            "flip for assembly"
        ),
        "acceptance": (
            "All three posts are straight and equal-height, the disc stays flat, "
            "all three locator tips enter the cradle sockets without force or "
            "rocking, and when placed over the powered module no LED die is "
            "directly visible from normal seated eye height."
        ),
    }


# --------------------------------------------------------------------------
# Coupon 2 — halo joint
# --------------------------------------------------------------------------


def joint_frame(lower: cfg.Shell) -> tuple[cfg.Shell, np.ndarray]:
    """The upper shell's frame, expressed in the lower shell's printed frame.

    The upper shell's axis is by definition the normal of the lower shell's cut
    plane, so in the returned frame that plane is exactly `z = -HALO_GAP` and
    the whole joint — rim face, halo slot, upper base — is a stack of parallel
    horizontal planes. The ring is built here, which is also how it prints.
    """
    flat = lower.as_printed()
    n = flat.cut_normal
    mid = (
        (flat.rim_r[0] + flat.rim_l[0]) / 2.0,
        (flat.rim_r[1] + flat.rim_l[1]) / 2.0,
    )
    origin = (mid[0] + n[0] * cfg.HALO_GAP, mid[1] + n[1] * cfg.HALO_GAP)
    matrix = trimesh.transformations.rotation_matrix(
        math.atan2(n[0], n[1]), [0.0, 1.0, 0.0]
    )
    matrix[0, 3], matrix[1, 3], matrix[2, 3] = origin[0], 0.0, origin[1]
    return flat, matrix


def inner_envelope(
    flat: cfg.Shell, clearance: float, s_max: float, sections: int = SECTIONS, steps: int = 260
) -> trimesh.Trimesh:
    """Solid of revolution filling the shell's cavity, minus `clearance`."""
    profile = [(0.0, 0.0)]
    profile += [
        (max(flat.radius_at(s) - cfg.WALL - clearance, 0.05), float(s))
        for s in np.linspace(0.0, s_max, steps)
    ]
    profile += [(0.0, s_max), (0.0, 0.0)]
    mesh = trimesh.creation.revolve(np.asarray(profile), sections=sections)
    return _finish(mesh, "shell cavity envelope")


def _radial_box(
    inner_r: float,
    outer_r: float,
    width: float,
    z0: float,
    z1: float,
    phase_deg: float,
) -> trimesh.Trimesh:
    box = trimesh.creation.box(
        extents=[outer_r - inner_r, width, z1 - z0]
    )
    box.apply_translation(
        [(inner_r + outer_r) / 2.0, 0.0, (z0 + z1) / 2.0]
    )
    box.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(phase_deg),
            [0.0, 0.0, 1.0],
        )
    )
    return box


def joint_clocking_key(upper: cfg.Shell) -> trimesh.Trimesh:
    """Support-free tapered tab that fixes upper-shell rotation."""
    register_inner_r = (
        upper.base_radius - cfg.WALL - cfg.RING_REGISTER_W
    )
    collar_r = register_inner_r - cfg.RING_SLIP
    key_inner_r = collar_r - 0.3
    key_outer_r = (
        register_inner_r + cfg.JOINT_CLOCK_KEY_DEPTH
    )
    tip_z0 = (
        cfg.JOINT_CLOCK_KEY_HEIGHT
        - cfg.JOINT_CLOCK_TIP_HEIGHT
    )
    body = _radial_box(
        key_inner_r,
        key_outer_r,
        cfg.JOINT_CLOCK_KEY_WIDTH,
        0.0,
        tip_z0 + 0.2,
        cfg.JOINT_CLOCK_PHASE_DEG,
    )
    tip = _radial_box(
        key_inner_r,
        key_outer_r,
        cfg.JOINT_CLOCK_TIP_WIDTH,
        tip_z0,
        cfg.JOINT_CLOCK_KEY_HEIGHT,
        cfg.JOINT_CLOCK_PHASE_DEG,
    )
    return _finish(
        _union([body, tip]),
        f"{upper.key} upper-shell clocking key",
    )


def cut_joint_clocking_groove(
    solid: trimesh.Trimesh,
    upper: cfg.Shell,
) -> trimesh.Trimesh:
    """Cut an open-bottom notch into the upper shell's internal register."""
    register_inner_r = (
        upper.base_radius - cfg.WALL - cfg.RING_REGISTER_W
    )
    cutter = _radial_box(
        register_inner_r - 0.3,
        register_inner_r + cfg.JOINT_CLOCK_GROOVE_DEPTH,
        cfg.JOINT_CLOCK_GROOVE_WIDTH,
        -0.2,
        UPPER_REGISTER_H + 0.2,
        cfg.JOINT_CLOCK_PHASE_DEG,
    )
    return _finish(
        _difference(solid, [cutter]),
        f"{upper.key} register with clocking groove",
    )


def joint_clocking_report(upper: cfg.Shell) -> dict:
    tangential_clearance = (
        cfg.JOINT_CLOCK_GROOVE_WIDTH
        - cfg.JOINT_CLOCK_KEY_WIDTH
    )
    radial_clearance = (
        cfg.JOINT_CLOCK_GROOVE_DEPTH
        - cfg.JOINT_CLOCK_KEY_DEPTH
    )
    top_clearance = (
        UPPER_REGISTER_H - cfg.JOINT_CLOCK_KEY_HEIGHT
    )
    register_material_behind = (
        cfg.RING_REGISTER_W
        - cfg.JOINT_CLOCK_GROOVE_DEPTH
    )
    register_inner_r = (
        upper.base_radius - cfg.WALL - cfg.RING_REGISTER_W
    )
    angular_play = math.degrees(
        math.atan2(
            tangential_clearance / 2.0,
            register_inner_r,
        )
    )
    if tangential_clearance < 0.6:
        raise RuntimeError(
            "joint clocking key has inadequate tangential clearance: "
            f"{tangential_clearance:.2f} mm"
        )
    if radial_clearance < 0.3:
        raise RuntimeError(
            "joint clocking key has inadequate radial clearance: "
            f"{radial_clearance:.2f} mm"
        )
    if top_clearance < 0.5:
        raise RuntimeError(
            "joint clocking key has inadequate top clearance: "
            f"{top_clearance:.2f} mm"
        )
    if register_material_behind < 2.0:
        raise RuntimeError(
            "joint clocking groove weakens the register: "
            f"{register_material_behind:.2f} mm remains"
        )
    return {
        "phase_deg": cfg.JOINT_CLOCK_PHASE_DEG,
        "key_width_mm": cfg.JOINT_CLOCK_KEY_WIDTH,
        "key_depth_mm": cfg.JOINT_CLOCK_KEY_DEPTH,
        "key_height_mm": cfg.JOINT_CLOCK_KEY_HEIGHT,
        "tip_width_mm": cfg.JOINT_CLOCK_TIP_WIDTH,
        "groove_width_mm": cfg.JOINT_CLOCK_GROOVE_WIDTH,
        "groove_depth_mm": cfg.JOINT_CLOCK_GROOVE_DEPTH,
        "tangential_clearance_total_mm": round(
            tangential_clearance, 2
        ),
        "radial_clearance_mm": round(radial_clearance, 2),
        "top_clearance_mm": round(top_clearance, 2),
        "register_material_behind_mm": round(
            register_material_behind, 2
        ),
        "maximum_angular_play_deg": round(angular_play, 3),
    }


def _lower_clock_engagement(lower: cfg.Shell) -> dict:
    """Shared radii and heights for the lower-shell skirt clock.

    The tab is built in the joint/print frame inside the upper 5 mm of the
    conformal skirt or band. Its joint-frame phase and radius are derived by
    projecting the printed-shell wall through `joint_frame`, so the open-rim
    notch cut in the shell frame lands on the same feature after assembly.
    """
    flat, matrix = joint_frame(lower)
    key_height = min(
        cfg.LOWER_CLOCK_KEY_HEIGHT,
        cfg.RING_OUTER_BAND_H - 0.6,
    )
    band_bottom_z = -cfg.HALO_GAP - cfg.RING_OUTER_BAND_H
    band_top_z = -cfg.HALO_GAP
    target_z = 0.5 * (band_bottom_z + band_top_z)
    theta = math.radians(cfg.LOWER_CLOCK_PHASE_DEG)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    inv = np.linalg.inv(matrix)
    # The oblique rim has one local height at this azimuth. Solve the cut-plane
    # equation against the varying shell radius instead of spanning from the
    # global short side to the global long side, which cuts a long wall channel.
    rim_s = flat.axis_length
    cut_slope = flat.cut_high * math.tan(math.radians(flat.cut_deg))
    for _ in range(12):
        rim_s = flat.axis_length + cut_slope * flat.radius_at(rim_s) * cos_t
    rim_s = min(max(rim_s, flat.short_side), flat.long_side)

    best = None
    s_short = flat.short_side
    s_long = flat.long_side
    for s in np.linspace(max(s_short - 2.0, 0.0), s_long + 1.0, 120):
        wall_inner = flat.radius_at(s) - cfg.WALL
        skirt_outer = wall_inner - cfg.RING_SLIP
        point = inv @ np.array(
            [skirt_outer * cos_t, skirt_outer * sin_t, s, 1.0],
            dtype=float,
        )
        joint_xy_r = math.hypot(float(point[0]), float(point[1]))
        joint_phase = math.degrees(
            math.atan2(float(point[1]), float(point[0]))
        )
        score = abs(float(point[2]) - target_z)
        if best is None or score < best["score"]:
            best = {
                "score": score,
                "s": float(s),
                "wall_inner_r": float(wall_inner),
                "skirt_outer_r_flat": float(skirt_outer),
                "joint_skirt_outer_r": joint_xy_r,
                "joint_phase_deg": joint_phase,
                "joint_z": float(point[2]),
            }
    if best is None or best["score"] > 1.25:
        raise RuntimeError(
            "could not locate lower-shell clocking station in the outer band"
        )

    wall_remaining = cfg.WALL - cfg.LOWER_CLOCK_GROOVE_DEPTH
    if key_height < 2.5:
        raise RuntimeError(
            "lower-shell clocking key is shorter than 2.5 mm: "
            f"{key_height:.2f} mm"
        )
    if wall_remaining < 0.6:
        raise RuntimeError(
            "lower-shell clocking groove leaves less than 0.6 mm of wall: "
            f"{wall_remaining:.2f} mm"
        )
    if cfg.LOWER_CLOCK_GROOVE_DEPTH < cfg.LOWER_CLOCK_KEY_DEPTH + 0.25:
        raise RuntimeError(
            "lower-shell clocking groove needs ≥0.25 mm radial clearance "
            "over its key"
        )
    return {
        "flat": flat,
        "key_height": key_height,
        "s_mid": best["s"],
        "skirt_outer_r": best["joint_skirt_outer_r"],
        "wall_inner_r": flat.radius_at(rim_s) - cfg.WALL,
        "wall_remaining": wall_remaining,
        "local_rim_z": rim_s,
        "band_bottom_z": band_bottom_z,
        "band_top_z": band_top_z,
        "joint_phase_deg": best["joint_phase_deg"],
        "shell_phase_deg": cfg.LOWER_CLOCK_PHASE_DEG,
    }


def lower_clocking_key(
    lower: cfg.Shell,
    bottom_z: float | None = None,
    skirt_source: trimesh.Trimesh | None = None,
) -> trimesh.Trimesh:
    """Outward tab that aligns a halo ring into its lower shell.

    Built in the joint/print frame so it roots into the real skirt or band. The
    underside rises at 45° from the skirt outer. Shell-frame phase 36° maps to
    the matching joint-frame azimuth after the cut-plane transform.
    `skirt_source` is accepted for call-site compatibility but the root radius
    comes from the projected shell wall.
    """
    del skirt_source
    engagement = _lower_clock_engagement(lower)
    band_bottom = engagement["band_bottom_z"]
    if bottom_z is not None:
        band_bottom = max(float(bottom_z), engagement["band_bottom_z"])
    band_top = engagement["band_top_z"]
    z0 = band_bottom + 0.15
    z1 = band_top + 0.05
    tip_z0 = z1 - cfg.LOWER_CLOCK_TIP_HEIGHT
    phase = engagement["joint_phase_deg"]
    skirt_outer_r = engagement["skirt_outer_r"]
    key_inner_r = skirt_outer_r - 0.55
    key_outer_r = skirt_outer_r + cfg.LOWER_CLOCK_KEY_DEPTH
    body = _radial_box(
        key_inner_r,
        key_outer_r,
        cfg.LOWER_CLOCK_KEY_WIDTH,
        z0,
        tip_z0 + 0.2,
        phase,
    )
    tip = _radial_box(
        key_inner_r,
        key_outer_r,
        cfg.LOWER_CLOCK_TIP_WIDTH,
        tip_z0,
        z1,
        phase,
    )
    nose = _finish(
        _union([body, tip]),
        f"{lower.key} lower-shell clocking nose source",
    )
    theta = math.radians(phase)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    nose = nose.slice_plane(
        plane_origin=(
            skirt_outer_r * cos_t,
            skirt_outer_r * sin_t,
            z0,
        ),
        plane_normal=(-cos_t, -sin_t, 1.0),
        cap=True,
    )
    key = _serialization_safe(
        _finish(nose, f"{lower.key} lower-shell clocking key"),
        f"{lower.key} lower-shell clocking key",
    )
    if float(key.volume) < 1.0:
        raise RuntimeError(
            f"{lower.key} lower-shell clocking key is too small after clipping"
        )
    return key


def _lower_clock_groove_envelope(lower: cfg.Shell) -> dict:
    """Shell-frame notch bounds enclosing the tilted joint-frame key."""
    engagement = _lower_clock_engagement(lower)
    key = lower_clocking_key(lower)
    _, matrix = joint_frame(lower)
    key.apply_transform(matrix)
    vertices = key.vertices
    theta = math.radians(engagement["shell_phase_deg"])
    tangent = np.asarray([-math.sin(theta), math.cos(theta)])
    tangent_values = vertices[:, :2] @ tangent
    transformed_key_width = float(np.ptp(tangent_values))
    tangential_clearance = (
        cfg.LOWER_CLOCK_GROOVE_WIDTH - cfg.LOWER_CLOCK_KEY_WIDTH
    )
    groove_width = max(
        cfg.LOWER_CLOCK_GROOVE_WIDTH,
        transformed_key_width + tangential_clearance,
    )
    groove_z0 = float(vertices[:, 2].min()) - 0.3
    groove_z1 = max(
        float(vertices[:, 2].max()) + 0.3,
        engagement["local_rim_z"] + 0.6,
    )
    return {
        **engagement,
        "groove_width_shell_frame": groove_width,
        "groove_z0": groove_z0,
        "groove_z1": groove_z1,
        "transformed_key_width": transformed_key_width,
    }


def _conformal_lower_clock_cutter(
    lower: cfg.Shell,
    engagement: dict,
    steps: int = 24,
) -> trimesh.Trimesh:
    """Short open-rim notch that follows the shell's tapered inner wall."""
    flat = engagement["flat"]
    theta = math.radians(engagement["shell_phase_deg"])
    radial = np.asarray([math.cos(theta), math.sin(theta)])
    tangent = np.asarray([-math.sin(theta), math.cos(theta)])
    half_width = engagement["groove_width_shell_frame"] / 2.0
    vertices = []
    for z in np.linspace(
        engagement["groove_z0"],
        engagement["groove_z1"],
        steps,
    ):
        wall_inner_r = flat.radius_at(float(z)) - cfg.WALL
        for radial_offset, tangent_offset in (
            (-0.4, -half_width),
            (cfg.LOWER_CLOCK_GROOVE_DEPTH, -half_width),
            (cfg.LOWER_CLOCK_GROOVE_DEPTH, half_width),
            (-0.4, half_width),
        ):
            xy = radial * (wall_inner_r + radial_offset) + tangent * tangent_offset
            vertices.append([float(xy[0]), float(xy[1]), float(z)])

    faces = []
    for index in range(steps - 1):
        a = index * 4
        b = (index + 1) * 4
        for edge in range(4):
            next_edge = (edge + 1) % 4
            faces.extend(
                [
                    [a + edge, a + next_edge, b + next_edge],
                    [a + edge, b + next_edge, b + edge],
                ]
            )
    last = (steps - 1) * 4
    faces.extend(
        [
            [0, 2, 1],
            [0, 3, 2],
            [last, last + 1, last + 2],
            [last, last + 2, last + 3],
        ]
    )
    return _finish(
        trimesh.Trimesh(
            vertices=np.asarray(vertices),
            faces=np.asarray(faces, dtype=np.int64),
            process=False,
        ),
        f"{lower.key} conformal lower clocking groove cutter",
    )


def cut_lower_clocking_groove(
    solid: trimesh.Trimesh,
    lower: cfg.Shell,
) -> trimesh.Trimesh:
    """Cut an open-rim notch into the lower shell for the skirt clocking tab."""
    engagement = _lower_clock_groove_envelope(lower)
    cutter = _conformal_lower_clock_cutter(lower, engagement)
    return _finish(
        _difference(solid, [cutter]),
        f"{lower.key} rim with lower clocking groove",
    )


def lower_clocking_report(lower: cfg.Shell) -> dict:
    engagement = _lower_clock_groove_envelope(lower)
    tangential_clearance = (
        cfg.LOWER_CLOCK_GROOVE_WIDTH - cfg.LOWER_CLOCK_KEY_WIDTH
    )
    radial_clearance = (
        cfg.LOWER_CLOCK_GROOVE_DEPTH - cfg.LOWER_CLOCK_KEY_DEPTH
    )
    if tangential_clearance < 0.6:
        raise RuntimeError(
            "lower-shell clocking key has inadequate tangential clearance: "
            f"{tangential_clearance:.2f} mm"
        )
    if radial_clearance < 0.25:
        raise RuntimeError(
            "lower-shell clocking key has inadequate radial clearance: "
            f"{radial_clearance:.2f} mm"
        )
    return {
        "phase_deg": cfg.LOWER_CLOCK_PHASE_DEG,
        "key_width_mm": cfg.LOWER_CLOCK_KEY_WIDTH,
        "key_depth_mm": cfg.LOWER_CLOCK_KEY_DEPTH,
        "key_height_mm": round(engagement["key_height"], 2),
        "tip_width_mm": cfg.LOWER_CLOCK_TIP_WIDTH,
        "groove_width_joint_frame_mm": cfg.LOWER_CLOCK_GROOVE_WIDTH,
        "groove_width_shell_frame_mm": round(
            engagement["groove_width_shell_frame"], 2
        ),
        "groove_depth_mm": cfg.LOWER_CLOCK_GROOVE_DEPTH,
        "local_rim_height_mm": round(engagement["local_rim_z"], 2),
        "open_notch_height_mm": round(
            engagement["groove_z1"] - engagement["groove_z0"], 2
        ),
        "tangential_clearance_total_mm": round(
            tangential_clearance, 2
        ),
        "radial_clearance_mm": round(radial_clearance, 2),
        "wall_remaining_behind_mm": round(
            engagement["wall_remaining"], 2
        ),
        "open_to_oblique_rim": True,
    }


def build_halo_ring(
    lower: cfg.Shell, upper: cfg.Shell, sections: int = SECTIONS, steps: int = 260
) -> tuple[trimesh.Trimesh, dict]:
    """The insert that holds the halo slot open and carries the upper shell.

    Built — and printed — with the upper shell's axis vertical, so the skirt
    that bonds inside the lower shell leans by the joint angle instead of the
    seat overhanging it.
    """
    flat, matrix = joint_frame(lower)
    gap = cfg.HALO_GAP

    rb_in = upper.base_radius - cfg.WALL
    collar_r = rb_in - UPPER_REGISTER_W - cfg.RING_SLIP
    corbel_r = rb_in - UPPER_REGISTER_W / 2.0
    bore_r = collar_r - cfg.RING_WEB
    corbel_h = corbel_r - collar_r  # 45°, so it prints without support

    recess = cfg.joint_recess(lower, upper)
    minimum_rim_outer_r = corbel_r + recess
    if recess < cfg.RING_RECESS:
        raise RuntimeError(
            f"halo ring sits only {recess:.1f} mm inboard of the outer surface; "
            f"need {cfg.RING_RECESS} mm for the slot to read as shadow"
        )

    # Skirt: conformal to the lower shell's cavity, cut flat top and bottom by
    # the joint planes so it prints as a plain leaning tube.
    s_max = flat.long_side + 2.0
    skirt = _difference(
        inner_envelope(flat, cfg.RING_SLIP, s_max, sections, steps),
        [inner_envelope(flat, cfg.RING_SLIP + cfg.RING_WEB, s_max, sections, steps)],
    )
    skirt.apply_transform(np.linalg.inv(matrix))
    skirt = skirt.slice_plane(
        plane_origin=(0.0, 0.0, -gap), plane_normal=(0.0, 0.0, -1.0), cap=True
    ).slice_plane(
        plane_origin=(0.0, 0.0, -gap - cfg.RING_FOOT), plane_normal=(0.0, 0.0, 1.0), cap=True
    )
    skirt = _finish(skirt, "halo ring skirt")

    # Funnel: 45° cone from the skirt up to the collar. Its mouth reaches the
    # collar exactly at the joint plane, so the annulus between collar and
    # skirt is wide open at slot height and light can reach the slot.
    slant = cfg.RING_WEB * math.sqrt(2.0)
    reach = 92.0 - bore_r
    funnel = trimesh.creation.revolve(
        np.asarray(
            [
                (bore_r, -gap),
                (92.0, -gap - reach),
                (92.0, -gap - reach - slant),
                (bore_r, -gap - slant),
                (bore_r, -gap),
            ]
        ),
        sections=sections,
    )
    funnel = _finish(funnel, "halo ring funnel")

    collar = trimesh.creation.revolve(
        np.asarray(
            [
                (bore_r, -gap - slant - 1.0),
                (collar_r, -gap - slant - 1.0),
                (collar_r, -corbel_h),
                (corbel_r, 0.0),
                (collar_r, 0.0),
                (collar_r, UPPER_REGISTER_H - 0.8),
                (collar_r - 0.8, UPPER_REGISTER_H),
                (bore_r, UPPER_REGISTER_H),
                (bore_r, -gap - slant - 1.0),
            ]
        ),
        sections=sections,
    )
    collar = _finish(collar, "halo ring collar")

    # Clip the funnel back to the shell cavity, then square off the bottom. The
    # clip envelope is a hair wider than the skirt: cutting exactly on the
    # skirt's own outer surface leaves coincident faces and slivers.
    clip = inner_envelope(flat, cfg.RING_SLIP * 0.8, s_max, sections, steps)
    clip.apply_transform(np.linalg.inv(matrix))
    outside = _difference(
        trimesh.creation.cylinder(radius=200.0, height=400.0, sections=64).apply_translation(
            [0.0, 0.0, -gap - 200.0]
        ),
        [clip],
    )
    below = trimesh.creation.box(extents=[400.0, 400.0, 400.0])
    below.apply_translation([0.0, 0.0, -gap - cfg.RING_FOOT - 200.0])
    clocking_key = joint_clocking_key(upper)
    lower_key = lower_clocking_key(
        lower,
        bottom_z=-gap - cfg.RING_FOOT,
        skirt_source=skirt,
    )
    # The outward lower-shell tab must be unioned after the cavity clip:
    # `outside` deliberately removes anything beyond the skirt outer face.
    ring = _difference(
        _union([skirt, funnel, collar, clocking_key]),
        [outside, below],
    )
    ring = _finish(_union([ring, lower_key]), "Boucle_Halo_Ring")
    bodies = ring.split(only_watertight=False)
    if len(bodies) != 1:
        raise RuntimeError(
            f"halo ring came out as {len(bodies)} loose bodies — the funnel is "
            "not reaching the skirt"
        )

    report = {
        "print_orientation": "upper-shell axis vertical, skirt down",
        "bore_radius": round(bore_r, 2),
        "collar_radius": round(collar_r, 2),
        "seat_radius": round(corbel_r, 2),
        "web": cfg.RING_WEB,
        "skirt_length": cfg.RING_FOOT,
        "seat_inboard_of_outer_surface": round(recess, 2),
        "light_window": [
            round(corbel_r, 2),
            round(minimum_rim_outer_r - cfg.WALL, 2),
        ],
        "upper_shell_clocking": joint_clocking_report(upper),
        "lower_shell_clocking": lower_clocking_report(lower),
    }
    return ring, report


def check_joint_fit(
    lower: cfg.Shell, upper: cfg.Shell, ring: trimesh.Trimesh, upper_solid: trimesh.Trimesh
) -> dict:
    """Dry-assemble the joint and confirm nothing shares space.

    The three parts are generated in different frames from different profiles,
    so a clean boolean on each part is not enough — an assembled overlap would
    only show up as a ring that will not seat.
    """
    _flat, matrix = joint_frame(lower)
    lower_solid = cut_lower_clocking_groove(shell_wall_solid(lower), lower)
    lower_solid.apply_transform(np.linalg.inv(matrix))

    clashes = {}
    for label, other in (("lower shell", lower_solid), ("upper shell", upper_solid)):
        overlap = trimesh.boolean.intersection([ring, other], engine="manifold")
        # An empty result is the expected one; trimesh warns while integrating it.
        with np.errstate(invalid="ignore"):
            clashes[label] = round(float(overlap.volume), 3) if len(overlap.faces) else 0.0
    worst = max(clashes.values())
    if worst > 0.01:
        raise RuntimeError(f"halo joint parts interfere: {clashes} mm³")

    clocking_key = joint_clocking_key(upper)
    captured_key = trimesh.boolean.intersection(
        [ring, clocking_key],
        engine="manifold",
    )
    key_shell_overlap = trimesh.boolean.intersection(
        [clocking_key, upper_solid],
        engine="manifold",
    )
    captured_key_volume = (
        float(captured_key.volume)
        if len(captured_key.faces)
        else 0.0
    )
    key_shell_overlap_volume = (
        float(key_shell_overlap.volume)
        if len(key_shell_overlap.faces)
        else 0.0
    )
    missing_key_volume = max(
        float(clocking_key.volume) - captured_key_volume,
        0.0,
    )
    if missing_key_volume > 0.01:
        raise RuntimeError(
            "halo ring lost part of its clocking key: "
            f"{missing_key_volume:.4f} mm³ missing"
        )
    if key_shell_overlap_volume > 0.01:
        raise RuntimeError(
            "upper shell clocking groove interferes with its key: "
            f"{key_shell_overlap_volume:.4f} mm³"
        )

    lower_key = lower_clocking_key(
        lower,
        bottom_z=float(ring.bounds[0, 2]),
        skirt_source=ring,
    )
    captured_lower_key = trimesh.boolean.intersection(
        [ring, lower_key],
        engine="manifold",
    )
    lower_key_shell_overlap = trimesh.boolean.intersection(
        [lower_key, lower_solid],
        engine="manifold",
    )
    captured_lower_key_volume = (
        float(captured_lower_key.volume)
        if len(captured_lower_key.faces)
        else 0.0
    )
    lower_key_shell_overlap_volume = (
        float(lower_key_shell_overlap.volume)
        if len(lower_key_shell_overlap.faces)
        else 0.0
    )
    missing_lower_key_volume = max(
        float(lower_key.volume) - captured_lower_key_volume,
        0.0,
    )
    if missing_lower_key_volume > 0.05:
        raise RuntimeError(
            "halo ring lost part of its lower-shell clocking key: "
            f"{missing_lower_key_volume:.4f} mm³ missing"
        )
    if lower_key_shell_overlap_volume > 0.01:
        raise RuntimeError(
            "lower shell clocking groove interferes with its key: "
            f"{lower_key_shell_overlap_volume:.4f} mm³"
        )

    measured_slot = upper_solid.bounds[0, 2] - lower_solid.bounds[1, 2]
    if abs(measured_slot - cfg.HALO_GAP) > 0.05:
        raise RuntimeError(
            f"assembled halo slot is {measured_slot:.3f}, expected {cfg.HALO_GAP}"
        )
    seat_height_error = abs(float(upper_solid.bounds[0, 2]))
    if seat_height_error > 0.01:
        raise RuntimeError(
            f"upper shell base misses the ring seat plane by {seat_height_error:.3f}"
        )
    return {
        "interference_mm3": clashes,
        "assembled_slot_mm": round(float(measured_slot), 3),
        "seat_height_error_mm": round(seat_height_error, 3),
        "nominal_skirt_clearance_per_side": cfg.RING_SLIP,
        "nominal_register_clearance_per_side": cfg.RING_SLIP,
        "register_engagement_height": UPPER_REGISTER_H,
        "upper_shell_clocking": joint_clocking_report(upper),
        "lower_shell_clocking": lower_clocking_report(lower),
        "clocking_geometry_validation": {
            "key_volume_mm3": round(
                float(clocking_key.volume), 4
            ),
            "key_volume_captured_by_ring_mm3": round(
                captured_key_volume, 4
            ),
            "missing_key_volume_mm3": round(
                missing_key_volume, 6
            ),
            "key_to_grooved_shell_overlap_mm3": round(
                key_shell_overlap_volume, 6
            ),
            "lower_key_volume_mm3": round(
                float(lower_key.volume), 4
            ),
            "lower_key_volume_captured_by_ring_mm3": round(
                captured_lower_key_volume, 4
            ),
            "missing_lower_key_volume_mm3": round(
                missing_lower_key_volume, 6
            ),
            "lower_key_to_grooved_shell_overlap_mm3": round(
                lower_key_shell_overlap_volume, 6
            ),
            "passed": True,
        },
    }


def build_joint_coupons(
    lower_shell: cfg.Shell, upper_shell: cfg.Shell
) -> tuple[list[trimesh.Trimesh], dict]:
    """Build one real lower/ring/upper joint coupon set."""
    # Half a revolve sector avoids cutting exactly through existing radial
    # edges, which otherwise creates zero-area slivers after 3MF serialization.
    slice_wedge = wedge(
        -JOINT_ARC_DEG / 2.0 + COUPON_WEDGE_PHASE_DEG,
        JOINT_ARC_DEG / 2.0 + COUPON_WEDGE_PHASE_DEG,
    )

    # -- lower: the top JOINT_LOWER_H of shell A, keeping its real oblique rim
    lower_full = cut_lower_clocking_groove(
        shell_wall_solid(lower_shell),
        lower_shell,
    )
    keep_from = max(lower_shell.short_side - JOINT_LOWER_H, 0.0)
    lower = lower_full.slice_plane(
        plane_origin=(0.0, 0.0, keep_from),
        plane_normal=(0.0, 0.0, 1.0),
        cap=True,
    )
    # A 100° slice of a 1.6 mm wall is too tippy to print on its own edge.
    foot_r = lower_shell.radius_at(keep_from)
    lower = _union(
        [
            lower,
            annular_sector(
                foot_r - cfg.WALL - COUPON_FOOT_IN,
                foot_r + COUPON_FOOT_OUT,
                COUPON_FOOT_H,
                -JOINT_ARC_DEG / 2.0,
                JOINT_ARC_DEG / 2.0,
                z0=keep_from,
            ),
        ]
    )
    lower = _finish(_intersection([lower, slice_wedge]), "Boucle_Joint_Lower")
    lower.apply_translation([0.0, 0.0, -lower.bounds[0, 2]])
    lower = _serialization_safe(lower, f"{lower_shell.key} joint lower")

    # -- upper: the bottom JOINT_UPPER_H of shell B plus its internal register
    upper_full = shell_wall_solid(upper_shell)
    upper = upper_full.slice_plane(
        plane_origin=(0.0, 0.0, JOINT_UPPER_H),
        plane_normal=(0.0, 0.0, -1.0),
        cap=True,
    )
    rb_out = upper_shell.base_radius
    rb_in = rb_out - cfg.WALL
    register = annular_sector(
        rb_in - UPPER_REGISTER_W,
        # A real overlap into the shell wall avoids a 0.01 mm boolean sliver
        # collapsing into degenerate faces during 3MF serialization.
        rb_in + cfg.WALL * 0.5,
        UPPER_REGISTER_H,
        0.0,
        360.0,
        steps=SECTIONS,
    )
    upper_solid = _finish(
        _union([upper, register]),
        f"{upper_shell.key} base",
    )
    upper_solid = cut_joint_clocking_groove(
        upper_solid,
        upper_shell,
    )

    ring_full, ring_report = build_halo_ring(lower_shell, upper_shell)
    ring_report["fit"] = check_joint_fit(lower_shell, upper_shell, ring_full, upper_solid)

    upper = _finish(_intersection([upper_solid, slice_wedge]), "Boucle_Joint_Upper")
    upper.apply_translation([0.0, 0.0, -upper.bounds[0, 2]])
    upper = _serialization_safe(upper, f"{upper_shell.key} joint upper")
    ring = _finish(_intersection([ring_full, slice_wedge]), "Boucle_Halo_Ring")
    ring.apply_translation([0.0, 0.0, -ring.bounds[0, 2]])
    ring = _serialization_safe(
        ring, f"{lower_shell.key}-{upper_shell.key} halo ring"
    )

    report = {
        "coupon": f"halo joint {lower_shell.label} → {upper_shell.label}",
        "arc_deg": JOINT_ARC_DEG,
        "halo_gap": cfg.HALO_GAP,
        "slip_fit_per_side": cfg.RING_SLIP,
        "lower": {
            "source": lower_shell.key,
            "height_short_side": JOINT_LOWER_H,
            "minimum_inner_radius_at_rim": ring_report["light_window"][1],
            "oblique_rim_span": round(lower_shell.long_side - lower_shell.short_side, 2),
        },
        "ring": ring_report,
        "upper": {
            "source": upper_shell.key,
            "height": JOINT_UPPER_H,
            "base_outer_radius": round(rb_out, 2),
            "base_inner_radius": round(rb_in, 2),
            "register_width": UPPER_REGISTER_W,
            "register_height": UPPER_REGISTER_H,
            "clocking_groove": joint_clocking_report(
                upper_shell
            ),
        },
        "acceptance": (
            f"Align the ring's outward skirt tab with the open rim notch in "
            f"{lower_shell.label}, then slide the ring in by hand with a "
            f"0.25 mm/side glue gap. Align the upper tapered tab with the open "
            f"register notch, then {upper_shell.label} drops onto the seat with "
            "no rocking or binding. Clamped in its assembled orientation, the "
            "slot measures 4.0 ± 0.2 mm at three points and eye-level inspection "
            "shows shadow, not a bright ring edge."
        ),
    }
    return [lower, ring, upper], report


# --------------------------------------------------------------------------
# Base interface and LED cradle
# --------------------------------------------------------------------------


def build_shell_base_coupon(shell: cfg.Shell) -> tuple[trimesh.Trimesh, dict]:
    """A short production shell-base arc for proving the plinth bearing seat."""
    full = shell_wall_solid(shell)
    lower = full.slice_plane(
        plane_origin=(0.0, 0.0, BASE_SEAT_H),
        plane_normal=(0.0, 0.0, -1.0),
        cap=True,
    )
    arc = _finish(
        _intersection(
            [
                lower,
                wedge(
                    -BASE_SEAT_ARC_DEG / 2.0 + COUPON_WEDGE_PHASE_DEG,
                    BASE_SEAT_ARC_DEG / 2.0 + COUPON_WEDGE_PHASE_DEG,
                ),
            ]
        ),
        "Boucle_Shell_A_Base_Seat_Check",
    )
    arc.apply_translation([0.0, 0.0, -arc.bounds[0, 2]])
    arc = _serialization_safe(arc, "Boucle_Shell_A_Base_Seat_Check")
    return arc, {
        "coupon": "shell A base seat check",
        "source": shell.key,
        "arc_deg": BASE_SEAT_ARC_DEG,
        "height": BASE_SEAT_H,
        "base_outer_diameter": round(shell.base_radius * 2.0, 2),
        "base_inner_diameter": round((shell.base_radius - cfg.WALL) * 2.0, 2),
        "acceptance": (
            "On Plate 4, the arc drops into the 1.0 mm annular locate groove, "
            "then is aligned over the 6.8 mm open cable slot and bridges that "
            "local interruption without rocking, cracking or permanent "
            "deformation. After a dry fit, bond only the groove contact — never "
            "the removable cradle flange."
        ),
    }


def build_cradle_coupon() -> tuple[trimesh.Trimesh, dict]:
    body_r = cfg.CRADLE_DIA / 2.0
    flange_r = cfg.CRADLE_FLANGE_DIA / 2.0
    flange_z0 = CRADLE_COUPON_H - cfg.CRADLE_FLANGE_H
    plinth_stop_r = flange_r - cfg.PLINTH_FLANGE_STOP_W
    ramp_top_r = (
        plinth_stop_r - cfg.CRADLE_FLANGE_RAMP_CLEARANCE
    )
    ramp_angle = math.radians(cfg.CRADLE_FLANGE_RAMP_ANGLE_DEG)
    ramp_h = (ramp_top_r - body_r) / math.tan(ramp_angle)
    ramp_z0 = flange_z0 - ramp_h
    final_lip = flange_r - ramp_top_r
    if ramp_top_r <= body_r:
        raise RuntimeError("cradle flange ramp does not extend beyond the body")
    if final_lip > 1.0:
        raise RuntimeError(
            "cradle flange retains more than 1 mm unsupported overhang"
        )
    if ramp_z0 <= 0.0:
        raise RuntimeError("cradle flange ramp extends below the body")

    # One revolved profile makes the Ø93.6 body grow to within 0.8 mm of the
    # Ø99 flange at 45°. The remaining lip is the flat bearing surface that
    # lands on Plate 7's 0.6 mm stop.
    profile = np.asarray(
        [
            (0.0, 0.0),
            (body_r, 0.0),
            (body_r, ramp_z0),
            (ramp_top_r, flange_z0),
            (flange_r, flange_z0),
            (flange_r, CRADLE_COUPON_H),
            (0.0, CRADLE_COUPON_H),
            (0.0, 0.0),
        ]
    )
    solid = trimesh.creation.revolve(profile, sections=SECTIONS)

    # Grow the anti-rotation key outward at 45° within the flange's own 4 mm
    # height. It reaches full depth after 2 mm, so the existing Plate 7 notch
    # remains compatible while the first key layer has no cantilever.
    key_inner_x = -(
        flange_r - cfg.CRADLE_KEY_FLANGE_OVERLAP
    )
    key_outer_x = -(flange_r + cfg.CRADLE_KEY_DEPTH)
    key_ramp_h = cfg.CRADLE_KEY_DEPTH / math.tan(
        math.radians(cfg.CRADLE_KEY_RAMP_ANGLE_DEG)
    )
    key_full_z = flange_z0 + key_ramp_h
    if key_full_z >= CRADLE_COUPON_H:
        raise RuntimeError("anti-rotation key has no full-depth section")
    key_profile = Polygon(
        [
            (key_inner_x, flange_z0),
            (-flange_r, flange_z0),
            (key_outer_x, key_full_z),
            (key_outer_x, CRADLE_COUPON_H),
            (key_inner_x, CRADLE_COUPON_H),
        ]
    )
    key = trimesh.creation.extrude_polygon(
        key_profile,
        cfg.CRADLE_KEY_W,
    )
    key.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.pi / 2.0,
            [1.0, 0.0, 0.0],
        )
    )
    key.apply_translation([0.0, cfg.CRADLE_KEY_W / 2.0, 0.0])
    solid = _finish(_union([solid, key]), "LED cradle blank")

    pocket_floor = CRADLE_COUPON_H - cfg.LED_POCKET_DEPTH
    if pocket_floor < 3.0:
        raise RuntimeError("LED pocket leaves less than 3 mm of cradle floor")
    pocket = annular_sector(
        0.0,
        cfg.LED_POCKET_DIA / 2.0,
        cfg.LED_POCKET_DEPTH + 1.0,
        0.0,
        360.0,
        z0=pocket_floor,
        steps=SECTIONS,
    )
    cable_slot_w = cfg.LED_CABLE_W + cfg.PLINTH_CABLE_CLEARANCE
    cable_slot_h = CRADLE_COUPON_H - pocket_floor + 1.0
    channel = trimesh.creation.box(
        extents=[cfg.CRADLE_DIA, cable_slot_w, cable_slot_h]
    )
    channel.apply_translation(
        [
            cfg.CRADLE_DIA / 2.0,
            0.0,
            pocket_floor + cable_slot_h / 2.0 - 0.5,
        ]
    )

    cutters = [pocket, channel]

    mesh = _finish(_difference(solid, cutters), "Boucle_LED_Cradle_Coupon")
    mesh.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(cfg.CABLE_PHASE_DEG),
            [0.0, 0.0, 1.0],
        )
    )

    socket_phases = []
    sockets = []
    for index in range(cfg.BAFFLE_LOCATOR_COUNT):
        angle_deg = (
            cfg.BAFFLE_LOCATOR_PHASE_DEG
            + 360.0 * index / cfg.BAFFLE_LOCATOR_COUNT
        ) % 360.0
        socket_phases.append(angle_deg)
        angle = math.radians(angle_deg)
        socket = trimesh.creation.cylinder(
            radius=cfg.BAFFLE_SOCKET_DIA / 2.0,
            height=cfg.BAFFLE_SOCKET_DEPTH + 0.4,
            sections=48,
        )
        socket.apply_translation(
            [
                cfg.BAFFLE_POST_R * math.cos(angle),
                cfg.BAFFLE_POST_R * math.sin(angle),
                (
                    CRADLE_COUPON_H
                    - cfg.BAFFLE_SOCKET_DEPTH / 2.0
                    + 0.2
                ),
            ]
        )
        sockets.append(socket)

    socket_inner_web = (
        cfg.BAFFLE_POST_R
        - cfg.BAFFLE_SOCKET_DIA / 2.0
        - cfg.LED_POCKET_DIA / 2.0
    )
    socket_outer_web = (
        cfg.CRADLE_DIA / 2.0
        - cfg.BAFFLE_POST_R
        - cfg.BAFFLE_SOCKET_DIA / 2.0
    )
    cable_angle_clearance = min(
        abs(
            (
                phase
                - cfg.CABLE_PHASE_DEG
                + 180.0
            )
            % 360.0
            - 180.0
        )
        for phase in socket_phases
    )
    cable_material_margin = (
        cfg.BAFFLE_POST_R
        * math.sin(math.radians(cable_angle_clearance))
        - cable_slot_w / 2.0
        - cfg.BAFFLE_SOCKET_DIA / 2.0
    )
    installed_peg_phases = [
        (-phase) % 360.0 for phase in socket_phases
    ]
    phase_alignment_error = max(
        min(
            abs(
                (
                    peg_phase - socket_phase + 180.0
                )
                % 360.0
                - 180.0
            )
            for socket_phase in socket_phases
        )
        for peg_phase in installed_peg_phases
    )
    peg_clearance_total = (
        cfg.BAFFLE_SOCKET_DIA - cfg.BAFFLE_LOCATOR_DIA
    )
    locator_bottom_clearance = (
        cfg.BAFFLE_SOCKET_DEPTH - cfg.BAFFLE_LOCATOR_H
    )
    if socket_inner_web < 1.5:
        raise RuntimeError(
            "diffuser sockets leave inadequate LED-pocket web: "
            f"{socket_inner_web:.2f} mm"
        )
    if socket_outer_web < 3.0:
        raise RuntimeError(
            "diffuser sockets leave inadequate outer cradle web: "
            f"{socket_outer_web:.2f} mm"
        )
    if cable_material_margin < 3.0:
        raise RuntimeError(
            "diffuser socket is too close to the cable channel: "
            f"{cable_material_margin:.2f} mm"
        )
    if not 0.4 <= peg_clearance_total <= 0.8:
        raise RuntimeError(
            "diffuser locator diametral clearance is outside the "
            f"0.4–0.8 mm slip-fit gate: {peg_clearance_total:.2f} mm"
        )
    if not 0.2 <= locator_bottom_clearance <= 0.8:
        raise RuntimeError(
            "diffuser locator bottom clearance is outside the "
            f"0.2–0.8 mm gate: {locator_bottom_clearance:.2f} mm"
        )
    if phase_alignment_error > 1e-6:
        raise RuntimeError(
            "flipping the diffuser does not align its locator pegs "
            f"with the cradle sockets: {phase_alignment_error:.3f}°"
        )
    mesh = _finish(
        _difference(mesh, sockets),
        "Boucle_LED_Cradle_Coupon with diffuser sockets",
    )
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0, 2]])
    mesh = _serialization_safe(mesh, "Boucle_LED_Cradle_Coupon")

    report = {
        "coupon": "LED cradle",
        "kit": "Bambu Lab LED Lamp Kit-001 (MH001)",
        "cradle_diameter": cfg.CRADLE_DIA,
        "retaining_flange_diameter": cfg.CRADLE_FLANGE_DIA,
        "retaining_flange_height": cfg.CRADLE_FLANGE_H,
        "flange_underside_ramp": {
            "angle_deg": cfg.CRADLE_FLANGE_RAMP_ANGLE_DEG,
            "height": round(ramp_h, 2),
            "top_diameter": round(ramp_top_r * 2.0, 2),
            "final_lip": round(final_lip, 2),
            "plinth_ramp_radial_clearance": round(
                cfg.CRADLE_FLANGE_RAMP_CLEARANCE,
                2,
            ),
        },
        "anti_rotation_key": [cfg.CRADLE_KEY_DEPTH, cfg.CRADLE_KEY_W],
        "anti_rotation_key_ramp": {
            "angle_deg": cfg.CRADLE_KEY_RAMP_ANGLE_DEG,
            "height": round(key_ramp_h, 2),
            "full_depth_height": round(
                CRADLE_COUPON_H - key_full_z,
                2,
            ),
        },
        "anti_rotation_key_phase_deg": (
            cfg.CABLE_PHASE_DEG + 180.0
        ) % 360.0,
        "coupon_height": CRADLE_COUPON_H,
        "pocket_diameter": cfg.LED_POCKET_DIA,
        "pocket_depth": cfg.LED_POCKET_DEPTH,
        "pocket_floor_thickness": round(pocket_floor, 2),
        "tape_pad_diameter": cfg.LED_TAPE_DIA,
        "diffuser_locator_sockets": {
            "count": cfg.BAFFLE_LOCATOR_COUNT,
            "diameter": cfg.BAFFLE_SOCKET_DIA,
            "depth": cfg.BAFFLE_SOCKET_DEPTH,
            "peg_clearance_total": round(
                peg_clearance_total, 2
            ),
            "bottom_clearance": round(
                locator_bottom_clearance, 2
            ),
            "phases_deg": socket_phases,
            "installed_peg_phases_deg": sorted(
                installed_peg_phases
            ),
            "phase_alignment_error_deg": round(
                phase_alignment_error, 6
            ),
            "minimum_led_pocket_web": round(
                socket_inner_web, 2
            ),
            "minimum_outer_web": round(socket_outer_web, 2),
            "cable_material_margin": round(
                cable_material_margin, 2
            ),
        },
        "cable_slot": {
            "width": round(cable_slot_w, 2),
            "floor_z": round(pocket_floor, 2),
            "open_to_top": True,
            "phase_deg": cfg.CABLE_PHASE_DEG,
            "assembly": (
                "Lay the attached cable sideways into the slot while lowering "
                "the LED; never thread the switch or USB plug through the part."
            ),
        },
        "screw_mounting": {
            "generated": False,
            "reason": (
                "Hole centres and safe engagement are unmeasured. Generic radial "
                "slots would cut through the D40 tape pad, weakening the known "
                "retention method. Add real blind pilots only after measuring."
            ),
        },
        "volume_mm3": round(float(mesh.volume), 1),
        "acceptance": (
            "The measured module drops into the pocket with its light face at "
            "the intended height, the tape pad lies flat, the attached cable "
            "lays sideways into the open-top slot without pinching, and the "
            "retaining flange seats flush in the plinth gauge. All three "
            "diffuser pegs enter the blind sockets by hand, seat on their Ø6 "
            "post shoulders without rocking, and lift out without tools. Use "
            "screws only after measuring their hole spacing and safe engagement "
            "depth."
        ),
    }
    return mesh, report


def shell_a_seat_groove(shell: cfg.Shell | None = None) -> dict:
    """Annular recess that locates and bonds Shell A's base wall."""
    if shell is None:
        shells = cfg.build_stack()
        shell = next(item for item in shells if item.key == "shell_a")
    shell_inner_r = shell.base_radius - cfg.WALL
    flare_outer_r = shell.radius_at(cfg.SHELL_A_SEAT_GROOVE_DEPTH)
    flare_inner_r = flare_outer_r - cfg.WALL
    groove_outer_r = (
        max(shell.base_radius, flare_outer_r)
        + cfg.SHELL_A_SEAT_RADIAL_CLEARANCE
    )
    groove_inner_r = (
        min(shell_inner_r, flare_inner_r)
        - cfg.SHELL_A_SEAT_RADIAL_CLEARANCE
    )
    seat_r = cfg.PLINTH_TOP_SEAT_OD / 2.0
    outer_land = seat_r - groove_outer_r
    remaining_seat = cfg.PLINTH_TOP_SEAT_H - cfg.SHELL_A_SEAT_GROOVE_DEPTH
    cradle_pass_clearance = (
        2.0 * shell_inner_r - cfg.CRADLE_FLANGE_DIA
    )
    if outer_land + 1e-9 < cfg.SHELL_A_SEAT_OUTER_LAND:
        raise RuntimeError(
            "plinth top seat leaves insufficient land outside Shell A groove: "
            f"{outer_land:.2f} mm"
        )
    if groove_inner_r <= (
        cfg.CRADLE_FLANGE_DIA + cfg.CRADLE_FLANGE_FIT
    ) / 2.0:
        raise RuntimeError(
            "Shell A seat groove collides with the cradle flange recess"
        )
    if remaining_seat < 2.5:
        raise RuntimeError(
            "Shell A seat groove leaves less than 2.5 mm under the bond floor"
        )
    if cradle_pass_clearance < 4.0:
        raise RuntimeError(
            "cradle flange cannot pass through bonded Shell A: "
            f"{cradle_pass_clearance:.2f} mm total clearance"
        )
    return {
        "shell_outer_diameter": round(shell.base_radius * 2.0, 2),
        "shell_inner_diameter": round(shell_inner_r * 2.0, 2),
        "flare_outer_diameter_at_groove_top": round(flare_outer_r * 2.0, 2),
        "groove_outer_diameter": round(groove_outer_r * 2.0, 2),
        "groove_inner_diameter": round(groove_inner_r * 2.0, 2),
        "groove_depth": cfg.SHELL_A_SEAT_GROOVE_DEPTH,
        "radial_clearance_per_side": cfg.SHELL_A_SEAT_RADIAL_CLEARANCE,
        "outer_land_width": round(outer_land, 2),
        "remaining_seat_under_groove": round(remaining_seat, 2),
        "cradle_flange_pass_clearance_total": round(
            cradle_pass_clearance, 2
        ),
        "bond_target": "Shell A wall to fixed plinth seat only",
    }


def build_gauge_ring() -> tuple[trimesh.Trimesh, dict]:
    """The full plinth bore, cradle shoulder and shell-bearing top seat."""
    bore_r = cfg.PLINTH_OD / 2.0 - cfg.PLINTH_WALL
    flange_r = cfg.CRADLE_FLANGE_DIA / 2.0
    recess_r = (cfg.CRADLE_FLANGE_DIA + cfg.CRADLE_FLANGE_FIT) / 2.0
    body_r = cfg.PLINTH_OD / 2.0
    seat_r = cfg.PLINTH_TOP_SEAT_OD / 2.0
    shoulder_z = GAUGE_H - cfg.PLINTH_TOP_SEAT_H
    stop_r = flange_r - cfg.PLINTH_FLANGE_STOP_W
    ramp_angle = math.radians(cfg.PLINTH_BORE_RAMP_ANGLE_DEG)
    ramp_h = (stop_r - bore_r) / math.tan(ramp_angle)
    ramp_bottom_z = shoulder_z - ramp_h
    initial_inward_step = recess_r - stop_r
    groove = shell_a_seat_groove()
    groove_outer_r = groove["groove_outer_diameter"] / 2.0
    groove_inner_r = groove["groove_inner_diameter"] / 2.0
    groove_floor_z = GAUGE_H - cfg.SHELL_A_SEAT_GROOVE_DEPTH
    if stop_r <= bore_r:
        raise RuntimeError(
            "cradle stop must remain outside the Ø94 plinth bore"
        )
    if cfg.PLINTH_FLANGE_STOP_W < 0.4:
        raise RuntimeError("cradle flange stop is narrower than one wall line")
    if initial_inward_step > 1.0:
        raise RuntimeError(
            "inverted cradle stop has more than 1 mm unsupported overhang"
        )
    if ramp_bottom_z <= 0.0:
        raise RuntimeError("plinth bore ramp extends below the base")
    profile = np.asarray(
        [
            (bore_r, 0.0),
            (body_r, 0.0),
            (body_r, shoulder_z),
            (seat_r, shoulder_z),
            (seat_r, GAUGE_H),
            (groove_outer_r, GAUGE_H),
            (groove_outer_r, groove_floor_z),
            (groove_inner_r, groove_floor_z),
            (groove_inner_r, GAUGE_H),
            (recess_r, GAUGE_H),
            (recess_r, shoulder_z),
            (stop_r, shoulder_z),
            (bore_r, ramp_bottom_z),
            (bore_r, 0.0),
        ]
    )
    blank = trimesh.creation.revolve(profile, sections=SECTIONS)
    cable_w = cfg.LED_CABLE_W + cfg.PLINTH_CABLE_CLEARANCE
    pocket_floor = CRADLE_COUPON_H - cfg.LED_POCKET_DEPTH
    cable_h = GAUGE_H - pocket_floor + 1.0
    cable_notch = trimesh.creation.box(
        extents=[seat_r - bore_r + 6.0, cable_w, cable_h]
    )
    cable_notch.apply_translation(
        [
            (seat_r + bore_r) / 2.0,
            0.0,
            pocket_floor + cable_h / 2.0 - 0.5,
        ]
    )
    key_notch = trimesh.creation.box(
        extents=[
            cfg.CRADLE_KEY_DEPTH + cfg.CRADLE_KEY_CLEARANCE + 1.0,
            cfg.CRADLE_KEY_W + cfg.CRADLE_KEY_CLEARANCE,
            cfg.CRADLE_FLANGE_H + 0.4,
        ]
    )
    key_notch.apply_translation(
        [
            -recess_r - (cfg.CRADLE_KEY_DEPTH + cfg.CRADLE_KEY_CLEARANCE) / 2.0
            + 0.5,
            0.0,
            GAUGE_H - cfg.CRADLE_FLANGE_H / 2.0,
        ]
    )
    mesh = _finish(
        _difference(blank, [cable_notch, key_notch]),
        "Boucle_Plinth_Interface_Gauge",
    )
    mesh.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(cfg.CABLE_PHASE_DEG),
            [0.0, 0.0, 1.0],
        )
    )
    mesh = _serialization_safe(mesh, "Boucle_Plinth_Interface_Gauge")
    report = {
        "coupon": "plinth interface gauge",
        "bore_diameter": round(bore_r * 2, 2),
        "outer_diameter": cfg.PLINTH_OD,
        "top_seat_outer_diameter": cfg.PLINTH_TOP_SEAT_OD,
        "flange_recess_diameter": round(recess_r * 2.0, 2),
        "top_seat_height": cfg.PLINTH_TOP_SEAT_H,
        "shoulder_height": round(shoulder_z, 2),
        "height": GAUGE_H,
        "print_orientation": "production top seat down on the bed",
        "cradle_stop": {
            "contact_width_mm": cfg.PLINTH_FLANGE_STOP_W,
            "initial_inward_step_mm": round(initial_inward_step, 3),
            "bore_ramp_angle_deg": cfg.PLINTH_BORE_RAMP_ANGLE_DEG,
            "bore_ramp_height_mm": round(ramp_h, 3),
            "sacrificial_support": False,
        },
        "cable_notch": {
            "width": round(cable_w, 2),
            "floor_z": round(pocket_floor, 2),
            "open_to_top": True,
            "phase_deg": cfg.CABLE_PHASE_DEG,
        },
        "anti_rotation_key_clearance": cfg.CRADLE_KEY_CLEARANCE,
        "anti_rotation_key_phase_deg": (
            cfg.CABLE_PHASE_DEG + 180.0
        ) % 360.0,
        "nominal_clearance_total": cfg.CRADLE_FIT,
        "shell_a_seat_groove": groove,
        "acceptance": (
            "The cradle body enters the complete bore without binding; the "
            "outer 0.6 mm of its flange stops on the narrow shoulder and "
            "finishes flush with the top. It must lift out by hand without "
            "perceptible lateral rattle. With both open-top cable slots aligned, "
            "the attached lead drops in sideways while its switch and USB plug "
            "remain outside, without pinching. The shell A base arc drops into "
            "the 1.0 mm annular locate groove, bridges the local cable-slot "
            "interruption without rocking, and leaves the cradle flange free to "
            "pass through Shell A's opening after bonding."
        ),
    }
    return mesh, report


def check_base_interface(shell: cfg.Shell) -> dict:
    """Analytic gates for the cradle stop and shell A bearing surface."""
    bore_d = cfg.PLINTH_OD - 2.0 * cfg.PLINTH_WALL
    recess_d = cfg.CRADLE_FLANGE_DIA + cfg.CRADLE_FLANGE_FIT
    shoulder_z = GAUGE_H - cfg.PLINTH_TOP_SEAT_H
    flange_bottom = CRADLE_COUPON_H - cfg.CRADLE_FLANGE_H
    groove = shell_a_seat_groove(shell)
    groove_inner_r = groove["groove_inner_diameter"] / 2.0
    groove_outer_r = groove["groove_outer_diameter"] / 2.0
    shell_inner_r = shell.base_radius - cfg.WALL
    supported_wall = min(shell.base_radius, groove_outer_r) - max(
        shell_inner_r, groove_inner_r
    )

    result = {
        "cradle_body_clearance_total": round(bore_d - cfg.CRADLE_DIA, 3),
        "cradle_flange_clearance_total": round(
            recess_d - cfg.CRADLE_FLANGE_DIA, 3
        ),
        "cradle_flange_stop_width": cfg.PLINTH_FLANGE_STOP_W,
        "bore_ramp_angle_deg": cfg.PLINTH_BORE_RAMP_ANGLE_DEG,
        "shoulder_to_flange_vertical_error": round(shoulder_z - flange_bottom, 3),
        "shell_wall_supported_width": round(supported_wall, 3),
        "shell_wall_width": cfg.WALL,
        "shell_a_seat_groove": groove,
        "local_cable_slot_bridge_span": round(
            cfg.LED_CABLE_W + cfg.PLINTH_CABLE_CLEARANCE, 3
        ),
        "anti_rotation_key_clearance": cfg.CRADLE_KEY_CLEARANCE,
    }
    if result["cradle_body_clearance_total"] < 0.2:
        raise RuntimeError(f"cradle body has inadequate clearance: {result}")
    if result["cradle_flange_clearance_total"] < 0.2:
        raise RuntimeError(f"cradle flange has inadequate clearance: {result}")
    if result["cradle_flange_stop_width"] < 0.4:
        raise RuntimeError(f"cradle flange stop is too narrow: {result}")
    if abs(result["shoulder_to_flange_vertical_error"]) > 0.05:
        raise RuntimeError(f"cradle flange cannot finish flush: {result}")
    if supported_wall < cfg.WALL - 0.05:
        raise RuntimeError(f"plinth does not support the full shell wall: {result}")
    if result["local_cable_slot_bridge_span"] > 8.0:
        raise RuntimeError(f"shell cable-slot bridge is too wide: {result}")
    return result


def build_leg_frame() -> tuple[trimesh.Trimesh, dict]:
    """Production plinth and three embedded legs in assembled orientation."""
    plinth, plinth_report = build_gauge_ring()
    plinth.apply_translation([0.0, 0.0, cfg.PLINTH_Z0])
    parts = [plinth]

    foot = np.array([cfg.LEG_FOOT_R, 0.0, 0.0])
    embedded_top = np.array(
        [cfg.LEG_EMBED_R, 0.0, cfg.LEG_EMBED_Z]
    )
    axis = embedded_top - foot
    length = float(np.linalg.norm(axis))
    overrun = 8.0
    profile = np.asarray(
        [
            (0.0, 0.0),
            (cfg.LEG_FOOT_DIA / 2.0, 0.0),
            (cfg.LEG_TOP_DIA / 2.0, length + overrun),
            (0.0, length + overrun),
            (0.0, 0.0),
        ]
    )
    leg = trimesh.creation.revolve(profile, sections=48)
    leg.apply_translation([0.0, 0.0, -overrun])
    align = trimesh.geometry.align_vectors(
        [0.0, 0.0, 1.0], axis / length
    )
    leg.apply_transform(align)
    leg.apply_translation(foot)

    bore_r = (
        cfg.PLINTH_OD / 2.0
        - cfg.PLINTH_WALL
        + cfg.LEG_BORE_GAP
    )
    bore_z0 = cfg.PLINTH_Z0 - 0.2
    bore_z1 = cfg.PLINTH_Z1
    bore = trimesh.creation.cylinder(
        radius=bore_r,
        height=bore_z1 - bore_z0,
        sections=SECTIONS,
    )
    bore.apply_translation(
        [0.0, 0.0, (bore_z0 + bore_z1) / 2.0]
    )
    leg = _difference(leg, [bore])

    leg_phases = []
    for index in range(cfg.LEG_COUNT):
        phase = (
            cfg.LEG_PHASE_DEG
            + 360.0 * index / cfg.LEG_COUNT
        ) % 360.0
        leg_phases.append(phase)
        spun = leg.copy()
        spun.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(phase),
                [0.0, 0.0, 1.0],
            )
        )
        parts.append(spun)

    frame = _union(parts)
    keep_above_floor = trimesh.creation.box(
        extents=[400.0, 400.0, 200.0]
    )
    keep_above_floor.apply_translation([0.0, 0.0, 100.0])
    frame = _finish(
        _intersection([frame, keep_above_floor]),
        "Boucle plinth and embedded leg frame",
    )
    if len(frame.split(only_watertight=False)) != 1:
        raise RuntimeError("leg frame is not one connected body")
    frame = _serialization_safe(
        frame, "Boucle plinth and embedded leg frame"
    )
    attachment_r = cfg.PLINTH_OD / 2.0
    leg_half_angle = math.degrees(
        math.asin(
            (cfg.LEG_TOP_DIA / 2.0) / attachment_r
        )
    )
    cable_half_angle = math.degrees(
        math.asin(
            (
                cfg.LED_CABLE_W
                + cfg.PLINTH_CABLE_CLEARANCE
            )
            / 2.0
            / attachment_r
        )
    )
    angular_material_margin = (
        cfg.CABLE_REAR_LEG_OFFSET_DEG
        - leg_half_angle
        - cable_half_angle
    )
    if angular_material_margin < 5.0:
        raise RuntimeError(
            "cable notch is too close to the rear leg joint: "
            f"{angular_material_margin:.2f}° material margin"
        )
    return frame, {
        "part": "plinth and leg frame",
        "assembled_orientation": "feet on floor",
        "print_orientation": "top seat on bed, legs upward",
        "connected_components": 1,
        "cradle_stop": plinth_report["cradle_stop"],
        "top_seat_height": cfg.PLINTH_TOP_SEAT_H,
        "leg_phases_deg": leg_phases,
        "front_leg_phases_deg": [
            leg_phases[1],
            leg_phases[2],
        ],
        "cable_phase_deg": cfg.CABLE_PHASE_DEG,
        "rear_leg_phase_deg": leg_phases[0],
        "cable_to_rear_leg_deg": (
            cfg.CABLE_REAR_LEG_OFFSET_DEG
        ),
        "front_open_midpoint_deg": (
            cfg.LEG_PHASE_DEG + 180.0
        ) % 360.0,
        "angular_material_margin_deg": round(
            angular_material_margin, 2
        ),
        "cradle_bore_clearance_mm": cfg.LEG_BORE_GAP,
        "volume_cm3": round(float(frame.volume) / 1000.0, 2),
    }


# --------------------------------------------------------------------------
# Print profiles and 3MF packaging — Bambu Lab P2S, 0.4 mm, Bambu PLA Matte
# --------------------------------------------------------------------------

# Nothing in this project has an overhang past 45°, so support is off
# everywhere; every part stands on a narrow footprint, so brim is on.
COMMON_PROFILE = {
    "enable_support": "0",
    "wall_generator": "classic",
    "precise_outer_wall": "1",
    "detect_thin_wall": "1",
    "brim_type": "outer_only",
    "brim_width": "5",
    "fuzzy_skin": "none",
    "fuzzy_skin_first_layer": "0",
    "seam_position": "aligned",
}

# Shell arcs. Arachne varies bead width to fill the modelled 1.2 / 1.6 / 2.0 mm
# walls without the Classic generator's near-continuous gap infill. The 0.40 mm
# target width remains the production baseline, but the physical caliper and
# light result—not an assumed exact bead count—is the acceptance gate.
SHELL_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "outer_wall_line_width": "0.40",
    "inner_wall_line_width": "0.40",
    "wall_loops": "6",
    "sparse_infill_density": "10%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "4",
    "bottom_shell_layers": "3",
    "outer_wall_speed": "80",
    "inner_wall_speed": "120",
    "small_perimeter_speed": "100%",
    "seam_position": "random",
    "fuzzy_skin_thickness": "0.30",
    "fuzzy_skin_point_distance": "0.80",
}

BAFFLE_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.20",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "outer_wall_speed": "100",
    "inner_wall_speed": "160",
}

# The ring is a fit part, not a lit one: finer layers for the 45° seat and the
# slip surfaces, and speed matters more than surface evenness.
RING_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.16",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "3",
    "outer_wall_speed": "120",
    "inner_wall_speed": "200",
}

# Base parts never show. Ironed top surfaces so the LED module's tape pad has
# something flat to stick to.
BASE_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.20",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "3",
    "top_surface_pattern": "monotonic",
    "bottom_surface_pattern": "monotonic",
    "ironing_type": "top",
    "outer_wall_speed": "150",
    "inner_wall_speed": "250",
    "brim_type": "auto_brim",
}

GAUGE_PROFILE = BASE_PROFILE | {
    # The gauge prints with its production top seat on the bed. Ironing the
    # opposite face adds time but cannot improve either measured interface.
    "ironing_type": "no ironing",
}


@dataclass(frozen=True)
class Part:
    label: str
    filename: str
    extruder: int
    profile: dict
    plate: int
    dx: float = 0.0
    dy: float = 0.0


# Bed offsets are relative to the centre of that plate's cell in the 312 mm grid.
PLATES = [
    (1, "Glow wall and diffuser baffle"),
    (2, "A to B halo and base seat"),
    (3, "B to C halo"),
    (4, "LED and plinth interface"),
]

# The joint arcs are ~110 mm across their chord and only ~35 mm deep, so they
# stand side by side across the bed rather than stacked front to back.
PARTS = [
    Part("Glow wall coupon", "boucle_glow_coupon.stl", 1, SHELL_PROFILE, 1),
    Part(
        "LED diffuser baffle",
        "boucle_led_baffle.stl",
        1,
        BAFFLE_PROFILE,
        1,
        dx=80.0,
    ),
    Part("A-B · Shell A rim", "boucle_joint_ab_lower.stl", 1, SHELL_PROFILE, 2, dx=-60.0),
    Part("A-B · Halo ring", "boucle_joint_ab_ring.stl", 1, RING_PROFILE, 2),
    Part("A-B · Shell B base", "boucle_joint_ab_upper.stl", 1, SHELL_PROFILE, 2, dx=60.0),
    Part(
        "Shell A base seat check",
        "boucle_shell_a_base_seat.stl",
        1,
        SHELL_PROFILE,
        2,
        dy=-95.0,
    ),
    Part("B-C · Shell B rim", "boucle_joint_bc_lower.stl", 1, SHELL_PROFILE, 3, dx=-60.0),
    Part("B-C · Halo ring", "boucle_joint_bc_ring.stl", 1, RING_PROFILE, 3),
    Part("B-C · Shell C base", "boucle_joint_bc_upper.stl", 1, SHELL_PROFILE, 3, dx=60.0),
    Part("LED cradle", "boucle_led_cradle_coupon.stl", 2, BASE_PROFILE, 4, dx=-60.0),
    Part(
        "Plinth interface gauge",
        "boucle_plinth_interface_gauge.stl",
        2,
        GAUGE_PROFILE,
        4,
        dx=60.0,
    ),
]


BED = 256.0
PLATE_PITCH = 312.0
PLATE_COLUMNS = 2


def plate_position(part: Part) -> tuple[float, float, float]:
    """Bed coordinates for a part.

    Studio lays plates out on a two-column grid — plate 3 sits *below* plate 1,
    not to the right of plate 2. Putting it in a third column drops the parts
    into a phantom cell and the plate slices empty.
    """
    column = (part.plate - 1) % PLATE_COLUMNS
    row = (part.plate - 1) // PLATE_COLUMNS
    return (
        BED / 2.0 + PLATE_PITCH * column + part.dx,
        BED / 2.0 - PLATE_PITCH * row + part.dy,
        0.0,
    )


def validate_layout(meshes: list[trimesh.Trimesh], margin: float = 6.0) -> None:
    """Every part must sit on its own plate, clear of the edges and neighbours.

    `margin` covers the 5 mm brim.
    """
    boxes: dict[int, list[tuple[str, np.ndarray]]] = {}
    for part, mesh in zip(PARTS, meshes):
        x, y, _z = plate_position(part)
        low, high = mesh.bounds
        if high[2] - low[2] > BED:
            raise ValueError(f"{part.label} is taller than the P2S build volume")

        origin_x = BED / 2.0 + PLATE_PITCH * ((part.plate - 1) % PLATE_COLUMNS)
        origin_y = BED / 2.0 - PLATE_PITCH * ((part.plate - 1) // PLATE_COLUMNS)
        box = np.array(
            [
                [x + low[0] - margin, y + low[1] - margin],
                [x + high[0] + margin, y + high[1] + margin],
            ]
        )
        if (
            box[0, 0] < origin_x - BED / 2.0
            or box[1, 0] > origin_x + BED / 2.0
            or box[0, 1] < origin_y - BED / 2.0
            or box[1, 1] > origin_y + BED / 2.0
        ):
            raise ValueError(f"{part.label} hangs off plate {part.plate}")
        boxes.setdefault(part.plate, []).append((part.label, box))

    for plate, entries in boxes.items():
        for i, (label_a, a) in enumerate(entries):
            for label_b, b in entries[i + 1 :]:
                if (
                    a[0, 0] < b[1, 0]
                    and b[0, 0] < a[1, 0]
                    and a[0, 1] < b[1, 1]
                    and b[0, 1] < a[1, 1]
                ):
                    raise ValueError(
                        f"plate {plate}: {label_a} and {label_b} overlap on the bed"
                    )


def plate_preview_png(
    plate_number: int,
    plate_label: str,
    meshes: list[trimesh.Trimesh],
    shell_hex: str,
    base_hex: str,
) -> bytes:
    """Simple truthful top view for Studio's plate browser."""
    size = 512
    inset = 28
    scale = (size - 2 * inset) / BED
    image = Image.new("RGB", (size, size), "#E9EBE8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (inset, inset, size - inset, size - inset),
        radius=10,
        fill="#5D6362",
        outline="#252C29",
        width=3,
    )
    for grid in range(0, int(BED) + 1, 20):
        at = inset + grid * scale
        draw.line((at, inset, at, size - inset), fill="#6B7270", width=1)
        draw.line((inset, at, size - inset, at), fill="#6B7270", width=1)

    for part, mesh in zip(PARTS, meshes):
        if part.plate != plate_number:
            continue
        hull = MultiPoint(mesh.vertices[:, :2]).convex_hull
        x, y, _z = plate_position(part)
        origin_x = BED / 2.0 + PLATE_PITCH * ((plate_number - 1) % PLATE_COLUMNS)
        origin_y = BED / 2.0 - PLATE_PITCH * ((plate_number - 1) // PLATE_COLUMNS)
        local_x = x - origin_x + BED / 2.0
        local_y = y - origin_y + BED / 2.0
        points = [
            (
                inset + (local_x + px) * scale,
                size - inset - (local_y + py) * scale,
            )
            for px, py in hull.exterior.coords
        ]
        colour = shell_hex if part.extruder == 1 else base_hex
        draw.polygon(points, fill=colour, outline="#252C29", width=2)

    draw.rectangle((0, 0, size, 23), fill="#252C29")
    draw.text((10, 5), f"Plate {plate_number} · {plate_label}", fill="#FFFFFF")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def validate_serialized_project(package: zipfile.ZipFile, object_count: int) -> None:
    """Reload child meshes exactly as written and reject repair-dependent 3MFs."""
    namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    production = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
    top = ET.fromstring(package.read("3D/3dmodel.model"))
    top_objects = top.findall("./m:resources/m:object", namespace)
    build_items = top.findall("./m:build/m:item", namespace)
    if len(top_objects) != object_count or len(build_items) != object_count:
        raise RuntimeError("top-level object/build count does not match coupon parts")
    top_ids = {node.get("id") for node in top_objects}
    for index, node in enumerate(top_objects, start=1):
        components = node.findall("./m:components/m:component", namespace)
        expected_path = f"/3D/Objects/object_{index}.model"
        if (
            len(components) != 1
            or components[0].get(f"{{{production}}}path") != expected_path
            or components[0].get("objectid") != str(index)
        ):
            raise RuntimeError(f"invalid component reference for object {index}")
    if {item.get("objectid") for item in build_items} != top_ids:
        raise RuntimeError("build items do not resolve to every top-level object")

    settings = ET.fromstring(package.read("Metadata/model_settings.config"))
    settings_ids = {node.get("id") for node in settings.findall("./object")}
    plate_ids = {
        metadata.get("value")
        for metadata in settings.findall("./plate/model_instance/metadata")
        if metadata.get("key") == "object_id"
    }
    assemble_ids = {
        item.get("object_id") for item in settings.findall("./assemble/assemble_item")
    }
    if settings_ids != top_ids or plate_ids != top_ids or assemble_ids != top_ids:
        raise RuntimeError("model settings contain unresolved object references")
    if len(settings.findall("./plate")) != len(PLATES):
        raise RuntimeError("model settings plate count does not match PLATES")

    uuids = [
        value
        for element in top.iter()
        for key, value in element.attrib.items()
        if key.endswith("UUID")
    ]
    if len(uuids) != len(set(uuids)):
        raise RuntimeError("duplicate UUID in top-level 3MF model")

    for index in range(1, object_count + 1):
        root = ET.fromstring(package.read(f"3D/Objects/object_{index}.model"))
        vertices = np.asarray(
            [
                [float(vertex.get(axis)) for axis in ("x", "y", "z")]
                for vertex in root.findall(".//m:vertex", namespace)
            ]
        )
        faces = np.asarray(
            [
                [int(triangle.get(key)) for key in ("v1", "v2", "v3")]
                for triangle in root.findall(".//m:triangle", namespace)
            ]
        )
        if np.any(
            (faces[:, 0] == faces[:, 1])
            | (faces[:, 1] == faces[:, 2])
            | (faces[:, 2] == faces[:, 0])
        ):
            raise RuntimeError(f"object_{index}.model contains repeated-index faces")
        areas = np.linalg.norm(
            np.cross(
                vertices[faces[:, 1]] - vertices[faces[:, 0]],
                vertices[faces[:, 2]] - vertices[faces[:, 0]],
            ),
            axis=1,
        )
        if float(areas.min()) <= 1e-10:
            raise RuntimeError(f"object_{index}.model contains zero-area faces")
        reloaded = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        reloaded.merge_vertices(digits_vertex=8)
        reloaded.remove_unreferenced_vertices()
        if not reloaded.is_watertight or not reloaded.is_volume:
            raise RuntimeError(
                f"object_{index}.model is not watertight after 3MF serialization"
            )


def _model_settings(meshes) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for index, (part, mesh) in enumerate(zip(PARTS, meshes), start=1):
        overrides = dict(part.profile)
        top_id = 99 + index
        lines.extend(
            [
                f'  <object id="{top_id}">',
                f'    <metadata key="name" value="{escape(part.label)}"/>',
                f'    <metadata key="extruder" value="{part.extruder}"/>',
                *[
                    f'    <metadata key="{key}" value="{value}"/>'
                    for key, value in overrides.items()
                ],
                f'    <metadata face_count="{len(mesh.faces)}"/>',
                f'    <part id="{index}" subtype="normal_part">',
                f'      <metadata key="name" value="{escape(part.label)}"/>',
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'      <metadata key="source_object_id" value="{index - 1}"/>',
                f'      <metadata key="source_volume_id" value="{index - 1}"/>',
                f'      <metadata key="extruder" value="{part.extruder}"/>',
                f'      <mesh_stat face_count="{len(mesh.faces)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                "    </part>",
                "  </object>",
            ]
        )

    for plate_number, plate_label in PLATES:
        lines.extend(
            [
                "  <plate>",
                f'    <metadata key="plater_id" value="{plate_number}"/>',
                f'    <metadata key="plater_name" value="{escape(plate_label)}"/>',
                '    <metadata key="locked" value="false"/>',
                '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
                f'    <metadata key="thumbnail_file" value="Metadata/plate_{plate_number}.png"/>',
                f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{plate_number}.png"/>',
                f'    <metadata key="top_file" value="Metadata/top_{plate_number}.png"/>',
                f'    <metadata key="pick_file" value="Metadata/pick_{plate_number}.png"/>',
            ]
        )
        for index, part in enumerate(PARTS, start=1):
            if part.plate != plate_number:
                continue
            lines.extend(
                [
                    "    <model_instance>",
                    f'      <metadata key="object_id" value="{99 + index}"/>',
                    '      <metadata key="instance_id" value="0"/>',
                    f'      <metadata key="identify_id" value="{299 + index}"/>',
                    "    </model_instance>",
                ]
            )
        lines.append("  </plate>")

    lines.append("  <assemble>")
    for index in range(1, len(PARTS) + 1):
        lines.append(
            f'    <assemble_item object_id="{99 + index}" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def build_coupon_project(
    *,
    mesh_dir: Path,
    meshes: list[trimesh.Trimesh],
    output_path: Path,
    paint_masks: dict[int, np.ndarray],
    shell_hex: str,
    base_hex: str,
) -> Path:
    """Package the coupons.

    Meshes are passed in memory rather than reloaded from the exported STLs:
    STL stores unwelded triangles, and welding them on load would break the
    face-index alignment the fuzzy paint mask depends on.
    """
    bambu.OBJECTS = [
        (part.label, mesh_dir / part.filename, part.extruder) for part in PARTS
    ]
    bambu.BUILD_POSITIONS = [plate_position(part) for part in PARTS]

    for part, mesh in zip(PARTS, meshes):
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold coupon: {part.label}")
    validate_layout(meshes)

    template_path = assets.BLANK_PROJECT
    with (
        zipfile.ZipFile(template_path) as template,
        zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr(
            "3D/3dmodel.model",
            bambu.top_model().replace(
                b"<metadata name=\"Title\">Cooper Paw-Lattice Bowl</metadata>",
                b"<metadata name=\"Title\">Boucl\xc3\xa9 Stack lamp \xe2\x80\x94 physical gate coupons</metadata>",
            ),
        )
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(mesh, index, paint_fuzzy=paint_masks.get(index)),
            )
        output.writestr("Metadata/model_settings.config", _model_settings(meshes))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        # Project level is the fallback for anything an object does not override.
        # Several of these keys are per-filament arrays in the P2S profile, so
        # match the template's shape rather than dropping a bare string in.
        for key, value in SHELL_PROFILE.items():
            current = settings.get(key)
            settings[key] = [value] * len(current) if isinstance(current, list) else value
        settings["filament_colour"] = [shell_hex, base_hex]
        settings["default_filament_colour"] = ["", ""]
        # Stock Bambu Matte profile for both slots. Custom "@Ogma <colour>"
        # names are phantom presets: Studio cannot resolve them and silently
        # loses the real temperature, flow and flush values.
        settings["filament_settings_id"] = ["Bambu PLA Matte @BBL P2S"] * 2
        # Every plate is single-filament, so a prime tower would only waste
        # material and steal bed space.
        settings["enable_prime_tower"] = "0"
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))

        for plate_number, label in PLATES:
            preview = plate_preview_png(
                plate_number, label, meshes, shell_hex, base_hex
            )
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview,
                )

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
        validate_serialized_project(package, len(meshes))
    return output_path


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def generate_coupons(job_dir: Path) -> Path:
    job_dir = Path(job_dir)
    mesh_dir = job_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    # This directory is generated output. Remove obsolete coupon names so a
    # revised package cannot ship stale STLs beside the current report.
    for stale in mesh_dir.glob("*.stl"):
        stale.unlink()

    shells = cfg.build_stack()

    glow, glow_paint, glow_report = build_glow_coupon()
    baffle, baffle_report = build_baffle()
    (ab_lower, ab_ring, ab_upper), ab_joint_report = build_joint_coupons(
        shells[0], shells[1]
    )
    shell_base, shell_base_report = build_shell_base_coupon(shells[0])
    (bc_lower, bc_ring, bc_upper), bc_joint_report = build_joint_coupons(
        shells[1], shells[2]
    )
    cradle, cradle_report = build_cradle_coupon()
    gauge, gauge_report = build_gauge_ring()
    gauge_report["interface_validation"] = check_base_interface(shells[0])
    # The production leg frame prints inverted with this top seat on the bed.
    # Match that orientation so the measured cradle recess and shell seat see
    # the same first-layer behaviour as the final part.
    gauge.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0])
    )
    gauge.apply_translation([0.0, 0.0, -gauge.bounds[0, 2]])

    by_file = {
        "boucle_glow_coupon.stl": glow,
        "boucle_led_baffle.stl": baffle,
        "boucle_joint_ab_lower.stl": ab_lower,
        "boucle_joint_ab_ring.stl": ab_ring,
        "boucle_joint_ab_upper.stl": ab_upper,
        "boucle_shell_a_base_seat.stl": shell_base,
        "boucle_joint_bc_lower.stl": bc_lower,
        "boucle_joint_bc_ring.stl": bc_ring,
        "boucle_joint_bc_upper.stl": bc_upper,
        "boucle_led_cradle_coupon.stl": cradle,
        "boucle_plinth_interface_gauge.stl": gauge,
    }
    # Centre every part on its own footprint so the plate offsets mean what
    # they say; face order — and so the paint mask — is untouched.
    for mesh in by_file.values():
        low, high = mesh.bounds
        mesh.apply_translation([-(low[0] + high[0]) / 2.0, -(low[1] + high[1]) / 2.0, 0.0])
    for filename, mesh in by_file.items():
        path = mesh_dir / filename
        mesh.export(path)
        reloaded = trimesh.load_mesh(path, process=True)
        if (
            not isinstance(reloaded, trimesh.Trimesh)
            or not reloaded.is_watertight
            or not reloaded.is_volume
            or len(reloaded.split(only_watertight=False)) != 1
        ):
            raise RuntimeError(f"serialized STL is not one watertight volume: {path}")
    ordered = [by_file[part.filename] for part in PARTS]

    report = {
        "project": "Bouclé Stack table lamp — physical gate coupons",
        "units": "mm",
        "shell_filament": SHELL_FILAMENT,
        "base_filament": BASE_FILAMENT,
        "wall": cfg.WALL,
        "stack": [
            {
                "key": sh.key,
                "base_diameter": round(sh.base_radius * 2, 2),
                "widest_diameter": round(sh.max_radius * 2, 2),
                "rim_diameter": round(sh.rim_half * 2, 2),
                "lean_deg": round(sh.axis_deg, 2),
                "local_cut_deg": round(sh.local_cut()[0], 2),
                "print_draft_deg": round(sh.as_printed().draft_deg, 2),
            }
            for sh in shells
        ],
        "overall_height": round(cfg.overall_height(shells), 2),
        "widest_diameter": round(cfg.widest_diameter(shells), 2),
        "printer": "Bambu Lab P2S, 0.4 mm nozzle, Bambu PLA Matte",
        "stability": {
            "status": "not qualified by geometry alone",
            "foot_centre_radius": cfg.LEG_FOOT_R,
            "support_polygon": "triangle through the three real foot contact patches",
            "warning": (
                "The 78 mm foot-centre radius is a circumradius, not a tipping "
                "boundary. Use sliced masses, upper-stack mass dummies and a "
                "10-degree board test in every orientation."
            ),
        },
        "thermal": {
            "status": "physical test required",
            "maximum_allowed_pla_surface_c": 45,
            "shell_a_test_hours": 8,
            "complete_burn_in_hours": 24,
        },
        "plates": [
            {
                "plate": number,
                "name": label,
                "filament": SHELL_FILAMENT if number != 4 else BASE_FILAMENT,
                "parts": [
                    {
                        "name": part.label,
                        "layer_height": part.profile["layer_height"],
                        "wall_loops": part.profile["wall_loops"],
                        "ams_slot": part.extruder,
                    }
                    for part in PARTS
                    if part.plate == number
                ],
            }
            for number, label in PLATES
        ],
        "hardware_preflight": {
            "required_before_plate_4": [
                "Measure the actual module against the D60 x H8 design envelope.",
                "Measure screw-hole centre spacing and module thickness under each screw head.",
                "Confirm the attached lead and strain relief lay sideways into the 6.8 mm open-top slots; the switch and USB stay outside.",
            ],
            "configured_module_diameter": cfg.LED_DIA,
            "configured_module_height": cfg.LED_HEIGHT,
        },
        "print_and_test_sequence": [
            {
                "stage": 0,
                "print": "none",
                "gate": (
                    "Measure the actual MH001 diameter, height, screw spacing, "
                    "screw-head stack and cable envelope. Do not print Plate 4 "
                    "unless they match the configured dimensions."
                ),
            },
            {
                "stage": 1,
                "print": "Plate 1 only — Glow wall and production diffuser baffle",
                "gate": (
                    "Measure each smooth wall at three points (target ±0.15 mm). "
                    "Using the same LED, distance and dark-room exposure, choose "
                    "the thinnest sector with even light and no pinholes visible "
                    "from 300 mm. If the winner is not 1.6 mm, change WALL and "
                    "regenerate every later plate."
                ),
            },
            {
                "stage": 2,
                "print": "Plate 2 — A→B halo and shell/base seat arc",
                "gate": (
                    "Dry-fit without force or rocking; verify the slot is "
                    "4.0 ±0.2 mm at three points and the ring is hidden at eye "
                    "level. After Plate 4, align the base arc over the local "
                    "cable-slot interruption and verify it bridges without "
                    "rocking or damage."
                ),
            },
            {
                "stage": 3,
                "print": "Plate 3 — B→C halo",
                "gate": (
                    "Repeat the complete fit and slot checks. This joint has a "
                    "different local cut, radius and ring and cannot inherit the "
                    "A→B result."
                ),
            },
            {
                "stage": 4,
                "print": "Plate 4 — LED cradle and plinth interface",
                "gate": (
                    "Cradle enters the full 28 mm bore by hand, is stopped by "
                    "its flange, finishes flush within 0.3 mm, has no obvious "
                    "rattle, and lifts out. Lower the actual module while laying "
                    "its attached lead sideways into both open-top slots; the "
                    "switch and USB remain outside and the lead is not pinched. "
                    "Do not use screws until safe engagement has been measured."
                ),
            },
            {
                "stage": 5,
                "print": "none — bonded coupon proof",
                "gate": (
                    "Bond the less favourable halo coupon with the intended "
                    "adhesive, cure for the maker's full stated time, then apply "
                    "a 500 g lateral load for 60 seconds. No separation, crack "
                    "or permanent slot change greater than 0.2 mm."
                ),
            },
            {
                "stage": 6,
                "print": "base, cradle, baffle and Shell A only",
                "gate": (
                    "Run the LED for eight hours and keep every measured PLA "
                    "surface below 45°C. Then place mass dummies equal to the "
                    "sliced B/C/ring masses at their assembled centres and pass "
                    "a 10° board test in every orientation before printing B/C."
                ),
            },
            {
                "stage": 7,
                "print": "complete lamp",
                "gate": (
                    "Pass a 24-hour powered burn-in plus repeated glare, cable "
                    "temperature and stability checks with no smell, softening, "
                    "colour change or cable heating."
                ),
            },
        ],
        "coupons": [
            glow_report,
            baffle_report,
            ab_joint_report,
            shell_base_report,
            bc_joint_report,
            cradle_report,
            gauge_report,
        ],
    }
    (job_dir / "dimensions_and_acceptance.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    palette = load_palette()
    shell_f = resolve_filament(SHELL_FILAMENT, palette)
    base_f = resolve_filament(BASE_FILAMENT, palette)
    output = job_dir / "Boucle_Stack_Lamp_Coupons_P2S.3mf"
    build_coupon_project(
        mesh_dir=mesh_dir,
        meshes=ordered,
        output_path=output,
        paint_masks={1: glow_paint},
        shell_hex=shell_f.hex,
        base_hex=base_f.hex,
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the Bouclé Stack lamp coupons")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(generate_coupons(args.out))
