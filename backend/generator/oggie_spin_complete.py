#!/usr/bin/env python3
"""Generate the complete five-arm Oggie Spin Bambu Studio project.

This extends the R188/bayonet mechanism with:

- five wrap-around colour-block arms on a single solid dovetail tongue;
- an integrated underside Matte PLA tapered cantilever snap-tab per arm;
- a pressed outer-race retaining ring;
- a fully printed Tough+ split-collet cartridge;
- 100% infill on every mass-matched colour block;
- one separate colour plate per arm.

Core and arms are a matched revision: friction ribs, rigid side detents and
legacy barb recesses are retired.

Run from the repository root:

    .venv/bin/python backend/generator/oggie_spin_complete.py \
        --out design/modular-spinner/complete
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import math
import shutil
import sys
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from shapely import union_all
from shapely.geometry import Point, Polygon, box

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import oggie_spin_bayonet as base  # noqa: E402
import printability  # noqa: E402

FILAMENTS = [
    ("Marine Blue Matte", "#3A8FCF"),
    ("Lemon Yellow Matte", "#F0C14A"),
    ("Mandarin Orange Matte", "#F26B38"),
    ("Grass Green Matte", "#61B15A"),
    ("Lilac Purple Matte", "#9B7AC7"),
    ("Orange Tough+ cartridge", "#F97316"),
]

# The slot's 2 mm bottom shelf is gone. It stopped the tongue short of the far
# face, which meant the latch had nowhere visible to land -- the root cause of
# two failed revisions. The slot now passes the full core height, the tongue
# goes all the way through, and the female pocket is an open recess in the
# core's underside where you can see the clip and press it.
SLOT_BOTTOM_Z = 0.0
# ...but the tongue still needs something to land on, or the user can simply
# keep pushing and drive the arm straight out the bottom -- the barb's entry
# ramp faces downward, so downward force just cams it out again and it slides
# through. The stop is a rigid ledge at the slot's OUTER end, far from the clip:
# the clip region stays full depth so the barb still reaches the exposed face
# and its recess still opens on the underside. The tongue steps to match and
# lands on the ledge, which becomes the Z datum; the clip then only has to stop
# lift, with 0.08 mm of play above it.
SHELF_OUTER_X = 18.00
SHELF_MAX_X = 19.40   # stop short of the core OD and its foot relief
# 45 deg ramp, so the height also sets how far out the ramp runs. Must land
# inside SHELF_MAX_X: 18.00 + 1.30 = 19.30 < 19.40.
SHELF_HEIGHT = 1.30
ARM_HEIGHT = base.CORE_HEIGHT - SLOT_BOTTOM_Z
# Short colour segments that wrap flush around the Ø40 core instead of long
# radial petals. Tip radius is roughly half the previous 37 mm envelope.
#
# Wrap clearance history: 0.25 mm rattled, so it was closed to 0.12 mm. That
# was the wrong fix -- the rattle came from the wrap being asked to locate the
# arm. Location is the dovetail's job; the wrap is a clearance surface. 0.12 mm
# sits inside realistic P2S surface deviation (+/-0.10-0.15 mm) and the core
# prints flat-face-down with no brim, so elephant's foot ate it and the arm
# bound on the way in. Reopened to 0.30 mm and paired with lead-in chamfers on
# both mating edges plus a bottom-edge relief on the core OD.
WRAP_RADIAL_CLEARANCE = 0.30
WRAP_INNER_R = base.CORE_DIAMETER / 2.0 + WRAP_RADIAL_CLEARANCE
WRAP_OUTER_R = 24.5
WRAP_HALF_ANGLE_DEG = 20.0
ARM_TIP_R = WRAP_OUTER_R
ARM_TONGUE_LEAD_IN = 0.40

# Change 0 -- kill the insertion interference stack.
WRAP_LEAD_IN_CHAMFER = 0.60      # 45 deg on the wrap's inner leading edge
CORE_TOP_EDGE_CHAMFER = 0.40     # 45 deg entry lead-in on the core top OD
CORE_FOOT_RELIEF_DEPTH = 0.35    # dodge elephant's foot on the core bottom OD
CORE_FOOT_RELIEF_HEIGHT = 0.60

# Solid dovetail tongue. The three-rail split (central dovetail + two thin
# guide rails) was tried and did not work well physically; one solid piece is
# better. Friction ribs stay retired -- axial hold is the snap-tab.
# Sets how far the tongue's inner face sits off the slot's inner wall -- and it
# is the ONLY thing that sets how much the arm rocks in the radial-vertical
# plane. Tip wobble is linear in it: 0.20 -> 0.72 mm, 0.14 -> 0.51, 0.10 -> 0.36,
# 0.08 -> 0.29. It does not touch engagement (CLIP_BARB_TIP_X is defined off the
# wall, not off this face), the push-through stop, or the retention bite.
# The wrap clearance has NO effect on rocking; that was measured and is a dead
# end. Do not chase this with a second dovetail rail either -- yaw is already
# 0.017 deg, forty times tighter than the rock.
SLIDE_INNER_RADIAL_CLEARANCE = 0.10
SLIDE_INNER_R = base.ARM_SLOT_INNER_R + SLIDE_INNER_RADIAL_CLEARANCE
# Nominal only: the tongue is clamped to ARM_SLOT_OUTER_R - 0.05 = 20.75, so
# this never actually reaches 21.40. An earlier trim to 21.15 "to clear the tab
# void" was based on misreading the reported value for the built geometry.
SLIDE_OUTER_R = 21.40
# One solid dovetail tongue, uniform clearance on both walls. The old split
# tongue used 0.16/side on the central rail and 0.22/side on the guides; a
# single face splits the difference and there is now only one stack to control.
TONGUE_SIDE_CLEARANCE = 0.18

# ---------------------------------------------------------------------------
# Tongue-tip snap clip.
#
# Third architecture, and the right one. The first two put the spring INSIDE the
# arm's wrap, which meant carving a void through the visible body, controlling
# clearance on both faces of a buried cantilever, and a release nobody could
# reach. Conall's call: make it a discrete male clip plugging into a female
# receiver instead.
#
# So the clip moved to the inner tip of the dovetail tongue -- the far end, deep
# inside the core, as far from the optical pattern as geometry allows. A short
# tangential cantilever carries a barb that points radially inward and snaps
# into a pocket in the slot's inner wall.
#
# What that buys:
#   * the wrap goes back to a plain solid annular sector -- no void, no thin
#     outer wall, nothing carved out of the colour band
#   * the whole mechanism is invisible once assembled
#   * the beam bends in-plane (X-Y: 14.8% elongation, not Z's 4.8%)
#   * the tongue's inner end has ~9.5 mm of tangential width to put a beam in,
#     and no structural job there -- the dovetail's grip is spread along its
#     whole length and is widest further out
#
# Radial budget across the tongue's inner end:
#   13.15  pocket floor in the core
#   13.35  barb tip           <- 0.45 inside the slot wall = the engagement
#   13.80  slot inner wall (ARM_SLOT_INNER_R)
#   14.00  beam inner face    <- the tongue's usual 0.20 slot clearance
#   14.95  beam outer face at the root (0.95 thick, tapering to 0.475 at the tip)
#   15.85  void outer         <- 0.90 of deflection space
#   15.85+ solid tongue, dovetail from here out
#
# NOTE the geometry here is CARTESIAN, not polar. The arm slot is a straight-
# edged trapezoid, so its inner wall is the line x = ARM_SLOT_INNER_R, not an
# arc. Building the beam as an annular sector put its ends at x = 13.39 -- half
# a millimetre inside the wall and buried in solid core. A straight bar is both
# correct and exact: no curved-beam approximation in the strain maths either.
CLIP_BEAM_INNER_R = SLIDE_INNER_R
CLIP_ROOT_THICK = 0.80
CLIP_TIP_THICK = 0.40
CLIP_VOID_OUTER_R = 16.10
# The slot narrows as x increases (it is a dovetail), so a beam that fits at
# rest can foul the side walls once it deflects outward. 4.45 keeps the root
# corners clear at full 0.70 mm travel with 0.13 mm to spare.
CLIP_BEAM_HALF_LENGTH = 4.45
CLIP_ROOT_WEB = 1.20
CLIP_Z0 = 0.00
# Free length is 7.70 mm, shorter than the 11.8 mm the
# wrap-mounted version had, so depth is dialled back to keep pull-off near
# 2.2 N. Strain lands at 1.13% -- under 8% of Matte PLA's 14.8% X-Y elongation
# at break, a 13:1 margin.
CLIP_DEPTH = 3.45  # thinner + deeper: same 2.2 N feel, lower peak stress
CLIP_ENGAGEMENT = 0.50
CLIP_RELEASE_TRAVEL = 0.80
CLIP_RELEASE_MARGIN_FLOOR = 0.20
CLIP_ENTRY_ANGLE_DEG = 30.0
CLIP_RETENTION_ANGLE_DEG = 45.0
CLIP_BARB_CENTRE_Y = 3.15
CLIP_BARB_HALF_WIDTH = 1.30
CLIP_BARB_PLATEAU = 0.40
# Deeper than the 0.45 engagement needs: the extra 1.15 mm is finger room, so
# you can get a nail beside the barb in the open recess and press it outward.
CLIP_POCKET_DEPTH = 1.75
CLIP_POCKET_RADIAL_CLEARANCE = 0.20
CLIP_POCKET_AXIAL_CLEARANCE_BELOW = 0.30
CLIP_POCKET_AXIAL_CLEARANCE_ABOVE = 0.08
CLIP_ENTRY_CHANNEL = True
CLIP_LIP_HEIGHT = 0.90
CLIP_SEATED_INTERFERENCE_MAX_MM3 = 0.001

CLIP_BARB_TIP_X = base.ARM_SLOT_INNER_R - CLIP_ENGAGEMENT
CLIP_BARB_PROUD = CLIP_BEAM_INNER_R - CLIP_BARB_TIP_X
CLIP_FREE_LENGTH = CLIP_BEAM_HALF_LENGTH * 2.0 - CLIP_ROOT_WEB
CLIP_ENTRY_RISE = CLIP_BARB_PROUD * math.tan(math.radians(CLIP_ENTRY_ANGLE_DEG))
CLIP_RETENTION_RISE = CLIP_BARB_PROUD * math.tan(
    math.radians(CLIP_RETENTION_ANGLE_DEG)
)
CLIP_BARB_HEIGHT = CLIP_ENTRY_RISE + CLIP_BARB_PLATEAU + CLIP_RETENTION_RISE
CLIP_BARB_Z0 = CLIP_Z0 + (CLIP_DEPTH - CLIP_BARB_HEIGHT) / 2.0
CLIP_BARB_Z1 = CLIP_BARB_Z0 + CLIP_BARB_HEIGHT
CLIP_BARB_PLATEAU_Z0 = CLIP_BARB_Z0 + CLIP_ENTRY_RISE
CLIP_BARB_PLATEAU_Z1 = CLIP_BARB_PLATEAU_Z0 + CLIP_BARB_PLATEAU
# Only the part of the barb inboard of the slot wall actually engages.
_CLIP_GAP_TO_WALL = CLIP_BEAM_INNER_R - base.ARM_SLOT_INNER_R
CLIP_ENGAGE_Z0 = CLIP_BARB_Z0 + _CLIP_GAP_TO_WALL / (
    CLIP_BARB_PROUD / CLIP_ENTRY_RISE
)
CLIP_ENGAGE_Z1 = CLIP_BARB_PLATEAU_Z1 + CLIP_ENGAGEMENT / (
    CLIP_BARB_PROUD / CLIP_RETENTION_RISE
)

BEARING_RING_SEAT_Z = base.BEARING_SEAT_Z + base.R188_WIDTH
# 45 deg lead-in at the top of the R188 pocket so the bearing self-centres
# instead of catching on the square counterbore step.
BEARING_POCKET_LEAD_IN = 0.40
BEARING_RING_COUNTERBORE_D = 15.15
BEARING_RING_OD = 15.22
BEARING_RING_ID = 10.80
BEARING_RING_HEIGHT = 1.20
BEARING_RING_DIAMETRAL_INTERFERENCE = (
    BEARING_RING_OD - BEARING_RING_COUNTERBORE_D
)

HUB_TO_CORE_GAP = 1.60
PRINTED_AXLE_OD = 6.40
PRINTED_AXLE_BEARING_CLEARANCE = base.R188_ID - PRINTED_AXLE_OD
COLLET_BEAD_OD = 6.80
COLLET_SPLIT_WIDTH = 0.55
COLLET_SPLIT_Z = 14.20
COLLET_INSTALLED_AXIAL_PLAY = 0.05
COLLET_CATCH_FACE_Z = (
    base.CORE_HEIGHT
    + (2.0 * HUB_TO_CORE_GAP)
    + (2.0 * base.HUB_FLANGE_HEIGHT)
)
COLLET_BEAD_Z0 = COLLET_CATCH_FACE_Z + COLLET_INSTALLED_AXIAL_PLAY
# Lead-in ramp on the underside of the bead. At 0.20 mm radial over 0.30 mm of
# rise this was 34 deg from the axis, needing ~26 N (2.6 kgf) to push the collet
# up through the R188 bore -- a lot of force on a small part, next to a bearing
# you do not want to damage. Stretching the ramp to 0.70 mm rise (16 deg) halves
# it to ~14 N. The flat crown shortens to compensate, so the bead's overall
# height and the retention face above it are unchanged.
COLLET_BEAD_PEAK_Z0 = COLLET_BEAD_Z0 + 0.70
COLLET_BEAD_PEAK_Z1 = COLLET_BEAD_Z0 + 1.00
COLLET_TIP_Z = COLLET_BEAD_Z0 + 2.25
COLLET_FINGER_LENGTH = COLLET_TIP_Z - COLLET_SPLIT_Z
RECEIVER_BORE_D = 6.48
RECEIVER_BOSS_OD = 8.40
RECEIVER_BOSS_HEIGHT = base.CORE_FACE_TO_RACE + HUB_TO_CORE_GAP

PRINTED_HUB_LUG_INNER_R = 6.85
PRINTED_HUB_LUG_OUTER_R = 8.05
PRINTED_HUB_LUG_Z = 0.75
PRINTED_HUB_DETENT_OUTER_R = 8.27
PRINTED_CAP_CAVITY_R = 7.25
PRINTED_CAP_CAVITY_DEPTH = 2.80
PRINTED_CAP_ENTRY_OUTER_R = 8.45
# Radial running clearance between lug OD and track OD. This was 0.06 mm --
# 2.7x tighter than the 0.16 mm the earlier M3 cartridge used, which looks like
# an unintended tightening when the bayonet was scaled up for the printed hub.
# At 0.06 mm against P2S feature tolerance of +/-0.10 the lug can simply refuse
# to enter. Restored to 0.16; detent and lock pocket moved with it so the 0.06
# detent interference and 0.14 pocket clearance are unchanged.
PRINTED_CAP_TRACK_OUTER_R = 8.21
PRINTED_CAP_TRACK_Z = 0.55
PRINTED_CAP_TRACK_HEIGHT = 1.50
PRINTED_CAP_LOCK_POCKET_OUTER_R = 8.41
RECEIVER_CAP_HEIGHT = 6.40
RECEIVER_CAP_SOCKET_R = 3.65
RECEIVER_CAP_SOCKET_DEPTH = 5.20
RECEIVER_CAP_SOCKET_RADIAL_CLEARANCE = (
    2.0 * RECEIVER_CAP_SOCKET_R - COLLET_BEAD_OD
)
RECEIVER_CAP_SOCKET_AXIAL_CLEARANCE = (
    RECEIVER_CAP_SOCKET_DEPTH
    - base.HUB_FLANGE_HEIGHT
    - (COLLET_TIP_Z - COLLET_CATCH_FACE_Z)
)

ORIGINAL_MODEL_SETTINGS = base._model_settings
ORIGINAL_CONFIGURE_FILAMENTS = base._configure_filament_slots


def _plate_position(number: int) -> tuple[float, float, float]:
    index = number - 1
    return (
        128.0 + (index % 3) * 312.0,
        128.0 - (index // 3) * 312.0,
        0.0,
    )


PLATES = [
    base.Plate("Complete five-slot core", ((1, 0.0, 0.0, 0.0),), _plate_position(1)),
    base.Plate(
        "R188 outer-race retaining ring",
        ((2, 0.0, 0.0, 0.0),),
        _plate_position(2),
    ),
    base.Plate(
        "Tough+ split-collet cartridge",
        ((3, -13.0, 0.0, 0.0), (4, 13.0, 0.0, 0.0)),
        _plate_position(3),
    ),
    base.Plate(
        "Removable bayonet thumb pads",
        ((5, -13.0, 0.0, 0.0), (6, 13.0, 0.0, 0.0)),
        _plate_position(4),
    ),
    *[
        base.Plate(
            f"Clip-lock colour block {index}",
            ((6 + index, 0.0, 0.0, 0.0),),
            _plate_position(4 + index),
        )
        for index in range(1, 6)
    ],
]

BATCH_PLATES = [
    base.Plate(
        "Five clip-lock colour blocks",
        (
            (1, 0.0, 0.0, 0.0),
            (2, -70.0, -70.0, 0.0),
            (3, 70.0, -70.0, 0.0),
            (4, 70.0, 70.0, 0.0),
            (5, -70.0, 70.0, 0.0),
        ),
        (128.0, 128.0, 0.0),
    )
]


def _slot_polygon(flare: float = 0.0) -> Polygon:
    return Polygon(
        [
            (
                base.ARM_SLOT_INNER_R,
                -(base.ARM_SLOT_INNER_HALF_W + flare),
            ),
            (
                base.ARM_SLOT_OUTER_R,
                -(base.ARM_SLOT_MOUTH_HALF_W + flare),
            ),
            (
                base.ARM_SLOT_OUTER_R,
                base.ARM_SLOT_MOUTH_HALF_W + flare,
            ),
            (
                base.ARM_SLOT_INNER_R,
                base.ARM_SLOT_INNER_HALF_W + flare,
            ),
        ]
    )


def _outer_shelf_polygon(clearance: float = 0.0) -> Polygon:
    """The slot polygon clipped to its outer end -- the ledge the tongue sits on."""
    # Negative clearance widens the cut INBOARD. The tongue's step must start
    # further in than the ledge does, or the strip of tongue between the two
    # lands on top of the ledge and the arm never seats.
    # Bounded on BOTH sides. Running the ledge out to the slot's outer edge
    # takes it into the core OD and its bottom foot relief, where the two
    # chamfers meet at a knife edge and the STL round-trip loses watertightness.
    sliver = _slot_polygon().intersection(
        box(SHELF_OUTER_X + clearance, -20.0, SHELF_MAX_X, 20.0)
    )
    if sliver.is_empty or sliver.geom_type != "Polygon":
        raise RuntimeError("outer shelf polygon is degenerate")
    return sliver


def _slot_mesh() -> trimesh.Trimesh:
    body = base._extrude(
        _slot_polygon(),
        base.CORE_HEIGHT - SLOT_BOTTOM_Z + 0.4,
        SLOT_BOTTOM_Z - 0.2,
    )
    # True 0.4 mm-high lead-in: flare grows continuously toward the top face.
    # Old cores without this still accept the arm because the tongue carries
    # its own bottom chamfer.
    lead = _loft_polygons(
        [
            (
                base.CORE_HEIGHT - ARM_TONGUE_LEAD_IN,
                _slot_polygon(),
            ),
            (
                base.CORE_HEIGHT,
                _slot_polygon(flare=ARM_TONGUE_LEAD_IN),
            ),
        ]
    )
    top_clearance = base._extrude(
        _slot_polygon(flare=ARM_TONGUE_LEAD_IN),
        0.2,
        base.CORE_HEIGHT,
    )
    slot = trimesh.boolean.union(
        [body, lead, top_clearance],
        engine="manifold",
    )
    # Leave the ledge standing at the outer end of the slot.
    # 45 deg ramp, not a square block: printed core-face-down the ledge tapers
    # inward going up, and the tongue's matching step becomes a 45 deg overhang
    # instead of a flat 2.5 mm shelf hanging in air.
    ledge = _loft_polygons(
        [
            (SLOT_BOTTOM_Z - 0.2, _outer_shelf_polygon()),
            (SLOT_BOTTOM_Z - 0.2 + SHELF_HEIGHT, _outer_shelf_polygon(SHELF_HEIGHT)),
        ]
    )
    stepped = trimesh.boolean.difference([slot, ledge], engine="manifold")
    if stepped is None or stepped.is_empty:
        raise RuntimeError("outer shelf removed the slot")
    return stepped


def _clip_pocket_cutters() -> list[trimesh.Trimesh]:
    """Female receiver, open on the core's underside, plus its entry channel.

    This is the pocket you can see on the far face. The tongue passes right
    through the core, the barb springs into this recess and its top face catches
    on the recess roof -- so the arm is held by core material in bearing, and the
    clip is visible and pressable from outside.

    Above the recess sits CLIP_LIP_HEIGHT of full-thickness wall: that lip is the
    only thing the barb cams over. Above the lip a channel runs to the top face
    so the barb drops in undeflected instead of dragging down the whole wall.
    """
    y0 = CLIP_BARB_CENTRE_Y - CLIP_BARB_HALF_WIDTH - CLIP_POCKET_RADIAL_CLEARANCE
    y1 = CLIP_BARB_CENTRE_Y + CLIP_BARB_HALF_WIDTH + CLIP_POCKET_RADIAL_CLEARANCE
    x0 = base.ARM_SLOT_INNER_R - CLIP_POCKET_DEPTH
    x1 = base.ARM_SLOT_INNER_R + 0.20
    # Open at the core's underside: this is the visible female pocket, and the
    # barb's top face catches on its roof. Nothing protrudes past the face.
    pocket_z0 = -0.10
    pocket_z1 = CLIP_ENGAGE_Z1 + CLIP_POCKET_AXIAL_CLEARANCE_ABOVE

    def slab(z0: float, z1: float) -> trimesh.Trimesh:
        return base._extrude(box(x0, y0, x1, y1), z1 - z0, z0)

    cutters = [slab(pocket_z0, pocket_z1)]
    if CLIP_ENTRY_CHANNEL:
        cutters.append(
            slab(pocket_z1 + CLIP_LIP_HEIGHT, base.CORE_HEIGHT + 0.20)
        )
    return cutters


def _core_edge_cutters() -> list[trimesh.Trimesh]:
    """Change 0: bottom-edge relief and top-edge lead-in on the core OD.

    The core prints flat-face-down with no brim and a 0.20 mm initial layer, so
    elephant's foot swells the first few tenths of the OD -- exactly the zone
    the arm wrap has to slide past first. The bottom relief keeps the wrap off
    those layers entirely; the top chamfer gives the wrap somewhere to find
    itself instead of meeting a square edge square-on.
    """
    core_r = base.CORE_DIAMETER / 2.0
    outside = core_r + 0.60
    foot = np.array(
        [
            [core_r - CORE_FOOT_RELIEF_DEPTH, -0.001],
            [core_r, CORE_FOOT_RELIEF_HEIGHT],
            [outside, CORE_FOOT_RELIEF_HEIGHT],
            [outside, -0.001],
            [core_r - CORE_FOOT_RELIEF_DEPTH, -0.001],
        ]
    )[::-1]
    top = np.array(
        [
            [core_r - CORE_TOP_EDGE_CHAMFER, base.CORE_HEIGHT + 0.001],
            [core_r, base.CORE_HEIGHT - CORE_TOP_EDGE_CHAMFER],
            [outside, base.CORE_HEIGHT - CORE_TOP_EDGE_CHAMFER],
            [outside, base.CORE_HEIGHT + 0.001],
            [core_r - CORE_TOP_EDGE_CHAMFER, base.CORE_HEIGHT + 0.001],
        ]
    )[::-1]
    return [
        _revolved_ring(foot),
        _revolved_ring(top),
    ]


def _revolved_ring(profile: np.ndarray) -> trimesh.Trimesh:
    """Revolve a closed (r, z) profile, normalising winding to a solid.

    trimesh.creation.revolve infers face orientation from the profile
    direction, so a profile traced the 'wrong' way yields an inside-out shell
    that the manifold engine rejects with "Not all meshes are volumes!".
    """
    mesh = trimesh.creation.revolve(profile, sections=base.CORE_SECTIONS)
    if mesh.volume < 0.0:
        mesh.invert()
    if not mesh.is_volume:
        raise RuntimeError("revolved ring is not a closed volume")
    return mesh


def _loft_polygons(sections: list[tuple[float, Polygon]]) -> trimesh.Trimesh:
    if len(sections) < 2:
        raise RuntimeError("loft requires at least two polygon sections")
    parts = []
    for (z0, poly0), (z1, poly1) in zip(sections, sections[1:]):
        if z1 <= z0:
            raise RuntimeError("loft sections must increase in Z")
        points = []
        for x, y in poly0.exterior.coords[:-1]:
            points.append([x, y, z0])
        for x, y in poly1.exterior.coords[:-1]:
            points.append([x, y, z1])
        hull = trimesh.convex.convex_hull(np.asarray(points, dtype=float))
        parts.append(hull)
    if len(parts) == 1:
        return parts[0]
    return trimesh.boolean.union(parts, engine="manifold")


def _extrude_with_bottom_chamfer(
    poly: Polygon,
    height: float,
    z0: float,
    chamfer: float,
) -> trimesh.Trimesh:
    if chamfer <= 0.0 or chamfer >= height:
        return base._extrude(poly, height, z0)
    inset = poly.buffer(-chamfer, join_style="mitre")
    if inset.is_empty or inset.geom_type != "Polygon":
        return base._extrude(poly, height, z0)
    lead = _loft_polygons([(z0, inset), (z0 + chamfer, poly)])
    body = base._extrude(poly, height - chamfer, z0 + chamfer)
    return trimesh.boolean.union([lead, body], engine="manifold")


def _annular_sector_polygon(
    inner_r: float,
    outer_r: float,
    a0_deg: float,
    a1_deg: float,
    steps: int = 36,
) -> Polygon:
    angles = np.linspace(math.radians(a0_deg), math.radians(a1_deg), steps + 1)
    outer = [(outer_r * math.cos(a), outer_r * math.sin(a)) for a in angles]
    inner = [
        (inner_r * math.cos(a), inner_r * math.sin(a))
        for a in angles[::-1]
    ]
    return Polygon(outer + inner)


def _weld_shells(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    """Fuse coincident-face shells the boolean engine left as separate bodies.

    Subtracting the slot cutter leaves the push-through ledge standing, but
    manifold emits it as its own shell touching the slot walls with zero gap and
    zero overlap. Bambu Studio unions per-layer footprints so it still prints
    solid -- which is why this was invisible on the first print -- but an
    exported STL made of five kissing shells is one clearance change away from
    being five loose parts on the bed.

    Welding exactly-coincident solids is a hard case for any boolean engine, and
    whether it succeeds depends on unrelated geometry elsewhere in the mesh: the
    plain union worked until a chamfer was added at the bearing pocket, then
    silently started returning three bodies. So try three strategies, cheapest
    and least-disturbing first, and refuse to return anything that is not a
    single body.
    """
    parts = list(mesh.split(only_watertight=False))
    if len(parts) <= 1:
        return mesh
    target = sum(abs(float(p.volume)) for p in parts)

    def one_body(candidate) -> bool:
        return (
            candidate is not None
            and not candidate.is_empty
            and len(candidate.split(only_watertight=False)) == 1
        )

    # 1. straight union of everything at once
    merged = trimesh.boolean.union(parts, engine="manifold")
    if not one_body(merged):
        # 2. accumulate one at a time -- different code path in the engine
        merged = parts[0]
        for part in parts[1:]:
            step = trimesh.boolean.union([merged, part], engine="manifold")
            merged = step if step is not None else merged
    if not one_body(merged):
        # 3. grow each satellite by 2 microns so it OVERLAPS instead of kissing.
        #    Coincident faces are the actual difficulty; a hair of interference
        #    removes the ambiguity. 0.002 mm is far below both the print's
        #    resolution and the 0.12 mm ledge clearance it sits in.
        merged = parts[0]
        for part in parts[1:]:
            grown = part.copy()
            centre = grown.centroid
            grown.apply_translation(-centre)
            grown.apply_scale(1.0 + 0.002 / max(grown.extents))
            grown.apply_translation(centre)
            step = trimesh.boolean.union([merged, grown], engine="manifold")
            merged = step if step is not None else merged
    if not one_body(merged):
        raise RuntimeError(
            f"{name}: {len(parts)} shells would not weld into one body"
        )
    error = abs(float(merged.volume) - target)
    if error > 0.5:
        raise RuntimeError(
            f"{name}: welding moved {error:.3f} mm3 of material -- the shells "
            "are not merely touching, something really is detached"
        )
    return base._finish(merged, name)


def _circle(radius: float, segments: int = 128) -> Polygon:
    return Point(0.0, 0.0).buffer(radius, resolution=segments // 4)


def build_complete_core() -> trimesh.Trimesh:
    body = base._cylinder(
        base.CORE_DIAMETER / 2.0,
        base.CORE_HEIGHT,
        sections=base.CORE_SECTIONS,
    )
    cutters = [
        # R188 pocket to the bearing top.
        base._cylinder(
            base.BEARING_POCKET_DIAMETER / 2.0,
            BEARING_RING_SEAT_Z - base.BEARING_SEAT_Z + 0.2,
            base.BEARING_SEAT_Z,
            sections=128,
        ),
        # Lead-in chamfer at the pocket mouth. Without it the R188 has to step
        # straight off the 15.15 counterbore into the 12.82 pocket across a
        # square 1.17 mm ledge, with nothing to centre it -- so it catches on
        # one edge and reads as "tight" even though the bore is dead on size.
        # This is an ENTRY fix, not a fit fix: the bore is unchanged and the
        # bearing still has 4.3 mm of parallel grip out of its 4.76 mm width.
        _loft_polygons(
            [
                (
                    BEARING_RING_SEAT_Z - BEARING_POCKET_LEAD_IN,
                    _circle(base.BEARING_POCKET_DIAMETER / 2.0),
                ),
                (
                    BEARING_RING_SEAT_Z + 0.01,
                    _circle(
                        base.BEARING_POCKET_DIAMETER / 2.0
                        + BEARING_POCKET_LEAD_IN
                    ),
                ),
            ]
        ),
        # Wider counterbore receives the pressed outer-race retaining ring.
        base._cylinder(
            BEARING_RING_COUNTERBORE_D / 2.0,
            base.CORE_HEIGHT - BEARING_RING_SEAT_Z + 0.2,
            BEARING_RING_SEAT_Z,
            sections=128,
        ),
        base._cylinder(
            base.BEARING_SHOULDER_OPENING / 2.0,
            base.BEARING_SEAT_Z + 0.2,
            -0.1,
            sections=128,
        ),
    ]
    cutters.extend(_core_edge_cutters())
    slot = _slot_mesh()
    clip_pockets = _clip_pocket_cutters()
    for index in range(base.ARM_SLOT_COUNT):
        transform = trimesh.transformations.rotation_matrix(
            math.radians(index * 360.0 / base.ARM_SLOT_COUNT - 90.0),
            [0.0, 0.0, 1.0],
        )
        rotated_slot = slot.copy()
        rotated_slot.apply_transform(transform)
        cutters.append(rotated_slot)
        for pocket in clip_pockets:
            rotated_pocket = pocket.copy()
            rotated_pocket.apply_transform(transform)
            cutters.append(rotated_pocket)
    return _weld_shells(
        base._difference(body, cutters, "complete Oggie Spin core"),
        "complete Oggie Spin core",
    )


def _mirror_y(polygon):
    return Polygon([(x, -y) for x, y in polygon.exterior.coords])


def _slot_half_width_at(radius: float) -> float:
    fraction = (
        (radius - base.ARM_SLOT_INNER_R)
        / (base.ARM_SLOT_OUTER_R - base.ARM_SLOT_INNER_R)
    )
    return (
        base.ARM_SLOT_INNER_HALF_W
        + fraction
        * (base.ARM_SLOT_MOUTH_HALF_W - base.ARM_SLOT_INNER_HALF_W)
    )


def _solid_tongue_polygon() -> Polygon:
    """One solid dovetail tongue that fills the slot with a uniform clearance.

    Replaces the three-rail arrangement (central dovetail plus two thin guide
    rails). Physical testing said the split tongue does not work well and a
    single solid piece does: three separate rails mean three independent
    tolerance stacks and three thin features that can shave, and the gaps
    between them let the arm rock before any one rail takes load. A solid
    tongue is one surface pair, engages the whole slot wall, and cannot rock.

    The slot is a dovetail -- wider at the inner radius than at the mouth --
    so this profile still carries the centrifugal load radially. Axial hold is
    the snap-tab's job, not the tongue's; there are no friction ribs and no
    interference anywhere on this face.
    """
    outer_r = min(SLIDE_OUTER_R, base.ARM_SLOT_OUTER_R - 0.05)
    inner_half = _slot_half_width_at(SLIDE_INNER_R) - TONGUE_SIDE_CLEARANCE
    outer_half = _slot_half_width_at(outer_r) - TONGUE_SIDE_CLEARANCE
    if inner_half <= 0.0 or outer_half <= 0.0:
        raise RuntimeError("solid tongue clearance exceeds the slot width")
    if outer_half >= inner_half:
        raise RuntimeError(
            "solid tongue is not a dovetail -- it would pull out radially"
        )
    return Polygon(
        [
            (SLIDE_INNER_R, -inner_half),
            (outer_r, -outer_half),
            (outer_r, outer_half),
            (SLIDE_INNER_R, inner_half),
        ]
    )


def _tongue_body() -> trimesh.Trimesh:
    tongue = _extrude_with_bottom_chamfer(
        _solid_tongue_polygon(),
        ARM_HEIGHT,
        SLOT_BOTTOM_Z,
        ARM_TONGUE_LEAD_IN,
    )
    # Step the outer end up so it lands on the core's ledge. The cut starts
    # 0.30 mm inboard of the ledge so the two never meet edge-on, and is 0.02 mm
    # deeper so the step face clears the ledge top by a hair rather than being
    # coplanar with it (coplanar faces make booleans unreliable).
    step = _loft_polygons(
        [
            (SLOT_BOTTOM_Z - 0.2, _outer_shelf_polygon(clearance=-0.30)),
            (
                SLOT_BOTTOM_Z - 0.2 + SHELF_HEIGHT + 0.02,
                _outer_shelf_polygon(clearance=SHELF_HEIGHT - 0.12),
            ),
        ]
    )
    stepped = trimesh.boolean.difference([tongue, step], engine="manifold")
    if stepped is None or stepped.is_empty:
        raise RuntimeError("outer shelf step removed the tongue")
    return stepped


def _clip_beam_polygon() -> Polygon:
    """Straight tangential cantilever at the tongue's inner tip.

    Rooted at -Y, free at +Y. Inner face is flat at x = CLIP_BEAM_INNER_R so the
    barb has a clean face to project from; the outer face tapers root-to-tip for
    near-uniform surface strain.
    """
    y_root = -CLIP_BEAM_HALF_LENGTH
    y_tip = CLIP_BEAM_HALF_LENGTH
    steps = 24
    outer = []
    for index in range(steps + 1):
        f = index / steps
        y = y_root + (y_tip - y_root) * f
        thickness = CLIP_ROOT_THICK + (CLIP_TIP_THICK - CLIP_ROOT_THICK) * f
        outer.append((CLIP_BEAM_INNER_R + thickness, y))
    return Polygon(
        [(CLIP_BEAM_INNER_R, y_root)]
        + outer
        + [(CLIP_BEAM_INNER_R, y_tip)]
    )


def _clip_barb_mesh() -> trimesh.Trimesh:
    """Male barb: 30 deg entry ramp below, 45 deg retention face above.

    A Z-loft, so both ramps genuinely exist in the mesh. Points in -x, off the
    beam's inner face, toward the slot's inner wall.
    """
    y0 = CLIP_BARB_CENTRE_Y - CLIP_BARB_HALF_WIDTH
    y1 = CLIP_BARB_CENTRE_Y + CLIP_BARB_HALF_WIDTH

    def section(x_inner: float) -> Polygon:
        return box(x_inner, y0, CLIP_BEAM_INNER_R, y1)

    return _loft_polygons(
        [
            (CLIP_BARB_Z0, section(CLIP_BEAM_INNER_R - 0.001)),
            (CLIP_BARB_PLATEAU_Z0, section(CLIP_BARB_TIP_X)),
            (CLIP_BARB_PLATEAU_Z1, section(CLIP_BARB_TIP_X)),
            (CLIP_BARB_Z1, section(CLIP_BEAM_INNER_R - 0.001)),
        ]
    )


def _clip_body() -> trimesh.Trimesh:
    beam = base._extrude(_clip_beam_polygon(), CLIP_DEPTH, CLIP_Z0)
    return base._union([beam, _clip_barb_mesh()], "tongue-tip snap clip")


def _clip_void_mesh() -> trimesh.Trimesh:
    """The cavity the clip flexes into, cut out of the tongue.

    Runs the full tongue height so the beam is a free-standing bar held only by
    its root web, and so the gap prints as a plain vertical slot with nothing
    bridging over it.
    """
    return base._extrude(
        box(
            CLIP_BEAM_INNER_R,
            -CLIP_BEAM_HALF_LENGTH + CLIP_ROOT_WEB,
            CLIP_VOID_OUTER_R,
            CLIP_BEAM_HALF_LENGTH + 0.30,
        ),
        CLIP_Z0 + CLIP_DEPTH + 0.50 + 0.10,
        -0.10,
    )


def _wrap_lead_in_cutter() -> trimesh.Trimesh:
    """45° chamfer on the wrap bore's leading (Z=0) edge."""
    profile = np.array(
        [
            [WRAP_INNER_R - 0.60, -0.001],
            [WRAP_INNER_R - 0.60, WRAP_LEAD_IN_CHAMFER],
            [WRAP_INNER_R, WRAP_LEAD_IN_CHAMFER],
            [WRAP_INNER_R + WRAP_LEAD_IN_CHAMFER, -0.001],
            [WRAP_INNER_R - 0.60, -0.001],
        ]
    )
    return _revolved_ring(profile)


