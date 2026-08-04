#!/usr/bin/env python3
"""Mesh builders for the Golf Tee LED lamp.

Produces the dimpled two-part ball, the tee with MH001 cradle seat, and
re-exports the proven Bouclé cradle / diffuser so hardware stays identical.

Run smoke checks from the repository root:

    .venv/bin/python -c "from golf_tee_lamp_geometry import smoke; smoke()"
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import manifold3d
import numpy as np
import trimesh

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import boucle_lamp_coupons as boucle  # noqa: E402
import golf_tee_lamp_config as cfg  # noqa: E402

SECTIONS = 192
# Subdiv 5 (~10k verts) resolves ~5 mm dimples on Ø175 without huge files.
SPHERE_SUBDIV = 5
SPHERE_SUBDIV_FAST = 4


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
    working = trimesh.Trimesh(
        vertices=np.round(mesh.vertices, 8), faces=mesh.faces, process=False
    )
    working.merge_vertices(digits_vertex=8)
    source = manifold3d.Mesh(
        vert_properties=working.vertices.astype(np.float32),
        tri_verts=working.faces.astype(np.uint32),
        tolerance=1e-6,
    )
    repaired = manifold3d.Manifold(source)
    if repaired.status() != manifold3d.Error.NoError:
        raise RuntimeError(
            f"{name} cannot be reconstructed at serialization precision: "
            f"{repaired.status()}"
        )
    emitted = repaired.simplify(1e-6).to_mesh64()
    cleaned = trimesh.Trimesh(
        vertices=np.round(np.asarray(emitted.vert_properties)[:, :3], 8),
        faces=np.asarray(emitted.tri_verts),
        process=False,
    )
    return _finish(cleaned, name)


def _union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.union(meshes, engine="manifold")


def _difference(mesh: trimesh.Trimesh, cutters: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.difference([mesh, *cutters], engine="manifold")


def _intersection(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.intersection(meshes, engine="manifold")


# --------------------------------------------------------------------------
# Shared hardware — identical to Bouclé production parts
# --------------------------------------------------------------------------


def build_cradle() -> tuple[trimesh.Trimesh, dict]:
    """Proven MH001 cradle; dimensions must stay locked to Bouclé."""
    mesh, report = boucle.build_cradle_coupon()
    report = dict(report)
    report["shared_with"] = "boucle_lamp_coupons.build_cradle_coupon"
    return mesh, report


def build_baffle() -> tuple[trimesh.Trimesh, dict]:
    mesh, report = boucle.build_baffle()
    report = dict(report)
    report["shared_with"] = "boucle_lamp_coupons.build_baffle"
    return mesh, report


# --------------------------------------------------------------------------
# Dimpled golf ball — constant-thickness dual-surface displacement
# --------------------------------------------------------------------------


def _unit_icosphere(subdiv: int) -> tuple[np.ndarray, np.ndarray]:
    sphere = trimesh.creation.icosphere(subdivisions=subdiv, radius=1.0)
    dirs = np.asarray(sphere.vertices, dtype=np.float64)
    norms = np.linalg.norm(dirs, axis=1, keepdims=True)
    dirs = dirs / np.maximum(norms, 1e-12)
    return dirs, np.asarray(sphere.faces)


def _displaced_shell(
    centers: np.ndarray, subdiv: int = SPHERE_SUBDIV
) -> trimesh.Trimesh:
    """Outer and inner surfaces share the same dimple field → constant wall t."""
    dirs, faces = _unit_icosphere(subdiv)
    depths = cfg.dimple_depth_field(dirs, centers)
    outer = trimesh.Trimesh(
        vertices=dirs * (cfg.BALL_R - depths)[:, None],
        faces=faces,
        process=False,
    )
    inner = trimesh.Trimesh(
        vertices=dirs * (cfg.BALL_INNER_R - depths)[:, None],
        faces=faces,
        process=False,
    )
    return _difference(outer, [inner])


def _sphere_shell(outer_r: float, inner_r: float, subdiv: int = SPHERE_SUBDIV) -> trimesh.Trimesh:
    outer = trimesh.creation.icosphere(subdivisions=subdiv, radius=outer_r)
    inner = trimesh.creation.icosphere(subdivisions=subdiv, radius=inner_r)
    return _difference(outer, [inner])


def _opening_cutter() -> trimesh.Trimesh:
    """Cylinder that opens the south pole for the tee seat."""
    height = abs(cfg.BALL_OPENING_Z) + 8.0
    cutter = trimesh.creation.cylinder(
        radius=cfg.BALL_OPENING_R + 0.05,
        height=height,
        sections=SECTIONS,
    )
    cutter.apply_translation([0.0, 0.0, cfg.BALL_OPENING_Z - height / 2.0])
    return cutter


def _support_free_skirt() -> trimesh.Trimesh:
    """Flat bed ring + 45° outer cone blending into the sphere wall."""
    skirt = cfg.support_free_skirt()
    z0 = cfg.BALL_OPENING_Z
    z1 = skirt["z_blend"]
    r_hole = cfg.BALL_OPENING_R
    r_bed = skirt["bed_outer_r"]
    r_out = skirt["r_blend"]
    r_in = skirt["r_inner_blend"]
    r_bed_in = skirt["bed_inner_r"]
    # Closed (r, z) profile: bed face → outer cone → blend → inner cone → bed.
    profile = np.asarray(
        [
            (r_hole, z0),
            (r_bed, z0),
            (r_out, z1),
            (r_in, z1),
            (r_bed_in, z0),
            (r_hole, z0),
        ]
    )
    return trimesh.creation.revolve(profile, sections=SECTIONS)


def _lower_sphere_cutter() -> trimesh.Trimesh:
    """Removes the shallow spherical shell below the support-free blend."""
    skirt = cfg.support_free_skirt()
    z1 = skirt["z_blend"]
    z0 = cfg.BALL_OPENING_Z - 12.0
    height = z1 - z0 + 0.05
    cutter = trimesh.creation.cylinder(
        radius=cfg.BALL_R + 4.0,
        height=height,
        sections=64,
    )
    cutter.apply_translation([0.0, 0.0, (z0 + z1 + 0.05) / 2.0])
    return cutter


def _annular_sector(
    r0: float,
    r1: float,
    a0_deg: float,
    a1_deg: float,
    height: float,
    z0: float,
    steps: int = 24,
) -> trimesh.Trimesh:
    """Solid annular wedge from a0→a1 (degrees), z in [z0, z0+height]."""
    a0 = math.radians(a0_deg)
    a1 = math.radians(a1_deg)
    if a1 < a0:
        a1 += 2.0 * math.pi
    angles = np.linspace(a0, a1, max(steps, 4))
    ring0 = np.column_stack(
        (r0 * np.cos(angles), r0 * np.sin(angles), np.full(len(angles), z0))
    )
    ring1 = np.column_stack(
        (r1 * np.cos(angles), r1 * np.sin(angles), np.full(len(angles), z0))
    )
    ring0t = ring0.copy()
    ring0t[:, 2] = z0 + height
    ring1t = ring1.copy()
    ring1t[:, 2] = z0 + height
    verts = np.vstack([ring0, ring1, ring0t, ring1t])
    n = len(angles)
    faces = []
    for i in range(n - 1):
        # bottom
        faces.append([i, i + 1, n + i + 1])
        faces.append([i, n + i + 1, n + i])
        # top
        faces.append([2 * n + i, 3 * n + i, 3 * n + i + 1])
        faces.append([2 * n + i, 3 * n + i + 1, 2 * n + i + 1])
        # inner wall
        faces.append([i, 2 * n + i, 2 * n + i + 1])
        faces.append([i, 2 * n + i + 1, i + 1])
        # outer wall
        faces.append([n + i, n + i + 1, 3 * n + i + 1])
        faces.append([n + i, 3 * n + i + 1, 3 * n + i])
    # end caps
    faces.append([0, n, 3 * n])
    faces.append([0, 3 * n, 2 * n])
    faces.append([n - 1, 2 * n + n - 1, 3 * n + n - 1])
    faces.append([n - 1, 3 * n + n - 1, 2 * n - 1])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces), process=True)
    if not mesh.is_volume:
        mesh.fix_normals()
    return mesh


def _bayonet_flange() -> trimesh.Trimesh:
    """Internal ring at the ball opening that carries the L-track slots."""
    pin_r = cfg.BAYONET_PCD / 2.0
    track_clear = cfg.BAYONET_PIN_DIA / 2.0 + cfg.BAYONET_PIN_CLEARANCE + 0.6
    r_inner = max(pin_r - track_clear - 1.2, cfg.LED_POCKET_DIA / 2.0 + 1.0)
    r_outer = cfg.BALL_OPENING_R - 0.15
    if r_outer - r_inner < 3.0:
        raise RuntimeError("bayonet flange is too thin radially")
    profile = np.asarray(
        [
            (r_inner, cfg.BALL_OPENING_Z),
            (r_outer, cfg.BALL_OPENING_Z),
            (r_outer, cfg.BALL_OPENING_Z + cfg.BAYONET_FLANGE_H),
            (r_inner, cfg.BALL_OPENING_Z + cfg.BAYONET_FLANGE_H),
            (r_inner, cfg.BALL_OPENING_Z),
        ]
    )
    return trimesh.creation.revolve(profile, sections=SECTIONS)


def _bayonet_slot_cutters() -> list[trimesh.Trimesh]:
    """L-tracks: axial entry from the opening + circumferential twist lock."""
    pin_r = cfg.BAYONET_PCD / 2.0
    half_w = cfg.BAYONET_PIN_DIA / 2.0 + cfg.BAYONET_PIN_CLEARANCE
    r0 = pin_r - half_w - 0.4
    r1 = pin_r + half_w + 0.4
    entry_h = cfg.BAYONET_FLANGE_H + 2.0
    track_z0 = cfg.BALL_OPENING_Z + cfg.BAYONET_FLANGE_H - cfg.BAYONET_TRACK_H - 0.2
    cutters = []
    for index in range(cfg.BAYONET_LUG_COUNT):
        phase = 360.0 * index / cfg.BAYONET_LUG_COUNT
        # Axial entry mouth (open at the seating face).
        entry = _annular_sector(
            r0,
            r1,
            phase - cfg.BAYONET_ENTRY_WIDTH_DEG / 2.0,
            phase + cfg.BAYONET_ENTRY_WIDTH_DEG / 2.0,
            entry_h,
            cfg.BALL_OPENING_Z - 1.0,
            steps=16,
        )
        # Circumferential lock track (twist toward +phase).
        track = _annular_sector(
            r0,
            r1,
            phase - cfg.BAYONET_ENTRY_WIDTH_DEG / 2.0,
            phase + cfg.BAYONET_TWIST_DEG + cfg.BAYONET_ENTRY_WIDTH_DEG / 2.0,
            cfg.BAYONET_TRACK_H + 0.4,
            track_z0,
            steps=28,
        )
        cutters.extend([entry, track])
    return cutters


def _bayonet_detent_bumps() -> list[trimesh.Trimesh]:
    """0.4 mm bumps at lock end of each L-track — tactile click, anti-backout."""
    pin_r = cfg.BAYONET_PCD / 2.0
    track_z0 = cfg.BALL_OPENING_Z + cfg.BAYONET_FLANGE_H - cfg.BAYONET_TRACK_H - 0.2
    # Centre of the pin at full lock (entry centre + twist).
    bumps = []
    for index in range(cfg.BAYONET_LUG_COUNT):
        phase = 360.0 * index / cfg.BAYONET_LUG_COUNT
        lock_deg = phase + cfg.BAYONET_TWIST_DEG
        lock_rad = math.radians(lock_deg)
        # Half-sphere protruding up from the track floor into the pin path.
        bump = trimesh.creation.icosphere(subdivisions=2, radius=cfg.BAYONET_DETENT_H)
        bump.apply_translation(
            [
                pin_r * math.cos(lock_rad),
                pin_r * math.sin(lock_rad),
                track_z0 + cfg.BAYONET_DETENT_H * 0.35,
            ]
        )
        bumps.append(bump)
    return bumps


def _bayonet_pins() -> trimesh.Trimesh:
    """Tee-side Ø5 pins with R1.2 root fillets (assembled tee frame)."""
    pins = []
    pin_r = cfg.BAYONET_PCD / 2.0
    z0 = cfg.TEE_CUP_Z1 - 0.4
    shaft_r = cfg.BAYONET_PIN_DIA / 2.0
    fillet_r = cfg.BAYONET_PIN_FILLET_R
    for index in range(cfg.BAYONET_LUG_COUNT):
        phase = math.radians(360.0 * index / cfg.BAYONET_LUG_COUNT)
        cx = pin_r * math.cos(phase)
        cy = pin_r * math.sin(phase)
        pin = trimesh.creation.cylinder(
            radius=shaft_r,
            height=cfg.BAYONET_PIN_H + 0.8,
            sections=48,
        )
        pin.apply_translation([cx, cy, z0 + (cfg.BAYONET_PIN_H + 0.8) / 2.0])
        # Toroidal fillet at the cup deck: keep the outer lower quarter only.
        torus = trimesh.creation.torus(
            major_radius=shaft_r + fillet_r,
            minor_radius=fillet_r,
            major_sections=48,
            minor_sections=24,
        )
        torus.apply_translation([cx, cy, z0])
        # Clip to the corner volume outside the shaft and above the deck.
        keep = trimesh.creation.cylinder(
            radius=shaft_r + fillet_r + 0.05,
            height=fillet_r * 2.0 + 0.2,
            sections=48,
        )
        keep.apply_translation([cx, cy, z0 + fillet_r / 2.0])
        shaft_cut = trimesh.creation.cylinder(
            radius=shaft_r - 0.02,
            height=fillet_r * 2.0 + 0.4,
            sections=48,
        )
        shaft_cut.apply_translation([cx, cy, z0 + fillet_r / 2.0])
        below = trimesh.creation.box(
            extents=[(shaft_r + fillet_r) * 4.0, (shaft_r + fillet_r) * 4.0, fillet_r + 0.4]
        )
        below.apply_translation([cx, cy, z0 - (fillet_r + 0.4) / 2.0])
        fillet = _difference(_intersection([torus, keep]), [shaft_cut, below])
        pins.append(_union([pin, fillet]))
    return _union(pins)


def build_ball_blank(include_dimples: bool = True) -> tuple[trimesh.Trimesh, dict]:
    """Complete hollow dimpled ball in ball-local coordinates (centre at origin)."""
    centers = cfg.dimple_unit_centers() if include_dimples else np.zeros((0, 3))
    subdiv = SPHERE_SUBDIV if include_dimples else SPHERE_SUBDIV_FAST
    if include_dimples and len(centers):
        shell = _displaced_shell(centers, subdiv=subdiv)
    else:
        shell = _sphere_shell(cfg.BALL_R, cfg.BALL_INNER_R, subdiv=subdiv)
    shell = _difference(shell, [_opening_cutter()])
    # Replace shallow lower sphere with flat ring + self-supporting cone.
    shell = _difference(shell, [_lower_sphere_cutter()])
    shell = _union([shell, _support_free_skirt()])
    shell = _union([shell, _bayonet_flange()])
    shell = _difference(shell, _bayonet_slot_cutters())
    # Detent bumps re-fill the lock end of each track for a positive click.
    shell = _union([shell, *_bayonet_detent_bumps()])
    shell = _serialization_safe(shell, "Golf_Ball_Blank")
    skirt = cfg.support_free_skirt()
    return shell, {
        "ball_od": cfg.BALL_OD,
        "wall": cfg.BALL_WALL,
        "opening_id": cfg.BALL_OPENING_ID,
        "dimple_count": int(len(centers)),
        "dimple_depth": cfg.DIMPLE_DEPTH,
        "dimple_alpha_max_rad": cfg.DIMPLE_ALPHA_MAX,
        "dimple_style": "constant-thickness dual-surface displacement",
        "wall_thickness_constant": cfg.BALL_WALL,
        "piece_count": 1,
        "support_free_skirt": {
            "overhang_deg": skirt["overhang_deg"],
            "cone_height": round(skirt["cone_height"], 2),
            "bed_ring_od": round(skirt["bed_outer_r"] * 2.0, 2),
            "ring_width": round(skirt["ring_width"], 2),
        },
        "join": {
            "type": "bayonet",
            "lugs": cfg.BAYONET_LUG_COUNT,
            "twist_deg": cfg.BAYONET_TWIST_DEG,
            "pcd": cfg.BAYONET_PCD,
            "pin_dia": cfg.BAYONET_PIN_DIA,
            "pin_fillet_r": cfg.BAYONET_PIN_FILLET_R,
            "detent_h": cfg.BAYONET_DETENT_H,
        },
        "infill": "0% sparse — solid 1.6 mm shell",
    }


def build_ball_print(include_dimples: bool = True) -> tuple[trimesh.Trimesh, dict]:
    """One-piece shade. Print opening-down; support the dome past ~45° overhang."""
    blank, report = build_ball_blank(include_dimples=include_dimples)
    ball = blank.copy()
    ball.apply_translation([0.0, 0.0, -cfg.BALL_OPENING_Z])
    ball.apply_translation([0.0, 0.0, -ball.bounds[0, 2]])
    ball = _serialization_safe(ball, "Golf_Ball")
    report = dict(report)
    report.update(
        {
            "part": "golf ball shade",
            "print_orientation": (
                "opening on bed, dome up; self-supporting 45° skirt — "
                "supports off (bayonet builds from the bed ring)"
            ),
            "bounds_mm": [
                [round(float(v), 2) for v in ball.bounds[0]],
                [round(float(v), 2) for v in ball.bounds[1]],
            ],
        }
    )
    return ball, report


def build_ball_assembled(include_dimples: bool = True) -> tuple[trimesh.Trimesh, dict]:
    """One-piece shade in ball-local frame, ready to translate to world Z."""
    blank, report = build_ball_blank(include_dimples=include_dimples)
    ball = blank.copy()
    ball = _serialization_safe(ball, "Golf_Ball_Assembled")
    report = dict(report)
    report.update({"part": "golf ball shade"})
    return ball, report


# --------------------------------------------------------------------------
# Green grass base (snap) + wooden tee (integrated LED pocket)
# --------------------------------------------------------------------------


def _tee_stem_profile() -> np.ndarray:
    """Revolved outer silhouette from foot to cup underside, z up."""
    foot_r = cfg.TEE_FOOT_OD / 2.0
    narrow_r = cfg.TEE_STEM_NARROW_OD / 2.0
    mid_r = cfg.TEE_STEM_MID_OD / 2.0
    top_r = cfg.TEE_STEM_TOP_OD / 2.0
    cup_body_r = cfg.CUP_OD / 2.0
    seat_r = cfg.BALL_SEAT_OD / 2.0
    return np.asarray(
        [
            (0.0, 0.0),
            (foot_r, 0.0),
            (foot_r, cfg.TEE_FOOT_FLAT_H),
            (narrow_r, cfg.TEE_STEM_NARROW_Z),
            (mid_r, cfg.TEE_STEM_MID_Z),
            (top_r, cfg.TEE_CUP_Z0 - 4.0),
            (cup_body_r, cfg.TEE_CUP_Z0),
            (cup_body_r, cfg.TEE_CUP_Z1 - cfg.CUP_SEAT_H),
            (seat_r, cfg.TEE_CUP_Z1 - cfg.CUP_SEAT_H),
            (seat_r, cfg.TEE_CUP_Z1),
            (0.0, cfg.TEE_CUP_Z1),
            (0.0, 0.0),
        ]
    )


def _snap_bead() -> trimesh.Trimesh:
    """Circumferential bead on the tee foot that clicks into the base groove."""
    profile = np.asarray(
        [
            (cfg.SNAP_SHAFT_OD / 2.0 - 0.2, cfg.SNAP_BEAD_Z - cfg.SNAP_BEAD_H / 2.0),
            (cfg.SNAP_BEAD_OD / 2.0, cfg.SNAP_BEAD_Z - cfg.SNAP_BEAD_H / 2.0 + 0.3),
            (cfg.SNAP_BEAD_OD / 2.0, cfg.SNAP_BEAD_Z + cfg.SNAP_BEAD_H / 2.0 - 0.3),
            (cfg.SNAP_SHAFT_OD / 2.0 - 0.2, cfg.SNAP_BEAD_Z + cfg.SNAP_BEAD_H / 2.0),
            (cfg.SNAP_SHAFT_OD / 2.0 - 0.2, cfg.SNAP_BEAD_Z - cfg.SNAP_BEAD_H / 2.0),
        ]
    )
    return trimesh.creation.revolve(profile, sections=SECTIONS)


def _snap_spring_slots() -> list[trimesh.Trimesh]:
    """Vertical slots that split the bead into cantilever spring fingers."""
    z1 = cfg.SNAP_BEAD_Z + cfg.SNAP_BEAD_H / 2.0 + cfg.SNAP_SLOT_DEPTH_EXTRA
    height = z1 + 1.0
    r1 = cfg.SNAP_BEAD_OD / 2.0 + 1.5
    cutters = []
    for index in range(cfg.SNAP_SLOT_COUNT):
        phase = 360.0 * index / cfg.SNAP_SLOT_COUNT
        cutters.append(
            _annular_sector(
                0.5,
                r1,
                phase - cfg.SNAP_SLOT_WIDTH_DEG / 2.0,
                phase + cfg.SNAP_SLOT_WIDTH_DEG / 2.0,
                height,
                -1.0,
                steps=10,
            )
        )
    return cutters


def _cable_stem_bore(pocket_z0: float) -> trimesh.Trimesh:
    """Vertical cable bore — clears MH001 inline switch + USB overmold."""
    top = pocket_z0 + 1.5
    bottom = -1.0
    height = top - bottom
    bore = trimesh.creation.cylinder(
        radius=cfg.CABLE_BORE_DIA / 2.0,
        height=height,
        sections=96,
    )
    bore.apply_translation([0.0, 0.0, (top + bottom) / 2.0])
    return bore


def base_top_fuzzy_mask(mesh: trimesh.Trimesh) -> np.ndarray:
    """Paint fuzzy only on the upward top face, clear of the snap entry."""
    normals = mesh.face_normals
    centroids = mesh.triangles_center
    z_top = float(mesh.bounds[1, 2])
    radial = np.sqrt(centroids[:, 0] ** 2 + centroids[:, 1] ** 2)
    return (
        (normals[:, 2] > 0.72)
        & (centroids[:, 2] > z_top - 0.35)
        & (radial > cfg.FUZZY_SNAP_KEEP_R)
    )


def _translated_cylinder(radius: float, height: float, z_center: float) -> trimesh.Trimesh:
    cyl = trimesh.creation.cylinder(radius=radius, height=height, sections=SECTIONS)
    cyl.apply_translation([0.0, 0.0, z_center])
    return cyl


def _rounded_square_prism(
    side: float, height: float, corner_r: float, z0: float = 0.0
) -> trimesh.Trimesh:
    """Axis-aligned rounded square extruded along +z from z0."""
    try:
        from shapely.geometry import box as shapely_box
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required for the square grass base") from exc

    half = side / 2.0
    radius = min(corner_r, half - 0.5)
    # Inset by radius then buffer to get a true rounded rectangle.
    core = shapely_box(-half + radius, -half + radius, half - radius, half - radius)
    poly = core.buffer(radius)
    prism = trimesh.creation.extrude_polygon(poly, height)
    prism.apply_translation([0.0, 0.0, z0])
    return prism


def build_grass_base() -> tuple[trimesh.Trimesh, dict]:
    """Square grass pad: snap recess, ballast pocket with cover ledge, felt, trench."""
    body = _rounded_square_prism(
        cfg.BASE_SIDE, cfg.BASE_H, cfg.BASE_CORNER_R, z0=0.0
    )

    recess_z0 = cfg.BASE_H - cfg.BASE_TEE_RECESS_DEPTH
    shaft_r = cfg.SNAP_SHAFT_OD / 2.0 + cfg.SNAP_SHAFT_CLEARANCE / 2.0
    entry_r = cfg.SNAP_ENTRY_OD / 2.0
    groove_r = cfg.SNAP_GROOVE_OD / 2.0
    groove_z0 = recess_z0 + cfg.SNAP_BEAD_Z - cfg.SNAP_GROOVE_H / 2.0
    groove_z1 = groove_z0 + cfg.SNAP_GROOVE_H
    if groove_z0 <= recess_z0 + 0.6:
        raise RuntimeError("snap groove sits too low in the base recess")
    lead = 1.2
    socket_profile = np.asarray(
        [
            (0.0, recess_z0 - 0.2),
            (shaft_r, recess_z0 - 0.2),
            (shaft_r, groove_z0),
            (groove_r, groove_z0),
            (groove_r, groove_z1),
            (shaft_r, groove_z1),
            (shaft_r, cfg.BASE_H - lead),
            (entry_r, cfg.BASE_H + 0.2),
            (0.0, cfg.BASE_H + 0.2),
            (0.0, recess_z0 - 0.2),
        ]
    )
    socket = trimesh.creation.revolve(socket_profile, sections=SECTIONS)

    well = trimesh.creation.cylinder(
        radius=cfg.CABLE_BORE_DIA / 2.0 + 0.4,
        height=cfg.BASE_H + 1.0,
        sections=64,
    )
    well.apply_translation([0.0, 0.0, cfg.BASE_H / 2.0])

    trench_roof = 2.0
    trench_h = min(cfg.BALLAST_DEPTH + 0.4, cfg.BASE_H - trench_roof + 0.4)
    trench_len = cfg.BASE_SIDE / 2.0 + 2.0
    trench_w = cfg.CABLE_EXIT_TRENCH_W
    trench = trimesh.creation.box(
        extents=[trench_len, trench_w, trench_h]
    )
    trench.apply_translation([trench_len / 2.0, 0.0, trench_h / 2.0 - 0.2])

    # Ballast: deep pocket + narrower mouth → radial ledge for the cover plate.
    ballast_outer_side = cfg.BASE_SIDE - 2.0 * cfg.BALLAST_OUTER_INSET
    corner = max(cfg.BASE_CORNER_R - cfg.BALLAST_OUTER_INSET, 4.0)
    mouth_side = ballast_outer_side - 2.0 * cfg.BALLAST_COVER_LEDGE
    mouth_corner = max(corner - cfg.BALLAST_COVER_LEDGE, 3.0)
    deep = _rounded_square_prism(
        ballast_outer_side,
        cfg.BALLAST_DEPTH - cfg.BALLAST_COVER_THICKNESS + 0.2,
        corner,
        z0=cfg.BALLAST_COVER_THICKNESS - 0.1,
    )
    mouth = _rounded_square_prism(
        mouth_side,
        cfg.BALLAST_COVER_THICKNESS + 0.15,
        mouth_corner,
        z0=-0.1,
    )
    keep = _translated_cylinder(
        cfg.BALLAST_INNER_R,
        cfg.BALLAST_DEPTH + 0.4,
        (cfg.BALLAST_DEPTH + 0.4) / 2.0 - 0.1,
    )
    ballast = _difference(_union([deep, mouth]), [keep])

    felt = _rounded_square_prism(
        cfg.FELT_PAD_SIDE,
        cfg.FELT_PAD_RECESS + 0.2,
        cfg.FELT_PAD_CORNER_R,
        z0=-0.1,
    )

    if recess_z0 < cfg.BALLAST_DEPTH + 2.5:
        raise RuntimeError("ballast pocket collides with the snap floor")

    base = _difference(body, [socket, well, trench, ballast, felt])
    if len(base.split(only_watertight=False)) != 1:
        raise RuntimeError("grass base must remain one connected body")
    base.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(cfg.CABLE_PHASE_DEG),
            [0.0, 0.0, 1.0],
        )
    )
    base.apply_translation([0.0, 0.0, -base.bounds[0, 2]])
    base = _serialization_safe(base, "Golf_Grass_Base")
    ballast_half = ballast_outer_side / 2.0
    ballast_cm3 = (
        (2.0 * ballast_half) ** 2 - math.pi * cfg.BALLAST_INNER_R**2
    ) * (cfg.BALLAST_DEPTH - cfg.BALLAST_COVER_THICKNESS) / 1000.0
    report = {
        "part": "grass base",
        "filament": cfg.BASE_FILAMENT_ID,
        "shape": "rounded_square",
        "side": cfg.BASE_SIDE,
        "corner_radius": cfg.BASE_CORNER_R,
        "height": cfg.BASE_H,
        "snap": {
            "entry_od": cfg.SNAP_ENTRY_OD,
            "groove_od": cfg.SNAP_GROOVE_OD,
            "shaft_clearance_od": round(shaft_r * 2.0, 2),
            "recess_depth": cfg.BASE_TEE_RECESS_DEPTH,
            "spring_slots_on_tee": cfg.SNAP_SLOT_COUNT,
        },
        "ballast": {
            "pocket_cm3": round(ballast_cm3, 1),
            "outer_side": ballast_outer_side,
            "inner_keepout_od": cfg.BALLAST_INNER_R * 2.0,
            "depth": cfg.BALLAST_DEPTH,
            "cover_ledge_mm": cfg.BALLAST_COVER_LEDGE,
            "cover_thickness": cfg.BALLAST_COVER_THICKNESS,
            "target_fill_g": "200–300 (steel washers / shot)",
        },
        "felt_pad": {
            "side": cfg.FELT_PAD_SIDE,
            "corner_radius": cfg.FELT_PAD_CORNER_R,
            "recess_mm": cfg.FELT_PAD_RECESS,
        },
        "fuzzy_turf": {
            "faces": "top only, clear of snap entry",
            "keep_radius": cfg.FUZZY_SNAP_KEEP_R,
            "thickness": cfg.BASE_FUZZY_THICKNESS,
            "point_distance": cfg.BASE_FUZZY_POINT_DISTANCE,
        },
        "cable_exit": {
            "style": "underside_trench_only",
            "central_well_dia": round(cfg.CABLE_BORE_DIA + 0.8, 2),
            "underside_trench_width": round(trench_w, 2),
            "clears_inline_switch_od": cfg.LED_INLINE_SWITCH_CLEAR_DIA,
            "trench_roof_mm": trench_roof,
            "phase_deg": cfg.CABLE_PHASE_DEG,
        },
        "print_orientation": "underside on bed",
        "volume_cm3": round(float(base.volume) / 1000.0, 2),
        "acceptance": (
            "Tee foot snaps into the recess with a positive click; pulls out "
            "with firm hand force but not under cable tug alone; ballast pocket "
            "accepts ≥200 g under the printed cover; square felt pad seats flush "
            "in the 1 mm recess over the cover; Ø18 bore and trench clear the "
            "MH001 inline switch and USB plug; fuzzy turf stops clear of the "
            "snap entry."
        ),
    }
    return base, report


def build_ballast_cover() -> tuple[trimesh.Trimesh, dict]:
    """1.2 mm drop-in plate that seals the ballast pocket before the felt pad."""
    side = cfg.ballast_cover_side()
    cover = _rounded_square_prism(
        side,
        cfg.BALLAST_COVER_THICKNESS,
        cfg.ballast_cover_corner_r(),
        z0=0.0,
    )
    hole = _translated_cylinder(
        cfg.BALLAST_INNER_R + 0.4,
        cfg.BALLAST_COVER_THICKNESS + 0.4,
        cfg.BALLAST_COVER_THICKNESS / 2.0,
    )
    # Cable trench relief so the cover does not bridge the exit channel.
    trench = trimesh.creation.box(
        extents=[
            side / 2.0 + 2.0,
            cfg.CABLE_EXIT_TRENCH_W + 0.4,
            cfg.BALLAST_COVER_THICKNESS + 0.4,
        ]
    )
    trench.apply_translation(
        [side / 4.0 + 1.0, 0.0, cfg.BALLAST_COVER_THICKNESS / 2.0]
    )
    cover = _difference(cover, [hole, trench])
    cover = _serialization_safe(cover, "Golf_Ballast_Cover")
    report = {
        "part": "ballast cover",
        "filament": cfg.BASE_FILAMENT_ID,
        "side": round(side, 2),
        "corner_radius": round(cfg.ballast_cover_corner_r(), 2),
        "thickness": cfg.BALLAST_COVER_THICKNESS,
        "central_hole_od": round((cfg.BALLAST_INNER_R + 0.4) * 2.0, 2),
        "fit": "drop-in on 1.5 mm ledge; optional CA glue",
        "print_orientation": "flat on bed",
        "volume_cm3": round(float(cover.volume) / 1000.0, 2),
        "acceptance": (
            "Cover drops onto the ballast ledge flush with the felt recess floor; "
            "felt pad then adheres over a rigid sealed pocket."
        ),
    }
    return cover, report


def build_reflector_cup() -> tuple[trimesh.Trimesh, dict]:
    """0.8 mm Ivory cup lining the LED pocket — bounces light into the shade."""
    outer_r = cfg.reflector_outer_r()
    inner_r = outer_r - cfg.REFLECTOR_WALL
    height = cfg.LED_POCKET_DEPTH - cfg.REFLECTOR_HEIGHT_CLEARANCE
    # MH001 must drop inside with a little free play.
    if inner_r < cfg.LED_DIA / 2.0 + 0.1:
        raise RuntimeError(
            f"reflector inner Ø{inner_r * 2:.2f} cannot clear MH001 Ø{cfg.LED_DIA}"
        )
    outer = trimesh.creation.cylinder(radius=outer_r, height=height, sections=96)
    outer.apply_translation([0.0, 0.0, height / 2.0])
    bore = trimesh.creation.cylinder(
        radius=inner_r,
        height=height - cfg.REFLECTOR_FLOOR + 0.2,
        sections=96,
    )
    bore.apply_translation(
        [0.0, 0.0, cfg.REFLECTOR_FLOOR + (height - cfg.REFLECTOR_FLOOR + 0.2) / 2.0]
    )
    cable = _translated_cylinder(
        cfg.CABLE_BORE_DIA / 2.0 + 0.5,
        cfg.REFLECTOR_FLOOR + 0.4,
        cfg.REFLECTOR_FLOOR / 2.0,
    )
    cup = _difference(outer, [bore, cable])
    cup = _serialization_safe(cup, "Golf_Reflector_Cup")
    report = {
        "part": "LED reflector cup",
        "filament": cfg.REFLECTOR_FILAMENT_ID,
        "outer_od": round(outer_r * 2.0, 2),
        "inner_od": round(inner_r * 2.0, 2),
        "wall": cfg.REFLECTOR_WALL,
        "floor": cfg.REFLECTOR_FLOOR,
        "height": round(height, 2),
        "cable_bore_od": round(cfg.CABLE_BORE_DIA + 1.0, 2),
        "print_orientation": "floor on bed",
        "volume_cm3": round(float(cup.volume) / 1000.0, 2),
        "acceptance": (
            "Cup drops into the tee LED pocket; MH001 seats inside; floor cable "
            "hole aligns with the Ø18 stem bore; white walls bounce light upward."
        ),
    }
    return cup, report


def build_tee() -> tuple[trimesh.Trimesh, dict]:
    """Wooden tee: LED pocket, bayonet pins, hollow stem, slotted snap bead.

    Print inverted: ball seat on the bed, stem and foot upward.
    """
    groove = cfg.ball_seat_groove()
    groove_outer_r = groove["groove_outer_diameter"] / 2.0
    groove_inner_r = groove["groove_inner_diameter"] / 2.0
    groove_floor_z = cfg.TEE_CUP_Z1 - cfg.BALL_SEAT_GROOVE_DEPTH

    blank = trimesh.creation.revolve(_tee_stem_profile(), sections=SECTIONS)
    blank = _union([blank, _snap_bead(), _bayonet_pins()])
    blank = _difference(blank, _snap_spring_slots())

    pocket_z1 = cfg.TEE_CUP_Z1 + 0.2
    pocket_z0 = cfg.TEE_CUP_Z1 - cfg.LED_POCKET_DEPTH
    if pocket_z0 < cfg.TEE_CUP_Z0 + 3.0:
        raise RuntimeError("LED pocket leaves less than 3 mm of cup floor")
    pocket = trimesh.creation.cylinder(
        radius=cfg.LED_POCKET_DIA / 2.0,
        height=cfg.LED_POCKET_DEPTH + 0.4,
        sections=SECTIONS,
    )
    pocket.apply_translation([0.0, 0.0, (pocket_z0 + pocket_z1) / 2.0])

    groove_cutter = trimesh.creation.revolve(
        np.asarray(
            [
                (groove_inner_r, groove_floor_z),
                (groove_outer_r, groove_floor_z),
                (groove_outer_r, cfg.TEE_CUP_Z1 + 0.2),
                (groove_inner_r, cfg.TEE_CUP_Z1 + 0.2),
                (groove_inner_r, groove_floor_z),
            ]
        ),
        sections=SECTIONS,
    )

    tee = _difference(
        blank,
        [pocket, groove_cutter, _cable_stem_bore(pocket_z0)],
    )
    tee.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(cfg.CABLE_PHASE_DEG),
            [0.0, 0.0, 1.0],
        )
    )
    tee = _serialization_safe(tee, "Golf_Tee")

    tee_print = tee.copy()
    tee_print.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0])
    )
    tee_print.apply_translation([0.0, 0.0, -tee_print.bounds[0, 2]])
    tee_print = _serialization_safe(tee_print, "Golf_Tee_Print")

    stem_wall = (cfg.TEE_STEM_NARROW_OD - cfg.CABLE_BORE_DIA) / 2.0
    floor_thickness = pocket_z0 - cfg.TEE_CUP_Z0
    report = {
        "part": "wooden golf tee",
        "filament": cfg.TEE_FILAMENT_LABEL_OVERRIDE,
        "assembled_orientation": "snapped into green base",
        "print_orientation": "top seat on bed, hollow stem upward; 3-layer brim",
        "height": cfg.TEE_OVERALL_H,
        "foot_od": cfg.TEE_FOOT_OD,
        "snap_bead_od": cfg.SNAP_BEAD_OD,
        "snap_spring_slots": cfg.SNAP_SLOT_COUNT,
        "cup_od": cfg.CUP_OD,
        "seat_od": cfg.BALL_SEAT_OD,
        "led_pocket": {
            "diameter": cfg.LED_POCKET_DIA,
            "depth": cfg.LED_POCKET_DEPTH,
            "floor_thickness": round(floor_thickness, 2),
            "tape_pad_diameter": cfg.LED_TAPE_DIA,
            "cable_floor_bore": True,
            "rim_cable_notch": False,
        },
        "bayonet": {
            "lugs": cfg.BAYONET_LUG_COUNT,
            "twist_deg": cfg.BAYONET_TWIST_DEG,
            "pcd": cfg.BAYONET_PCD,
            "pin_dia": cfg.BAYONET_PIN_DIA,
            "pin_height": cfg.BAYONET_PIN_H,
            "pin_fillet_r": cfg.BAYONET_PIN_FILLET_R,
            "detent_h": cfg.BAYONET_DETENT_H,
        },
        "hollow_cable_bore_dia": cfg.CABLE_BORE_DIA,
        "minimum_stem_wall": round(stem_wall, 2),
        "cable_phase_deg": cfg.CABLE_PHASE_DEG,
        "ball_seat_groove": groove,
        "volume_cm3": round(float(tee.volume) / 1000.0, 2),
        "acceptance": (
            "LED reflector drops into the cup; MH001 seats on top; USB then "
            "inline switch pass the Ø18 pocket-floor bore and hollow stem; ball "
            "bayonet locks with a ~60° twist and detent click; slotted foot snaps "
            "into the grass base; cup seat rim is continuous (no side notch)."
        ),
    }
    report["assembled_height"] = cfg.TEE_OVERALL_H
    return tee_print, report, tee


def build_tee_print() -> tuple[trimesh.Trimesh, dict]:
    printed, report, _assembled = build_tee()
    return printed, report


def build_tee_assembled() -> tuple[trimesh.Trimesh, dict]:
    _printed, report, assembled = build_tee()
    return assembled, report


# --------------------------------------------------------------------------
# Smoke / validation
# --------------------------------------------------------------------------


def smoke(include_dimples: bool = False) -> dict:
    """Fast geometry gate. Full dimples are reserved for production generate."""
    ball, ball_r = build_ball_print(include_dimples=include_dimples)
    tee, tee_r = build_tee_print()
    base, base_r = build_grass_base()
    cover, cover_r = build_ballast_cover()
    reflector, reflector_r = build_reflector_cup()
    groove = cfg.ball_seat_groove()
    wall = groove["wall_thickness_constant"]
    if wall < 1.2:
        raise RuntimeError(f"ball wall is only {wall} mm")
    if tee_r["led_pocket"].get("rim_cable_notch"):
        raise RuntimeError("tee cup must not have a rim cable notch")
    if cfg.CABLE_BORE_DIA < 18.0:
        raise RuntimeError("cable bore must clear MH001 switch/USB (≥Ø18)")
    return {
        "summary": cfg.summary(),
        "ball": ball_r,
        "tee": tee_r,
        "base": base_r,
        "ballast_cover": cover_r,
        "reflector": reflector_r,
        "mesh_watertight": {
            "ball": bool(ball.is_watertight),
            "tee": bool(tee.is_watertight),
            "base": bool(base.is_watertight),
            "ballast_cover": bool(cover.is_watertight),
            "reflector": bool(reflector.is_watertight),
        },
    }


if __name__ == "__main__":
    import json

    print(json.dumps(smoke(include_dimples=False), indent=2))
