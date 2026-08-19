"""User Parameters — the editable control surface of every generated model.

Everything a builder measures comes from here, and every entry becomes a row in
Fusion's Modify > Change Parameters dialog. That is the whole point of the
exercise: a dimension that is baked into a Point3D is dead, a dimension that is
a named parameter is something you can type a new number into and watch the
model rebuild.

Naming convention is `ogma<Area><Thing>` so the whole set sorts together in the
parameters dialog and cannot collide with anything you add by hand.

The `SHARED`/`HEX`/... tables below are (name, expression, unit, comment). The
expression is a string, so it may reference another parameter — which is how
the derived values stay derived rather than being frozen numbers.
"""

from __future__ import annotations

from . import config as cfg
from .api import add_parameter
from .units import mm


def _mm(value: float) -> str:
    return mm(value)


# --------------------------------------------------------------------------
# Shared — created for every style.
# --------------------------------------------------------------------------

SHARED = (
    ("ogmaStandHeight", _mm(cfg.STAND_HEIGHT), "mm",
     "Overall stand height. Drives the bowl seat height with it."),
    ("ogmaStandOD", _mm(cfg.STAND_OD), "mm",
     "Outer envelope diameter. Cooper base and top ring use this directly."),
    ("ogmaWallOuterR", _mm(cfg.WALL_OUTER_R), "mm",
     "Outer wall radius of the drum / lattice shell."),
    ("ogmaWallInnerR", _mm(cfg.WALL_INNER_R), "mm",
     "Inner wall radius. Wall thickness = ogmaWallOuterR - ogmaWallInnerR."),

    ("ogmaBowlSeatD", _mm(cfg.BOWL_SEAT_D), "mm",
     "Diameter the metal bowl rim lands on. Locked to the Cooper insert."),
    ("ogmaBowlOpeningD", _mm(cfg.BOWL_OPENING_D), "mm",
     "Through-bore under the bowl. Locked to the Cooper insert."),
    ("ogmaBowlRimRecess", _mm(cfg.BOWL_RIM_RECESS), "mm",
     "How far the bowl rim sits below the top edge, so the bowl nests."),
    ("ogmaSeatZ", "ogmaStandHeight - ogmaBowlRimRecess", "mm",
     "Derived: height of the bowl-rim landing."),

    ("ogmaLetterHeight", _mm(cfg.LETTER_HEIGHT), "mm",
     "Cap height of the name letters."),
    ("ogmaLetterThickness", _mm(cfg.LETTER_THICKNESS), "mm",
     "How far a letter stands proud of the wall once seated."),
    ("ogmaLetterPocketDepth", _mm(cfg.LETTER_POCKET_DEPTH), "mm",
     "Depth of the glyph pocket cut into the wall."),
    ("ogmaLetterPocketClearance", _mm(cfg.LETTER_POCKET_CLEARANCE), "mm",
     "Per-side slop between letter and pocket. Raise if letters bind."),
    ("ogmaLetterGap", _mm(cfg.LETTER_GAP), "mm",
     "Clear tangential gap between adjacent letters."),
    ("ogmaLetterEndMargin", _mm(cfg.LETTER_END_MARGIN), "mm",
     "Clear space from the outer letters to the end of the name field."),
)


HEX = (
    ("ogmaHexGrooveDepth", _mm(cfg.HEX["groove_depth"]), "mm",
     "How deep the honeycomb grooves cut. Web left = wall - this."),
    ("ogmaHexGrooveGap", _mm(cfg.HEX["groove_gap"]), "mm",
     "Width of the groove between two proud hex tiles."),
    ("ogmaHexGrooveChamfer", _mm(cfg.HEX["groove_chamfer"]), "mm",
     "Chamfer run on the groove wall; softens the tile edge."),
    ("ogmaHexCellRadius", _mm(cfg.HEX["target_cell_radius"]), "mm",
     "Target hex cell radius. Column count is derived from it and quantised, "
     "so small edits here may not change the pattern at all."),
    ("ogmaHexEdgeBand", _mm(cfg.HEX["pattern_edge_band"]), "mm",
     "Pattern-free band at the top and bottom of the drum."),
    ("ogmaHexNameMargin", _mm(cfg.HEX["name_keepout_margin"]), "mm",
     "Margin around the packed name where the honeycomb is suppressed."),
    ("ogmaHexTopBead", _mm(cfg.HEX["top_edge_bead"]), "mm",
     "Radial bead on the very top edge."),
    ("ogmaHexBottomChamfer", _mm(cfg.HEX["bottom_edge_chamfer"]), "mm",
     "Inward chamfer at the bed-facing bottom edge."),
    ("ogmaHexSupportStartZ", _mm(cfg.HEX["support_start_z"]), "mm",
     "Where the internal seat ramp begins. Lower = shallower overhang."),
    ("ogmaHexLetterCenterZ", _mm(cfg.HEX["letter_center_z"]), "mm",
     "Optical centre height of the name on the staggered cell field."),
)


