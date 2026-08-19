"""Geometry constants — mirror of products/dog-bowl/generator/geometry_config.py.

This module is the single source of truth for the Fusion side, and it is
deliberately a *transcription* of the trimesh generator's numbers rather than a
re-derivation. `tests/check_parity.py` asserts every value here against the
Python generator, so the two cannot drift silently.

All values are MILLIMETRES and DEGREES. Conversion to Fusion's internal
centimetre/radian database units happens in `units.py` and nowhere else.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Locked metal bowl — the same Cooper stainless insert seats every style.
# --------------------------------------------------------------------------
BOWL_RIM_OD = 140.0
BOWL_BODY_OD = 130.0
BOWL_BASE_OD = 100.0
BOWL_DEPTH = 35.0
BOWL_OPENING_D = 133.0
BOWL_SEAT_D = 142.0
BOWL_RIM_RECESS = 1.8

# --------------------------------------------------------------------------
# Shared outer envelope (Cooper family) — every style lives inside this.
# --------------------------------------------------------------------------
STAND_OD = 170.0
STAND_HEIGHT = 78.0
WALL_OUTER_R = 81.6
WALL_INNER_R = 77.6

# --------------------------------------------------------------------------
# Letters — shared across all four styles.
# --------------------------------------------------------------------------
MAX_NAME_LEN = 8
MAX_RAIL_OUTER_DEG = 45.0
LETTER_HEIGHT = 15.0
LETTER_THICKNESS = 1.4
LETTER_POCKET_DEPTH = 0.85
LETTER_POCKET_CLEARANCE = 0.10
LETTER_POCKET_FLOOR_GAP = 0.06
LETTER_GAP = 1.2
LETTER_END_MARGIN = 2.5

# Font style id -> (family name as installed on the OS, bold flag).
#
# The trimesh generator ships .ttf files and rasterises them. Fusion can only
# use fonts installed on the machine, so these are the closest system-available
# equivalents. `font_name` is what goes into SketchTextInput.fontName.
FONT_STYLES = {
    "bold": ("Overpass", True, "Overpass Bold — the physically tested default"),
    "clean": ("Source Sans 3", True, "Source Sans 3 SemiBold"),
    "serif": ("Lora", False, "Lora MediumItalic"),
    "slab": ("Roboto Slab", True, "Roboto Slab Bold"),
    "rounded": ("Fredoka", True, "Fredoka SemiBold"),
    "playful": ("Baloo 2", True, "Baloo 2 SemiBold"),
    "condensed": ("Barlow Condensed", True, "Barlow Condensed SemiBold"),
}
DEFAULT_FONT_STYLE = "bold"

# Fallbacks tried in order when the requested family is not installed. Fusion
# silently substitutes a default face for an unknown fontName, which produces a
# correct-but-wrong-looking model; `letters.resolve_font` warns instead.
FONT_FALLBACKS = ("Arial", "Helvetica", "Helvetica Neue", "Verdana")


# --------------------------------------------------------------------------
# Per-style parameters.
# --------------------------------------------------------------------------

HEX = {
    "h": 78.0,
    "rb_out": WALL_OUTER_R,
    "rt_out": WALL_OUTER_R,
    "wall_inner_r": WALL_INNER_R,
    "support_start_z": 58.0,
    "groove_depth": 1.0,
    "groove_gap": 2.7,
    "groove_chamfer": 1.30,
    "target_cell_radius": 9.24,
    "pattern_edge_band": 5.0,
    "pattern_border_width": 1.4,
    "pattern_border_depth": 0.45,
    "name_keepout_margin": 1.5,
    "top_edge_bead": 0.45,
    "top_edge_height": 1.2,
    "bottom_edge_chamfer": 0.35,
    "bottom_edge_height": 1.2,
    "letter_center_z": 37.0,
}

FLUTED = {
    "h": 78.0,
    "rb_out": WALL_OUTER_R,
    "rt_out": WALL_OUTER_R,
    "wall_inner_r": WALL_INNER_R,
    "support_start_z": 58.0,
    "flute_count": 64,
    "flute_depth": 1.1,
    "min_web": 2.5,
    "pattern_edge_band": 5.0,
    "pattern_border_width": 1.4,
    "pattern_border_depth": 0.45,
    "name_keepout_margin": 2.5,
    "name_fade": 6.0,
    "top_edge_bead": 0.45,
    "top_edge_height": 1.2,
    "bottom_edge_chamfer": 0.35,
    "bottom_edge_height": 1.2,
    "letter_center_z": 39.0,
}

COOPER = {
    "stand_od": STAND_OD,
    "stand_height": STAND_HEIGHT,
    "base_height": 12.0,
    "base_inner_r": 68.0,
    "lattice_bottom": 10.0,
    "lattice_top": 72.0,
    "top_bottom": 72.0,
    "wall_outer_r": WALL_OUTER_R,
    "wall_inner_r": WALL_INNER_R,
    "paw_recess_depth": 0.7,
    "paw_count": 16,
    "paw_rows": (18.5, 38.0, 57.0),
    "paw_rail_clear_deg": 4.0,
    "name_rail_outer_r": 86.0,
    "name_rail_inner_r": 77.5,
    "name_rail_z0": 29.0,
    "name_rail_z1": 52.0,
    "name_rail_blend_z_lo": 19.0,
    "name_rail_blend_z_hi": 60.0,
    "letter_center_z": 40.5,
    "top_joint_pin_count": 8,
    "top_joint_pin_radius": 1.50,
    "top_joint_hole_radius": 1.75,
    "top_joint_radius": 79.6,
    "top_joint_pin_height": 3.0,
}

# One paw = 3 metacarpal lobes + 4 digits. Each entry is
# (d_theta_mm_at_R80, dz_mm, tangent_radius, vertical_radius, tilt_deg)
# transcribed from cooper_bowl_design.iter_paw_pad_specs(). The generator
# writes angular offsets as `dx / 80.0` radians, i.e. dx millimetres of arc at
# an 80 mm reference radius — kept in that form here so the shape is
# radius-independent the way the original is.
PAW_LOBES = (
    (0.0, 0.8, 6.2, 4.4, 0.0),
    (-3.5, -1.7, 4.4, 3.6, -10.0),
    (3.5, -1.7, 4.4, 3.6, 10.0),
    (-8.8, 6.8, 2.7, 3.5, -25.0),
    (-3.0, 9.0, 2.7, 3.5, -9.0),
    (3.0, 9.0, 2.7, 3.5, 9.0),
    (8.8, 6.8, 2.7, 3.5, 25.0),
)
PAW_LOBE_REFERENCE_R = 80.0

WAVE = {
    "h": 78.0,
    "amp": 8.0,
    "waves": 2,
    "seam_p": 45.0,
    "rt_out": 75.6,
    "rb_out": 85.7,
    "wall_thick": 5.5,
    "collar_clearance": 0.5,
    "collar_outer_r": 74.0,
    "sleeve_wall": 2.2,
    "min_upper_wall": 4.0,
    "seat_insert_clearance": 0.3,
    "seat_flange_edge_inset": 0.3,
    "shadow_chamfer": 0.6,
    "seam_gap": 0.7,
    "sectors": 64,
    "letter_center_z": 52.0,
}


def wave_derived(p=None):
    """Derived wave seam / collar numbers — mirrors geometry_config.wave_derived."""
    p = p or WAVE
    seam_y = p["h"] * p["seam_p"] / 100.0
    seam_y = max(p["amp"] + 18.0, min(p["h"] - 24.0 - p["amp"], seam_y))
    s_min = seam_y - p["amp"]
    s_max = seam_y + p["amp"]
    return {
        "seam_y": seam_y,
        "s_min": s_min,
        "s_max": s_max,
        "y2": s_max + 4.0,
        "rb_in": p["rb_out"] - p["wall_thick"],
        "rc": p["collar_outer_r"],
        "seat_z": p["h"] - BOWL_RIM_RECESS,
    }


# --------------------------------------------------------------------------
# Derived honeycomb lattice — mirrors hex_bowl_design._honeycomb_params.
# --------------------------------------------------------------------------

def honeycomb_params(p=None):
    """Cell radius / pitch for the honeycomb field.

    Reproduces the generator exactly, including its use of Python's
    banker's-rounding `round()` — 18.5 rounds to 18, not 19, which is why
    ncols comes out at 36 rather than 38.
    """
    import math

    p = p or HEX
    reference_r = 0.5 * (p["rb_out"] + p["rt_out"])
    ncols = 2 * max(6, round(math.pi * reference_r / (1.5 * p["target_cell_radius"])))
    radius = 2.0 * math.pi * reference_r / (1.5 * ncols)
    return {
        "reference_r": reference_r,
        "ncols": ncols,
        "radius": radius,
        "pitch_u": 1.5 * radius,
        "pitch_z": math.sqrt(3.0) * radius,
        "apothem": math.sqrt(3.0) * 0.5 * radius,
    }


def flute_cutter(p=None):
    """Radius and centre distance for one circular flute cutter.

    The generator's flute profile is a sine:

        offset(theta) = -flute_depth * (0.5 + 0.5 * sin(flute_count * theta))

    A revolved sine surface has no BRep equivalent that stays editable, so the
    Fusion build cuts each flute with a cylinder sized to match the sine's
    pitch and depth: same flute count, same depth, same remaining web, a
    round-bottomed valley instead of a sinusoidal one. Visually and in print
    the two are indistinguishable at 1.1 mm deep on an 8 mm pitch; the payoff
    is that flute_count and flute_depth stay live parameters.
    """
    import math

    p = p or FLUTED
    reference_r = p["rb_out"]
    pitch = 2.0 * math.pi * reference_r / p["flute_count"]
    depth = p["flute_depth"]
    # Cutter radius that produces a valley `pitch` wide and `depth` deep in a
    # locally flat wall: (pitch/2)^2 = 2*rc*depth - depth^2.
    rc = ((pitch * 0.5) ** 2 + depth ** 2) / (2.0 * depth)
    return {
        "pitch": pitch,
        "cutter_r": rc,
        "centre_r": reference_r - depth + rc,
        "web": (p["rb_out"] - p["wall_inner_r"]) - depth,
    }


STYLE_IDS = ("cooper", "wave", "hex", "fluted")

STYLE_LABELS = {
    "cooper": "Cooper — paw lattice",
    "wave": "Wave — split sine stand",
    "hex": "Honeycomb — recessed hex drum",
    "fluted": "Fluted — vertical flute drum",
}
