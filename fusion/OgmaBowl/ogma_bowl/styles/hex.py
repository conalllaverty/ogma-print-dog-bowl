"""Honeycomb drum — a continuous wall with recessed grooves between proud tiles.

The generator computes a radial offset per (theta, z) sample and wraps a
1056 x 209 point mesh around it. That is not a shape Fusion can hold as BRep,
so the same result is built the other way round: recess the wall across the
pattern band, then put the hexagonal tiles back as real solids and trim them
flush to the true cylinder.

What is preserved exactly
    cell radius, pitch and stagger (from config.honeycomb_params, including
    the generator's banker's-rounded column count of 36), groove depth, groove
    gap, remaining web, the 5 mm pattern-free edge bands, both border rings,
    the top bead, the bottom chamfer, and the Cooper seat.

What differs
    the groove wall is a straight taper rather than a smoothstep chamfer, and
    the name keepout is a rectangular patch rather than a whole-cell-boundary
    suppression. Both are visible only under raking light and both stay
    parameter-driven.
"""

from __future__ import annotations

import math

import adsk.fusion

from .. import config as cfg
from ..api import (
    circular_pattern,
    cut,
    extrude,
    join,
    largest_profile,
    offset_plane,
    polyline,
    rectangular_pattern,
    sketch_on,
)
from .common import annulus_body, build_drum, sagitta

STYLE_ID = "hex"
LABEL = cfg.STYLE_LABELS["hex"]
OUTPUT_SUFFIX = "Honeycomb"


def _hexagon_points(radius_mm: float, apothem_mm: float, centre_z_mm: float):
    """Flat-top hexagon in (u, z) — vertices left/right, flats top/bottom.

    Matches the generator's distance metric
    `max(dz, dz*0.5 + du*sqrt(3)/2) <= apothem`, which puts the vertices at
    +/-radius along u and the flats at +/-apothem along z.
    """
    r, a = radius_mm, apothem_mm
    return [
        (r, centre_z_mm),
        (r * 0.5, centre_z_mm + a),
        (-r * 0.5, centre_z_mm + a),
        (-r, centre_z_mm),
        (-r * 0.5, centre_z_mm - a),
        (r * 0.5, centre_z_mm - a),
    ]