def build_arm(name: str) -> trimesh.Trimesh:
    # Mesh Z=0 is the installed core bottom. The outer wrap spans the full
    # 14 mm core height so it sits flush on both faces. Three rails sit on the
    # 2 mm shelf; the underside clip provides axial retention.
    wrap = _annular_sector_polygon(
        WRAP_INNER_R,
        WRAP_OUTER_R,
        -WRAP_HALF_ANGLE_DEG,
        WRAP_HALF_ANGLE_DEG,
    )
    positive_pad = Point(
        WRAP_OUTER_R * math.cos(math.radians(16.0)),
        WRAP_OUTER_R * math.sin(math.radians(16.0)),
    ).buffer(1.8, resolution=16)
    negative_pad = _mirror_y(positive_pad)

    wrap_shape = union_all([wrap, positive_pad, negative_pad])
    if wrap_shape.geom_type == "MultiPolygon":
        wrap_parts = [
            base._extrude(Polygon(geom.exterior.coords), base.CORE_HEIGHT, 0.0)
            for geom in wrap_shape.geoms
        ]
        wrap_body = base._union(wrap_parts, f"{name} wrap")
    else:
        wrap_body = base._extrude(wrap_shape, base.CORE_HEIGHT, 0.0)

    # Change 0: 45 deg lead-in on the wrap's inner leading edge (local Z=0 is
    # the leading face during top-down insertion). Previously the wrap met the
    # core square-on-square with 0.12 mm of clearance and no chamfer anywhere.
    wrap_body = trimesh.boolean.difference(
        [wrap_body, _wrap_lead_in_cutter()],
        engine="manifold",
    )
    # The wrap is now a plain solid annular sector. The whole latch lives at the
    # tongue's inner tip, so nothing is carved out of the visible body.
    tongue = trimesh.boolean.difference(
        [_tongue_body(), _clip_void_mesh()],
        engine="manifold",
    )
    if tongue is None or tongue.is_empty:
        raise RuntimeError("clip void removed the tongue")
    installed = base._union(
        [wrap_body, tongue, _clip_body()],
        name,
    )
    # Print with the flush top face on the bed. Leaving the wrap-bottom-down
    # made the slot tongue a large unsupported overhang above the 2 mm shelf.
    return _flip_arm_for_print(installed, name)


