"""Cooper paw lattice — base, paw panel, top seat ring, and glue-in letters.

Four printed parts, and the only style with a raised name plaque rather than
pockets cut straight into the wall.

Paw pads
--------
The generator bites each pad out with an ellipsoid whose centre sits just
outside the wall, so only `paw_recess_depth` of it is inside. Seven of those
make one paw: three metacarpal lobes and four digits, each with its own size
and tilt.

Fusion has no creatable sphere primitive (`SphereFeatures` is read-only), so an
ellipsoid means revolve-then-non-uniform-scale — three features per lobe, 21
per paw, ~1000 for the drum. Instead each lobe is drawn as a tilted ellipse on
a tangent plane and cut radially with a taper. At 0.7 mm deep the difference
between a dished ellipsoid floor and a tapered flat one is smaller than a layer
line, and the silhouette — which is the whole visual of the pad — is identical.
One sketch holds all seven lobes, so a paw is one sketch and one cut.

Pads inside the name-rail keepout are suppressed on the pattern rather than
skipped at creation, which needs the timeline marker rolled back to the pattern
first. That is a documented precondition, not a workaround.
"""

from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from .. import config as cfg
from ..api import (
    circular_pattern,
    collection,
    cut,
    extrude,
    join,
    largest_profile,
    offset_plane,
    polyline,
    pt,
    revolve,
    revolve_symmetric,
    sketch_on,
    suppress_pattern_elements,
)
from ..units import cm

STYLE_ID = "cooper"
LABEL = cfg.STYLE_LABELS["cooper"]
OUTPUT_SUFFIX = "Paw_Lattice"

P = cfg.COOPER


# --------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------

def build_base(component):
    """Annular base with the locating groove the panel's tongue drops into."""
    h = P["base_height"]
    r_out = P["stand_od"] * 0.5
    groove_out = P["wall_outer_r"] + 0.35
    groove_in = P["wall_inner_r"] - 0.35
    groove_z = h - 3.5

    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_base_profile")
    polyline(sketch, [
        (P["base_inner_r"], 0.0),
        (r_out, 0.0),
        (r_out, h),
        (groove_out, h),
        (groove_out, groove_z),
        (groove_in, groove_z),
        (groove_in, h),
        (P["base_inner_r"], h),
    ])
    feat = revolve(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0, name="Base",
    )
    body = feat.bodies.item(0)
    body.name = "Cooper_Bowl_Base"
    return body


def build_top_ring(component):
    """Top ring: conical self-centring seat, rim pocket, and the pin holes."""
    h = P["stand_height"]
    z0 = P["top_bottom"]
    r_out = P["stand_od"] * 0.5
    seat_r = cfg.BOWL_SEAT_D * 0.5
    bore_r = cfg.BOWL_OPENING_D * 0.5
    seat_z = h - cfg.BOWL_RIM_RECESS

    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_top_ring")
    polyline(sketch, [
        (bore_r, z0),
        (r_out, z0),
        (r_out, h),
        (seat_r, h),
        (seat_r, seat_z),
    ])
    feat = revolve(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0, name="Top seat ring",
    )
    ring = feat.bodies.item(0)
    ring.name = "Cooper_Top_Seat_Ring"

    hole = _pin_body(component, P["top_joint_hole_radius"],
                     P["top_joint_pin_height"] + 0.4, z0 - 0.2,
                     "ogma_pin_hole")
    pattern = circular_pattern(
        component, [hole], component.zConstructionAxis,
        quantity=int(P["top_joint_pin_count"]), total_angle_deg=360.0,
        name="Pin holes",
    )
    tools = [hole] + _pattern_bodies(pattern)
    cut(component, ring, tools, "Drill pin holes")
    return ring


def build_panel(component, ctx):
    """Shell + tongue + paw pads + name plaque + alignment pins."""
    r_in, r_out = P["wall_inner_r"], P["wall_outer_r"]
    z0 = P["base_height"] - 3.0
    z1 = P["lattice_top"]

    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_panel_shell")
    polyline(sketch, [(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1)])
    feat = revolve(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0, name="Panel shell",
    )
    panel = feat.bodies.item(0)
    panel.name = "Cooper_Paw_Panel"

    _cut_paws(component, panel, ctx)
    _add_plaque(component, panel, ctx)

    pin = _pin_body(component, P["top_joint_pin_radius"],
                    P["top_joint_pin_height"] + 0.5, z1 - 0.5, "ogma_pin")
    pattern = circular_pattern(
        component, [pin], component.zConstructionAxis,
        quantity=int(P["top_joint_pin_count"]), total_angle_deg=360.0,
        name="Alignment pins",
    )
    join(component, panel, [pin] + _pattern_bodies(pattern), "Add pins")
    return panel


# --------------------------------------------------------------------------
# Paws
# --------------------------------------------------------------------------

def _ellipse_points(cu, cz, major, minor, tilt_deg, samples=32):
    """A tilted ellipse as a closed point loop in (u, z) sketch space."""
    tilt = math.radians(tilt_deg)
    cos_t, sin_t = math.cos(tilt), math.sin(tilt)
    points = []
    for k in range(samples):
        angle = 2.0 * math.pi * k / samples
        a = major * math.cos(angle)
        b = minor * math.sin(angle)
        points.append((cu + a * cos_t - b * sin_t, cz + a * sin_t + b * cos_t))
    return points


