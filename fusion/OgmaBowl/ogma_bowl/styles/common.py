"""Geometry shared by the two drum styles (honeycomb and fluted).

Both are the same solid of revolution — same envelope, same Cooper seat, same
edge treatment — and differ only in what gets cut into the wall afterwards.
That is exactly the split the Python style registry makes, so it is the split
kept here.
"""

from __future__ import annotations

import adsk.fusion

from .. import config as cfg
from ..api import largest_profile, polyline, revolve, sketch_on


def drum_profile(p) -> list:
    """Closed (radius, height) polyline for a honeycomb/fluted drum.

    Traced bottom-outside, up the wall, over the top, then down the inside:

        bottom chamfer -> wall -> lower border ring -> wall -> upper border
        ring -> wall -> top bead -> top inner edge -> bowl rim shelf ->
        conical bowl seat -> support ramp -> inner wall -> back to the start

    The two border rings and both edge treatments are axisymmetric in the
    generator (`_pattern_border_offset` is a function of z alone), so they
    belong in the revolve profile rather than in a separate feature. Only the
    honeycomb and flute textures actually vary with theta.
    """
    h = p["h"]
    rb, rt = p["rb_out"], p["rt_out"]
    band = p["pattern_edge_band"]
    half_border = p["pattern_border_width"] * 0.5
    border_d = p["pattern_border_depth"]
    seat_r = cfg.BOWL_SEAT_D * 0.5
    bore_r = cfg.BOWL_OPENING_D * 0.5
    seat_z = h - cfg.BOWL_RIM_RECESS

    return [
        # outer wall, bottom to top
        (rb - p["bottom_edge_chamfer"], 0.0),
        (rb, p["bottom_edge_height"]),
        (rb, band - half_border),
        (rb - border_d, band),
        (rb, band + half_border),
        (rt, h - band - half_border),
        (rt - border_d, h - band),
        (rt, h - band + half_border),
        (rt, h - p["top_edge_height"]),
        (rt + p["top_edge_bead"], h),
        # inner, top to bottom
        (seat_r, h),
        (seat_r, seat_z),
        (bore_r, seat_z - (seat_r - bore_r)),
        (p["wall_inner_r"], p["support_start_z"]),
        (p["wall_inner_r"], 0.0),
    ]


def build_drum(component, p, name: str = "Drum"):
    """Revolve the drum and return its BRepBody."""
    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_drum_profile")
    polyline(sketch, drum_profile(p))
    feat = revolve(
        component,
        largest_profile(sketch),
        component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0,
        name=name,
    )
    body = feat.bodies.item(0)
    body.name = name
    return body


def annulus_body(component, component_name, r_inner, r_outer, z0, z1,
                 angle_deg: float = 360.0):
    """A revolved annular band — used as a boolean tool."""
    sketch = sketch_on(component, component.xZConstructionPlane, component_name)
    polyline(sketch, [
        (r_inner, z0), (r_outer, z0), (r_outer, z1), (r_inner, z1),
    ])
    feat = revolve(
        component,
        largest_profile(sketch),
        component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=angle_deg,
        name=component_name,
    )
    body = feat.bodies.item(0)
    body.name = component_name
    return body


def sagitta(radius_mm: float, chord_mm: float) -> float:
    """How far a flat chord of `chord_mm` falls inside a circle of `radius_mm`.

    A tile sketched on a tangent plane is flat; the drum is not. This is the
    gap that opens at the tile's edges, and it is why the tile bodies are grown
    slightly proud and then trimmed back to the true cylinder.
    """
    import math

    half = chord_mm * 0.5
    if half >= radius_mm:
        return 0.0
    return radius_mm - math.sqrt(radius_mm * radius_mm - half * half)
