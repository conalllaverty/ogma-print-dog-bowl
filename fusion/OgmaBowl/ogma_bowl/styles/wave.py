"""Wave — a three-piece stand split on a sine seam.

Lower half, upper shell, and a bowl seat insert that prints inverted on its own
flange. The two halves join on a 0.5 mm/side collar sleeve that was proven
physically on the P2S on 2026-07-23; that clearance is the one number in this
file that should not be touched without reprinting a coupon.

The sine seam
-------------
Everything except the seam is a solid of revolution, so the build is: revolve
each half past the seam, then split with the seam surface and keep the piece
you want.

The seam surface is lofted between two closed 3-D splines that share the same
z(theta) = seam_y - amp * cos(waves * (theta - pi/2)) and differ only in
radius, which makes the loft a ruled surface — radially straight, following the
sine exactly. That is the one piece of geometry here that is sampled rather
than equation-driven: change `ogmaWaveAmp` or `ogmaWaveCount` and the splines
need regenerating, which means re-running the command rather than editing a
parameter in place. Every other dimension on this style is live.

If the loft fails on your build, `SEAM_FALLBACK` produces a flat seam instead
and reports it, so you still get a usable pair of halves.
"""

from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from .. import config as cfg
from ..api import (
    collection,
    fitted_spline,
    largest_profile,
    loft_surface,
    polyline,
    revolve,
    sketch_on,
    split_body,
)

STYLE_ID = "wave"
LABEL = cfg.STYLE_LABELS["wave"]
OUTPUT_SUFFIX = "Wave"

P = cfg.WAVE
D = cfg.wave_derived()

SEAM_SAMPLES = 96
SEAM_INNER_R = 30.0
SEAM_OUTER_R = 130.0


def _ro(z: float) -> float:
    """Outer radius at height z — a straight taper from bed to rim."""
    return P["rb_out"] + (P["rt_out"] - P["rb_out"]) * (z / P["h"])


def _seam_z(theta_rad: float, offset: float = 0.0) -> float:
    return (
        D["seam_y"]
        - P["amp"] * math.cos(P["waves"] * (theta_rad - math.pi / 2.0))
        + offset
    )


def _upper_dimensions():
    """Shell / seat-insert interface, with the generator's own guard rails."""
    seat_z = D["seat_z"]
    seat_r = cfg.BOWL_SEAT_D / 2.0
    bore_r = cfg.BOWL_OPENING_D / 2.0
    shell_top_outer_r = _ro(seat_z)
    shell_top_inner_r = shell_top_outer_r - P["min_upper_wall"]
    u = {
        "seat_z": seat_z,
        "seat_r": seat_r,
        "bore_r": bore_r,
        "support_z": seat_z - (seat_r - bore_r),
        "shell_top_z": seat_z,
        "shell_top_outer_r": shell_top_outer_r,
        "shell_top_inner_r": shell_top_inner_r,
        "insert_locator_outer_r": shell_top_inner_r - P["seat_insert_clearance"],
        "insert_flange_outer_r": shell_top_outer_r - P["seat_flange_edge_inset"],
        "sleeve_inner": D["rc"] + P["collar_clearance"],
        "sleeve_top_z": D["y2"] + 1.0,
        "support_bridge_z": D["y2"] + 6.0,
    }
    u["support_bridge_r"] = _ro(u["support_bridge_z"]) - P["min_upper_wall"]

    if u["insert_locator_outer_r"] <= seat_r:
        raise ValueError("Wave seat insert has no outer locating flange.")
    if u["insert_flange_outer_r"] <= shell_top_inner_r:
        raise ValueError("Wave seat flange does not overlap the shell rim.")
    if u["insert_flange_outer_r"] >= shell_top_outer_r:
        raise ValueError("Wave seat flange must stay inside the exterior rim.")
    if u["sleeve_inner"] >= _ro(u["sleeve_top_z"]) - P["min_upper_wall"]:
        raise ValueError("Wave receiver wall violates the upper wall envelope.")
    if u["support_bridge_r"] <= bore_r or u["support_bridge_r"] >= _ro(
            u["support_bridge_z"]):
        raise ValueError("Wave support bridge violates the upper wall envelope.")
    return u


# --------------------------------------------------------------------------
# Seam surface
# --------------------------------------------------------------------------

def _seam_spline(component, radius_mm, offset_mm, tag):
    sketch = sketch_on(component, component.xYConstructionPlane,
                       "ogma_seam_{}".format(tag))
    points = []
    for k in range(SEAM_SAMPLES + 1):
        theta = 2.0 * math.pi * k / SEAM_SAMPLES
        points.append((
            radius_mm * math.sin(theta),
            -radius_mm * math.cos(theta),
            _seam_z(theta, offset_mm),
        ))
    spline = fitted_spline(sketch, points)
    try:
        spline.isClosed = True
    except Exception:
        pass
    return spline


def build_seam_surface(component, offset_mm, tag):
    """Ruled surface through the sine seam. Returns a BRepFace, or None."""
    try:
        inner = _seam_spline(component, SEAM_INNER_R, offset_mm, tag + "_in")
        outer = _seam_spline(component, SEAM_OUTER_R, offset_mm, tag + "_out")
        feat = loft_surface(component, [inner, outer],
                            "Seam surface {}".format(tag))
        for i in range(feat.bodies.count):
            body = feat.bodies.item(i)
            if body.faces.count:
                return body
    except Exception:
        return None
    return None


