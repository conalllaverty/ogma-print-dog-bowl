#!/usr/bin/env python3
"""Build the complete ready-to-print Bouclé Stack lamp for Bambu Lab P2S.

The primary output is one eight-plate 3MF, with matching individual fallback
projects. Each plate has one object to avoid the inter-object travel moves that
produced strings on the physical coupons:

1. Shell A
2. Shell B
3. Shell C
4. A→B halo ring
5. B→C halo ring
6. LED diffuser baffle
7. Plinth and leg frame
8. Removable LED cradle

Shells and rings use Bone White Bambu PLA Matte; the hidden diffuser uses PLA
Basic Jade White for higher transmission; the leg frame and removable cradle
use Dark Chocolate Bambu PLA Matte. Only shell exterior sidewalls are
fuzzy-painted; bed bands, oblique rims, interiors, and precision parts remain
smooth.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import boucle_lamp_config as cfg  # noqa: E402
import boucle_lamp_coupons as geometry  # noqa: E402
import build_bambu_project as bambu  # noqa: E402
from ogma.filaments import load_palette, resolve_filament  # noqa: E402


FILAMENT = "matte-bone-white"
BASE_FILAMENT = "matte-dark-chocolate"
SHELL_C_WALL = 1.20
MATTE_FILAMENT_PROFILE = "Bambu PLA Matte @BBL P2S"
DIFFUSER_FILAMENT_PROFILE = "Bambu PLA Basic @BBL P2S"
DIFFUSER_FILAMENT_HEX = "#FFFFFF"
DIFFUSER_FILAMENT_LABEL = "Bambu PLA Basic · Jade White"
BASE_FILAMENT_LABEL = "Bambu PLA Matte · Dark Chocolate"
PLATE_PITCH = 312.0
PLATE_CENTRE = 128.0
PLATE_COLUMNS = 3
EDGE_BAND = 4.0


@dataclass(frozen=True)
class FuzzyStyle:
    key: str
    label: str
    thickness: float
    point_distance: float
    noise_type: str
    mode: str
    scale: float
    octaves: int
    persistence: float
    artifact_name: str
    report_name: str

    def profile_settings(self) -> dict[str, str]:
        return {
            "fuzzy_skin_thickness": f"{self.thickness:.2f}",
            "fuzzy_skin_point_distance": f"{self.point_distance:.2f}",
            "fuzzy_skin_noise_type": self.noise_type,
            "fuzzy_skin_mode": self.mode,
            "fuzzy_skin_scale": f"{self.scale:.1f}",
            "fuzzy_skin_octaves": str(self.octaves),
            "fuzzy_skin_persistence": f"{self.persistence:.1f}",
        }

    def report(self) -> dict[str, str | float | int]:
        return {
            "key": self.key,
            "label": self.label,
            "thickness_mm": self.thickness,
            "point_distance_mm": self.point_distance,
            "noise_type": self.noise_type,
            "generator_mode": self.mode,
            "feature_size_mm": self.scale,
            "octaves": self.octaves,
            "persistence": self.persistence,
        }


PRODUCTION_FUZZY_STYLE = FuzzyStyle(
    key="production",
    label="coarse ceramic / sandstone",
    thickness=0.30,
    point_distance=0.80,
    noise_type="classic",
    mode="displacement",
    scale=1.0,
    octaves=4,
    persistence=0.5,
    artifact_name="Boucle_Stack_Lamp_All_Plates_P2S.3mf",
    report_name="production_report.json",
)

COMMON_PROFILE = {
    "enable_support": "0",
    "precise_outer_wall": "1",
    "detect_thin_wall": "1",
    "fuzzy_skin": "none",
    "fuzzy_skin_first_layer": "0",
    "brim_type": "outer_only",
    "brim_width": "8",
}

def shell_profile(fuzzy_style: FuzzyStyle) -> dict[str, str]:
    return COMMON_PROFILE | {
        "layer_height": "0.20",
        "wall_generator": "arachne",
        "outer_wall_line_width": "0.40",
        "inner_wall_line_width": "0.40",
        "wall_loops": "4",
        "sparse_infill_density": "0%",
        "top_shell_layers": "4",
        "bottom_shell_layers": "3",
        "outer_wall_speed": "60",
        "inner_wall_speed": "100",
        "small_perimeter_speed": "80%",
        # Random avoids one bright vertical seam; the fuzzy texture hides the
        # small distributed starts better than a smooth translucent wall does.
        "seam_position": "random",
        **fuzzy_style.profile_settings(),
    }

RING_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.16",
    "wall_generator": "classic",
    # Every ring feature is already wider than one full extrusion. Disabling
    # thin-wall detection avoids Studio's failed Voronoi fallback on the
    # narrow radial webs without changing generated paths or material use.
    "detect_thin_wall": "0",
    # The stock P2S "Auto" mode suppresses retraction for long gap-infill
    # detours. They stay over the ring, but the physical coupons showed that
    # this Bone White spool can still draw hairs during travel, so retract every
    # eligible infill move instead.
    "reduce_infill_retraction_mode": "Disabled",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.42",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "4",
    "outer_wall_speed": "90",
    "inner_wall_speed": "150",
    "seam_position": "aligned",
}

BAFFLE_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "outer_wall_line_width": "0.40",
    "inner_wall_line_width": "0.40",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "6",
    "bottom_shell_layers": "6",
    "outer_wall_speed": "80",
    "inner_wall_speed": "120",
    "seam_position": "aligned",
}

LEG_FRAME_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "reduce_infill_retraction_mode": "Disabled",
    # The 2.6 mm shell-groove closure and 0.8 mm cradle-stop step are short
    # bridges. Generated support introduced the only unretracted >5 mm travels
    # in the sliced plate and physically strung inside the inset.
    "enable_support": "0",
    "bridge_speed": "20",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.42",
    "wall_loops": "5",
    "sparse_infill_density": "20%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "outer_wall_speed": "60",
    "inner_wall_speed": "100",
    "seam_position": "aligned",
}

CRADLE_PROFILE = COMMON_PROFILE | {
    "layer_height": "0.20",
    "wall_generator": "arachne",
    "reduce_infill_retraction_mode": "Disabled",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.42",
    "wall_loops": "4",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "top_shell_layers": "5",
    "bottom_shell_layers": "5",
    "outer_wall_speed": "70",
    "inner_wall_speed": "110",
    "seam_position": "aligned",
}

FILAMENT_PROFILE_OVERRIDES = {
    MATTE_FILAMENT_PROFILE: {
        "counter_coef_2": ["0.003"],
        "counter_coef_3": ["0.0066"],
        "counter_limit_max": ["0.082"],
        "counter_limit_min": ["0.0066"],
        "filament_flow_ratio": ["1.01", "0.98"],
        "filament_density": ["1.32"],
        "filament_cost": ["24.99"],
        "filament_max_volumetric_speed": ["22", "40"],
        "filament_retraction_distances_when_cut": ["0", "10"],
        "hole_coef_2": ["-0.0026"],
        "hole_coef_3": ["0.1116"],
        "hole_limit_max": ["0.1116"],
        "hole_limit_min": ["0.046"],
        "impact_strength_z": ["6.6"],
    },
    DIFFUSER_FILAMENT_PROFILE: {
        "counter_coef_2": ["0.0025"],
        "counter_coef_3": ["0.014"],
        "counter_limit_max": ["0.076"],
        "counter_limit_min": ["0.014"],
        "filament_flow_ratio": ["0.98", "0.98"],
        "filament_density": ["1.26"],
        "filament_cost": ["24.99"],
        "filament_change_length": ["5"],
        "filament_prime_volume": ["30"],
        "filament_max_volumetric_speed": ["21", "40"],
        "filament_retraction_distances_when_cut": ["10", "10"],
        "hole_coef_2": ["-0.0028"],
        "hole_coef_3": ["0.12"],
        "hole_limit_max": ["0.12"],
        "hole_limit_min": ["0.05"],
        "impact_strength_z": ["13.8"],
    },
}


@dataclass
class Part:
    label: str
    filename: str
    mesh: trimesh.Trimesh
    plate: int
    profile: dict[str, str]
    paint: np.ndarray | None = None
    extruder: int = 1
    filament_id: str | None = FILAMENT
    filament_hex: str | None = None
    filament_profile: str = MATTE_FILAMENT_PROFILE
    filament_label: str = "Bambu PLA Matte · Bone White"


def plate_position(plate: int) -> tuple[float, float, float]:
    if plate < 1:
        raise ValueError("plate numbers are one-based")
    index = plate - 1
    return (
        PLATE_CENTRE + PLATE_PITCH * (index % PLATE_COLUMNS),
        PLATE_CENTRE - PLATE_PITCH * (index // PLATE_COLUMNS),
        0.0,
    )


def centre_on_bed(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    mesh = geometry._serialization_safe(mesh, name)
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0, 2]])
    return geometry._serialization_safe(mesh, name)


def fuzzy_outer_wall_mask(
    mesh: trimesh.Trimesh,
    shell: cfg.Shell,
    wall_thickness: float = cfg.WALL,
    fuzzy_style: FuzzyStyle = PRODUCTION_FUZZY_STYLE,
) -> tuple[np.ndarray, dict]:
    """Paint only exterior side facets, leaving smooth 4 mm edge bands."""
    triangles = mesh.vertices[mesh.faces]
    centres = triangles.mean(axis=1)
    normals = mesh.face_normals

    radial = np.zeros_like(normals)
    radial[:, :2] = centres[:, :2]
    radial_length = np.linalg.norm(radial, axis=1)
    valid = radial_length > 1e-8
    radial[valid] /= radial_length[valid, None]
    outward = np.einsum("ij,ij->i", normals, radial) > 0.72

    cut_deg, cut_high = shell.local_cut()
    top_z = shell.axis_length + cut_high * np.tan(np.radians(cut_deg)) * triangles[:, :, 0]
    distance_below_rim = top_z - triangles[:, :, 2]
    clear_of_bed = triangles[:, :, 2].min(axis=1) >= EDGE_BAND - 1e-6
    clear_of_rim = distance_below_rim.min(axis=1) >= EDGE_BAND - 1e-6
    paint = outward & clear_of_bed & clear_of_rim

    outer_area = float(mesh.area_faces[outward].sum())
    painted_area = float(mesh.area_faces[paint].sum())
    if not np.any(paint) or outer_area <= 0.0:
        raise RuntimeError(f"{shell.key}: no exterior faces selected for fuzzy paint")
    if painted_area / outer_area < 0.65:
        raise RuntimeError(
            f"{shell.key}: fuzzy paint covers only {painted_area / outer_area:.1%} "
            "of the exterior sidewall"
        )
    if np.any(paint & ~outward):
        raise RuntimeError(f"{shell.key}: non-exterior facets selected for fuzzy paint")
    minimum_wall = wall_thickness - fuzzy_style.thickness
    if minimum_wall < 0.8:
        raise RuntimeError(
            f"{shell.key}: fuzzy displacement leaves only {minimum_wall:.2f} mm "
            "of modelled wall"
        )

    return paint, {
        "painted_faces": int(paint.sum()),
        "total_faces": len(mesh.faces),
        "painted_outer_area_fraction": round(painted_area / outer_area, 3),
        "smooth_base_band_mm": EDGE_BAND,
        "smooth_rim_band_mm": EDGE_BAND,
        "wall_thickness_mm": wall_thickness,
        "minimum_wall_after_fuzzy_mm": round(minimum_wall, 2),
        **fuzzy_style.report(),
    }


def production_shell(
    shell: cfg.Shell,
    add_register: bool,
    sections: int = geometry.SECTIONS,
    stride: int = 1,
    wall_thickness: float = cfg.WALL,
) -> trimesh.Trimesh:
    """Full shell with the same internal locating ledge proven by the coupons.

    The locating ledge always keeps the canonical 1.6 mm base interface, even
    when the optical wall above it is thinner. Shells A and B also receive an
    open-rim notch that clocks the halo ring dropped into them.
    """
    wall = geometry.shell_wall_solid(
        shell,
        sections=sections,
        stride=stride,
        wall=wall_thickness,
    )
    if add_register:
        inner_r = shell.base_radius - cfg.WALL
        wall_inner_r = shell.base_radius - wall_thickness
        register = geometry.annular_sector(
            inner_r - cfg.RING_REGISTER_W,
            max(inner_r, wall_inner_r) + cfg.WALL * 0.5,
            geometry.UPPER_REGISTER_H,
            0.0,
            360.0,
            steps=sections,
        )
        solid = geometry._finish(
            geometry._union([wall, register]),
            f"{shell.key} production wall and locating register",
        )
        solid = geometry.cut_joint_clocking_groove(solid, shell)
    else:
        solid = wall

    if shell.key in {"shell_a", "shell_b"}:
        solid = geometry.cut_lower_clocking_groove(solid, shell)
    return solid


def shell_wall_thickness(shell: cfg.Shell) -> float:
    return SHELL_C_WALL if shell.key == "shell_c" else cfg.WALL


def open_ab_ring(
    lower: cfg.Shell,
    upper: cfg.Shell,
    sections: int = geometry.SECTIONS,
    steps: int = 260,
) -> tuple[trimesh.Trimesh, dict]:
    """Optically open A→B ring with a straight continuous bond band.

    The previous 45° funnel intercepted roughly 22% of the LED's direct rays.
    The former ten deep scarfed tabs projected a triangular shadow pattern onto
    Shell A. A continuous full-depth skirt now provides the complete 360°
    bonding surface and a straight lower edge while remaining bed-rooted.
    Twenty thin webs carry the upper stack into a bed-rooted central collar
    while leaving the complete lower bore open.
    """
    flat, matrix = geometry.joint_frame(lower)
    gap = cfg.HALO_GAP
    rb_in = upper.base_radius - cfg.WALL
    collar_r = rb_in - cfg.RING_REGISTER_W - cfg.RING_SLIP
    corbel_r = rb_in - cfg.RING_REGISTER_W / 2.0
    bore_r = collar_r - cfg.RING_WEB
    corbel_h = corbel_r - collar_r
    bottom_z = -gap - cfg.RING_FOOT
    collar_bottom_z = bottom_z

    s_max = flat.long_side + 2.0
    full_skirt = geometry._difference(
        geometry.inner_envelope(
            flat, cfg.RING_SLIP, s_max, sections=sections, steps=steps
        ),
        [
            geometry.inner_envelope(
                flat,
                cfg.RING_SLIP + cfg.RING_WEB,
                s_max,
                sections=sections,
                steps=steps,
            )
        ],
    )
    full_skirt.apply_transform(np.linalg.inv(matrix))
    full_skirt = full_skirt.slice_plane(
        plane_origin=(0.0, 0.0, -gap),
        plane_normal=(0.0, 0.0, -1.0),
        cap=True,
    ).slice_plane(
        plane_origin=(0.0, 0.0, bottom_z),
        plane_normal=(0.0, 0.0, 1.0),
        cap=True,
    )
    full_skirt = geometry._finish(full_skirt, "open A-B skirt source")
    skirt = full_skirt

    collar = trimesh.creation.revolve(
        np.asarray(
            [
                (bore_r, collar_bottom_z),
                (collar_r, collar_bottom_z),
                (collar_r, -corbel_h),
                (corbel_r, 0.0),
                (collar_r, 0.0),
                (collar_r, geometry.UPPER_REGISTER_H - 0.8),
                (collar_r - 0.8, geometry.UPPER_REGISTER_H),
                (bore_r, geometry.UPPER_REGISTER_H),
                (bore_r, collar_bottom_z),
            ]
        ),
        sections=sections,
    )
    collar = geometry._finish(collar, "open A-B central collar")

    clip = geometry.inner_envelope(
        flat,
        cfg.RING_SLIP * 0.8,
        s_max,
        sections=sections,
        steps=steps,
    )
    clip.apply_transform(np.linalg.inv(matrix))
    beam_inner = bore_r - 0.1
    beam_outer = 92.0
    web_top_z = -gap
    web_height = web_top_z - bottom_z
    web_thickness = 1.2
    web_angles = tuple(index * 18.0 for index in range(20))
    webs = []
    for angle_deg in web_angles:
        beam = trimesh.creation.box(
            extents=[beam_outer - beam_inner, web_thickness, web_height]
        )
        beam.apply_translation(
            [
                (beam_inner + beam_outer) / 2.0,
                0.0,
                (bottom_z + web_top_z) / 2.0,
            ]
        )
        beam.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(angle_deg), [0.0, 0.0, 1.0]
            )
        )
        webs.append(geometry._intersection([beam, clip]))

    clocking_key = geometry.joint_clocking_key(upper)
    lower_key = geometry.lower_clocking_key(
        lower,
        bottom_z=bottom_z,
        skirt_source=full_skirt,
    )
    ring = geometry._finish(
        geometry._union(
            [skirt, collar, clocking_key, lower_key, *webs]
        ),
        "Boucle open A-B halo ring",
    )
    if len(ring.split(only_watertight=False)) != 1:
        raise RuntimeError("open A-B ring is not one connected body")

    centres = ring.triangles_center
    severe_downward = (
        (ring.face_normals[:, 2] < -0.72)
        & (centres[:, 2] > bottom_z + 0.2)
    )
    unsupported_area = float(ring.area_faces[severe_downward].sum())
    if unsupported_area > 1.0:
        bad_z = centres[severe_downward, 2]
        raise RuntimeError(
            "open A-B ring contains steep unsupported underside: "
            f"{unsupported_area:.2f} mm² at Z"
            f"{float(bad_z.min()):.2f}..{float(bad_z.max()):.2f}"
        )

    recess = cfg.joint_recess(lower, upper)
    minimum_rim_outer_r = corbel_r + recess
    annulus_mid_r = (collar_r + minimum_rim_outer_r - cfg.WALL) / 2.0
    web_obstruction = (
        len(web_angles) * web_thickness / (2.0 * math.pi * annulus_mid_r)
    )
    return ring, {
        "print_orientation": (
            "upper-shell axis vertical, continuous bond band and webs down"
        ),
        "architecture": (
            "straight continuous full-depth bond skirt + bed-rooted central "
            "collar + twenty straight radial webs"
        ),
        "bore_radius": round(bore_r, 2),
        "collar_radius": round(collar_r, 2),
        "seat_radius": round(corbel_r, 2),
        "web": cfg.RING_WEB,
        "bond_band_depth": cfg.RING_FOOT,
        "glue_tab_count": 0,
        "outer_skirt_arc_degrees": 360.0,
        "radial_web_count": len(web_angles),
        "radial_web_thickness": web_thickness,
        "radial_web_height": web_height,
        "collar_bottom_z": round(collar_bottom_z, 2),
        "annular_light_path_obstruction_fraction": round(web_obstruction, 4),
        "steep_unsupported_underside_area_mm2": round(unsupported_area, 3),
        "seat_inboard_of_outer_surface": round(recess, 2),
        "light_window": [
            round(corbel_r, 2),
            round(minimum_rim_outer_r - cfg.WALL, 2),
        ],
        "upper_shell_clocking": (
            geometry.joint_clocking_report(upper)
        ),
        "lower_shell_clocking": (
            geometry.lower_clocking_report(lower)
        ),
    }


def compact_bc_ring(
    lower: cfg.Shell,
    upper: cfg.Shell,
    sections: int = geometry.SECTIONS,
    steps: int = 260,
) -> tuple[trimesh.Trimesh, dict]:
    """Support-free B→C ring with a continuous shallow outer band.

    The former continuous funnel reached 22 mm down around the complete rim,
    colliding with the A→B hardware where Shell B is only 10.2 mm tall. This
    version uses a 5 mm bed-rooted conformal band around the complete rim, a
    narrow central tube through the A→B ring bore, and five evenly distributed
    bed-rooted radial webs. Every layer remains connected without reaching the
    locating ledge or the A→B ring.
    """
    flat, matrix = geometry.joint_frame(lower)
    gap = cfg.HALO_GAP
    rb_in = upper.base_radius - cfg.WALL
    collar_r = rb_in - cfg.RING_REGISTER_W - cfg.RING_SLIP
    corbel_r = rb_in - cfg.RING_REGISTER_W / 2.0
    bore_r = collar_r - cfg.RING_WEB
    corbel_h = corbel_r - collar_r
    bottom_z = -gap - cfg.RING_OUTER_BAND_H
    short_side_clearance = (
        lower.short_side
        - geometry.UPPER_REGISTER_H
        - cfg.RING_OUTER_BAND_H
    )
    if short_side_clearance < 1.0:
        raise RuntimeError(
            "B-C outer band leaves insufficient clearance above Shell B's "
            f"lower register: {short_side_clearance:.2f} mm"
        )

    s_max = flat.long_side + 2.0
    skirt = geometry._difference(
        geometry.inner_envelope(
            flat, cfg.RING_SLIP, s_max, sections=sections, steps=steps
        ),
        [
            geometry.inner_envelope(
                flat,
                cfg.RING_SLIP + cfg.RING_WEB,
                s_max,
                sections=sections,
                steps=steps,
            )
        ],
    )
    skirt.apply_transform(np.linalg.inv(matrix))
    skirt = skirt.slice_plane(
        plane_origin=(0.0, 0.0, -gap),
        plane_normal=(0.0, 0.0, -1.0),
        cap=True,
    ).slice_plane(
        plane_origin=(0.0, 0.0, bottom_z),
        plane_normal=(0.0, 0.0, 1.0),
        cap=True,
    )
    skirt = geometry._finish(skirt, "shallow B-C continuous outer band")

    collar = trimesh.creation.revolve(
        np.asarray(
            [
                (bore_r, bottom_z),
                (collar_r, bottom_z),
                (collar_r, -corbel_h),
                (corbel_r, 0.0),
                (collar_r, 0.0),
                (collar_r, geometry.UPPER_REGISTER_H - 0.8),
                (collar_r - 0.8, geometry.UPPER_REGISTER_H),
                (bore_r, geometry.UPPER_REGISTER_H),
                (bore_r, bottom_z),
            ]
        ),
        sections=sections,
    )
    collar = geometry._finish(collar, "shallow B-C central collar")

    clip = geometry.inner_envelope(
        flat,
        cfg.RING_SLIP * 0.8,
        s_max,
        sections=sections,
        steps=steps,
    )
    clip.apply_transform(np.linalg.inv(matrix))
    beam_inner = collar_r - 0.5
    beam_outer = 80.0
    web_top_z = -gap
    web_height = web_top_z - bottom_z
    webs = []
    web_angles = tuple(360.0 * index / 5.0 for index in range(5))
    for angle_deg in web_angles:
        beam = trimesh.creation.box(
            extents=[beam_outer - beam_inner, 1.6, web_height]
        )
        beam.apply_translation(
            [
                (beam_inner + beam_outer) / 2.0,
                0.0,
                (bottom_z + web_top_z) / 2.0,
            ]
        )
        beam.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(angle_deg), [0.0, 0.0, 1.0]
            )
        )
        clipped = geometry._intersection([beam, clip])
        webs.append(clipped)

    clocking_key = geometry.joint_clocking_key(upper)
    lower_key = geometry.lower_clocking_key(
        lower,
        bottom_z=bottom_z,
        skirt_source=skirt,
    )
    ring = geometry._finish(
        geometry._union(
            [skirt, collar, clocking_key, lower_key, *webs]
        ),
        "Boucle shallow B-C halo ring",
    )
    if len(ring.split(only_watertight=False)) != 1:
        raise RuntimeError("shallow B-C ring is not one connected body")

    centres = ring.triangles_center
    severe_downward = (
        (ring.face_normals[:, 2] < -0.72)
        & (centres[:, 2] > bottom_z + 0.2)
    )
    unsupported_area = float(ring.area_faces[severe_downward].sum())
    if unsupported_area > 1.0:
        raise RuntimeError(
            "shallow B-C ring contains steep unsupported underside: "
            f"{unsupported_area:.2f} mm²"
        )

    recess = cfg.joint_recess(lower, upper)
    return ring, {
        "print_orientation": "upper-shell axis vertical, central collar and skirt down",
        "architecture": "5 mm continuous outer band + central collar + five radial webs",
        "bore_radius": round(bore_r, 2),
        "collar_radius": round(collar_r, 2),
        "seat_radius": round(corbel_r, 2),
        "web": cfg.RING_WEB,
        "outer_band_height": cfg.RING_OUTER_BAND_H,
        "short_side_clearance_to_lower_register": round(
            short_side_clearance,
            2,
        ),
        "outer_skirt_arc_degrees": 360.0,
        "radial_web_count": len(web_angles),
        "radial_web_thickness": 1.6,
        "radial_web_height": web_height,
        "steep_unsupported_underside_area_mm2": round(unsupported_area, 3),
        "seat_inboard_of_outer_surface": round(recess, 2),
        "light_window": [
            round(corbel_r, 2),
            round(corbel_r + recess - cfg.WALL, 2),
        ],
        "upper_shell_clocking": (
            geometry.joint_clocking_report(upper)
        ),
        "lower_shell_clocking": (
            geometry.lower_clocking_report(lower)
        ),
    }


def world_transform(shell: cfg.Shell) -> np.ndarray:
    matrix = trimesh.transformations.rotation_matrix(
        math.radians(shell.axis_deg), [0.0, 1.0, 0.0]
    )
    matrix[0, 3] = shell.origin[0]
    matrix[2, 3] = shell.origin[1]
    return matrix


def overlap_volume(first: trimesh.Trimesh, second: trimesh.Trimesh) -> float:
    overlap = trimesh.boolean.intersection([first, second], engine="manifold")
    return float(overlap.volume) if len(overlap.faces) else 0.0


def complete_stack_check(
    shells: list[cfg.Shell],
    production_shells: list[trimesh.Trimesh],
    rings: list[trimesh.Trimesh],
) -> dict:
    components: list[tuple[str, trimesh.Trimesh]] = []
    for shell, mesh in zip(shells, production_shells):
        placed = mesh.copy()
        placed.apply_transform(world_transform(shell))
        components.append((f"Shell {shell.key[-1].upper()}", placed))
    for index, ring in enumerate(rings):
        placed = ring.copy()
        placed.apply_transform(world_transform(shells[index + 1]))
        lower = shells[index].key[-1].upper()
        upper = shells[index + 1].key[-1].upper()
        components.append((f"{lower}-{upper} ring", placed))

    collisions = {}
    for first_index, (first_name, first) in enumerate(components):
        for second_name, second in components[first_index + 1 :]:
            collisions[f"{first_name} vs {second_name}"] = round(
                overlap_volume(first, second), 4
            )
    if max(collisions.values()) > 0.01:
        raise RuntimeError(f"complete lamp stack has hidden collisions: {collisions}")
    return {
        "component_count": len(components),
        "pair_count": len(collisions),
        "collision_volume_mm3": collisions,
        "passed": True,
    }


def retained_base_interface_check(
    shell: cfg.Shell,
    thin_shell: trimesh.Trimesh,
) -> dict:
    """Prove the thinner optical wall did not alter the fitted lower 4 mm."""
    reference = production_shell(
        shell,
        add_register=True,
        wall_thickness=cfg.WALL,
    )
    slab = trimesh.creation.box(
        extents=[
            2.0 * (shell.base_radius + 2.0),
            2.0 * (shell.base_radius + 2.0),
            geometry.UPPER_REGISTER_H,
        ]
    )
    slab.apply_translation([0.0, 0.0, geometry.UPPER_REGISTER_H / 2.0])
    reference_base = geometry._intersection([reference, slab])
    thin_base = geometry._intersection([thin_shell, slab])
    common = geometry._intersection([reference_base, thin_base])
    reference_only = max(float(reference_base.volume - common.volume), 0.0)
    thin_only = max(float(thin_base.volume - common.volume), 0.0)
    tolerance = 0.001
    if max(reference_only, thin_only) > tolerance:
        raise RuntimeError(
            "thin Shell C changed its retained base interface: "
            f"reference-only {reference_only:.4f} mm³, "
            f"thin-only {thin_only:.4f} mm³"
        )
    return {
        "height_mm": geometry.UPPER_REGISTER_H,
        "reference_wall_mm": cfg.WALL,
        "optical_wall_mm": SHELL_C_WALL,
        "reference_only_volume_mm3": round(reference_only, 6),
        "thin_only_volume_mm3": round(thin_only, 6),
        "passed": True,
    }


def build_parts(
    fuzzy_style: FuzzyStyle = PRODUCTION_FUZZY_STYLE,
) -> tuple[list[Part], dict]:
    shells = cfg.build_stack()
    parts: list[Part] = []
    shell_reports = []
    shell_walls = [shell_wall_thickness(shell) for shell in shells]
    production_shells = [
        production_shell(
            shell,
            add_register=index > 0,
            wall_thickness=shell_walls[index],
        )
        for index, shell in enumerate(shells)
    ]

    for index, (shell, raw_mesh, wall_thickness) in enumerate(
        zip(shells, production_shells, shell_walls), start=1
    ):
        mesh = centre_on_bed(
            raw_mesh,
            f"Boucle production Shell {shell.key[-1].upper()}",
        )
        paint, paint_report = fuzzy_outer_wall_mask(
            mesh,
            shell,
            wall_thickness=wall_thickness,
            fuzzy_style=fuzzy_style,
        )
        parts.append(
            Part(
                f"Shell {shell.key[-1].upper()} · Bone White fuzzy exterior",
                f"boucle_shell_{shell.key[-1]}.stl",
                mesh,
                index,
                shell_profile(fuzzy_style),
                paint,
            )
        )
        shell_reports.append(
            {
                "shell": shell.key,
                "plate": index,
                "diameter_mm": round(float(np.ptp(mesh.bounds[:, 0])), 2),
                "height_mm": round(float(np.ptp(mesh.bounds[:, 2])), 2),
                "volume_cm3": round(float(mesh.volume) / 1000.0, 2),
                "wall_thickness_mm": wall_thickness,
                "locating_register": index > 1,
                "clocking_notch": (
                    geometry.joint_clocking_report(shell)
                    if index > 1
                    else None
                ),
                "lower_rim_clocking_notch": (
                    geometry.lower_clocking_report(shell)
                    if shell.key in {"shell_a", "shell_b"}
                    else None
                ),
                "fuzzy_paint": paint_report,
            }
        )

    ring_reports = []
    raw_rings = []
    for plate, (lower, upper) in enumerate(zip(shells, shells[1:]), start=4):
        if plate == 5:
            ring, report = compact_bc_ring(lower, upper)
        else:
            ring, report = open_ab_ring(lower, upper)
        upper_solid = production_shells[plate - 3]
        report["fit_validation"] = geometry.check_joint_fit(
            lower, upper, ring, upper_solid
        )
        raw_rings.append(ring.copy())
        ring = centre_on_bed(
            ring,
            f"Boucle production {lower.key[-1].upper()}-{upper.key[-1].upper()} halo ring",
        )
        parts.append(
            Part(
                f"Halo ring {lower.key[-1].upper()}→{upper.key[-1].upper()} · smooth",
                f"boucle_halo_{lower.key[-1]}{upper.key[-1]}.stl",
                ring,
                plate,
                RING_PROFILE,
            )
        )
        ring_reports.append(
            {
                "joint": f"{lower.key[-1].upper()}→{upper.key[-1].upper()}",
                "plate": plate,
                "diameter_mm": round(float(np.ptp(ring.bounds[:, 0])), 2),
                "height_mm": round(float(np.ptp(ring.bounds[:, 2])), 2),
                "volume_cm3": round(float(ring.volume) / 1000.0, 2),
                **report,
            }
        )

    baffle, baffle_report = geometry.build_baffle()
    baffle = centre_on_bed(baffle, "Boucle production LED diffuser baffle")
    parts.append(
        Part(
            "LED diffuser baffle · Jade White",
            "boucle_led_diffuser_baffle.stl",
            baffle,
            6,
            BAFFLE_PROFILE,
            extruder=2,
            filament_id=None,
            filament_hex=DIFFUSER_FILAMENT_HEX,
            filament_profile=DIFFUSER_FILAMENT_PROFILE,
            filament_label=DIFFUSER_FILAMENT_LABEL,
        )
    )
    baffle_report = {
        **baffle_report,
        "plate": 6,
        "volume_cm3": round(float(baffle.volume) / 1000.0, 2),
        "optical_role": "thin glare diffuser; install disc 30 mm above LED",
        "filament": DIFFUSER_FILAMENT_LABEL,
        "filament_profile": DIFFUSER_FILAMENT_PROFILE,
    }

    leg_frame_assembled, leg_frame_report = geometry.build_leg_frame()
    leg_frame = leg_frame_assembled.copy()
    leg_frame.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.pi,
            [1.0, 0.0, 0.0],
        )
    )
    leg_frame = centre_on_bed(
        leg_frame,
        "Boucle production inverted plinth and leg frame",
    )
    parts.append(
        Part(
            "Leg frame · Dark Chocolate",
            "boucle_leg_frame.stl",
            leg_frame,
            7,
            LEG_FRAME_PROFILE,
            extruder=3,
            filament_id=BASE_FILAMENT,
            filament_label=BASE_FILAMENT_LABEL,
        )
    )
    leg_frame_report = {
        **leg_frame_report,
        "plate": 7,
        "diameter_mm": round(
            float(
                max(
                    np.ptp(leg_frame.bounds[:, 0]),
                    np.ptp(leg_frame.bounds[:, 1]),
                )
            ),
            2,
        ),
        "height_mm": round(
            float(np.ptp(leg_frame.bounds[:, 2])), 2
        ),
    }

    cradle, cradle_report = geometry.build_cradle_coupon()
    cradle = centre_on_bed(
        cradle,
        "Boucle production removable LED cradle",
    )
    parts.append(
        Part(
            "LED cradle · Dark Chocolate",
            "boucle_led_cradle.stl",
            cradle,
            8,
            CRADLE_PROFILE,
            extruder=3,
            filament_id=BASE_FILAMENT,
            filament_label=BASE_FILAMENT_LABEL,
        )
    )
    cradle_report = {
        **cradle_report,
        "plate": 8,
        "volume_cm3": round(float(cradle.volume) / 1000.0, 2),
    }

    cradle_assembled = cradle.copy()
    cradle_assembled.apply_translation(
        [0.0, 0.0, cfg.PLINTH_Z0]
    )
    baffle_assembled = baffle.copy()
    baffle_assembled.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.pi,
            [1.0, 0.0, 0.0],
        )
    )
    baffle_assembled.apply_translation(
        [
            0.0,
            0.0,
            (
                cfg.CRADLE_Z1
                + cfg.BAFFLE_POST_H
                + cfg.BAFFLE_WALL
            ),
        ]
    )
    base_cradle_overlap = trimesh.boolean.intersection(
        [leg_frame_assembled, cradle_assembled],
        engine="manifold",
    )
    if len(base_cradle_overlap.faces):
        triangles = base_cradle_overlap.triangles
        base_cradle_overlap_mm3 = abs(
            float(
                np.einsum(
                    "ij,ij->i",
                    triangles[:, 0],
                    np.cross(triangles[:, 1], triangles[:, 2]),
                ).sum()
                / 6.0
            )
        )
        overlap_z_span = float(
            np.ptp(base_cradle_overlap.bounds[:, 2])
        )
    else:
        base_cradle_overlap_mm3 = 0.0
        overlap_z_span = 0.0
    # The flange land and cradle flange share a seating plane. Manifold can
    # report a few mm³ of paper-thin coplanar contact there; ignore that film.
    if (
        base_cradle_overlap_mm3 > 0.01
        and not (
            overlap_z_span < 0.05
            and base_cradle_overlap_mm3 < 10.0
        )
    ):
        raise RuntimeError(
            "leg frame intrudes into removable LED cradle: "
            f"{base_cradle_overlap_mm3:.4f} mm³"
        )
    baffle_cradle_overlap = trimesh.boolean.intersection(
        [baffle_assembled, cradle_assembled],
        engine="manifold",
    )
    if len(baffle_cradle_overlap.faces):
        triangles = baffle_cradle_overlap.triangles
        baffle_cradle_overlap_mm3 = abs(
            float(
                np.einsum(
                    "ij,ij->i",
                    triangles[:, 0],
                    np.cross(triangles[:, 1], triangles[:, 2]),
                ).sum()
                / 6.0
            )
        )
    else:
        baffle_cradle_overlap_mm3 = 0.0
    if baffle_cradle_overlap_mm3 > 0.01:
        raise RuntimeError(
            "diffuser locator pegs interfere with cradle sockets: "
            f"{baffle_cradle_overlap_mm3:.4f} mm³"
        )
    base_validation = {
        **geometry.check_base_interface(shells[0]),
        "base_cradle_collision_volume_mm3": round(
            base_cradle_overlap_mm3, 6
        ),
        "diffuser_cradle_collision_volume_mm3": round(
            baffle_cradle_overlap_mm3, 6
        ),
        "diffuser_locator_clearance_total_mm": round(
            cfg.BAFFLE_SOCKET_DIA - cfg.BAFFLE_LOCATOR_DIA,
            2,
        ),
        "diffuser_locator_bottom_clearance_mm": round(
            cfg.BAFFLE_SOCKET_DEPTH - cfg.BAFFLE_LOCATOR_H,
            2,
        ),
        "cable_phase_deg": cfg.CABLE_PHASE_DEG,
        "passed": True,
    }

    stack_validation = complete_stack_check(shells, production_shells, raw_rings)
    shell_c_interface = retained_base_interface_check(
        shells[2], production_shells[2]
    )
    report = {
        "product": "Bouclé Stack complete ready-to-print lamp",
        "printer": "Bambu Lab P2S, 0.4 mm nozzle",
        "filament": (
            "Bone White Matte shells/rings; Jade White PLA Basic diffuser; "
            "Dark Chocolate Matte leg frame/cradle"
        ),
        "parts": len(parts),
        "plates": len(parts),
        "fuzzy_skin": fuzzy_style.report(),
        "strategy": (
            "One object per plate removes the long inter-object travel moves that "
            "caused strings on the physical coupon plates."
        ),
        "stringing_controls": {
            "objects_per_plate": 1,
            "combined_project_plates": len(parts),
            "retraction_mm": 0.8,
            "retraction_speed_mm_s": 30,
            "retract_on_layer_change": True,
            "wipe_mm": 2.0,
            "avoid_crossing_wall": True,
            "unlimited_wall_avoidance_detour": True,
            "infill_retraction_reduction": (
                "Disabled project-wide in the combined 3MF; "
                "disabled on ring, leg-frame and cradle fallbacks"
            ),
            "prime_tower": False,
        },
        "shells": shell_reports,
        "rings": ring_reports,
        "diffuser_baffle": baffle_report,
        "leg_frame": leg_frame_report,
        "led_cradle": cradle_report,
        "base_validation": base_validation,
        "complete_stack_validation": stack_validation,
        "shell_c_base_interface_validation": shell_c_interface,
        "assembly_order": [
            "Leg frame — print inverted; no sacrificial support removal",
            "Stand the frame on its three feet",
            "Dry-fit LED cradle, diffuser and Shell A — confirm the shell drops into the 1.0 mm seat groove and the cradle flange still passes through Shell A's opening",
            "Remove the cradle and diffuser before bonding",
            "Bond Shell A into the plinth locate groove only — wipe a thin epoxy film on the groove floor; do not glue the cradle",
            "After cure, reinstall the cradle and diffuser through Shell A",
            "A→B halo ring — align its outward skirt tab with Shell A's open rim notch",
            "Shell B — align its inner register notch with the tapered ring tab",
            "B→C halo ring — align its outward skirt tab with Shell B's open rim notch",
            "Shell C — align its inner register notch with the tapered ring tab",
        ],
    }
    return parts, report


def model_settings(parts: list[Part]) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for index, part in enumerate(parts, start=1):
        top_id = 99 + index
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
                f'    <part id="{index}" subtype="normal_part">',
                f'      <metadata key="name" value="{escape(part.label)}"/>',
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'      <metadata key="source_file" value="{escape(part.filename)}"/>',
                f'      <metadata key="source_object_id" value="{index - 1}"/>',
                f'      <metadata key="source_volume_id" value="{index - 1}"/>',
                f'      <metadata key="extruder" value="{part.extruder}"/>',
                f'      <mesh_stat face_count="{len(part.mesh.faces)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                "    </part>",
                "  </object>",
            ]
        )

    for index, part in enumerate(parts, start=1):
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
                f'      <metadata key="object_id" value="{99 + index}"/>',
                '      <metadata key="instance_id" value="0"/>',
                f'      <metadata key="identify_id" value="{299 + index}"/>',
                "    </model_instance>",
                "  </plate>",
            ]
        )

    lines.append("  <assemble>")
    for index in range(1, len(parts) + 1):
        lines.append(
            f'    <assemble_item object_id="{99 + index}" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def plate_preview(part: Part, colour_hex: str) -> bytes:
    colour_hex = colour_hex.lstrip("#")
    size = 512
    image = Image.new("RGB", (size, size), "#ECE9E2")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, size - 24, size - 24), radius=20, fill="#FCFBF8", outline="#76716A", width=3)
    font = ImageFont.load_default()

    low, high = part.mesh.bounds
    width = max(high[0] - low[0], high[1] - low[1], 1.0)
    scale = 360.0 / width
    x0, y0 = size / 2.0, size / 2.0 + 18
    outer = [
        (
            x0 + (x - (low[0] + high[0]) / 2.0) * scale,
            y0 - (y - (low[1] + high[1]) / 2.0) * scale,
        )
        for x, y in part.mesh.vertices[:, :2]
    ]
    draw.ellipse(
        (
            min(point[0] for point in outer),
            min(point[1] for point in outer),
            max(point[0] for point in outer),
            max(point[1] for point in outer),
        ),
        fill=f"#{colour_hex}",
        outline="#655F57",
        width=3,
    )
    if "Halo" in part.label:
        radius = min(
            max(point[0] for point in outer) - min(point[0] for point in outer),
            max(point[1] for point in outer) - min(point[1] for point in outer),
        ) * 0.26
        draw.ellipse(
            (x0 - radius, y0 - radius, x0 + radius, y0 + radius),
            fill="#FCFBF8",
            outline="#655F57",
            width=2,
        )

    draw.text((40, 42), f"Plate {part.plate}", fill="#27231F", font=font)
    draw.text((40, 62), part.label, fill="#27231F", font=font)
    draw.text(
        (40, 446),
        f"{part.filament_label} · one object only",
        fill="#5F5952",
        font=font,
    )
    draw.text((40, 464), "Supports OFF · print in supplied orientation", fill="#5F5952", font=font)
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def validate_project(
    package: zipfile.ZipFile,
    parts: list[Part],
    filament_slots: list[tuple[str, str]],
) -> None:
    bambu.assert_object_id_hygiene(package)
    namespace = {"m": bambu.CORE}
    top = ET.fromstring(package.read("3D/3dmodel.model"))
    top_ids = {
        node.get("id") for node in top.findall("./m:resources/m:object", namespace)
    }
    if top_ids != {str(100 + index) for index in range(len(parts))}:
        raise RuntimeError(f"unexpected top-level 3MF object ids: {top_ids}")

    settings = ET.fromstring(package.read("Metadata/model_settings.config"))
    plate_nodes = settings.findall("./plate")
    if len(plate_nodes) != len(parts):
        raise RuntimeError(
            f"production 3MF contains {len(plate_nodes)} plates; "
            f"expected {len(parts)}"
        )
    for plate in plate_nodes:
        instances = plate.findall("./model_instance")
        if len(instances) != 1:
            raise RuntimeError("every production plate must contain exactly one object")

    object_nodes = settings.findall("./object")
    if len(object_nodes) != len(parts):
        raise RuntimeError("production project object count is inconsistent")
    for node, part in zip(object_nodes, parts):
        extruder = node.find(
            "./metadata[@key='extruder']"
        )
        if (
            extruder is None
            or extruder.get("value") != str(part.extruder)
        ):
            raise RuntimeError(
                f"{part.label} has the wrong filament slot"
            )

    project = json.loads(package.read("Metadata/project_settings.config"))
    expected_infill_retraction = (
        "Disabled"
        if any(
            part.profile.get(
                "reduce_infill_retraction_mode"
            )
            == "Disabled"
            for part in parts
        )
        else parts[0].profile.get(
            "reduce_infill_retraction_mode"
        )
    )
    if (
        expected_infill_retraction is not None
        and project.get("reduce_infill_retraction_mode")
        != expected_infill_retraction
    ):
        raise RuntimeError(
            "production project changed its infill retraction policy"
        )
    filament_profiles = project.get("filament_settings_id")
    expected_profiles = [
        profile for _colour, profile in filament_slots
    ]
    if filament_profiles != expected_profiles:
        raise RuntimeError(
            "production project filament profiles do not match their slots"
        )
    expected_colours = [
        colour for colour, _profile in filament_slots
    ]
    if project.get("filament_colour") != expected_colours:
        raise RuntimeError(
            "production project filament colours do not match their slots"
        )
    slot_count = len(filament_slots)
    for key in (
        "filament_colour_type",
        "filament_density",
        "filament_type",
        "filament_vendor",
    ):
        values = project.get(key)
        if not isinstance(values, list) or len(values) != slot_count:
            raise RuntimeError(
                f"{key} does not cover all filament slots"
            )
    purge_matrix = project.get("flush_volumes_matrix")
    if (
        not isinstance(purge_matrix, list)
        or len(purge_matrix) != slot_count**2
    ):
        raise RuntimeError("production project purge matrix is malformed")
    for part in parts:
        if not 1 <= part.extruder <= len(filament_slots):
            raise RuntimeError(
                f"{part.label} references unavailable filament slot "
                f"{part.extruder}"
            )
    for key in (
        "filament_retraction_length",
        "filament_retraction_speed",
        "filament_deretraction_speed",
        "filament_retract_before_wipe",
        "filament_retract_when_changing_layer",
        "filament_retraction_minimum_travel",
        "filament_retract_restart_extra",
        "filament_wipe",
        "filament_wipe_distance",
    ):
        values = project.get(key)
        if isinstance(values, list) and any(value != "nil" for value in values):
            raise RuntimeError(f"{key} overrides the production travel profile")
    if project.get("curr_bed_type") != "Textured PEI Plate":
        raise RuntimeError("production project does not target Textured PEI Plate")

    for index in range(1, len(parts) + 1):
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
        areas = np.linalg.norm(
            np.cross(
                vertices[faces[:, 1]] - vertices[faces[:, 0]],
                vertices[faces[:, 2]] - vertices[faces[:, 0]],
            ),
            axis=1,
        )
        if np.any(areas <= 1e-10):
            raise RuntimeError(f"object_{index}.model contains zero-area faces")
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        mesh.merge_vertices(digits_vertex=8)
        if not mesh.is_watertight or not mesh.is_volume:
            raise RuntimeError(f"object_{index}.model is not a watertight volume")


def configure_filament_slots(
    settings: dict,
    filament_slots: list[tuple[str, str]],
) -> None:
    """Expand the stock dual-variant P2S arrays for each filament slot."""
    old_profiles = settings.get("filament_settings_id")
    if not isinstance(old_profiles, list) or not old_profiles:
        raise RuntimeError("template has no filament profiles")
    old_count = len(old_profiles)
    slot_keys = {
        "additional_cooling_fan_speed",
        "counter_coef_2",
        "counter_coef_3",
        "counter_limit_max",
        "counter_limit_min",
        "eng_plate_temp",
        "eng_plate_temp_initial_layer",
        "filament_cooling_before_tower",
        "filament_deretraction_speed",
        "filament_end_gcode",
        "filament_extruder_variant",
        "filament_flow_ratio",
        "filament_ids",
        "filament_long_retractions_when_cut",
        "filament_max_volumetric_speed",
        "filament_ramming_travel_time",
        "filament_retract_before_wipe",
        "filament_retract_restart_extra",
        "filament_retract_when_changing_layer",
        "filament_retraction_distances_when_cut",
        "filament_retraction_length",
        "filament_retraction_minimum_travel",
        "filament_retraction_speed",
        "filament_start_gcode",
        "filament_wipe",
        "filament_wipe_distance",
        "filament_z_hop",
        "filament_z_hop_types",
        "first_x_layer_fan_speed",
        "hole_coef_2",
        "hole_coef_3",
        "hole_limit_max",
        "hole_limit_min",
        "long_retractions_when_ec",
        "nozzle_temperature",
        "nozzle_temperature_initial_layer",
        "retraction_distances_when_ec",
        "slow_down_min_speed",
        "supertack_plate_temp",
        "supertack_plate_temp_initial_layer",
    }
    slot_keys.update(
        key
        for key in settings
        if key.startswith("filament_")
        and key not in {"filament_map", "filament_nozzle_map"}
    )
    slot_keys.update(
        """
        activate_air_filtration additional_fan_full_speed_layer
        chamber_temperatures circle_compensation_speed
        close_additional_fan_first_x_layers close_fan_the_first_x_layers
        complete_print_exhaust_fan_speed cool_plate_temp
        cool_plate_temp_initial_layer cooling_perimeter_transition_distance
        cooling_slowdown_logic counter_coef_1 diameter_limit
        during_print_exhaust_fan_speed fan_cooling_layer_time
        fan_max_speed fan_min_speed full_fan_speed_layer hot_plate_temp
        hot_plate_temp_initial_layer impact_strength_z
        no_slow_down_for_cooling_on_outwalls nozzle_temperature_range_high
        nozzle_temperature_range_low overhang_fan_speed
        overhang_fan_threshold overhang_threshold_participating_cooling
        override_process_overhang_speed reduce_fan_stop_start_freq
        required_nozzle_HRC slow_down_for_layer_cooling
        slow_down_layer_time temperature_vitrification textured_plate_temp
        textured_plate_temp_initial_layer volumetric_speed_coefficients
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
            current[
                index * group_size : (index + 1) * group_size
            ]
            for index in range(old_count)
        ]
        expanded = []
        for _colour, profile in filament_slots:
            override = FILAMENT_PROFILE_OVERRIDES.get(
                profile, {}
            ).get(key)
            if override is not None:
                expanded.extend(override)
                continue
            source_index = (
                old_profiles.index(profile)
                if profile in old_profiles
                else 0
            )
            expanded.extend(old_groups[source_index])
        settings[key] = expanded

    variant_count = len(
        settings.get("print_extruder_variant", ["standard"])
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
    settings["filament_ids"] = [
        (
            "GFA00"
            if profile == DIFFUSER_FILAMENT_PROFILE
            else "GFA01"
        )
        for _colour, profile in filament_slots
    ]
    settings["filament_multi_colour"] = [
        colour for colour, _profile in filament_slots
    ]

    # No plate changes filament mid-print, but the project still requires a
    # square purge matrix sized to the configured filament count.
    grid = len(filament_slots)
    settings["flush_volumes_matrix"] = [
        "0" if row == column else "280"
        for row in range(grid)
        for column in range(grid)
    ]
    settings["flush_volumes_vector"] = ["140"] * (grid * 2)


def write_project(
    parts: list[Part],
    out_dir: Path,
    colour_hex: str,
    output_name: str,
    filament_slots: list[tuple[str, str]] | None = None,
    project_title: str = "Bouclé Stack lamp — P2S production",
) -> Path:
    if filament_slots is None:
        filament_profiles = {
            part.filament_profile for part in parts
        }
        if len(filament_profiles) != 1:
            raise RuntimeError(
                "one production project cannot mix filament profiles"
            )
        filament_profile = filament_profiles.pop()
        filament_slots = [
            (colour_hex, filament_profile),
            (colour_hex, filament_profile),
        ]
    for part in parts:
        if not 1 <= part.extruder <= len(filament_slots):
            raise RuntimeError(
                f"{part.label} references missing filament slot "
                f"{part.extruder}"
            )
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
        (
            part.label,
            out_dir / "meshes" / part.filename,
            part.extruder,
        )
        for part in parts
    ]
    bambu.BUILD_POSITIONS = [plate_position(part.plate) for part in parts]

    output_path = out_dir / output_name
    template_path = GENERATOR_DIR / "blank_project.3mf"
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
                (
                    f'<metadata name="Title">{escape(project_title)}</metadata>'
                ).encode(),
            ),
        )
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, part in enumerate(parts, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(part.mesh, index, paint_fuzzy=part.paint),
            )
        output.writestr("Metadata/model_settings.config", model_settings(parts))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        configure_filament_slots(settings, filament_slots)
        fallback_profile = parts[0].profile
        for key, value in fallback_profile.items():
            current = settings.get(key)
            settings[key] = [value] * len(current) if isinstance(current, list) else value
        if any(
            part.profile.get(
                "reduce_infill_retraction_mode"
            )
            == "Disabled"
            for part in parts
        ):
            # Bambu Studio applies this policy project-wide even when it is
            # present in per-object metadata. The combined project contains
            # rings and base parts that require the stricter policy.
            settings[
                "reduce_infill_retraction_mode"
            ] = "Disabled"
        settings["reduce_crossing_wall"] = "1"
        settings["max_travel_detour_distance"] = "0"
        settings["retract_when_changing_layer"] = ["1", "1"]
        settings["retraction_length"] = ["0.8", "0.8"]
        settings["retraction_speed"] = ["30", "30"]
        settings["deretraction_speed"] = ["30", "30"]
        settings["retraction_minimum_travel"] = ["1", "1"]
        settings["retract_before_wipe"] = ["70%", "70%"]
        settings["wipe"] = ["1", "1"]
        settings["wipe_distance"] = ["2", "2"]
        for key in (
            "filament_retraction_length",
            "filament_retraction_speed",
            "filament_deretraction_speed",
            "filament_retract_before_wipe",
            "filament_retract_when_changing_layer",
            "filament_retraction_minimum_travel",
            "filament_retract_restart_extra",
            "filament_wipe",
            "filament_wipe_distance",
        ):
            current = settings.get(key)
            settings[key] = (
                ["nil"] * (2 * len(filament_slots))
                if isinstance(current, list)
                else "nil"
            )
        settings["travel_speed"] = "600"
        settings["print_sequence"] = "by layer"
        settings["brim_object_gap"] = "0.1"
        settings["curr_bed_type"] = "Textured PEI Plate"
        settings["filament_colour"] = [
            colour for colour, _profile in filament_slots
        ]
        settings["default_filament_colour"] = [
            ""
        ] * len(filament_slots)
        settings["filament_settings_id"] = [
            profile for _colour, profile in filament_slots
        ]
        settings["enable_prime_tower"] = "0"
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
            preview = plate_preview(
                part,
                filament_slots[part.extruder - 1][0],
            )
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(f"Metadata/{stem}_{part.plate}.png", preview)

    with zipfile.ZipFile(output_path) as package:
        validate_project(package, parts, filament_slots)
    return output_path