def _paw_sketch(component, plane, row_z, tag):
    """One paw: seven tilted ellipses in a single sketch."""
    sketch = sketch_on(component, plane, "ogma_paw_{}".format(tag))
    splines = sketch.sketchCurves.sketchFittedSplines
    for du, dz, tangent_r, vertical_r, tilt in cfg.PAW_LOBES:
        loop = _ellipse_points(du, row_z + dz, tangent_r, vertical_r, tilt)
        pts = collection([pt(u, z, 0.0) for (u, z) in loop])
        spline = splines.add(pts)
        try:
            spline.isClosed = True
        except Exception:
            # Older builds close the loop implicitly when the first and last
            # fit points coincide; the explicit flag is the belt.
            pass
    return sketch


def _cut_paws(component, panel, ctx):
    r_out = P["wall_outer_r"]
    depth = P["paw_recess_depth"]
    plane = offset_plane(
        component, component.xZConstructionPlane, -(r_out + 0.45),
        "ogma_paw_plane",
    )
    rail_half = ctx.get("rail_outer_deg", 32.0) + P["paw_rail_clear_deg"]
    step = 360.0 / P["paw_count"]

    for row_index, row_z in enumerate(P["paw_rows"]):
        tag = "row{}".format(row_index + 1)
        sketch = _paw_sketch(component, plane, row_z, tag)
        profiles = collection([
            sketch.profiles.item(i) for i in range(sketch.profiles.count)
        ])
        if profiles.count == 0:
            continue
        feat = extrude(
            component, profiles,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            distance_mm=depth + 0.45,
            taper_deg=-12.0,
            name="Paw {}".format(tag),
        )
        seeds = [feat.bodies.item(i) for i in range(feat.bodies.count)]
        offset_deg = (row_index % 2) * step * 0.5
        if offset_deg:
            for body in seeds:
                _rotate(component, body, offset_deg)
        pattern = circular_pattern(
            component, seeds, component.zConstructionAxis,
            quantity=int(P["paw_count"]), total_angle_deg=360.0,
            name="Paw ring {}".format(tag),
        )
        suppress = []
        for i in range(int(P["paw_count"])):
            theta = (offset_deg + i * step + 180.0) % 360.0 - 180.0
            if abs(theta) < rail_half:
                suppress.append(i)
        if suppress:
            suppress_pattern_elements(
                component.parentDesign, pattern, suppress
            )
        tools = seeds + _pattern_bodies(pattern)
        cut(component, panel, tools, "Recess paws {}".format(tag))


# --------------------------------------------------------------------------
# Name plaque
# --------------------------------------------------------------------------

def _add_plaque(component, panel, ctx):
    """Raised name rail with long Z blends top and bottom.

    The generator eases the plaque out of the wall with a smoothstep over
    ~10 mm of Z, because a square ledge changes the layer cross-section in one
    step and prints as a bright ring right round the cylinder. The trapezoid
    below is the straight-sided equivalent and keeps that ease-in.

    The angular ends are square rather than blended — the generator's angular
    ease is only 1.5 deg. Add a fillet on the two vertical edges if you want it
    softened; see EDITING.md.
    """
    half_deg = ctx.get("rail_flat_deg", 30.5)
    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_plaque")
    polyline(sketch, [
        (P["name_rail_inner_r"], P["name_rail_blend_z_lo"]),
        (P["name_rail_outer_r"], P["name_rail_z0"]),
        (P["name_rail_outer_r"], P["name_rail_z1"]),
        (P["name_rail_inner_r"], P["name_rail_blend_z_hi"]),
    ])
    feat = revolve_symmetric(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        half_angle_deg=half_deg, name="Name plaque",
    )
    plaque = feat.bodies.item(0)
    plaque.name = "ogma_plaque"
    join(component, panel, [plaque], "Add name plaque")
    return plaque


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _pin_body(component, radius_mm, height_mm, z_mm, name):
    sketch = sketch_on(component, component.xYConstructionPlane, name)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        pt(0.0, -P["top_joint_radius"], 0.0), cm(radius_mm)
    )
    feat = extrude(
        component, largest_profile(sketch),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        distance_mm=height_mm, name=name,
    )
    body = feat.bodies.item(0)
    body.name = name
    _lift(component, body, z_mm)
    return body


def _pattern_bodies(pattern_feature):
    out = []
    try:
        for i in range(pattern_feature.bodies.count):
            out.append(pattern_feature.bodies.item(i))
    except Exception:
        pass
    return out


def _rotate(component, body, angle_deg):
    matrix = adsk.core.Matrix3D.create()
    matrix.setToRotation(
        math.radians(angle_deg),
        adsk.core.Vector3D.create(0, 0, 1),
        adsk.core.Point3D.create(0, 0, 0),
    )
    moves = component.features.moveFeatures
    inp = moves.createInput2(collection([body]))
    inp.defineAsFreeMove(matrix)
    return moves.add(inp)


def _lift(component, body, z_mm):
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(0, 0, cm(z_mm))
    moves = component.features.moveFeatures
    inp = moves.createInput2(collection([body]))
    inp.defineAsFreeMove(matrix)
    return moves.add(inp)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def build(component, ctx):
    base = build_base(component)
    panel = build_panel(component, ctx)
    ring = build_top_ring(component)
    return {
        "body": panel,
        "wall_radius": P["name_rail_outer_r"],
        "letter_center_z": P["letter_center_z"],
        "keepout_margin": 0.0,
        "keepout_fill_depth": 0.0,
        "parts": [base, panel, ring],
        "notes": [
            "Four plates: base, paw panel, top seat ring, letters.",
            "Paw pads are {:.1f} mm recesses, not through-holes — through-holes "
            "break every perimeter loop and band the wall.".format(
                P["paw_recess_depth"]),
        ],
    }
