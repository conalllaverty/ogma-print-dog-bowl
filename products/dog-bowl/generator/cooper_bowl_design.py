#!/usr/bin/env python3
"""Generate the Ogma Print Cooper paw-lattice dog bowl stand.

Outputs print-ready STL meshes, assembly meshes, renders, and dimensional data.
The stainless-steel bowl is a visualization/reference component only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely import union_all
from shapely.affinity import scale as scale_geometry
from shapely.geometry import box

from ogma import assets
from ogma.geom import unwrap_cylinder_u as _unwrap_cylinder_u


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "cooper_dog_bowl"
MESH = OUT / "meshes"
VIS = OUT / "visuals"
NAME = "COOPER"
MAX_NAME_LEN = 8
MAX_RAIL_OUTER_DEG = 45.0  # packing beyond this is rejected as too wide
_FONTS = assets.FONTS
# Print-oriented faces: SemiBold reads sharper than Black/Rounded at FDM scale.
FONT_STYLES = {
    "bold": _FONTS / "Overpass-Variable.ttf",  # default — physically tested for FDM
    "clean": _FONTS / "SourceSans3-Semibold.ttf",
    "serif": _FONTS / "Lora-MediumItalic.ttf",  # original Named Bowl treatment
    "slab": _FONTS / "RobotoSlab-Variable.ttf",
    "rounded": _FONTS / "Fredoka-Variable.ttf",
    "playful": _FONTS / "Baloo2-SemiBold.ttf",
    "condensed": _FONTS / "BarlowCondensed-SemiBold.ttf",
}
FONT_VARIATIONS = {
    "bold": "Bold",
    "slab": "Bold",
    "rounded": "SemiBold",
}
FONT_STYLE = "bold"
FONT_PATH = str(FONT_STYLES["bold"])


class NameFitError(ValueError):
    """Raised when a name cannot fit the name rail cleanly."""

# Primary dimensions, millimetres.
STAND_OD = 170.0
STAND_HEIGHT = 78.0
BASE_HEIGHT = 12.0
LATTICE_BOTTOM = 10.0
LATTICE_TOP = 72.0

# The panel's lowest point in assembly coordinates — and **not** LATTICE_BOTTOM.
#
# The visible lattice starts at LATTICE_BOTTOM (10.0), but the locating tongue
# that keys into the base groove hangs 1 mm below it, at BASE_HEIGHT - 3.0. The
# panel is exported for printing translated by its own bounds
# (`-panel.bounds[0, 2]`), so *this* is the constant that converts between
# assembly and print frames.
#
# Using LATTICE_BOTTOM for that conversion is a 1 mm error, and it was being made
# by the fuzzy-skin paint mask: every paw's no-fuzz exclusion sat 1 mm below the
# pad it was meant to protect, which paints a fuzzed strip along one edge of each
# paw and leaves a smooth strip along the other. That is visible in Bambu
# Studio's painted triangles, and on the printed wall.
PANEL_BOTTOM_Z = BASE_HEIGHT - 3.0
TOP_BOTTOM = 72.0
WALL_OUTER_R = 81.6
WALL_INNER_R = 77.6
# Paw marks are shallow outer-face recesses (not through-holes). Through-holes
# break every perimeter loop and cause large layer-time swings — a primary
# driver of horizontal banding on cylindrical walls. Prefer features that keep
# per-layer extrusion time nearly constant (validate in Bambu Preview → Layer Time).
# Keep recess depth modest: even shallow pads leave faint hull lines at their
# top/bottom silhouette; ~0.7 mm reads clearly without a strong ring.
PAW_RECESS_DEPTH = 0.7  # sharp pads; panel fuzzy paint skips pad silhouettes
# Grow pad ellipses slightly when building the fuzzy-paint exclusion mask so
# recess rims stay smooth (matches ~70/30 outer fuzzy/smooth area split).
# Where the fuzzy-skin exclusion sits relative to the pad opening it protects.
#
# Measured against the opening the cutter actually leaves in the wall, not the
# ellipsoid's full semi-axes — see _pad_opening_scale. This used to be 1.15 of
# the semi-axes, which is 1.25x the opening: a 0.67 mm skirt of wall left smooth
# around every pad, 4,194 mm2 of it. That skirt is what the wall slivers carried
# 22 mm down the drum as the streaks running off the outer toes.
#
# Just inside the rim rather than just outside it. Outside, the boundary falls on
# open wall, which is triangulated in slivers 2.7 mm wide and the full height of
# the drum — that is what turns a skirt into a streak, and it is also why the
# outline comes out spiky. Three percent in, it falls on the dish flank instead,
# which the boolean tessellates finely, so the outline is clean and no sliver can
# carry it anywhere. It costs nothing at the rim: 0.97, 1.00 and 1.03 all fuzz
# exactly the same 944 rim-crossing triangles.
#
# Sizing this correctly is the whole fix. Dividing the wall into 1.5 mm rings so
# the mask had finer triangles to work with was tried first: it does bound the
# damage from a mis-sized exclusion (76 streaks of 3.5 mm rather than 2,484 of
# 22.4 mm) but with this value it fixes nothing, costs 8,098 triangles a panel,
# and leaves *more* wall smooth (17 mm2 against 8) because the paint boundary
# then has to staircase along the rings.
PAW_PAINT_EXCLUDE_GROW = 0.97

#: How far outside the wall the pad cutters are centred, so the boolean is clean
#: at the surface. Shared with the paint silhouettes, which need it to work out
#: how wide the resulting opening actually is.
PAW_CUTTER_OVERCUT = 0.45
PAW_PAINT_R_MID = WALL_OUTER_R
PAW_PAINT_SEAM_DEG = -90.0  # unwrap seam through the plaque arc (pad-free)
# Name-rail plaque face. Letters seat in shallow glyph-shaped pockets — no pins.
NAME_RAIL_OUTER_R = 86.0
# How deep the glyph pockets are cut. Also the letter's real thickness, since
# LETTER_PROUD is zero and the pocket has to swallow the letter whole.
#
# 2.2 mm, up from 1.2. Shared by all four styles, so they stay consistent.
#
# The trade is insertion, not strength: the pocket is a straight glyph prism
# between two cylinders with no draft, so a letter slides in on
# LETTER_POCKET_CLEARANCE alone — 0.10 mm a side, now over 2.2 mm of travel
# rather than 1.2. Nothing about the seating changes (the back is cylindrical
# and the glue gap is still LETTER_POCKET_FLOOR_GAP), but a snug fit gets snugger
# with depth, and this has not been print-tested at either depth yet. The
# letter_test coupon exists for exactly this.
LETTER_POCKET_DEPTH = 2.2
LETTER_POCKET_CLEARANCE = 0.10  # tighter outline so less grey halo shows
LETTER_POCKET_FLOOR_GAP = 0.06  # tiny glue gap under the curved letter back
# Bowl dimensions are read through `design.` on purpose, never imported by
# value. They are now set per job from the customer's bowl diameter
# (see cooper_bowl_design.configure_bowl), and `from ... import BOWL_SEAT_D`
# binds whatever the value was at import — so this module would have gone on
# building seats for a 140 mm bowl no matter what was chosen. The same shape
# of bug already cost this codebase the stale LETTER_FACE_R default.
BOWL_RIM_OD = 140.0
BOWL_BODY_OD = 130.0
BOWL_BASE_OD = 100.0
BOWL_DEPTH = 35.0
BOWL_OPENING_D = 133.0
BOWL_SEAT_D = 142.0
# Rim sits this far below the outer top edge so the bowl nests slightly.
BOWL_RIM_RECESS = 1.8
SEAT_Z = STAND_HEIGHT - BOWL_RIM_RECESS  # bowl-rim landing height
TOP_JOINT_PIN_COUNT = 8
TOP_JOINT_PIN_RADIUS = 1.50
TOP_JOINT_HOLE_RADIUS = 1.75
TOP_JOINT_RADIUS = 79.6
TOP_JOINT_PIN_HEIGHT = 3.0
LETTER_HEIGHT = 15.0  # slightly smaller → finer look at 0.4 mm nozzle
# How far a glued-in letter stands above the rail. Zero: the letters sit flush.
#
# It was 1.4 mm, which left a lip around every character — and a food bowl gets
# washed. A raised glyph edge catches residue exactly where a brush skips, and
# the join between letter and pocket is the hardest part of the whole product to
# clean. Flush, the wall wipes in one pass and the name reads by colour instead
# of relief.
#
# Every style derives its own LETTER_FACE_R as `<rail radius> + LETTER_PROUD`,
# so this one number makes the paw lattice, honeycomb, fluted drum and split
# wave flush together.
#
# Flush also means the pocket has to swallow the letter whole, so the letter's
# real thickness is LETTER_POCKET_DEPTH. Deeper is better here for a second
# reason: a letter captured on all four sides cannot be lifted by a scrubbing
# brush the way a proud one can.
LETTER_PROUD = 0.0  # flush with the rail
# Vertically centred on the name-rail flat face (z 29–52 → mid 40.5).
LETTER_CENTER_Z = 40.5
# Outer letter face sits LETTER_PROUD outside the rail; curved back seats
# on the pocket floor at NAME_RAIL_OUTER_R - LETTER_POCKET_DEPTH.
LETTER_FACE_R = NAME_RAIL_OUTER_R + LETTER_PROUD
LETTER_GAP = 1.2  # clear tangential gap between adjacent letter bounds
LETTER_END_MARGIN = 2.5  # clear space from first/last letter to rail bevel
# Glyph raster → polygon: finer grid keeps C/O curves from looking hexagonal.
GLYPH_PIXEL_MM = 0.12
GLYPH_FONT_PX = 520
GLYPH_SMOOTH_MM = 0.035  # light open/close; avoid heavy round-off
GLYPH_SIMPLIFY_MM = 0.02
# Filled by build_letters() after measuring glyph widths.
NAME_RAIL_FLAT_DEG = 30.5
NAME_RAIL_OUTER_DEG = 32.0
# Name-rail flat Z span (must match beveled_name_rail defaults).
NAME_RAIL_FLAT_Z0 = 29.0
NAME_RAIL_FLAT_Z1 = 52.0


def cylinder(radius: float, height: float, z0: float, sections: int = 192) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    mesh.apply_translation([0, 0, z0 + height / 2])
    return mesh


def boolean_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.union(meshes, engine="manifold")


def boolean_difference(mesh: trimesh.Trimesh, cutters: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    return trimesh.boolean.difference([mesh, *cutters], engine="manifold")


def annular_sector(
    r_inner: float,
    r_outer: float,
    z_bottom: float,
    z_top: float,
    angle_min: float,
    angle_max: float,
    segments: int = 48,
) -> trimesh.Trimesh:
    """Create a watertight annular-sector prism."""
    angles = np.linspace(angle_min, angle_max, segments + 1)
    vertices = []
    for z in (z_bottom, z_top):
        for r in (r_inner, r_outer):
            vertices.extend([[r * math.sin(a), -r * math.cos(a), z] for a in angles])
    n = segments + 1

    def idx(z_i: int, r_i: int, a_i: int) -> int:
        return z_i * 2 * n + r_i * n + a_i

    faces = []
    for i in range(segments):
        # Bottom and top.
        faces.extend(
            [
                [idx(0, 0, i), idx(0, 1, i + 1), idx(0, 1, i)],
                [idx(0, 0, i), idx(0, 0, i + 1), idx(0, 1, i + 1)],
                [idx(1, 0, i), idx(1, 1, i), idx(1, 1, i + 1)],
                [idx(1, 0, i), idx(1, 1, i + 1), idx(1, 0, i + 1)],
            ]
        )
        # Inner and outer curved walls.
        faces.extend(
            [
                [idx(0, 0, i), idx(1, 0, i), idx(1, 0, i + 1)],
                [idx(0, 0, i), idx(1, 0, i + 1), idx(0, 0, i + 1)],
                [idx(0, 1, i), idx(1, 1, i + 1), idx(1, 1, i)],
                [idx(0, 1, i), idx(0, 1, i + 1), idx(1, 1, i + 1)],
            ]
        )
    for i in (0, segments):
        j = 0 if i == 0 else segments
        faces.extend(
            [
                [idx(0, 0, j), idx(0, 1, j), idx(1, 1, j)],
                [idx(0, 0, j), idx(1, 1, j), idx(1, 0, j)],
            ]
        )
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    return mesh


def tapered_annular_sector(
    r_inner_bottom: float,
    r_outer_bottom: float,
    r_inner_top: float,
    r_outer_top: float,
    z_bottom: float,
    z_top: float,
    angle_min: float,
    angle_max: float,
    segments: int = 48,
) -> trimesh.Trimesh:
    """Create a watertight annular sector with linearly tapered radial walls."""
    angles = np.linspace(angle_min, angle_max, segments + 1)
    vertices = []
    for z, radii in (
        (z_bottom, (r_inner_bottom, r_outer_bottom)),
        (z_top, (r_inner_top, r_outer_top)),
    ):
        for r in radii:
            vertices.extend([[r * math.sin(a), -r * math.cos(a), z] for a in angles])
    n = segments + 1

    def idx(z_i: int, r_i: int, a_i: int) -> int:
        return z_i * 2 * n + r_i * n + a_i

    faces = []
    for i in range(segments):
        faces.extend(
            [
                [idx(0, 0, i), idx(0, 1, i + 1), idx(0, 1, i)],
                [idx(0, 0, i), idx(0, 0, i + 1), idx(0, 1, i + 1)],
                [idx(1, 0, i), idx(1, 1, i), idx(1, 1, i + 1)],
                [idx(1, 0, i), idx(1, 1, i + 1), idx(1, 0, i + 1)],
                [idx(0, 0, i), idx(1, 0, i), idx(1, 0, i + 1)],
                [idx(0, 0, i), idx(1, 0, i + 1), idx(0, 0, i + 1)],
                [idx(0, 1, i), idx(1, 1, i + 1), idx(1, 1, i)],
                [idx(0, 1, i), idx(0, 1, i + 1), idx(1, 1, i + 1)],
            ]
        )
    for j in (0, segments):
        faces.extend(
            [
                [idx(0, 0, j), idx(0, 1, j), idx(1, 1, j)],
                [idx(0, 0, j), idx(1, 1, j), idx(1, 0, j)],
            ]
        )
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    return mesh


def beveled_name_rail(
    r_inner: float = 77.5,
    r_outer: float = NAME_RAIL_OUTER_R,
    r_wall: float = WALL_OUTER_R,
    z_bottom: float = 19.0,
    z_flat_bottom: float = NAME_RAIL_FLAT_Z0,
    z_flat_top: float = NAME_RAIL_FLAT_Z1,
    z_top: float = 60.0,
    angle_min: float = math.radians(-32),
    angle_flat_min: float = math.radians(-30.5),
    angle_flat_max: float = math.radians(30.5),
    angle_max: float = math.radians(32),
    segments: int = 64,
    z_slices: int = 24,
) -> trimesh.Trimesh:
    """Curved name rail with long, smooth Z blends (reduces hull-line banding).

    Abrupt top/bottom ledges change layer cross-section in one step and print as
    a bright ring around the whole cylinder. Longer ease-in/out blends spread
    that change over many layers.
    """
    angles = np.linspace(angle_min, angle_max, segments + 1)
    z_levels = np.linspace(z_bottom, z_top, z_slices)

    def smoothstep(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    def outer_radius(angle: float, z: float) -> float:
        if angle < angle_flat_min:
            angle_factor = smoothstep((angle - angle_min) / (angle_flat_min - angle_min))
        elif angle > angle_flat_max:
            angle_factor = smoothstep((angle_max - angle) / (angle_max - angle_flat_max))
        else:
            angle_factor = 1.0
        if z < z_flat_bottom:
            z_factor = smoothstep((z - z_bottom) / (z_flat_bottom - z_bottom))
        elif z > z_flat_top:
            z_factor = smoothstep((z_top - z) / (z_top - z_flat_top))
        else:
            z_factor = 1.0
        factor = min(angle_factor, z_factor)
        return r_wall + (r_outer - r_wall) * factor

    vertices = []
    for z in z_levels:
        vertices.extend([[r_inner * math.sin(a), -r_inner * math.cos(a), z] for a in angles])
        vertices.extend(
            [
                [outer_radius(a, z) * math.sin(a), -outer_radius(a, z) * math.cos(a), z]
                for a in angles
            ]
        )
    n_a = len(angles)

    def idx(z_i: int, r_i: int, a_i: int) -> int:
        return z_i * 2 * n_a + r_i * n_a + a_i

    faces = []
    last_z = len(z_levels) - 1
    for i in range(segments):
        faces.extend(
            [
                [idx(0, 0, i), idx(0, 1, i + 1), idx(0, 1, i)],
                [idx(0, 0, i), idx(0, 0, i + 1), idx(0, 1, i + 1)],
                [idx(last_z, 0, i), idx(last_z, 1, i), idx(last_z, 1, i + 1)],
                [idx(last_z, 0, i), idx(last_z, 1, i + 1), idx(last_z, 0, i + 1)],
            ]
        )
        for z_i in range(last_z):
            faces.extend(
                [
                    [idx(z_i, 0, i), idx(z_i + 1, 0, i), idx(z_i + 1, 0, i + 1)],
                    [idx(z_i, 0, i), idx(z_i + 1, 0, i + 1), idx(z_i, 0, i + 1)],
                    [idx(z_i, 1, i), idx(z_i + 1, 1, i + 1), idx(z_i + 1, 1, i)],
                    [idx(z_i, 1, i), idx(z_i, 1, i + 1), idx(z_i + 1, 1, i + 1)],
                ]
            )
    for a_i in (0, segments):
        for z_i in range(last_z):
            faces.extend(
                [
                    [idx(z_i, 0, a_i), idx(z_i, 1, a_i), idx(z_i + 1, 1, a_i)],
                    [idx(z_i, 0, a_i), idx(z_i + 1, 1, a_i), idx(z_i + 1, 0, a_i)],
                ]
            )
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    return mesh


# The paw lattice's own rail geometry, captured at import.
#
# These three are module globals that the honeycomb, fluted drum and wave each
# overwrite with their own wall radius (see their `_configure_*_letters`). None
# of them puts it back. In a one-shot CLI run that is harmless — the process
# exits. The API server is long-lived and builds every style in one process, so
# whichever style ran last left its rail radius behind for the next one.
#
# The paw lattice was the visible casualty because it is the only style that
# never sets these at all: it relies on the module defaults, and by the time it
# ran they were the honeycomb's. Its letters were built for an 81.6 mm wall and
# placed on an 86 mm one — buried inside the drum, which read as "the letters
# have disappeared".
#
# The golden harness could not have caught this: it runs each case in a fresh
# subprocess, so every build starts from a clean module.
_LETTER_GEOMETRY_DEFAULTS = {
    "NAME_RAIL_OUTER_R": NAME_RAIL_OUTER_R,
    "LETTER_FACE_R": LETTER_FACE_R,
    "LETTER_CENTER_Z": LETTER_CENTER_Z,
}


# The bowl the stand is built around, in millimetres.
#
# 140 is the reference: a nominal 5.5" bowl measures 139.7 mm and the stand was
# designed against it. Everything else about the bowl is derived from this by the
# ratios the reference embodies, so one number moves the whole seat.
#
# Only two of these reach the printed part — BOWL_OPENING_D, which must clear the
# bowl's body, and BOWL_SEAT_D, which must catch its rim. The rest describe
# `visual_bowl()`, which is a reference render and never printed, so approximating
# them by ratio is honest.
DEFAULT_BOWL_RIM_OD = 140.0
BOWL_BODY_RATIO = 130.0 / 140.0     # body just under the rim
BOWL_BASE_RATIO = 100.0 / 140.0
BOWL_DEPTH_RATIO = 35.0 / 140.0
BOWL_SEAT_CLEARANCE = 2.0           # seat Ø over rim Ø — catches the rim
BOWL_OPENING_CLEARANCE = 3.0        # opening Ø over body Ø — passes the body

# What a 170 mm stand can actually hold. Below the minimum the opening closes up;
# above the maximum the seat eats the wall and leaves no material for the top
# ring. Measured, not guessed: at Ø158 the ring land is 1.6 mm.
MIN_BOWL_RIM_OD = 127.0             # 5.0"
MAX_BOWL_RIM_OD = 152.0             # 6.0"

# How much of the rim must overhang the opening. This is the number that stops a
# bowl dropping straight through, and it is not a matter of taste: print
# tolerance on a ~135 mm hole runs ±0.2-0.4 mm and stainless bowls vary ±0.5 mm
# between batches, so anything under ~1.5 mm can reach zero in the real world.
# The Ø139 coupon that felt best by hand had 0.35 mm.
MIN_SEAT_ENGAGEMENT = 2.0

# One-piece construction.
#
# The three-part stand keys together with a tongue in a groove and eight pins,
# each joint carrying 0.35 mm of clearance around a 170 mm circumference. That is
# capillary width: water wicks in and cannot dry, on a thing that gets rinsed.
# Printed as one body there is nothing to wick into.
#
# The obstacle was never the joints, it was the bowl seat: its underside is an
# 11 mm horizontal ledge, which prints fine flat on a plate as its own part and
# needs support the moment it is halfway up a tall one. Replacing that ledge with
# a cone at this angle makes the whole stand self-supporting upright — measured
# at 0 mm² needing support, against 24,475 mm² for a naive merge.
ONE_PIECE_CONE_DEG = 45.0

# Extra opening clearance the cone costs, over the flat ledge.
#
# The cone rises into the space the bowl's body passes through, so the opening
# has to grow by this much to keep clear of it. Ø133 -> Ø134 for the reference
# bowl, confirmed on a printed full-ring coupon; the sectors before it bracketed
# 133/136/139 and skipped the answer.
ONE_PIECE_OPENING_EXTRA = 1.0


def configure_bowl(
    rim_od_mm: float | None = None,
    body_od_mm: float | None = None,
) -> None:
    """Resize the seat for a given bowl, in millimetres.

    `body_od_mm` is the bowl's width just below the rim — the part that has to
    pass through the opening, as opposed to the rim, which has to be caught by
    the seat. They are separate measurements on a real bowl and the ratio
    between them is not reliable across manufacturers, so it is a parameter
    rather than a derivation; it merely *defaults* to the reference ratio.

    Sets the module globals every style reads through `design.` — which is why
    those styles must not import them by value; see the note by BOWL_RIM_OD.

    Called from configure_output, so each job starts from the customer's choice
    rather than inheriting the previous one. The API builds every style in one
    long-lived process, and module state that is set but never reset is how the
    paw lattice ended up with the honeycomb's rail radius.
    """
    global BOWL_RIM_OD, BOWL_BODY_OD, BOWL_BASE_OD, BOWL_DEPTH
    global BOWL_OPENING_D, BOWL_SEAT_D
    rim = float(DEFAULT_BOWL_RIM_OD if rim_od_mm is None else rim_od_mm)
    if not (MIN_BOWL_RIM_OD <= rim <= MAX_BOWL_RIM_OD):
        raise ValueError(
            f"bowl diameter {rim:.1f} mm is outside the {MIN_BOWL_RIM_OD:.0f}"
            f"-{MAX_BOWL_RIM_OD:.0f} mm this stand can seat"
        )
    body = float(rim * BOWL_BODY_RATIO if body_od_mm is None else body_od_mm)
    engagement = (rim - (body + BOWL_OPENING_CLEARANCE)) / 2.0
    if engagement < MIN_SEAT_ENGAGEMENT:
        raise ValueError(
            f"a {body:.1f} mm body in a {rim:.1f} mm rim leaves only "
            f"{engagement:.2f} mm of seat to catch the rim; "
            f"{MIN_SEAT_ENGAGEMENT:.1f} mm is the minimum before the bowl can "
            f"drop through"
        )
    BOWL_RIM_OD = rim
    BOWL_BODY_OD = body
    BOWL_BASE_OD = rim * BOWL_BASE_RATIO
    BOWL_DEPTH = rim * BOWL_DEPTH_RATIO
    BOWL_SEAT_D = rim + BOWL_SEAT_CLEARANCE
    BOWL_OPENING_D = body + BOWL_OPENING_CLEARANCE


def reset_letter_geometry() -> None:
    """Restore the paw lattice's rail geometry.

    Called from `configure_output`, which every style invokes first, before
    applying its own overrides. That makes each build start from a known state
    instead of inheriting the previous one.
    """
    globals().update(_LETTER_GEOMETRY_DEFAULTS)


def configure_output(
    out_dir: Path,
    name: str,
    font_style: str = "bold",
    bowl_rim_od_mm: float | None = None,
    bowl_body_od_mm: float | None = None,
) -> None:
    """Point mesh/visual exports at a job directory and set the name/font.

    Also resets the letter rail geometry — see `reset_letter_geometry`. This is
    the one call every style makes before configuring anything of its own, so it
    is where "start from a clean slate" belongs.
    """
    reset_letter_geometry()
    configure_bowl(bowl_rim_od_mm, bowl_body_od_mm)
    global OUT, MESH, VIS, NAME, FONT_STYLE, FONT_PATH
    if font_style not in FONT_STYLES:
        raise ValueError(f"Unknown font style '{font_style}'. Choose from {sorted(FONT_STYLES)}")
    font_path = FONT_STYLES[font_style]
    if not font_path.is_file():
        raise FileNotFoundError(f"Font file missing for style '{font_style}': {font_path}")
    NAME = normalize_name(name)
    FONT_STYLE = font_style
    FONT_PATH = str(font_path)
    OUT = Path(out_dir)
    MESH = OUT / "meshes"
    VIS = OUT / "visuals"
    MESH.mkdir(parents=True, exist_ok=True)
    VIS.mkdir(parents=True, exist_ok=True)


def normalize_name(name: str) -> str:
    cleaned = "".join(ch for ch in name.upper() if ch.isalpha())
    if not cleaned:
        raise ValueError("Name must contain at least one letter A–Z")
    if len(cleaned) > MAX_NAME_LEN:
        raise ValueError(f"Name must be {MAX_NAME_LEN} characters or fewer (got {len(cleaned)})")
    if len(cleaned) < 2:
        raise ValueError("Name must be at least 2 letters")
    return cleaned


def glyph_polygon(
    letter: str,
    target_height: float = LETTER_HEIGHT,
    font_path: str | None = None,
    font_style: str | None = None,
):
    """Rasterize a glyph at high resolution for smooth printable outlines.

    `font_path`/`font_style` default to the globals set by configure_output().
    They can be passed explicitly so a caller that only wants to measure a
    glyph (the fit pre-check) doesn't have to mutate job state to do it.
    """
    font = ImageFont.truetype(font_path or FONT_PATH, GLYPH_FONT_PX)
    variation = FONT_VARIATIONS.get(font_style or FONT_STYLE)
    if variation is not None:
        font.set_variation_by_name(variation.encode())
    bbox = font.getbbox(letter, stroke_width=0)
    width = bbox[2] - bbox[0] + 16
    height = bbox[3] - bbox[1] + 16
    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    draw.text((8 - bbox[0], 8 - bbox[1]), letter, font=font, fill=255)
    occupied = np.asarray(image) > 96
    ys, xs = np.nonzero(occupied)
    occupied = occupied[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]

    pixel = GLYPH_PIXEL_MM
    target_rows = max(1, round(target_height / pixel))
    target_cols = max(1, round(occupied.shape[1] * target_rows / occupied.shape[0]))
    resized = Image.fromarray((occupied * 255).astype(np.uint8)).resize(
        (target_cols, target_rows), Image.Resampling.LANCZOS
    )
    mask = np.asarray(resized) > 128
    cells = []
    for row, col in zip(*np.nonzero(mask)):
        x0 = (col - target_cols / 2) * pixel
        y0 = (target_rows - row - 1 - target_rows / 2) * pixel
        cells.append(box(x0, y0, x0 + pixel, y0 + pixel))
    # Mild morphological smooth only — heavy buffer/simplify made letters chunky.
    polygon = (
        union_all(cells)
        .buffer(GLYPH_SMOOTH_MM)
        .buffer(-GLYPH_SMOOTH_MM)
        .simplify(GLYPH_SIMPLIFY_MM, preserve_topology=True)
    )
    return polygon, mask, pixel


def choose_pin_points(mask: np.ndarray, pixel: float) -> list[tuple[float, float]]:
    """Choose two well-separated pin locations supported by solid glyph strokes."""
    rows, cols = mask.shape
    candidates = []
    for row, col in zip(*np.nonzero(mask)):
        if row < 2 or col < 2 or row >= rows - 2 or col >= cols - 2:
            continue
        local = mask[row - 2 : row + 3, col - 2 : col + 3]
        if local.mean() > 0.65:
            x = (col + 0.5 - cols / 2) * pixel
            y = (rows - row - 0.5 - rows / 2) * pixel
            candidates.append((x, y))
    if not candidates:
        candidates = [
            ((col + 0.5 - cols / 2) * pixel, (rows - row - 0.5 - rows / 2) * pixel)
            for row, col in zip(*np.nonzero(mask))
        ]
    candidates = np.asarray(candidates)
    upper = candidates[candidates[:, 1] >= np.median(candidates[:, 1])]
    lower = candidates[candidates[:, 1] < np.median(candidates[:, 1])]
    p1 = upper[np.argmin(np.abs(upper[:, 0]) + 0.15 * np.abs(upper[:, 1] - 4.5))]
    p2 = lower[np.argmin(np.abs(lower[:, 0]) + 0.15 * np.abs(lower[:, 1] + 4.5))]
    return [tuple(p1), tuple(p2)]


def letter_angular_half_extent(mesh: trimesh.Trimesh) -> float:
    """Max |theta| of a letter when seated at theta=0 on the name rail.

    Uses the full solid (including thickness) because the inner face sits at a
    smaller radius and therefore subtends a larger angle than the outer face.
    """
    placed = assembly_letter({"mesh": mesh, "arc_center": 0.0})
    theta = np.arctan2(placed.vertices[:, 0], -placed.vertices[:, 1])
    return float(np.max(np.abs(theta)))


def pack_letter_arc_centers(half_angles: list[float]) -> list[float]:
    """Place letter centres so adjacent solids keep LETTER_GAP at LETTER_FACE_R.

    half_angles are radians (from letter_angular_half_extent). Returned values
    are arc lengths (mm) at LETTER_FACE_R for use as arc_center.
    """
    if not half_angles:
        return []
    gap_angle = LETTER_GAP / LETTER_FACE_R
    angles = [0.0]
    for i in range(1, len(half_angles)):
        step = half_angles[i - 1] + gap_angle + half_angles[i]
        angles.append(angles[-1] + step)
    mid = (angles[0] - half_angles[0] + angles[-1] + half_angles[-1]) / 2.0
    return [(a - mid) * LETTER_FACE_R for a in angles]


def required_name_rail_angles(half_angles: list[float], arc_centers: list[float]) -> tuple[float, float]:
    """Return (flat_half_deg, outer_half_deg) that fit packed letters plus margin."""
    margin_angle = LETTER_END_MARGIN / LETTER_FACE_R
    half_span_rad = max(abs(c) / LETTER_FACE_R + ha for c, ha in zip(arc_centers, half_angles))
    flat_deg = math.degrees(half_span_rad + margin_angle)
    outer_deg = flat_deg + 1.5
    return flat_deg, outer_deg


def letter_print_to_assembly_matrix(
    arc_center: float, face_r: float | None = None
) -> np.ndarray:
    """Map print-space letter (X tangent, Y vertical, Z into rail) to world.

    `face_r` defaults to the *current* LETTER_FACE_R, resolved on each call.

    It used to be written `face_r: float = LETTER_FACE_R`, which binds the value
    once, when this module is imported. LETTER_FACE_R is a module global that
    every style except the paw lattice reassigns at run time — the honeycomb,
    fluted drum and wave all set their own rail radius — so every call that
    omitted the argument silently used the paw lattice's 87.4 mm.

    Cooper was the one style where the stale default was correct, which is
    exactly why it was the one style that looked right. On the honeycomb the
    letters were placed 87.4 mm out from a wall that ends at 81.6 mm: floating
    in mid-air, which is what showed up in the viewer.

    Worse, this is not only a placement bug. `curved_letter_mesh` applies this
    same matrix to cut the letter's concave back against a cylinder at the rail
    radius. Positioned 4.4 mm too far out, the letter sits entirely outside that
    cylinder and the boolean removes nothing — so the *printed* letter kept a
    flat back and could never have seated in its pocket.

    Note the asymmetry that hid it: `theta` below reads the live global, so the
    angular placement was always right. Only the radius was wrong.
    """
    if face_r is None:
        face_r = LETTER_FACE_R
    theta = arc_center / LETTER_FACE_R
    tangent = np.array([math.cos(theta), math.sin(theta), 0.0])
    radial = np.array([math.sin(theta), -math.cos(theta), 0.0])
    vertical = np.array([0.0, 0.0, 1.0])
    transform = np.eye(4)
    # Print X -> -tangent (mirrored glyph), Y -> vertical, Z -> -radial.
    transform[:3, :3] = np.column_stack((-tangent, vertical, -radial))
    transform[:3, 3] = radial * face_r + np.array([0.0, 0.0, LETTER_CENTER_Z])
    return transform


def glyph_bulge(polygon, face_r: float | None = None) -> float:
    """How far a glyph's corners stand proud of the rail, given a flat face.

    The letter's outer face is flat because that is the side that prints against
    the bed. A flat plane tangent to the rail cylinder is only level with it at
    the tangent point; `w` millimetres to either side it stands proud by
    hypot(R, w) - R. That is what stops LETTER_PROUD = 0 from actually being
    flush.

    Sinking the letter by this much puts its *widest* point level with the rail,
    which is the edge that a cloth or a brush would otherwise catch. The middle
    of the glyph then sits that far below flush — a shallow dish, which wipes
    clean in a way a raised edge does not.

    Per glyph, not one constant, because it goes with the square of the
    half-width and the fonts differ enormously: measured across all seven faces
    and A-Z, 0.257 mm for condensed 'W' up to 0.698 mm for slab 'W'. A single
    offset large enough for the widest would leave 'I' in a 0.7 mm trench.
    """
    r = LETTER_FACE_R if face_r is None else face_r
    half_width = max(abs(polygon.bounds[0]), abs(polygon.bounds[2]))
    return math.hypot(r, half_width) - r


def curved_letter_mesh(polygon, arc_center: float) -> trimesh.Trimesh:
    """Letter with flat printable face and concave cylindrical back.

    The back matches the pocket floor radius so the glyph seats tight against
    the curved rail instead of rocking on a flat chord.
    """
    r_back = NAME_RAIL_OUTER_R - LETTER_POCKET_DEPTH
    # Extra depth so the cylinder boolean cleanly forms the concave back.
    extrude_h = LETTER_PROUD + LETTER_POCKET_DEPTH + 1.2
    body = trimesh.creation.extrude_polygon(polygon, height=extrude_h, engine="earcut")

    body.apply_transform(letter_print_to_assembly_matrix(arc_center))
    core = trimesh.creation.cylinder(radius=r_back, height=120.0, sections=160)
    body = boolean_difference(body, [core])
    body.apply_transform(np.linalg.inv(letter_print_to_assembly_matrix(arc_center)))
    body.apply_translation([0.0, 0.0, -float(body.bounds[0, 2])])
    body.remove_unreferenced_vertices()
    return body


def letter_pocket_cutter(polygon, arc_center: float) -> trimesh.Trimesh:
    """Glyph-shaped pocket cutter: oversized outline, cylindrical floor."""
    poly = polygon.buffer(LETTER_POCKET_CLEARANCE)
    if poly.is_empty:
        raise ValueError("letter pocket polygon vanished after clearance buffer")
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    r_outer = NAME_RAIL_OUTER_R + 0.55
    # Dropped by the glyph's own bulge too — the letter is seated that much
    # deeper (see glyph_bulge), so a floor at the nominal depth would hold it
    # proud of the rail again.
    r_floor = (
        NAME_RAIL_OUTER_R
        - glyph_bulge(polygon)
        - LETTER_POCKET_DEPTH
        - LETTER_POCKET_FLOOR_GAP
    )
    extrude_h = (r_outer - r_floor) + 0.4
    body = trimesh.creation.extrude_polygon(poly, height=extrude_h, engine="earcut")
    body.apply_transform(letter_print_to_assembly_matrix(arc_center, face_r=r_outer))
    core = trimesh.creation.cylinder(radius=r_floor, height=120.0, sections=160)
    return boolean_difference(body, [core])


def build_letters(name: str | None = None):
    global NAME_RAIL_FLAT_DEG, NAME_RAIL_OUTER_DEG, NAME
    if name is not None:
        NAME = normalize_name(name)
    letter_data = []
    widths: list[float] = []
    half_angles: list[float] = []
    polygons = []

    for letter in NAME:
        polygon, _mask, _pixel = glyph_polygon(letter)
        # Visible face prints on the bed. Mirror so it reads correctly through
        # the plate; the curved back faces upward (no supports needed).
        polygon = scale_geometry(polygon, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0))
        polygons.append(polygon)
        # Size using a theta=0 seating — curvature is local and packing-stable.
        provisional = curved_letter_mesh(polygon, arc_center=0.0)
        xmin, xmax = float(provisional.bounds[0][0]), float(provisional.bounds[1][0])
        widths.append(xmax - xmin)
        half_angles.append(letter_angular_half_extent(provisional))

    arc_centers = pack_letter_arc_centers(half_angles)
    NAME_RAIL_FLAT_DEG, NAME_RAIL_OUTER_DEG = required_name_rail_angles(half_angles, arc_centers)
    if NAME_RAIL_OUTER_DEG > MAX_RAIL_OUTER_DEG:
        raise NameFitError(
            f"'{NAME}' is too wide for the rail "
            f"(needs ±{NAME_RAIL_OUTER_DEG:.1f}°, max ±{MAX_RAIL_OUTER_DEG:.0f}°). "
            "Try fewer letters or the condensed letter style."
        )

    print(
        f"Letter packing (angular, gap={LETTER_GAP:.1f} mm at R={LETTER_FACE_R:.1f}):"
    )
    bodies = []
    for ch, polygon, w, ha, c in zip(NAME, polygons, widths, half_angles, arc_centers):
        mesh = curved_letter_mesh(polygon, arc_center=c)
        mesh.metadata["name"] = f"Letter_{ch}"
        bodies.append(mesh)
        print(
            f"  {ch}: flat_w={w:.2f}  half_angle={math.degrees(ha):.2f}°  "
            f"arc_center={c:+.2f}"
        )
    for i in range(len(half_angles) - 1):
        dtheta = (arc_centers[i + 1] - arc_centers[i]) / LETTER_FACE_R
        gap = (dtheta - half_angles[i] - half_angles[i + 1]) * LETTER_FACE_R
        print(f"  gap {NAME[i]}-{NAME[i + 1]}: {gap:.2f} mm")
    total_span = (
        arc_centers[-1] / LETTER_FACE_R
        + half_angles[-1]
        - (arc_centers[0] / LETTER_FACE_R - half_angles[0])
    ) * LETTER_FACE_R
    print(
        f"  total angular span={total_span:.2f} mm | rail flat=±{NAME_RAIL_FLAT_DEG:.2f}° "
        f"outer=±{NAME_RAIL_OUTER_DEG:.2f}°"
    )
    print(
        f"  pockets: depth={LETTER_POCKET_DEPTH:.2f} mm, "
        f"outline clearance={LETTER_POCKET_CLEARANCE:.2f} mm, "
        f"floor gap={LETTER_POCKET_FLOOR_GAP:.2f} mm"
    )

    for index, letter in enumerate(NAME):
        letter_data.append(
            {
                "character": letter,
                "mesh": bodies[index],
                "polygon": polygons[index],
                "pins": [],
                "width": widths[index],
                "half_angle": half_angles[index],
                "arc_center": float(arc_centers[index]),
            }
        )
    return letter_data


def ellipsoid_cutter(
    theta: float,
    z: float,
    tangent_r: float,
    vertical_r: float,
    tilt_deg: float = 0.0,
    recess_depth: float = PAW_RECESS_DEPTH,
) -> trimesh.Trimesh:
    """Ellipsoid boolean cutter for a shallow outer-face recess.

    Centre sits just outside the outer wall so the solid only bites inward by
    recess_depth, leaving a continuous inner shell (no through-holes).
    """
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    tangent = np.array([math.cos(theta), math.sin(theta), 0.0])
    radial = np.array([math.sin(theta), -math.cos(theta), 0.0])
    vertical = np.array([0.0, 0.0, 1.0])
    tilt = math.radians(tilt_deg)
    major = tangent * math.cos(tilt) + vertical * math.sin(tilt)
    minor = -tangent * math.sin(tilt) + vertical * math.cos(tilt)
    # Overcut slightly outside so the boolean is clean at the outer surface.
    radial_half = recess_depth + PAW_CUTTER_OVERCUT
    center_r = WALL_OUTER_R + PAW_CUTTER_OVERCUT
    linear = np.column_stack((major * tangent_r, radial * radial_half, minor * vertical_r))
    transform = np.eye(4)
    transform[:3, :3] = linear
    transform[:3, 3] = radial * center_r + np.array([0, 0, z])
    mesh.apply_transform(transform)
    return mesh


def iter_paw_pad_specs(rail_outer_deg: float | None = None):
    """Yield (theta, z, tangent_r, vertical_r, tilt_deg) for every paw pad lobe."""
    paw_count = 16
    rail = NAME_RAIL_OUTER_DEG if rail_outer_deg is None else rail_outer_deg
    rail_half = math.radians(rail + 4.0)
    for row, pad_z in enumerate((18.5, 38.0, 57.0)):
        offset = (row % 2) * math.pi / paw_count
        for i in range(paw_count):
            theta = 2 * math.pi * i / paw_count + offset
            # Front is near theta=0 with outward normal -Y; skip rail angles.
            if abs(((theta + math.pi) % (2 * math.pi)) - math.pi) < rail_half:
                continue
            yield theta, pad_z + 0.8, 6.2, 4.4, 0.0
            yield theta - 3.5 / 80.0, pad_z - 1.7, 4.4, 3.6, -10.0
            yield theta + 3.5 / 80.0, pad_z - 1.7, 4.4, 3.6, 10.0
            for dx, dz, tilt in zip(
                (-8.8, -3.0, 3.0, 8.8),
                (6.8, 9.0, 9.0, 6.8),
                (-25.0, -9.0, 9.0, 25.0),
            ):
                yield theta + dx / 80.0, pad_z + dz, 2.7, 3.5, tilt


def paw_cutters() -> list[trimesh.Trimesh]:
    cutters = []
    # Group metacarpal lobes into one boolean per paw; digits stay separate.
    specs = list(iter_paw_pad_specs())
    i = 0
    while i < len(specs):
        # Each paw emits 3 metacarpal lobes then 4 digits.
        meta = [ellipsoid_cutter(*specs[i + k][:5]) for k in range(3)]
        cutters.append(boolean_union(meta))
        for k in range(3, 7):
            cutters.append(ellipsoid_cutter(*specs[i + k][:5]))
        i += 7
    return cutters


def unwrap_cylinder_u(x, y, r_mid: float = PAW_PAINT_R_MID, seam_deg: float = PAW_PAINT_SEAM_DEG):
    """Map XY to unwrapped arc-length u; seam through the plaque (pad-free)."""
    return _unwrap_cylinder_u(x, y, r_mid=r_mid, seam_deg=seam_deg)


def _pad_opening_scale(recess_depth: float = PAW_RECESS_DEPTH) -> float:
    """How much of a pad cutter's cross-section actually reaches the wall.

    The cutter is an ellipsoid centred PAW_CUTTER_OVERCUT proud of the wall, so
    the wall cuts it off-centre and the opening it leaves is narrower than the
    ellipsoid's full semi-axes — by this factor, 0.920 at the shipping numbers.

    Worth its own function because the paint silhouettes have to match the
    opening, not the ellipsoid. Sizing them off the full semi-axes made every
    exclusion 9% wider than the pad it was covering before any margin was added.
    """
    half = recess_depth + PAW_CUTTER_OVERCUT
    return math.sqrt(max(0.0, 1.0 - (PAW_CUTTER_OVERCUT / half) ** 2))


def paw_paint_silhouettes(
    z_offset: float = LATTICE_BOTTOM,
    grow: float = PAW_PAINT_EXCLUDE_GROW,
    rail_outer_deg: float | None = None,
    samples: int = 48,
):
    """2D pad polygons in unwrapped (u, z) space for fuzzy-skin paint exclusion."""
    from shapely.geometry import Polygon

    polys = []
    for theta, z, tangent_r, vertical_r, tilt_deg in iter_paw_pad_specs(rail_outer_deg):
        x = WALL_OUTER_R * math.sin(theta)
        y = -WALL_OUTER_R * math.cos(theta)
        cu = float(unwrap_cylinder_u(np.array([x]), np.array([y]))[0])
        cz = z - z_offset
        tilt = math.radians(tilt_deg)
        opening = grow * _pad_opening_scale()
        pts = []
        for k in range(samples):
            ang = 2 * math.pi * k / samples
            maj = opening * tangent_r * math.cos(ang)
            mnr = opening * vertical_r * math.sin(ang)
            pts.append(
                (
                    cu + maj * math.cos(tilt) - mnr * math.sin(tilt),
                    cz + maj * math.sin(tilt) + mnr * math.cos(tilt),
                )
            )
        poly = Polygon(pts)
        if poly.is_valid and poly.area > 1e-9:
            polys.append(poly)
    return polys


def radial_cylinder(theta: float, x_offset: float, z: float, radius: float, length: float):
    """Legacy radial blind-hole cutter (unused after letter pockets)."""
    base_theta = theta + x_offset / LETTER_FACE_R
    radial = np.array([math.sin(base_theta), -math.cos(base_theta), 0.0])
    face_r = NAME_RAIL_OUTER_R
    overcut = 0.4
    cutter_length = length + overcut
    center_r = face_r - length / 2.0 + overcut / 2.0
    mesh = trimesh.creation.cylinder(radius=radius, height=cutter_length, sections=32)
    transform = trimesh.geometry.align_vectors([0, 0, 1], radial)
    mesh.apply_transform(transform)
    mesh.apply_translation(radial * center_r + np.array([0, 0, z]))
    return mesh


def _revolved_wedge(points) -> trimesh.Trimesh:
    """A solid of revolution from an open (r, z) polyline.

    Closes the profile and fixes the winding, because `revolve` does neither and
    both failures surface identically — as "Not all meshes are volumes" from
    whichever boolean runs next, which names none of its inputs. An open profile
    revolves to a shell; a clockwise one to a solid of negative volume with its
    normals inside out.
    """
    profile = np.asarray(points, dtype=float)
    if not np.allclose(profile[0], profile[-1]):
        profile = np.vstack([profile, profile[:1]])
    wedge = trimesh.creation.revolve(profile, sections=256)
    if wedge.volume < 0:
        wedge.invert()
    return wedge


def _seat_cone_fillet() -> trimesh.Trimesh:
    """The wedge that turns the bowl seat's ledge into a printable cone.

    Additive rather than subtractive: the ledge is the *underside* of existing
    material, so the fix is to fill the space beneath it, from the wall's inner
    face up to the opening, at ONE_PIECE_CONE_DEG.
    """
    r_open = BOWL_OPENING_D / 2.0
    rise = (WALL_INNER_R - r_open) * math.tan(math.radians(ONE_PIECE_CONE_DEG))
    return _revolved_wedge([
        [r_open, TOP_BOTTOM],
        [WALL_INNER_R, TOP_BOTTOM - rise],
        [WALL_INNER_R, TOP_BOTTOM],
    ])


def _top_flange_fillet() -> trimesh.Trimesh:
    """The wedge under the top ring's outer edge.

    The ring is wider than the wall it sits on, so merging leaves a 3.4 mm
    downward-facing step right round the drum — 1,780 mm² of ceiling, and by far
    the largest thing needing support in a naive merge. As three parts it never
    mattered, because the ring printed flat on its own plate.
    """
    overhang = STAND_OD / 2.0 - WALL_OUTER_R
    drop = overhang * math.tan(math.radians(ONE_PIECE_CONE_DEG))
    return _revolved_wedge([
        [STAND_OD / 2.0, TOP_BOTTOM],
        [WALL_OUTER_R, TOP_BOTTOM - drop],
        [WALL_OUTER_R, TOP_BOTTOM],
    ])


def build_top_ring(one_piece: bool = False) -> trimesh.Trimesh:
    top_outer = cylinder(STAND_OD / 2, STAND_HEIGHT - TOP_BOTTOM, TOP_BOTTOM)
    # Upright seat ring: conical self-centering seat, then a shallow rim pocket so
    # the metal bowl sits BOWL_RIM_RECESS below the outer top edge.
    seat_z = STAND_HEIGHT - BOWL_RIM_RECESS
    seat_height = seat_z - TOP_BOTTOM
    opening_lower = cylinder(
        BOWL_OPENING_D / 2,
        seat_height + BOWL_RIM_RECESS + 1,
        TOP_BOTTOM - 1,
    )
    opening_slope = trimesh.creation.cone(
        radius=BOWL_OPENING_D / 2,
        radius_top=BOWL_SEAT_D / 2,
        height=seat_height,
        sections=192,
    )
    opening_slope.apply_translation([0, 0, TOP_BOTTOM])
    # Clear above the seat plane out to the seat diameter → recessed rim pocket.
    opening_pocket = cylinder(BOWL_SEAT_D / 2, BOWL_RIM_RECESS + 1.0, seat_z - 0.2)
    pin_holes = []
    for i in range(TOP_JOINT_PIN_COUNT):
        theta = 2 * math.pi * i / TOP_JOINT_PIN_COUNT
        hole = cylinder(TOP_JOINT_HOLE_RADIUS, TOP_JOINT_PIN_HEIGHT + 0.4, TOP_BOTTOM - 0.2)
        hole.apply_translation(
            [TOP_JOINT_RADIUS * math.sin(theta), -TOP_JOINT_RADIUS * math.cos(theta), 0]
        )
        pin_holes.append(hole)
    cutters = [opening_lower, opening_slope, opening_pocket]
    if not one_piece:
        cutters.extend(pin_holes)
    ring = boolean_difference(top_outer, cutters)
    ring.metadata["name"] = "Cooper_Top_Seat_Ring"
    return ring


def build_base(one_piece: bool = False) -> trimesh.Trimesh:
    base_outer = cylinder(STAND_OD / 2, BASE_HEIGHT, 0)
    base_inner = cylinder(68.0, BASE_HEIGHT + 2, -1)
    base = boolean_difference(base_outer, [base_inner])

    # Open annular groove for the upper structure's locating tongue. There is no
    # upper structure to locate when the stand is one body, and the groove is
    # the larger half of the water trap that motivates one-piece at all.
    if not one_piece:
        groove_outer = cylinder(WALL_OUTER_R + 0.35, 4.0, BASE_HEIGHT - 3.5)
        groove_inner = cylinder(WALL_INNER_R - 0.35, 5.0, BASE_HEIGHT - 4.0)
        groove = boolean_difference(groove_outer, [groove_inner])
        base = boolean_difference(base, [groove])
    base.metadata["name"] = "Cooper_Bowl_Base"
    return base


def build_panel(letter_data, one_piece: bool = False) -> trimesh.Trimesh:
    shell_outer = cylinder(WALL_OUTER_R, LATTICE_TOP - LATTICE_BOTTOM, LATTICE_BOTTOM)
    shell_inner = cylinder(WALL_INNER_R, LATTICE_TOP - LATTICE_BOTTOM + 2, LATTICE_BOTTOM - 1)
    shell = boolean_difference(shell_outer, [shell_inner])
    shell = boolean_difference(shell, paw_cutters())

    # Tongue extends below the visible lattice and keys into the base groove.
    # Both disappear in one-piece: the panel simply continues into the base.
    tongue_outer = cylinder(WALL_OUTER_R, 3.0, BASE_HEIGHT - 3.0)
    tongue_inner = cylinder(WALL_INNER_R, 4.0, BASE_HEIGHT - 3.5)
    tongue = boolean_difference(tongue_outer, [tongue_inner])

    # The rail has a structural 4 mm print-leading chamfer plus smaller
    # aesthetic chamfers on the remaining three sides. Angles come from
    # build_letters() so the flat face covers the packed word + margin.
    plaque = beveled_name_rail(
        angle_min=math.radians(-NAME_RAIL_OUTER_DEG),
        angle_flat_min=math.radians(-NAME_RAIL_FLAT_DEG),
        angle_flat_max=math.radians(NAME_RAIL_FLAT_DEG),
        angle_max=math.radians(NAME_RAIL_OUTER_DEG),
    )
    top_pins = []
    _skip_pins = one_piece
    for i in range(TOP_JOINT_PIN_COUNT):
        theta = 2 * math.pi * i / TOP_JOINT_PIN_COUNT
        pin = cylinder(
            TOP_JOINT_PIN_RADIUS,
            TOP_JOINT_PIN_HEIGHT + 0.5,
            LATTICE_TOP - 0.5,
            sections=32,
        )
        pin.apply_translation(
            [TOP_JOINT_RADIUS * math.sin(theta), -TOP_JOINT_RADIUS * math.cos(theta), 0]
        )
        top_pins.append(pin)
    parts = [shell, plaque] if one_piece else [shell, tongue, plaque, *top_pins]
    lattice = boolean_union(parts)

    # Shallow glyph-shaped pockets — letters drop in flush; no pin sockets.
    pocket_cutters = [
        letter_pocket_cutter(item["polygon"], item["arc_center"]) for item in letter_data
    ]
    lattice = boolean_difference(lattice, pocket_cutters)

    lattice.remove_unreferenced_vertices()
    lattice.metadata["name"] = "Cooper_Paw_Panel"
    return lattice


def assembly_letter(item) -> trimesh.Trimesh:
    """Transform a print-oriented letter to its assembled tangent position.

    Seated `glyph_bulge` below the nominal face radius so the glyph's widest
    point finishes flush with the rail rather than standing proud of it. The
    matching pocket floor drops by the same amount.
    """
    mesh = item["mesh"].copy()
    polygon = item.get("polygon")
    sink = glyph_bulge(polygon) if polygon is not None else 0.0
    mesh.apply_transform(
        letter_print_to_assembly_matrix(item["arc_center"], face_r=LETTER_FACE_R - sink)
    )
    return mesh


def visual_bowl() -> trimesh.Trimesh:
    """Approximate the supplied 140 x 95 x 30 mm stainless insert."""
    profile = np.array(
        [
            [0.0, SEAT_Z - BOWL_DEPTH],
            [BOWL_BASE_OD / 2, SEAT_Z - BOWL_DEPTH],
            [57.0, SEAT_Z - 31.0],
            [65.0, SEAT_Z - 7.0],
            [70.0, SEAT_Z],
            [67.0, SEAT_Z + 1.0],
            [62.5, SEAT_Z - 6.0],
            [54.0, SEAT_Z - 30.0],
            [0.0, SEAT_Z - 32.0],
            [0.0, SEAT_Z - BOWL_DEPTH],
        ]
    )
    return trimesh.creation.revolve(profile, sections=192)


def render_meshes(
    meshes_and_colors: list[tuple[trimesh.Trimesh, tuple[int, int, int]]],
    path: Path,
    yaw_deg: float = 24,
    pitch_deg: float = -68,
    size: tuple[int, int] = (1200, 900),
    clip_mesh_indices: set[int] | None = None,
):
    """Lightweight orthographic triangle renderer with supersampling."""
    scale_factor = 2
    width, height = size[0] * scale_factor, size[1] * scale_factor
    image = Image.new("RGB", (width, height), (242, 239, 232))
    draw = ImageDraw.Draw(image)
    draw.ellipse(
        (width * 0.18, height * 0.78, width * 0.82, height * 0.89),
        fill=(210, 203, 192),
    )

    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    rz = trimesh.transformations.rotation_matrix(yaw, [0, 0, 1])
    rx = trimesh.transformations.rotation_matrix(pitch, [1, 0, 0])
    rotation = rx @ rz
    prepared = []
    all_points = []
    for mesh, color in meshes_and_colors:
        transformed = mesh.copy()
        transformed.apply_transform(rotation)
        prepared.append((transformed, color))
        all_points.append(transformed.vertices)
    points = np.vstack(all_points)
    span = np.ptp(points[:, :2], axis=0)
    pixel_scale = min(width * 0.72 / span[0], height * 0.72 / span[1])
    center = (points[:, :2].min(axis=0) + points[:, :2].max(axis=0)) / 2
    screen_center = np.array([width / 2, height * 0.49])
    opening_world_center = np.array([0.0, 0.0, SEAT_Z, 1.0])
    opening_view_center = (rotation @ opening_world_center)[:2]
    opening_screen_center = (opening_view_center - center) * pixel_scale + screen_center
    opening_screen_center[1] = height - opening_screen_center[1]
    opening_rx = (BOWL_OPENING_D / 2 + 1.0) * pixel_scale
    opening_ry = opening_rx * abs(math.cos(pitch))
    light = np.array([-0.3, -0.5, 0.81])
    triangles = []
    for mesh_index, (mesh, color) in enumerate(prepared):
        verts = mesh.vertices
        for face, normal in zip(mesh.faces, mesh.face_normals):
            if normal[2] <= 0:
                continue
            tri = verts[face]
            depth = tri[:, 2].mean() + mesh_index * 1000.0
            brightness = float(np.clip(0.48 + 0.52 * np.dot(normal, light), 0.28, 1.0))
            shaded = tuple(int(np.clip(c * brightness + 12, 0, 255)) for c in color)
            xy = (tri[:, :2] - center) * pixel_scale + screen_center
            xy[:, 1] = height - xy[:, 1]
            clipped = bool(clip_mesh_indices and mesh_index in clip_mesh_indices)
            triangles.append((depth, [tuple(v) for v in xy], shaded, clipped))
    for _, polygon, color, clipped in sorted(triangles, key=lambda value: value[0]):
        if clipped:
            continue
        draw.polygon(polygon, fill=color)
    if clip_mesh_indices:
        clipped_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        clipped_draw = ImageDraw.Draw(clipped_layer)
        for _, polygon, color, clipped in sorted(triangles, key=lambda value: value[0]):
            if clipped:
                clipped_draw.polygon(polygon, fill=(*color, 255))
        ellipse_mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(ellipse_mask).ellipse(
            (
                opening_screen_center[0] - opening_rx,
                opening_screen_center[1] - opening_ry,
                opening_screen_center[0] + opening_rx,
                opening_screen_center[1] + opening_ry,
            ),
            fill=255,
        )
        alpha = Image.fromarray(
            np.minimum(np.asarray(clipped_layer.getchannel("A")), np.asarray(ellipse_mask)).astype(np.uint8)
        )
        clipped_layer.putalpha(alpha)
        image.paste(clipped_layer, (0, 0), clipped_layer)
    image.resize(size, Image.Resampling.LANCZOS).save(path, quality=94)


def write_dimension_svg(path: Path):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">
<rect width="1200" height="760" fill="#f6f3ed"/>
<text x="70" y="70" font-family="Arial" font-size="38" font-weight="700" fill="#3a3028">COOPER Paw-Lattice Bowl Stand</text>
<text x="70" y="108" font-family="Arial" font-size="20" fill="#6d6258">Printable stand + pocket-set name letters</text>
<g transform="translate(125 170)" stroke="#54463a" fill="none" stroke-width="4">
  <path d="M110 410 L110 120 Q110 75 155 75 L545 75 Q590 75 590 120 L590 410" fill="#9c6b42" fill-opacity=".18"/>
  <rect x="95" y="400" width="510" height="45" rx="15" fill="#9c6b42" fill-opacity=".35"/>
  <path d="M110 120 H590 V75 H110 Z" fill="#9c6b42" fill-opacity=".35"/>
  <ellipse cx="350" cy="85" rx="210" ry="38" fill="#c8c8c8" fill-opacity=".55"/>
  <ellipse cx="350" cy="80" rx="160" ry="24" fill="#f6f3ed"/>
  <text x="350" y="285" text-anchor="middle" font-family="Arial" font-size="56" font-weight="700" fill="#efe5d8" stroke="none">COOPER</text>
  <g stroke="#287f8e" stroke-width="3">
    <line x1="95" y1="500" x2="605" y2="500"/><line x1="95" y1="485" x2="95" y2="515"/><line x1="605" y1="485" x2="605" y2="515"/>
    <line x1="680" y1="75" x2="680" y2="445"/><line x1="665" y1="75" x2="695" y2="75"/><line x1="665" y1="445" x2="695" y2="445"/>
  </g>
</g>
<text x="475" y="705" text-anchor="middle" font-family="Arial" font-size="25" fill="#287f8e">170 mm overall diameter</text>
<text x="900" y="445" font-family="Arial" font-size="25" fill="#287f8e">{STAND_HEIGHT:g} mm</text>
<g font-family="Arial" font-size="22" fill="#3a3028">
  <text x="820" y="200">Bowl rim: 140 mm</text>
  <text x="820" y="240">Opening: 133 mm</text>
  <text x="820" y="280">Separate upright seat ring</text>
  <text x="820" y="320">Lattice wall: {WALL_OUTER_R - WALL_INNER_R:g} mm</text>
  <text x="820" y="360">Letter pockets: {LETTER_POCKET_DEPTH:g} mm deep</text>
  <text x="820" y="400">Curved letter backs (rail match)</text>
</g>
</svg>"""
    path.write_text(svg)


