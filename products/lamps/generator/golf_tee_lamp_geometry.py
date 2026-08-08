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
from scipy.spatial import ConvexHull

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import boucle_lamp_coupons as boucle  # noqa: E402
import golf_tee_lamp_config as cfg  # noqa: E402

SECTIONS = 192
# Subdiv 5 supplies the base sphere. Explicit centre and profile-ring samples
# make every dimple reach its configured depth without a prohibitively dense
# global sphere.
SPHERE_SUBDIV = 5
SPHERE_SUBDIV_FAST = 4
DIMPLE_PROFILE_RING_SAMPLES = ((0.45, 8), (0.90, 12))


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


def _dimple_profile_samples(centers: np.ndarray) -> np.ndarray:
    """Add exact centres and concentric profile rings to the sphere point cloud."""
    samples = [centers]
    for centre in centers:
        helper = (
            np.asarray([1.0, 0.0, 0.0])
            if abs(float(centre[2])) > 0.9
            else np.asarray([0.0, 0.0, 1.0])
        )
        tangent_u = np.cross(centre, helper)
        tangent_u /= max(float(np.linalg.norm(tangent_u)), 1e-12)
        tangent_v = np.cross(centre, tangent_u)
        for fraction, count in DIMPLE_PROFILE_RING_SAMPLES:
            alpha = cfg.DIMPLE_ALPHA_MAX * fraction
            phases = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
            ring = (
                math.cos(alpha) * centre[None, :]
                + math.sin(alpha)
                * (
                    np.cos(phases)[:, None] * tangent_u[None, :]
                    + np.sin(phases)[:, None] * tangent_v[None, :]
                )
            )
            samples.append(ring)
    return np.vstack(samples)


def _dimple_unit_sphere(
    centers: np.ndarray, subdiv: int
) -> tuple[np.ndarray, np.ndarray]:
    """Triangulate a sphere containing exact samples for every dimple profile."""
    base_dirs, _base_faces = _unit_icosphere(subdiv)
    cloud = np.vstack([base_dirs, _dimple_profile_samples(centers)])
    cloud = np.unique(np.round(cloud, 11), axis=0)
    cloud /= np.maximum(np.linalg.norm(cloud, axis=1, keepdims=True), 1e-12)
    hull = ConvexHull(cloud, qhull_options="QJ Pp")
    surface = trimesh.Trimesh(
        vertices=cloud,
        faces=np.asarray(hull.simplices),
        process=False,
    )
    surface.fix_normals()
    surface.remove_unreferenced_vertices()
    dirs = np.asarray(surface.vertices, dtype=np.float64)
    dirs /= np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-12)
    return dirs, np.asarray(surface.faces)


def _displaced_shell(
    centers: np.ndarray, subdiv: int = SPHERE_SUBDIV
) -> trimesh.Trimesh:
    """Outer and inner surfaces share the same dimple field → constant wall t."""
    dirs, faces = _dimple_unit_sphere(centers, subdiv)
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
        "dimple_style": (
            "repulsion-relaxed equal-area centres; exact centre/profile samples; "
            "constant-thickness dual-surface displacement"
        ),
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
    cup_ramp_h = (cup_body_r - top_r) / math.tan(
        math.radians(cfg.TEE_CUP_UNDERSIDE_ANGLE_DEG)
    )
    cup_ramp_z0 = cfg.TEE_CUP_Z0 - cup_ramp_h
    seat_z0 = cfg.TEE_CUP_Z1 - cfg.CUP_SEAT_H
    seat_ramp_h = (seat_r - cup_body_r) / math.tan(
        math.radians(cfg.TEE_SEAT_UNDERSIDE_ANGLE_DEG)
    )
    seat_ramp_z0 = seat_z0 - seat_ramp_h
    if cup_ramp_z0 <= cfg.TEE_STEM_MID_Z:
        raise RuntimeError("tee cup ramp collides with the mid-stem transition")
    if seat_ramp_z0 <= cfg.TEE_CUP_Z0:
        raise RuntimeError("tee seat ramp collides with the lower cup ramp")
    return np.asarray(
        [
            (0.0, 0.0),
            (foot_r, 0.0),
            (foot_r, cfg.TEE_FOOT_FLAT_H),
            (narrow_r, cfg.TEE_STEM_NARROW_Z),
            (mid_r, cfg.TEE_STEM_MID_Z),
            (top_r, cup_ramp_z0),
            (cup_body_r, cfg.TEE_CUP_Z0),
            (cup_body_r, seat_ramp_z0),
            (seat_r, seat_z0),
            (seat_r, cfg.TEE_CUP_Z1),
            (0.0, cfg.TEE_CUP_Z1),
            (0.0, 0.0),
        ]
    )


