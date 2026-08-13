"""Canonical geometry for the Bouclé Stack table lamp.

The lamp is a stack of three shells of revolution. Each shell is cut by an
oblique plane; the next shell's axis is the normal of that plane, so the stack
zig-zags ±12°. Because a shell's base plane is always perpendicular to its own
axis, every shell prints flat on the bed with no supports — the lean is an
assembly fact, not a print fact.

This module owns the numbers. Both the 2D concept sheet
(`scripts/generate_lamp_concept_svg.py`) and the coupon/CAD generators import
from here so the drawing and the meshes cannot drift apart.

All units are millimetres. The reference frame for the assembled lamp is a
front elevation: +x right, +z up, projection along -y.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Hardware — Bambu Lab LED Lamp Kit-001 (MH001)
# --------------------------------------------------------------------------

# The current EU listing specifies D59 × H8; Bambu's dimension drawing rounds
# the outer diameter to Ø60. Use the larger drawing envelope for a safe pocket.
LED_DIA = 60.0
LED_HEIGHT = 8.0
LED_POCKET_DIA = LED_DIA + 0.4
LED_POCKET_DEPTH = LED_HEIGHT + 0.5
LED_TAPE_DIA = 40.0
LED_SCREW = "BT3×12 FHCS"
LED_SCREW_PILOT = 2.6
LED_CABLE_W = 6.0
LED_CABLE_H = 4.5

# --------------------------------------------------------------------------
# Shells
# --------------------------------------------------------------------------

WALL = 1.6            # canonical A/B wall and all joint interfaces; C overrides optically
HALO_GAP = 4.0        # light slot between shells, along the joint normal
RIM_INSET = 12.0      # nominal inset of a shell base inside the rim below
RING_RECESS = 12.0    # halo ring sits this far inboard of the outer surface
RING_REGISTER_W = 4.0 # width of the register the upper shell drops onto
RING_WEB = 3.0        # halo ring web thickness
RING_FOOT = 22.0      # how far the ring reaches down inside the lower shell
RING_SLIP = 0.25      # clearance between the ring shoulder and the upper shell
RING_OUTER_BAND_H = 5.0  # B→C band depth and lower-clock top-zone height
# One hidden tapered tab clocks the upper shell into the ring register. A second
# outward tab on the ring skirt clocks the ring into the lower shell so the
# conformal band does not have to be found by feel alone. Both notches stay
# open to a free face (register bore / oblique rim) and remain support-free.
JOINT_CLOCK_PHASE_DEG = 0.0
JOINT_CLOCK_KEY_WIDTH = 3.0
JOINT_CLOCK_KEY_DEPTH = 1.0
JOINT_CLOCK_KEY_HEIGHT = 3.2
JOINT_CLOCK_TIP_WIDTH = 2.4
JOINT_CLOCK_TIP_HEIGHT = 0.8
JOINT_CLOCK_GROOVE_WIDTH = 3.8
JOINT_CLOCK_GROOVE_DEPTH = 1.4
# 36° keeps the lower tab away from the upper-shell key while the continuous
# 5 mm band roots it around the complete circumference.
LOWER_CLOCK_PHASE_DEG = 36.0
LOWER_CLOCK_KEY_WIDTH = 3.0
LOWER_CLOCK_KEY_DEPTH = 0.55
LOWER_CLOCK_KEY_HEIGHT = 4.0
LOWER_CLOCK_TIP_WIDTH = 2.4
LOWER_CLOCK_TIP_HEIGHT = 0.8
LOWER_CLOCK_GROOVE_WIDTH = 3.8
LOWER_CLOCK_GROOVE_DEPTH = 0.9
LOWER_CLOCK_RAMP_DEG = 45.0
MAX_DRAFT = 45.0      # printable outward overhang limit, base-plane-down

# --------------------------------------------------------------------------
# Base
# --------------------------------------------------------------------------

PLINTH_OD = 104.0
PLINTH_WALL = 5.0
PLINTH_Z0 = 54.0
PLINTH_Z1 = 82.0
# Seat OD is larger than Shell A's Ø112 base so a shallow annular recess can
# locate the wall for bonding. The cradle stays removable through Shell A's
# inner opening; glue Shell A only to this fixed plinth seat, never to the
# cradle flange.
PLINTH_TOP_SEAT_OD = 116.0
# Printed inverted (seat on the bed). The former full-width horizontal shoulder
# made the Ø94 bore start as a 2.7 mm inward cliff, which peeled into chords.
# The cradle flange now bears only on a narrow outer stop; beneath it, the bore
# opens along a 45° self-supporting ramp. This keeps the cradle flush and
# removable without a breakaway puck.
PLINTH_TOP_SEAT_H = 4.0
PLINTH_FLANGE_STOP_W = 0.6
PLINTH_BORE_RAMP_ANGLE_DEG = 45.0
# Shallow recess that captures Shell A's 1.6 mm base wall for radial location
# and a controlled glue film. Depth must leave ≥2.5 mm of seat under the groove
# and print as a bed-face recess in the inverted leg-frame orientation. The
# outer wall clears Shell A's flare at groove depth, not just the base circle.
SHELL_A_SEAT_GROOVE_DEPTH = 1.0
SHELL_A_SEAT_RADIAL_CLEARANCE = 0.25  # per side around the flared wall
SHELL_A_SEAT_OUTER_LAND = 0.8         # land outside the groove outer wall

LEG_COUNT = 3
LEG_PHASE_DEG = 90.0  # two legs toward the viewer, one behind — not one dead front
LEG_FOOT_R = 78.0
LEG_TOP_R = PLINTH_OD / 2
LEG_TOP_DIA = 16.0
LEG_FOOT_DIA = 10.0
# The tapered leg continues through its visible plinth contact and terminates
# inside the wall. Clipping it outside the cradle bore removes the former
# slanted end cap and creates a long, load-bearing blended joint.
LEG_EMBED_R = PLINTH_OD / 2 - PLINTH_WALL - 5.0
LEG_EMBED_Z = PLINTH_Z0 + 18.0
LEG_BORE_GAP = 0.2
# Route the lead beside the single rear leg, leaving the gap between the two
# front legs visually open. The offset preserves material between the cable
# notch and the embedded leg joint instead of cutting directly through it.
CABLE_REAR_LEG_OFFSET_DEG = 20.0
CABLE_PHASE_DEG = (
    LEG_PHASE_DEG + CABLE_REAR_LEG_OFFSET_DEG
) % 360.0

CRADLE_DIA = PLINTH_OD - 2 * PLINTH_WALL - 0.4
CRADLE_Z0 = PLINTH_Z0
CRADLE_Z1 = PLINTH_Z1
CRADLE_FIT = 0.4
CRADLE_FLANGE_DIA = 99.0
CRADLE_FLANGE_H = PLINTH_TOP_SEAT_H
CRADLE_FLANGE_FIT = 0.4
# The cradle prints base-down. Mirror the plinth's internal ramp beneath its
# retaining flange, offset inward by the normal radial fit clearance, so the
# flange starts with only a short printable lip instead of a 2.7 mm cliff.
CRADLE_FLANGE_RAMP_ANGLE_DEG = PLINTH_BORE_RAMP_ANGLE_DEG
CRADLE_FLANGE_RAMP_CLEARANCE = CRADLE_FIT / 2.0
CRADLE_KEY_W = 8.0
CRADLE_KEY_DEPTH = 2.0
CRADLE_KEY_CLEARANCE = 0.4
CRADLE_KEY_FLANGE_OVERLAP = 1.0
CRADLE_KEY_RAMP_ANGLE_DEG = 45.0
PLINTH_CABLE_CLEARANCE = 0.8

BAFFLE_DIA = 76.0
# Six 0.20 mm layers: stiff enough to keep the three posts coplanar while
# transmitting materially more light than the former 2.0 mm glare plate.
BAFFLE_WALL = 1.2
BAFFLE_POST_H = 30.0
BAFFLE_POST_DIA = 6.0
BAFFLE_POST_R = 34.0
# Reduced tips positively locate the flipped diffuser without changing its
# 30 mm optical stand-off. The three blind cradle sockets are vertical and
# open upward, so both mating features remain support-free. A 60° phase keeps
# every socket well away from the cable channel at 110°.
BAFFLE_LOCATOR_COUNT = 3
BAFFLE_LOCATOR_PHASE_DEG = 60.0
BAFFLE_LOCATOR_DIA = 3.0
BAFFLE_LOCATOR_H = 2.0
BAFFLE_SOCKET_DIA = 3.6
BAFFLE_SOCKET_DEPTH = 2.4


# --------------------------------------------------------------------------
# 2D vector helpers, in the elevation plane
# --------------------------------------------------------------------------


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def vmul(a, k):
    return (a[0] * k, a[1] * k)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def vlen(a):
    return math.hypot(a[0], a[1])


def axis_dir(deg: float):
    """Unit axis leaning `deg` degrees from vertical, positive toward +x."""
    r = math.radians(deg)
    return (math.sin(r), math.cos(r))


def perp(a):
    """The in-plane normal used for silhouette offsets."""
    return (a[1], -a[0])


def catmull_rom(keys, per_span: int = 70):
    """Smooth a list of (s, r) key points into a dense polyline."""
    pts = [keys[0]] + list(keys) + [keys[-1]]
    out = []
    for i in range(len(pts) - 3):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for j in range(per_span):
            t = j / per_span
            t2, t3 = t * t, t * t * t
            comp = []
            for k in (0, 1):
                comp.append(
                    0.5
                    * (
                        2 * p1[k]
                        + (-p0[k] + p2[k]) * t
                        + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                        + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3
                    )
                )
            out.append((comp[0], comp[1]))
    out.append(keys[-1])
    return out


# --------------------------------------------------------------------------
# Shell
# --------------------------------------------------------------------------


@dataclass
class Shell:
    key: str
    label: str
    profile_keys: list           # [(s, r)] shape definition, scaled to base_radius
    axis_length: float           # axis distance from base plane to the top cut plane
    cut_deg: float               # world tilt of the top cut plane
    cut_high: int                # +1 = plane rises toward +x, -1 = rises toward -x
    origin: tuple = (0.0, 0.0)   # centre of the base circle, world
    axis_deg: float = 0.0        # lean of the local axis, positive toward +x
    base_radius: float = 0.0
    base_inset: float = RIM_INSET

    samples: list = field(default_factory=list, repr=False)
    right: list = field(default_factory=list, repr=False)
    left: list = field(default_factory=list, repr=False)
    rim_r: tuple = (0.0, 0.0)
    rim_l: tuple = (0.0, 0.0)
    rim_mid: tuple = (0.0, 0.0)
    rim_half: float = 0.0
    cut_normal: tuple = (0.0, 1.0)
    max_radius: float = 0.0
    max_radius_z: float = 0.0
    short_side: float = 0.0
    long_side: float = 0.0
    draft_deg: float = 0.0

    def build(self):
        scale = self.base_radius / self.profile_keys[0][1]
        keys = [(s, r * scale) for s, r in self.profile_keys]
        self.samples = catmull_rom(keys)

        a = axis_dir(self.axis_deg)
        u = perp(a)
        beta = math.radians(self.cut_deg)
        n = (-self.cut_high * math.sin(beta), math.cos(beta))
        self.cut_normal = n
        q = vadd(self.origin, vmul(a, self.axis_length))

        def side(sign):
            pts = []
            prev = None
            for s, r in self.samples:
                p = vadd(vadd(self.origin, vmul(a, s)), vmul(u, sign * r))
                f = vdot(vsub(p, q), n)
                if prev is not None and prev[2] < 0.0 <= f:
                    t = -prev[2] / (f - prev[2])
                    pts.append(
                        (
                            prev[0][0] + (p[0] - prev[0][0]) * t,
                            prev[0][1] + (p[1] - prev[0][1]) * t,
                        )
                    )
                    return pts, prev[1][0] + (s - prev[1][0]) * t
                if f < 0.0:
                    pts.append(p)
                prev = (p, (s, r), f)
            raise ValueError(f"{self.key}: profile never reaches the cut plane")

        self.right, s_right = side(+1)
        self.left, s_left = side(-1)
        self.rim_r = self.right[-1]
        self.rim_l = self.left[-1]
        self.rim_mid = vmul(vadd(self.rim_r, self.rim_l), 0.5)
        self.rim_half = vlen(vsub(self.rim_r, self.rim_l)) / 2.0
        self.short_side = min(s_right, s_left)
        self.long_side = max(s_right, s_left)

        live = [(s, r) for s, r in self.samples if s <= max(s_right, s_left)]
        self.max_radius = max(r for _, r in live)
        self.max_radius_z = self.origin[1] + next(s for s, r in live if r == self.max_radius)

        worst = 0.0
        for (s0, r0), (s1, r1) in zip(live, live[1:]):
            if s1 > s0 and r1 > r0:
                worst = max(worst, math.degrees(math.atan2(r1 - r0, s1 - s0)))
        self.draft_deg = worst

    # -- derived ----------------------------------------------------------

    def outline(self):
        """Elevation silhouette, right side up then left side down."""
        return list(self.right) + list(reversed(self.left))

    def next_origin(self, gap: float = HALO_GAP):
        return vadd(self.rim_mid, vmul(self.cut_normal, gap))

    def next_axis_deg(self):
        n = self.cut_normal
        return math.degrees(math.atan2(n[0], n[1]))

    def local_cut(self):
        """The top cut expressed in the shell's own frame — i.e. as printed."""
        d = self.next_axis_deg() - self.axis_deg
        return abs(d), (-1 if d > 0 else 1)

    def as_printed(self) -> "Shell":
        """The same shell with its base plane on the bed and its axis vertical."""
        deg, high = self.local_cut()
        flat = Shell(
            key=self.key,
            label=self.label,
            profile_keys=self.profile_keys,
            axis_length=self.axis_length,
            cut_deg=deg,
            cut_high=high,
            origin=(0.0, 0.0),
            axis_deg=0.0,
            base_radius=self.base_radius,
            base_inset=self.base_inset,
        )
        flat.build()
        return flat

    def radius_at(self, s: float) -> float:
        """Outer radius at axial distance `s` from the base plane."""
        scale = self.base_radius / self.profile_keys[0][1]
        keys = [(ks, kr * scale) for ks, kr in self.profile_keys]
        pts = catmull_rom(keys)
        if s <= pts[0][0]:
            return pts[0][1]
        for (s0, r0), (s1, r1) in zip(pts, pts[1:]):
            if s0 <= s <= s1 and s1 > s0:
                return r0 + (r1 - r0) * (s - s0) / (s1 - s0)
        return pts[-1][1]


