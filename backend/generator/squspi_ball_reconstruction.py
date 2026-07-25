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
PANEL_SOCKET_CENTRES_XZ = ((-4.755, 2.150), (3.920, 17.250))
PANEL_SOCKET_DIAMETER = 2.20

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
) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    overrides = {
        "layer_height": "0.20",
        "wall_loops": "4",
        "sparse_infill_density": "15%",
        "sparse_infill_pattern": "gyroid",
        "enable_support": "0",
        "outer_wall_speed": "80",
        "inner_wall_speed": "140",
        "top_shell_layers": "5",
        "bottom_shell_layers": "4",
        "seam_position": "back",
        "fuzzy_skin": "none",
    }
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
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        settings["filament_type"] = ["PLA", "PLA"]
        settings["filament_vendor"] = ["Bambu Lab", "Bambu Lab"]
        settings["filament_settings_id"] = [
            "Bambu PLA Matte @BBL P2S",
            "Bambu PLA Matte @BBL P2S",
        ]
        settings["filament_ids"] = ["GFA01", "GFA01"]
        settings["filament_colour"] = ["#FFFFFF", "#FFFFFF"]
        settings["default_filament_colour"] = ["", ""]
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
    """Write the three printable P2S Matte PLA coupon projects."""
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

    parametric_button = build_parametric_button_baseline()
    parametric_base = build_parametric_base_baseline()
    parametric_link = build_parametric_link_baseline()
    parametric_panel_shell = build_parametric_panel_shell()
    parametric_panel = build_parametric_panel_baseline()
    parametric_validation = [
        validate_mesh("parametric_button_baseline", parametric_button),
        validate_mesh("parametric_base_baseline", parametric_base),
        validate_mesh("parametric_link_baseline", parametric_link),
        validate_mesh("parametric_panel_shell", parametric_panel_shell),
        validate_mesh("parametric_panel_baseline", parametric_panel),
    ]
    parametric_button.export(candidate_dir / "button_baseline.stl")
    parametric_base.export(candidate_dir / "base_baseline.stl")
    parametric_link.export(candidate_dir / "link_baseline.stl")
    parametric_panel_shell.export(candidate_dir / "panel_shell_core.stl")
    parametric_panel.export(candidate_dir / "panel_baseline.stl")

    coupon_meshes = [
        ("r188_fit_matrix", build_bearing_fit_coupon()),
        ("link_root_matrix", build_link_root_coupon()),
        *build_running_clearance_coupons(),
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
        "reference_validation": validation,
        "axisymmetric_profiles": {
            "button": radial_profile(references["button"]),
            "base": radial_profile(references["base"]),
        },
        "parametric_candidates": {
            "validation": parametric_validation,
            "known_gaps": [
                "Button is a near-exact revolve of the measured half-section.",
                "Base arm tips are still a simplified loft versus the organic source tips.",
                "Link pins are tapered cones approximating blended STL snap geometry.",
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
            },
        },
        "coupon_validation": coupon_validation,
        "p2s_projects": {
            "printer_profile": "Bambu Lab P2S 0.4 nozzle",
            "filament_profile": "Bambu PLA Matte @BBL P2S",
            "files": coupon_projects,
            "directory": str(project_dir),
        },
        "next_gate": (
            "Print the R188, running-clearance, and link-root coupons; freeze selected "
            "fits; then refine base arm tips and bake the panel edge lip into the shell."
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