def _snap_bead() -> trimesh.Trimesh:
    """Circumferential bead with a 45° print-side lead-in."""
    shaft_r = cfg.SNAP_SHAFT_OD / 2.0
    bead_r = cfg.SNAP_BEAD_OD / 2.0
    z_bottom = cfg.SNAP_BEAD_Z - cfg.SNAP_BEAD_H / 2.0
    z_top = cfg.SNAP_BEAD_Z + cfg.SNAP_BEAD_H / 2.0
    ramp_h = bead_r - shaft_r
    if ramp_h >= cfg.SNAP_BEAD_H:
        raise RuntimeError("snap bead is too short for its 45° lower lead-in")
    profile = np.asarray(
        [
            (shaft_r - 0.2, z_bottom),
            (shaft_r, z_bottom),
            (bead_r, z_bottom + ramp_h),
            (bead_r, z_top),
            (shaft_r - 0.2, z_top),
            (shaft_r - 0.2, z_bottom),
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


def _controller_stem_passage(pocket_z0: float) -> trimesh.Trimesh:
    """Vertical keyed passage for the 19.65 × 10.65 mm inline controller."""
    top = pocket_z0 + 1.5
    bottom = -1.0
    height = top - bottom
    passage = _rounded_rectangle_prism(
        cfg.CONTROLLER_PASSAGE_W,
        cfg.CONTROLLER_PASSAGE_H,
        height=height,
        corner_r=cfg.CONTROLLER_PASSAGE_CORNER_R,
        z0=bottom,
    )
    return passage


def _led_side_cable_chase(pocket_z0: float, pocket_z1: float) -> trimesh.Trimesh:
    """Radial floor chase joining the MH001 side lead to the centre passage."""
    chase_bottom = pocket_z0 - cfg.LED_CABLE_CHASE_H
    chase = trimesh.creation.box(
        extents=[
            cfg.LED_CABLE_CHASE_OUTER_R,
            cfg.LED_CABLE_CHASE_W,
            pocket_z1 - chase_bottom + 0.4,
        ]
    )
    chase.apply_translation(
        [
            cfg.LED_CABLE_CHASE_OUTER_R / 2.0,
            0.0,
            (chase_bottom + pocket_z1 + 0.4) / 2.0,
        ]
    )
    return chase


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


def _rounded_rectangle_prism(
    width: float,
    depth: float,
    height: float,
    corner_r: float,
    z0: float = 0.0,
) -> trimesh.Trimesh:
    """Axis-aligned rounded rectangle extruded along +z from z0."""
    try:
        from shapely.geometry import box as shapely_box
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required for rounded passages") from exc

    half_x = width / 2.0
    half_y = depth / 2.0
    radius = min(corner_r, half_x - 0.2, half_y - 0.2)
    # Inset by radius then buffer to get a true rounded rectangle.
    core = shapely_box(
        -half_x + radius,
        -half_y + radius,
        half_x - radius,
        half_y - radius,
    )
    poly = core.buffer(radius)
    prism = trimesh.creation.extrude_polygon(poly, height)
    prism.apply_translation([0.0, 0.0, z0])
    return prism


def _rounded_square_prism(
    side: float, height: float, corner_r: float, z0: float = 0.0
) -> trimesh.Trimesh:
    return _rounded_rectangle_prism(side, side, height, corner_r, z0=z0)


def _rounded_square_ring(side: float, corner_r: float, count: int = 128) -> np.ndarray:
    """Resampled boundary of a rounded square in XY (not closed)."""
    try:
        from shapely.geometry import box as shapely_box
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("shapely is required for the square grass base") from exc

    half = side / 2.0
    radius = min(corner_r, half - 0.5)
    core = shapely_box(-half + radius, -half + radius, half - radius, half - radius)
    poly = core.buffer(radius)
    coords = np.asarray(poly.exterior.coords)[:-1]
    closed = np.vstack([coords, coords[:1]])
    seg_len = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    u = np.concatenate([[0.0], np.cumsum(seg_len)])
    u /= u[-1]
    samples = np.linspace(0.0, 1.0, count, endpoint=False)
    return np.column_stack(
        [
            np.interp(samples, u, closed[:, 0]),
            np.interp(samples, u, closed[:, 1]),
        ]
    )


def _loft_rounded_squares(
    side0: float,
    corner0: float,
    side1: float,
    corner1: float,
    z0: float,
    z1: float,
    count: int = 128,
) -> trimesh.Trimesh:
    """Solid frustum between two rounded squares (convex, centroid-capped)."""
    ring0 = _rounded_square_ring(side0, corner0, count=count)
    ring1 = _rounded_square_ring(side1, corner1, count=count)
    n = count
    v0 = np.column_stack([ring0, np.full(n, z0)])
    v1 = np.column_stack([ring1, np.full(n, z1)])
    c0 = np.array([0.0, 0.0, z0])
    c1 = np.array([0.0, 0.0, z1])
    verts = np.vstack([v0, v1, c0[None, :], c1[None, :]])
    i_c0, i_c1 = 2 * n, 2 * n + 1
    faces: list[list[int]] = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j])
        faces.append([i, n + j, n + i])
        faces.append([i_c0, j, i])
        faces.append([i_c1, n + i, n + j])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    if not mesh.is_volume:
        raise RuntimeError("rounded-square loft is not a volume")
    return mesh