def _flip_arm_for_print(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    """Turn the arm over for printing -- with a ROTATION, not a reflection.

    This used to scale Z by -1, which has determinant -1: a mirror. Every
    validator passed because _arm_installed_orientation applied the same mirror
    and cancelled it, so the model was self-consistent. But the exported STL was
    the mirror image of the arm. Print that, physically turn it over -- which is
    a rotation -- and the barb lands at -y while the core's pocket is at +y. The
    parts can never clip together.

    A 180 deg rotation about X is what turning a part over actually is:
    (x, y, z) -> (x, -y, -z), then lifted back onto the bed.

    ...and the arm no longer needs turning over at all. The flip existed to keep
    the slot tongue off an overhang above the old 2 mm shelf, and that shelf is
    gone. Worse, it put the clip beam's first print layer 10.35 mm up, hanging
    0.60 mm over air anchored only at its root -- the slicer flags it as a
    floating cantilever, and a drooped first layer touching the tongue below
    would weld the beam solid. Printed the right way up, the beam's first layer
    lands on the build plate and the optical inlay ends up on the top surface.
    """
    return base._finish(mesh.copy(), f"{name} print orientation")


def _arm_installed_orientation(print_oriented: trimesh.Trimesh) -> trimesh.Trimesh:
    return _flip_arm_for_print(
        print_oriented,
        print_oriented.metadata.get("name", "arm"),
    )


def build_bearing_ring() -> trimesh.Trimesh:
    return base._annulus(
        BEARING_RING_OD,
        BEARING_RING_ID,
        BEARING_RING_HEIGHT,
        "R188 outer-race retaining ring",
    )


def _printed_hub_flange(name: str) -> trimesh.Trimesh:
    flange = base._cylinder(
        base.HUB_FLANGE_DIAMETER / 2.0,
        base.HUB_FLANGE_HEIGHT,
        sections=128,
    )
    lugs = []
    for angle in (0.0, 120.0, 240.0):
        lugs.append(
            base._annular_sector(
                PRINTED_HUB_LUG_INNER_R,
                PRINTED_HUB_LUG_OUTER_R,
                angle - base.HUB_LUG_ANGLE / 2.0,
                angle + base.HUB_LUG_ANGLE / 2.0,
                base.HUB_LUG_HEIGHT,
                PRINTED_HUB_LUG_Z,
                steps=8,
            )
        )
        lugs.append(
            base._annular_sector(
                PRINTED_HUB_LUG_OUTER_R - 0.10,
                PRINTED_HUB_DETENT_OUTER_R,
                angle - base.HUB_DETENT_ANGLE / 2.0,
                angle + base.HUB_DETENT_ANGLE / 2.0,
                base.HUB_LUG_HEIGHT,
                PRINTED_HUB_LUG_Z,
                steps=4,
            )
        )
    return base._union([flange, *lugs], name)


def _collet_bead() -> trimesh.Trimesh:
    profile = np.array(
        [
            [0.0, COLLET_BEAD_Z0],
            [PRINTED_AXLE_OD / 2.0, COLLET_BEAD_Z0],
            [COLLET_BEAD_OD / 2.0, COLLET_BEAD_PEAK_Z0],
            [COLLET_BEAD_OD / 2.0, COLLET_BEAD_PEAK_Z1],
            [PRINTED_AXLE_OD * 0.42, COLLET_TIP_Z],
            [0.0, COLLET_TIP_Z],
        ]
    )
    return trimesh.creation.revolve(profile, cap=True, sections=128)


def build_collet_hub() -> trimesh.Trimesh:
    flange = _printed_hub_flange("split-collet hub flange")
    spacer = base._cylinder(
        RECEIVER_BOSS_OD / 2.0,
        RECEIVER_BOSS_HEIGHT,
        base.HUB_FLANGE_HEIGHT,
        sections=96,
    )
    shaft = base._cylinder(
        PRINTED_AXLE_OD / 2.0,
        COLLET_TIP_Z - base.HUB_FLANGE_HEIGHT,
        base.HUB_FLANGE_HEIGHT,
        sections=96,
    )
    body = base._union(
        [flange, spacer, shaft, _collet_bead()],
        "Tough+ split-collet through-axle blank",
    )
    slot_height = COLLET_TIP_Z - COLLET_SPLIT_Z + 0.2
    slots = [
        base._extrude(
            box(
                -COLLET_SPLIT_WIDTH / 2.0,
                -COLLET_BEAD_OD,
                COLLET_SPLIT_WIDTH / 2.0,
                COLLET_BEAD_OD,
            ),
            slot_height,
            COLLET_SPLIT_Z,
        ),
        base._extrude(
            box(
                -COLLET_BEAD_OD,
                -COLLET_SPLIT_WIDTH / 2.0,
                COLLET_BEAD_OD,
                COLLET_SPLIT_WIDTH / 2.0,
            ),
            slot_height,
            COLLET_SPLIT_Z,
        ),
    ]
    # Round both slot roots so cyclic collet strain does not terminate at a
    # sharp printed corner.
    slots.extend(
        [
            trimesh.creation.cylinder(
                radius=COLLET_SPLIT_WIDTH / 2.0,
                segment=[
                    [-COLLET_BEAD_OD, 0.0, COLLET_SPLIT_Z],
                    [COLLET_BEAD_OD, 0.0, COLLET_SPLIT_Z],
                ],
                sections=32,
            ),
            trimesh.creation.cylinder(
                radius=COLLET_SPLIT_WIDTH / 2.0,
                segment=[
                    [0.0, -COLLET_BEAD_OD, COLLET_SPLIT_Z],
                    [0.0, COLLET_BEAD_OD, COLLET_SPLIT_Z],
                ],
                sections=32,
            ),
        ]
    )
    return base._difference(body, slots, "Tough+ split-collet through-axle hub")


def build_receiver_hub() -> trimesh.Trimesh:
    flange = _printed_hub_flange("receiver hub flange")
    receiver = base._cylinder(
        RECEIVER_BOSS_OD / 2.0,
        RECEIVER_BOSS_HEIGHT,
        base.HUB_FLANGE_HEIGHT,
        sections=96,
    )
    body = base._union(
        [flange, receiver],
        "Tough+ through-bore receiver hub blank",
    )
    bore = base._cylinder(
        RECEIVER_BORE_D / 2.0,
        base.HUB_FLANGE_HEIGHT + RECEIVER_BOSS_HEIGHT + 0.4,
        -0.2,
        sections=96,
    )
    return base._difference(body, [bore], "Tough+ through-bore receiver hub")


def _flip_cap_for_print(
    mesh: trimesh.Trimesh,
    height: float,
    name: str,
) -> trimesh.Trimesh:
    flipped = mesh.copy()
    matrix = np.eye(4)
    matrix[2, 2] = -1.0
    matrix[2, 3] = height
    flipped.apply_transform(matrix)
    return base._finish(flipped, f"{name} print orientation")


def build_printed_thumb_pad(
    name: str,
    *,
    height: float = base.CAP_HEIGHT,
    central_socket_depth: float = 0.0,
) -> trimesh.Trimesh:
    body = base._cylinder(base.CAP_DIAMETER / 2.0, height, sections=160)
    cutters = [
        base._cylinder(
            PRINTED_CAP_CAVITY_R,
            PRINTED_CAP_CAVITY_DEPTH + 0.1,
            -0.1,
            sections=128,
        )
    ]
    if central_socket_depth > 0.0:
        cutters.append(
            base._cylinder(
                RECEIVER_CAP_SOCKET_R,
                central_socket_depth + 0.1,
                -0.1,
                sections=96,
            )
        )
    for angle in (0.0, 120.0, 240.0):
        cutters.append(
            base._annular_sector(
                PRINTED_HUB_LUG_INNER_R - 0.05,
                PRINTED_CAP_ENTRY_OUTER_R,
                angle - base.CAP_ENTRY_ANGLE / 2.0,
                angle + base.CAP_ENTRY_ANGLE / 2.0,
                PRINTED_CAP_CAVITY_DEPTH + 0.1,
                -0.1,
                steps=10,
            )
        )
        cutters.append(
            base._annular_sector(
                PRINTED_HUB_LUG_INNER_R - 0.05,
                PRINTED_CAP_TRACK_OUTER_R,
                angle - base.CAP_LOCK_ROTATION_DEG - 5.0,
                angle + base.CAP_ENTRY_ANGLE / 2.0,
                PRINTED_CAP_TRACK_HEIGHT,
                PRINTED_CAP_TRACK_Z,
                steps=24,
            )
        )
        cutters.append(
            base._annular_sector(
                PRINTED_HUB_LUG_INNER_R - 0.05,
                PRINTED_CAP_LOCK_POCKET_OUTER_R,
                angle
                - base.CAP_LOCK_ROTATION_DEG
                - base.CAP_ENTRY_ANGLE / 2.0,
                angle
                - base.CAP_LOCK_ROTATION_DEG
                + base.CAP_ENTRY_ANGLE / 2.0,
                PRINTED_CAP_TRACK_HEIGHT,
                PRINTED_CAP_TRACK_Z,
                steps=10,
            )
        )
    pad = base._difference(body, cutters, name)
    return _flip_cap_for_print(pad, height, name)


def build_meshes() -> list[tuple[str, trimesh.Trimesh, int]]:
    return [
        ("Complete Oggie Spin core", build_complete_core(), 1),
        ("R188 outer-race retaining ring", build_bearing_ring(), 1),
        ("Tough+ split-collet through-axle hub", build_collet_hub(), 6),
        ("Tough+ through-bore receiver hub", build_receiver_hub(), 6),
        (
            "Socketed thumb pad 1",
            build_printed_thumb_pad(
                "socketed thumb pad 1",
                height=RECEIVER_CAP_HEIGHT,
                central_socket_depth=RECEIVER_CAP_SOCKET_DEPTH,
            ),
            2,
        ),
        (
            "Socketed thumb pad 2",
            build_printed_thumb_pad(
                "socketed thumb pad 2",
                height=RECEIVER_CAP_HEIGHT,
                central_socket_depth=RECEIVER_CAP_SOCKET_DEPTH,
            ),
            2,
        ),
        *[
            (
                f"Clip-lock colour block {index}",
                build_arm(f"Clip-lock colour block {index}"),
                index,
            )
            for index in range(1, 6)
        ],
    ]


def _preview_png(plate_number: int, size: int = 512) -> bytes:
    image = Image.new("RGBA", (size, size), (244, 241, 234, 255))
    draw = ImageDraw.Draw(image)
    draw.text((26, 22), f"Oggie Spin complete · plate {plate_number}", fill="#252A32")
    if plate_number == 1:
        draw.ellipse((112, 112, 400, 400), fill=FILAMENTS[0][1], outline="#252A32", width=5)
        draw.ellipse((210, 210, 302, 302), fill="#FFFFFF", outline="#252A32", width=4)
    elif plate_number == 2:
        draw.ellipse((160, 160, 352, 352), fill=FILAMENTS[0][1], outline="#252A32", width=5)
        draw.ellipse((218, 218, 294, 294), fill="#FFFFFF", outline="#252A32", width=4)
        draw.text((174, 380), "OUTER-RACE RING", fill="#252A32")
    elif plate_number == 3:
        colour = FILAMENTS[5][1]
        for cx in (164, 348):
            draw.ellipse((cx - 62, 194, cx + 62, 318), fill=colour, outline="#252A32", width=5)
        draw.rounded_rectangle((150, 74, 178, 256), radius=10, fill=colour, outline="#252A32", width=4)
        draw.text((144, 360), "TOUGH+ SPLIT COLLET", fill="#252A32")
    elif plate_number == 4:
        colour = FILAMENTS[1][1]
        for cx in (174, 338):
            draw.ellipse((cx - 76, 180, cx + 76, 332), fill=colour, outline="#252A32", width=5)
            draw.ellipse((cx - 50, 206, cx + 50, 306), fill="#FFFFFF", outline="#252A32", width=3)
    colour = FILAMENTS[plate_number - 5][1]
    if plate_number >= 5:
        draw.ellipse((146, 146, 366, 366), fill="#D8DEE8", outline="#252A32", width=4)
        draw.pieslice(
            (118, 118, 394, 394),
            start=250,
            end=290,
            fill=colour,
            outline="#252A32",
            width=4,
        )
        draw.ellipse((196, 196, 316, 316), fill="#F4F1EA", outline="#252A32", width=3)
        draw.text((150, 370), "THREE-RAIL · UNDERSIDE CLIP", fill="#252A32")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# --- Bambu PLA Matte, published TDS (X-Y / in-layer-plane values) -----------
MATTE_FLEX_MODULUS_MPA = 2360.0      # +/- 250
MATTE_FLEX_STRENGTH_MPA = 53.0       # +/- 6
PLA_ON_PLA_FRICTION = 0.35


def clip_forces(engagement: float = None) -> dict:
    """Snap-clip forces derived from the built constants, never hand-written.

    Every force figure in the docs must come from here. Two revisions carried a
    2.20 N pull-off in prose that the geometry never supported -- it had been
    computed from the total barb protrusion (0.65 mm) instead of the deflection
    the core actually demands (0.45 mm, barb crest x13.35 against lip x13.80).

    Tapered cantilever, root t to tip t/2:
        F = E*b*t^3*y / (6*L^3)        eps = 1.09*t*y / L^2
    Ramp force is F*(mu + tan a) / (1 - mu*tan a).
    """
    y = CLIP_ENGAGEMENT if engagement is None else engagement
    b, t, L = CLIP_DEPTH, CLIP_ROOT_THICK, CLIP_FREE_LENGTH
    E, S, mu = MATTE_FLEX_MODULUS_MPA, MATTE_FLEX_STRENGTH_MPA, PLA_ON_PLA_FRICTION

    # The textbook tapered-beam formula puts the load at the free tip. Our barb
    # sits inboard of the tip, so the real lever arm is root-to-barb, and the
    # real force is HIGHER than the tip formula reports. Neither end of that
    # bracket is the truth; quote both rather than pick one and be quietly wrong.
    root_y = -(CLIP_BEAM_HALF_LENGTH - CLIP_ROOT_WEB)
    L_barb = CLIP_BARB_CENTRE_Y - root_y

    def ramp(force: float, deg: float) -> float:
        a = math.tan(math.radians(deg))
        return force * (mu + a) / (1.0 - mu * a)

    def deflect(modulus: float, span: float = None) -> float:
        span = L if span is None else span
        return modulus * b * t**3 * y / (6.0 * span**3)

    F = deflect(E)
    F_barb = deflect(E, L_barb)
    strain = 1.09 * t * y / (L_barb * L_barb)
    stress = strain * E
    return {
        "basis": "Bambu PLA Matte TDS X-Y: 2360 MPa flexural modulus, 53 MPa flexural strength",
        "deflection_mm": round(y, 3),
        "beam_root_thickness_mm": t,
        "beam_tip_thickness_mm": CLIP_TIP_THICK,
        "beam_depth_mm": b,
        "beam_free_length_mm": round(L, 3),
        "barb_lever_arm_mm": round(L_barb, 3),
        "deflection_force_N": [round(F, 3), round(F_barb, 3)],
        "insertion_force_N": [
            round(ramp(F, CLIP_ENTRY_ANGLE_DEG), 2),
            round(ramp(F_barb, CLIP_ENTRY_ANGLE_DEG), 2),
        ],
        "pull_off_force_N": [
            round(ramp(F, CLIP_RETENTION_ANGLE_DEG), 2),
            round(ramp(F_barb, CLIP_RETENTION_ANGLE_DEG), 2),
        ],
        "force_bracket_note": (
            "[load-at-tip, load-at-barb]. The truth is between them and nearer "
            "the upper figure; the barb is inboard of the beam tip"
        ),
        "barb_contact_area_mm2": round(
            2.0 * CLIP_BARB_HALF_WIDTH * CLIP_DEPTH
            / math.sin(math.radians(CLIP_RETENTION_ANGLE_DEG)), 2
        ),
        "surface_strain_pct": round(strain * 100.0, 3),
        "peak_bending_stress_MPa": round(stress, 2),
        "stress_margin_to_flexural_strength": round(S / stress, 2),
        "note": (
            "compare bending stress to FLEXURAL STRENGTH, never strain to "
            "tensile elongation at break -- that error once reported a 12:1 "
            "margin where the real one was under 2:1"
        ),
    }


def audit_printability(
    built: list[tuple[str, trimesh.Trimesh]],
    spec: printability.PrintSpec | None = None,
) -> dict:
    """Run every part through the manufacturability pass before export.

    Geometric validation compares the model to itself and cannot see anything
    that only exists once a part is oriented on a bed and built layer by layer.
    That gap is how a mirrored export, a missing push-through stop and a
    floating cantilever all reached the slicer. This closes it: the build now
    refuses to emit a part the slicer would reject.
    """
    spec = spec or printability.PrintSpec()
    reports = []
    for name, mesh in built:
        if "inlay" in name.lower():
            continue  # inlays are thin by design and sit inside their recess
        reports.append(printability.audit(mesh, spec, name=name))
    blocking = [r for r in reports if r.blocking]
    if blocking:
        raise RuntimeError(
            "printability audit failed:\n"
            + "\n".join(r.summary() for r in blocking)
        )
    return {
        "spec": {
            "nozzle_mm": spec.nozzle,
            "layer_height_mm": spec.layer_height,
            "overhang_limit_deg": spec.overhang_limit_deg,
            "min_feature_mm": spec.min_feature,
            "min_anchor_ratio": spec.min_anchor_ratio,
        },
        "parts": [r.as_dict() for r in reports],
        "blocking": False,
    }


def _validate_clip_lock_fit(
    core: trimesh.Trimesh,
    arm: trimesh.Trimesh,
) -> dict:
    # Exported arm meshes are print-flipped (top face on the bed). Restore the
    # installed frame before clearance checks.
    installed = _arm_installed_orientation(arm)
    # NO RELIEF MASK. The previous revision subtracted a generous box around the
    # hook before measuring interference, which is precisely why it could not
    # fail: that mask covered the 0.50 mm the stem overran its pocket by, so a
    # hard jam against solid core was reported as "unexpected interference 0.0"
    # and its 0.33 mm3 was accepted as "seated engagement".
    #
    # A correctly seated snap-fit touches nothing. The hook sits in its pocket
    # with clearance on every face, so the honest expected value is zero and we
    # measure against the true core solid.
    relieved_core = core

    placed = []
    intersections = []
    unexpected_intersections = []
    for index in range(base.ARM_SLOT_COUNT):
        rotated = installed.copy()
        rotated.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(index * 72.0 - 90.0),
                [0.0, 0.0, 1.0],
            )
        )
        placed.append(rotated)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            overlap = trimesh.boolean.intersection(
                [core, rotated],
                engine="manifold",
            )
            volume = (
                0.0
                if overlap is None or overlap.is_empty
                else round(float(overlap.volume), 6)
            )
        intersections.append(volume)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            unexpected_overlap = trimesh.boolean.intersection(
                [relieved_core, rotated],
                engine="manifold",
            )
            unexpected_volume = (
                0.0
                if unexpected_overlap is None or unexpected_overlap.is_empty
                else round(float(unexpected_overlap.volume), 6)
            )
        unexpected_intersections.append(unexpected_volume)
    maximum = max(intersections)
    if maximum > CLIP_SEATED_INTERFERENCE_MAX_MM3:
        raise RuntimeError(
            "installed snap-tab arm interferes with the core by "
            f"{maximum:.6f} mm³ (a seated snap-fit must touch nothing; "
            f"limit {CLIP_SEATED_INTERFERENCE_MAX_MM3:.3f} mm³)"
        )
    unexpected_maximum = max(unexpected_intersections)
    if unexpected_maximum > CLIP_SEATED_INTERFERENCE_MAX_MM3:
        raise RuntimeError(
            "installed snap-tab arm has interference of "
            f"{unexpected_maximum:.6f} mm³ against the true core solid"
        )

    neighbour_volumes = []
    for index in range(base.ARM_SLOT_COUNT):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            overlap = trimesh.boolean.intersection(
                [placed[index], placed[(index + 1) % base.ARM_SLOT_COUNT]],
                engine="manifold",
            )
            volume = (
                0.0
                if overlap is None or overlap.is_empty
                else round(float(overlap.volume), 6)
            )
        neighbour_volumes.append(volume)
    neighbour_maximum = max(neighbour_volumes)
    if neighbour_maximum > 0.001:
        raise RuntimeError(
            "adjacent wrap-around arms collide by "
            f"{neighbour_maximum:.6f} mm³"
        )

    # ------------------------------------------------------------------
    # Release, retention and freedom. The old revision checked only that a
    # translated latch stopped overlapping; it never checked that the margin
    # was meaningful, that the arm was actually held, or that the cantilever
    # was free to move at all.
    # ------------------------------------------------------------------
    slot0 = trimesh.transformations.rotation_matrix(
        math.radians(-90.0), [0.0, 0.0, 1.0]
    )
    # The barb retracts in +x (away from the slot's inner wall) to release.
    outward = np.asarray(slot0[:3, :3] @ np.array([1.0, 0.0, 0.0]), dtype=float)

    def _overlap(a: trimesh.Trimesh, b: trimesh.Trimesh) -> float:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            hit = trimesh.boolean.intersection([a, b], engine="manifold")
        if hit is None or hit.is_empty:
            return 0.0
        return round(float(hit.volume), 6)

    # 1. Retention. Lift the seated arm by half the engagement: the barb must
    #    drive into the pocket roof. Zero here means the clip does nothing.
    lifted = placed[0].copy()
    lifted.apply_translation([0.0, 0.0, CLIP_ENGAGEMENT * 0.5])
    retention_bite = _overlap(core, lifted)
    if retention_bite <= 0.0:
        raise RuntimeError(
            "snap clip does not retain: lifting the seated arm by "
            f"{CLIP_ENGAGEMENT * 0.5:.2f} mm produces no barb/pocket bite"
        )

    # 2. Release travel margin against the true requirement.
    required_travel = base.ARM_SLOT_INNER_R - CLIP_BARB_TIP_X
    release_margin = round(CLIP_RELEASE_TRAVEL - required_travel, 4)
    if release_margin < CLIP_RELEASE_MARGIN_FLOOR:
        raise RuntimeError(
            f"snap clip release margin {release_margin:.3f} mm is below the "
            f"{CLIP_RELEASE_MARGIN_FLOOR:.2f} mm floor"
        )

    # 3. The deflected clip must clear the core at the design travel.
    latch = _clip_body()
    latch.apply_transform(slot0)
    released = latch.copy()
    released.apply_translation(outward * CLIP_RELEASE_TRAVEL)
    released_volume = _overlap(core, released)
    if released_volume > CLIP_SEATED_INTERFERENCE_MAX_MM3:
        raise RuntimeError(
            f"snap clip release travel {CLIP_RELEASE_TRAVEL:.2f} mm does not "
            f"clear the core ({released_volume:.6f} mm³ still overlapping)"
        )

    # 4. Freedom. Walk the beam span and confirm open air on BOTH faces
    #    everywhere outside the root web. Clearing only the outer face leaves
    #    the inner face welded for its whole length -- a defect no volume check
    #    catches, because a weld adds no interference.
    installed_arm = _arm_installed_orientation(arm)
    probe_z = CLIP_Z0 + CLIP_DEPTH / 2.0
    y_lo = -CLIP_BEAM_HALF_LENGTH + CLIP_ROOT_WEB + 0.40
    y_hi = CLIP_BEAM_HALF_LENGTH - 0.30
    xs = np.arange(
        CLIP_BEAM_INNER_R - 0.40, CLIP_VOID_OUTER_R + 0.40, 0.025
    )
    inner_gap_min = None
    outer_gap_min = None
    for step in range(13):
        y = y_lo + (y_hi - y_lo) * step / 12.0
        solid = installed_arm.contains(
            np.array([[x, y, probe_z] for x in xs])
        )
        runs, current = [], None
        for x, filled in zip(xs, solid):
            if filled and current is None:
                current = [x, x]
            elif filled:
                current[1] = x
            elif current is not None:
                runs.append(tuple(current))
                current = None
        if current is not None:
            runs.append(tuple(current))
        beam_runs = [r for r in runs if r[1] <= CLIP_VOID_OUTER_R - 0.02]
        if not beam_runs:
            raise RuntimeError(
                f"snap clip beam missing at y={y:.2f} -- the void removed it"
            )
        beam = max(beam_runs, key=lambda r: r[1])
        in_barb_window = (
            CLIP_BARB_CENTRE_Y - CLIP_BARB_HALF_WIDTH - 0.40
            <= y
            <= CLIP_BARB_CENTRE_Y + CLIP_BARB_HALF_WIDTH + 0.40
        )
        outer_gap = CLIP_VOID_OUTER_R - beam[1]
        outer_gap_min = (
            outer_gap if outer_gap_min is None else min(outer_gap_min, outer_gap)
        )
        if outer_gap < required_travel:
            raise RuntimeError(
                f"snap clip cannot deflect at y={y:.2f}: only "
                f"{outer_gap:.3f} mm of travel space, needs {required_travel:.2f}"
            )
        if not in_barb_window:
            inner_gap = beam[0] - base.ARM_SLOT_INNER_R
            inner_gap_min = (
                inner_gap
                if inner_gap_min is None
                else min(inner_gap_min, inner_gap)
            )
            if inner_gap < 0.10:
                raise RuntimeError(
                    f"snap clip inner face is welded at y={y:.2f} "
                    f"(gap {inner_gap:.3f} mm)"
                )

    return {
        "installed_intersection_volume_mm3": intersections,
        "maximum_intersection_volume_mm3": maximum,
        "unexpected_intersection_volume_mm3": unexpected_intersections,
        "maximum_unexpected_intersection_volume_mm3": unexpected_maximum,
        "released_latch_intersection_volume_mm3": released_volume,
        "retention_bite_volume_mm3": retention_bite,
        "tongue_side_clearance_mm": TONGUE_SIDE_CLEARANCE,
        "clip_engagement_mm": CLIP_ENGAGEMENT,
        "clip_release_travel_mm": CLIP_RELEASE_TRAVEL,
        "clip_release_required_mm": round(required_travel, 3),
        "clip_release_margin_mm": release_margin,
        "clip_entry_angle_deg": CLIP_ENTRY_ANGLE_DEG,
        "clip_retention_angle_deg": CLIP_RETENTION_ANGLE_DEG,
        "clip_minimum_inner_gap_mm": round(inner_gap_min, 3),
        "clip_minimum_travel_space_mm": round(outer_gap_min, 3),
        "clip_axial_play_mm": CLIP_POCKET_AXIAL_CLEARANCE_ABOVE,
        "clip_free_cantilever": True,
        "installed_clear_of_core": True,
        "adjacent_arm_intersection_volume_mm3": neighbour_volumes,
        "adjacent_arms_clear": True,
        "wrap_inner_radius_mm": WRAP_INNER_R,
        "wrap_outer_radius_mm": WRAP_OUTER_R,
        "wrap_half_angle_deg": WRAP_HALF_ANGLE_DEG,
        "wrap_height_mm": base.CORE_HEIGHT,
        "slot_insert_height_mm": ARM_HEIGHT,
        "core_radial_clearance_mm": round(
            WRAP_INNER_R - base.CORE_DIAMETER / 2.0,
            3,
        ),
        "matched_revision": True,
    }


