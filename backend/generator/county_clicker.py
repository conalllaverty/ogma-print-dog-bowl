#!/usr/bin/env python3
"""Generate standalone MX-switch clickers for all 32 counties of Ireland.

County outlines retain their relative geographic scale, with narrow counties
enlarged independently so the MX mechanism has enough material around it. The
finished pieces are standalone handheld clickers, not tessellating map tiles.
Each county reuses the Tyrone mechanism: fixed GAA-coloured shell, contrasting
moving top, and an Outemu/MX fit.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from shapely.affinity import translate as translate_geometry
from shapely.geometry import Point, Polygon, mapping, shape
from shapely.ops import polylabel, transform, unary_union

GENERATOR_DIR = Path(__file__).resolve().parent
BOUNDARIES_DIR = GENERATOR_DIR / "county_boundaries"
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import build_bambu_project as bambu  # noqa: E402
import sushi_clicker as sushi  # noqa: E402
from county_gaa_colours import COUNTIES, COUNTY_COLOURS  # noqa: E402

# Handheld map scale: Tyrone is the width anchor. Tiny counties are boosted just
# enough for the MX switch; that slightly softens perfect geographic fit.
REFERENCE_COUNTY = "Tyrone"
REFERENCE_WIDTH_MM = 62.0
MIN_INSCRIBED_RADIUS_MM = 11.5
SWITCH_SHOULDER_SIZE_MM = 16.4
MIN_SWITCH_SHOULDER_WALL_MM = 1.50
MAX_SWITCH_CENTER_SHIFT_MM = 3.0
MIN_CAP_AREA_RETENTION = 0.45
MIN_CAP_NECK_MM = 1.20
# Keep characteristic jogs (e.g. Tyrone/Strabane) at handheld scale.
SIMPLIFY_MM = 0.08
MIN_BOUNDARY_IOU = 0.99
MAX_BOUNDARY_HAUSDORFF_MM = 0.10

BODY_HEIGHT = 23.5
# Derive the cap from the finished pocket, rather than offsetting the outer
# outline independently. A 1.25 mm CAD offset keeps the exact polygon-to-polygon
# minimum at or above the requested loose 1.20 mm fit after buffer tessellation.
POCKET_INSET = 1.4
CAP_SIDE_CLEARANCE = 1.25
MIN_SIDE_CLEARANCE_MM = 1.20
# Wicklow's southwest pocket lobe only stays on a single connected top when the
# moving-top clearance is tightened. Do not enlarge the shell for this — only
# the yellow top grows into that lobe (≈0.75 mm side gap, ≥0.80 mm neck).
COUNTY_CAP_SIDE_CLEARANCE_MM = {"Wicklow": 0.75}
COUNTY_MIN_SIDE_CLEARANCE_MM = {"Wicklow": 0.70}
COUNTY_MIN_CAP_NECK_MM = {"Wicklow": 0.80}
CAP_INSET = POCKET_INSET + CAP_SIDE_CLEARANCE
POCKET_FLOOR_Z = 13.2
CAP_SLAB_Z0 = 3.0
CAP_SLAB_THICKNESS = 4.0
CAP_ASSEMBLED_Z = 19.0
CAP_PROUD = CAP_ASSEMBLED_Z + CAP_SLAB_Z0 + CAP_SLAB_THICKNESS - BODY_HEIGHT
FULL_TRAVEL = 4.0

SWITCH_OPENING = sushi.SWITCH_OPENING
SWITCH_PIN_CLEARANCE_FLOOR = sushi.SWITCH_PIN_CLEARANCE_FLOOR
MX_CROSS_MAJOR = sushi.MX_CROSS_MAJOR
MX_CROSS_MINOR = sushi.MX_CROSS_MINOR
MX_SOCKET_DEPTH = sushi.MX_SOCKET_DEPTH
MX_SOCKET_BOSS_D = sushi.MX_SOCKET_BOSS_D
MAX_TRAVEL_OVERLAP_MM3 = 0.01

NI_COUNTIES = {
    "Antrim",
    "Armagh",
    "Derry",
    "Down",
    "Fermanagh",
    "Tyrone",
}


@dataclass(frozen=True)
class CountyGeometry:
    name: str
    outer: Polygon
    map_polygon: Polygon  # absolute Ireland-map coordinates (mm)
    source_polygon: Polygon  # projected official boundary before print simplification
    centre_local: tuple[float, float]
    inscribed_radius: float
    shell_colour: tuple[str, str]
    top_colour: tuple[str, str]
    size_boosted: bool = False
    size_scale_factor: float = 1.0
    switch_shoulder_wall_mm: float = 0.0
    switch_lower_wall_mm: float = 0.0
    switch_center_shift_mm: float = 0.0
    cap_area_retention: float = 0.0
    scale_reasons: tuple[str, ...] = ()


def _largest_polygon(geom) -> Polygon:
    if isinstance(geom, Polygon):
        return geom
    polygons = [part for part in geom.geoms if isinstance(part, Polygon)]
    if not polygons:
        raise ValueError("Expected a polygon")
    return max(polygons, key=lambda item: item.area)


def _cap_side_clearance(county_name: str | None = None) -> float:
    if county_name and county_name in COUNTY_CAP_SIDE_CLEARANCE_MM:
        return COUNTY_CAP_SIDE_CLEARANCE_MM[county_name]
    return CAP_SIDE_CLEARANCE


def _min_side_clearance(county_name: str | None = None) -> float:
    if county_name and county_name in COUNTY_MIN_SIDE_CLEARANCE_MM:
        return COUNTY_MIN_SIDE_CLEARANCE_MM[county_name]
    return MIN_SIDE_CLEARANCE_MM


def _min_cap_neck(county_name: str | None = None) -> float:
    if county_name and county_name in COUNTY_MIN_CAP_NECK_MM:
        return COUNTY_MIN_CAP_NECK_MM[county_name]
    return MIN_CAP_NECK_MM


def _cap_inset(county_name: str | None = None) -> float:
    return POCKET_INSET + _cap_side_clearance(county_name)


def _load_raw_polygon(path: Path) -> Polygon:
    text = path.read_text()
    text = re.sub(r",\s*([}\]])", r"\1", text)
    data = json.loads(text)
    features = data["features"] if "features" in data else [data]
    geom = unary_union([shape(feature["geometry"]) for feature in features])
    return _largest_polygon(geom)


def _hex_luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _map_swatch(shell_hex: str, top_hex: str) -> tuple[str, str]:
    """Choose visible SVG fill/stroke. Near-white shells use the top colour."""
    if _hex_luminance(shell_hex) >= 0.85:
        return top_hex, "#252C29"
    return shell_hex, top_hex


def _project_to_metres(polygons: dict[str, Polygon]) -> dict[str, Polygon]:
    lon0 = sum(poly.centroid.x for poly in polygons.values()) / len(polygons)
    lat0 = sum(poly.centroid.y for poly in polygons.values()) / len(polygons)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))

    def _to_m(x, y, z=None):
        return ((x - lon0) * m_per_deg_lon, (y - lat0) * m_per_deg_lat)

    return {name: transform(_to_m, poly) for name, poly in polygons.items()}


_SWITCH_SHOULDER_PROFILE = Polygon(
    sushi._superellipse_ring(
        SWITCH_SHOULDER_SIZE_MM,
        SWITCH_SHOULDER_SIZE_MM,
        30.0,
        128,
    )
)
_SWITCH_LOWER_PROFILE = Polygon(
    sushi._superellipse_ring(
        SWITCH_OPENING,
        SWITCH_OPENING,
        30.0,
        128,
    )
)


def _switch_wall_mm(
    outer: Polygon,
    centre: tuple[float, float],
    profile: Polygon = _SWITCH_SHOULDER_PROFILE,
) -> float:
    """Minimum material around a translated switch-cavity cross-section."""
    cavity = translate_geometry(profile, xoff=centre[0], yoff=centre[1])
    if not outer.contains(cavity):
        return -float(cavity.difference(outer).area)
    return float(cavity.boundary.distance(outer.boundary))


def _best_switch_centre(
    outer: Polygon,
    seed: tuple[float, float],
) -> tuple[tuple[float, float], float]:
    """Maximise wall around the square shoulder with deterministic grid refinement."""
    best_centre = seed
    best_wall = _switch_wall_mm(outer, seed)
    for radius, step in ((6.0, 1.0), (1.5, 0.25), (0.35, 0.05)):
        origin = best_centre
        count = int(round((radius * 2) / step))
        for ix in range(count + 1):
            x = origin[0] - radius + ix * step
            for iy in range(count + 1):
                y = origin[1] - radius + iy * step
                candidate = (x, y)
                if math.dist(candidate, seed) > MAX_SWITCH_CENTER_SHIFT_MM:
                    continue
                wall = _switch_wall_mm(outer, candidate)
                if wall > best_wall:
                    best_centre = candidate
                    best_wall = wall
    return best_centre, best_wall


def _scale_polygon(poly: Polygon, factor: float) -> Polygon:
    return _largest_polygon(
        transform(lambda x, y, z=None: (x * factor, y * factor), poly)
    )


def _cap_area_retention(outer: Polygon, county_name: str | None = None) -> float:
    return float(_cap_polygon(outer, county_name).area / outer.area)


def _fit_switch_and_top(
    local: Polygon,
    seed: tuple[float, float],
    county_name: str | None = None,
) -> tuple[Polygon, tuple[float, float], float, float, float, tuple[str, ...]]:
    """Scale only as needed for shoulder wall and recognizable moving-top area."""

    def evaluate(
        factor: float,
    ) -> tuple[Polygon, tuple[float, float], float, float]:
        scaled = _scale_polygon(local, factor)
        scaled_seed = (seed[0] * factor, seed[1] * factor)
        centre, shoulder_wall = _best_switch_centre(scaled, scaled_seed)
        cap_retention = _cap_area_retention(scaled, county_name)
        return scaled, centre, shoulder_wall, cap_retention

    base, centre, shoulder_wall, cap_retention = evaluate(1.0)
    reasons: list[str] = []
    if shoulder_wall < MIN_SWITCH_SHOULDER_WALL_MM:
        reasons.append("switch_shoulder_wall")
    if cap_retention < MIN_CAP_AREA_RETENTION:
        reasons.append("moving_top_area")
    if not reasons:
        return base, centre, shoulder_wall, cap_retention, 1.0, ()

    low = 1.0
    high = 1.05
    while True:
        candidate = evaluate(high)
        if (
            candidate[2] >= MIN_SWITCH_SHOULDER_WALL_MM
            and candidate[3] >= MIN_CAP_AREA_RETENTION
        ):
            break
        low = high
        high *= 1.05
        if high > 2.5:
            raise ValueError("Could not scale county to satisfy physical fit gates")

    for _ in range(14):
        mid = (low + high) / 2
        candidate = evaluate(mid)
        if (
            candidate[2] >= MIN_SWITCH_SHOULDER_WALL_MM
            and candidate[3] >= MIN_CAP_AREA_RETENTION
        ):
            high = mid
        else:
            low = mid

    fitted, centre, shoulder_wall, cap_retention = evaluate(high)
    return (
        fitted,
        centre,
        shoulder_wall,
        cap_retention,
        high,
        tuple(reasons),
    )


def load_county_map() -> dict[str, CountyGeometry]:
    raw = {
        path.stem: _load_raw_polygon(path)
        for path in sorted(BOUNDARIES_DIR.glob("*.geojson"))
    }
    if set(raw) != set(COUNTIES):
        missing = sorted(set(COUNTIES) - set(raw))
        extra = sorted(set(raw) - set(COUNTIES))
        raise ValueError(f"Boundary mismatch missing={missing} extra={extra}")

    metres = _project_to_metres(raw)
    union = unary_union(list(metres.values()))
    min_x, min_y, _, _ = union.bounds
    ref = metres[REFERENCE_COUNTY]
    scale = REFERENCE_WIDTH_MM / (ref.bounds[2] - ref.bounds[0])

    result: dict[str, CountyGeometry] = {}
    for name, poly_m in metres.items():
        source_poly = transform(
            lambda x, y, z=None: ((x - min_x) * scale, (y - min_y) * scale),
            poly_m,
        )
        # Standalone pieces no longer need the old map-assembly seam inset.
        # Simplification is the only shape-changing operation before any
        # uniform size boost needed by the MX mechanism.
        map_poly = source_poly.simplify(SIMPLIFY_MM, preserve_topology=True)
        if not map_poly.is_valid:
            map_poly = _largest_polygon(map_poly.buffer(0))
        cx = (map_poly.bounds[0] + map_poly.bounds[2]) / 2
        cy = (map_poly.bounds[1] + map_poly.bounds[3]) / 2
        local = transform(lambda x, y, z=None: (x - cx, y - cy), map_poly)
        local = _largest_polygon(local)
        centre_pt = polylabel(local, tolerance=0.05)
        original_centre = (float(centre_pt.x), float(centre_pt.y))
        inscribed = float(centre_pt.distance(local.boundary))
        size_scale_factor = 1.0
        scale_reasons: list[str] = []
        if inscribed < MIN_INSCRIBED_RADIUS_MM:
            boost = MIN_INSCRIBED_RADIUS_MM / max(inscribed, 0.1)
            size_scale_factor = boost
            scale_reasons.append("minimum_mechanism_radius")
            local = _scale_polygon(local, boost)
            map_poly = transform(
                lambda x, y, z=None: (
                    cx + (x - cx) * boost,
                    cy + (y - cy) * boost,
                ),
                map_poly,
            )
            centre_pt = polylabel(local, tolerance=0.05)
        (
            local,
            switch_centre,
            shoulder_wall,
            cap_retention,
            physical_scale,
            physical_reasons,
        ) = _fit_switch_and_top(
            local,
            (float(centre_pt.x), float(centre_pt.y)),
            name,
        )
        if physical_scale != 1.0:
            map_poly = transform(
                lambda x, y, z=None: (
                    cx + (x - cx) * physical_scale,
                    cy + (y - cy) * physical_scale,
                ),
                map_poly,
            )
            size_scale_factor *= physical_scale
            scale_reasons.extend(physical_reasons)
        inscribed = float(Point(*switch_centre).distance(local.boundary))
        lower_wall = _switch_wall_mm(
            local,
            switch_centre,
            _SWITCH_LOWER_PROFILE,
        )
        shifted_original = (
            original_centre[0] * size_scale_factor,
            original_centre[1] * size_scale_factor,
        )
        centre_shift = math.dist(switch_centre, shifted_original)
        boosted = size_scale_factor > 1.0 + 1e-6
        shell_name, shell_hex, top_name, top_hex = COUNTY_COLOURS[name]
        result[name] = CountyGeometry(
            name=name,
            outer=local,
            map_polygon=map_poly,
            source_polygon=source_poly,
            centre_local=switch_centre,
            inscribed_radius=inscribed,
            shell_colour=(shell_name, shell_hex),
            top_colour=(top_name, top_hex),
            size_boosted=boosted,
            size_scale_factor=size_scale_factor,
            switch_shoulder_wall_mm=shoulder_wall,
            switch_lower_wall_mm=lower_wall,
            switch_center_shift_mm=centre_shift,
            cap_area_retention=cap_retention,
            scale_reasons=tuple(scale_reasons),
        )
    return result


def _extrude(polygon: Polygon, height: float, z0: float = 0.0) -> trimesh.Trimesh:
    mesh = trimesh.creation.extrude_polygon(polygon, height=height, engine="earcut")
    mesh.apply_translation([0.0, 0.0, z0])
    return mesh


def _difference(mesh: trimesh.Trimesh, cutters: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    result = trimesh.boolean.difference([mesh, *cutters], engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    return result


def _union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    result = trimesh.boolean.union(meshes, engine="manifold")
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    return result


def _raw_cap_polygon(outer: Polygon, county_name: str | None = None) -> Polygon:
    pocket = _pocket_polygon(outer, POCKET_INSET)
    clearance = _cap_side_clearance(county_name)
    cap = _largest_polygon(
        pocket.buffer(
            -clearance,
            resolution=16,
            join_style="round",
        )
    )
    return cap


def _cap_polygon(outer: Polygon, county_name: str | None = None) -> Polygon:
    """Return a robust top offset from the actual pocket."""
    raw_cap = _raw_cap_polygon(outer, county_name)
    erosion = _min_cap_neck(county_name) / 2
    core = raw_cap.buffer(-erosion, resolution=8, join_style="round")
    if hasattr(core, "geoms"):
        parts = [part for part in core.geoms if isinstance(part, Polygon)]
        if parts:
            main = max(parts, key=lambda part: part.area)
            rebuilt = main.buffer(erosion, resolution=8, join_style="round")
            cap = _largest_polygon(raw_cap.intersection(rebuilt))
        else:
            cap = raw_cap
    else:
        cap = raw_cap
    if not cap.is_valid or cap.area <= 0:
        raise ValueError("Cap inset produced an invalid polygon")
    return cap


def _pocket_polygon(outer: Polygon, inset: float) -> Polygon:
    pocket = _largest_polygon(outer.buffer(-inset, resolution=5, join_style="round"))
    pocket = pocket.simplify(0.12, preserve_topology=True)
    if not pocket.is_valid or pocket.area <= 0:
        raise ValueError("Pocket inset produced an invalid polygon")
    return pocket


def _cavity_levels() -> list[tuple[float, float, float]]:
    """Full tested switch opening and flange shoulder."""
    return [
        (SWITCH_PIN_CLEARANCE_FLOOR, SWITCH_OPENING, SWITCH_OPENING),
        (10.8, SWITCH_OPENING, SWITCH_OPENING),
        (12.2, SWITCH_SHOULDER_SIZE_MM, SWITCH_SHOULDER_SIZE_MM),
        (BODY_HEIGHT + 1.0, SWITCH_SHOULDER_SIZE_MM, SWITCH_SHOULDER_SIZE_MM),
    ]


def build_shell(county: CountyGeometry) -> trimesh.Trimesh:
    if county.switch_shoulder_wall_mm < MIN_SWITCH_SHOULDER_WALL_MM:
        raise ValueError(
            f"{county.name} has only {county.switch_shoulder_wall_mm:.2f} mm "
            f"around the switch shoulder"
        )
    body = _extrude(county.outer, BODY_HEIGHT)
    pocket = _extrude(
        _pocket_polygon(county.outer, POCKET_INSET),
        BODY_HEIGHT - POCKET_FLOOR_Z + 1.0,
        POCKET_FLOOR_Z,
    )
    cavity = sushi._lofted_solid(
        _cavity_levels(),
        exponent=30.0,
        sections=64,
    )
    cavity.apply_translation([county.centre_local[0], county.centre_local[1], 0.0])
    shell = _difference(body, [pocket, cavity])
    shell.metadata["name"] = f"{county.name} fixed shell"
    return shell


def build_cap(county: CountyGeometry) -> trimesh.Trimesh:
    clearance = _cap_side_clearance(county.name)
    min_clearance = _min_side_clearance(county.name)
    if clearance < min_clearance:
        raise ValueError(
            f"{county.name} CAP_SIDE_CLEARANCE {clearance} must be >= "
            f"MIN_SIDE_CLEARANCE_MM {min_clearance}"
        )
    cap_poly = _cap_polygon(county.outer, county.name)
    centre = county.centre_local
    slab = _extrude(cap_poly, CAP_SLAB_THICKNESS, CAP_SLAB_Z0)
    boss = sushi._cylinder(
        MX_SOCKET_BOSS_D / 2,
        5.55,
        (centre[0], centre[1], 2.775),
        sections=96,
    )
    button = _union([slab, boss])
    socket = sushi._mx_cross_cutter(
        MX_CROSS_MAJOR,
        MX_CROSS_MINOR,
        MX_SOCKET_DEPTH,
        z0=-0.05,
    )
    socket.apply_translation([centre[0], centre[1], 0.0])
    button = _difference(button, [socket])
    button.metadata["name"] = f"{county.name} moving top"
    return button, cap_poly, _cap_inset(county.name)


def _sample_side_clearance(
    cap: Polygon,
    pocket: Polygon,
    samples: int = 250,
    county_name: str | None = None,
) -> dict:
    """Signed distance from cap outline samples to the pocket wall (mm)."""
    coords = list(cap.exterior.coords)
    step = max(1, len(coords) // samples)
    signed: list[float] = []
    outside_area = float(cap.difference(pocket).area)
    for x, y in coords[::step]:
        point = Point(x, y)
        if pocket.contains(point) or pocket.boundary.distance(point) < 1e-6:
            signed.append(float(point.distance(pocket.boundary)))
        else:
            signed.append(-float(point.distance(pocket.boundary)))
    signed.sort()
    exact_min = float(cap.boundary.distance(pocket.boundary))
    return {
        "cap_inside_pocket": outside_area <= 1e-3 and (not signed or signed[0] >= 0.0),
        "cap_outside_pocket_area_mm2": round(outside_area, 4),
        "min_side_clearance_mm": round(signed[0], 4) if signed else 0.0,
        "p10_side_clearance_mm": round(signed[max(0, len(signed) // 10)], 4)
        if signed
        else 0.0,
        "median_side_clearance_mm": round(signed[len(signed) // 2], 4) if signed else 0.0,
        "exact_min_side_clearance_mm": round(exact_min, 4),
        "target_side_clearance_mm": round(_cap_side_clearance(county_name), 3),
        "min_allowed_side_clearance_mm": _min_side_clearance(county_name),
    }


def _cap_robustness(
    outer: Polygon,
    cap: Polygon,
    county_name: str | None = None,
) -> dict:
    raw_cap = _raw_cap_polygon(outer, county_name)
    neck = _min_cap_neck(county_name)
    erosion = neck / 2
    core = cap.buffer(-erosion, resolution=8, join_style="round")
    parts = (
        [part for part in core.geoms if isinstance(part, Polygon)]
        if hasattr(core, "geoms")
        else ([] if core.is_empty else [core])
    )
    part_areas = sorted((float(part.area) for part in parts), reverse=True)
    secondary_area = sum(part_areas[1:]) if len(part_areas) > 1 else 0.0
    return {
        "cap_area_retention_percent": round(100 * cap.area / outer.area, 3),
        "cap_perimeter_retention_percent": round(100 * cap.length / outer.length, 3),
        "fragile_lobe_trimmed_percent": round(
            100 * max(0.0, raw_cap.area - cap.area) / raw_cap.area,
            4,
        ),
        "neck_test_width_mm": neck,
        "core_component_count": len(parts),
        "secondary_core_area_percent": round(
            100 * secondary_area / cap.area if cap.area else 0.0,
            4,
        ),
        "min_area_retention_percent": round(100 * MIN_CAP_AREA_RETENTION, 1),
    }


def _cap_shell_overlap_mm3(
    shell: trimesh.Trimesh,
    cap: trimesh.Trimesh,
    assembled_z: float,
) -> float:
    """Return full moving-top/shell overlap, including the MX boss."""
    moved = cap.copy()
    moved.apply_translation([0.0, 0.0, assembled_z])
    overlap = trimesh.boolean.intersection([shell, moved], engine="manifold")
    if overlap is None or overlap.is_empty:
        return 0.0
    return float(overlap.volume)


def check_boundary_fidelity(county: CountyGeometry) -> dict:
    """Compare the printable outline with its official open-data boundary."""
    generated = county.map_polygon
    if county.size_scale_factor != 1.0:
        cx = (generated.bounds[0] + generated.bounds[2]) / 2
        cy = (generated.bounds[1] + generated.bounds[3]) / 2
        generated = transform(
            lambda x, y, z=None: (
                cx + (x - cx) / county.size_scale_factor,
                cy + (y - cy) / county.size_scale_factor,
            ),
            generated,
        )

    source = county.source_polygon
    intersection_area = float(source.intersection(generated).area)
    union_area = float(source.union(generated).area)
    iou = intersection_area / union_area if union_area > 0 else 0.0
    hausdorff = float(source.boundary.hausdorff_distance(generated.boundary))
    area_ratio = float(generated.area / source.area) if source.area > 0 else 0.0
    ok = iou >= MIN_BOUNDARY_IOU and hausdorff <= MAX_BOUNDARY_HAUSDORFF_MM
    if county.name in NI_COUNTIES:
        dataset = "OSNI Open Data – 50K Boundaries – NI Counties"
        publisher = "Ordnance Survey of Northern Ireland / Land & Property Services"
        licence = "UK Open Government Licence 3.0"
    else:
        dataset = "Counties – National Statutory Boundaries – 2019"
        publisher = "Tailte Éireann"
        licence = "Creative Commons Attribution 4.0"
    return {
        "ok": ok,
        "dataset": dataset,
        "publisher": publisher,
        "licence": licence,
        "iou": round(iou, 6),
        "accuracy_percent_iou": round(iou * 100, 3),
        "hausdorff_distance_mm_at_print_scale": round(hausdorff, 4),
        "generated_to_source_area_ratio": round(area_ratio, 6),
        "size_scale_factor_excluded_from_comparison": round(
            county.size_scale_factor, 6
        ),
        "min_iou": MIN_BOUNDARY_IOU,
        "max_hausdorff_mm": MAX_BOUNDARY_HAUSDORFF_MM,
    }


def check_cap_pocket_fit(
    county: CountyGeometry,
    *,
    shell: trimesh.Trimesh | None = None,
    cap: trimesh.Trimesh | None = None,
    cap_poly: Polygon | None = None,
) -> dict:
    """Geometric + mesh fit checks for the nested moving top."""
    pocket = _pocket_polygon(county.outer, POCKET_INSET)
    if cap_poly is None:
        cap_poly = _cap_polygon(county.outer, county.name)
    clearance = _sample_side_clearance(cap_poly, pocket, county_name=county.name)
    robustness = _cap_robustness(county.outer, cap_poly, county.name)
    min_side = _min_side_clearance(county.name)
    cap_centre = polylabel(cap_poly, tolerance=0.05)
    cap_inscribed = float(cap_centre.distance(cap_poly.boundary))
    switch_point = Point(*county.centre_local)
    switch_in_cap = cap_poly.contains(switch_point)
    boss_edge_clearance = (
        float(switch_point.distance(cap_poly.boundary)) - MX_SOCKET_BOSS_D / 2
        if switch_in_cap
        else -1.0
    )
    shoulder_wall = _switch_wall_mm(county.outer, county.centre_local)
    lower_wall = _switch_wall_mm(
        county.outer,
        county.centre_local,
        _SWITCH_LOWER_PROFILE,
    )
    fidelity = check_boundary_fidelity(county)
    issues: list[str] = []
    if not clearance["cap_inside_pocket"]:
        issues.append(
            f"top outline is not inside the pocket "
            f"(outside area {clearance['cap_outside_pocket_area_mm2']} mm²)"
        )
    if clearance["exact_min_side_clearance_mm"] < min_side:
        issues.append(
            f"exact min side clearance "
            f"{clearance['exact_min_side_clearance_mm']} mm "
            f"< {min_side} mm"
        )
    if cap_inscribed < MX_SOCKET_BOSS_D / 2 + 1.5:
        issues.append(
            f"cap inscribed radius {cap_inscribed:.2f} mm is too small for MX boss"
        )
    if shoulder_wall < MIN_SWITCH_SHOULDER_WALL_MM:
        issues.append(
            f"switch shoulder wall {shoulder_wall:.3f} mm "
            f"< {MIN_SWITCH_SHOULDER_WALL_MM:.3f} mm"
        )
    if robustness["cap_area_retention_percent"] < 100 * MIN_CAP_AREA_RETENTION:
        issues.append(
            f"moving-top area retention "
            f"{robustness['cap_area_retention_percent']:.2f}% "
            f"< {100 * MIN_CAP_AREA_RETENTION:.2f}%"
        )
    if robustness["core_component_count"] > 1:
        issues.append(
            f"moving top has {robustness['core_component_count']} substantial "
            f"components after {_min_cap_neck(county.name):.2f} mm neck test"
        )
    if not switch_in_cap or boss_edge_clearance < 1.5:
        issues.append(
            f"MX boss edge clearance {boss_edge_clearance:.2f} mm is too small "
            f"at optimized switch centre"
        )
    if not fidelity["ok"]:
        issues.append(
            f"boundary fidelity failed: IoU {fidelity['iou']:.4f}, "
            f"Hausdorff {fidelity['hausdorff_distance_mm_at_print_scale']:.4f} mm"
        )

    travel = {}
    if shell is not None and cap is not None:
        for label, z in (
            ("released", CAP_ASSEMBLED_Z),
            ("mid", CAP_ASSEMBLED_Z - FULL_TRAVEL / 2),
            ("pressed", CAP_ASSEMBLED_Z - FULL_TRAVEL),
        ):
            vol = _cap_shell_overlap_mm3(shell, cap, z)
            travel[label] = {
                "assembled_z": z,
                "cap_shell_overlap_mm3": round(vol, 4),
            }
            if vol > MAX_TRAVEL_OVERLAP_MM3:
                issues.append(
                    f"{label} position: cap/shell overlap {vol:.4f} mm³ "
                    f"> {MAX_TRAVEL_OVERLAP_MM3} mm³"
                )

    return {
        "county": county.name,
        "ok": not issues,
        "issues": issues,
        "clearance": clearance,
        "cap_inscribed_radius_mm": round(cap_inscribed, 3),
        "mx_boss_edge_clearance_mm": round(boss_edge_clearance, 3),
        "shell_inscribed_radius_mm": round(county.inscribed_radius, 3),
        "switch_cavity": {
            "centre_strategy": "square-shoulder clearance optimization",
            "centre_shift_from_circle_polylabel_mm": round(
                county.switch_center_shift_mm,
                3,
            ),
            "lower_opening_wall_mm": round(lower_wall, 3),
            "shoulder_wall_mm": round(shoulder_wall, 3),
            "min_shoulder_wall_mm": MIN_SWITCH_SHOULDER_WALL_MM,
            "shoulder_size_mm": SWITCH_SHOULDER_SIZE_MM,
        },
        "moving_top_robustness": robustness,
        "boundary_source_fidelity": fidelity,
        "travel_cap_overlap": travel,
        "decisions_needed": [],
    }


def validate_county_map_fit(counties: dict[str, CountyGeometry] | None = None) -> dict:
    """Fast 2D fit audit for every county (no mesh booleans)."""
    counties = counties or load_county_map()
    results = []
    for name in COUNTIES:
        report = check_cap_pocket_fit(counties[name])
        results.append(report)
    failed = [item for item in results if not item["ok"]]
    fidelities = [item["boundary_source_fidelity"] for item in results]
    shoulders = [item["switch_cavity"]["shoulder_wall_mm"] for item in results]
    cap_retention = [
        item["moving_top_robustness"]["cap_area_retention_percent"]
        for item in results
    ]
    return {
        "ok": not failed,
        "reference_width_mm": REFERENCE_WIDTH_MM,
        "cap_inset": CAP_INSET,
        "pocket_inset": POCKET_INSET,
        "min_side_clearance_mm": MIN_SIDE_CLEARANCE_MM,
        "county_cap_side_clearance_mm": COUNTY_CAP_SIDE_CLEARANCE_MM,
        "county_min_side_clearance_mm": COUNTY_MIN_SIDE_CLEARANCE_MM,
        "county_min_cap_neck_mm": COUNTY_MIN_CAP_NECK_MM,
        "county_count": len(results),
        "failed_count": len(failed),
        "failed_counties": [item["county"] for item in failed],
        "physical_printability": {
            "min_switch_shoulder_wall_mm": round(min(shoulders), 3),
            "required_switch_shoulder_wall_mm": MIN_SWITCH_SHOULDER_WALL_MM,
            "min_moving_top_area_retention_percent": round(
                min(cap_retention),
                3,
            ),
            "required_moving_top_area_retention_percent": round(
                100 * MIN_CAP_AREA_RETENTION,
                1,
            ),
            "moving_top_neck_test_mm": MIN_CAP_NECK_MM,
        },
        "boundary_source_accuracy": {
            "metric": "intersection over union after reversing intentional size boost",
            "min_accuracy_percent_iou": round(
                min(item["accuracy_percent_iou"] for item in fidelities), 3
            ),
            "max_accuracy_percent_iou": round(
                max(item["accuracy_percent_iou"] for item in fidelities), 3
            ),
            "max_hausdorff_distance_mm_at_print_scale": round(
                max(
                    item["hausdorff_distance_mm_at_print_scale"]
                    for item in fidelities
                ),
                4,
            ),
            "min_required_iou": MIN_BOUNDARY_IOU,
            "max_allowed_hausdorff_mm": MAX_BOUNDARY_HAUSDORFF_MM,
        },
        "results": results,
    }


def _validate_mesh(name: str, mesh: trimesh.Trimesh) -> dict:
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight:
        raise ValueError(f"{name} is not watertight")
    if not mesh.is_volume or mesh.volume <= 0:
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


def _top_model(title: str, object_count: int) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{bambu.CORE}" '
        f'xmlns:BambuStudio="{bambu.BAMBU}" xmlns:p="{bambu.PROD}" requiredextensions="p">',
        ' <metadata name="Application">BambuStudio-02.07.01.62</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        f' <metadata name="Title">{escape(title)}</metadata>',
        " <resources>",
    ]
    for index in range(1, object_count + 1):
        top_id = 99 + index
        lines.extend(
            [
                f'  <object id="{top_id}" p:UUID="{bambu.object_uuid(top_id, 0xABCDEF123456)}" type="model">',
                "   <components>",
                f'    <component p:path="/3D/Objects/object_{index}.model" objectid="{index}" '
                f'p:UUID="{bambu.object_uuid(0x1000 + index, 0xABCDEF123456)}" '
                'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>',
                "   </components>",
                "  </object>",
            ]
        )
    lines.extend(
        [
            " </resources>",
            f' <build p:UUID="{bambu.object_uuid(9999, 0xABCDEF123456)}">',
        ]
    )
    positions = ((128.0, 128.0, 0.0), (440.0, 128.0, 0.0), (128.0, -184.0, 0.0))
    for index, (x, y, z) in enumerate(positions[:object_count], start=1):
        lines.append(
            f'  <item objectid="{99 + index}" '
            f'p:UUID="{bambu.object_uuid(5000 + index, 0xABCDEF123456)}" '
            f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}" printable="1"/>'
        )
    lines.extend([" </build>", "</model>"])
    return ("\n".join(lines) + "\n").encode()


def _model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
    plates: list[tuple[str, list[int]]],
) -> bytes:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    overrides = {
        "layer_height": "0.16",
        "wall_loops": "4",
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
    for index, ((name, source, extruder), mesh) in enumerate(zip(objects, meshes), start=1):
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
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                "    </part>",
                "  </object>",
            ]
        )
    for plate_number, (plate_name, object_indices) in enumerate(plates, start=1):
        lines.extend(
            [
                "  <plate>",
                f'    <metadata key="plater_id" value="{plate_number}"/>',
                f'    <metadata key="plater_name" value="{escape(plate_name)}"/>',
                '    <metadata key="locked" value="false"/>',
                '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
                f'    <metadata key="thumbnail_file" value="Metadata/plate_{plate_number}.png"/>',
                f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{plate_number}.png"/>',
                f'    <metadata key="top_file" value="Metadata/top_{plate_number}.png"/>',
                f'    <metadata key="pick_file" value="Metadata/pick_{plate_number}.png"/>',
            ]
        )
        for object_index in object_indices:
            lines.extend(
                [
                    "    <model_instance>",
                    f'      <metadata key="object_id" value="{99 + object_index}"/>',
                    '      <metadata key="instance_id" value="0"/>',
                    f'      <metadata key="identify_id" value="{299 + object_index}"/>',
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


def _preview_png(
    *,
    title: str,
    plate_number: int,
    outer: Polygon,
    cap: Polygon,
    shell_hex: str,
    top_hex: str,
) -> bytes:
    image = Image.new("RGBA", (512, 512), (246, 247, 244, 255))
    draw = ImageDraw.Draw(image)
    polygon = outer if plate_number == 1 else cap
    min_x, min_y, max_x, max_y = polygon.bounds
    scale = min(390 / max(max_x - min_x, 1e-3), 310 / max(max_y - min_y, 1e-3))
    points = [
        (
            256 + (x - (min_x + max_x) / 2) * scale,
            260 - (y - (min_y + max_y) / 2) * scale,
        )
        for x, y in polygon.exterior.coords
    ]
    fill = shell_hex if plate_number == 1 else top_hex
    draw.polygon(points, fill=fill, outline="#252C29", width=4)
    draw.text((24, 24), f"{title} - plate {plate_number}", fill="#252C29")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_bambu_project(
    *,
    title: str,
    output_path: Path,
    objects: list[tuple[str, Path, int]],
    plates: list[tuple[str, list[int]]],
    outer: Polygon,
    cap: Polygon,
    filaments: list[tuple[str, str]],
) -> Path:
    meshes = [trimesh.load_mesh(path, process=True) for _, path, _ in objects]
    for (name, _, _), mesh in zip(objects, meshes):
        _validate_mesh(name, mesh)

    bambu.OBJECTS = objects
    template_path = GENERATOR_DIR / "blank_project.3mf"
    with (
        zipfile.ZipFile(template_path) as template,
        zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", _top_model(title, len(objects)))
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr(
            "Metadata/model_settings.config",
            _model_settings(objects, meshes, plates),
        )

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["layer_height"] = "0.16"
        settings["initial_layer_print_height"] = "0.20"
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        settings["enable_prime_tower"] = "0"
        settings["filament_colour"] = [colour for _, colour in filaments]
        settings["default_filament_colour"] = ["", ""]
        settings["filament_settings_id"] = [
            "Bambu PLA Matte @BBL P2S" for _ in filaments
        ]
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=2, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))
        for plate_number in range(1, len(plates) + 1):
            preview = _preview_png(
                title=title,
                plate_number=plate_number,
                outer=outer,
                cap=cap,
                shell_hex=filaments[0][1],
                top_hex=filaments[1][1],
            )
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(f"Metadata/{stem}_{plate_number}.png", preview)

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
    return output_path


def generate_county(county: CountyGeometry, job_dir: Path) -> Path:
    job_dir = Path(job_dir)
    mesh_dir = job_dir / "meshes"
    if mesh_dir.exists():
        shutil.rmtree(mesh_dir)
    mesh_dir.mkdir(parents=True, exist_ok=True)

    shell = build_shell(county)
    cap, cap_poly, cap_inset = build_cap(county)
    fit = check_cap_pocket_fit(
        county,
        shell=shell,
        cap=cap,
        cap_poly=cap_poly,
    )
    if not fit["ok"]:
        raise ValueError(
            f"{county.name} failed nest fit checks: " + "; ".join(fit["issues"])
        )
    cap_print = cap.copy()
    cap_print.apply_transform(
        trimesh.transformations.rotation_matrix(np.pi, [1.0, 0.0, 0.0])
    )
    cap_print.apply_translation([0.0, 0.0, -float(cap_print.bounds[0, 2])])

    named = [
        (f"{county.name.lower()}_shell", shell),
        (f"{county.name.lower()}_top", cap_print),
    ]
    validation = []
    for filename, mesh in named:
        validation.append(_validate_mesh(filename, mesh))
        mesh.export(mesh_dir / f"{filename}.stl")

    objects = [
        (f"{county.name} fixed shell", mesh_dir / f"{county.name.lower()}_shell.stl", 1),
        (f"{county.name} moving top", mesh_dir / f"{county.name.lower()}_top.stl", 2),
    ]
    plates = [
        (f"{county.name} shell", [1]),
        (f"{county.name} moving top", [2]),
    ]
    output = job_dir / f"{county.name}_County_Clicker_P2S.3mf"
    build_bambu_project(
        title=f"{county.name} County Clicker",
        output_path=output,
        objects=objects,
        plates=plates,
        outer=county.outer,
        cap=cap_poly,
        filaments=[county.shell_colour, county.top_colour],
    )

    report = {
        "project": f"{county.name} County Clicker",
        "series": "Standalone Ireland county clickers",
        "units": "mm",
        "sizing": {
            "reference_county": REFERENCE_COUNTY,
            "reference_width_mm": REFERENCE_WIDTH_MM,
            "size_boosted": county.size_boosted,
            "size_scale_factor": round(county.size_scale_factor, 6),
            "scale_reasons": list(county.scale_reasons),
            "placement_center_mm": [
                round((county.map_polygon.bounds[0] + county.map_polygon.bounds[2]) / 2, 3),
                round((county.map_polygon.bounds[1] + county.map_polygon.bounds[3]) / 2, 3),
            ],
        },
        "filaments": [
            {"slot": 1, "name": county.shell_colour[0], "hex": county.shell_colour[1]},
            {"slot": 2, "name": county.top_colour[0], "hex": county.top_colour[1]},
        ],
        "shell": {
            "outer_size": [
                round(county.outer.bounds[2] - county.outer.bounds[0], 3),
                round(county.outer.bounds[3] - county.outer.bounds[1], 3),
                BODY_HEIGHT,
            ],
            "inscribed_radius_mm": round(county.inscribed_radius, 3),
            "cap_inset": round(cap_inset, 3),
            "pocket_inset": POCKET_INSET,
            "moving_side_clearance": round(cap_inset - POCKET_INSET, 3),
            "min_side_clearance_mm": _min_side_clearance(county.name),
        },
        "moving_top": {
            "released_height_above_shell": round(CAP_PROUD, 3),
            "full_switch_travel": FULL_TRAVEL,
            "print_orientation": "top face-down; MX socket boss points upward",
            "robustness": fit["moving_top_robustness"],
        },
        "switch": {
            "type": "Outemu (Gaote) Blue, 3-pin, 50 gf",
            "centre_xy": [round(county.centre_local[0], 3), round(county.centre_local[1], 3)],
            "mount_opening": SWITCH_OPENING,
            "shoulder_size": SWITCH_SHOULDER_SIZE_MM,
            "lower_opening_wall_mm": fit["switch_cavity"]["lower_opening_wall_mm"],
            "shoulder_wall_mm": fit["switch_cavity"]["shoulder_wall_mm"],
            "minimum_shoulder_wall_mm": MIN_SWITCH_SHOULDER_WALL_MM,
            "centre_strategy": fit["switch_cavity"]["centre_strategy"],
        },
        "boundary_source_fidelity": fit["boundary_source_fidelity"],
        "fit_checks": fit,
        "validation": validation,
    }
    (job_dir / "dimensions_and_validation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return output


def write_ireland_layout(counties: dict[str, CountyGeometry], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    union = unary_union([county.map_polygon for county in counties.values()])
    min_x, min_y, max_x, max_y = union.bounds
    width = max_x - min_x
    height = max_y - min_y
    pad = 24.0
    svg_w = width + 2 * pad
    svg_h = height + 2 * pad + 56
    boosted = sorted(name for name, county in counties.items() if county.size_boosted)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w:.1f}" height="{svg_h:.1f}" '
        f'viewBox="0 0 {svg_w:.1f} {svg_h:.1f}">',
        '<rect width="100%" height="100%" fill="#F4F6F2"/>',
        f'<text x="{pad}" y="28" font-family="system-ui,sans-serif" font-size="18" '
        f'font-weight="700" fill="#252C29">Ireland county clickers — geographic preview only</text>',
        f'<text x="{pad}" y="46" font-family="system-ui,sans-serif" font-size="11" fill="#65706A">'
        f'{width:.0f} x {height:.0f} mm · Tyrone ~{REFERENCE_WIDTH_MM:.0f} mm handheld · '
        f'standalone pieces · independently enlarged where needed · not tessellating</text>',
        f'<text x="{pad}" y="62" font-family="system-ui,sans-serif" font-size="11" fill="#65706A">'
        f'Near-white GAA shells show their top colour on this preview so the county stays visible'
        f'{(" · boosted for switch: " + ", ".join(boosted)) if boosted else ""}</text>',
        f'<g transform="translate({pad} {pad + 48}) scale(1 -1) translate(0 {-height})">',
    ]
    layout = {
        "ireland_width_mm": round(width, 3),
        "ireland_height_mm": round(height, 3),
        "reference_county": REFERENCE_COUNTY,
        "reference_width_mm": REFERENCE_WIDTH_MM,
        "origin": "southwest corner of the projected island bounds",
        "counties": {},
    }
    for name in COUNTIES:
        county = counties[name]
        coords = " ".join(
            f"{x:.2f},{y:.2f}" for x, y in county.map_polygon.exterior.coords
        )
        fill, stroke = _map_swatch(county.shell_colour[1], county.top_colour[1])
        parts.append(
            f'<path d="M {coords} Z" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="0.8" '
            f'fill-opacity="0.92">'
            f'<title>{name} — shell {county.shell_colour[0]}, top {county.top_colour[0]}'
            f'{" (size-boosted)" if county.size_boosted else ""}</title></path>'
        )
        cx = (county.map_polygon.bounds[0] + county.map_polygon.bounds[2]) / 2
        cy = (county.map_polygon.bounds[1] + county.map_polygon.bounds[3]) / 2
        layout["counties"][name] = {
            "center_mm": [round(cx, 3), round(cy, 3)],
            "bounds_mm": {
                "min": [round(v, 3) for v in county.map_polygon.bounds[:2]],
                "max": [round(v, 3) for v in county.map_polygon.bounds[2:]],
                "size": [
                    round(county.map_polygon.bounds[2] - county.map_polygon.bounds[0], 3),
                    round(county.map_polygon.bounds[3] - county.map_polygon.bounds[1], 3),
                ],
            },
            "shell": {"name": county.shell_colour[0], "hex": county.shell_colour[1]},
            "top": {"name": county.top_colour[0], "hex": county.top_colour[1]},
            "inscribed_radius_mm": round(county.inscribed_radius, 3),
            "size_boosted": county.size_boosted,
            "size_scale_factor": round(county.size_scale_factor, 6),
            "scale_reasons": list(county.scale_reasons),
            "switch_shoulder_wall_mm": round(
                county.switch_shoulder_wall_mm,
                3,
            ),
            "moving_top_area_retention_percent": round(
                county.cap_area_retention * 100,
                3,
            ),
            "boundary_source_fidelity": check_boundary_fidelity(county),
            "geojson": mapping(county.map_polygon),
        }
    parts.extend(["</g>", "</svg>"])
    svg_path = out_dir / "ireland_county_clicker_map.svg"
    svg_path.write_text("\n".join(parts) + "\n")
    (out_dir / "ireland_county_clicker_layout.json").write_text(
        json.dumps(layout, indent=2) + "\n"
    )
    return svg_path


def generate_all(out_root: Path, only: list[str] | None = None) -> list[Path]:
    counties = load_county_map()
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    audit = validate_county_map_fit(counties)
    (out_root / "series_fit_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    if not audit["ok"]:
        raise ValueError(
            "Series nest-fit audit failed for: " + ", ".join(audit["failed_counties"])
        )
    selected = only or list(COUNTIES)
    outputs = []
    for name in selected:
        county = counties[name]
        print(f"Generating {name} ...", flush=True)
        outputs.append(generate_county(county, out_root / name.lower()))
    print(f"Wrote {len(outputs)} standalone county projects to {out_root}", flush=True)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate standalone Ireland county MX clickers"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--county",
        action="append",
        choices=list(COUNTIES),
        help="Generate only this county (repeatable). Default: all 32.",
    )
    parser.add_argument(
        "--layout-only",
        action="store_true",
        help="Write a geographic reference SVG/JSON (not a tessellating assembly)",
    )
    parser.add_argument(
        "--check-fit",
        action="store_true",
        help="Run 2D nest-fit audit for all counties and write series_fit_audit.json",
    )
    args = parser.parse_args()
    if args.check_fit:
        audit = validate_county_map_fit()
        args.out.mkdir(parents=True, exist_ok=True)
        path = args.out / "series_fit_audit.json"
        path.write_text(json.dumps(audit, indent=2) + "\n")
        print(path)
        if not audit["ok"]:
            raise SystemExit(
                "Fit audit failed: " + ", ".join(audit["failed_counties"])
            )
        print(
            f"Fit audit OK — {audit['county_count']} counties, "
            f"cap inset {audit['cap_inset']} mm, "
            f"min clearance {audit['min_side_clearance_mm']} mm, "
            f"min shoulder wall "
            f"{audit['physical_printability']['min_switch_shoulder_wall_mm']:.3f} mm, "
            f"boundary IoU "
            f"{audit['boundary_source_accuracy']['min_accuracy_percent_iou']:.3f}–"
            f"{audit['boundary_source_accuracy']['max_accuracy_percent_iou']:.3f}%"
        )
        return
    if args.layout_only:
        counties = load_county_map()
        path = write_ireland_layout(counties, args.out)
        print(path)
        return
    for path in generate_all(args.out, only=args.county):
        print(path)


if __name__ == "__main__":
    main()