def _ballast_pocket_cutter() -> tuple[trimesh.Trimesh, dict]:
    """Ballast void with a true 45° cover seat (no horizontal underside ledge)."""
    ballast_outer_side = cfg.BASE_SIDE - 2.0 * cfg.BALLAST_OUTER_INSET
    corner = max(cfg.BASE_CORNER_R - cfg.BALLAST_OUTER_INSET, 4.0)
    deep_side = ballast_outer_side - 2.0 * cfg.BALLAST_COVER_LEDGE
    deep_corner = max(corner - cfg.BALLAST_COVER_LEDGE, 3.0)
    seat_angle = math.radians(cfg.BALLAST_COVER_SEAT_ANGLE_DEG)
    seat_h = cfg.BALLAST_COVER_LEDGE / math.tan(seat_angle)
    seat_z0 = cfg.FELT_PAD_RECESS
    seat_z1 = seat_z0 + seat_h
    if seat_z1 > cfg.BALLAST_DEPTH - 1.0:
        raise RuntimeError("ballast cover seat ramp consumes the pocket depth")

    # Full-size vertical mouth clears the tapered plug through the felt recess.
    mouth = _rounded_square_prism(
        ballast_outer_side,
        seat_z0 + 0.1,
        corner,
        z0=-0.05,
    )
    # The cavity narrows inward at 45°. A matching cover enters small-face-first
    # and stops with its large outward face at the felt-recess floor.
    seat = _loft_rounded_squares(
        ballast_outer_side,
        corner,
        deep_side,
        deep_corner,
        z0=seat_z0 - 0.05,
        z1=seat_z1,
    )
    deep = _rounded_square_prism(
        deep_side,
        cfg.BALLAST_DEPTH - seat_z1 + 0.25,
        deep_corner,
        z0=seat_z1 - 0.05,
    )
    keep = _translated_cylinder(
        cfg.BALLAST_INNER_R,
        cfg.BALLAST_DEPTH + 0.4,
        (cfg.BALLAST_DEPTH + 0.4) / 2.0 - 0.1,
    )
    void = _difference(_union([mouth, seat, deep]), [keep])
    meta = {
        "outer_side": ballast_outer_side,
        "deep_side": round(deep_side, 2),
        "cover_seat_radial_mm": cfg.BALLAST_COVER_LEDGE,
        "cover_seat_angle_deg": cfg.BALLAST_COVER_SEAT_ANGLE_DEG,
        "cover_seat_height_mm": round(seat_h, 2),
        "cover_seat_z_mm": [round(seat_z0, 2), round(seat_z1, 2)],
        "cover_thickness": cfg.BALLAST_COVER_THICKNESS,
    }
    return void, meta