def _assembled_cartridge(
    collet: trimesh.Trimesh,
    receiver: trimesh.Trimesh,
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    lower = collet.copy()
    lower.apply_translation(
        [0.0, 0.0, -HUB_TO_CORE_GAP - base.HUB_FLANGE_HEIGHT]
    )
    upper = receiver.copy()
    upper.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.pi,
            [1.0, 0.0, 0.0],
        )
    )
    upper.apply_translation(
        [
            0.0,
            0.0,
            base.CORE_HEIGHT
            + HUB_TO_CORE_GAP
            + base.HUB_FLANGE_HEIGHT,
        ]
    )
    return lower, upper


def _validate_collet_cartridge(
    collet: trimesh.Trimesh,
    receiver: trimesh.Trimesh,
) -> dict:
    lower, upper = _assembled_cartridge(collet, receiver)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        overlap = trimesh.boolean.intersection(
            [lower, upper],
            engine="manifold",
        )
        installed_overlap = (
            0.0
            if overlap is None or overlap.is_empty
            else round(float(overlap.volume), 6)
        )
    if installed_overlap > 0.001:
        raise RuntimeError(
            "installed split-collet and receiver have rigid interference "
            f"({installed_overlap:.6f} mm³)"
        )
    if not -0.08 <= PRINTED_AXLE_BEARING_CLEARANCE <= 0.15:
        raise RuntimeError("printed axle/R188 fit is outside the trial range")
    if COLLET_BEAD_OD <= RECEIVER_BORE_D:
        raise RuntimeError("split-collet bead cannot retain behind receiver face")
    return {
        "installed_intersection_volume_mm3": installed_overlap,
        "installed_clear": True,
        "axle_diameter_mm": PRINTED_AXLE_OD,
        "bearing_bore_diameter_mm": base.R188_ID,
        "bearing_diametral_clearance_mm": round(
            PRINTED_AXLE_BEARING_CLEARANCE,
            3,
        ),
        "bearing_diametral_interference_mm": round(
            max(0.0, -PRINTED_AXLE_BEARING_CLEARANCE),
            3,
        ),
        "bearing_fit_class": (
            "light interference trial"
            if PRINTED_AXLE_BEARING_CLEARANCE < 0.0
            else "clearance"
        ),
        "receiver_bore_diameter_mm": RECEIVER_BORE_D,
        "shaft_receiver_diametral_clearance_mm": round(
            RECEIVER_BORE_D - PRINTED_AXLE_OD,
            3,
        ),
        "bead_diameter_mm": COLLET_BEAD_OD,
        "bead_compression_through_bearing_diameter_mm": round(
            COLLET_BEAD_OD - base.R188_ID,
            3,
        ),
        "bead_compression_through_receiver_diameter_mm": round(
            COLLET_BEAD_OD - RECEIVER_BORE_D,
            3,
        ),
        "finger_count": 4,
        "finger_length_mm": round(COLLET_FINGER_LENGTH, 3),
        "slot_width_mm": COLLET_SPLIT_WIDTH,
        "installed_axial_play_mm": COLLET_INSTALLED_AXIAL_PLAY,
        "release": (
            "remove the upper thumb pad, pinch the four exposed collet "
            "fingers inward, and push the axle back through the receiver"
        ),
    }


