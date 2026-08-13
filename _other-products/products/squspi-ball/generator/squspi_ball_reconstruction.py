#!/usr/bin/env python3
"""Stage-one Squspi ball reconstruction and fit-coupon generator.

The supplied files are tessellated STL/3MF exports rather than editable CAD.
This module establishes clean, centred reference masters, records measurable
interfaces, and generates the coupons needed before replacing each reference
with a parametric model.

All dimensions are millimetres.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon, box

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ogma import assets  # noqa: E402

from ogma import bambu_project as bambu  # noqa: E402


@dataclass(frozen=True)
class R188Bearing:
    bore_diameter: float = 6.35
    outer_diameter: float = 12.70
    width: float = 4.7625


@dataclass(frozen=True)
class CouponParams:
    housing_diameters: tuple[float, ...] = (12.55, 12.65, 12.75)
    shaft_diameters: tuple[float, ...] = (6.20, 6.30, 6.40)
    running_clearances: tuple[float, ...] = (0.40, 0.50, 0.60)
    link_neck_multipliers: tuple[float, ...] = (1.00, 1.20, 1.30)
    selected_housing_diameter: float = 12.75
    selected_shaft_diameter: float = 6.40
    selected_axial_clearance: float = 0.30
    axial_clearances: tuple[float, ...] = (0.10, 0.20, 0.30)
    pin_head_diameters: tuple[float, ...] = (2.35, 2.45, 2.55)
    socket_diameters: tuple[float, ...] = (2.15, 2.20, 2.25)
    experimental_pin_head_diameter: float = 2.35
    experimental_socket_diameter: float = 2.20
    experimental_socket_slit: float = 0.60
    compliant_socket_slots: tuple[float, ...] = (0.60, 0.80, 1.00)


R188 = R188Bearing()
COUPONS = CouponParams()

MASTER_PATTERNS = {
    "link": "obj_1_*.stl",
    "button": "obj_7_*.stl",
    "base": "obj_8_*.stl",
    "panel": "obj_11_*.stl",
}

# Positive-radius half-section extracted from the axisymmetric source button.
# The profile is intentionally explicit and editable; revolving it reproduces
# the source to within roughly 0.02 mm while exposing every functional ledge.
BUTTON_PROFILE_RZ = (
    (0.000, 0.000),
    (2.200, 0.000),
    (3.200, 1.000),
    (3.200, 3.900),
    (4.200, 4.900),
    (12.307, 4.900),
    (12.307, 4.650),
    (11.555, 3.900),
    (12.755, 3.900),
    (12.757, 4.900),
    (11.320, 5.689),
    (10.162, 6.241),
    (8.480, 6.918),
    (6.712, 7.481),
    (5.028, 7.889),
    (3.504, 7.889),
    (3.101, 7.547),
    (0.000, 7.547),
    (0.000, 0.000),
)

# The panel's dominant body is a four-millimetre spherical shell. The source
# outer face fits a 25.000 mm sphere and the inner face a 21.000 mm sphere.
# Different inner/outer elevation limits reproduce the source's closed edge
# walls rather than pretending the panel is a constant-angle cut.
PANEL_SPHERE_OUTER_RADIUS = 25.0
PANEL_SPHERE_INNER_RADIUS = 21.0
PANEL_SPHERE_CENTRE = (18.1581, 0.0, -0.25)
PANEL_OUTER_ELEVATION = (0.5726, 49.9677)
PANEL_INNER_ELEVATION = (8.4283, 58.0546)
PANEL_OUTER_HALF_SPAN = (
    (0.5726, 14.0),
    (5.0, 18.0),
    (10.0, 22.0),
    (15.0, 29.0),
    (40.0, 29.0),
    (40.1, 19.0),
    (49.9677, 19.0),
)
PANEL_INNER_HALF_SPAN = (
    (8.4283, 24.0),
    (10.0, 27.3),
    (40.0, 26.9),
    (45.0, 19.0),
    (58.0546, 19.0),
)
PANEL_SOCKET_CENTRES_XZ = ((-4.75476, 2.15001), (3.920, 17.250))
PANEL_SOCKET_DIAMETER = 2.20
PANEL_LOWER_POCKET_MEASURED_DIAMETER = 2.19725
PANEL_LOWER_POCKET_BOTTOM_Y = 4.00001
PANEL_LOWER_POCKET_MOUTH_Y = (2.678, 2.919)
PANEL_LOWER_POCKET_MIN_WALL = 0.480
PANEL_UPPER_POCKET_AXIS_BOTTOM_Y = 3.84496
PANEL_UPPER_POCKET_MOUTH_Y = 4.90
PANEL_UPPER_POCKET_LOCAL_NORMAL = (0.326, 0.946, 0.0)
SOURCE_LINK_PIN_CENTRES_XZ = ((-2.890, 1.393), (-2.890, 6.393))
SOURCE_SECTOR_SECOND_PANEL_ANGLE_DEG = -106.5
LINK_PIN_SWEEP_PROFILE = (
    # (positive Y, X centre, equivalent radius)
    (2.5500, -2.9080, 1.0020),
    (2.6500, -2.9077, 1.0019),
    (2.7500, -2.8967, 1.0019),
    (3.0000, -2.8691, 1.0020),
    (3.1000, -2.9018, 0.9749),
    (3.2000, -2.9436, 0.9165),
    (3.3000, -2.9268, 0.8175),
    (3.4000, -2.9043, 0.7158),
    (3.5000, -2.8820, 0.6142),
    (3.6000, -2.8596, 0.5128),
    (3.6500, -2.8485, 0.4621),
    (3.7000, -2.9550, 0.3363),
    (3.7200, -3.0410, 0.2409),
    (3.7400, -3.1350, 0.1140),
)

# Central X/Z section of the four-millimetre link core, centred on its source
# bounds. Snap pins are added separately along Y.
LINK_CORE_PROFILE_XZ = (
    (-2.695, 2.459),
    (-1.130, 2.239),
    (-1.130, 0.078),
    (3.147, 0.000),
    (3.147, 2.346),
    (4.701, 2.346),
    (4.701, 6.746),
    (0.201, 6.746),
    (0.201, 5.546),
    (1.601, 5.546),
    (2.201, 4.946),
    (2.201, 3.746),
    (-1.143, 3.746),
    (-1.143, 3.546),
    (-1.145, 4.289),
    (-1.112, 5.108),
    (-1.154, 5.108),
    (-1.154, 7.108),
    (-4.077, 7.108),
    (-4.375, 6.842),
    (-4.701, 6.400),
    (-4.701, 2.679),
    (-4.259, 2.679),
)

BASE_ARM_PROFILE_RZ = (
    (7.45, 0.00),
    (11.22, 2.21),
    (12.25, 2.50),
    (16.94, 2.50),
    (17.81, 3.00),
    (17.94, 3.50),
    (17.34, 4.50),
    (16.24, 5.50),
    (15.00, 6.50),
    (14.30, 7.00),
    (13.56, 7.50),
    (7.45, 7.50),
)

BASE_BORE_PROFILE_RZ = (
    (0.00, -0.50),
    (2.10, -0.50),
    (2.10, 1.60),
    (5.398, 1.60),
    (5.398, 1.80),
    (6.240, 1.80),
    (6.240, 3.50),
    (6.290, 3.50),
    (6.290, 6.50),
    (6.400, 6.50),
    (6.400, 7.00),
    (6.900, 7.50),
    (6.900, 8.00),
    (0.00, 8.00),
)

BASE_UPPER_ANNULUS_PROFILE_RZ = (
    (0.00, 5.50),
    (8.50, 5.50),
    (13.42, 6.50),
    (13.92, 7.00),
    (13.56, 7.50),
    (0.00, 7.50),
)
BASE_ARM_ANGLES_DEG = (30.0, 90.0, 150.0, 210.0, 270.0, 330.0)
BASE_PEG_LOCAL_CENTRE = (14.76, 2.59, 4.00)
BASE_PEG_LOCAL_AXIS = (-0.150, 0.989, 0.0)
BASE_PEG_FULL_DIAMETER_LENGTH = 0.65
BASE_PEG_RETENTION_DIAMETERS = (2.25, 2.30, 2.35)
BASE_PEG_PROCESS_DIAMETERS = (2.20, 2.30, 2.40, 2.50)

# Compact twin-rail integration. The first full-width saddle was rejected
# because it visibly replaced too much of the source panel. This version fills
# only the two source upper blind pockets and cuts two short channels inside a
# tightly bounded connector mask. The hinge axis remains 4.50 mm inward, where
# an Ø4.40 mm boss clears the untouched spherical shell.
REAL_KEYED_SOURCE_POCKET_XZ = (3.920, 17.250)
REAL_KEYED_PANEL_INWARD_OFFSET = 4.50
REAL_KEYED_FIXED_EAR_DIAMETER = 1.85
REAL_KEYED_RUNNING_HOLE_DIAMETER = 1.90
TWIN_RAIL_COUPON_TONGUE_HOLE_DIAMETER = 2.05
TWIN_RAIL_COUPON_TONGUE_ENTRY_DIAMETER = 2.40
TWIN_RAIL_COUPON_TONGUE_CHAMFER_DEPTH = 0.50
TWIN_RAIL_LATCH_HOOK_RADII = (0.32, 0.36, 0.40)
TWIN_RAIL_LATCH_BEAM_WIDTH = 0.65
TWIN_RAIL_LATCH_BEAM_HEIGHT = 0.90
TWIN_RAIL_LATCH_BEAM_LENGTH = 4.15
HOOK_RAIL_DIAMETER = 3.00
HOOK_RAIL_RUNNING_CLEARANCE = 0.20
HOOK_RAIL_HOOK_OUTER_RADIUS = 3.00
HOOK_RAIL_HOOK_U_RANGE = (3.75, 7.40)
HOOK_RAIL_MOUTH_WIDTH = 2.65
HOOK_RAIL_ENTRY_WIDTH = 3.30
HOOK_RAIL_CAP_DIAMETER = 4.10
HOOK_RAIL_SUPPORT_INNER_U = 9.05
HOOK_RAIL_OUTER_U = 10.55
HOOK_RAIL_SUPPORT_AXIAL_EMBED = (
    HOOK_RAIL_OUTER_U - HOOK_RAIL_SUPPORT_INNER_U
)
HOOK_RAIL_INTEGRATION_RAIL_U_RANGE = (2.39, 8.21)
HOOK_RAIL_INTEGRATION_ROOT_U_RANGE = (2.40, 3.70)
HOOK_RAIL_INTEGRATION_CAP_U_RANGE = (7.50, 8.20)
# Whole-base inversion after the cropped-arm trial proved unassemblable. The
# source assembly uses the panel's narrow lower connector at the base; the
# broad upper connector belongs to the link. Flexible hooks therefore live on
# all six Tough+ base arms and rigid rails replace only the lower panel pockets.
FULL_BASE_HOOK_U_RANGE = (1.40, 3.20)
FULL_BASE_HOOK_MOUTH_WIDTH = 2.45
FULL_BASE_HOOK_ENTRY_WIDTH = 3.10
FULL_BASE_HOOK_ROOT_HALF_V = 0.90
FULL_BASE_HOOK_ROOT_W_RANGE = (-3.40, -1.60)
FULL_BASE_PANEL_RAIL_U_RANGE = (1.10, 4.10)
FULL_BASE_PANEL_RAIL_ROOT_U_RANGE = (3.40, 4.10)
FULL_BASE_PANEL_RAIL_ROOT_RADIUS = 2.10
FULL_BASE_PANEL_HOOK_CAVITY_U_RANGE = (1.20, 3.35)
FULL_BASE_PANEL_HOOK_CAVITY_RADIUS = 3.55
FULL_BASE_CLEARANCE_BORE_U_RANGE = (1.00, 4.25)
FULL_BASE_CLEARANCE_OPENING_U_RANGE = (0.95, 3.40)
FULL_BASE_CLEARANCE_ROOT_U_RANGE = (3.30, 4.25)
FULL_BASE_ASSEMBLY_ANGLE_DEG = 30.0
FULL_BASE_COLLISION_FREE_DEGREES = (20, 45)
REAL_KEYED_BASE_HINGE_CENTRE = (0.0, 14.76, 4.00)
REAL_KEYED_COLLISION_FREE_DEGREES = (-45, 75)
REAL_KEYED_STOP_CLEARANCE = 0.015
REAL_KEYED_UPPER_POCKET_BOTTOM = (3.655377, 3.936086, 17.250005)
REAL_KEYED_UPPER_POCKET_MOUTH = (3.980945, 4.881605, 17.250006)
REAL_KEYED_RAIL_CENTRE_U = 3.95
REAL_KEYED_CHANNEL_V_RANGE = (-5.00, 0.20)
REAL_KEYED_CHANNEL_W_RANGE = (-0.30, 2.30)
REAL_KEYED_CHANNEL_TAIL_WIDTH = 3.30
REAL_KEYED_CHANNEL_THROAT_WIDTH = 2.40
REAL_KEYED_PRIMARY_KEY_V_RANGE = (-4.985, -0.185)
REAL_KEYED_FOLLOWER_KEY_V_RANGE = (-4.835, -0.185)
REAL_KEYED_KEY_W_RANGE = (-0.05, 2.05)
REAL_KEYED_PRIMARY_KEY_WIDTHS = (3.00, 2.00)
REAL_KEYED_FOLLOWER_KEY_WIDTHS = (2.80, 1.80)
REAL_KEYED_LATCH_CENTRE = (5.42, -4.35, 0.45)
REAL_KEYED_LATCH_TOOTH_RADIUS = 0.35
REAL_KEYED_LATCH_NOTCH_RADIUS = 0.50
REAL_KEYED_EAR_CENTRE_U = 3.20
REAL_KEYED_EAR_OUTER_RADIUS = 2.18
REAL_KEYED_BASE_BOSS_RADIUS = 2.25


def _union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    result = trimesh.boolean.union(meshes, engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    result.merge_vertices()
    result.remove_unreferenced_vertices()
    result.fix_normals()
    return result


def _difference(
    mesh: trimesh.Trimesh,
    cutters: list[trimesh.Trimesh],
) -> trimesh.Trimesh:
    result = trimesh.boolean.difference([mesh, *cutters], engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    result.merge_vertices()
    result.remove_unreferenced_vertices()
    result.fix_normals()
    return result


def _intersection(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    result = trimesh.boolean.intersection(meshes, engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    result.merge_vertices()
    result.remove_unreferenced_vertices()
    result.fix_normals()
    return result


def _box(
    size: tuple[float, float, float],
    centre: tuple[float, float, float],
) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation(centre)
    return mesh


def _cylinder(
    diameter: float,
    height: float,
    centre: tuple[float, float, float],
    *,
    sections: int = 96,
) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(
        radius=diameter / 2,
        height=height,
        sections=sections,
    )
    mesh.apply_translation(centre)
    return mesh


def _rounded_prism(
    width: float,
    depth: float,
    height: float,
    radius: float,
    *,
    z0: float = 0.0,
) -> trimesh.Trimesh:
    polygon = box(
        -width / 2 + radius,
        -depth / 2 + radius,
        width / 2 - radius,
        depth / 2 - radius,
    ).buffer(radius, resolution=10)
    mesh = trimesh.creation.extrude_polygon(
        polygon,
        height=height,
        engine="earcut",
    )
    mesh.apply_translation([0.0, 0.0, z0])
    return mesh


def _extrude_xz(polygon: Polygon, depth: float) -> trimesh.Trimesh:
    """Extrude an X/Z polygon symmetrically along Y."""
    mesh = trimesh.creation.extrude_polygon(
        polygon,
        height=depth,
        engine="earcut",
    )
    mesh.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
    )
    mesh.apply_translation([0.0, depth / 2, 0.0])
    return mesh


def _cone_between(
    radius: float,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> trimesh.Trimesh:
    start_v = np.asarray(start, dtype=float)
    end_v = np.asarray(end, dtype=float)
    vector = end_v - start_v
    length = float(np.linalg.norm(vector))
    mesh = trimesh.creation.cone(radius=radius, height=length, sections=48)
    transform = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], vector)
    mesh.apply_transform(transform)
    mesh.apply_translation(start_v)
    return mesh


def _frustum_between(
    start_radius: float,
    end_radius: float,
    start: np.ndarray,
    end: np.ndarray,
    *,
    sections: int = 64,
) -> trimesh.Trimesh:
    """Create a closed truncated cone between two arbitrary points."""
    start_v = np.asarray(start, dtype=float)
    end_v = np.asarray(end, dtype=float)
    vector = end_v - start_v
    length = float(np.linalg.norm(vector))
    profile = np.asarray(
        [
            [0.0, 0.0],
            [start_radius, 0.0],
            [end_radius, length],
            [0.0, length],
        ]
    )
    mesh = trimesh.creation.revolve(profile, sections=sections)
    mesh.apply_transform(
        trimesh.geometry.align_vectors([0.0, 0.0, 1.0], vector)
    )
    mesh.apply_translation(start_v)
    return mesh


def _positive_volume_components(mesh: trimesh.Trimesh) -> list[trimesh.Trimesh]:
    cleaned = mesh.copy()
    cleaned.process(validate=True)
    cleaned.merge_vertices()
    cleaned.update_faces(cleaned.nondegenerate_faces())
    cleaned.remove_unreferenced_vertices()
    components = [
        component
        for component in cleaned.split(only_watertight=False)
        if component.is_volume and abs(component.volume) > 1e-4
    ]
    return sorted(components, key=lambda item: abs(item.volume), reverse=True)


def load_reference(path: Path) -> trimesh.Trimesh:
    """Load one source STL, remove zero-volume debris, and centre it on Z=0."""
    raw = trimesh.load_mesh(path, process=False)
    components = _positive_volume_components(raw)
    if not components:
        raise ValueError(f"{path.name} contains no positive-volume component")
    mesh = components[0] if len(components) == 1 else _union(components)
    centre_xy = (mesh.bounds[0, :2] + mesh.bounds[1, :2]) / 2
    mesh.apply_translation([-centre_xy[0], -centre_xy[1], -mesh.bounds[0, 2]])
    mesh.metadata["name"] = path.stem
    return mesh


def validate_mesh(name: str, mesh: trimesh.Trimesh) -> dict:
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight:
        raise ValueError(f"{name} is not watertight")
    if not mesh.is_volume:
        raise ValueError(f"{name} is not a positive volume")
    return {
        "name": name,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "volume_mm3": round(float(abs(mesh.volume)), 3),
        "surface_area_mm2": round(float(mesh.area), 3),
        "bounds_mm": {
            "min": [round(float(value), 4) for value in mesh.bounds[0]],
            "max": [round(float(value), 4) for value in mesh.bounds[1]],
            "size": [round(float(value), 4) for value in mesh.extents],
        },
    }


def radial_profile(
    mesh: trimesh.Trimesh,
    *,
    sample_count: int = 40,
) -> list[dict[str, float]]:
    """Record robust radial extrema by Z band for near-axisymmetric parts."""
    vertices = mesh.vertices
    radii = np.linalg.norm(vertices[:, :2], axis=1)
    levels = np.linspace(mesh.bounds[0, 2], mesh.bounds[1, 2], sample_count + 1)
    profile: list[dict[str, float]] = []
    for low, high in zip(levels[:-1], levels[1:]):
        selected = (vertices[:, 2] >= low) & (vertices[:, 2] <= high)
        if not selected.any():
            continue
        values = radii[selected]
        profile.append(
            {
                "z": round(float((low + high) / 2), 4),
                "radius_p05": round(float(np.percentile(values, 5)), 4),
                "radius_p95": round(float(np.percentile(values, 95)), 4),
            }
        )
    return profile


def build_parametric_button_baseline() -> trimesh.Trimesh:
    """Revolve the measured button half-section into an editable baseline."""
    mesh = trimesh.creation.revolve(
        np.asarray(BUTTON_PROFILE_RZ),
        sections=192,
    )
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    mesh.metadata["name"] = "Parametric baseline button"
    return mesh


def build_parametric_panel_shell() -> trimesh.Trimesh:
    """Build the measured concentric spherical core without interface lugs."""
    azimuth_steps = 96
    elevation_steps = 80
    vertices: list[list[float]] = []

    def surface(
        radius: float,
        elevation_bounds: tuple[float, float],
        half_span_profile: tuple[tuple[float, float], ...],
    ) -> None:
        for elevation in np.linspace(*elevation_bounds, elevation_steps):
            el = math.radians(float(elevation))
            half_span = float(
                np.interp(
                    elevation,
                    [item[0] for item in half_span_profile],
                    [item[1] for item in half_span_profile],
                )
            )
            for azimuth in np.linspace(-half_span, half_span, azimuth_steps):
                # The panel faces toward negative X; zero azimuth is its centre.
                az = math.radians(float(azimuth))
                x = PANEL_SPHERE_CENTRE[0] - radius * math.cos(el) * math.cos(az)
                y = PANEL_SPHERE_CENTRE[1] + radius * math.cos(el) * math.sin(az)
                z = PANEL_SPHERE_CENTRE[2] + radius * math.sin(el)
                vertices.append([x, y, z])

    surface(
        PANEL_SPHERE_OUTER_RADIUS,
        PANEL_OUTER_ELEVATION,
        PANEL_OUTER_HALF_SPAN,
    )
    surface(
        PANEL_SPHERE_INNER_RADIUS,
        PANEL_INNER_ELEVATION,
        PANEL_INNER_HALF_SPAN,
    )

    stride = azimuth_steps * elevation_steps
    faces: list[list[int]] = []

    def index(surface_index: int, elevation_index: int, azimuth_index: int) -> int:
        return (
            surface_index * stride
            + elevation_index * azimuth_steps
            + azimuth_index
        )

    for elevation_index in range(elevation_steps - 1):
        for azimuth_index in range(azimuth_steps - 1):
            outer_a = index(0, elevation_index, azimuth_index)
            outer_b = index(0, elevation_index, azimuth_index + 1)
            outer_c = index(0, elevation_index + 1, azimuth_index + 1)
            outer_d = index(0, elevation_index + 1, azimuth_index)
            faces.extend(
                [
                    [outer_a, outer_b, outer_c],
                    [outer_a, outer_c, outer_d],
                ]
            )
            inner_a = index(1, elevation_index, azimuth_index)
            inner_b = index(1, elevation_index + 1, azimuth_index)
            inner_c = index(1, elevation_index + 1, azimuth_index + 1)
            inner_d = index(1, elevation_index, azimuth_index + 1)
            faces.extend(
                [
                    [inner_a, inner_b, inner_c],
                    [inner_a, inner_c, inner_d],
                ]
            )

    # Close low/high elevation edges and both azimuth sides.
    for azimuth_index in range(azimuth_steps - 1):
        next_azimuth = azimuth_index + 1
        for elevation_index, reverse in ((0, True), (elevation_steps - 1, False)):
            outer_a = index(0, elevation_index, azimuth_index)
            outer_b = index(0, elevation_index, next_azimuth)
            inner_a = index(1, elevation_index, azimuth_index)
            inner_b = index(1, elevation_index, next_azimuth)
            pair = (
                [[outer_a, inner_b, outer_b], [outer_a, inner_a, inner_b]]
                if reverse
                else [[outer_a, outer_b, inner_b], [outer_a, inner_b, inner_a]]
            )
            faces.extend(pair)

    for elevation_index in range(elevation_steps - 1):
        next_elevation = elevation_index + 1
        for azimuth_index, reverse in ((0, False), (azimuth_steps - 1, True)):
            outer_a = index(0, elevation_index, azimuth_index)
            outer_b = index(0, next_elevation, azimuth_index)
            inner_a = index(1, elevation_index, azimuth_index)
            inner_b = index(1, next_elevation, azimuth_index)
            pair = (
                [[outer_a, inner_b, outer_b], [outer_a, inner_a, inner_b]]
                if reverse
                else [[outer_a, outer_b, inner_b], [outer_a, inner_b, inner_a]]
            )
            faces.extend(pair)

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices),
        faces=np.asarray(faces),
        process=True,
    )
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    mesh.metadata["name"] = "Parametric panel spherical core"
    return mesh


def _spherical_shell_patch(
    inner_radius: float,
    outer_radius: float,
    azimuth_bounds: tuple[float, float],
    elevation_bounds: tuple[float, float],
    *,
    azimuth_steps: int = 32,
    elevation_steps: int = 32,
) -> trimesh.Trimesh:
    """Create one closed constant-angle spherical shell patch."""
    vertices = []
    for radius in (outer_radius, inner_radius):
        for elevation in np.linspace(*elevation_bounds, elevation_steps):
            el = math.radians(float(elevation))
            for azimuth in np.linspace(*azimuth_bounds, azimuth_steps):
                az = math.radians(float(azimuth))
                vertices.append(
                    [
                        PANEL_SPHERE_CENTRE[0]
                        - radius * math.cos(el) * math.cos(az),
                        radius * math.cos(el) * math.sin(az),
                        PANEL_SPHERE_CENTRE[2] + radius * math.sin(el),
                    ]
                )
    stride = azimuth_steps * elevation_steps
    faces = []

    def vertex(surface: int, elevation: int, azimuth: int) -> int:
        return surface * stride + elevation * azimuth_steps + azimuth

    for elevation in range(elevation_steps - 1):
        for azimuth in range(azimuth_steps - 1):
            a = vertex(0, elevation, azimuth)
            b = vertex(0, elevation, azimuth + 1)
            c = vertex(0, elevation + 1, azimuth + 1)
            d = vertex(0, elevation + 1, azimuth)
            faces.extend([[a, b, c], [a, c, d]])
            a = vertex(1, elevation, azimuth)
            b = vertex(1, elevation + 1, azimuth)
            c = vertex(1, elevation + 1, azimuth + 1)
            d = vertex(1, elevation, azimuth + 1)
            faces.extend([[a, b, c], [a, c, d]])
    for elevation, reverse in ((0, True), (elevation_steps - 1, False)):
        for azimuth in range(azimuth_steps - 1):
            oa = vertex(0, elevation, azimuth)
            ob = vertex(0, elevation, azimuth + 1)
            ia = vertex(1, elevation, azimuth)
            ib = vertex(1, elevation, azimuth + 1)
            faces.extend(
                [[oa, ib, ob], [oa, ia, ib]]
                if reverse
                else [[oa, ob, ib], [oa, ib, ia]]
            )
    for azimuth, reverse in ((0, False), (azimuth_steps - 1, True)):
        for elevation in range(elevation_steps - 1):
            oa = vertex(0, elevation, azimuth)
            ob = vertex(0, elevation + 1, azimuth)
            ia = vertex(1, elevation, azimuth)
            ib = vertex(1, elevation + 1, azimuth)
            faces.extend(
                [[oa, ib, ob], [oa, ia, ib]]
                if reverse
                else [[oa, ob, ib], [oa, ib, ia]]
            )
    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices),
        faces=np.asarray(faces),
        process=True,
    )
    mesh.fix_normals()
    return mesh


def build_parametric_panel_baseline() -> trimesh.Trimesh:
    """Add the two measured interface rails and four local sockets.

    The source also has a roughly 0.8–1.2 mm raised spherical lip near the
    outer edge. Baking that lip into the shell outer surface remains a
    separate refinement; booleaning thin spherical patches onto the current
    shell produces non-manifold unions under Manifold.
    """
    shell = build_parametric_panel_shell()
    rail_path = LineString(PANEL_SOCKET_CENTRES_XZ)
    rail_profile = rail_path.buffer(
        1.20,
        cap_style="round",
        join_style="round",
        resolution=16,
    )
    rails = []
    for y in (-4.0, 4.0):
        rail = _extrude_xz(rail_profile, 1.20)
        rail.apply_translation([0.0, y, 0.0])
        rails.append(rail)
    body = _union([shell, *rails])
    socket_cutters = []
    for x, z in PANEL_SOCKET_CENTRES_XZ:
        for y in (-4.0, 4.0):
            socket_cutters.append(
                trimesh.creation.cylinder(
                    radius=PANEL_SOCKET_DIAMETER / 2,
                    segment=np.asarray(
                        [
                            [x, y - 1.0, z],
                            [x, y + 1.0, z],
                        ]
                    ),
                    sections=64,
                )
            )
    mesh = _difference(body, socket_cutters)
    mesh.metadata["name"] = "Parametric baseline panel"
    return mesh


def build_source_envelope_panel(
    source_link: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Panel shell cleared by the source link's two proven pivot envelopes.

    The spherical body remains parameter-driven, but the functional joint is
    cut from the exact cleaned source link in both validated configurations.
    This preserves the blind-pocket/body clearance without pretending the
    earlier through-ring reconstruction was source-equivalent.
    """
    shell = build_parametric_panel_shell()
    rail_path = LineString(PANEL_SOCKET_CENTRES_XZ)
    rail_profile = rail_path.buffer(
        1.20,
        cap_style="round",
        join_style="round",
        resolution=16,
    )
    rails = []
    for y in (-4.0, 4.0):
        rail = _extrude_xz(rail_profile, 1.20)
        rail.apply_translation([0.0, y, 0.0])
        rails.append(rail)
    body = _union([shell, *rails])

    panel_socket = np.asarray(
        [PANEL_SOCKET_CENTRES_XZ[0][0], 0.0, PANEL_SOCKET_CENTRES_XZ[0][1]]
    )
    lower_pin = np.asarray(
        [
            SOURCE_LINK_PIN_CENTRES_XZ[0][0],
            0.0,
            SOURCE_LINK_PIN_CENTRES_XZ[0][1],
        ]
    )
    upper_pin = np.asarray(
        [
            SOURCE_LINK_PIN_CENTRES_XZ[1][0],
            0.0,
            SOURCE_LINK_PIN_CENTRES_XZ[1][1],
        ]
    )

    # Invert each validated panel placement to express the stationary source
    # link as a cutter in panel-local coordinates.
    upper_configuration = source_link.copy()
    upper_configuration.apply_translation(panel_socket - upper_pin)

    lower_configuration = source_link.copy()
    lower_configuration.apply_translation(-lower_pin)
    lower_configuration.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(-SOURCE_SECTOR_SECOND_PANEL_ANGLE_DEG),
            [0.0, 1.0, 0.0],
        )
    )
    lower_configuration.apply_translation(panel_socket)

    swept_joint = _union([upper_configuration, lower_configuration])
    panel = _difference(body, [swept_joint])
    panel.metadata["name"] = "Source-envelope reconstructed panel"
    return panel