FLUTED = (
    ("ogmaFluteCount", str(cfg.FLUTED["flute_count"]), "",
     "Number of vertical flutes around the drum."),
    ("ogmaFluteDepth", _mm(cfg.FLUTED["flute_depth"]), "mm",
     "How deep each flute cuts inward. Web left = wall - this."),
    ("ogmaFluteMinWeb", _mm(cfg.FLUTED["min_web"]), "mm",
     "Minimum acceptable remaining wall. The builder refuses to go below it."),
    ("ogmaFlutedEdgeBand", _mm(cfg.FLUTED["pattern_edge_band"]), "mm",
     "Flute-free band at the top and bottom of the drum."),
    ("ogmaFlutedNameMargin", _mm(cfg.FLUTED["name_keepout_margin"]), "mm",
     "Margin around the name where the wall stays flat for the pockets."),
    ("ogmaFlutedNameFade", _mm(cfg.FLUTED["name_fade"]), "mm",
     "Distance over which flutes ramp back in beside the name."),
    ("ogmaFlutedSupportStartZ", _mm(cfg.FLUTED["support_start_z"]), "mm",
     "Where the internal seat ramp begins."),
    ("ogmaFlutedLetterCenterZ", _mm(cfg.FLUTED["letter_center_z"]), "mm",
     "Centre height of the name — true drum midpoint on this style."),
)


COOPER = (
    ("ogmaCooperBaseHeight", _mm(cfg.COOPER["base_height"]), "mm",
     "Height of the separate printed base."),
    ("ogmaCooperBaseInnerR", _mm(cfg.COOPER["base_inner_r"]), "mm",
     "Inner radius of the base annulus."),
    ("ogmaCooperLatticeBottom", _mm(cfg.COOPER["lattice_bottom"]), "mm",
     "Where the visible paw panel starts."),
    ("ogmaCooperLatticeTop", _mm(cfg.COOPER["lattice_top"]), "mm",
     "Where the paw panel ends and the top ring begins."),
    ("ogmaPawRecessDepth", _mm(cfg.COOPER["paw_recess_depth"]), "mm",
     "How deep the paw pads are recessed. Shallow on purpose: deeper pads "
     "swing the per-layer extrusion time and show as banding."),
    ("ogmaPawCount", str(cfg.COOPER["paw_count"]), "",
     "Paws per row around the drum, before the name-rail keepout."),
    ("ogmaPawRow1Z", _mm(cfg.COOPER["paw_rows"][0]), "mm", "Height of paw row 1."),
    ("ogmaPawRow2Z", _mm(cfg.COOPER["paw_rows"][1]), "mm", "Height of paw row 2."),
    ("ogmaPawRow3Z", _mm(cfg.COOPER["paw_rows"][2]), "mm", "Height of paw row 3."),
    ("ogmaRailOuterR", _mm(cfg.COOPER["name_rail_outer_r"]), "mm",
     "Outer radius of the name-rail plaque face."),
    ("ogmaRailInnerR", _mm(cfg.COOPER["name_rail_inner_r"]), "mm",
     "Inner radius of the plaque; it roots inside the wall."),
    ("ogmaRailZ0", _mm(cfg.COOPER["name_rail_z0"]), "mm", "Plaque flat face bottom."),
    ("ogmaRailZ1", _mm(cfg.COOPER["name_rail_z1"]), "mm", "Plaque flat face top."),
    ("ogmaCooperLetterCenterZ", _mm(cfg.COOPER["letter_center_z"]), "mm",
     "Centre height of the name on the plaque."),
    ("ogmaPinCount", str(cfg.COOPER["top_joint_pin_count"]), "",
     "Alignment pins between panel and top ring."),
    ("ogmaPinRadius", _mm(cfg.COOPER["top_joint_pin_radius"]), "mm", "Pin radius."),
    ("ogmaPinHoleRadius", _mm(cfg.COOPER["top_joint_hole_radius"]), "mm",
     "Matching hole radius. Difference from ogmaPinRadius is the fit clearance."),
    ("ogmaPinCircleR", _mm(cfg.COOPER["top_joint_radius"]), "mm",
     "Bolt-circle radius the pins sit on."),
    ("ogmaPinHeight", _mm(cfg.COOPER["top_joint_pin_height"]), "mm", "Pin length."),
)