def _snap_socket_cutter(recess_z0: float) -> tuple[trimesh.Trimesh, dict]:
    """Snap recess with a 45° upper groove lip (underside-on-bed print)."""
    shaft_r = cfg.SNAP_SHAFT_OD / 2.0 + cfg.SNAP_SHAFT_CLEARANCE / 2.0
    entry_r = cfg.SNAP_ENTRY_OD / 2.0
    mouth_r = cfg.SNAP_MOUTH_OD / 2.0
    groove_r = cfg.SNAP_GROOVE_OD / 2.0
    groove_z0 = recess_z0 + cfg.SNAP_BEAD_Z - cfg.SNAP_GROOVE_H / 2.0
    groove_z1 = groove_z0 + cfg.SNAP_GROOVE_H
    if groove_z0 <= recess_z0 + 0.6:
        raise RuntimeError("snap groove sits too low in the base recess")
    if entry_r <= shaft_r:
        raise RuntimeError("snap insertion throat must be wider than the shaft socket")
    if mouth_r <= entry_r:
        raise RuntimeError("snap mouth must flare beyond the insertion throat")
    undercut = groove_r - entry_r
    if undercut <= 0.2:
        raise RuntimeError("snap groove undercut is too shallow")
    lip_angle = math.radians(cfg.SNAP_GROOVE_CEILING_ANGLE_DEG)
    chamfer_h = undercut / math.tan(lip_angle)
    flat_h = cfg.SNAP_GROOVE_H - chamfer_h
    if flat_h < 0.35:
        raise RuntimeError(
            "snap groove is too short for a 45° upper lip plus bead land; "
            f"need ≥{chamfer_h + 0.35:.2f} mm, have {cfg.SNAP_GROOVE_H:.2f} mm"
        )
    mouth_lead_h = mouth_r - entry_r  # 45° outward mouth lead-in
    socket_profile = np.asarray(
        [
            (0.0, recess_z0 - 0.2),
            (shaft_r, recess_z0 - 0.2),
            (shaft_r, groove_z0),
            (groove_r, groove_z0),
            (groove_r, groove_z0 + flat_h),
            (entry_r, groove_z1),  # 45° retention lip; also the insertion throat
            (entry_r, cfg.BASE_H - mouth_lead_h),
            (mouth_r, cfg.BASE_H + 0.2),
            (0.0, cfg.BASE_H + 0.2),
            (0.0, recess_z0 - 0.2),
        ]
    )
    socket = trimesh.creation.revolve(socket_profile, sections=SECTIONS)
    meta = {
        "entry_od": cfg.SNAP_ENTRY_OD,
        "mouth_od": cfg.SNAP_MOUTH_OD,
        "groove_od": cfg.SNAP_GROOVE_OD,
        "shaft_clearance_od": round(shaft_r * 2.0, 2),
        "bead_entry_interference_radial": round(
            cfg.SNAP_BEAD_OD / 2.0 - entry_r, 2
        ),
        "recess_depth": cfg.BASE_TEE_RECESS_DEPTH,
        "spring_slots_on_tee": cfg.SNAP_SLOT_COUNT,
        "groove_lip_angle_deg": cfg.SNAP_GROOVE_CEILING_ANGLE_DEG,
        "groove_lip_chamfer_mm": round(chamfer_h, 2),
        "groove_flat_land_mm": round(flat_h, 2),
    }
    return socket, meta