def _validate_printed_bayonet_path(
    hub: trimesh.Trimesh,
    print_oriented_cap: trimesh.Trimesh,
    cap_height: float,
) -> dict:
    # Unlike the earlier boss-mounted bayonet, this cap wraps around the full
    # hub flange, so its open face aligns with the hub's outer face at Z=0.
    cap = print_oriented_cap.copy()
    cap.apply_translation(
        [0.0, 0.0, -(cap_height - base.HUB_FLANGE_HEIGHT)]
    )
    samples = {}
    for angle in range(0, int(base.CAP_LOCK_ROTATION_DEG) + 1, 5):
        rotated = cap.copy()
        rotated.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(angle),
                [0.0, 0.0, 1.0],
            )
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            intersection = trimesh.boolean.intersection(
                [hub, rotated],
                engine="manifold",
            )
            volume = (
                0.0
                if intersection is None or intersection.is_empty
                else float(intersection.volume)
            )
        samples[str(angle)] = round(volume, 6)
    entry = samples["0"]
    locked = samples[str(int(base.CAP_LOCK_ROTATION_DEG))]
    maximum = max(samples.values())
    if entry > 0.001 or locked > 0.001:
        raise RuntimeError(
            "printed hub bayonet entry or terminal pocket has hard interference"
        )
    if maximum < 0.01 or maximum > 0.50:
        raise RuntimeError(
            f"printed hub detent interference {maximum:.6f} mm³ is outside target"
        )
    return {
        "sampled_rotation_deg": list(
            range(0, int(base.CAP_LOCK_ROTATION_DEG) + 1, 5)
        ),
        "intersection_volume_mm3": samples,
        "maximum_intersection_volume_mm3": maximum,
        "entry_clear": entry <= 0.001,
        "locked_clear": locked <= 0.001,
        "detent_flex_interference_present": maximum >= 0.01,
    }


