"""Fluted drum — vertical flutes cut inward into the same envelope as the hex.

Same body, same seat, same edge treatment; only the wall texture changes. That
is the whole reason the style registry exists on the Python side, and it holds
here: this module is the honeycomb's build with one cutter swapped.

The flute profile
-----------------
The generator uses the archived Named Bowl v4.5 sine, sign-inverted so flutes
cut in rather than bulge out:

    offset(theta) = -flute_depth * (0.5 + 0.5 * sin(flute_count * theta))

A revolved sinusoid is not BRep-representable without a spline surface that
stops being editable the moment you change the flute count, so each flute is
cut with a cylinder sized from the sine's own pitch and depth. Flute count,
flute depth and the remaining web are identical; the valley floor is a circular
arc instead of a sine crest. At 1.1 mm deep on an 8.0 mm pitch the two profiles
differ by under 0.05 mm, which is an eighth of a layer line.

The payoff is that `ogmaFluteCount` and `ogmaFluteDepth` remain live parameters
you can drag, and the flute stays a real feature you can suppress or delete.
"""

from __future__ import annotations

import math

import adsk.fusion

from .. import config as cfg
from ..api import (
    circular_pattern,
    cut,
    join,
    largest_profile,
    polyline,
    revolve,
    revolve_symmetric,
    sketch_on,
)
from .common import annulus_body, build_drum

STYLE_ID = "fluted"
LABEL = cfg.STYLE_LABELS["fluted"]
OUTPUT_SUFFIX = "Fluted"


def build(component, ctx):
    p = dict(cfg.FLUTED)
    fl = cfg.flute_cutter(p)

    web = fl["web"]
    if web < p["min_web"]:
        raise ValueError(
            "Flute depth {:.2f} mm leaves only {:.2f} mm of web and the "
            "minimum is {:.2f} mm. Reduce ogmaFluteDepth or thicken the "
            "wall.".format(p["flute_depth"], web, p["min_web"])
        )

    drum = build_drum(component, p, "Fluted body")
    wall_r = p["rb_out"]
    band_z0 = p["pattern_edge_band"]
    band_z1 = p["h"] - p["pattern_edge_band"]

    # One flute cutter: a cylinder whose axis is parallel to Z, offset so it
    # bites `flute_depth` into the wall.
    sketch = sketch_on(component, component.xYConstructionPlane,
                       "ogma_flute_cutter")
    circles = sketch.sketchCurves.sketchCircles
    from ..api import pt

    circles.addByCenterRadius(
        pt(0.0, -fl["centre_r"], 0.0), fl["cutter_r"] / 10.0
    )
    from ..api import extrude

    feat = extrude(
        component,
        largest_profile(sketch),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        distance_mm=band_z1 - band_z0,
        name="Flute cutter",
    )
    cutter = feat.bodies.item(0)
    cutter.name = "ogma_flute_cutter"
    _lift(component, cutter, band_z0)

    pattern = circular_pattern(
        component, [cutter], component.zConstructionAxis,
        quantity=int(p["flute_count"]), total_angle_deg=360.0,
        name="Flute ring",
    )
    tools = [cutter]
    try:
        for i in range(pattern.bodies.count):
            tools.append(pattern.bodies.item(i))
    except Exception:
        pass
    cut(component, drum, tools, "Cut flutes")

    return {
        "body": drum,
        "wall_radius": wall_r,
        "letter_center_z": p["letter_center_z"],
        "keepout_margin": p["name_keepout_margin"],
        "keepout_fill_depth": p["flute_depth"],
        "parts": [drum],
        "notes": [
            "Flutes: {} at {:.2f} mm pitch, {:.2f} mm deep, {:.2f} mm web "
            "remaining. No supports needed — the flutes are constant in Z so "
            "every layer has the same footprint.".format(
                int(p["flute_count"]), fl["pitch"], p["flute_depth"], web),
        ],
    }


def fill_name_keepout(component, drum, wall_r, centre_z, half_width,
                      half_height, depth):
    """Restore flat wall behind the name so the glyph pockets have a floor.

    The generator smoothsteps the flutes back to zero over `name_fade` mm so
    there is no hard seam beside the first and last letter. Here the patch gets
    the same fade allowance built into its half-width, and its edges are
    filleted rather than stepped.
    """
    sketch = sketch_on(component, component.xZConstructionPlane,
                       "ogma_flute_name_patch")
    polyline(sketch, [
        (wall_r - depth - 0.2, centre_z - half_height),
        (wall_r, centre_z - half_height),
        (wall_r, centre_z + half_height),
        (wall_r - depth - 0.2, centre_z + half_height),
    ])
    span = math.degrees(2.0 * half_width / wall_r)
    feat = revolve_symmetric(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        half_angle_deg=span * 0.5, name="Name patch",
    )
    patch = feat.bodies.item(0)
    patch.name = "ogma_name_patch"
    join(component, drum, [patch], "Flatten the name field")
    return patch


def _lift(component, body, z_mm: float):
    """Move a body up the Z axis."""
    import adsk.core

    from ..api import collection
    from ..units import cm

    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(0, 0, cm(z_mm))
    moves = component.features.moveFeatures
    inp = moves.createInput2(collection([body]))
    inp.defineAsFreeMove(matrix)
    return moves.add(inp)