def validate_fuzzy_style(
    project_path: Path,
    parts: list[Part],
    fuzzy_style: FuzzyStyle,
) -> None:
    expected = fuzzy_style.profile_settings()
    with zipfile.ZipFile(project_path) as package:
        project = json.loads(
            package.read("Metadata/project_settings.config")
        )
        for key, value in expected.items():
            if project.get(key) != value:
                raise RuntimeError(
                    f"{project_path.name}: {key} is {project.get(key)!r}; "
                    f"expected {value!r}"
                )

        settings = ET.fromstring(
            package.read("Metadata/model_settings.config")
        )
        object_nodes = settings.findall("./object")
        for node, part in zip(object_nodes[:3], parts[:3]):
            metadata = {
                item.get("key"): item.get("value")
                for item in node.findall("./metadata")
            }
            for key, value in expected.items():
                if metadata.get(key) != value:
                    raise RuntimeError(
                        f"{project_path.name}: {part.label} has "
                        f"{key}={metadata.get(key)!r}; expected {value!r}"
                    )

        namespace = {"m": bambu.CORE}
        for index, part in enumerate(parts[:3], start=1):
            root = ET.fromstring(
                package.read(f"3D/Objects/object_{index}.model")
            )
            painted = root.findall(
                ".//m:triangle[@paint_fuzzy_skin='4']",
                namespace,
            )
            if not painted:
                raise RuntimeError(
                    f"{project_path.name}: {part.label} lost its fuzzy paint"
                )