def build_grass_base() -> tuple[trimesh.Trimesh, dict]:
    """Square grass pad: snap recess, 45° ballast seat, felt, trench."""
    body = _rounded_square_prism(
        cfg.BASE_SIDE, cfg.BASE_H, cfg.BASE_CORNER_R, z0=0.0
    )

    recess_z0 = cfg.BASE_H - cfg.BASE_TEE_RECESS_DEPTH
    socket, snap_meta = _snap_socket_cutter(recess_z0)

    well = _rounded_rectangle_prism(
        cfg.CONTROLLER_PASSAGE_W + cfg.BASE_CONTROLLER_PASSAGE_CLEARANCE,
        cfg.CONTROLLER_PASSAGE_H + cfg.BASE_CONTROLLER_PASSAGE_CLEARANCE,
        height=cfg.BASE_H + 1.0,
        corner_r=cfg.CONTROLLER_PASSAGE_CORNER_R
        + cfg.BASE_CONTROLLER_PASSAGE_CLEARANCE / 2.0,
        z0=-0.1,
    )

    trench_roof = 2.0
    trench_h = min(cfg.BALLAST_DEPTH + 0.4, cfg.BASE_H - trench_roof + 0.4)
    trench_len = cfg.BASE_SIDE / 2.0 + 2.0
    trench_w = cfg.CABLE_EXIT_TRENCH_W
    trench = trimesh.creation.box(
        extents=[trench_len, trench_w, trench_h]
    )
    trench.apply_translation([trench_len / 2.0, 0.0, trench_h / 2.0 - 0.2])

    ballast, ballast_meta = _ballast_pocket_cutter()

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
    ballast_cm3 = float(ballast.volume) / 1000.0
    report = {
        "part": "grass base",
        "filament": cfg.BASE_FILAMENT_ID,
        "shape": "rounded_square",
        "side": cfg.BASE_SIDE,
        "corner_radius": cfg.BASE_CORNER_R,
        "height": cfg.BASE_H,
        "snap": snap_meta,
        "ballast": {
            "pocket_cm3": round(ballast_cm3, 1),
            "outer_side": ballast_meta["outer_side"],
            "deep_side": ballast_meta["deep_side"],
            "inner_keepout_od": cfg.BALLAST_INNER_R * 2.0,
            "depth": cfg.BALLAST_DEPTH,
            "cover_seat_radial_mm": ballast_meta["cover_seat_radial_mm"],
            "cover_seat_angle_deg": ballast_meta["cover_seat_angle_deg"],
            "cover_seat_height_mm": ballast_meta["cover_seat_height_mm"],
            "cover_seat_z_mm": ballast_meta["cover_seat_z_mm"],
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
            "style": "keyed controller well plus flexible-lead underside trench",
            "central_well_mm": [
                round(
                    cfg.CONTROLLER_PASSAGE_W
                    + cfg.BASE_CONTROLLER_PASSAGE_CLEARANCE,
                    2,
                ),
                round(
                    cfg.CONTROLLER_PASSAGE_H
                    + cfg.BASE_CONTROLLER_PASSAGE_CLEARANCE,
                    2,
                ),
            ],
            "underside_trench_width": round(trench_w, 2),
            "controller_mm": [
                cfg.LED_CONTROLLER_L,
                cfg.LED_CONTROLLER_W,
                cfg.LED_CONTROLLER_H,
            ],
            "trench_roof_mm": trench_roof,
            "phase_deg": cfg.CABLE_PHASE_DEG,
        },
        "print_orientation": "underside on bed",
        "supports": (
            "tree(auto) on build plate — ballast pocket roof and trench bridge; "
            "snap opens upward so support scars stay off the snap faces"
        ),
        "volume_cm3": round(float(base.volume) / 1000.0, 2),
        "acceptance": (
            "Tee foot snaps into the recess with a positive click; pulls out "
            "with firm hand force but not under cable tug alone; ballast pocket "
            "accepts ≥200 g under the printed cover; square felt pad seats flush "
            "in the 1 mm recess over the cover; the keyed centre well passes the "
            "19.65 × 10.65 mm controller and the side trench carries only the "
            "flexible lead; fuzzy turf stops clear of the snap entry."
        ),
    }
    return base, report