WAVE = (
    ("ogmaWaveAmp", _mm(cfg.WAVE["amp"]), "mm",
     "Sine seam amplitude — half the peak-to-trough height."),
    ("ogmaWaveCount", str(cfg.WAVE["waves"]), "",
     "Number of full sine periods around the stand."),
    ("ogmaWaveSeamPercent", str(cfg.WAVE["seam_p"]), "",
     "Seam mid-height as a percent of stand height."),
    ("ogmaWaveTopR", _mm(cfg.WAVE["rt_out"]), "mm", "Outer radius at the top."),
    ("ogmaWaveBottomR", _mm(cfg.WAVE["rb_out"]), "mm", "Outer radius at the bed."),
    ("ogmaWaveWallThick", _mm(cfg.WAVE["wall_thick"]), "mm", "Lower-half wall."),
    ("ogmaWaveMinUpperWall", _mm(cfg.WAVE["min_upper_wall"]), "mm",
     "Minimum upper-shell wall through the lettering zone."),
    ("ogmaWaveCollarR", _mm(cfg.WAVE["collar_outer_r"]), "mm",
     "Collar outer radius. Print-proven at 74 mm against a 74.5 mm receiver."),
    ("ogmaWaveCollarClearance", _mm(cfg.WAVE["collar_clearance"]), "mm",
     "Per-side sleeve clearance. 0.5 mm passed physically on the P2S; "
     "tightening this is the first thing to check if halves won't seat."),
    ("ogmaWaveSeamGap", _mm(cfg.WAVE["seam_gap"]), "mm",
     "How far the lower half stops below the true sine seam."),
    ("ogmaWaveShadowChamfer", _mm(cfg.WAVE["shadow_chamfer"]), "mm",
     "Chamfer at the seam that reads as a shadow line."),
    ("ogmaWaveSeatClearance", _mm(cfg.WAVE["seat_insert_clearance"]), "mm",
     "Clearance between seat insert locator and shell bore."),
    ("ogmaWaveLetterCenterZ", _mm(cfg.WAVE["letter_center_z"]), "mm",
     "Centre height of the name on the large low-seam lobe."),
)


STYLE_TABLES = {
    "hex": HEX,
    "fluted": FLUTED,
    "cooper": COOPER,
    "wave": WAVE,
}


def create(design, style_id: str) -> dict:
    """Create the shared + per-style parameters. Returns {name: UserParameter}."""
    made = {}
    for name, expression, unit, comment in SHARED + STYLE_TABLES[style_id]:
        made[name] = add_parameter(design, name, expression, unit, comment)
    return made


def value_mm(design, name: str) -> float:
    """Read a length parameter back, in millimetres.

    Parameter.value is in database units (cm), so this is the only correct way
    to get a number out that you can compare against config.py.
    """
    param = design.userParameters.itemByName(name)
    if param is None:
        raise KeyError("user parameter '{}' does not exist".format(name))
    return param.value * 10.0


def value_raw(design, name: str) -> float:
    """Read a unitless parameter (counts, percentages) back as a plain float."""
    param = design.userParameters.itemByName(name)
    if param is None:
        raise KeyError("user parameter '{}' does not exist".format(name))
    return param.value