# --------------------------------------------------------------------------
# Halves
# --------------------------------------------------------------------------

def build_lower(component):
    """Wall, floor and hollow collar as one revolve, cut back at the seam."""
    channel_z = 0.5 * (3.0 + D["y2"])
    rc = D["rc"]
    top = D["s_max"] + 6.0

    profile = [
        (P["rb_out"], 0.0),
        (_ro(top), top),
        (_ro(top) - P["wall_thick"], top),
    ]
    inner_top = _ro(top) - P["wall_thick"]
    profile += [
        (inner_top, top),
        (_ro(3.0) - P["wall_thick"], 3.0),
        (rc, 3.0),
        (rc, channel_z - 1.0),
        (rc - 0.8, channel_z - 1.0),
        (rc - 0.8, channel_z + 1.0),
        (rc, channel_z + 1.8),
        (rc, D["y2"] - 1.2),
        (rc - 1.2, D["y2"]),
        (rc - 2.4, D["y2"]),
        (rc - 2.4, 0.0),
    ]
    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_wave_lower")
    polyline(sketch, profile)
    feat = revolve(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0, name="Wave lower",
    )
    body = feat.bodies.item(0)
    body.name = "Wave_Lower"
    return body


def build_upper(component):
    """Cosmetic shell with the receiver bore; open at the top."""
    u = _upper_dimensions()
    bottom = D["s_min"] - 6.0

    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_wave_upper")
    polyline(sketch, [
        (_ro(bottom), bottom),
        (_ro(u["shell_top_z"]), u["shell_top_z"]),
        (u["shell_top_inner_r"], u["shell_top_z"]),
        (u["support_bridge_r"], u["support_bridge_z"]),
        (u["sleeve_inner"], u["sleeve_top_z"]),
        (u["sleeve_inner"], bottom),
    ])
    feat = revolve(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0, name="Wave upper",
    )
    body = feat.bodies.item(0)
    body.name = "Wave_Upper"
    return body


def build_seat_insert(component):
    """Top-hanging bowl seat; prints inverted on its own broad flange."""
    u = _upper_dimensions()
    sketch = sketch_on(component, component.xZConstructionPlane, "ogma_wave_seat")
    polyline(sketch, [
        (u["insert_locator_outer_r"], u["support_z"]),
        (u["insert_locator_outer_r"], u["seat_z"]),
        (u["insert_flange_outer_r"], u["seat_z"]),
        (u["insert_flange_outer_r"], P["h"]),
        (u["seat_r"], P["h"]),
        (u["seat_r"], u["seat_z"]),
        (u["bore_r"], u["support_z"]),
    ])
    feat = revolve(
        component, largest_profile(sketch), component.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0, name="Wave seat insert",
    )
    body = feat.bodies.item(0)
    body.name = "Wave_Bowl_Seat_Insert"
    return body


def _keep_side(component, split_feature, keep_lower: bool, name: str):
    """Keep the piece on one side of the seam, delete the rest."""
    kept = None
    survivors = []
    for i in range(split_feature.bodies.count):
        survivors.append(split_feature.bodies.item(i))
    if not survivors:
        return None
    scored = []
    for body in survivors:
        bbox = body.boundingBox
        scored.append(((bbox.minPoint.z + bbox.maxPoint.z) * 0.5, body))
    scored.sort(key=lambda item: item[0])
    kept = scored[0][1] if keep_lower else scored[-1][1]
    for _z, body in scored:
        if body is not kept:
            try:
                body.deleteMe()
            except Exception:
                pass
    kept.name = name
    return kept


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def build(component, ctx):
    notes = []
    lower = build_lower(component)
    upper = build_upper(component)
    seat = build_seat_insert(component)

    lower_seam = build_seam_surface(component, -P["seam_gap"], "lower")
    upper_seam = build_seam_surface(component, 0.0, "upper")

    if lower_seam and upper_seam:
        feat = split_body(component, [lower], lower_seam.faces.item(0), True,
                          "Split lower at seam")
        lower = _keep_side(component, feat, True, "Wave_Lower") or lower
        feat = split_body(component, [upper], upper_seam.faces.item(0), True,
                          "Split upper at seam")
        upper = _keep_side(component, feat, False, "Wave_Upper") or upper
        for surface in (lower_seam, upper_seam):
            try:
                surface.deleteMe()
            except Exception:
                pass
        notes.append(
            "Sine seam: {} periods, {:.1f} mm amplitude, sampled at {} points "
            "and lofted as a ruled surface. Changing the amplitude or period "
            "needs the command re-run, not just a parameter edit.".format(
                int(P["waves"]), P["amp"], SEAM_SAMPLES)
        )
    else:
        notes.append(
            "SEAM FALLBACK: the ruled loft through the sine splines failed on "
            "this build, so the halves are left un-split. Run 'Split Body' by "
            "hand, or re-run the command — see EDITING.md, Wave section."
        )

    notes.append(
        "Collar sleeve clearance is {:.1f} mm per side at R{:.1f} against a "
        "R{:.1f} receiver. That pair passed physically on the P2S; re-coupon "
        "before changing it.".format(
            P["collar_clearance"], D["rc"], D["rc"] + P["collar_clearance"])
    )

    return {
        "body": upper,
        "wall_radius": _ro(P["letter_center_z"]),
        "letter_center_z": P["letter_center_z"],
        "keepout_margin": 0.0,
        "keepout_fill_depth": 0.0,
        "parts": [lower, upper, seat],
        "notes": notes,
    }
