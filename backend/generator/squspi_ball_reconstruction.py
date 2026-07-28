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
from shapely.geometry import LineString, Point, Polygon, box

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import build_bambu_project as bambu  # noqa: E402


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

    template_path = GENERATOR_DIR / "blank_project.3mf"
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
        "stage": "parametric baseline candidates + fit coupons",
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
        "coupon_validation": coupon_validation,
        "p2s_projects": {
            "printer_profile": "Bambu Lab P2S 0.4 nozzle",
            "filament_profile": "Bambu PLA Matte @BBL P2S",
            "files": coupon_projects,
            "directory": str(project_dir),
        },
        "next_gate": (
            "Print the combined upper-to-lower vertical chain using two selected "
            "source-arm bases, two exact-profile buttons, unchanged source panels, "
            "and the accepted measured-pin link. Verify both hub stacks remain free "
            "while the chain completes its full fold without binding or damage."
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