def _tile_column(component, p, hc, tile_r, tile_a, plane, column_offset_u,
                 z_start, rows, tag):
    """One staggered set: a tile, patterned around the drum and up it."""
    theta_step_deg = math.degrees(2.0 * hc["pitch_u"] / hc["reference_r"])
    sketch = sketch_on(component, plane, "ogma_hex_tile_{}".format(tag))
    centre_u = column_offset_u
    points = _hexagon_points(tile_r, tile_a, z_start)
    polyline(sketch, [(u + centre_u, z) for (u, z) in points])

    depth = p["groove_depth"] + 1.0
    feat = extrude(
        component,
        largest_profile(sketch),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        distance_mm=depth,
        direction=adsk.fusion.ExtentDirections.PositiveExtentDirection,
        taper_deg=-_taper_deg(p),
        name="Hex tile {}".format(tag),
    )
    body = feat.bodies.item(0)
    body.name = "ogma_hex_tile_{}".format(tag)

    around = circular_pattern(
        component, [body], component.zConstructionAxis,
        quantity=int(hc["ncols"] // 2), total_angle_deg=360.0,
        name="Hex ring {}".format(tag),
    )
    ring_bodies = _pattern_bodies(around, body)
    up = rectangular_pattern(
        component, ring_bodies, component.zConstructionAxis,
        quantity=rows, spacing_mm=hc["pitch_z"],
        name="Hex stack {}".format(tag),
    )
    return _pattern_bodies(up, *ring_bodies)


def _taper_deg(p) -> float:
    """Taper that turns the groove's vertical wall into the generator's chamfer.

    The generator smoothsteps the radial offset over `groove_chamfer` mm of
    in-plane distance while dropping `groove_depth` mm radially. The straight
    equivalent is the arctangent of that ratio.
    """
    return math.degrees(math.atan2(p["groove_chamfer"], p["groove_depth"]))


def _pattern_bodies(pattern_feature, *seeds):
    """Every body a pattern produced, plus the seeds it was built from."""
    bodies = list(seeds)
    try:
        for i in range(pattern_feature.bodies.count):
            bodies.append(pattern_feature.bodies.item(i))
    except Exception:
        pass
    seen, unique = set(), []
    for body in bodies:
        key = body.entityToken if hasattr(body, "entityToken") else id(body)
        if key not in seen:
            seen.add(key)
            unique.append(body)
    return unique


def build(component, ctx):
    """Build the honeycomb drum. `ctx` carries the resolved name/font options."""
    p = dict(cfg.HEX)
    hc = cfg.honeycomb_params(p)
    drum = build_drum(component, p, "Honeycomb body")

    band_z0 = p["pattern_edge_band"]
    band_z1 = p["h"] - p["pattern_edge_band"]
    wall_r = p["rb_out"]
    floor_r = wall_r - p["groove_depth"]

    # 1. recess the pattern band to the groove floor
    band = annulus_body(
        component, "ogma_hex_band", floor_r, wall_r + 5.0, band_z0, band_z1,
    )
    cut(component, drum, [band], "Recess pattern band")

    # 2. put the tiles back
    tile_apothem = hc["apothem"] - p["groove_gap"] * 0.5
    tile_radius = tile_apothem * 2.0 / math.sqrt(3.0)
    chord = 2.0 * tile_radius
    plane = offset_plane(
        component, component.xZConstructionPlane,
        -(wall_r + sagitta(wall_r, chord) + 0.2), "ogma_hex_tile_plane",
    )
    rows = int(math.ceil((band_z1 - band_z0) / hc["pitch_z"])) + 2
    z_start = band_z0 - hc["pitch_z"]

    tiles = []
    tiles += _tile_column(component, p, hc, tile_radius, tile_apothem, plane,
                          0.0, z_start, rows, "even")
    tiles += _tile_column(component, p, hc, tile_radius, tile_apothem, plane,
                          hc["pitch_u"], z_start + hc["pitch_z"] * 0.5, rows,
                          "odd")
    join(component, drum, tiles, "Honeycomb tiles")

    # 3. trim the flat-sketched tiles back to the true cylinder
    proud = annulus_body(
        component, "ogma_hex_trim", wall_r, wall_r + 6.0, band_z0, band_z1,
    )
    cut(component, drum, [proud], "Trim tiles flush")

    return {
        "body": drum,
        "wall_radius": wall_r,
        "letter_center_z": p["letter_center_z"],
        "keepout_margin": p["name_keepout_margin"],
        "keepout_fill_depth": p["groove_depth"],
        "parts": [drum],
        "notes": [
            "Honeycomb: {} columns of R{:.2f} mm cells, {:.2f} mm pitch, "
            "{:.2f} mm web left under the grooves.".format(
                hc["ncols"], hc["radius"], hc["pitch_u"],
                wall_r - p["wall_inner_r"] - p["groove_depth"]),
        ],
    }


def fill_name_keepout(component, drum, wall_r, centre_z, half_width, half_height,
                      depth):
    """Fill the grooves behind the name so the pockets cut into flat wall.

    The generator suppresses whole honeycomb cells here. A filled patch reads
    the same way from any normal viewing distance and, unlike per-instance
    pattern suppression, survives a change to the cell size without needing the
    timeline rolled back.
    """
    sketch = sketch_on(component, component.xZConstructionPlane,
                       "ogma_hex_name_patch")
    polyline(sketch, [
        (wall_r - depth - 0.2, centre_z - half_height),
        (wall_r, centre_z - half_height),
        (wall_r, centre_z + half_height),
        (wall_r - depth - 0.2, centre_z + half_height),
    ])
    span = math.degrees(2.0 * half_width / wall_r)
    from ..api import revolve_symmetric

    feat = revolve_symmetric(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        half_angle_deg=span * 0.5, name="Name patch",
    )
    patch = feat.bodies.item(0)
    patch.name = "ogma_name_patch"
    join(component, drum, [patch], "Smooth the name field")
    return patch