def generate(out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    for stale in mesh_dir.glob("*.stl"):
        stale.unlink()

    parts, report = build_parts()
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
    filament = resolve_filament(FILAMENT, palette)
    base_filament = resolve_filament(BASE_FILAMENT, palette)
    plate_dir = out_dir / "plates"
    plate_dir.mkdir(parents=True, exist_ok=True)
    for stale in plate_dir.glob("*.3mf"):
        stale.unlink()
    stale_master = out_dir / "Boucle_Stack_Lamp_Shade_P2S.3mf"
    if stale_master.exists():
        stale_master.unlink()
    combined_name = PRODUCTION_FUZZY_STYLE.artifact_name
    combined_path = out_dir / combined_name
    if combined_path.exists():
        combined_path.unlink()

    projects = []
    for part in parts:
        resolved_filament = (
            resolve_filament(part.filament_id, palette)
            if part.filament_id is not None
            else None
        )
        colour_hex = part.filament_hex or (
            resolved_filament.hex
            if resolved_filament is not None
            else None
        )
        if colour_hex is None:
            raise RuntimeError(
                f"{part.label} has no resolvable filament colour"
            )
        filename = (
            f"{part.plate:02d}_"
            f"{part.label.split(' · ')[0].replace(' ', '_').replace('→', '_to_')}_P2S.3mf"
        )
        projects.append(
            write_project(
                [replace(part, plate=1, extruder=1)],
                plate_dir,
                colour_hex,
                filename,
            )
        )
    combined_path = write_project(
        parts,
        out_dir,
        filament.hex,
        combined_name,
        filament_slots=[
            (filament.hex, MATTE_FILAMENT_PROFILE),
            (
                DIFFUSER_FILAMENT_HEX,
                DIFFUSER_FILAMENT_PROFILE,
            ),
            (base_filament.hex, MATTE_FILAMENT_PROFILE),
        ],
    )
    validate_fuzzy_style(
        combined_path,
        parts,
        PRODUCTION_FUZZY_STYLE,
    )
    report["filament_id"] = filament.id
    report["filament_hex"] = filament.hex
    report["filaments"] = {
        "shells_and_rings": {
            "id": filament.id,
            "hex": filament.hex,
            "profile": MATTE_FILAMENT_PROFILE,
        },
        "diffuser": {
            "name": DIFFUSER_FILAMENT_LABEL,
            "hex": DIFFUSER_FILAMENT_HEX,
            "profile": DIFFUSER_FILAMENT_PROFILE,
        },
        "leg_frame_and_cradle": {
            "id": base_filament.id,
            "hex": base_filament.hex,
            "profile": MATTE_FILAMENT_PROFILE,
        },
    }
    report["projects"] = [str(path.relative_to(out_dir)) for path in projects]
    report["combined_project"] = str(
        combined_path.relative_to(out_dir)
    )
    (out_dir / PRODUCTION_FUZZY_STYLE.report_name).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return [combined_path, *projects]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for project in generate(args.out):
        print(project)