def _assembled_upper_cap(
    print_oriented_cap: trimesh.Trimesh,
) -> trimesh.Trimesh:
    cap = print_oriented_cap.copy()
    cap.apply_translation(
        [
            0.0,
            0.0,
            -(RECEIVER_CAP_HEIGHT - base.HUB_FLANGE_HEIGHT),
        ]
    )
    cap.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.pi,
            [1.0, 0.0, 0.0],
        )
    )
    cap.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(base.CAP_LOCK_ROTATION_DEG),
            [0.0, 0.0, 1.0],
        )
    )
    cap.apply_translation(
        [
            0.0,
            0.0,
            base.CORE_HEIGHT + HUB_TO_CORE_GAP + base.HUB_FLANGE_HEIGHT,
        ]
    )
    return cap


def _validate_receiver_cap_clearance(
    collet: trimesh.Trimesh,
    receiver: trimesh.Trimesh,
    receiver_cap: trimesh.Trimesh,
) -> dict:
    lower, _upper = _assembled_cartridge(collet, receiver)
    cap = _assembled_upper_cap(receiver_cap)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        overlap = trimesh.boolean.intersection(
            [lower, cap],
            engine="manifold",
        )
        volume = (
            0.0
            if overlap is None or overlap.is_empty
            else round(float(overlap.volume), 6)
        )
    if volume > 0.001:
        raise RuntimeError(
            "receiver-side thumb pad collides with the exposed collet tip "
            f"({volume:.6f} mm³)"
        )
    if RECEIVER_CAP_SOCKET_AXIAL_CLEARANCE < 0.40:
        raise RuntimeError("receiver-side thumb pad has insufficient tip clearance")
    return {
        "installed_collet_intersection_volume_mm3": volume,
        "installed_collet_clear": True,
        "cap_height_mm": RECEIVER_CAP_HEIGHT,
        "socket_diameter_mm": 2.0 * RECEIVER_CAP_SOCKET_R,
        "socket_depth_mm": RECEIVER_CAP_SOCKET_DEPTH,
        "collet_radial_clearance_mm": round(
            RECEIVER_CAP_SOCKET_RADIAL_CLEARANCE,
            3,
        ),
        "collet_tip_axial_clearance_mm": round(
            RECEIVER_CAP_SOCKET_AXIAL_CLEARANCE,
            3,
        ),
    }


def _validate_identical_pads(
    first: trimesh.Trimesh,
    second: trimesh.Trimesh,
) -> dict:
    same_vertices = (
        first.vertices.shape == second.vertices.shape
        and np.allclose(first.vertices, second.vertices, atol=1e-7)
    )
    same_faces = (
        first.faces.shape == second.faces.shape
        and np.array_equal(first.faces, second.faces)
    )
    if not same_vertices or not same_faces:
        raise RuntimeError("thumb-pad objects are not geometrically identical")
    return {
        "geometrically_identical": True,
        "volume_mm3_each": round(float(first.volume), 3),
        "bounds_mm_each": np.round(first.extents, 3).tolist(),
    }


def _set_or_replace_metadata(node: ET.Element, key: str, value: str) -> None:
    for item in node.findall("./metadata"):
        if item.get("key") == key:
            item.set("value", value)
            return
    ET.SubElement(node, "metadata", {"key": key, "value": value})