def build_ballast_cover() -> tuple[trimesh.Trimesh, dict]:
    """45° tapered plug that seals the ballast pocket behind the felt pad."""
    outward_side = cfg.ballast_cover_side()
    inward_side = cfg.ballast_cover_inward_side()
    outward_corner = cfg.ballast_cover_corner_r()
    inward_corner = cfg.ballast_cover_inward_corner_r()
    cover = _loft_rounded_squares(
        outward_side,
        outward_corner,
        inward_side,
        inward_corner,
        z0=0.0,
        z1=cfg.BALLAST_COVER_THICKNESS,
    )
    hole = _translated_cylinder(
        cfg.BALLAST_INNER_R + 0.4,
        cfg.BALLAST_COVER_THICKNESS + 0.4,
        cfg.BALLAST_COVER_THICKNESS / 2.0,
    )
    # Cable trench relief so the cover does not bridge the exit channel.
    trench = trimesh.creation.box(
        extents=[
            outward_side / 2.0 + 2.0,
            cfg.CABLE_EXIT_TRENCH_W + 0.4,
            cfg.BALLAST_COVER_THICKNESS + 0.4,
        ]
    )
    trench.apply_translation(
        [outward_side / 4.0 + 1.0, 0.0, cfg.BALLAST_COVER_THICKNESS / 2.0]
    )
    cover = _difference(cover, [hole, trench])
    cover = _serialization_safe(cover, "Golf_Ballast_Cover")
    report = {
        "part": "ballast cover",
        "filament": cfg.BASE_FILAMENT_ID,
        "outward_side": round(outward_side, 2),
        "inward_side": round(inward_side, 2),
        "outward_corner_radius": round(outward_corner, 2),
        "inward_corner_radius": round(inward_corner, 2),
        "thickness": cfg.BALLAST_COVER_THICKNESS,
        "central_hole_od": round((cfg.BALLAST_INNER_R + 0.4) * 2.0, 2),
        "fit": (
            f"{cfg.BALLAST_COVER_SEAT_ANGLE_DEG:.0f}° tapered plug in "
            f"{cfg.BALLAST_COVER_LEDGE:.1f} mm seat; "
            f"{cfg.BALLAST_COVER_CLEARANCE:.2f} mm/side; outward face at "
            f"Z{cfg.ballast_cover_installed_z():.2f}; optional CA glue"
        ),
        "print_orientation": "large outward face on bed; shrinks inward at 45°",
        "volume_cm3": round(float(cover.volume) / 1000.0, 2),
        "acceptance": (
            "Tapered cover passes through the pocket mouth and settles into the "
            "45° seat within 0.05 mm of the felt-recess floor; felt pad then "
            "adheres over a rigid sealed pocket."
        ),
    }
    return cover, report


def build_reflector_cup() -> tuple[trimesh.Trimesh, dict]:
    """0.8 mm Ivory cup with a side-lead notch for the MH001."""
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
    controller = _rounded_rectangle_prism(
        cfg.CONTROLLER_PASSAGE_W + 0.6,
        cfg.CONTROLLER_PASSAGE_H + 0.6,
        cfg.REFLECTOR_FLOOR + 0.4,
        cfg.CONTROLLER_PASSAGE_CORNER_R + 0.3,
        z0=-0.1,
    )
    side_lead = trimesh.creation.box(
        extents=[
            outer_r + 2.0,
            cfg.LED_CABLE_CHASE_W + 0.6,
            height + 0.4,
        ]
    )
    side_lead.apply_translation(
        [(outer_r + 2.0) / 2.0, 0.0, height / 2.0]
    )
    cup = _difference(outer, [bore, controller, side_lead])
    cup.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(cfg.CABLE_PHASE_DEG),
            [0.0, 0.0, 1.0],
        )
    )
    cup = _serialization_safe(cup, "Golf_Reflector_Cup")
    report = {
        "part": "LED reflector cup",
        "filament": cfg.REFLECTOR_FILAMENT_ID,
        "outer_od": round(outer_r * 2.0, 2),
        "inner_od": round(inner_r * 2.0, 2),
        "wall": cfg.REFLECTOR_WALL,
        "floor": cfg.REFLECTOR_FLOOR,
        "height": round(height, 2),
        "controller_passage_mm": [
            round(cfg.CONTROLLER_PASSAGE_W + 0.6, 2),
            round(cfg.CONTROLLER_PASSAGE_H + 0.6, 2),
        ],
        "side_lead_notch_width": round(cfg.LED_CABLE_CHASE_W + 0.6, 2),
        "print_orientation": "floor on bed",
        "volume_cm3": round(float(cup.volume) / 1000.0, 2),
        "acceptance": (
            "Cup drops into the tee LED pocket; MH001 seats inside; its side lead "
            "aligns with the radial notch and the keyed controller passage; white "
            "walls bounce light upward."
        ),
    }
    return cup, report