def build_parametric_link_baseline() -> trimesh.Trimesh:
    """Extrude the measured core and add four mirrored tapered snap pins."""
    profile = Polygon(LINK_CORE_PROFILE_XZ)
    core = _extrude_xz(profile, 4.0)
    # The rounded root is full-width while the neck remains four millimetres.
    # Clip 0.0001 mm inside the profile to avoid a line fragment in Shapely's
    # intersection result.
    root_result = profile.intersection(box(-10.0, -10.0, -1.1301, 10.0))
    root_polygons = [
        item
        for item in getattr(root_result, "geoms", [root_result])
        if isinstance(item, Polygon) and item.area > 1e-6
    ]
    root = _extrude_xz(max(root_polygons, key=lambda item: item.area), 7.5)
    pins = []
    for side in (-1.0, 1.0):
        for z in (1.35, 6.35):
            pins.append(
                _cone_between(
                    1.0,
                    (-2.75, side * 1.80, z),
                    (-3.10, side * 3.75, z),
                )
            )
    mesh = _union([core, root, *pins])
    mesh.metadata["name"] = "Parametric baseline link"
    return mesh


def _measured_pin_sweep(
    *,
    centre_z: float,
    side: float,
    sections: int = 96,
) -> trimesh.Trimesh:
    """Build one measured tapered link pin along positive or negative Y."""
    vertices: list[list[float]] = []
    for y, centre_x, radius in LINK_PIN_SWEEP_PROFILE:
        for angle in np.linspace(0.0, 2.0 * math.pi, sections, endpoint=False):
            vertices.append(
                [
                    centre_x + radius * math.cos(float(angle)),
                    side * y,
                    centre_z + radius * math.sin(float(angle)),
                ]
            )

    faces: list[list[int]] = []
    ring_count = len(LINK_PIN_SWEEP_PROFILE)
    for ring_index in range(ring_count - 1):
        first = ring_index * sections
        second = (ring_index + 1) * sections
        for index in range(sections):
            next_index = (index + 1) % sections
            faces.extend(
                [
                    [first + index, first + next_index, second + next_index],
                    [first + index, second + next_index, second + index],
                ]
            )

    start_center_index = len(vertices)
    start_y, start_x, _ = LINK_PIN_SWEEP_PROFILE[0]
    vertices.append([start_x, side * start_y, centre_z])
    end_center_index = len(vertices)
    vertices.append([-3.15, side * 3.75098, centre_z])
    last_ring = (ring_count - 1) * sections
    for index in range(sections):
        next_index = (index + 1) % sections
        faces.append([start_center_index, next_index, index])
        faces.append(
            [
                end_center_index,
                last_ring + index,
                last_ring + next_index,
            ]
        )

    pin = trimesh.Trimesh(
        vertices=np.asarray(vertices),
        faces=np.asarray(faces),
        process=True,
    )
    pin.merge_vertices()
    pin.remove_unreferenced_vertices()
    pin.fix_normals()
    return pin