def _complete_model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    root = ET.fromstring(ORIGINAL_MODEL_SETTINGS(objects, meshes))
    for object_id in range(7, 12):
        part = root.find(f".//part[@id='{object_id}']")
        if part is None:
            raise RuntimeError(f"cannot apply arm print overrides to object {object_id}")
        ET.SubElement(
            part,
            "metadata",
            {"key": "sparse_infill_density", "value": "100%"},
        )
        ET.SubElement(
            part,
            "metadata",
            {"key": "sparse_infill_pattern", "value": "grid"},
        )
        # Keep the established arm override for equal mass across all colours.
        _set_or_replace_metadata(part, "wall_loops", "2")
    for obj in root.findall(".//object"):
        part_ids = {int(part.get("id")) for part in obj.findall("./part")}
        if part_ids & set(range(7, 12)):
            _set_or_replace_metadata(obj, "wall_loops", "2")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _batch_model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    root = ET.fromstring(ORIGINAL_MODEL_SETTINGS(objects, meshes))
    arm_ids = set(range(1, 6))
    for object_id in arm_ids:
        part = root.find(f".//part[@id='{object_id}']")
        if part is None:
            raise RuntimeError(
                f"cannot apply batch arm overrides to object {object_id}"
            )
        _set_or_replace_metadata(part, "wall_loops", "2")
        _set_or_replace_metadata(part, "sparse_infill_density", "100%")
        _set_or_replace_metadata(part, "sparse_infill_pattern", "gyroid")
    for obj in root.findall(".//object"):
        part_ids = {int(part.get("id")) for part in obj.findall("./part")}
        if part_ids & arm_ids:
            _set_or_replace_metadata(obj, "wall_loops", "2")
            _set_or_replace_metadata(obj, "sparse_infill_density", "100%")
            _set_or_replace_metadata(obj, "sparse_infill_pattern", "gyroid")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _batch_preview_png(_plate_number: int, size: int = 512) -> bytes:
    image = Image.new("RGBA", (size, size), (244, 241, 234, 255))
    draw = ImageDraw.Draw(image)
    draw.text((26, 22), "Oggie Spin · five clip-lock blocks", fill="#252A32")
    positions = ((256, 256), (135, 135), (377, 135), (377, 377), (135, 377))
    colour = FILAMENTS[0][1]
    for cx, cy in positions:
        draw.pieslice(
            (cx - 62, cy - 62, cx + 62, cy + 62),
            start=250,
            end=290,
            fill=colour,
            outline="#252A32",
            width=3,
        )
    draw.text((146, 462), "BY LAYER · 2 WALLS · 100% GYROID", fill="#252A32")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _batch_top_model() -> bytes:
    bambu = base.bambu
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{bambu.CORE}" '
        f'xmlns:BambuStudio="{bambu.BAMBU}" xmlns:p="{bambu.PROD}" requiredextensions="p">',
        ' <metadata name="Application">BambuStudio-02.07.01.62</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        ' <metadata name="Title">Oggie Spin Five Clip-Lock Blocks</metadata>',
        " <resources>",
    ]
    for object_index, x, y, z in BATCH_PLATES[0].components:
        top_id = 99 + object_index
        lines.extend(
            [
                f'  <object id="{top_id}" '
                f'p:UUID="{bambu.object_uuid(top_id, 0xABCDEF123456)}" '
                'type="model">',
                "   <components>",
                f'    <component p:path="/3D/Objects/object_{object_index}.model" '
                f'objectid="{object_index}" '
                f'p:UUID="{bambu.object_uuid(0x1000 + object_index, 0xABCDEF123456)}" '
                f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}"/>',
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
    plate_x, plate_y, plate_z = BATCH_PLATES[0].position
    for object_index in range(1, 6):
        top_id = 99 + object_index
        lines.append(
            f'  <item objectid="{top_id}" '
            f'p:UUID="{bambu.object_uuid(5000 + object_index, 0xABCDEF123456)}" '
            f'transform="1 0 0 0 1 0 0 0 1 '
            f'{plate_x:.3f} {plate_y:.3f} {plate_z:.3f}" printable="1"/>'
        )
    lines.extend([" </build>", "</model>"])
    return ("\n".join(lines) + "\n").encode()


def _split_batch_model_settings(data: bytes) -> bytes:
    root = ET.fromstring(data)
    source_object = root.find("./object")
    if source_object is None:
        raise RuntimeError("batch model settings have no source object")
    source_index = list(root).index(source_object)
    source_parts = {
        int(part.get("id")): part
        for part in source_object.findall("./part")
    }
    root.remove(source_object)
    for object_index in range(1, 6):
        obj = copy.deepcopy(source_object)
        obj.set("id", str(99 + object_index))
        for part in obj.findall("./part"):
            obj.remove(part)
        obj.append(copy.deepcopy(source_parts[object_index]))
        _set_or_replace_metadata(
            obj,
            "name",
            f"Clip-lock colour block {object_index}",
        )
        _set_or_replace_metadata(obj, "extruder", "1")
        root.insert(source_index + object_index - 1, obj)

    plate = root.find("./plate")
    if plate is None:
        raise RuntimeError("batch model settings have no plate")
    for instance in plate.findall("./model_instance"):
        plate.remove(instance)
    for object_index in range(1, 6):
        instance = ET.SubElement(plate, "model_instance")
        ET.SubElement(
            instance,
            "metadata",
            {"key": "object_id", "value": str(99 + object_index)},
        )
        ET.SubElement(
            instance,
            "metadata",
            {"key": "instance_id", "value": "0"},
        )
        ET.SubElement(
            instance,
            "metadata",
            {"key": "identify_id", "value": str(299 + object_index)},
        )

    assemble = root.find("./assemble")
    if assemble is None:
        raise RuntimeError("batch model settings have no assemble section")
    for item in list(assemble):
        assemble.remove(item)
    for object_index in range(1, 6):
        ET.SubElement(
            assemble,
            "assemble_item",
            {
                "object_id": str(99 + object_index),
                "instance_id": "0",
                "transform": "1 0 0 0 1 0 0 0 1 0 0 0",
                "offset": "0 0 0",
            },
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _rewrite_batch_project_settings(path: Path) -> None:
    temp_path = path.with_suffix(".tmp.3mf")
    with (
        zipfile.ZipFile(path, "r") as source,
        zipfile.ZipFile(
            temp_path,
            "w",
            zipfile.ZIP_DEFLATED,
            compresslevel=7,
        ) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "3D/3dmodel.model":
                data = _batch_top_model()
            elif item.filename == "Metadata/model_settings.config":
                data = _split_batch_model_settings(data)
            elif item.filename == "Metadata/project_settings.config":
                settings = json.loads(data)
                settings["print_sequence"] = "by layer"
                settings["z_hop"] = ["0.6", "0.6"]
                settings["z_hop_types"] = ["Slope Lift", "Slope Lift"]
                settings["reduce_crossing_wall"] = "1"
                settings["max_travel_detour_distance"] = "0"
                settings["retract_when_changing_layer"] = ["1", "1"]
                settings["retraction_length"] = ["0.8", "0.8"]
                settings["retraction_speed"] = ["30", "30"]
                settings["deretraction_speed"] = ["30", "30"]
                settings["retraction_minimum_travel"] = ["1", "1"]
                settings["retract_before_wipe"] = ["70%", "70%"]
                settings["wipe"] = ["1", "1"]
                settings["wipe_distance"] = ["2", "2"]
                settings["enable_prime_tower"] = "0"
                data = json.dumps(
                    settings,
                    indent=2,
                    ensure_ascii=False,
                ).encode()
            target.writestr(item, data)
    temp_path.replace(path)


def _build_five_block_plate(
    out_dir: Path,
    complete_objects: list[tuple[str, Path, int]],
) -> tuple[Path, dict]:
    output = out_dir / "Oggie_Spin_5x_Clip_Lock_P2S.3mf"
    batch_objects = [
        (
            f"Clip-lock colour block {index}",
            complete_objects[5 + index][1],
            1,
        )
        for index in range(1, 6)
    ]
    previous = (
        base.PLATES,
        base.FILAMENTS,
        base._preview_png,
        base._model_settings,
        base._configure_filament_slots,
    )
    try:
        base.PLATES = BATCH_PLATES
        # Keep the template's two filament records structurally intact to avoid
        # Bambu's missing-variant warning; every object still uses slot 1.
        base.FILAMENTS = [FILAMENTS[0], FILAMENTS[0]]
        base._preview_png = _batch_preview_png
        base._model_settings = _batch_model_settings
        base._configure_filament_slots = ORIGINAL_CONFIGURE_FILAMENTS
        base.build_bambu_project(output, batch_objects)
    finally:
        (
            base.PLATES,
            base.FILAMENTS,
            base._preview_png,
            base._model_settings,
            base._configure_filament_slots,
        ) = previous
    _rewrite_batch_project_settings(output)

    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("five-block project failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        bambu_settings = json.loads(
            package.read("Metadata/project_settings.config")
        )
        model_settings = ET.fromstring(
            package.read("Metadata/model_settings.config")
        )
        plates = model_settings.findall("./plate")
        if len(plates) != 1:
            raise RuntimeError("five-block project must contain exactly one plate")
        if len(plates[0].findall("./model_instance")) != 5:
            raise RuntimeError(
                "five-block project must contain five separate plate objects"
            )
        for object_id in range(1, 6):
            part = model_settings.find(f".//part[@id='{object_id}']")
            if part is None:
                raise RuntimeError(f"five-block project lost object {object_id}")
            metadata = {
                item.get("key"): item.get("value")
                for item in part.findall("./metadata")
            }
            if (
                metadata.get("wall_loops") != "2"
                or metadata.get("sparse_infill_density") != "100%"
                or metadata.get("sparse_infill_pattern") != "gyroid"
            ):
                raise RuntimeError(
                    f"five-block object {object_id} lost print overrides"
                )
        if bambu_settings.get("print_sequence") != "by layer":
            raise RuntimeError("five-block project lost by-layer sequencing")
        if bambu_settings.get("z_hop") != ["0.6", "0.6"]:
            raise RuntimeError("five-block project lost 0.6 mm Z hop")
        if bambu_settings.get("z_hop_types") != ["Slope Lift", "Slope Lift"]:
            raise RuntimeError("five-block project lost slope Z-hop type")
    return output, {
        "path": output.name,
        "objects": 5,
        "plates": 1,
        "separate_plate_objects": True,
        "print_sequence": "by layer",
        "assigned_filament_slot": 1,
        "configured_filament_slots": 2,
        "expected_filament_changes": 0,
        "wall_loops": 2,
        "infill": "100% gyroid",
        "z_hop_mm": 0.6,
        "z_hop_type": "Slope Lift",
        "prime_tower": False,
        "layout_centres_mm": [
            [0.0, 0.0],
            [-70.0, -70.0],
            [70.0, -70.0],
            [70.0, 70.0],
            [-70.0, 70.0],
        ],
    }


def _set_last_slot_group(settings: dict, key: str, values: list[str]) -> None:
    current = settings.get(key)
    if not isinstance(current, list) or len(current) < len(FILAMENTS):
        return
    group_size = len(current) // len(FILAMENTS)
    if group_size < 1:
        return
    settings[key][-group_size:] = values * group_size


def _configure_complete_filaments(settings: dict) -> None:
    ORIGINAL_CONFIGURE_FILAMENTS(settings)
    settings["filament_settings_id"][-1] = "Bambu PLA Tough+ @BBL P2S"
    settings["filament_ids"][-1] = "GFA10"
    _set_last_slot_group(settings, "nozzle_temperature", ["245"])
    _set_last_slot_group(settings, "nozzle_temperature_initial_layer", ["245"])
    _set_last_slot_group(settings, "nozzle_temperature_range_low", ["230"])
    _set_last_slot_group(settings, "nozzle_temperature_range_high", ["260"])
    _set_last_slot_group(settings, "filament_max_volumetric_speed", ["21"])
    _set_last_slot_group(settings, "filament_flow_ratio", ["0.98"])
    _set_last_slot_group(settings, "filament_density", ["1.21"])


def _colour_mesh(mesh: trimesh.Trimesh, colour_hex: str) -> trimesh.Trimesh:
    coloured = mesh.copy()
    rgb = tuple(int(colour_hex[index : index + 2], 16) for index in (1, 3, 5))
    coloured.visual.face_colors = [*rgb, 255]
    return coloured


def _write_assembly_preview(
    out_dir: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(
        _colour_mesh(built[0][1], FILAMENTS[0][1]),
        node_name="complete_core",
    )
    for index in range(5):
        arm = _arm_installed_orientation(built[6 + index][1])
        arm.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(index * 72.0 - 90.0),
                [0.0, 0.0, 1.0],
            )
        )
        scene.add_geometry(
            _colour_mesh(arm, FILAMENTS[index][1]),
            node_name=f"clip_lock_arm_{index + 1}",
        )

    bearing = base._annulus(
        base.R188_OD,
        base.R188_ID,
        base.R188_WIDTH,
        "visual R188",
    )
    bearing.apply_translation([0.0, 0.0, base.BEARING_SEAT_Z])
    scene.add_geometry(_colour_mesh(bearing, "#AEB7C4"), node_name="r188")

    ring = built[1][1].copy()
    ring.apply_translation([0.0, 0.0, BEARING_RING_SEAT_Z])
    scene.add_geometry(
        _colour_mesh(ring, FILAMENTS[0][1]),
        node_name="bearing_retaining_ring",
    )

    lower_hub, upper_hub = _assembled_cartridge(built[2][1], built[3][1])
    scene.add_geometry(
        _colour_mesh(lower_hub, FILAMENTS[5][1]),
        node_name="lower_split_collet_hub",
    )
    scene.add_geometry(
        _colour_mesh(upper_hub, FILAMENTS[5][1]),
        node_name="upper_receiver_hub",
    )
    upper_cap = _assembled_upper_cap(built[5][1])
    scene.add_geometry(
        _colour_mesh(upper_cap, FILAMENTS[1][1]),
        node_name="upper_thumb_pad",
    )
    lower_cap = built[4][1].copy()
    lower_cap.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(base.CAP_LOCK_ROTATION_DEG),
            [0.0, 0.0, 1.0],
        )
    )
    lower_cap.apply_translation(
        [
            0.0,
            0.0,
            -HUB_TO_CORE_GAP - RECEIVER_CAP_HEIGHT,
        ]
    )
    scene.add_geometry(
        _colour_mesh(lower_cap, FILAMENTS[1][1]),
        node_name="lower_thumb_pad",
    )
    (out_dir / "oggie_spin_complete_assembly.glb").write_bytes(
        scene.export(file_type="glb")
    )