def build_tee() -> tuple[trimesh.Trimesh, dict]:
    """Wooden tee: LED pocket, bayonet pins, hollow stem, slotted snap bead.

    Print foot-down. Both cup expansions are 45° self-supporting ramps.
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
        [
            pocket,
            groove_cutter,
            _controller_stem_passage(pocket_z0),
            _led_side_cable_chase(pocket_z0, pocket_z1),
        ],
    )
    tee.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(cfg.CABLE_PHASE_DEG),
            [0.0, 0.0, 1.0],
        )
    )
    tee = _serialization_safe(tee, "Golf_Tee")

    tee_print = tee.copy()
    tee_print.apply_translation([0.0, 0.0, -tee_print.bounds[0, 2]])
    tee_print = _serialization_safe(tee_print, "Golf_Tee_Print")

    controller_corner_r = (
        math.hypot(
            cfg.CONTROLLER_PASSAGE_W / 2.0 - cfg.CONTROLLER_PASSAGE_CORNER_R,
            cfg.CONTROLLER_PASSAGE_H / 2.0 - cfg.CONTROLLER_PASSAGE_CORNER_R,
        )
        + cfg.CONTROLLER_PASSAGE_CORNER_R
    )
    stem_wall = cfg.TEE_STEM_NARROW_OD / 2.0 - controller_corner_r
    floor_thickness = pocket_z0 - cfg.TEE_CUP_Z0
    report = {
        "part": "wooden golf tee",
        "filament": cfg.TEE_FILAMENT_LABEL_OVERRIDE,
        "assembled_orientation": "snapped into green base",
        "print_orientation": (
            "snap foot on bed, cup and bayonet pins upward; 8 mm outer brim; "
            "45° cup and seat underside ramps; supports off"
        ),
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
            "controller_passage": [
                cfg.CONTROLLER_PASSAGE_W,
                cfg.CONTROLLER_PASSAGE_H,
            ],
            "side_cable_chase": {
                "width": cfg.LED_CABLE_CHASE_W,
                "height": cfg.LED_CABLE_CHASE_H,
                "outer_radius": cfg.LED_CABLE_CHASE_OUTER_R,
            },
            "rim_cable_notch": True,
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
        "self_supporting_cup": {
            "cup_underside_angle_deg": cfg.TEE_CUP_UNDERSIDE_ANGLE_DEG,
            "seat_underside_angle_deg": cfg.TEE_SEAT_UNDERSIDE_ANGLE_DEG,
        },
        "hollow_controller_passage": [
            cfg.CONTROLLER_PASSAGE_W,
            cfg.CONTROLLER_PASSAGE_H,
        ],
        "minimum_stem_wall": round(stem_wall, 2),
        "cable_phase_deg": cfg.CABLE_PHASE_DEG,
        "ball_seat_groove": groove,
        "volume_cm3": round(float(tee.volume) / 1000.0, 2),
        "acceptance": (
            "LED reflector drops into the cup with its notch aligned; the MH001 "
            "side lead settles into the radial chase; USB and the 19.65 × 10.65 mm "
            "controller pass the keyed stem passage; ball bayonet locks with a "
            "~60° twist and detent click; revised slotted foot snaps into the base."
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
    passage = tee_r["led_pocket"].get("controller_passage")
    if passage != [cfg.CONTROLLER_PASSAGE_W, cfg.CONTROLLER_PASSAGE_H]:
        raise RuntimeError("tee controller passage metadata is missing")
    if cfg.CONTROLLER_PASSAGE_W <= cfg.LED_CONTROLLER_W:
        raise RuntimeError("controller passage is not wider than the controller")
    if cfg.CONTROLLER_PASSAGE_H <= cfg.LED_CONTROLLER_H:
        raise RuntimeError("controller passage is not taller than the controller")
    if not tee_r["led_pocket"].get("rim_cable_notch"):
        raise RuntimeError("tee cup must include the MH001 side-lead chase")
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