def joint_recess(lower: Shell, upper: Shell) -> float:
    """How far the halo ring's seat sits inboard of the lower shell's rim.

    This is what decides whether the slot reads as a band of shadow or shows a
    lit edge of the ring, so both joints have to agree — otherwise the two
    halos look different and the printed coupon only proves one of them.
    """
    corbel_r = upper.base_radius - WALL - RING_REGISTER_W / 2.0
    flat = lower.as_printed()
    # Every azimuth on an oblique rim lands at an axial position between the
    # short and long sides. Outward-flaring A is tightest at the short side,
    # while inward-tapering B is tightest at the long side; checking only one
    # endpoint silently overstated B→C concealment.
    rim_radii = [
        flat.radius_at(
            flat.short_side
            + (flat.long_side - flat.short_side) * index / 180.0
        )
        for index in range(181)
    ]
    return min(rim_radii) - corbel_r


def build_stack() -> list[Shell]:
    """Resolve the three shells, chaining each base plane off the rim below."""
    shells = [
        Shell(
            key="shell_a",
            label="A · lower bowl",
            profile_keys=[(0, 56), (18, 65), (38, 71), (60, 74), (88, 76)],
            axis_length=56.0,
            cut_deg=12.0,
            cut_high=-1,
            # Sit on the locate-groove floor, not the taller outer/inner lands.
            origin=(0.0, PLINTH_Z1 - SHELL_A_SEAT_GROOVE_DEPTH),
            axis_deg=0.0,
            base_radius=56.0,
        ),
        Shell(
            key="shell_b",
            label="B · wedge",
            profile_keys=[(0, 63), (24, 62), (52, 61), (96, 60)],
            axis_length=38.0,
            cut_deg=12.0,
            cut_high=+1,
            base_inset=12.0,
        ),
        Shell(
            key="shell_c",
            label="C · upper bowl",
            profile_keys=[(0, 59), (26, 63), (58, 66), (96, 68.5)],
            axis_length=44.0,
            cut_deg=9.0,
            cut_high=-1,
            # 15.5 rather than nominal 12: B tapers inward, so concealment is
            # tightest at its long side. This leaves >=12 mm around the complete
            # B→C rim instead of passing only the wider short side.
            base_inset=15.5,
        ),
    ]

    shells[0].build()
    for prev, cur in zip(shells, shells[1:]):
        cur.origin = prev.next_origin()
        cur.axis_deg = prev.next_axis_deg()
        cur.base_radius = prev.rim_half - cur.base_inset
        cur.build()

    for sh in shells:
        draft = sh.as_printed().draft_deg
        if draft > MAX_DRAFT:
            raise ValueError(f"{sh.key}: {draft:.1f}° overhang exceeds {MAX_DRAFT}°")

    for lower, upper in zip(shells, shells[1:]):
        recess = joint_recess(lower, upper)
        if recess < RING_RECESS:
            raise ValueError(
                f"{lower.key}–{upper.key}: halo ring sits {recess:.1f} mm inboard, "
                f"need {RING_RECESS} mm — raise {upper.key}'s base_inset"
            )
    return shells


def overall_height(shells: list[Shell]) -> float:
    return max(shells[-1].rim_l[1], shells[-1].rim_r[1])


def widest_diameter(shells: list[Shell]) -> float:
    return max(sh.max_radius for sh in shells) * 2