def _validate_package(path: Path, object_count: int) -> dict:
    with zipfile.ZipFile(path) as package:
        if package.testzip() is not None:
            raise RuntimeError("complete 3MF failed ZIP integrity")
        names = set(package.namelist())
        for index in range(1, object_count + 1):
            expected = f"3D/Objects/object_{index}.model"
            if expected not in names:
                raise RuntimeError(f"complete 3MF missing {expected}")
        settings = ET.fromstring(package.read("Metadata/model_settings.config"))
        plate_nodes = settings.findall("./plate")
        if len(plate_nodes) != len(PLATES):
            raise RuntimeError(
                f"complete 3MF has {len(plate_nodes)} plates, expected {len(PLATES)}"
            )
        project = json.loads(package.read("Metadata/project_settings.config"))
        expected_profiles = [
            *(["Bambu PLA Matte @BBL P2S"] * 5),
            "Bambu PLA Tough+ @BBL P2S",
        ]
        if project.get("filament_settings_id") != expected_profiles:
            raise RuntimeError("complete 3MF lost its Matte/Tough+ filament slots")
        solid_arm_ids = set()
        two_wall_arm_ids = set()
        for part in settings.findall(".//part"):
            metadata = {
                item.get("key"): item.get("value")
                for item in part.findall("./metadata")
            }
            part_id = int(part.get("id"))
            if (
                metadata.get("sparse_infill_density") == "100%"
                and metadata.get("sparse_infill_pattern") == "grid"
            ):
                solid_arm_ids.add(part_id)
            if metadata.get("wall_loops") == "2":
                two_wall_arm_ids.add(part_id)
        if solid_arm_ids != set(range(7, 12)):
            raise RuntimeError(
                "complete 3MF does not assign 100% grid infill to exactly five arms"
            )
        if two_wall_arm_ids != set(range(7, 12)):
            raise RuntimeError(
                "complete 3MF does not assign 2 wall loops to exactly five arms"
            )
        return {
            "objects": object_count,
            "plates": len(plate_nodes),
            "printer_profile": project.get("printer_settings_id"),
            "filament_profiles": project.get("filament_settings_id"),
            "filament_colours": project.get("filament_colour"),
            "layer_height": project.get("layer_height"),
            "solid_infill_object_ids": sorted(solid_arm_ids),
            "two_wall_arm_object_ids": sorted(two_wall_arm_ids),
        }


def generate(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    if mesh_dir.exists():
        shutil.rmtree(mesh_dir)
    mesh_dir.mkdir(parents=True, exist_ok=True)

    # The shared packager reads these globals.
    base.PLATES = PLATES
    base.FILAMENTS = FILAMENTS
    base._preview_png = _preview_png
    base._model_settings = _complete_model_settings
    base._configure_filament_slots = _configure_complete_filaments

    built = build_meshes()
    objects = []
    validation = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        stem = (
            name.lower()
            .replace(" + ", "_")
            .replace(" ", "_")
            .replace("-", "_")
        )
        path = mesh_dir / f"{index:02d}_{stem}.stl"
        mesh.export(path)
        reloaded = trimesh.load_mesh(path, process=True)
        base._finish(reloaded, name)
        objects.append((name, path, extruder))
        validation.append(
            {
                "object": index,
                "name": name,
                "watertight": bool(reloaded.is_watertight),
                "vertices": len(reloaded.vertices),
                "faces": len(reloaded.faces),
                "volume_mm3": round(float(reloaded.volume), 3),
                "bounds_mm": np.round(reloaded.extents, 3).tolist(),
            }
        )

    output = out_dir / "Oggie_Spin_Complete_P2S.3mf"
    base.build_bambu_project(output, objects)
    package = _validate_package(output, len(objects))
    batch_output, batch_package = _build_five_block_plate(out_dir, objects)
    printability_report = audit_printability(
        [(name, mesh) for name, mesh, *_ in built]
    )
    clip_fit = _validate_clip_lock_fit(built[0][1], built[6][1])
    collet = _validate_collet_cartridge(built[2][1], built[3][1])
    lower_bayonet_path = _validate_printed_bayonet_path(
        built[2][1],
        built[4][1],
        RECEIVER_CAP_HEIGHT,
    )
    upper_bayonet_path = _validate_printed_bayonet_path(
        built[3][1],
        built[5][1],
        RECEIVER_CAP_HEIGHT,
    )
    receiver_cap_clearance = _validate_receiver_cap_clearance(
        built[2][1],
        built[3][1],
        built[5][1],
    )
    identical_pads = _validate_identical_pads(built[4][1], built[5][1])
    _write_assembly_preview(out_dir, built)

    report = {
        "project": "Oggie Spin complete five-arm spinner",
        "status": "complete printable prototype; physical approval pending",
        "printer": "Bambu Lab P2S, 0.4 mm nozzle",
        "material": "Bambu PLA Matte + Bambu PLA Tough+",
        "finished_envelope_mm": {
            "diameter": ARM_TIP_R * 2.0,
            "core_height": base.CORE_HEIGHT,
            "body_height": ARM_HEIGHT,
            "assembled_height": (
                base.CORE_HEIGHT
                + (2.0 * HUB_TO_CORE_GAP)
                + (2.0 * RECEIVER_CAP_HEIGHT)
            ),
        },
        "core": {
            "diameter": base.CORE_DIAMETER,
            "height": base.CORE_HEIGHT,
            "slots": 5,
            "slot_pitch_deg": 72.0,
            "bearing_pocket_diameter": base.BEARING_POCKET_DIAMETER,
            "bearing_nominal_outer_diameter": base.R188_OD,
            "bearing_diametral_clearance": round(
                base.BEARING_POCKET_DIAMETER - base.R188_OD,
                3,
            ),
            "bearing_diametral_interference": round(
                max(0.0, base.R188_OD - base.BEARING_POCKET_DIAMETER),
                3,
            ),
            "bearing_fit_revision": (
                "12.86 mm released the R188 under gravity; 12.68 mm would not "
                "install by hand; 12.78 mm remained too tight; 12.82 mm uses "
                "the retaining ring for axial capture"
            ),
            "clip_pockets": True,
            "matched_arm_revision": True,
        },
        "clip_lock_joint": {
            "arms": 5,
            "style": (
                "short wrap-around colour segment with a single solid "
                "dovetail tongue and a tapered underside cantilever snap-tab"
            ),
            "arm_height": ARM_HEIGHT,
            "wrap_height": base.CORE_HEIGHT,
            "wrap_inner_radius": WRAP_INNER_R,
            "wrap_outer_radius": WRAP_OUTER_R,
            "wrap_half_angle_deg": WRAP_HALF_ANGLE_DEG,
            "core_radial_clearance": round(
                WRAP_INNER_R - base.CORE_DIAMETER / 2.0,
                3,
            ),
            "tongue_lead_in_mm": ARM_TONGUE_LEAD_IN,
            "tongue_inner_radius_mm": SLIDE_INNER_R,
            "tongue_outer_radius_mm": round(
                min(SLIDE_OUTER_R, base.ARM_SLOT_OUTER_R - 0.05), 3
            ),
            "tongue_style": "single solid dovetail (three-rail split retired)",
            "tongue_side_clearance_mm": TONGUE_SIDE_CLEARANCE,
            "snap_clip_mm": {
                "location": "inner tip of the dovetail tongue",
                "beam_inner_face_radius": CLIP_BEAM_INNER_R,
                "root_thickness": CLIP_ROOT_THICK,
                "tip_thickness": CLIP_TIP_THICK,
                "half_length": CLIP_BEAM_HALF_LENGTH,
                "root_web": CLIP_ROOT_WEB,
                "free_length": round(CLIP_FREE_LENGTH, 3),
                "depth_z": CLIP_DEPTH,
                "void_outer_x": CLIP_VOID_OUTER_R,
                "travel_space": round(
                    CLIP_VOID_OUTER_R - CLIP_BEAM_INNER_R - CLIP_ROOT_THICK, 3
                ),
            },
            "snap_clip_forces": clip_forces(),
            "clip_engagement_mm": CLIP_ENGAGEMENT,
            "clip_release_travel_mm": CLIP_RELEASE_TRAVEL,
            "clip_release_margin_mm": round(
                CLIP_RELEASE_TRAVEL - CLIP_ENGAGEMENT, 3
            ),
            "clip_entry_angle_deg": CLIP_ENTRY_ANGLE_DEG,
            "clip_retention_angle_deg": CLIP_RETENTION_ANGLE_DEG,
            "clip_pocket_depth_mm": CLIP_POCKET_DEPTH,
            "clip_entry_channel": CLIP_ENTRY_CHANNEL,
            "clip_retaining_lip_height_mm": CLIP_LIP_HEIGHT,
            "wrap_style": "plain solid annular sector -- no void, no latch",
            "wrap_lead_in_chamfer_mm": WRAP_LEAD_IN_CHAMFER,
            "core_top_edge_chamfer_mm": CORE_TOP_EDGE_CHAMFER,
            "core_foot_relief_mm": CORE_FOOT_RELIEF_DEPTH,
            "release": (
                "dual mode: (a) firm straight pull -- the 45 deg retention "
                "face cams the barb out at about 1.4 N; (b) press the barb "
                "where it is visible in the open underside recess, push it "
                "outward 0.45 mm and lift. There is no fingernail lever: the "
                "inner gap beside the beam is 0.35 mm and a nail is ~0.5 mm."
            ),
            "radial_load_path": "single solid dovetail tongue",
            "axial_retention": (
                "integrated underside Matte PLA tapered cantilever snap-tab, "
                "0.45 mm engagement, 30 deg entry / 45 deg retention"
            ),
            "weighting": "100% grid infill; no separate weight pods",
            "mass_rule": (
                "all five arms must use identical geometry and slicer settings"
            ),
            "print_orientation": (
                "as built, flush top face UP -- do not flip. The old flip "
                "existed for the retired 2 mm bottom shelf; it put the clip "
                "beam's first layer 10.35 mm up hanging over air, which is the "
                "floating cantilever the slicer rejected"
            ),
            "revision": (
                "matched core/arm revision: single solid dovetail tongue with "
                "a tapered cantilever snap-tab; the three-rail split tongue, "
                "friction ribs, rigid side detents, legacy barb recesses and "
                "the underside battery-cover clip are all retired"
            ),
        },
        "bearing_retainer": {
            "type": "pressed outer-race ring",
            "counterbore_diameter": BEARING_RING_COUNTERBORE_D,
            "ring_outer_diameter": BEARING_RING_OD,
            "ring_inner_diameter": BEARING_RING_ID,
            "height": BEARING_RING_HEIGHT,
            "diametral_interference": round(
                BEARING_RING_DIAMETRAL_INTERFERENCE,
                3,
            ),
        },
        "cartridge": {
            "type": "fully printed four-finger split collet + through-bore receiver",
            "material": "Bambu PLA Tough+",
            "integrated_inner_race_spacers": True,
            "hub_to_core_gap_each_side": HUB_TO_CORE_GAP,
            **collet,
        },
        "thumb_pads": {
            "geometry": "two identical socketed bayonet pads",
            "height_each": RECEIVER_CAP_HEIGHT,
            "socket_each": receiver_cap_clearance,
            "identity_validation": identical_pads,
            "manufacturing": (
                "same mesh on both sides; the receiver side requires the "
                "socket and the collet side retains it for batch uniformity"
            ),
        },
        "hardware": ["1 × R188 bearing (12.70 × 6.35 × 4.76 mm)"],
        "print": {
            "plates": len(PLATES),
            "layer_height": 0.16,
            "wall_loops_default": 5,
            "arm_wall_loops": 2,
            "default_infill": "25% gyroid",
            "arm_infill": "100% grid",
            "supports": False,
            "arm_colour_slots": [item[0] for item in FILAMENTS[:5]],
            "structural_filament_slot": FILAMENTS[5][0],
        },
        "physical_gates": [
            "bearing enters the Ø12.82 pocket by controlled hand pressure, seats on the lower shoulder, and is captured by the outer-race retaining ring",
            "retaining ring presses to the bearing outer race and cannot lift by hand",
            "Tough+ collet compresses through the R188 and receiver without cracking",
            "collet bead snaps fully beyond the receiver face with 0.05 mm axial play",
            "assembled printed cartridge leaves both hubs 1.6 mm clear of the core",
            "both identical thumb pads install by hand without pliers",
            "receiver-side thumb pad seats fully without touching the exposed collet tip",
            "exposed collet fingers release only when deliberately pinched together",
            "split collet survives 100 assemble/release cycles without whitening or creep",
            "all five solid-tongue blocks seat on the bottom shelves by hand without hammering",
            "each underside clip clicks into its core pocket on install",
            "pinch/press the underside tip to release; no accidental lift in normal handling",
            "all five clip locks survive 100 insert/remove cycles without whitening or creep",
            "both thumb pads survive 100 bayonet cycles",
            "assembled spinner turns freely without visible wobble",
        ],
        "meshes": validation,
        "package": package,
        "five_block_plate": batch_package,
        "clip_lock_validation": clip_fit,
        "printability": printability_report,
        "split_collet_validation": collet,
        "thumb_bayonet_validation": {
            "pad_1_collet_side": lower_bayonet_path,
            "pad_2_receiver_side": upper_bayonet_path,
            "receiver_tip_clearance": receiver_cap_clearance,
        },
    }
    (out_dir / "dimensions_and_validation.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {output}")
    print(f"Wrote {batch_output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("design/modular-spinner/complete"),
    )
    args = parser.parse_args()
    generate(args.out)


if __name__ == "__main__":
    main()