def build_source_core_parametric_pin_link(
    source_link: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Preserve the exact central body while replacing only four pin sweeps."""
    core_clip = _box((20.0, 5.24, 20.0), (0.0, 0.0, 10.0))
    core = _intersection([source_link, core_clip])
    pins = [
        _measured_pin_sweep(centre_z=centre_z, side=side)
        for _, centre_z in SOURCE_LINK_PIN_CENTRES_XZ
        for side in (-1.0, 1.0)
    ]
    link = _union([core, *pins])
    link.metadata["name"] = "Source-core parametric-pin link"
    return link


def build_parametric_base_baseline() -> trimesh.Trimesh:
    """Build the stepped hub, upper annulus, and six radial arm ribs."""
    lower_hub = _cylinder(15.20, 6.5, (0.0, 0.0, 3.25), sections=192)
    upper_annulus = trimesh.creation.revolve(
        np.asarray(BASE_UPPER_ANNULUS_PROFILE_RZ),
        sections=192,
    )
    arm_profile = Polygon(BASE_ARM_PROFILE_RZ)
    one_arm = _extrude_xz(arm_profile, 3.0)
    tip_profile = arm_profile.intersection(box(12.0, -1.0, 20.0, 9.0))
    one_tip = _extrude_xz(tip_profile, 4.0)
    one_arm = _union([one_arm, one_tip])
    arms = []
    for angle in range(30, 390, 60):
        arm = one_arm.copy()
        rotation = trimesh.transformations.rotation_matrix(
            math.radians(float(angle)),
            [0.0, 0.0, 1.0],
        )
        arm.apply_transform(rotation)
        arms.append(arm)
    body = _union([lower_hub, upper_annulus, *arms])
    bore = trimesh.creation.revolve(
        np.asarray(BASE_BORE_PROFILE_RZ),
        sections=192,
    )
    mesh = _difference(body, [bore])
    mesh.metadata["name"] = "Parametric baseline six-arm base"
    return mesh


def build_selected_source_base(
    source_base: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Preserve every source arm surface and enlarge only the R188 pocket.

    The cutter begins at the existing 1.80 mm bearing shoulder, so all external
    geometry, panel interfaces, and axial stack planes remain source-exact.
    """
    pocket_start = 1.80
    pocket_height = 7.00
    pocket = _cylinder(
        COUPONS.selected_housing_diameter,
        pocket_height,
        (
            0.0,
            0.0,
            pocket_start + pocket_height / 2,
        ),
        sections=192,
    )
    base = _difference(source_base.copy(), [pocket])
    base.metadata["name"] = (
        f"Source-arm base with {COUPONS.selected_housing_diameter:.2f} mm R188 pocket"
    )
    return base


def build_base_retention_variants(
    selected_source_base: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Add controlled diameter only to the six source arm-peg cylinders."""
    output: list[tuple[str, trimesh.Trimesh]] = []
    local_u, local_v, local_z = BASE_PEG_LOCAL_CENTRE
    axis_u, axis_v, axis_z = BASE_PEG_LOCAL_AXIS

    for variant_index, diameter in enumerate(
        BASE_PEG_RETENTION_DIAMETERS,
        start=1,
    ):
        reinforcements = []
        for angle_deg in BASE_ARM_ANGLES_DEG:
            angle = math.radians(angle_deg)
            radial = np.asarray([math.cos(angle), math.sin(angle), 0.0])
            tangential = np.asarray([-math.sin(angle), math.cos(angle), 0.0])
            centre = (
                local_u * radial
                + local_v * tangential
                + np.asarray([0.0, 0.0, local_z])
            )
            axis = axis_u * radial + axis_v * tangential
            axis[2] = axis_z
            axis = axis / np.linalg.norm(axis)
            half_length = BASE_PEG_FULL_DIAMETER_LENGTH / 2
            segment = np.asarray(
                [
                    centre - axis * half_length,
                    centre + axis * half_length,
                ]
            )
            reinforcements.append(
                trimesh.creation.cylinder(
                    radius=diameter / 2,
                    segment=segment,
                    sections=96,
                )
            )

        variant = _union(
            [
                selected_source_base.copy(),
                *reinforcements,
                *_identifier_dots(
                    count=variant_index,
                    centre=(0.0, -10.8),
                    z0=7.45,
                ),
            ]
        )
        variant.metadata["name"] = (
            f"Base arm retention peg {diameter:.2f} mm — "
            f"{variant_index} dot{'s' if variant_index > 1 else ''}"
        )
        label = f"{diameter:.2f}".replace(".", "_")
        output.append((f"base_arm_retention_{label}", variant))
    return output


def build_base_peg_process_gauge(
    selected_source_base: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Real-orientation single-arm coupons with slicer-visible diameter steps."""
    output: list[tuple[str, trimesh.Trimesh]] = []
    angle = math.radians(90.0)
    radial = np.asarray([math.cos(angle), math.sin(angle), 0.0])
    tangential = np.asarray([-math.sin(angle), math.cos(angle), 0.0])
    local_u, local_v, local_z = BASE_PEG_LOCAL_CENTRE
    axis_u, axis_v, axis_z = BASE_PEG_LOCAL_AXIS
    centre = (
        local_u * radial
        + local_v * tangential
        + np.asarray([0.0, 0.0, local_z])
    )
    axis = axis_u * radial + axis_v * tangential
    axis[2] = axis_z
    axis = axis / np.linalg.norm(axis)
    half_length = BASE_PEG_FULL_DIAMETER_LENGTH / 2
    segment = np.asarray(
        [
            centre - axis * half_length,
            centre + axis * half_length,
        ]
    )

    for index, diameter in enumerate(BASE_PEG_PROCESS_DIAMETERS, start=1):
        working = selected_source_base.copy()
        if diameter > 2.20:
            enlarged_section = trimesh.creation.cylinder(
                radius=diameter / 2,
                segment=segment,
                sections=128,
            )
            working = _union([working, enlarged_section])

        crop = _box((12.0, 13.0, 10.0), (0.0, 13.0, 5.0))
        arm = _intersection([working, crop])
        foot = _box((12.0, 6.0, 1.20), (0.0, 8.50, 0.60))
        coupon = _union(
            [
                arm,
                foot,
                *_identifier_dots(
                    count=index,
                    centre=(0.0, 7.0),
                    z0=1.15,
                    spacing=1.3,
                ),
            ]
        )
        xy_centre = (coupon.bounds[0, :2] + coupon.bounds[1, :2]) / 2
        coupon.apply_translation(
            [
                -xy_centre[0],
                -xy_centre[1],
                -coupon.bounds[0, 2],
            ]
        )
        coupon.metadata["name"] = (
            f"Real-orientation base peg {diameter:.2f} mm — {index} dots"
        )
        label = f"{diameter:.2f}".replace(".", "_")
        output.append((f"base_peg_process_{label}", coupon))
    return output


def _normalize_to_bed(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    result = mesh.copy()
    xy_centre = (result.bounds[0, :2] + result.bounds[1, :2]) / 2
    result.apply_translation(
        [
            -xy_centre[0],
            -xy_centre[1],
            -result.bounds[0, 2],
        ]
    )
    return result


def build_keyed_connector_architecture_coupon(
) -> list[tuple[str, trimesh.Trimesh]]:
    """Matte receiver/tongue plus a keyed Tough+ clevis for a filament pin."""
    # Panel-side surrogate: a one-ended dovetail channel prevents pull-out in
    # Z while allowing assembly from the open Y end.
    receiver = _rounded_prism(20.0, 12.0, 6.0, 2.0)
    channel_profile = Polygon(
        [
            (-5.00, 1.20),
            (5.00, 1.20),
            (4.20, 6.50),
            (-4.20, 6.50),
        ]
    )
    channel = _extrude_xz(channel_profile, 11.0)
    channel.apply_translation([0.0, 0.5, 0.0])
    receiver = _difference(receiver, [channel])
    receiver = _normalize_to_bed(receiver)
    receiver.metadata["name"] = "Matte keyed panel receiver"

    # Tough+ insert: 0.30 mm per-side dovetail clearance, bridge, and two ears
    # around a 4.00 mm-wide base-arm surrogate.
    key_profile = Polygon(
        [
            (-4.70, 1.40),
            (4.70, 1.40),
            (3.90, 5.80),
            (-3.90, 5.80),
        ]
    )
    key = _extrude_xz(key_profile, 11.0)
    key.apply_translation([0.0, 0.5, 0.0])
    bridge = _box((8.40, 3.00, 4.00), (0.0, 7.00, 6.00))
    ears = [
        _box((2.00, 10.00, 8.00), (side * 3.20, 13.00, 8.00))
        for side in (-1.0, 1.0)
    ]
    insert = _union([key, bridge, *ears])
    hinge_hole = trimesh.creation.cylinder(
        radius=0.95,
        segment=np.asarray(
            [
                [-5.0, 13.0, 8.0],
                [5.0, 13.0, 8.0],
            ]
        ),
        sections=64,
    )
    insert = _difference(insert, [hinge_hole])
    insert = _normalize_to_bed(insert)
    insert.metadata["name"] = "Tough+ keyed clevis insert"

    # Base-arm surrogate: a rounded pivot boss and handle, both Matte PLA.
    pivot_boss = trimesh.creation.cylinder(
        radius=3.00,
        segment=np.asarray(
            [
                [-2.0, 13.0, 8.0],
                [2.0, 13.0, 8.0],
            ]
        ),
        sections=96,
    )
    arm_handle = _box((4.00, 9.00, 4.00), (0.0, 17.00, 8.00))
    tongue = _union([pivot_boss, arm_handle])
    tongue_hole = trimesh.creation.cylinder(
        radius=0.95,
        segment=np.asarray(
            [
                [-3.0, 13.0, 8.0],
                [3.0, 13.0, 8.0],
            ]
        ),
        sections=64,
    )
    tongue = _difference(tongue, [tongue_hole])
    tongue = _normalize_to_bed(tongue)
    tongue.metadata["name"] = "Matte base-arm pivot surrogate"

    return [
        ("keyed_panel_receiver", receiver),
        ("keyed_tough_clevis", insert),
        ("keyed_base_tongue", tongue),
    ]


def build_fixed_pin_clevis_variants() -> list[tuple[str, trimesh.Trimesh]]:
    """Tough+ inserts with one gripping ear and one Ø1.90 running-fit ear.

    The original architecture coupon used Ø1.90 holes through both clevis ears.
    That allowed a 1.75 mm filament hinge pin to migrate under vertical cycling.
    These variants keep the tongue-side motion unchanged while fixing the pin
    in only the left ear.
    """
    variants = (
        (1.80, 1),
        (1.75, 2),
        (1.70, 3),
    )
    output: list[tuple[str, trimesh.Trimesh]] = []

    for tight_diameter, dot_count in variants:
        key_profile = Polygon(
            [
                (-4.70, 1.40),
                (4.70, 1.40),
                (3.90, 5.80),
                (-3.90, 5.80),
            ]
        )
        key = _extrude_xz(key_profile, 11.0)
        key.apply_translation([0.0, 0.5, 0.0])
        bridge = _box((8.40, 3.00, 4.00), (0.0, 7.00, 6.00))
        ears = [
            _box((2.00, 10.00, 8.00), (side * 3.20, 13.00, 8.00))
            for side in (-1.0, 1.0)
        ]
        insert = _union([key, bridge, *ears])

        tight_hole = trimesh.creation.cylinder(
            radius=tight_diameter / 2,
            segment=np.asarray(
                [
                    [-4.5, 13.0, 8.0],
                    [-1.9, 13.0, 8.0],
                ]
            ),
            sections=64,
        )
        running_hole = trimesh.creation.cylinder(
            radius=0.95,
            segment=np.asarray(
                [
                    [1.9, 13.0, 8.0],
                    [4.5, 13.0, 8.0],
                ]
            ),
            sections=64,
        )
        insert = _difference(insert, [tight_hole, running_hole])

        # Dots sit on the top of the fixed ear, away from the tongue sweep.
        identifiers = [
            _cylinder(
                0.55,
                0.35,
                (
                    -3.20,
                    15.0 + (index - (dot_count - 1) / 2) * 1.4,
                    12.175,
                ),
                sections=24,
            )
            for index in range(dot_count)
        ]
        insert = _union([insert, *identifiers])
        insert = _normalize_to_bed(insert)
        insert.metadata["name"] = (
            f"Tough+ fixed-pin clevis {tight_diameter:.2f} mm"
        )
        label = f"{tight_diameter:.2f}".replace(".", "_")
        output.append((f"fixed_pin_clevis_{label}", insert))

    return output


def _real_keyed_panel_frame(
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return hinge, U/V/W axes, and source-pocket local transform."""
    lower = np.asarray(PANEL_SOCKET_CENTRES_XZ[0], dtype=float)
    upper = np.asarray(REAL_KEYED_SOURCE_POCKET_XZ, dtype=float)
    panel_axis = np.asarray(
        [upper[0] - lower[0], 0.0, upper[1] - lower[1]],
        dtype=float,
    )
    panel_axis /= np.linalg.norm(panel_axis)
    pin_axis = np.asarray([0.0, 1.0, 0.0])
    inward_normal = np.cross(pin_axis, panel_axis)
    inward_normal /= np.linalg.norm(inward_normal)
    source_centre = np.asarray([upper[0], 0.0, upper[1]])
    hinge_centre = (
        source_centre
        + REAL_KEYED_PANEL_INWARD_OFFSET * inward_normal
    )
    transform = np.eye(4)
    transform[:3, :3] = np.column_stack(
        [pin_axis, panel_axis, inward_normal]
    )
    transform[:3, 3] = source_centre
    return (
        hinge_centre,
        pin_axis,
        panel_axis,
        inward_normal,
        transform,
    )


def _real_keyed_local_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    result = mesh.copy()
    result.apply_transform(_real_keyed_panel_frame()[4])
    return result


def _real_keyed_oriented_box(
    size: tuple[float, float, float],
    centre: tuple[float, float, float],
) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation(centre)
    return _real_keyed_local_mesh(mesh)


def _real_keyed_point(point: tuple[float, float, float]) -> np.ndarray:
    local = np.asarray([*point, 1.0], dtype=float)
    return (_real_keyed_panel_frame()[4] @ local)[:3]


def _real_keyed_extrusion(
    profile: Polygon,
    v_range: tuple[float, float],
) -> trimesh.Trimesh:
    depth = v_range[1] - v_range[0]
    mesh = _extrude_xz(profile, depth)
    mesh.apply_translation([0.0, sum(v_range) / 2, 0.0])
    return _real_keyed_local_mesh(mesh)


def _real_keyed_extrude_vw(
    profile: Polygon,
    u_range: tuple[float, float],
) -> trimesh.Trimesh:
    """Extrude a local V/W profile along the pin-axis U direction."""
    depth = u_range[1] - u_range[0]
    mesh = trimesh.creation.extrude_polygon(profile, height=depth)
    vertices = np.asarray(mesh.vertices).copy()
    mesh.vertices = np.column_stack(
        [
            vertices[:, 2] + u_range[0],
            vertices[:, 0],
            vertices[:, 1],
        ]
    )
    return _real_keyed_local_mesh(mesh)


def _real_keyed_rail_profile(
    centre_u: float,
    *,
    w_range: tuple[float, float],
    tail_width: float,
    throat_width: float,
) -> Polygon:
    return Polygon(
        [
            (centre_u - tail_width / 2, w_range[0]),
            (centre_u + tail_width / 2, w_range[0]),
            (centre_u + throat_width / 2, w_range[1]),
            (centre_u - throat_width / 2, w_range[1]),
        ]
    )


def build_real_keyed_filled_panel(
    source_panel: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Fill the two obsolete source pockets without changing the outer shell."""
    pocket_bottom = np.asarray(
        REAL_KEYED_UPPER_POCKET_BOTTOM,
        dtype=float,
    )
    pocket_mouth = np.asarray(
        REAL_KEYED_UPPER_POCKET_MOUTH,
        dtype=float,
    )
    pocket_axis = pocket_mouth - pocket_bottom
    pocket_axis /= np.linalg.norm(pocket_axis)
    plugs = []
    for side in (-1.0, 1.0):
        mirror = np.asarray([1.0, side, 1.0])
        plugs.append(
            trimesh.creation.cylinder(
                radius=PANEL_LOWER_POCKET_MEASURED_DIAMETER / 2,
                segment=np.asarray(
                    [
                        (pocket_bottom - 0.05 * pocket_axis) * mirror,
                        pocket_mouth * mirror,
                    ]
                ),
                sections=96,
            )
        )
    filled_panel = _union([source_panel.copy(), *plugs])
    filled_panel.metadata["name"] = "Source panel with upper pockets filled"
    return filled_panel


def build_real_keyed_panel_receiver(
    source_panel: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Cut masked twin rails while preserving the source spherical shell."""
    filled_panel = build_real_keyed_filled_panel(source_panel)

    channels = [
        _real_keyed_extrusion(
            _real_keyed_rail_profile(
                side * REAL_KEYED_RAIL_CENTRE_U,
                w_range=REAL_KEYED_CHANNEL_W_RANGE,
                tail_width=REAL_KEYED_CHANNEL_TAIL_WIDTH,
                throat_width=REAL_KEYED_CHANNEL_THROAT_WIDTH,
            ),
            REAL_KEYED_CHANNEL_V_RANGE,
        )
        for side in (-1.0, 1.0)
    ]
    latch_notch = trimesh.creation.icosphere(
        subdivisions=3,
        radius=REAL_KEYED_LATCH_NOTCH_RADIUS,
    )
    latch_notch.apply_translation(
        _real_keyed_point(REAL_KEYED_LATCH_CENTRE)
    )
    panel = _difference(filled_panel, [*channels, latch_notch])
    panel.metadata["name"] = "Source panel with masked twin-rail receiver"
    return panel


def build_real_keyed_clevis_insert(
    *,
    include_rigid_latch: bool = True,
) -> trimesh.Trimesh:
    """Build the one-piece Tough+ twin-key clevis cartridge."""
    hinge, pin_axis, _, _, _ = _real_keyed_panel_frame()
    primary_key = _real_keyed_extrusion(
        _real_keyed_rail_profile(
            REAL_KEYED_RAIL_CENTRE_U,
            w_range=REAL_KEYED_KEY_W_RANGE,
            tail_width=REAL_KEYED_PRIMARY_KEY_WIDTHS[0],
            throat_width=REAL_KEYED_PRIMARY_KEY_WIDTHS[1],
        ),
        REAL_KEYED_PRIMARY_KEY_V_RANGE,
    )
    follower_key = _real_keyed_extrusion(
        _real_keyed_rail_profile(
            -REAL_KEYED_RAIL_CENTRE_U,
            w_range=REAL_KEYED_KEY_W_RANGE,
            tail_width=REAL_KEYED_FOLLOWER_KEY_WIDTHS[0],
            throat_width=REAL_KEYED_FOLLOWER_KEY_WIDTHS[1],
        ),
        REAL_KEYED_FOLLOWER_KEY_V_RANGE,
    )

    # Two narrow stalks leave the source skin between the rails untouched.
    # They join a strengthened rear yoke which routes around, rather than
    # through, the rotating Ø4.50 mm tongue envelope. Its extra depth extends
    # away from the pivot so it does not consume the 0.20 mm running clearance.
    stalks = [
        _real_keyed_oriented_box(
            (1.80, 1.40, 1.60),
            (side * REAL_KEYED_RAIL_CENTRE_U, -1.80, 2.70),
        )
        for side in (-1.0, 1.0)
    ]
    rear_yoke = _real_keyed_oriented_box(
        (8.40, 1.65, 1.25),
        (0.00, -1.83, 2.67),
    )
    ears = [
        trimesh.creation.cylinder(
            radius=REAL_KEYED_EAR_OUTER_RADIUS,
            segment=np.asarray(
                [
                    hinge
                    + (side * REAL_KEYED_EAR_CENTRE_U - 1.00) * pin_axis,
                    hinge
                    + (side * REAL_KEYED_EAR_CENTRE_U + 1.00) * pin_axis,
                ]
            ),
            sections=96,
        )
        for side in (-1.0, 1.0)
    ]
    latch_tooth = trimesh.creation.icosphere(
        subdivisions=3,
        radius=REAL_KEYED_LATCH_TOOTH_RADIUS,
    )
    latch_tooth.apply_translation(
        _real_keyed_point(REAL_KEYED_LATCH_CENTRE)
    )
    solids = [
        primary_key,
        follower_key,
        *stalks,
        rear_yoke,
        *ears,
    ]
    if include_rigid_latch:
        solids.append(latch_tooth)
    insert = _union(solids)
    boss_clearance = trimesh.creation.cylinder(
        radius=REAL_KEYED_BASE_BOSS_RADIUS + 0.20,
        segment=np.asarray(
            [
                hinge - 2.19 * pin_axis,
                hinge + 2.19 * pin_axis,
            ]
        ),
        sections=96,
    )

    fixed_hole = trimesh.creation.cylinder(
        radius=REAL_KEYED_FIXED_EAR_DIAMETER / 2,
        segment=np.asarray(
            [
                hinge - 4.60 * pin_axis,
                hinge - 1.85 * pin_axis,
            ]
        ),
        sections=64,
    )
    running_hole = trimesh.creation.cylinder(
        radius=REAL_KEYED_RUNNING_HOLE_DIAMETER / 2,
        segment=np.asarray(
            [
                hinge + 1.85 * pin_axis,
                hinge + 4.60 * pin_axis,
            ]
        ),
        sections=64,
    )
    fixed_entry_chamfer = _frustum_between(
        1.10,
        REAL_KEYED_FIXED_EAR_DIAMETER / 2,
        hinge - 2.15 * pin_axis,
        hinge - 2.50 * pin_axis,
        sections=64,
    )
    insert = _difference(
        insert,
        [
            boss_clearance,
            fixed_hole,
            running_hole,
            fixed_entry_chamfer,
        ],
    )
    insert.metadata["name"] = (
        "Tough+ twin-key clevis with 1.85 mm fixed ear"
    )
    return insert


def build_monolithic_receiver_clevis(
    source_panel: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Fuse the reinforced clevis and its two anchor ribs into the panel."""
    filled_panel = build_real_keyed_filled_panel(source_panel)
    clevis = build_real_keyed_clevis_insert(include_rigid_latch=False)
    monolithic = _union([filled_panel, clevis])
    monolithic.metadata["name"] = "Monolithic reinforced receiver and clevis"
    return monolithic


def _hook_rail_profile() -> Polygon:
    """Return a C-hook on the original source pin axis."""
    inner_radius = (
        HOOK_RAIL_DIAMETER / 2 + HOOK_RAIL_RUNNING_CLEARANCE
    )
    outer = Point(0.0, 0.0).buffer(
        HOOK_RAIL_HOOK_OUTER_RADIUS,
        resolution=64,
    )
    inner = Point(0.0, 0.0).buffer(inner_radius, resolution=64)
    opening = Polygon(
        [
            (
                -HOOK_RAIL_MOUTH_WIDTH / 2,
                -0.30,
            ),
            (
                HOOK_RAIL_MOUTH_WIDTH / 2,
                -0.30,
            ),
            (
                HOOK_RAIL_ENTRY_WIDTH / 2,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.40,
            ),
            (
                -HOOK_RAIL_ENTRY_WIDTH / 2,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.40,
            ),
        ]
    )
    profile = outer.difference(inner).difference(opening)
    if not isinstance(profile, Polygon) or not profile.is_valid:
        raise ValueError("Hook/rail C-hook profile is not one valid polygon")
    return profile


def _hook_rail_mirrored_u_range(
    u_range: tuple[float, float],
    side: float,
) -> tuple[float, float]:
    if side > 0:
        return u_range
    return (-u_range[1], -u_range[0])


def _hook_rail_root_opening_profile() -> Polygon:
    """Slightly overcut the source boss so no old pocket blocks the hook."""
    return Polygon(
        [
            (-(HOOK_RAIL_MOUTH_WIDTH + 0.15) / 2, -0.45),
            ((HOOK_RAIL_MOUTH_WIDTH + 0.15) / 2, -0.45),
            (
                (HOOK_RAIL_ENTRY_WIDTH + 0.15) / 2,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.60,
            ),
            (
                -(HOOK_RAIL_ENTRY_WIDTH + 0.15) / 2,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.60,
            ),
        ]
    )


def build_hook_rail_panel(
    source_panel: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Replace the original upper pin pockets with stronger extended hooks."""
    hook_profile = _hook_rail_profile()
    hooks = [
        _real_keyed_extrude_vw(
            hook_profile,
            _hook_rail_mirrored_u_range(
                HOOK_RAIL_HOOK_U_RANGE,
                side,
            ),
        )
        for side in (-1.0, 1.0)
    ]
    panel = _union([source_panel.copy(), *hooks])

    inner_radius = (
        HOOK_RAIL_DIAMETER / 2 + HOOK_RAIL_RUNNING_CLEARANCE
    )
    bore_profile = Point(0.0, 0.0).buffer(
        inner_radius + 0.01,
        resolution=64,
    )
    cap_cavity_profile = Point(0.0, 0.0).buffer(
        HOOK_RAIL_CAP_DIAMETER / 2 + 0.10,
        resolution=64,
    )
    panel = _difference(
        panel,
        [
            _real_keyed_extrude_vw(
                bore_profile,
                _hook_rail_mirrored_u_range((3.60, 7.65), side),
            )
            for side in (-1.0, 1.0)
        ],
    )
    panel = _difference(
        panel,
        [
            _real_keyed_extrude_vw(
                cap_cavity_profile,
                _hook_rail_mirrored_u_range((2.85, 3.78), side),
            )
            for side in (-1.0, 1.0)
        ],
    )
    panel = _difference(
        panel,
        [
            _real_keyed_extrude_vw(
                _hook_rail_root_opening_profile(),
                _hook_rail_mirrored_u_range((2.80, 5.20), side),
            )
            for side in (-1.0, 1.0)
        ],
    )
    panel.metadata["name"] = (
        "Source panel with extended hooks on original pin axis"
    )
    return panel


def build_hook_rail_base_coupon() -> trimesh.Trimesh:
    """Build two longer source-position rail stubs with captive inner caps."""
    rail_z = 6.00
    rails = [
        trimesh.creation.cylinder(
            radius=HOOK_RAIL_DIAMETER / 2,
            segment=np.asarray(
                [
                    [side * 3.25, 0.0, rail_z],
                    [side * HOOK_RAIL_OUTER_U, 0.0, rail_z],
                ]
            ),
            sections=96,
        )
        for side in (-1.0, 1.0)
    ]
    inner_caps = [
        trimesh.creation.cylinder(
            radius=HOOK_RAIL_CAP_DIAMETER / 2,
            segment=np.asarray(
                [
                    [side * 3.00, 0.0, rail_z],
                    [side * 3.70, 0.0, rail_z],
                ]
            ),
            sections=96,
        )
        for side in (-1.0, 1.0)
    ]
    root_shoulders = [
        _frustum_between(
            HOOK_RAIL_DIAMETER / 2 + 0.05,
            2.10,
            np.asarray(
                [side * (HOOK_RAIL_SUPPORT_INNER_U - 0.15), 0.0, rail_z]
            ),
            np.asarray(
                [side * (HOOK_RAIL_SUPPORT_INNER_U + 0.50), 0.0, rail_z]
            ),
            sections=96,
        )
        for side in (-1.0, 1.0)
    ]
    foot = _box((24.0, 10.0, 1.60), (0.0, 0.0, 0.80))
    side_supports = [
        _box(
            (1.80, 5.00, 8.10),
            (
                side * (HOOK_RAIL_SUPPORT_INNER_U + 0.90),
                0.0,
                4.05,
            ),
        )
        for side in (-1.0, 1.0)
    ]
    base = _union(
        [
            foot,
            *side_supports,
            *rails,
            *inner_caps,
            *root_shoulders,
        ]
    )
    base.metadata["name"] = (
        "Matte paired source-axis rails with full column embedment"
    )
    return base


def build_hook_rail_material_coupons(
    source_panel: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Build one hook mesh and one rail mesh for a controlled material A/B."""
    full_panel = build_hook_rail_panel(source_panel)
    crop = _box((16.0, 18.0, 10.0), (2.0, 0.0, 15.5))
    panel_coupon = _normalize_to_bed(_intersection([full_panel, crop]))
    panel_coupon.metadata["name"] = "Original-axis extended hook panel"
    rail_base = _normalize_to_bed(build_hook_rail_base_coupon())
    validate_mesh("hook_rail_panel_coupon", panel_coupon)
    validate_mesh("hook_rail_base_coupon", rail_base)
    return [
        ("hook_rail_panel_coupon", panel_coupon),
        ("hook_rail_base_coupon", rail_base),
    ]


def build_hook_rail_integrated_panel(
    source_panel: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Add the proven Tough+ hooks and deeper real-arm root clearance."""
    panel = build_hook_rail_panel(source_panel)
    cap_cavity_profile = Point(0.0, 0.0).buffer(
        HOOK_RAIL_CAP_DIAMETER / 2 + 0.10,
        resolution=64,
    )
    for side in (-1.0, 1.0):
        panel = _difference(
            panel,
            [
                _real_keyed_extrude_vw(
                    cap_cavity_profile,
                    _hook_rail_mirrored_u_range((2.30, 3.00), side),
                ),
                _real_keyed_extrude_vw(
                    _hook_rail_root_opening_profile(),
                    _hook_rail_mirrored_u_range((2.25, 3.00), side),
                ),
            ],
        )
    panel.metadata["name"] = (
        "Full Tough+ source panel with original-axis extended hooks"
    )
    return panel


def _hook_rail_integration_rail(
    side: float,
    *,
    centre: np.ndarray,
) -> trimesh.Trimesh:
    axis = np.asarray([1.0, 0.0, 0.0])
    rail = trimesh.creation.cylinder(
        radius=HOOK_RAIL_DIAMETER / 2,
        segment=np.asarray(
            [
                centre
                + side * HOOK_RAIL_INTEGRATION_RAIL_U_RANGE[0] * axis,
                centre
                + side * HOOK_RAIL_INTEGRATION_RAIL_U_RANGE[1] * axis,
            ]
        ),
        sections=96,
    )
    root = trimesh.creation.cylinder(
        radius=HOOK_RAIL_CAP_DIAMETER / 2,
        segment=np.asarray(
            [
                centre
                + side * HOOK_RAIL_INTEGRATION_ROOT_U_RANGE[0] * axis,
                centre
                + side * HOOK_RAIL_INTEGRATION_ROOT_U_RANGE[1] * axis,
            ]
        ),
        sections=96,
    )
    outer_cap = trimesh.creation.cylinder(
        radius=HOOK_RAIL_CAP_DIAMETER / 2,
        segment=np.asarray(
            [
                centre
                + side * HOOK_RAIL_INTEGRATION_CAP_U_RANGE[0] * axis,
                centre
                + side * HOOK_RAIL_INTEGRATION_CAP_U_RANGE[1] * axis,
            ]
        ),
        sections=96,
    )
    return _union([rail, root, outer_cap])


def build_hook_rail_integrated_base(
    selected_source_base: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Extend one real source-arm pin pair into the accepted Matte rails."""
    centre = np.asarray(REAL_KEYED_BASE_HINGE_CENTRE, dtype=float)
    rails = [
        _hook_rail_integration_rail(side, centre=centre)
        for side in (-1.0, 1.0)
    ]
    base = _union([selected_source_base.copy(), *rails])
    base.metadata["name"] = (
        "Source base with one original-axis paired-rail arm"
    )
    return base


def build_hook_rail_full_integration_parts(
    source_panel: trimesh.Trimesh,
    selected_source_base: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Prepare one full panel and one cropped real arm for physical approval."""
    panel = _normalize_to_bed(build_hook_rail_integrated_panel(source_panel))
    base = build_hook_rail_integrated_base(selected_source_base)
    base_crop = _intersection(
        [
            base,
            _box((20.0, 14.0, 10.0), (0.0, 13.0, 5.0)),
        ]
    )
    base_crop = _normalize_to_bed(base_crop)
    panel.metadata["name"] = "Full Tough+ panel with accepted hooks"
    base_crop.metadata["name"] = "Cropped real Matte base arm with paired rails"
    validate_mesh("hook_rail_full_panel", panel)
    validate_mesh("hook_rail_real_base_arm", base_crop)
    return [
        ("hook_rail_full_panel", panel),
        ("hook_rail_real_base_arm", base_crop),
    ]


def _full_base_lower_panel_frame(
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return the source panel's actual base-side lower hinge frame."""
    lower_xz = np.asarray(PANEL_SOCKET_CENTRES_XZ[0], dtype=float)
    upper_xz = np.asarray(PANEL_SOCKET_CENTRES_XZ[1], dtype=float)
    origin = np.asarray([lower_xz[0], 0.0, lower_xz[1]])
    upper = np.asarray([upper_xz[0], 0.0, upper_xz[1]])
    u_axis = np.asarray([0.0, 1.0, 0.0])
    v_axis = upper - origin
    v_axis /= np.linalg.norm(v_axis)
    w_axis = np.cross(u_axis, v_axis)
    w_axis /= np.linalg.norm(w_axis)
    transform = np.eye(4)
    transform[:3, :3] = np.column_stack([u_axis, v_axis, w_axis])
    transform[:3, 3] = origin
    return origin, u_axis, v_axis, w_axis, transform


def _full_base_arm_frame(
    angle_deg: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return hinge centre and U/V/W axes for one source base arm."""
    angle = math.radians(float(angle_deg))
    w_axis = np.asarray([math.cos(angle), math.sin(angle), 0.0])
    u_axis = np.asarray([-math.sin(angle), math.cos(angle), 0.0])
    v_axis = np.asarray([0.0, 0.0, 1.0])
    centre = (
        REAL_KEYED_BASE_HINGE_CENTRE[1] * w_axis
        + np.asarray([0.0, 0.0, REAL_KEYED_BASE_HINGE_CENTRE[2]])
    )
    return centre, u_axis, v_axis, w_axis


def _full_base_oriented_extrude_vw(
    profile: Polygon,
    u_range: tuple[float, float],
    *,
    centre: np.ndarray,
    u_axis: np.ndarray,
    v_axis: np.ndarray,
    w_axis: np.ndarray,
) -> trimesh.Trimesh:
    """Extrude a local V/W profile along an arbitrary hinge U axis."""
    depth = u_range[1] - u_range[0]
    mesh = trimesh.creation.extrude_polygon(profile, height=depth)
    vertices = np.asarray(mesh.vertices).copy()
    local = np.column_stack(
        [
            vertices[:, 2] + u_range[0],
            vertices[:, 0],
            vertices[:, 1],
        ]
    )
    mesh.vertices = (
        centre
        + local[:, 0, None] * u_axis
        + local[:, 1, None] * v_axis
        + local[:, 2, None] * w_axis
    )
    return mesh


def _full_base_hook_profile() -> Polygon:
    """Return one rooted Tough+ C-hook opening radially away from the hub."""
    inner_radius = (
        HOOK_RAIL_DIAMETER / 2 + HOOK_RAIL_RUNNING_CLEARANCE
    )
    outer = Point(0.0, 0.0).buffer(
        HOOK_RAIL_HOOK_OUTER_RADIUS,
        resolution=64,
    )
    inner = Point(0.0, 0.0).buffer(inner_radius, resolution=64)
    opening = Polygon(
        [
            (-FULL_BASE_HOOK_MOUTH_WIDTH / 2, -0.30),
            (FULL_BASE_HOOK_MOUTH_WIDTH / 2, -0.30),
            (
                FULL_BASE_HOOK_ENTRY_WIDTH / 2,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.40,
            ),
            (
                -FULL_BASE_HOOK_ENTRY_WIDTH / 2,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.40,
            ),
        ]
    )
    ring = outer.difference(inner).difference(opening)
    rooted = ring.union(
        box(
            -FULL_BASE_HOOK_ROOT_HALF_V,
            FULL_BASE_HOOK_ROOT_W_RANGE[0],
            FULL_BASE_HOOK_ROOT_HALF_V,
            FULL_BASE_HOOK_ROOT_W_RANGE[1],
        )
    )
    if not isinstance(rooted, Polygon) or not rooted.is_valid:
        raise ValueError("Full-base C-hook profile is not one valid polygon")
    return rooted


def _full_base_source_opening_profile() -> Polygon:
    """Overcut only the source arm behind each authored hook opening."""
    throat_half_width = (
        HOOK_RAIL_DIAMETER / 2 + HOOK_RAIL_RUNNING_CLEARANCE
    )
    entry_half_width = throat_half_width + 0.05
    return Polygon(
        [
            (-throat_half_width, -1.55),
            (throat_half_width, -1.55),
            (
                entry_half_width,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.60,
            ),
            (
                -entry_half_width,
                HOOK_RAIL_HOOK_OUTER_RADIUS + 0.60,
            ),
        ]
    )


def _full_base_hook_geometry(
    angle_deg: float,
) -> tuple[list[trimesh.Trimesh], list[trimesh.Trimesh]]:
    """Build the two hooks and source-clearance cutters for one base arm."""
    centre, u_axis, v_axis, w_axis = _full_base_arm_frame(angle_deg)
    hook_profile = _full_base_hook_profile()
    inner_radius = (
        HOOK_RAIL_DIAMETER / 2 + HOOK_RAIL_RUNNING_CLEARANCE
    )
    bore_profile = Point(0.0, 0.0).buffer(
        inner_radius + 0.01,
        resolution=64,
    )
    root_cavity_profile = Point(0.0, 0.0).buffer(
        FULL_BASE_PANEL_RAIL_ROOT_RADIUS + 0.10,
        resolution=64,
    )
    hooks = []
    cutters = []
    for side in (-1.0, 1.0):
        def oriented(
            profile: Polygon,
            u_range: tuple[float, float],
        ) -> trimesh.Trimesh:
            return _full_base_oriented_extrude_vw(
                profile,
                _hook_rail_mirrored_u_range(u_range, side),
                centre=centre,
                u_axis=u_axis,
                v_axis=v_axis,
                w_axis=w_axis,
            )

        hooks.append(oriented(hook_profile, FULL_BASE_HOOK_U_RANGE))
        cutters.extend(
            [
                oriented(
                    bore_profile,
                    FULL_BASE_CLEARANCE_BORE_U_RANGE,
                ),
                oriented(
                    _full_base_source_opening_profile(),
                    FULL_BASE_CLEARANCE_OPENING_U_RANGE,
                ),
                oriented(
                    root_cavity_profile,
                    FULL_BASE_CLEARANCE_ROOT_U_RANGE,
                ),
            ]
        )
    return hooks, cutters


def build_full_base_with_hooks(
    selected_source_base: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Replace all six source peg pairs with outward-accessible Tough+ hooks."""
    hooks = []
    cutters = []
    for angle_deg in BASE_ARM_ANGLES_DEG:
        arm_hooks, arm_cutters = _full_base_hook_geometry(angle_deg)
        hooks.extend(arm_hooks)
        cutters.extend(arm_cutters)
    cleared_source = _difference(selected_source_base.copy(), cutters)
    base = _union([cleared_source, *hooks])
    base.metadata["name"] = (
        "Full source base with twelve lower-axis Tough+ hooks"
    )
    return base


def build_lower_panel_with_rails(
    source_panel: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Replace only the true base-side lower pockets with rigid Matte rails."""
    origin, u_axis, v_axis, w_axis, transform = (
        _full_base_lower_panel_frame()
    )
    cavity_profile = Point(0.0, 0.0).buffer(
        FULL_BASE_PANEL_HOOK_CAVITY_RADIUS,
        resolution=64,
    )
    cavity_cutters = [
        _full_base_oriented_extrude_vw(
            cavity_profile,
            _hook_rail_mirrored_u_range(
                FULL_BASE_PANEL_HOOK_CAVITY_U_RANGE,
                side,
            ),
            centre=origin,
            u_axis=u_axis,
            v_axis=v_axis,
            w_axis=w_axis,
        )
        for side in (-1.0, 1.0)
    ]
    rails = []
    roots = []
    for side in (-1.0, 1.0):
        rail_u = _hook_rail_mirrored_u_range(
            FULL_BASE_PANEL_RAIL_U_RANGE,
            side,
        )
        rail = trimesh.creation.cylinder(
            radius=HOOK_RAIL_DIAMETER / 2,
            segment=np.asarray(
                [[rail_u[0], 0.0, 0.0], [rail_u[1], 0.0, 0.0]]
            ),
            sections=96,
        )
        rail.apply_transform(transform)
        rails.append(rail)

        root_u = _hook_rail_mirrored_u_range(
            FULL_BASE_PANEL_RAIL_ROOT_U_RANGE,
            side,
        )
        root = trimesh.creation.cylinder(
            radius=FULL_BASE_PANEL_RAIL_ROOT_RADIUS,
            segment=np.asarray(
                [[root_u[0], 0.0, 0.0], [root_u[1], 0.0, 0.0]]
            ),
            sections=96,
        )
        root.apply_transform(transform)
        roots.append(root)

    panel = _union(
        [
            _difference(source_panel.copy(), cavity_cutters),
            *rails,
            *roots,
        ]
    )
    panel.metadata["name"] = (
        "Source panel with rigid rails at the true lower base connector"
    )
    return panel


def build_full_base_hook_test_parts(
    source_panel: trimesh.Trimesh,
    selected_source_base: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Prepare one complete base and one reusable panel for all-arm testing."""
    base = _normalize_to_bed(
        build_full_base_with_hooks(selected_source_base)
    )
    panel = _normalize_to_bed(build_lower_panel_with_rails(source_panel))
    base.metadata["name"] = "Complete Tough+ base with all twelve hooks"
    panel.metadata["name"] = "Matte panel with lower rigid rails"
    validate_mesh("full_base_tough_hooks", base)
    validate_mesh("lower_panel_matte_rails", panel)
    return [
        ("full_base_tough_hooks", base),
        ("lower_panel_matte_rails", panel),
    ]


def build_real_keyed_source_base(
    selected_source_base: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Replace one source peg pair with an Ø4.40 mm pinned tongue."""
    tip_cutter = _box(
        (14.00, 11.00, 10.00),
        (0.00, 15.50, 4.00),
    )
    trimmed_base = _difference(
        selected_source_base.copy(),
        [tip_cutter],
    )
    hinge = np.asarray(REAL_KEYED_BASE_HINGE_CENTRE, dtype=float)
    boss = trimesh.creation.cylinder(
        radius=REAL_KEYED_BASE_BOSS_RADIUS,
        segment=np.asarray(
            [
                hinge + np.asarray([-2.00, 0.00, 0.00]),
                hinge + np.asarray([2.00, 0.00, 0.00]),
            ]
        ),
        sections=96,
    )
    handle = _box(
        (4.00, 6.80, 4.00),
        (0.00, 11.30, 4.00),
    )
    tongue = _union([trimmed_base, boss, handle])
    through_hole = trimesh.creation.cylinder(
        radius=REAL_KEYED_RUNNING_HOLE_DIAMETER / 2,
        segment=np.asarray(
            [
                hinge + np.asarray([-3.00, 0.00, 0.00]),
                hinge + np.asarray([3.00, 0.00, 0.00]),
            ]
        ),
        sections=64,
    )
    base = _difference(tongue, [through_hole])
    base.metadata["name"] = "Source base with one keyed pin tongue"
    return base


def build_twin_rail_tongue_surrogate() -> trimesh.Trimesh:
    """Build the coupon's Ø4.50 / Ø2.05 running-fit tongue."""
    hinge = np.zeros(3)
    pin_axis = np.asarray([1.0, 0.0, 0.0])
    boss = trimesh.creation.cylinder(
        radius=REAL_KEYED_BASE_BOSS_RADIUS,
        segment=np.asarray(
            [
                hinge - 2.00 * pin_axis,
                hinge + 2.00 * pin_axis,
            ]
        ),
        sections=96,
    )
    handle = _box((4.00, 7.00, 3.50), (0.0, 4.00, 0.0))
    tongue = _union([boss, handle])
    hole = trimesh.creation.cylinder(
        radius=TWIN_RAIL_COUPON_TONGUE_HOLE_DIAMETER / 2,
        segment=np.asarray(
            [
                hinge - 3.00 * pin_axis,
                hinge + 3.00 * pin_axis,
            ]
        ),
        sections=64,
    )
    entry_radius = TWIN_RAIL_COUPON_TONGUE_ENTRY_DIAMETER / 2
    hole_radius = TWIN_RAIL_COUPON_TONGUE_HOLE_DIAMETER / 2
    chamfer_depth = TWIN_RAIL_COUPON_TONGUE_CHAMFER_DEPTH
    entry_chamfers = [
        _frustum_between(
            entry_radius,
            hole_radius,
            hinge - 2.10 * pin_axis,
            hinge - (2.10 - chamfer_depth) * pin_axis,
            sections=64,
        ),
        _frustum_between(
            entry_radius,
            hole_radius,
            hinge + 2.10 * pin_axis,
            hinge + (2.10 - chamfer_depth) * pin_axis,
            sections=64,
        ),
    ]
    tongue = _difference(tongue, [hole, *entry_chamfers])
    tongue.metadata["name"] = "Matte 4.50 mm tongue with 2.05 mm running hole"
    return tongue


def _orient_twin_rail_cartridge_for_print(
    cartridge: trimesh.Trimesh,
) -> trimesh.Trimesh:
    """Place rail tails on the bed with local W as print Z."""
    result = cartridge.copy()
    result.apply_transform(np.linalg.inv(_real_keyed_panel_frame()[4]))
    print_rotation = np.eye(4)
    print_rotation[:3, :3] = np.asarray(
        [
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    result.apply_transform(print_rotation)
    return _normalize_to_bed(result)


def _build_twin_rail_compliant_latch_cartridge(
    hook_radius: float,
    dot_count: int,
) -> trimesh.Trimesh:
    """Replace the rigid rail bump with a relieved Tough+ cantilever."""
    cartridge = build_real_keyed_clevis_insert(include_rigid_latch=False)

    # Remove the complete outer strip of the primary key. The resulting
    # 0.40 mm inner slot isolates the beam from the rail body. The beam starts
    # at rail-floor height so it grows from the bed instead of over support.
    relief = _real_keyed_oriented_box(
        (1.60, 4.40, 2.30),
        (4.90, -2.90, 1.00),
    )
    cartridge = _difference(cartridge, [relief])

    beam = _real_keyed_oriented_box(
        (
            TWIN_RAIL_LATCH_BEAM_WIDTH,
            TWIN_RAIL_LATCH_BEAM_LENGTH,
            TWIN_RAIL_LATCH_BEAM_HEIGHT,
        ),
        (4.88, -2.55, 0.40),
    )
    hook = trimesh.creation.icosphere(
        subdivisions=3,
        radius=hook_radius,
    )
    hook.apply_translation(_real_keyed_point(REAL_KEYED_LATCH_CENTRE))

    identifiers = []
    for index in range(dot_count):
        dot = trimesh.creation.cylinder(
            radius=0.22,
            height=0.30,
            sections=24,
        )
        dot.apply_translation(
            [
                -REAL_KEYED_EAR_CENTRE_U,
                (index - (dot_count - 1) / 2) * 0.48,
                REAL_KEYED_PANEL_INWARD_OFFSET
                + REAL_KEYED_EAR_OUTER_RADIUS
                + 0.02,
            ]
        )
        identifiers.append(_real_keyed_local_mesh(dot))

    cartridge = _union([cartridge, beam, hook, *identifiers])
    # Manifold can emit near-zero slivers where the spherical hook meets the
    # beam. Keep the single functional solid and discard sub-micron debris.
    components = _positive_volume_components(cartridge)
    if not components:
        raise ValueError("Compliant latch cartridge produced no solid")
    cartridge = max(components, key=lambda item: abs(float(item.volume)))
    cartridge.process(validate=True)
    cartridge.fix_normals()
    cartridge.metadata["name"] = (
        f"Tough+ compliant latch R{hook_radius:.2f} - {dot_count} dots"
    )
    return cartridge


def build_twin_rail_compliant_latch_variants(
    source_panel: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Build three replacement cartridges for the corrected deep notch."""
    receiver = build_real_keyed_panel_receiver(source_panel)
    _, _, panel_axis, _, _ = _real_keyed_panel_frame()
    output = []
    for dot_count, hook_radius in enumerate(
        TWIN_RAIL_LATCH_HOOK_RADII,
        start=1,
    ):
        cartridge = _build_twin_rail_compliant_latch_cartridge(
            hook_radius,
            dot_count,
        )
        authored_overlap = _intersection_volume(receiver, cartridge)
        if authored_overlap > 1e-4:
            raise ValueError(
                f"Compliant latch R{hook_radius:.2f} overlaps receiver "
                f"by {authored_overlap:.6f} mm3"
            )
        hook = trimesh.creation.icosphere(
            subdivisions=3,
            radius=hook_radius,
        )
        hook.apply_translation(_real_keyed_point(REAL_KEYED_LATCH_CENTRE))
        withdrawal_probe = hook.copy()
        withdrawal_probe.apply_translation(0.25 * panel_axis)
        engagement = _intersection_volume(receiver, withdrawal_probe)
        if engagement < 0.003:
            raise ValueError(
                f"Compliant latch R{hook_radius:.2f} has no withdrawal engagement"
            )

        printed = _orient_twin_rail_cartridge_for_print(cartridge)
        label = f"{hook_radius:.2f}".replace(".", "_")
        printed.metadata["name"] = (
            f"Tough+ compliant latch R{hook_radius:.2f} - {dot_count} dots"
        )
        validate_mesh(f"twin_rail_latch_{label}", printed)
        output.append((f"twin_rail_latch_{label}", printed))
    return output


def build_twin_rail_latch_matrix(
    source_panel: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Build the corrected receiver plus three compliant cartridges."""
    full_receiver = build_real_keyed_panel_receiver(source_panel)
    crop = _box((16.0, 18.0, 8.0), (2.0, 0.0, 16.0))
    receiver = _normalize_to_bed(_intersection([full_receiver, crop]))
    receiver.metadata["name"] = "Matte corrected deep-notch receiver"
    validate_mesh("twin_rail_latch_matrix_receiver", receiver)
    return [
        ("twin_rail_latch_matrix_receiver", receiver),
        *build_twin_rail_compliant_latch_variants(source_panel),
    ]


def build_monolithic_receiver_material_coupon(
    source_panel: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Crop one exact monolithic mesh for the Matte/Tough+ material A/B."""
    full_receiver = build_monolithic_receiver_clevis(source_panel)
    crop = _box((16.0, 18.0, 8.0), (2.0, 0.0, 16.0))
    coupon = _normalize_to_bed(_intersection([full_receiver, crop]))
    coupon.metadata["name"] = "Monolithic receiver and clevis material coupon"
    validate_mesh("monolithic_receiver_clevis_coupon", coupon)
    return [("monolithic_receiver_clevis_coupon", coupon)]


def build_twin_rail_curvature_coupon(
    source_panel: trimesh.Trimesh,
) -> list[tuple[str, trimesh.Trimesh]]:
    """Build the actual-curvature rail/latch coupon and tongue surrogate."""
    full_panel = build_real_keyed_panel_receiver(source_panel)

    # Preserve the source part's Z-layer orientation while cropping away the
    # lower two-thirds. Do not add a bed foot: the first foot overlapped the
    # rail cavities (~4 mm³ each) and blocked cartridge insertion.
    crop = _box((16.0, 18.0, 8.0), (2.0, 0.0, 16.0))
    panel_coupon = _normalize_to_bed(_intersection([full_panel, crop]))
    panel_coupon.metadata["name"] = (
        "Matte actual-curvature twin-rail receiver coupon"
    )

    # Print the cartridge with local W vertical. Both rail tails then start on
    # the bed and narrow upward, while the proven fixed/running pin holes remain
    # horizontal just as they were in the successful clevis matrix.
    cartridge = _orient_twin_rail_cartridge_for_print(
        _build_twin_rail_compliant_latch_cartridge(0.36, 2)
    )
    cartridge.metadata["name"] = (
        "Tough+ compliant twin-rail latch with 1.85 mm fixed ear"
    )

    # The surrogate reproduces the production hinge interface, but prints on
    # one pin-axis face so this coupon remains focused on the receiver/latch.
    tongue = build_twin_rail_tongue_surrogate()
    tongue_rotation = np.eye(4)
    tongue_rotation[:3, :3] = np.asarray(
        [
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],
        ]
    )
    tongue.apply_transform(tongue_rotation)
    tongue = _normalize_to_bed(tongue)

    for name, mesh in (
        ("twin_rail_curvature_panel", panel_coupon),
        ("twin_rail_curvature_cartridge", cartridge),
        ("twin_rail_curvature_tongue", tongue),
    ):
        validate_mesh(name, mesh)
    return [
        ("twin_rail_curvature_panel", panel_coupon),
        ("twin_rail_curvature_cartridge", cartridge),
        ("twin_rail_curvature_tongue", tongue),
    ]


def _real_keyed_panel_to_base_transform() -> np.ndarray:
    hinge, _, _, _, panel_frame = _real_keyed_panel_frame()
    # The test pose hangs the panel below the selected +Y base arm. Rotating
    # both panel parts around the resulting +X pin axis exercises the joint.
    target_frame = np.column_stack(
        [
            np.asarray([1.0, 0.0, 0.0]),
            np.asarray([0.0, 0.0, 1.0]),
            np.asarray([0.0, -1.0, 0.0]),
        ]
    )
    rotation = target_frame @ panel_frame[:3, :3].T
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = (
        np.asarray(REAL_KEYED_BASE_HINGE_CENTRE)
        - rotation @ hinge
    )
    return transform


def _intersection_volume(
    first: trimesh.Trimesh,
    second: trimesh.Trimesh,
) -> float:
    result = trimesh.boolean.intersection(
        [first, second],
        engine="manifold",
    )
    if result is None or result.is_empty:
        return 0.0
    return abs(float(result.volume))


def validate_monolithic_receiver_clevis(
    source_panel: trimesh.Trimesh,
    monolithic: trimesh.Trimesh,
    base: trimesh.Trimesh,
) -> dict:
    """Validate fused root engagement and the complete pivot sweep."""
    mesh_validation = validate_mesh("monolithic_receiver_clevis", monolithic)
    if len(monolithic.split()) != 1:
        raise ValueError("Monolithic receiver/clevis is not one connected solid")

    filled_panel = build_real_keyed_filled_panel(source_panel)
    clevis = build_real_keyed_clevis_insert(include_rigid_latch=False)
    anchor_overlap = _intersection_volume(filled_panel, clevis)
    if anchor_overlap < 20.0:
        raise ValueError(
            f"Monolithic clevis anchors overlap only {anchor_overlap:.4f} mm3"
        )

    source_removed = trimesh.boolean.difference(
        [source_panel, monolithic],
        engine="manifold",
    )
    removed_volume = (
        0.0
        if source_removed is None or source_removed.is_empty
        else abs(float(source_removed.volume))
    )
    if removed_volume > 1e-3:
        raise ValueError(
            f"Monolithic receiver removes {removed_volume:.6f} mm3 of source"
        )

    moved = monolithic.copy()
    moved.apply_transform(_real_keyed_panel_to_base_transform())
    hinge = np.asarray(REAL_KEYED_BASE_HINGE_CENTRE)
    sweep = []
    for angle in range(
        REAL_KEYED_COLLISION_FREE_DEGREES[0],
        REAL_KEYED_COLLISION_FREE_DEGREES[1] + 1,
    ):
        pose = moved.copy()
        pose.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(float(angle)),
                [1.0, 0.0, 0.0],
                hinge,
            )
        )
        sweep.append(
            {
                "angle_degrees": angle,
                "base_overlap_mm3": round(
                    _intersection_volume(pose, base),
                    6,
                ),
            }
        )
    maximum_overlap = max(item["base_overlap_mm3"] for item in sweep)
    if maximum_overlap > 1e-4:
        raise ValueError(
            f"Monolithic receiver pivot collision is {maximum_overlap:.6f} mm3"
        )

    return {
        "architecture": "single-material monolithic receiver and clevis",
        "mesh": mesh_validation,
        "source_material_removed_mm3": round(removed_volume, 6),
        "material_added_mm3": round(
            abs(float(monolithic.volume)) - abs(float(source_panel.volume)),
            6,
        ),
        "embedded_anchor_overlap_mm3": round(anchor_overlap, 6),
        "connected_components": 1,
        "fixed_ear_diameter_mm": REAL_KEYED_FIXED_EAR_DIAMETER,
        "running_ear_diameter_mm": REAL_KEYED_RUNNING_HOLE_DIAMETER,
        "collision_free_range_degrees": list(
            REAL_KEYED_COLLISION_FREE_DEGREES
        ),
        "maximum_pivot_overlap_mm3": round(maximum_overlap, 6),
        "sweep": sweep,
    }


def validate_hook_rail_architecture(
    source_panel: trimesh.Trimesh,
    hook_panel: trimesh.Trimesh,
    rail_base: trimesh.Trimesh,
) -> dict:
    """Validate source-axis snap entry, capture and coupon pivot clearance."""
    panel_validation = validate_mesh("hook_rail_panel", hook_panel)
    base_validation = validate_mesh("hook_rail_base", rail_base)
    if len(hook_panel.split()) != 1 or len(rail_base.split()) != 1:
        raise ValueError("Hook/rail coupon contains disconnected solids")
    if HOOK_RAIL_SUPPORT_AXIAL_EMBED < 1.20:
        raise ValueError("Rail-to-column embedment is below 1.20 mm")

    source_removed = trimesh.boolean.difference(
        [source_panel, hook_panel],
        engine="manifold",
    )
    removed_volume = (
        0.0
        if source_removed is None or source_removed.is_empty
        else abs(float(source_removed.volume))
    )
    source_added = trimesh.boolean.difference(
        [hook_panel, source_panel],
        engine="manifold",
    )
    added_volume = (
        0.0
        if source_added is None or source_added.is_empty
        else abs(float(source_added.volume))
    )
    removed_percent = 100.0 * removed_volume / abs(float(source_panel.volume))
    if removed_percent > 4.0:
        raise ValueError(
            f"Hook panel removes {removed_percent:.3f}% of source material"
        )

    _, _, _, _, frame = _real_keyed_panel_frame()
    inverse_frame = np.linalg.inv(frame)
    changed_vertices = []
    for changed in (source_removed, source_added):
        if changed is None or changed.is_empty:
            continue
        for component in changed.split(only_watertight=False):
            if abs(float(component.volume)) < 1e-4:
                continue
            changed_vertices.append(
                trimesh.transform_points(
                    component.vertices,
                    inverse_frame,
                )
            )
    if changed_vertices:
        changed_local = np.vstack(changed_vertices)
        inside_mask = (
            (np.abs(changed_local[:, 0]) <= 7.80)
            & (changed_local[:, 1] >= -3.40)
            & (changed_local[:, 1] <= 3.50)
            & (changed_local[:, 2] >= -3.20)
            & (changed_local[:, 2] <= 3.70)
        )
        if not bool(np.all(inside_mask)):
            outside_count = int(np.count_nonzero(~inside_mask))
            raise ValueError(
                f"{outside_count} hook changes fall outside source-pin mask"
            )

    panel_crop = _intersection(
        [
            hook_panel,
            _box((16.0, 18.0, 10.0), (2.0, 0.0, 15.5)),
        ]
    )
    coupon_pose = panel_crop.copy()
    coupon_pose.apply_transform(inverse_frame)
    assembly_transform = np.eye(4)
    assembly_transform[:3, :3] = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, -1.0, 0.0],
        ]
    )
    assembly_transform[:3, 3] = [0.0, 0.0, 6.0]
    coupon_pose.apply_transform(assembly_transform)

    seated_overlap = _intersection_volume(coupon_pose, rail_base)
    if seated_overlap > 1e-3:
        raise ValueError(
            f"Hook and rail overlap {seated_overlap:.6f} mm3 when seated"
        )

    outward_probe = coupon_pose.copy()
    outward_probe.apply_translation([0.0, 0.0, 0.40])
    outward_engagement = _intersection_volume(outward_probe, rail_base)
    if outward_engagement < 2.0:
        raise ValueError("C-hooks do not positively oppose outward withdrawal")

    closed_side_probe = coupon_pose.copy()
    closed_side_probe.apply_translation([0.0, 0.0, -0.40])
    closed_side_engagement = _intersection_volume(
        closed_side_probe,
        rail_base,
    )
    if closed_side_engagement < 2.0:
        raise ValueError("C-hooks do not retain against the closed side")

    snap_path = []
    for distance in np.arange(0.0, 4.01, 0.10):
        probe = coupon_pose.copy()
        probe.apply_translation([0.0, -float(distance), 0.0])
        snap_path.append(
            {
                "translation_mm": round(float(distance), 2),
                "interference_mm3": round(
                    _intersection_volume(probe, rail_base),
                    6,
                ),
            }
        )
    peak_snap_interference = max(
        item["interference_mm3"] for item in snap_path
    )
    if not 0.10 <= peak_snap_interference <= 1.50:
        raise ValueError(
            f"Hook snap-path peak is {peak_snap_interference:.6f} mm3"
        )

    axial_engagement = {}
    for label, distance in (("negative", -0.30), ("positive", 0.30)):
        probe = coupon_pose.copy()
        probe.apply_translation([distance, 0.0, 0.0])
        axial_engagement[label] = _intersection_volume(probe, rail_base)
        if axial_engagement[label] < 1.0:
            raise ValueError(f"Inner rail caps do not retain axially: {label}")

    coupon_hinge = np.asarray([0.0, 0.0, 6.0])
    pivot_sweep = []
    for angle in range(
        REAL_KEYED_COLLISION_FREE_DEGREES[0],
        REAL_KEYED_COLLISION_FREE_DEGREES[1] + 1,
        5,
    ):
        pose = coupon_pose.copy()
        pose.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(float(angle)),
                [1.0, 0.0, 0.0],
                coupon_hinge,
            )
        )
        pivot_sweep.append(
            {
                "angle_degrees": angle,
                "base_overlap_mm3": round(
                    _intersection_volume(pose, rail_base),
                    6,
                ),
            }
        )
    maximum_pivot_overlap = max(
        item["base_overlap_mm3"] for item in pivot_sweep
    )
    if maximum_pivot_overlap > 1e-3:
        raise ValueError(
            f"Hook/rail coupon pivot overlap is "
            f"{maximum_pivot_overlap:.6f} mm3"
        )

    return {
        "architecture": (
            "extended C-hooks at original source pin pockets with paired rails"
        ),
        "panel_mesh": panel_validation,
        "rail_base_mesh": base_validation,
        "source_material_removed_mm3": round(removed_volume, 6),
        "source_material_removed_percent": round(removed_percent, 4),
        "source_material_added_mm3": round(added_volume, 6),
        "rail_diameter_mm": HOOK_RAIL_DIAMETER,
        "rail_support_axial_embed_mm": round(
            HOOK_RAIL_SUPPORT_AXIAL_EMBED,
            4,
        ),
        "rail_support_top_cover_mm": 0.60,
        "rail_root_shoulder_outer_radius_mm": 2.10,
        "hook_inner_diameter_mm": round(
            2
            * (
                HOOK_RAIL_DIAMETER / 2
                + HOOK_RAIL_RUNNING_CLEARANCE
            ),
            4,
        ),
        "hook_wall_mm": round(
            HOOK_RAIL_HOOK_OUTER_RADIUS
            - HOOK_RAIL_DIAMETER / 2
            - HOOK_RAIL_RUNNING_CLEARANCE,
            4,
        ),
        "radial_running_clearance_mm": HOOK_RAIL_RUNNING_CLEARANCE,
        "hook_axial_width_mm": round(
            HOOK_RAIL_HOOK_U_RANGE[1] - HOOK_RAIL_HOOK_U_RANGE[0],
            4,
        ),
        "mouth_width_mm": HOOK_RAIL_MOUTH_WIDTH,
        "mouth_undercut_per_side_mm": round(
            (HOOK_RAIL_DIAMETER - HOOK_RAIL_MOUTH_WIDTH) / 2,
            4,
        ),
        "seated_overlap_mm3": round(seated_overlap, 6),
        "outward_probe_engagement_mm3": round(outward_engagement, 6),
        "closed_side_probe_engagement_mm3": round(
            closed_side_engagement,
            6,
        ),
        "axial_cap_engagement_mm3": {
            label: round(value, 6)
            for label, value in axial_engagement.items()
        },
        "peak_snap_path_interference_mm3": round(
            peak_snap_interference,
            6,
        ),
        "maximum_pivot_overlap_mm3": round(
            maximum_pivot_overlap,
            6,
        ),
        "snap_path": snap_path,
        "pivot_sweep": pivot_sweep,
    }


def validate_hook_rail_full_integration(
    source_panel: trimesh.Trimesh,
    selected_source_base: trimesh.Trimesh,
    integrated_panel: trimesh.Trimesh,
    integrated_base: trimesh.Trimesh,
) -> dict:
    """Validate the full Tough+ panel and real Matte base-arm rail roots."""
    panel_validation = validate_mesh(
        "hook_rail_integrated_panel",
        integrated_panel,
    )
    base_validation = validate_mesh(
        "hook_rail_integrated_base",
        integrated_base,
    )
    if len(integrated_panel.split()) != 1 or len(integrated_base.split()) != 1:
        raise ValueError("Integrated hook/rail parts are disconnected")

    source_removed = trimesh.boolean.difference(
        [source_panel, integrated_panel],
        engine="manifold",
    )
    source_added = trimesh.boolean.difference(
        [integrated_panel, source_panel],
        engine="manifold",
    )
    removed_volume = (
        0.0
        if source_removed is None or source_removed.is_empty
        else abs(float(source_removed.volume))
    )
    added_volume = (
        0.0
        if source_added is None or source_added.is_empty
        else abs(float(source_added.volume))
    )
    removed_percent = 100.0 * removed_volume / abs(float(source_panel.volume))
    if removed_percent > 5.0:
        raise ValueError(
            f"Integrated hook panel removes {removed_percent:.3f}% of source"
        )

    centre = np.asarray(REAL_KEYED_BASE_HINGE_CENTRE, dtype=float)
    root_overlaps = {}
    for side, label in ((-1.0, "negative"), (1.0, "positive")):
        rail = _hook_rail_integration_rail(side, centre=centre)
        overlap = _intersection_volume(rail, selected_source_base)
        root_overlaps[label] = overlap
        if overlap < 4.0:
            raise ValueError(
                f"{label} production rail root overlaps only {overlap:.4f} mm3"
            )

    panel_crop = _intersection(
        [
            integrated_panel,
            _box((16.0, 18.0, 10.0), (2.0, 0.0, 15.5)),
        ]
    )
    _, _, _, _, frame = _real_keyed_panel_frame()
    panel_pose = panel_crop.copy()
    panel_pose.apply_transform(np.linalg.inv(frame))
    assembly_transform = np.eye(4)
    assembly_transform[:3, :3] = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, -1.0, 0.0],
        ]
    )
    assembly_transform[:3, 3] = [0.0, 0.0, 6.0]
    panel_pose.apply_transform(assembly_transform)

    coupon_centre = np.asarray([0.0, 0.0, 6.0])
    rail_pair = [
        _hook_rail_integration_rail(side, centre=coupon_centre)
        for side in (-1.0, 1.0)
    ]

    def rail_overlap(mesh: trimesh.Trimesh) -> float:
        return sum(_intersection_volume(mesh, rail) for rail in rail_pair)

    seated_overlap = rail_overlap(panel_pose)
    if seated_overlap > 1e-3:
        raise ValueError(
            f"Integrated panel/rail seated overlap is {seated_overlap:.6f} mm3"
        )

    axial_capture = {}
    for label, shift in (("negative", -0.30), ("positive", 0.30)):
        probe = panel_pose.copy()
        probe.apply_translation([shift, 0.0, 0.0])
        axial_capture[label] = rail_overlap(probe)
        if axial_capture[label] < 3.0:
            raise ValueError(f"Integrated rail caps do not capture {label}")

    pivot_sweep = []
    for angle in range(
        REAL_KEYED_COLLISION_FREE_DEGREES[0],
        REAL_KEYED_COLLISION_FREE_DEGREES[1] + 1,
        5,
    ):
        pose = panel_pose.copy()
        pose.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(float(angle)),
                [1.0, 0.0, 0.0],
                coupon_centre,
            )
        )
        pivot_sweep.append(
            {
                "angle_degrees": angle,
                "rail_overlap_mm3": round(rail_overlap(pose), 6),
            }
        )
    maximum_pivot_overlap = max(
        item["rail_overlap_mm3"] for item in pivot_sweep
    )
    if maximum_pivot_overlap > 1e-3:
        raise ValueError(
            f"Integrated rail pivot overlap is {maximum_pivot_overlap:.6f} mm3"
        )

    return {
        "panel_material": "Bambu PLA Tough+",
        "base_material": "Bambu PLA Matte",
        "panel_mesh": panel_validation,
        "base_mesh": base_validation,
        "source_material_removed_mm3": round(removed_volume, 6),
        "source_material_removed_percent": round(removed_percent, 4),
        "source_material_added_mm3": round(added_volume, 6),
        "rail_root_overlap_mm3": {
            label: round(value, 6)
            for label, value in root_overlaps.items()
        },
        "seated_overlap_mm3": round(seated_overlap, 6),
        "axial_cap_capture_mm3": {
            label: round(value, 6)
            for label, value in axial_capture.items()
        },
        "maximum_pivot_overlap_mm3": round(
            maximum_pivot_overlap,
            6,
        ),
        "pivot_sweep": pivot_sweep,
    }


def _full_base_panel_pose(
    panel: trimesh.Trimesh,
    angle_deg: float,
) -> trimesh.Trimesh:
    """Place the lower panel connector on the positive-Y source base arm."""
    frame = _full_base_lower_panel_frame()[4]
    pose = panel.copy()
    pose.apply_transform(np.linalg.inv(frame))
    u_axis = np.asarray([1.0, 0.0, 0.0])
    v_axis = np.asarray([0.0, 1.0, 0.0])
    w_axis = np.asarray([0.0, 0.0, 1.0])
    rotation = trimesh.transformations.rotation_matrix(
        math.radians(float(angle_deg)),
        u_axis,
    )[:3, :3]
    transform = np.eye(4)
    transform[:3, :3] = np.column_stack(
        [u_axis, rotation @ v_axis, rotation @ w_axis]
    )
    transform[:3, 3] = np.asarray(REAL_KEYED_BASE_HINGE_CENTRE)
    pose.apply_transform(transform)
    return pose


def validate_full_base_hook_architecture(
    source_panel: trimesh.Trimesh,
    selected_source_base: trimesh.Trimesh,
    panel: trimesh.Trimesh,
    base: trimesh.Trimesh,
) -> dict:
    """Validate the true lower-axis panel rails against all six base arms."""
    panel_validation = validate_mesh("lower_panel_matte_rails", panel)
    base_validation = validate_mesh("full_base_tough_hooks", base)
    if len(panel.split()) != 1 or len(base.split()) != 1:
        raise ValueError("Full-base hook test contains disconnected solids")

    source_panel_removed = trimesh.boolean.difference(
        [source_panel, panel],
        engine="manifold",
    )
    source_panel_added = trimesh.boolean.difference(
        [panel, source_panel],
        engine="manifold",
    )
    panel_removed_volume = (
        0.0
        if source_panel_removed is None or source_panel_removed.is_empty
        else abs(float(source_panel_removed.volume))
    )
    panel_added_volume = (
        0.0
        if source_panel_added is None or source_panel_added.is_empty
        else abs(float(source_panel_added.volume))
    )
    panel_removed_percent = (
        100.0 * panel_removed_volume / abs(float(source_panel.volume))
    )
    if panel_removed_percent > 3.0:
        raise ValueError(
            f"Lower rail panel removes {panel_removed_percent:.3f}% of source"
        )
    if not np.allclose(panel.bounds, source_panel.bounds, atol=1e-4):
        raise ValueError("Lower rail conversion changes the panel silhouette")

    source_base_removed = trimesh.boolean.difference(
        [selected_source_base, base],
        engine="manifold",
    )
    source_base_added = trimesh.boolean.difference(
        [base, selected_source_base],
        engine="manifold",
    )
    base_removed_volume = (
        0.0
        if source_base_removed is None or source_base_removed.is_empty
        else abs(float(source_base_removed.volume))
    )
    base_added_volume = (
        0.0
        if source_base_added is None or source_base_added.is_empty
        else abs(float(source_base_added.volume))
    )
    base_removed_percent = (
        100.0 * base_removed_volume / abs(float(selected_source_base.volume))
    )
    if base_removed_percent > 15.0:
        raise ValueError(
            f"Full hook base removes {base_removed_percent:.3f}% of source"
        )

    hook_groups = []
    all_hooks = []
    all_cutters = []
    for angle_deg in BASE_ARM_ANGLES_DEG:
        hooks, cutters = _full_base_hook_geometry(angle_deg)
        hook_groups.append(hooks)
        all_hooks.extend(hooks)
        all_cutters.extend(cutters)
    cleared_source = _difference(selected_source_base.copy(), all_cutters)
    root_overlaps = [
        _intersection_volume(hook, cleared_source)
        for hook in all_hooks
    ]
    if min(root_overlaps) < 0.50:
        raise ValueError(
            f"Minimum full-base hook root overlap is {min(root_overlaps):.4f} mm3"
        )

    adjacent_overlap = 0.0
    for index, group in enumerate(hook_groups):
        neighbour = hook_groups[(index + 1) % len(hook_groups)]
        adjacent_overlap = max(
            adjacent_overlap,
            sum(
                _intersection_volume(first, second)
                for first in group
                for second in neighbour
            ),
        )
    if adjacent_overlap > 1e-4:
        raise ValueError(
            f"Adjacent full-base hooks overlap {adjacent_overlap:.6f} mm3"
        )

    origin, _, _, _, transform = _full_base_lower_panel_frame()
    rail_root_overlaps = []
    for side in (-1.0, 1.0):
        root_u = _hook_rail_mirrored_u_range(
            FULL_BASE_PANEL_RAIL_ROOT_U_RANGE,
            side,
        )
        root = trimesh.creation.cylinder(
            radius=FULL_BASE_PANEL_RAIL_ROOT_RADIUS,
            segment=np.asarray(
                [[root_u[0], 0.0, 0.0], [root_u[1], 0.0, 0.0]]
            ),
            sections=96,
        )
        root.apply_transform(transform)
        rail_root_overlaps.append(_intersection_volume(root, source_panel))
    if min(rail_root_overlaps) < 5.0:
        raise ValueError(
            "Lower panel rail root embeds less than 5.00 mm3 in source"
        )

    panel_pose = _full_base_panel_pose(
        panel,
        FULL_BASE_ASSEMBLY_ANGLE_DEG,
    )
    seated_overlap = _intersection_volume(panel_pose, base)
    if seated_overlap > 1e-3:
        raise ValueError(
            f"Full-base hook/rail seated overlap is {seated_overlap:.6f} mm3"
        )

    snap_path = []
    for distance in np.arange(0.0, 8.01, 0.10):
        probe = panel_pose.copy()
        probe.apply_translation([0.0, float(distance), 0.0])
        source_interference = _intersection_volume(probe, cleared_source)
        snap_path.append(
            {
                "translation_mm": round(float(distance), 2),
                "interference_mm3": round(
                    _intersection_volume(probe, base),
                    6,
                ),
                "non_hook_base_interference_mm3": round(
                    source_interference,
                    6,
                ),
            }
        )
    peak_snap_interference = max(
        item["interference_mm3"] for item in snap_path
    )
    if not 0.30 <= peak_snap_interference <= 1.20:
        raise ValueError(
            f"Full-panel snap-path peak is {peak_snap_interference:.6f} mm3"
        )
    if snap_path[-1]["interference_mm3"] > 1e-3:
        raise ValueError("Full panel has no collision-free external start pose")
    maximum_non_hook_interference = max(
        item["non_hook_base_interference_mm3"] for item in snap_path
    )
    if maximum_non_hook_interference > 1e-4:
        raise ValueError(
            "Full-panel insertion contacts non-hook base material by "
            f"{maximum_non_hook_interference:.6f} mm3"
        )

    axial_capture = {}
    for label, shift in (("negative", -0.30), ("positive", 0.30)):
        probe = panel_pose.copy()
        probe.apply_translation([shift, 0.0, 0.0])
        axial_capture[label] = _intersection_volume(probe, base)
        if axial_capture[label] < 2.0:
            raise ValueError(f"Full-base rail root does not capture {label}")

    pivot_sweep = []
    for angle in range(
        FULL_BASE_COLLISION_FREE_DEGREES[0],
        FULL_BASE_COLLISION_FREE_DEGREES[1] + 1,
    ):
        pose = _full_base_panel_pose(panel, float(angle))
        pivot_sweep.append(
            {
                "angle_degrees": angle,
                "base_overlap_mm3": round(
                    _intersection_volume(pose, base),
                    6,
                ),
            }
        )
    maximum_pivot_overlap = max(
        item["base_overlap_mm3"] for item in pivot_sweep
    )
    if maximum_pivot_overlap > 1e-3:
        raise ValueError(
            f"Full-base pivot overlap is {maximum_pivot_overlap:.6f} mm3"
        )

    return {
        "architecture": (
            "Tough+ hooks on all six source base arms with rigid Matte rails "
            "at the panel's true lower connector"
        ),
        "base_material": "Bambu PLA Tough+",
        "panel_material": "Bambu PLA Matte",
        "base_mesh": base_validation,
        "panel_mesh": panel_validation,
        "source_base_material_removed_mm3": round(base_removed_volume, 6),
        "source_base_material_removed_percent": round(base_removed_percent, 4),
        "source_base_material_added_mm3": round(base_added_volume, 6),
        "source_panel_material_removed_mm3": round(
            panel_removed_volume,
            6,
        ),
        "source_panel_material_removed_percent": round(
            panel_removed_percent,
            4,
        ),
        "source_panel_material_added_mm3": round(panel_added_volume, 6),
        "minimum_hook_root_overlap_mm3": round(min(root_overlaps), 6),
        "maximum_adjacent_hook_overlap_mm3": round(adjacent_overlap, 6),
        "minimum_panel_rail_root_overlap_mm3": round(
            min(rail_root_overlaps),
            6,
        ),
        "rail_diameter_mm": HOOK_RAIL_DIAMETER,
        "hook_inner_diameter_mm": round(
            2
            * (
                HOOK_RAIL_DIAMETER / 2
                + HOOK_RAIL_RUNNING_CLEARANCE
            ),
            4,
        ),
        "hook_axial_width_mm": round(
            FULL_BASE_HOOK_U_RANGE[1] - FULL_BASE_HOOK_U_RANGE[0],
            4,
        ),
        "hook_mouth_width_mm": FULL_BASE_HOOK_MOUTH_WIDTH,
        "hook_mouth_undercut_per_side_mm": round(
            (HOOK_RAIL_DIAMETER - FULL_BASE_HOOK_MOUTH_WIDTH) / 2,
            4,
        ),
        "seated_overlap_mm3": round(seated_overlap, 6),
        "peak_snap_path_interference_mm3": round(
            peak_snap_interference,
            6,
        ),
        "maximum_non_hook_insertion_overlap_mm3": round(
            maximum_non_hook_interference,
            6,
        ),
        "axial_capture_mm3": {
            label: round(value, 6)
            for label, value in axial_capture.items()
        },
        "collision_free_range_degrees": list(
            FULL_BASE_COLLISION_FREE_DEGREES
        ),
        "maximum_pivot_overlap_mm3": round(maximum_pivot_overlap, 6),
        "snap_path": snap_path,
        "pivot_sweep": pivot_sweep,
    }


def validate_real_keyed_joint(
    source_panel: trimesh.Trimesh,
    panel: trimesh.Trimesh,
    insert: trimesh.Trimesh,
    base: trimesh.Trimesh,
) -> dict:
    """Validate fidelity, stop registration, pin walls, and pivot sweep."""
    _, _, panel_axis, _, panel_frame = _real_keyed_panel_frame()

    source_removed = trimesh.boolean.difference(
        [source_panel, panel],
        engine="manifold",
    )
    source_added = trimesh.boolean.difference(
        [panel, source_panel],
        engine="manifold",
    )
    removed_volume = (
        0.0
        if source_removed is None or source_removed.is_empty
        else abs(float(source_removed.volume))
    )
    added_volume = (
        0.0
        if source_added is None or source_added.is_empty
        else abs(float(source_added.volume))
    )
    removed_percent = 100.0 * removed_volume / abs(float(source_panel.volume))
    added_percent = 100.0 * added_volume / abs(float(source_panel.volume))
    if removed_percent > 3.5:
        raise ValueError(
            f"Twin-rail panel removes {removed_percent:.3f}% of source volume"
        )
    if not np.allclose(panel.bounds, source_panel.bounds, atol=1e-4):
        raise ValueError("Twin-rail receiver changes the source panel silhouette")

    inverse_frame = np.linalg.inv(panel_frame)
    changed_vertices = []
    for changed in (source_removed, source_added):
        if changed is None or changed.is_empty:
            continue
        for component in changed.split(only_watertight=False):
            # Booleaning the tessellated STL can create remote numerical
            # slivers below one cubic micron. They are not authored changes.
            if abs(float(component.volume)) < 1e-4:
                continue
            local = trimesh.transform_points(
                component.vertices,
                inverse_frame,
            )
            changed_vertices.append(local)
    if changed_vertices:
        changed_local = np.vstack(changed_vertices)
        inside_mask = (
            (np.abs(changed_local[:, 0]) <= 6.10)
            & (changed_local[:, 1] >= -5.75)
            & (changed_local[:, 1] <= 3.50)
            & (changed_local[:, 2] >= -2.40)
            & (changed_local[:, 2] <= 2.90)
        )
        if not bool(np.all(inside_mask)):
            outside_count = int(np.count_nonzero(~inside_mask))
            raise ValueError(
                f"{outside_count} changed vertices fall outside connector mask"
            )

    authored_overlap = _intersection_volume(panel, insert)
    if authored_overlap > 1e-4:
        raise ValueError(
            f"Panel/cartridge authored overlap is {authored_overlap:.6f} mm3"
        )

    def stop_overlap(shift: float) -> float:
        probe = insert.copy()
        probe.apply_translation(-shift * panel_axis)
        return _intersection_volume(panel, probe)

    low = 0.0
    high = 0.08
    if stop_overlap(high) < 1e-5:
        raise ValueError("Primary rail does not register on its closed stop")
    for _ in range(18):
        middle = (low + high) / 2
        if stop_overlap(middle) >= 1e-5:
            high = middle
        else:
            low = middle
    stop_contact = high
    if stop_contact > 0.03:
        raise ValueError(
            f"Stop leaves {stop_contact:.4f} mm hinge-hole misregistration"
        )

    # Probe only the production hook. The former whole-cartridge probe could
    # count unrelated ear/shell contact and falsely report a working latch.
    latch_hook = trimesh.creation.icosphere(
        subdivisions=3,
        radius=TWIN_RAIL_LATCH_HOOK_RADII[1],
    )
    latch_hook.apply_translation(_real_keyed_point(REAL_KEYED_LATCH_CENTRE))
    if _intersection_volume(panel, latch_hook) > 1e-4:
        raise ValueError("Twin-rail hook overlaps its notch when seated")
    latch_probe = latch_hook.copy()
    latch_probe.apply_translation(0.25 * panel_axis)
    latch_engagement = _intersection_volume(panel, latch_probe)
    if latch_engagement < 0.005:
        raise ValueError("Twin-rail latch has no positive withdrawal engagement")

    fixed_ear_ligament = (
        REAL_KEYED_EAR_OUTER_RADIUS
        - REAL_KEYED_FIXED_EAR_DIAMETER / 2
    )
    running_ear_ligament = (
        REAL_KEYED_EAR_OUTER_RADIUS
        - REAL_KEYED_RUNNING_HOLE_DIAMETER / 2
    )
    if min(fixed_ear_ligament, running_ear_ligament) < 1.20:
        raise ValueError("Clevis ear has less than 1.20 mm radial ligament")
    tongue_ligament = (
        REAL_KEYED_BASE_BOSS_RADIUS
        - REAL_KEYED_RUNNING_HOLE_DIAMETER / 2
    )
    if tongue_ligament < 1.20:
        raise ValueError("Base tongue has less than 1.20 mm radial ligament")

    panel_pose = panel.copy()
    insert_pose = insert.copy()
    transform = _real_keyed_panel_to_base_transform()
    panel_pose.apply_transform(transform)
    insert_pose.apply_transform(transform)
    hinge = np.asarray(REAL_KEYED_BASE_HINGE_CENTRE)

    assembled_overlap = {
        "panel_insert_mm3": _intersection_volume(panel_pose, insert_pose),
        "panel_base_mm3": _intersection_volume(panel_pose, base),
        "insert_base_mm3": _intersection_volume(insert_pose, base),
    }
    base_points = base.vertices[
        :: max(1, len(base.vertices) // 1500)
    ]
    base_tree = cKDTree(base_points)

    def clearance_to_base(moved: trimesh.Trimesh) -> float:
        moving_points = moved.vertices[
            :: max(1, len(moved.vertices) // 1500)
        ]
        forward = base_tree.query(moving_points, workers=-1)[0]
        reverse = cKDTree(moving_points).query(
            base_points,
            workers=-1,
        )[0]
        return float(min(np.min(forward), np.min(reverse)))

    def evaluate_angle(angle: float) -> dict:
        rotation = trimesh.transformations.rotation_matrix(
            math.radians(float(angle)),
            [1.0, 0.0, 0.0],
            hinge,
        )
        moved_panel = panel_pose.copy()
        moved_insert = insert_pose.copy()
        moved_panel.apply_transform(rotation)
        moved_insert.apply_transform(rotation)
        panel_overlap = _intersection_volume(moved_panel, base)
        insert_overlap = _intersection_volume(moved_insert, base)
        moving = trimesh.util.concatenate([moved_panel, moved_insert])
        return {
            "angle_degrees": round(float(angle), 3),
            "panel_base_overlap_mm3": round(panel_overlap, 6),
            "insert_base_overlap_mm3": round(insert_overlap, 6),
            "sampled_clearance_mm": round(clearance_to_base(moving), 5),
        }

    coarse_angles = np.arange(
        REAL_KEYED_COLLISION_FREE_DEGREES[0],
        REAL_KEYED_COLLISION_FREE_DEGREES[1] + 0.5,
        1.0,
    )
    coarse = [evaluate_angle(float(angle)) for angle in coarse_angles]
    lowest = sorted(
        coarse,
        key=lambda item: item["sampled_clearance_mm"],
    )[:5]
    refined_angles = set(float(value) for value in coarse_angles)
    for item in lowest:
        centre = float(item["angle_degrees"])
        for angle in np.arange(centre - 1.0, centre + 1.001, 0.10):
            if (
                REAL_KEYED_COLLISION_FREE_DEGREES[0]
                <= angle
                <= REAL_KEYED_COLLISION_FREE_DEGREES[1]
            ):
                refined_angles.add(round(float(angle), 3))
        for angle in np.arange(centre - 0.20, centre + 0.201, 0.05):
            if (
                REAL_KEYED_COLLISION_FREE_DEGREES[0]
                <= angle
                <= REAL_KEYED_COLLISION_FREE_DEGREES[1]
            ):
                refined_angles.add(round(float(angle), 3))
    coarse_by_angle = {
        float(item["angle_degrees"]): item
        for item in coarse
    }
    sweep = [
        coarse_by_angle.get(angle) or evaluate_angle(angle)
        for angle in sorted(refined_angles)
    ]

    maximum_overlap = max(
        [
            *assembled_overlap.values(),
            *[
                item[key]
                for item in sweep
                for key in (
                    "panel_base_overlap_mm3",
                    "insert_base_overlap_mm3",
                )
            ],
        ]
    )
    if maximum_overlap > 1e-4:
        raise ValueError(
            f"Real keyed joint collision volume is {maximum_overlap:.6f} mm3"
        )
    return {
        "source_fidelity": {
            "source_volume_mm3": round(abs(float(source_panel.volume)), 6),
            "candidate_volume_mm3": round(abs(float(panel.volume)), 6),
            "removed_volume_mm3": round(removed_volume, 6),
            "removed_percent": round(removed_percent, 4),
            "added_volume_mm3": round(added_volume, 6),
            "added_percent": round(added_percent, 4),
            "bounds_unchanged": True,
            "changes_inside_connector_mask": True,
        },
        "architecture": "masked twin-rail one-piece clevis cartridge",
        "fixed_ear_diameter_mm": REAL_KEYED_FIXED_EAR_DIAMETER,
        "running_hole_diameter_mm": REAL_KEYED_RUNNING_HOLE_DIAMETER,
        "filament_pin_diameter_mm": 1.75,
        "panel_hinge_inward_offset_mm": REAL_KEYED_PANEL_INWARD_OFFSET,
        "authored_stop_clearance_mm": REAL_KEYED_STOP_CLEARANCE,
        "measured_stop_contact_mm": round(stop_contact, 5),
        "hinge_registration_error_at_stop_mm": round(stop_contact, 5),
        "fixed_ear_radial_ligament_mm": round(fixed_ear_ligament, 4),
        "running_ear_radial_ligament_mm": round(
            running_ear_ligament,
            4,
        ),
        "tongue_radial_ligament_mm": round(tongue_ligament, 4),
        "rail_clearance_per_side_mm": {
            "primary_tail": round(
                (
                    REAL_KEYED_CHANNEL_TAIL_WIDTH
                    - REAL_KEYED_PRIMARY_KEY_WIDTHS[0]
                )
                / 2,
                4,
            ),
            "primary_throat": round(
                (
                    REAL_KEYED_CHANNEL_THROAT_WIDTH
                    - REAL_KEYED_PRIMARY_KEY_WIDTHS[1]
                )
                / 2,
                4,
            ),
            "follower_tail": round(
                (
                    REAL_KEYED_CHANNEL_TAIL_WIDTH
                    - REAL_KEYED_FOLLOWER_KEY_WIDTHS[0]
                )
                / 2,
                4,
            ),
            "follower_throat": round(
                (
                    REAL_KEYED_CHANNEL_THROAT_WIDTH
                    - REAL_KEYED_FOLLOWER_KEY_WIDTHS[1]
                )
                / 2,
                4,
            ),
        },
        "rail_floor_clearance_mm": round(
            REAL_KEYED_KEY_W_RANGE[0]
            - REAL_KEYED_CHANNEL_W_RANGE[0],
            4,
        ),
        "authored_minimum_outer_skin_mm": 1.50,
        "latch_withdrawal_probe": {
            "translation_mm": 0.25,
            "engagement_volume_mm3": round(latch_engagement, 6),
            "physical_release_force_required": "coupon gate",
        },
        "panel_insert_authored_overlap_mm3": round(authored_overlap, 6),
        "closed_stop_probe": {
            "zero_shift_overlap_mm3": round(stop_overlap(0.0), 6),
            "contact_overlap_mm3": round(stop_overlap(stop_contact), 6),
        },
        "collision_free_range_degrees": list(
            REAL_KEYED_COLLISION_FREE_DEGREES
        ),
        "assembled_overlap_mm3": {
            key: round(value, 6)
            for key, value in assembled_overlap.items()
        },
        "sweep": sweep,
    }


def compare_surfaces(
    reference: trimesh.Trimesh,
    candidate: trimesh.Trimesh,
    *,
    sample_count: int = 6000,
    seed: int = 188,
) -> dict:
    """Return bidirectional sampled surface error in millimetres."""
    state = np.random.get_state()
    np.random.seed(seed)
    try:
        forward_points, _ = trimesh.sample.sample_surface(candidate, sample_count)
        reverse_points, _ = trimesh.sample.sample_surface(reference, sample_count)
    finally:
        np.random.set_state(state)
    forward = np.abs(trimesh.proximity.signed_distance(reference, forward_points))
    reverse = np.abs(trimesh.proximity.signed_distance(candidate, reverse_points))

    def summary(values: np.ndarray) -> dict[str, float]:
        return {
            "mean": round(float(np.mean(values)), 5),
            "p95": round(float(np.percentile(values, 95)), 5),
            "max": round(float(np.max(values)), 5),
        }

    return {
        "candidate_to_reference_mm": summary(forward),
        "reference_to_candidate_mm": summary(reverse),
        "volume_delta_percent": round(
            100.0
            * (abs(candidate.volume) - abs(reference.volume))
            / abs(reference.volume),
            4,
        ),
    }


def validate_source_sector_assembly(
    link: trimesh.Trimesh,
    panel: trimesh.Trimesh,
) -> dict:
    """Validate the source one-link/two-panel pairing before packaging it.

    Both panels use the lower blind-pocket end. Panel A connects to the upper
    link pin pair at the neutral angle. Panel B connects to the lower pair
    after the source-observed fold. The tiny Panel-B/link overlap is the
    intended blind-pocket interference plus STL tessellation, not a body clash.
    """

    def placed_panel(
        target_xz: tuple[float, float],
        angle_deg: float,
    ) -> trimesh.Trimesh:
        result = panel.copy()
        source_socket = np.asarray(
            [PANEL_SOCKET_CENTRES_XZ[0][0], 0.0, PANEL_SOCKET_CENTRES_XZ[0][1]]
        )
        result.apply_translation(-source_socket)
        result.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(angle_deg),
                [0.0, 1.0, 0.0],
            )
        )
        result.apply_translation([target_xz[0], 0.0, target_xz[1]])
        return result

    def intersection_volume(
        first: trimesh.Trimesh,
        second: trimesh.Trimesh,
    ) -> float:
        intersection = trimesh.boolean.intersection(
            [first, second],
            engine="manifold",
        )
        if intersection is None:
            return 0.0
        return abs(float(intersection.volume))

    lower_pin, upper_pin = SOURCE_LINK_PIN_CENTRES_XZ
    panel_a = placed_panel(upper_pin, 0.0)
    panel_b = placed_panel(lower_pin, SOURCE_SECTOR_SECOND_PANEL_ANGLE_DEG)
    collisions = {
        "link_to_panel_a_mm3": round(
            intersection_volume(link, panel_a),
            6,
        ),
        "link_to_panel_b_mm3": round(
            intersection_volume(link, panel_b),
            6,
        ),
        "panel_a_to_panel_b_mm3": round(
            intersection_volume(panel_a, panel_b),
            6,
        ),
    }
    if collisions["link_to_panel_a_mm3"] > 0.01:
        raise ValueError("Source panel A has unexpected link body collision")
    if collisions["link_to_panel_b_mm3"] > 0.25:
        raise ValueError("Source panel B has excessive link body collision")
    if collisions["panel_a_to_panel_b_mm3"] > 0.01:
        raise ValueError("Source sector panels collide")
    return {
        "panel_socket_used": "lower blind pocket on both panels",
        "panel_a_connection": "upper link pin pair at 0 degrees",
        "panel_b_connection": (
            f"lower link pin pair at {SOURCE_SECTOR_SECOND_PANEL_ANGLE_DEG:.1f} degrees"
        ),
        "collision_volumes": collisions,
        "status": "joint geometry accepted",
    }


def build_bearing_fit_coupon() -> trimesh.Trimesh:
    """R188 outer-race sockets and inner-race shafts on one labelled gauge."""
    plate_width = 78.0
    plate_depth = 38.0
    plate_height = R188.width
    plate = _rounded_prism(plate_width, plate_depth, plate_height, 3.0)
    x_positions = (-25.0, 0.0, 25.0)

    housing_cutters = [
        _cylinder(
            diameter,
            plate_height + 2.0,
            (x, 9.5, plate_height / 2),
        )
        for x, diameter in zip(x_positions, COUPONS.housing_diameters)
    ]
    coupon = _difference(plate, housing_cutters)

    shaft_bases = []
    shafts = []
    identifiers = []
    for index, (x, diameter) in enumerate(
        zip(x_positions, COUPONS.shaft_diameters),
        start=1,
    ):
        shaft_bases.append(
            _cylinder(10.0, 1.2, (x, -9.5, plate_height + 0.6), sections=64)
        )
        shafts.append(
            _cylinder(
                diameter,
                R188.width,
                (x, -9.5, plate_height + 1.2 + R188.width / 2),
            )
        )
        for dot_index in range(index):
            identifiers.append(
                _cylinder(
                    1.0,
                    0.35,
                    (
                        x + (dot_index - (index - 1) / 2) * 1.8,
                        -16.0,
                        plate_height + 0.175,
                    ),
                    sections=24,
                )
            )
    coupon = _union([coupon, *shaft_bases, *shafts, *identifiers])
    coupon.metadata["name"] = "R188 bearing fit matrix"
    return coupon


def _identifier_dots(
    *,
    count: int,
    centre: tuple[float, float],
    z0: float,
    spacing: float = 1.6,
) -> list[trimesh.Trimesh]:
    """Raised tactile dots used to identify coupon variants after printing."""
    return [
        _cylinder(
            0.9,
            0.35,
            (
                centre[0] + (index - (count - 1) / 2) * spacing,
                centre[1],
                z0 + 0.175,
            ),
            sections=24,
        )
        for index in range(count)
    ]


def build_r188_stack_coupons() -> list[tuple[str, trimesh.Trimesh]]:
    """Three base/cap pairs testing 0.10–0.30 mm assembled axial freedom.

    The base shoulder supports only the outer race. The cap's 7.40 mm collar
    addresses only the inner race, while the selected 6.40 mm shaft passes
    through the bearing. In use the printed cap is flipped shaft-down and its
    broad disk seats on the top of the housing.
    """
    housing_height = 6.50
    shoulder_z = 1.20
    through_diameter = 7.20
    cap_disk_height = 2.00
    cap_disk_diameter = 20.00
    inner_race_collar_diameter = 7.40
    shaft_length = 5.40
    output: list[tuple[str, trimesh.Trimesh]] = []

    for index, clearance in enumerate(COUPONS.axial_clearances, start=1):
        body = _cylinder(24.0, housing_height, (0.0, 0.0, housing_height / 2))
        through = _cylinder(
            through_diameter,
            housing_height + 2.0,
            (0.0, 0.0, housing_height / 2),
        )
        pocket_start = shoulder_z
        pocket_height = housing_height - pocket_start + 1.0
        pocket = _cylinder(
            COUPONS.selected_housing_diameter,
            pocket_height,
            (0.0, 0.0, pocket_start + pocket_height / 2),
        )
        # Three underside access holes let the bearing be pushed out against
        # its outer race rather than levering on a shield.
        ejectors = [
            _cylinder(
                2.0,
                shoulder_z + 0.4,
                (
                    5.0 * math.cos(math.radians(angle)),
                    5.0 * math.sin(math.radians(angle)),
                    (shoulder_z + 0.4) / 2,
                ),
                sections=40,
            )
            for angle in (30.0, 150.0, 270.0)
        ]
        base = _difference(body, [through, pocket, *ejectors])
        base = _union(
            [
                base,
                *_identifier_dots(
                    count=index,
                    centre=(0.0, -10.8),
                    z0=housing_height,
                ),
            ]
        )
        base.metadata["name"] = (
            f"R188 stack base {clearance:.2f} mm axial freedom"
        )

        cap_disk = _cylinder(
            cap_disk_diameter,
            cap_disk_height,
            (0.0, 0.0, cap_disk_height / 2),
        )
        shaft_overlap = 0.15
        shaft = _cylinder(
            COUPONS.selected_shaft_diameter,
            shaft_length + shaft_overlap,
            (
                0.0,
                0.0,
                cap_disk_height - shaft_overlap + (shaft_length + shaft_overlap) / 2,
            ),
        )
        bearing_top = shoulder_z + R188.width
        collar_projection = housing_height - bearing_top - clearance
        if collar_projection <= 0:
            raise ValueError("Axial clearance leaves no inner-race collar")
        collar = _cylinder(
            inner_race_collar_diameter,
            collar_projection + shaft_overlap,
            (
                0.0,
                0.0,
                cap_disk_height
                - shaft_overlap
                + (collar_projection + shaft_overlap) / 2,
            ),
        )
        cap = _union(
            [
                cap_disk,
                shaft,
                collar,
                *_identifier_dots(
                    count=index,
                    centre=(0.0, -7.8),
                    z0=cap_disk_height,
                ),
            ]
        )
        cap.metadata["name"] = (
            f"R188 stack cap {clearance:.2f} mm axial freedom — flip to assemble"
        )

        label = f"{clearance:.2f}".replace(".", "_")
        output.extend(
            [
                (f"r188_stack_{label}_base", base),
                (f"r188_stack_{label}_cap", cap),
            ]
        )
    return output


def build_pin_socket_coupons() -> list[tuple[str, trimesh.Trimesh]]:
    """Source-like snap heads and panel sockets, identified by one to three dots."""
    output: list[tuple[str, trimesh.Trimesh]] = []
    base_height = 2.00
    stem_height = 2.20
    stem_diameter = 1.95
    head_height = 1.50

    for index, head_diameter in enumerate(COUPONS.pin_head_diameters, start=1):
        base = _cylinder(12.0, base_height, (0.0, 0.0, base_height / 2))
        root_overlap = 0.15
        stem = _cylinder(
            stem_diameter,
            stem_height + root_overlap,
            (
                0.0,
                0.0,
                base_height - root_overlap + (stem_height + root_overlap) / 2,
            ),
            sections=64,
        )
        head = _cone_between(
            head_diameter / 2,
            (0.0, 0.0, base_height + stem_height - root_overlap),
            (0.0, 0.0, base_height + stem_height + head_height),
        )
        pin = _union(
            [
                base,
                stem,
                head,
                *_identifier_dots(
                    count=index,
                    centre=(0.0, -4.8),
                    z0=base_height,
                    spacing=1.3,
                ),
            ]
        )
        pin.metadata["name"] = (
            f"Snap pin head {head_diameter:.2f} mm / stem {stem_diameter:.2f} mm"
        )
        label = f"{head_diameter:.2f}".replace(".", "_")
        output.append((f"snap_pin_head_{label}", pin))

    for index, socket_diameter in enumerate(COUPONS.socket_diameters, start=1):
        ring = _cylinder(10.0, 2.0, (0.0, 0.0, 1.0), sections=96)
        handle = _rounded_prism(9.0, 5.0, 2.0, 1.5)
        handle.apply_translation([6.0, 0.0, 0.0])
        socket = _union([ring, handle])
        cutter = _cylinder(
            socket_diameter,
            4.0,
            (0.0, 0.0, 2.0),
            sections=64,
        )
        socket = _difference(socket, [cutter])
        socket = _union(
            [
                socket,
                *_identifier_dots(
                    count=index,
                    centre=(7.0, 0.0),
                    z0=2.0,
                    spacing=1.2,
                ),
            ]
        )
        socket.metadata["name"] = f"Panel socket {socket_diameter:.2f} mm"
        label = f"{socket_diameter:.2f}".replace(".", "_")
        output.append((f"panel_socket_{label}", socket))
    return output


def build_nominal_socket_pair_coupons() -> list[tuple[str, trimesh.Trimesh]]:
    """Three fresh Ø2.20 sockets, dot-matched to the three pin-head variants."""
    output: list[tuple[str, trimesh.Trimesh]] = []
    for index in range(1, 4):
        ring = _cylinder(10.0, 2.0, (0.0, 0.0, 1.0), sections=96)
        handle = _rounded_prism(9.0, 5.0, 2.0, 1.5)
        handle.apply_translation([6.0, 0.0, 0.0])
        socket = _union([ring, handle])
        cutter = _cylinder(
            PANEL_SOCKET_DIAMETER,
            4.0,
            (0.0, 0.0, 2.0),
            sections=64,
        )
        socket = _difference(socket, [cutter])
        socket = _union(
            [
                socket,
                *_identifier_dots(
                    count=index,
                    centre=(7.0, 0.0),
                    z0=2.0,
                    spacing=1.2,
                ),
            ]
        )
        socket.metadata["name"] = (
            f"Panel socket {PANEL_SOCKET_DIAMETER:.2f} mm — pair {index}"
        )
        output.append((f"panel_socket_2_20_pair_{index}", socket))
    return output


def build_compliant_socket_coupons() -> list[tuple[str, trimesh.Trimesh]]:
    """Reinforced pins paired with thin split sockets that provide compliance.

    The first rigid-ring matrix failed because the pin had to bend to create
    every bit of snap-through displacement. These C-shaped socket tabs move
    that compliance into the panel-side feature, while the pin receives a
    broad tapered root representative of the source link blend.
    """
    output: list[tuple[str, trimesh.Trimesh]] = []
    pin_profile = np.asarray(
        [
            (0.000, 1.850),
            (2.000, 1.850),
            (2.000, 2.050),
            (1.400, 2.450),
            (0.975, 2.800),
            (0.975, 4.600),
            (1.175, 4.600),
            (1.175, 4.900),
            (0.400, 6.100),
            (0.000, 6.100),
            (0.000, 1.850),
        ]
    )

    for index, slot_width in enumerate(COUPONS.compliant_socket_slots, start=1):
        base = _cylinder(12.0, 2.0, (0.0, 0.0, 1.0))
        pin_body = trimesh.creation.revolve(pin_profile, sections=128)
        pin = _union(
            [
                base,
                pin_body,
                *_identifier_dots(
                    count=index,
                    centre=(0.0, -4.8),
                    z0=2.0,
                    spacing=1.3,
                ),
            ]
        )
        pin.metadata["name"] = (
            f"Reinforced snap pin 2.35 mm head — pair {index}"
        )
        output.append((f"reinforced_snap_pin_pair_{index}", pin))

        socket_thickness = 1.20
        ring = _cylinder(
            10.0,
            socket_thickness,
            (0.0, 0.0, socket_thickness / 2),
            sections=96,
        )
        handle = _rounded_prism(9.0, 5.0, socket_thickness, 1.5)
        handle.apply_translation([6.0, 0.0, 0.0])
        socket = _union([ring, handle])
        hole = _cylinder(
            PANEL_SOCKET_DIAMETER,
            socket_thickness + 2.0,
            (0.0, 0.0, socket_thickness / 2),
            sections=64,
        )
        slit = _box(
            (5.0, slot_width, socket_thickness + 2.0),
            (-3.5, 0.0, socket_thickness / 2),
        )
        socket = _difference(socket, [hole, slit])
        socket = _union(
            [
                socket,
                *_identifier_dots(
                    count=index,
                    centre=(7.0, 0.0),
                    z0=socket_thickness,
                    spacing=1.2,
                ),
            ]
        )
        socket.metadata["name"] = (
            f"Compliant panel socket 2.20 mm / {slot_width:.2f} mm slit"
        )
        label = f"{slot_width:.2f}".replace(".", "_")
        output.append((f"compliant_socket_slot_{label}", socket))
    return output


def _capsule_polygon(length: float, width: float):
    radius = width / 2
    return box(
        -length / 2 + radius,
        -radius,
        length / 2 - radius,
        radius,
    ).buffer(radius, resolution=12)


def build_link_root_coupon() -> trimesh.Trimesh:
    """Three flat link-root specimens with progressively wider necks."""
    meshes = []
    base_neck = 2.20
    for index, multiplier in enumerate(COUPONS.link_neck_multipliers):
        neck = base_neck * multiplier
        x = (index - 1) * 20.0
        ends = Point(-6.5, 0).buffer(4.0, resolution=16).union(
            Point(6.5, 0).buffer(4.0, resolution=16)
        )
        bridge = box(-6.5, -neck / 2, 6.5, neck / 2).buffer(
            min(1.0, neck * 0.35),
            resolution=8,
            join_style="round",
        )
        outline = ends.union(bridge)
        specimen = trimesh.creation.extrude_polygon(
            outline,
            height=4.0,
            engine="earcut",
        )
        specimen.apply_translation([x, 0.0, 0.0])
        meshes.append(specimen)
        for dot_index in range(index + 1):
            meshes.append(
                _cylinder(
                    0.9,
                    0.35,
                    (
                        x + (dot_index - index / 2) * 1.5,
                        -3.0,
                        4.175,
                    ),
                    sections=24,
                )
            )
    coupon = _union(meshes)
    coupon.metadata["name"] = "Link neck and root radius coupon"
    return coupon


def build_running_clearance_coupons() -> list[tuple[str, trimesh.Trimesh]]:
    """Separate male/female gauges for 0.40, 0.50, and 0.60 mm side clearance."""
    output: list[tuple[str, trimesh.Trimesh]] = []
    tongue_width = 10.0
    for index, clearance in enumerate(COUPONS.running_clearances, start=1):
        female = _rounded_prism(28.0, 20.0, 4.0, 2.0)
        channel = _box(
            (18.0, tongue_width + 2 * clearance, 5.0),
            (5.0, 0.0, 2.5),
        )
        female = _difference(female, [channel])
        male = _rounded_prism(24.0, tongue_width, 3.4, 1.0)
        male.apply_translation([0.0, 0.0, 0.3])
        for dot_index in range(index):
            male = _union(
                [
                    male,
                    _cylinder(
                        0.9,
                        0.35,
                        (
                            -8.0 + dot_index * 1.5,
                            0.0,
                            3.875,
                        ),
                        sections=24,
                    ),
                ]
            )
        label = f"{clearance:.2f}".replace(".", "_")
        female.metadata["name"] = f"Running clearance {clearance:.2f} female"
        male.metadata["name"] = f"Running clearance {clearance:.2f} male"
        output.extend(
            [
                (f"running_clearance_{label}_female", female),
                (f"running_clearance_{label}_male", male),
            ]
        )
    return output


def _locate_masters(source_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for name, pattern in MASTER_PATTERNS.items():
        matches = sorted(source_dir.glob(pattern))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"Expected one {name} source matching {pattern!r}; found {len(matches)}"
            )
        paths[name] = matches[0]
    return paths


def _preview_png(title: str, accent: str = "#F99963", size: int = 512) -> bytes:
    image = Image.new("RGBA", (size, size), (246, 240, 231, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (56, 120, 456, 392),
        radius=36,
        fill="#FFFFFF",
        outline="#3F3634",
        width=5,
    )
    draw.ellipse((180, 180, 332, 332), fill=accent, outline="#3F3634", width=4)
    draw.text((28, 28), title, fill="#3F3634")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _coupon_model_settings(
    *,
    plate_title: str,
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
    enable_support: bool = False,
    process_overrides: dict[str, str] | None = None,
) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    overrides = {
        "layer_height": "0.20",
        "wall_loops": "4",
        "sparse_infill_density": "15%",
        "sparse_infill_pattern": "gyroid",
        "enable_support": "1" if enable_support else "0",
        "outer_wall_speed": "80",
        "inner_wall_speed": "140",
        "top_shell_layers": "5",
        "bottom_shell_layers": "4",
        "seam_position": "back",
        "fuzzy_skin": "none",
    }
    if enable_support:
        overrides.update(
            {
                "support_type": "normal(auto)",
                "support_style": "snug",
                "support_on_build_plate_only": "1",
                "support_threshold_angle": "30",
                "support_top_z_distance": "0.20",
            }
        )
    if process_overrides:
        overrides.update(process_overrides)
    for index, ((name, source, extruder), mesh) in enumerate(
        zip(objects, meshes),
        start=1,
    ):
        top_id = 99 + index
        lines.extend(
            [
                f'  <object id="{top_id}">',
                f'    <metadata key="name" value="{escape(name)}"/>',
                f'    <metadata key="extruder" value="{extruder}"/>',
                *[
                    f'    <metadata key="{key}" value="{value}"/>'
                    for key, value in overrides.items()
                ],
                f'    <metadata face_count="{len(mesh.faces)}"/>',
                f'    <part id="{index}" subtype="normal_part">',
                f'      <metadata key="name" value="{escape(name)}"/>',
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'      <metadata key="source_file" value="{escape(source.name)}"/>',
                f'      <metadata key="source_object_id" value="{index - 1}"/>',
                f'      <metadata key="source_volume_id" value="{index - 1}"/>',
                f'      <metadata key="extruder" value="{extruder}"/>',
                f'      <mesh_stat face_count="{len(mesh.faces)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" '
                'backwards_edges="0"/>',
                "    </part>",
                "  </object>",
            ]
        )

    lines.extend(
        [
            "  <plate>",
            '    <metadata key="plater_id" value="1"/>',
            f'    <metadata key="plater_name" value="{escape(plate_title)}"/>',
            '    <metadata key="locked" value="false"/>',
            '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
            '    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>',
            '    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>',
            '    <metadata key="top_file" value="Metadata/top_1.png"/>',
            '    <metadata key="pick_file" value="Metadata/pick_1.png"/>',
        ]
    )
    for index in range(1, len(objects) + 1):
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
    for index in range(1, len(objects) + 1):
        lines.append(
            f'    <assemble_item object_id="{99 + index}" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def build_coupon_3mf(
    *,
    output_path: Path,
    plate_title: str,
    objects: list[tuple[str, Path, int]],
    positions: list[tuple[float, float, float]],
    enable_support: bool = False,
    filament_profile: str = "Bambu PLA Matte @BBL P2S",
    filament_id: str = "GFA01",
    filament_colour: str = "#FFFFFF",
    process_overrides: dict[str, str] | None = None,
    filament_profiles: tuple[str, str] | None = None,
    filament_ids: tuple[str, str] | None = None,
    filament_colours: tuple[str, str] | None = None,
) -> Path:
    """Package coupon meshes into a single-plate Bambu Lab P2S Matte PLA project."""
    if len(objects) != len(positions):
        raise ValueError("Each coupon object needs a build position")

    meshes = [trimesh.load_mesh(path, process=True) for _, path, _ in objects]
    for (name, _, _), mesh in zip(objects, meshes):
        validate_mesh(name, mesh)

    bambu.OBJECTS = objects
    bambu.BUILD_POSITIONS = positions

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
        output.writestr("3D/3dmodel.model", bambu.top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr(
            "Metadata/model_settings.config",
            _coupon_model_settings(
                plate_title=plate_title,
                objects=objects,
                meshes=meshes,
                enable_support=enable_support,
                process_overrides=process_overrides,
            ),
        )

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["printer_model"] = "Bambu Lab P2S"
        settings["printer_settings_id"] = "Bambu Lab P2S 0.4 nozzle"
        settings["layer_height"] = "0.20"
        settings["initial_layer_print_height"] = "0.20"
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "1" if enable_support else "0"
        if enable_support:
            settings["support_type"] = "normal(auto)"
            settings["support_style"] = "snug"
            settings["support_on_build_plate_only"] = "1"
            settings["support_threshold_angle"] = "30"
            settings["support_top_z_distance"] = "0.20"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        selected_profiles = list(
            filament_profiles
            if filament_profiles is not None
            else (filament_profile, filament_profile)
        )
        selected_ids = list(
            filament_ids
            if filament_ids is not None
            else (filament_id, filament_id)
        )
        selected_colours = list(
            filament_colours
            if filament_colours is not None
            else (filament_colour, filament_colour)
        )
        settings["filament_type"] = ["PLA", "PLA"]
        settings["filament_vendor"] = ["Bambu Lab", "Bambu Lab"]
        settings["filament_settings_id"] = selected_profiles
        settings["filament_ids"] = selected_ids
        settings["filament_colour"] = selected_colours
        settings["default_filament_colour"] = ["", ""]
        if any("PLA Tough+" in profile for profile in selected_profiles):
            temperatures = [
                "245" if "PLA Tough+" in profile else "220"
                for profile in selected_profiles
            ]
            max_speeds = [
                "21" if "PLA Tough+" in profile else "22"
                for profile in selected_profiles
            ]
            densities = [
                "1.21" if "PLA Tough+" in profile else "1.30"
                for profile in selected_profiles
            ]
            settings["nozzle_temperature"] = temperatures
            settings["nozzle_temperature_initial_layer"] = temperatures
            settings["filament_flow_ratio"] = ["0.98", "0.98"]
            settings["filament_max_volumetric_speed"] = max_speeds
            settings["filament_density"] = densities
        if process_overrides:
            settings.update(process_overrides)
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=2, ensure_ascii=False).encode(),
        )
        for filename in (
            "Metadata/slice_info.config",
            "Metadata/filament_sequence.json",
        ):
            output.writestr(filename, template.read(filename))

        preview = _preview_png(plate_title)
        for stem in ("plate", "plate_no_light", "top", "pick"):
            output.writestr(f"Metadata/{stem}_1.png", preview)

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
    return output_path


def build_twin_rail_curvature_project(
    coupon_dir: Path,
    output_path: Path,
) -> Path:
    """Package only the approved actual-curvature rail/latch test."""
    return build_coupon_3mf(
        output_path=Path(output_path),
        plate_title="Twin-rail actual-curvature latch coupon v3",
        objects=[
            (
                "Matte actual-curvature twin-rail receiver",
                Path(coupon_dir) / "twin_rail_curvature_panel.stl",
                1,
            ),
            (
                "Tough+ twin-rail cartridge - 1.85 mm fixed ear",
                Path(coupon_dir) / "twin_rail_curvature_cartridge.stl",
                2,
            ),
            (
                "Matte 4.50 mm tongue - 2.05 mm chamfered hole",
                Path(coupon_dir) / "twin_rail_curvature_tongue.stl",
                1,
            ),
        ],
        positions=[
            (52.0, 52.0, 0.0),
            (128.0, 204.0, 0.0),
            (204.0, 52.0, 0.0),
        ],
        enable_support=True,
        filament_profiles=(
            "Bambu PLA Matte @BBL P2S",
            "Bambu PLA Tough+ @BBL P2S",
        ),
        filament_ids=("GFA01", "GFA10"),
        filament_colours=("#FFFFFF", "#F97316"),
        process_overrides={
            "layer_height": "0.16",
            "wall_loops": "5",
            "wall_generator": "arachne",
            "sparse_infill_density": "20%",
            "sparse_infill_pattern": "gyroid",
            "outer_wall_line_width": "0.40",
            "inner_wall_line_width": "0.42",
            "outer_wall_speed": "40",
            "inner_wall_speed": "80",
            "small_perimeter_speed": "30",
            "brim_type": "outer_only",
            "brim_width": "3",
            "print_sequence": "by object",
        },
    )


def build_twin_rail_latch_matrix_project(
    coupon_dir: Path,
    output_path: Path,
) -> Path:
    """Package the corrected receiver and three compliant latch strengths."""
    return build_coupon_3mf(
        output_path=Path(output_path),
        plate_title="Twin-rail compliant latch matrix v4 - strengthened bridge",
        objects=[
            (
                "Matte corrected deep-notch receiver",
                Path(coupon_dir) / "twin_rail_latch_matrix_receiver.stl",
                1,
            ),
            (
                "Tough+ easy latch R0.32 - one dot",
                Path(coupon_dir) / "twin_rail_latch_0_32.stl",
                2,
            ),
            (
                "Tough+ balanced latch R0.36 - two dots",
                Path(coupon_dir) / "twin_rail_latch_0_36.stl",
                2,
            ),
            (
                "Tough+ strong latch R0.40 - three dots",
                Path(coupon_dir) / "twin_rail_latch_0_40.stl",
                2,
            ),
        ],
        positions=[
            (50.0, 50.0, 0.0),
            (50.0, 205.0, 0.0),
            (205.0, 50.0, 0.0),
            (205.0, 205.0, 0.0),
        ],
        enable_support=True,
        filament_profiles=(
            "Bambu PLA Matte @BBL P2S",
            "Bambu PLA Tough+ @BBL P2S",
        ),
        filament_ids=("GFA01", "GFA10"),
        filament_colours=("#FFFFFF", "#F97316"),
        process_overrides={
            "layer_height": "0.16",
            "wall_loops": "5",
            "wall_generator": "arachne",
            "sparse_infill_density": "20%",
            "sparse_infill_pattern": "gyroid",
            "outer_wall_line_width": "0.40",
            "inner_wall_line_width": "0.42",
            "outer_wall_speed": "40",
            "inner_wall_speed": "80",
            "small_perimeter_speed": "30",
            "brim_type": "outer_only",
            "brim_width": "3",
            "print_sequence": "by object",
        },
    )


def build_monolithic_receiver_material_project(
    coupon_dir: Path,
    output_path: Path,
) -> Path:
    """Package two identical monolithic coupons with different filaments."""
    mesh_path = Path(coupon_dir) / "monolithic_receiver_clevis_coupon.stl"
    return build_coupon_3mf(
        output_path=Path(output_path),
        plate_title="Monolithic receiver material A-B - Matte and Tough+",
        objects=[
            (
                "Monolithic receiver and clevis - Matte control",
                mesh_path,
                1,
            ),
            (
                "Monolithic receiver and clevis - Tough+ candidate",
                mesh_path,
                2,
            ),
        ],
        positions=[
            (52.0, 52.0, 0.0),
            (204.0, 204.0, 0.0),
        ],
        enable_support=True,
        filament_profiles=(
            "Bambu PLA Matte @BBL P2S",
            "Bambu PLA Tough+ @BBL P2S",
        ),
        filament_ids=("GFA01", "GFA10"),
        filament_colours=("#FFFFFF", "#F97316"),
        process_overrides={
            "layer_height": "0.16",
            "wall_loops": "5",
            "wall_generator": "arachne",
            "sparse_infill_density": "20%",
            "sparse_infill_pattern": "gyroid",
            "outer_wall_line_width": "0.40",
            "inner_wall_line_width": "0.42",
            "outer_wall_speed": "40",
            "inner_wall_speed": "80",
            "small_perimeter_speed": "30",
            "brim_type": "outer_only",
            "brim_width": "3",
            "print_sequence": "by object",
        },
    )


def build_hook_rail_material_project(
    coupon_dir: Path,
    output_path: Path,
) -> Path:
    """Package original-axis Matte/Tough+ hooks with fresh Matte rails."""
    panel_path = Path(coupon_dir) / "hook_rail_panel_coupon.stl"
    rail_path = Path(coupon_dir) / "hook_rail_base_coupon.stl"
    return build_coupon_3mf(
        output_path=Path(output_path),
        plate_title="Original pin-axis hook rail A-B v2 - full supports",
        objects=[
            (
                "Original-axis extended hooks - Matte control",
                panel_path,
                1,
            ),
            (
                "Full-support original-axis rail base A - Matte",
                rail_path,
                1,
            ),
            (
                "Full-support original-axis rail base B - Matte",
                rail_path,
                1,
            ),
            (
                "Original-axis extended hooks - Tough+ candidate",
                panel_path,
                2,
            ),
        ],
        positions=[
            (50.0, 50.0, 0.0),
            (50.0, 205.0, 0.0),
            (205.0, 50.0, 0.0),
            (205.0, 205.0, 0.0),
        ],
        enable_support=True,
        filament_profiles=(
            "Bambu PLA Matte @BBL P2S",
            "Bambu PLA Tough+ @BBL P2S",
        ),
        filament_ids=("GFA01", "GFA10"),
        filament_colours=("#FFFFFF", "#F97316"),
        process_overrides={
            "layer_height": "0.16",
            "wall_loops": "5",
            "wall_generator": "arachne",
            "sparse_infill_density": "20%",
            "sparse_infill_pattern": "gyroid",
            "outer_wall_line_width": "0.40",
            "inner_wall_line_width": "0.42",
            "outer_wall_speed": "40",
            "inner_wall_speed": "80",
            "small_perimeter_speed": "30",
            "brim_type": "outer_only",
            "brim_width": "3",
            "print_sequence": "by object",
        },
    )


def build_hook_rail_full_integration_project(
    coupon_dir: Path,
    output_path: Path,
) -> Path:
    """Package the approved Tough+ panel with one real Matte base arm."""
    panel_path = Path(coupon_dir) / "hook_rail_full_panel.stl"
    base_path = Path(coupon_dir) / "hook_rail_real_base_arm.stl"
    return build_coupon_3mf(
        output_path=Path(output_path),
        plate_title="Full panel and real base-arm hook rail integration",
        objects=[
            (
                "Cropped real base arm with paired rails - Matte",
                base_path,
                1,
            ),
            (
                "Full source panel with extended hooks - Tough+",
                panel_path,
                2,
            ),
        ],
        positions=[
            (65.0, 128.0, 0.0),
            (190.0, 128.0, 0.0),
        ],
        enable_support=True,
        filament_profiles=(
            "Bambu PLA Matte @BBL P2S",
            "Bambu PLA Tough+ @BBL P2S",
        ),
        filament_ids=("GFA01", "GFA10"),
        filament_colours=("#FFFFFF", "#F97316"),
        process_overrides={
            "layer_height": "0.16",
            "wall_loops": "5",
            "wall_generator": "arachne",
            "sparse_infill_density": "20%",
            "sparse_infill_pattern": "gyroid",
            "outer_wall_line_width": "0.40",
            "inner_wall_line_width": "0.42",
            "outer_wall_speed": "40",
            "inner_wall_speed": "80",
            "small_perimeter_speed": "30",
            "brim_type": "outer_only",
            "brim_width": "3",
            "print_sequence": "by object",
        },
    )


def build_full_base_hook_test_project(
    coupon_dir: Path,
    output_path: Path,
) -> Path:
    """Package the panel first, then the complete Tough+ base."""
    return build_coupon_3mf(
        output_path=Path(output_path),
        plate_title="Full base lower-hook and panel-rail test",
        objects=[
            (
                "Matte panel - high-adhesion lower rigid rails",
                Path(coupon_dir) / "lower_panel_matte_rails.stl",
                1,
            ),
            (
                "Complete Tough+ base - twelve lower-axis hooks",
                Path(coupon_dir) / "full_base_tough_hooks.stl",
                2,
            ),
        ],
        positions=[
            (194.0, 128.0, 0.0),
            (62.0, 128.0, 0.0),
        ],
        enable_support=True,
        filament_profiles=(
            "Bambu PLA Matte @BBL P2S",
            "Bambu PLA Tough+ @BBL P2S",
        ),
        filament_ids=("GFA01", "GFA10"),
        filament_colours=("#FFFFFF", "#F97316"),
        process_overrides={
            "layer_height": "0.16",
            "wall_loops": "5",
            "wall_generator": "arachne",
            "sparse_infill_density": "20%",
            "sparse_infill_pattern": "gyroid",
            "outer_wall_line_width": "0.40",
            "inner_wall_line_width": "0.42",
            "outer_wall_speed": "40",
            "inner_wall_speed": "80",
            "small_perimeter_speed": "30",
            "brim_type": "outer_only",
            "brim_width": "8",
            "brim_object_gap": "0",
            "initial_layer_speed": "25",
            "initial_layer_infill_speed": "30",
            "print_sequence": "by object",
        },
    )


def build_lower_panel_adhesion_project(
    coupon_dir: Path,
    output_path: Path,
) -> Path:
    """Package a panel-only reprint with maximum first-layer adhesion."""
    return build_coupon_3mf(
        output_path=Path(output_path),
        plate_title="Lower rail panel high-adhesion reprint",
        objects=[
            (
                "Matte lower rail panel - 8 mm attached brim",
                Path(coupon_dir) / "lower_panel_matte_rails.stl",
                1,
            ),
        ],
        positions=[(128.0, 128.0, 0.0)],
        enable_support=True,
        filament_profile="Bambu PLA Matte @BBL P2S",
        filament_id="GFA01",
        filament_colour="#FFFFFF",
        process_overrides={
            "layer_height": "0.16",
            "wall_loops": "5",
            "wall_generator": "arachne",
            "sparse_infill_density": "20%",
            "sparse_infill_pattern": "gyroid",
            "outer_wall_line_width": "0.40",
            "inner_wall_line_width": "0.42",
            "outer_wall_speed": "40",
            "inner_wall_speed": "80",
            "small_perimeter_speed": "30",
            "brim_type": "outer_only",
            "brim_width": "8",
            "brim_object_gap": "0",
            "initial_layer_speed": "25",
            "initial_layer_infill_speed": "30",
        },
    )


def build_coupon_projects(coupon_dir: Path, output_dir: Path) -> list[Path]:
    """Write the printable P2S Matte PLA coupon projects."""
    coupon_dir = Path(coupon_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    projects = [
        (
            "Squspi_R188_Fit_Coupon_P2S.3mf",
            "R188 fit matrix — print first",
            [
                (
                    "R188 housing and shaft fit matrix",
                    coupon_dir / "r188_fit_matrix.stl",
                    1,
                )
            ],
            [(128.0, 128.0, 0.0)],
        ),
        (
            "Squspi_Running_Clearance_Coupons_P2S.3mf",
            "Running clearance gauges",
            [
                (
                    "Running clearance 0.40 female",
                    coupon_dir / "running_clearance_0_40_female.stl",
                    1,
                ),
                (
                    "Running clearance 0.40 male",
                    coupon_dir / "running_clearance_0_40_male.stl",
                    1,
                ),
                (
                    "Running clearance 0.50 female",
                    coupon_dir / "running_clearance_0_50_female.stl",
                    1,
                ),
                (
                    "Running clearance 0.50 male",
                    coupon_dir / "running_clearance_0_50_male.stl",
                    1,
                ),
                (
                    "Running clearance 0.60 female",
                    coupon_dir / "running_clearance_0_60_female.stl",
                    1,
                ),
                (
                    "Running clearance 0.60 male",
                    coupon_dir / "running_clearance_0_60_male.stl",
                    1,
                ),
            ],
            [
                (90.0, 150.0, 0.0),
                (160.0, 150.0, 0.0),
                (90.0, 120.0, 0.0),
                (160.0, 120.0, 0.0),
                (90.0, 90.0, 0.0),
                (160.0, 90.0, 0.0),
            ],
        ),
        (
            "Squspi_Link_Root_Coupon_P2S.3mf",
            "Link neck and root coupon",
            [
                (
                    "Link neck and root radius matrix",
                    coupon_dir / "link_root_matrix.stl",
                    1,
                )
            ],
            [(128.0, 128.0, 0.0)],
        ),
        (
            "Squspi_R188_Assembled_Stack_Coupon_P2S.3mf",
            "R188 assembled stack - 0.10, 0.20, 0.30 mm",
            [
                (
                    "R188 stack 0.10 base — one dot",
                    coupon_dir / "r188_stack_0_10_base.stl",
                    1,
                ),
                (
                    "R188 stack 0.10 cap — one dot — flip after print",
                    coupon_dir / "r188_stack_0_10_cap.stl",
                    1,
                ),
                (
                    "R188 stack 0.20 base — two dots",
                    coupon_dir / "r188_stack_0_20_base.stl",
                    1,
                ),
                (
                    "R188 stack 0.20 cap — two dots — flip after print",
                    coupon_dir / "r188_stack_0_20_cap.stl",
                    1,
                ),
                (
                    "R188 stack 0.30 base — three dots",
                    coupon_dir / "r188_stack_0_30_base.stl",
                    1,
                ),
                (
                    "R188 stack 0.30 cap — three dots — flip after print",
                    coupon_dir / "r188_stack_0_30_cap.stl",
                    1,
                ),
            ],
            [
                (80.0, 150.0, 0.0),
                (80.0, 100.0, 0.0),
                (128.0, 150.0, 0.0),
                (128.0, 100.0, 0.0),
                (176.0, 150.0, 0.0),
                (176.0, 100.0, 0.0),
            ],
        ),
        (
            "Squspi_Pin_Socket_Fit_Matrix_P2S.3mf",
            "Source-like snap pin and panel socket matrix",
            [
                (
                    "Snap pin head 2.35 mm — one dot",
                    coupon_dir / "snap_pin_head_2_35.stl",
                    1,
                ),
                (
                    "Snap pin head 2.45 mm — two dots",
                    coupon_dir / "snap_pin_head_2_45.stl",
                    1,
                ),
                (
                    "Snap pin head 2.55 mm — three dots",
                    coupon_dir / "snap_pin_head_2_55.stl",
                    1,
                ),
                (
                    "Panel socket 2.20 mm paired with 2.35 head — one dot",
                    coupon_dir / "panel_socket_2_20_pair_1.stl",
                    1,
                ),
                (
                    "Panel socket 2.20 mm paired with 2.45 head — two dots",
                    coupon_dir / "panel_socket_2_20_pair_2.stl",
                    1,
                ),
                (
                    "Panel socket 2.20 mm paired with 2.55 head — three dots",
                    coupon_dir / "panel_socket_2_20_pair_3.stl",
                    1,
                ),
            ],
            [
                (80.0, 145.0, 0.0),
                (128.0, 145.0, 0.0),
                (176.0, 145.0, 0.0),
                (80.0, 100.0, 0.0),
                (128.0, 100.0, 0.0),
                (176.0, 100.0, 0.0),
            ],
        ),
        (
            "Squspi_Compliant_Socket_Coupon_P2S.3mf",
            "Reinforced pin and compliant socket matrix",
            [
                (
                    "Reinforced pin paired with 0.60 mm socket slit — one dot",
                    coupon_dir / "reinforced_snap_pin_pair_1.stl",
                    1,
                ),
                (
                    "Compliant 2.20 mm socket with 0.60 mm slit — one dot",
                    coupon_dir / "compliant_socket_slot_0_60.stl",
                    1,
                ),
                (
                    "Reinforced pin paired with 0.80 mm socket slit — two dots",
                    coupon_dir / "reinforced_snap_pin_pair_2.stl",
                    1,
                ),
                (
                    "Compliant 2.20 mm socket with 0.80 mm slit — two dots",
                    coupon_dir / "compliant_socket_slot_0_80.stl",
                    1,
                ),
                (
                    "Reinforced pin paired with 1.00 mm socket slit — three dots",
                    coupon_dir / "reinforced_snap_pin_pair_3.stl",
                    1,
                ),
                (
                    "Compliant 2.20 mm socket with 1.00 mm slit — three dots",
                    coupon_dir / "compliant_socket_slot_1_00.stl",
                    1,
                ),
            ],
            [
                (80.0, 145.0, 0.0),
                (80.0, 100.0, 0.0),
                (128.0, 145.0, 0.0),
                (128.0, 100.0, 0.0),
                (176.0, 145.0, 0.0),
                (176.0, 100.0, 0.0),
            ],
        ),
    ]

    written: list[Path] = []
    for filename, title, objects, positions in projects:
        written.append(
            build_coupon_3mf(
                output_path=output_dir / filename,
                plate_title=title,
                objects=objects,
                positions=positions,
            )
        )
    written.append(
        build_coupon_3mf(
            output_path=output_dir / "Squspi_Source_Joint_Control_P2S.3mf",
            plate_title="Source blind-pocket joint control",
            objects=[
                (
                    "Cleaned source link control",
                    coupon_dir / "source_control_link.stl",
                    1,
                ),
                (
                    "Cleaned source panel control A",
                    coupon_dir / "source_control_panel.stl",
                    1,
                ),
                (
                    "Cleaned source panel control B",
                    coupon_dir / "source_control_panel.stl",
                    1,
                ),
            ],
            positions=[
                (128.0, 105.0, 0.0),
                (100.0, 145.0, 0.0),
                (156.0, 145.0, 0.0),
            ],
            enable_support=True,
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=(
                output_dir / "Squspi_Hybrid_Reconstructed_Panel_Sector_P2S.3mf"
            ),
            plate_title="Hybrid sector - source link and reconstructed panels",
            objects=[
                (
                    "Source link control",
                    coupon_dir / "hybrid_source_link.stl",
                    1,
                ),
                (
                    "Source-envelope reconstructed panel A",
                    coupon_dir / "hybrid_reconstructed_panel.stl",
                    1,
                ),
                (
                    "Source-envelope reconstructed panel B",
                    coupon_dir / "hybrid_reconstructed_panel.stl",
                    1,
                ),
            ],
            positions=[
                (128.0, 105.0, 0.0),
                (100.0, 145.0, 0.0),
                (156.0, 145.0, 0.0),
            ],
            enable_support=True,
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=(
                output_dir / "Squspi_Hybrid_Reconstructed_Link_Sector_P2S.3mf"
            ),
            plate_title="Hybrid sector - reconstructed link and source panels",
            objects=[
                (
                    "Source-core parametric-pin reconstructed link",
                    coupon_dir / "hybrid_reconstructed_link.stl",
                    1,
                ),
                (
                    "Source panel control A",
                    coupon_dir / "hybrid_source_panel.stl",
                    1,
                ),
                (
                    "Source panel control B",
                    coupon_dir / "hybrid_source_panel.stl",
                    1,
                ),
            ],
            positions=[
                (128.0, 105.0, 0.0),
                (100.0, 145.0, 0.0),
                (156.0, 145.0, 0.0),
            ],
            enable_support=True,
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=output_dir / "Squspi_Actual_Base_Button_Stack_P2S.3mf",
            plate_title="Actual source-shaped base and button stack",
            objects=[
                (
                    "Source-arm base with selected 12.75 mm R188 pocket",
                    coupon_dir / "actual_stack_selected_base.stl",
                    1,
                ),
                (
                    "Exact-profile button with selected 6.40 mm shaft",
                    coupon_dir / "actual_stack_exact_button.stl",
                    1,
                ),
            ],
            positions=[
                (105.0, 128.0, 0.0),
                (155.0, 128.0, 0.0),
            ],
            enable_support=True,
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=output_dir / "Squspi_Validated_Vertical_Chain_P2S.3mf",
            plate_title="Validated upper-to-lower vertical chain",
            objects=[
                (
                    "Upper source-arm base with selected R188 pocket",
                    coupon_dir / "actual_stack_selected_base.stl",
                    1,
                ),
                (
                    "Upper exact-profile button",
                    coupon_dir / "actual_stack_exact_button.stl",
                    1,
                ),
                (
                    "Upper unchanged source panel",
                    coupon_dir / "hybrid_source_panel.stl",
                    1,
                ),
                (
                    "Measured-pin reconstructed link",
                    coupon_dir / "hybrid_reconstructed_link.stl",
                    1,
                ),
                (
                    "Lower unchanged source panel",
                    coupon_dir / "hybrid_source_panel.stl",
                    1,
                ),
                (
                    "Lower source-arm base with selected R188 pocket",
                    coupon_dir / "actual_stack_selected_base.stl",
                    1,
                ),
                (
                    "Lower exact-profile button",
                    coupon_dir / "actual_stack_exact_button.stl",
                    1,
                ),
            ],
            positions=[
                (65.0, 165.0, 0.0),
                (65.0, 105.0, 0.0),
                (108.0, 155.0, 0.0),
                (128.0, 95.0, 0.0),
                (148.0, 155.0, 0.0),
                (191.0, 165.0, 0.0),
                (191.0, 105.0, 0.0),
            ],
            enable_support=True,
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=output_dir / "Squspi_ToughPlus_Source_Panel_Control_P2S.3mf",
            plate_title="Unchanged source panel - PLA Tough+ control",
            objects=[
                (
                    "Unchanged source panel in PLA Tough+",
                    coupon_dir / "hybrid_source_panel.stl",
                    1,
                ),
            ],
            positions=[
                (128.0, 128.0, 0.0),
            ],
            enable_support=True,
            filament_profile="Bambu PLA Tough+ @BBL P2S",
            filament_id="GFA10",
            filament_colour="#FFFFFF",
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=output_dir / "Squspi_Base_Arm_Retention_Matrix_P2S.3mf",
            plate_title="Base arm retention matrix for Tough+ panel",
            objects=[
                (
                    "Base pegs 2.25 mm — one dot",
                    coupon_dir / "base_arm_retention_2_25.stl",
                    1,
                ),
                (
                    "Base pegs 2.30 mm — two dots",
                    coupon_dir / "base_arm_retention_2_30.stl",
                    1,
                ),
                (
                    "Base pegs 2.35 mm — three dots",
                    coupon_dir / "base_arm_retention_2_35.stl",
                    1,
                ),
            ],
            positions=[
                (65.0, 128.0, 0.0),
                (128.0, 128.0, 0.0),
                (191.0, 128.0, 0.0),
            ],
            enable_support=True,
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=output_dir / "Squspi_Base_Peg_Process_Gauge_P2S.3mf",
            plate_title="Base peg process gauge - 0.12 mm Arachne",
            objects=[
                (
                    "Source peg 2.20 mm — one dot",
                    coupon_dir / "base_peg_process_2_20.stl",
                    1,
                ),
                (
                    "Peg 2.30 mm — two dots",
                    coupon_dir / "base_peg_process_2_30.stl",
                    1,
                ),
                (
                    "Peg 2.40 mm — three dots",
                    coupon_dir / "base_peg_process_2_40.stl",
                    1,
                ),
                (
                    "Peg 2.50 mm — four dots",
                    coupon_dir / "base_peg_process_2_50.stl",
                    1,
                ),
            ],
            positions=[
                (60.0, 128.0, 0.0),
                (105.0, 128.0, 0.0),
                (150.0, 128.0, 0.0),
                (195.0, 128.0, 0.0),
            ],
            enable_support=True,
            process_overrides={
                "layer_height": "0.12",
                "wall_generator": "arachne",
                "outer_wall_line_width": "0.36",
                "inner_wall_line_width": "0.40",
                "outer_wall_speed": "35",
                "inner_wall_speed": "70",
                "small_perimeter_speed": "35",
            },
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=(
                output_dir / "Squspi_Keyed_ToughPlus_Connector_Coupon_P2S.3mf"
            ),
            plate_title="Keyed Tough+ clevis and captive filament pin",
            objects=[
                (
                    "Matte keyed panel receiver",
                    coupon_dir / "keyed_panel_receiver.stl",
                    1,
                ),
                (
                    "Tough+ keyed clevis insert",
                    coupon_dir / "keyed_tough_clevis.stl",
                    2,
                ),
                (
                    "Matte base-arm pivot surrogate",
                    coupon_dir / "keyed_base_tongue.stl",
                    1,
                ),
            ],
            positions=[
                (90.0, 128.0, 0.0),
                (128.0, 128.0, 0.0),
                (166.0, 128.0, 0.0),
            ],
            enable_support=True,
            filament_profiles=(
                "Bambu PLA Matte @BBL P2S",
                "Bambu PLA Tough+ @BBL P2S",
            ),
            filament_ids=("GFA01", "GFA10"),
            filament_colours=("#FFFFFF", "#F97316"),
            process_overrides={
                "layer_height": "0.16",
                "wall_generator": "arachne",
                "outer_wall_line_width": "0.40",
                "inner_wall_line_width": "0.42",
                "outer_wall_speed": "50",
                "inner_wall_speed": "100",
                "small_perimeter_speed": "50",
            },
        )
    )
    written.append(
        build_coupon_3mf(
            output_path=output_dir / "Squspi_Fixed_Pin_Clevis_Matrix_P2S.3mf",
            plate_title="Tough+ fixed filament pin clevis matrix",
            objects=[
                (
                    "Fixed ear 1.80 mm - one dot - test first",
                    coupon_dir / "fixed_pin_clevis_1_80.stl",
                    1,
                ),
                (
                    "Fixed ear 1.75 mm - two dots",
                    coupon_dir / "fixed_pin_clevis_1_75.stl",
                    1,
                ),
                (
                    "Fixed ear 1.70 mm - three dots",
                    coupon_dir / "fixed_pin_clevis_1_70.stl",
                    1,
                ),
            ],
            positions=[
                (70.0, 128.0, 0.0),
                (128.0, 128.0, 0.0),
                (186.0, 128.0, 0.0),
            ],
            enable_support=True,
            filament_profile="Bambu PLA Tough+ @BBL P2S",
            filament_id="GFA10",
            filament_colour="#FFFFFF",
            process_overrides={
                "layer_height": "0.16",
                "wall_generator": "arachne",
                "outer_wall_line_width": "0.40",
                "inner_wall_line_width": "0.42",
                "outer_wall_speed": "50",
                "inner_wall_speed": "100",
                "small_perimeter_speed": "50",
            },
        )
    )
    written.append(
        build_twin_rail_curvature_project(
            coupon_dir,
            output_dir / "Squspi_Twin_Rail_Curvature_Coupon_P2S.3mf",
        )
    )
    written.append(
        build_twin_rail_latch_matrix_project(
            coupon_dir,
            output_dir / "Squspi_Twin_Rail_Latch_Matrix_v4_P2S.3mf",
        )
    )
    written.append(
        build_monolithic_receiver_material_project(
            coupon_dir,
            output_dir / "Squspi_Monolithic_Receiver_Material_AB_P2S.3mf",
        )
    )
    written.append(
        build_hook_rail_material_project(
            coupon_dir,
            output_dir
            / "Squspi_Original_Pin_Axis_Hook_Rail_AB_v2_P2S.3mf",
        )
    )
    written.append(
        build_full_base_hook_test_project(
            coupon_dir,
            output_dir
            / "Squspi_Full_Base_Lower_Hooks_Panel_Rails_P2S.3mf",
        )
    )
    written.append(
        build_lower_panel_adhesion_project(
            coupon_dir,
            output_dir
            / "Squspi_Lower_Rail_Panel_High_Adhesion_P2S.3mf",
        )
    )
    return written


def generate(source_dir: Path, output_dir: Path) -> Path:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    reference_dir = output_dir / "reference_masters"
    candidate_dir = output_dir / "parametric_candidates"
    coupon_dir = output_dir / "coupons"
    reference_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    coupon_dir.mkdir(parents=True, exist_ok=True)

    source_paths = _locate_masters(source_dir)
    references: dict[str, trimesh.Trimesh] = {}
    validation = []
    for name, path in source_paths.items():
        mesh = load_reference(path)
        references[name] = mesh
        validation.append(validate_mesh(f"reference_{name}", mesh))
        mesh.export(reference_dir / f"{name}_reference.stl")

    source_sector_validation = validate_source_sector_assembly(
        references["link"],
        references["panel"],
    )
    references["link"].export(coupon_dir / "source_control_link.stl")
    references["panel"].export(coupon_dir / "source_control_panel.stl")

    parametric_button = build_parametric_button_baseline()
    parametric_base = build_parametric_base_baseline()
    selected_source_base = build_selected_source_base(references["base"])
    parametric_link = build_parametric_link_baseline()
    parametric_panel_shell = build_parametric_panel_shell()
    parametric_panel = build_parametric_panel_baseline()
    source_envelope_panel = build_source_envelope_panel(references["link"])
    source_core_parametric_pin_link = build_source_core_parametric_pin_link(
        references["link"]
    )
    real_keyed_panel = build_real_keyed_panel_receiver(references["panel"])
    real_keyed_insert = _build_twin_rail_compliant_latch_cartridge(0.36, 2)
    real_keyed_base = build_real_keyed_source_base(selected_source_base)
    real_keyed_validation = validate_real_keyed_joint(
        references["panel"],
        real_keyed_panel,
        real_keyed_insert,
        real_keyed_base,
    )
    monolithic_receiver = build_monolithic_receiver_clevis(
        references["panel"]
    )
    monolithic_validation = validate_monolithic_receiver_clevis(
        references["panel"],
        monolithic_receiver,
        real_keyed_base,
    )
    hook_rail_panel = build_hook_rail_panel(references["panel"])
    hook_rail_base = build_hook_rail_base_coupon()
    hook_rail_validation = validate_hook_rail_architecture(
        references["panel"],
        hook_rail_panel,
        hook_rail_base,
    )
    full_base_hooks = build_full_base_with_hooks(selected_source_base)
    lower_panel_rails = build_lower_panel_with_rails(
        references["panel"]
    )
    full_base_hook_validation = validate_full_base_hook_architecture(
        references["panel"],
        selected_source_base,
        lower_panel_rails,
        full_base_hooks,
    )
    hybrid_panel_sector_validation = validate_source_sector_assembly(
        references["link"],
        source_envelope_panel,
    )
    hybrid_link_sector_validation = validate_source_sector_assembly(
        source_core_parametric_pin_link,
        references["panel"],
    )
    parametric_validation = [
        validate_mesh("parametric_button_baseline", parametric_button),
        validate_mesh("parametric_base_baseline", parametric_base),
        validate_mesh("selected_source_base", selected_source_base),
        validate_mesh("parametric_link_baseline", parametric_link),
        validate_mesh("parametric_panel_shell", parametric_panel_shell),
        validate_mesh("parametric_panel_baseline", parametric_panel),
        validate_mesh("source_envelope_panel", source_envelope_panel),
        validate_mesh(
            "source_core_parametric_pin_link",
            source_core_parametric_pin_link,
        ),
        validate_mesh("twin_rail_review_panel", real_keyed_panel),
        validate_mesh("twin_rail_review_cartridge", real_keyed_insert),
        validate_mesh("twin_rail_review_base", real_keyed_base),
        validate_mesh("monolithic_receiver_clevis", monolithic_receiver),
        validate_mesh("hook_rail_panel", hook_rail_panel),
        validate_mesh("hook_rail_base", hook_rail_base),
        validate_mesh(
            "full_base_tough_hooks",
            full_base_hooks,
        ),
        validate_mesh(
            "lower_panel_matte_rails",
            lower_panel_rails,
        ),
    ]
    parametric_button.export(candidate_dir / "button_baseline.stl")
    parametric_base.export(candidate_dir / "base_baseline.stl")
    selected_source_base.export(candidate_dir / "base_selected_r188_source_arms.stl")
    parametric_link.export(candidate_dir / "link_baseline.stl")
    parametric_panel_shell.export(candidate_dir / "panel_shell_core.stl")
    parametric_panel.export(candidate_dir / "panel_baseline.stl")
    source_envelope_panel.export(candidate_dir / "panel_source_envelope.stl")
    source_core_parametric_pin_link.export(
        candidate_dir / "link_source_core_parametric_pins.stl"
    )
    real_keyed_panel.export(candidate_dir / "twin_rail_review_panel.stl")
    real_keyed_insert.export(
        candidate_dir / "twin_rail_review_cartridge.stl"
    )
    real_keyed_base.export(candidate_dir / "twin_rail_review_base.stl")
    monolithic_receiver.export(
        candidate_dir / "monolithic_receiver_clevis.stl"
    )
    hook_rail_panel.export(candidate_dir / "hook_rail_panel.stl")
    hook_rail_base.export(candidate_dir / "hook_rail_base.stl")
    full_base_hooks.export(
        candidate_dir / "full_base_tough_hooks.stl"
    )
    lower_panel_rails.export(
        candidate_dir / "lower_panel_matte_rails.stl"
    )
    references["link"].export(coupon_dir / "hybrid_source_link.stl")
    source_envelope_panel.export(coupon_dir / "hybrid_reconstructed_panel.stl")
    source_core_parametric_pin_link.export(
        coupon_dir / "hybrid_reconstructed_link.stl"
    )
    references["panel"].export(coupon_dir / "hybrid_source_panel.stl")
    selected_source_base.export(coupon_dir / "actual_stack_selected_base.stl")
    parametric_button.export(coupon_dir / "actual_stack_exact_button.stl")

    coupon_meshes = [
        ("r188_fit_matrix", build_bearing_fit_coupon()),
        ("link_root_matrix", build_link_root_coupon()),
        *build_running_clearance_coupons(),
        *build_r188_stack_coupons(),
        *build_pin_socket_coupons(),
        *build_nominal_socket_pair_coupons(),
        *build_compliant_socket_coupons(),
        *build_base_retention_variants(selected_source_base),
        *build_base_peg_process_gauge(selected_source_base),
        *build_keyed_connector_architecture_coupon(),
        *build_fixed_pin_clevis_variants(),
        *build_twin_rail_curvature_coupon(references["panel"]),
        *build_twin_rail_latch_matrix(references["panel"]),
        *build_monolithic_receiver_material_coupon(references["panel"]),
        *build_hook_rail_material_coupons(references["panel"]),
        *build_full_base_hook_test_parts(
            references["panel"],
            selected_source_base,
        ),
    ]
    coupon_validation = []
    for filename, mesh in coupon_meshes:
        coupon_validation.append(validate_mesh(filename, mesh))
        mesh.export(coupon_dir / f"{filename}.stl")

    project_dir = output_dir / "p2s_projects"
    coupon_projects = [
        str(path.name) for path in build_coupon_projects(coupon_dir, project_dir)
    ]

    report = {
        "project": "Squspi ball reconstruction",
        "stage": "full Tough+ base hooks and lower Matte panel rails",
        "units": "mm",
        "source_directory": str(source_dir),
        "source_files": {name: path.name for name, path in source_paths.items()},
        "r188": asdict(R188),
        "coupon_parameters": asdict(COUPONS),
        "joint_dimension_register": {
            "lower_panel_blind_pocket": {
                "axis": "Y",
                "centre_xz": list(PANEL_SOCKET_CENTRES_XZ[0]),
                "measured_diameter": PANEL_LOWER_POCKET_MEASURED_DIAMETER,
                "nominal_diameter": PANEL_SOCKET_DIAMETER,
                "blind_bottom_abs_y": PANEL_LOWER_POCKET_BOTTOM_Y,
                "mouth_abs_y_range": list(PANEL_LOWER_POCKET_MOUTH_Y),
                "minimum_local_wall": PANEL_LOWER_POCKET_MIN_WALL,
            },
            "upper_panel_oblique_pocket": {
                "axis": "approximately Y; shell-trimmed",
                "centre_xz": list(PANEL_SOCKET_CENTRES_XZ[1]),
                "axis_bottom_abs_y": PANEL_UPPER_POCKET_AXIS_BOTTOM_Y,
                "nominal_mouth_abs_y": PANEL_UPPER_POCKET_MOUTH_Y,
                "local_bottom_normal_positive_y": list(
                    PANEL_UPPER_POCKET_LOCAL_NORMAL
                ),
                "construction": "separate oblique shell/rail feature",
            },
            "source_link_pins": {
                "centres_xz": [list(item) for item in SOURCE_LINK_PIN_CENTRES_XZ],
                "full_radius": 1.002,
                "tip_abs_y": 3.75098,
                "radial_clearance_per_side": [0.075, 0.097],
                "axial_clearance_to_lower_pocket_bottom": 0.249,
            },
        },
        "reference_validation": validation,
        "source_sector_control": source_sector_validation,
        "axisymmetric_profiles": {
            "button": radial_profile(references["button"]),
            "base": radial_profile(references["base"]),
        },
        "parametric_candidates": {
            "validation": parametric_validation,
            "known_gaps": [
                "Button is a near-exact revolve of the measured half-section.",
                "Base arm tips are still a simplified loft versus the organic source tips.",
                (
                    "Legacy parametric_link_baseline uses approximate cones; "
                    "source_core_parametric_pin_link replaces them with measured sweeps."
                ),
                "Panel omits the raised outer spherical lip until a manifold shell bake-in exists.",
            ],
            "surface_comparison": {
                "button": compare_surfaces(
                    references["button"],
                    parametric_button,
                ),
                "base": compare_surfaces(
                    references["base"],
                    parametric_base,
                ),
                "selected_source_base": compare_surfaces(
                    references["base"],
                    selected_source_base,
                ),
                "link": compare_surfaces(
                    references["link"],
                    parametric_link,
                ),
                "panel_shell_core": compare_surfaces(
                    references["panel"],
                    parametric_panel_shell,
                ),
                "panel": compare_surfaces(
                    references["panel"],
                    parametric_panel,
                ),
                "source_envelope_panel": compare_surfaces(
                    references["panel"],
                    source_envelope_panel,
                ),
                "source_core_parametric_pin_link": compare_surfaces(
                    references["link"],
                    source_core_parametric_pin_link,
                ),
            },
        },
        "hybrid_panel_sector": hybrid_panel_sector_validation,
        "hybrid_link_sector": hybrid_link_sector_validation,
        "real_keyed_joint": real_keyed_validation,
        "monolithic_receiver_clevis": monolithic_validation,
        "hook_rail_architecture": hook_rail_validation,
        "full_base_hook_architecture": full_base_hook_validation,
        "coupon_validation": coupon_validation,
        "p2s_projects": {
            "printer_profile": "Bambu Lab P2S 0.4 nozzle",
            "filament_profile": "Bambu PLA Matte @BBL P2S",
            "files": coupon_projects,
            "directory": str(project_dir),
        },
        "next_gate": (
            "Print the complete Tough+ base and one Matte panel with rigid "
            "rails at its true lower connector. Test the same panel on all "
            "six arms, then complete 200 pivot cycles and 20 outward "
            "hand-loads on the weakest arm before releasing a full set."
        ),
    }
    report_path = output_dir / "reconstruction_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare Squspi reference masters and fit coupons"
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(generate(args.source_dir, args.out))