def main(one_piece: bool = False):
    MESH.mkdir(parents=True, exist_ok=True)
    VIS.mkdir(parents=True, exist_ok=True)

    if one_piece:
        # The cone eats into the space the bowl's body passes through, so the
        # opening opens up by exactly what the printed ring coupon confirmed.
        global BOWL_OPENING_D
        BOWL_OPENING_D = BOWL_OPENING_D + ONE_PIECE_OPENING_EXTRA

    letters = build_letters()
    base = build_base(one_piece)
    panel = build_panel(letters, one_piece)
    top_ring = build_top_ring(one_piece)

    if one_piece:
        stand = boolean_union(
            [base, panel, top_ring, _seat_cone_fillet(), _top_flange_fillet()]
        )
        stand.metadata["name"] = "Cooper_One_Piece"
        stand_print = stand.copy()
        stand_print.apply_translation([0, 0, -stand.bounds[0, 2]])
        # PLY, not STL, for the printable copy.
        #
        # STL is float32 triangle soup: exporting this union and reading it back
        # loses watertightness, and bambu_project rejects a non-manifold
        # printable mesh outright. PLY keeps the vertices as written, so it
        # survives the round trip — which is why the drum styles already write
        # their bodies as .ply and load them with process=False.
        stand_print.export(MESH / "cooper_one_piece.ply")
        stand.export(MESH / "assembly_one_piece.stl")
    else:
        stand = trimesh.util.concatenate([base, panel, top_ring])
        base.export(MESH / "cooper_base.stl")
        panel_print = panel.copy()
        panel_print.apply_translation([0, 0, -panel.bounds[0, 2]])
        panel_print.export(MESH / "cooper_paw_panel.stl")
        top_ring_print = top_ring.copy()
        top_ring_print.apply_translation([0, 0, -top_ring.bounds[0, 2]])
        top_ring_print.export(MESH / "cooper_top_seat_ring.stl")
        panel.export(MESH / "assembly_paw_panel.stl")
        top_ring.export(MESH / "assembly_top_seat_ring.stl")
    fit_seat = annular_sector(
        BOWL_OPENING_D / 2,
        BOWL_SEAT_D / 2,
        0.0,
        2.4,
        math.radians(-30),
        math.radians(30),
    )
    fit_lip = annular_sector(
        BOWL_SEAT_D / 2,
        76.0,
        0.0,
        5.0,
        math.radians(-30),
        math.radians(30),
    )
    boolean_union([fit_seat, fit_lip]).export(MESH / "OPTIONAL_bowl_fit_gauge_60deg.stl")

    assembly_letters = []
    for index, item in enumerate(letters, start=1):
        print_mesh = item["mesh"]
        print_mesh.export(MESH / f"letter_{index}_{item['character']}.stl")
        assembled = assembly_letter(item)
        assembled.export(MESH / f"assembly_letter_{index}_{item['character']}.stl")
        assembly_letters.append(assembled)

    bowl = visual_bowl()
    bowl.export(MESH / "REFERENCE_ONLY_metal_bowl.stl")
    interior_faces = np.flatnonzero(bowl.face_normals[:, 2] > 0.02)
    exterior_faces = np.flatnonzero(bowl.face_normals[:, 2] <= 0.02)
    bowl_interior = bowl.submesh([interior_faces], append=True, repair=False)
    bowl_exterior = bowl.submesh([exterior_faces], append=True, repair=False)
    render_meshes(
        [
            (bowl_exterior, (190, 196, 198)),
            (stand, (142, 92, 53)),
            (bowl_interior, (190, 196, 198)),
            *[(m, (232, 216, 191)) for m in assembly_letters],
        ],
        VIS / "cooper_bowl_assembled.png",
        clip_mesh_indices={2},
    )

    exploded_letters = []
    for mesh in assembly_letters:
        moved = mesh.copy()
        # Move outward from the front for an exploded attachment view.
        moved.apply_translation([0, -22, 4])
        exploded_letters.append(moved)
    lifted_bowl = bowl.copy()
    lifted_bowl.apply_translation([0, 0, 42])
    render_meshes(
        [(stand, (142, 92, 53)), *[(m, (232, 216, 191)) for m in exploded_letters], (lifted_bowl, (190, 196, 198))],
        VIS / "cooper_bowl_exploded.png",
    )
    write_dimension_svg(VIS / "cooper_bowl_dimensions.svg")

    report = {
        "design": "Cooper Paw-Lattice Bowl Stand",
        "units": "mm",
        "stand": {
            "diameter": STAND_OD,
            "height": STAND_HEIGHT,
            "wall_thickness": WALL_OUTER_R - WALL_INNER_R,
            "base_watertight": bool(base.is_watertight),
            "panel_watertight": bool(panel.is_watertight),
            "top_ring_watertight": bool(top_ring.is_watertight),
            "base_volume_mm3": float(base.volume),
            "panel_volume_mm3": float(panel.volume),
            "top_ring_volume_mm3": float(top_ring.volume),
            "bounds": stand.bounds.round(3).tolist(),
            "base_triangles": int(len(base.faces)),
            "panel_triangles": int(len(panel.faces)),
            "top_ring_triangles": int(len(top_ring.faces)),
            "assembly": "base tongue/groove plus eight pinned top-ring joints",
        },
        "bowl": {
            "rim_outer_diameter": BOWL_RIM_OD,
            "body_outer_diameter": BOWL_BODY_OD,
            "base_diameter": BOWL_BASE_OD,
            "depth": BOWL_DEPTH,
            "stand_opening": BOWL_OPENING_D,
            "seat_diameter": BOWL_SEAT_D,
            "seat_type": "separate upright-printed self-centering conical ring",
            "bowl_rim_recess_mm": BOWL_RIM_RECESS,
            "seat_landing_z": SEAT_Z,
            "seat_slope_height": SEAT_Z - TOP_BOTTOM,
            "seat_slope_angle_degrees": math.degrees(
                math.atan(((BOWL_SEAT_D - BOWL_OPENING_D) / 2) / (SEAT_Z - TOP_BOTTOM))
            ),
            "body_to_wall_radial_clearance": WALL_INNER_R - BOWL_BODY_OD / 2,
            "estimated_suspended_bottom_height": SEAT_Z - BOWL_DEPTH,
        },
        "letters": {
            "text": NAME,
            "height": LETTER_HEIGHT,
            "proud_thickness": LETTER_PROUD,
            "pocket_depth": LETTER_POCKET_DEPTH,
            "pocket_outline_clearance": LETTER_POCKET_CLEARANCE,
            "pocket_floor_gap": LETTER_POCKET_FLOOR_GAP,
            "back_radius": NAME_RAIL_OUTER_R - LETTER_POCKET_DEPTH,
            "face_radius": LETTER_FACE_R,
            "mount": "recessed glyph pockets with cylindrical backs; glue only",
            "tangential_gap": LETTER_GAP,
            "end_margin": LETTER_END_MARGIN,
            "arc_centers": [float(item["arc_center"]) for item in letters],
            "widths": [float(item["width"]) for item in letters],
            "name_rail_flat_deg": NAME_RAIL_FLAT_DEG,
            "name_rail_outer_deg": NAME_RAIL_OUTER_DEG,
        },
    }
    (OUT / "dimensions_and_validation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
