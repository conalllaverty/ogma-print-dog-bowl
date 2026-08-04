"""Canonical geometry for the Golf Tee LED lamp.

A Ø175 sculptural golf ball sits on a Matte PLA tee over a Grass Green base.
The MH001 LED seats in the tee cup over a white reflector insert. A 3-lug
¼-turn bayonet with end-of-travel detents locks the shade for serviceability.
Cable runs through an Ø18 pocket-floor bore and hollow stem to an underside
base trench. The tee foot uses slotted spring fingers; the base carries a
ballast pocket, a printed ballast cover, and a felt-pad recess.

Dimples displace outer and inner surfaces equally so the wall stays a constant
1.6 mm solid shell (four 0.4 mm passes, 0% sparse infill).

All-PLA workflow: Jade White Basic shade, Matte tee/base/cover, Ivory reflector.
PLA-on-PLA supports (no PETG interface).

All units are millimetres. Assembled frame: +z up, base underside on z = 0.
"""

from __future__ import annotations

import math

import numpy as np

# --------------------------------------------------------------------------
# Hardware — Bambu Lab LED Lamp Kit-001 (MH001)
# --------------------------------------------------------------------------

LED_DIA = 60.0
LED_HEIGHT = 8.0
# Pocket leaves room for a 0.8 mm white reflector liner around the MH001.
LED_POCKET_DIA = LED_DIA + 2.0 * (0.8 + 0.25)  # 62.1
LED_POCKET_DEPTH = LED_HEIGHT + 0.5 + 0.8  # LED + reflector floor
LED_TAPE_DIA = 40.0
LED_CABLE_W = 6.0
LED_CABLE_H = 4.5
# Inline on/off button (~14.5–15 mm) + USB-A overmold (~16 mm wide). Ø18 leaves
# print-bulge margin that Ø16 did not.
LED_INLINE_SWITCH_CLEAR_DIA = 18.0

PLINTH_CABLE_CLEARANCE = 0.8
CABLE_PHASE_DEG = 0.0
CABLE_CHANNEL_W = LED_CABLE_W + PLINTH_CABLE_CLEARANCE  # 6.8
CABLE_BORE_DIA = LED_INLINE_SWITCH_CLEAR_DIA
# Underside trench must also clear the switch/USB on the way out.
CABLE_EXIT_TRENCH_W = CABLE_BORE_DIA + 1.0  # 19.0

# --------------------------------------------------------------------------
# Filaments — all-PLA workflow
# --------------------------------------------------------------------------

# Translucent shade — Jade White Basic transmits far more than Matte Bone White.
BALL_FILAMENT_ID = None  # not in Matte palette
BALL_FILAMENT_HEX = "#FFFFFF"
BALL_FILAMENT_PROFILE = "Bambu PLA Basic @BBL P2S"
BALL_FILAMENT_LABEL = "Bambu PLA Basic · Jade White (semi-translucent)"

# Matte Caramel tee (replaces wood-fill).
TEE_FILAMENT_ID = "matte-caramel"
TEE_FILAMENT_LABEL_OVERRIDE = "Bambu PLA Matte · Caramel"

BASE_FILAMENT_ID = "matte-grass-green"

# Opaque white reflector cup under the MH001 (bounce light into the shade).
REFLECTOR_FILAMENT_ID = "matte-ivory-white"

# PLA-on-PLA supports — no PETG interface slot (shade is self-supporting).
SUPPORT_Z_DISTANCE = 0.18  # mm (kept for docs / optional painted supports)

# Baked Variable Layer Height for the shade (Metadata/layer_heights_profile.txt).
VLH_BASE_LAYER_H = 0.20
VLH_APEX_LAYER_H = 0.08
VLH_FINE_FRACTION = 0.20  # top 20% of print height

# --------------------------------------------------------------------------
# Golf ball shade — constant-thickness displaced dimples
# --------------------------------------------------------------------------

BALL_OD = 175.0
BALL_R = BALL_OD / 2.0  # 87.5
BALL_WALL = 1.6
BALL_INNER_R = BALL_R - BALL_WALL  # 85.9

BALL_OPENING_ID = 85.0
BALL_OPENING_R = BALL_OPENING_ID / 2.0
BALL_OPENING_Z = -math.sqrt(BALL_R * BALL_R - BALL_OPENING_R * BALL_OPENING_R)

DIMPLE_COUNT = 550
DIMPLE_DEPTH = 1.4
DIMPLE_ALPHA_MAX = 0.058
DIMPLE_SURFACE_DIA = round(2.0 * BALL_R * DIMPLE_ALPHA_MAX, 2)
DIMPLE_EQUATOR_KEEP_MM = 0.0
DIMPLE_OPENING_KEEP_MM = 8.0

BALL_SEAT_GROOVE_DEPTH = 1.0
BALL_SEAT_RADIAL_CLEARANCE = 0.25
BALL_SEAT_OUTER_LAND = 0.8
BALL_SEAT_OD = 110.0
LED_POCKET_SEAT_LAND = 2.5

# Self-supporting print skirt (opening-down): flat bed ring → ≤45° cone → sphere.
# Replaces the shallow spherical overhang that forced massive supports.
SUPPORT_FREE_OVERHANG_DEG = 45.0
SUPPORT_FREE_BLEND_MARGIN_MM = 2.0  # dimple keepout above blend


def ball_vlh_profile(print_height: float) -> list[float]:
    """Z / layer-height pairs for Bambu `layer_heights_profile.txt`.

    Keeps 0.20 mm through the lower 80%, then ramps to 0.08 mm on the apex.
    """
    if print_height < 20.0:
        raise ValueError(f"shade print height {print_height:.1f} mm is too short for VLH")
    z_fine = print_height * (1.0 - VLH_FINE_FRACTION)
    return [
        0.0,
        VLH_BASE_LAYER_H,
        z_fine,
        VLH_BASE_LAYER_H,
        print_height * 0.88,
        0.12,
        print_height * 0.94,
        0.10,
        print_height * 0.98,
        VLH_APEX_LAYER_H,
        print_height,
        VLH_APEX_LAYER_H,
    ]


def support_free_skirt() -> dict:
    """Flat bed ring + cone that meets the sphere where overhang ≤ threshold."""
    alpha = math.radians(SUPPORT_FREE_OVERHANG_DEG)
    z_blend = -BALL_R * math.cos(alpha)
    r_blend = BALL_R * math.sin(alpha)
    r_inner_blend = math.sqrt(max(BALL_INNER_R * BALL_INNER_R - z_blend * z_blend, 0.0))
    dz = z_blend - BALL_OPENING_Z
    if dz <= 1.0:
        raise ValueError("support-free blend is at or below the opening plane")
    # Outer cone at `alpha` from vertical: dr/dz = tan(alpha).
    bed_outer_r = r_blend - dz * math.tan(alpha)
    if bed_outer_r <= BALL_OPENING_R + 1.0:
        raise ValueError("support-free bed ring is too narrow")
    # Inner cone meets the sphere inner surface at the blend.
    bed_inner_r = r_inner_blend - dz * math.tan(alpha)
    if bed_inner_r <= BALL_OPENING_R:
        bed_inner_r = BALL_OPENING_R + 0.2
    return {
        "overhang_deg": SUPPORT_FREE_OVERHANG_DEG,
        "z_blend": z_blend,
        "r_blend": r_blend,
        "r_inner_blend": r_inner_blend,
        "bed_outer_r": bed_outer_r,
        "bed_inner_r": bed_inner_r,
        "ring_width": bed_outer_r - BALL_OPENING_R,
        "cone_height": dz,
    }

# --------------------------------------------------------------------------
# Bayonet (3-lug · ~¼-turn) — serviceable ball ↔ tee join
# --------------------------------------------------------------------------

BAYONET_LUG_COUNT = 3
BAYONET_TWIST_DEG = 60.0
BAYONET_PIN_DIA = 5.0
BAYONET_PIN_H = 4.0
BAYONET_PIN_CLEARANCE = 0.35
BAYONET_PIN_FILLET_R = 1.2  # root fillet where pin meets tee cup
# PCD sits on the land between the LED pocket and the ball groove.
BAYONET_PCD = 70.0
BAYONET_FLANGE_H = 6.0
BAYONET_ENTRY_WIDTH_DEG = 18.0
BAYONET_TRACK_H = 2.4
# Positive click at end of twist travel (shade-side bump into the L-track).
BAYONET_DETENT_H = 0.4

# --------------------------------------------------------------------------
# Green grass base + snap + ballast (rounded-square footprint)
# --------------------------------------------------------------------------

BASE_SIDE = 120.0  # outer square side length
BASE_CORNER_R = 14.0  # soft corners — still reads as a pad, not a disc
BASE_H = 18.0  # taller to host ballast under the snap floor
BASE_TEE_RECESS_DEPTH = 7.0

SNAP_SHAFT_OD = 74.0
SNAP_BEAD_OD = 77.0
SNAP_BEAD_H = 1.6
SNAP_BEAD_Z = 3.2
SNAP_ENTRY_OD = 75.6
SNAP_GROOVE_OD = 77.4
SNAP_GROOVE_H = 2.0
SNAP_SHAFT_CLEARANCE = 0.35
# Vertical slots turn the bead into cantilever spring fingers (anti-creep).
SNAP_SLOT_COUNT = 4
SNAP_SLOT_WIDTH_DEG = 10.0
SNAP_SLOT_DEPTH_EXTRA = 1.5  # above bead top
# Keep fuzzy turf clear of the snap entry (paint mask radius).
FUZZY_SNAP_KEEP_R = SNAP_ENTRY_OD / 2.0 + 3.0

# Underside ballast pocket. Square outer, round keepout.
BALLAST_DEPTH = 7.0
BALLAST_INNER_R = 40.0  # circular keepout around the snap well
BALLAST_OUTER_INSET = 4.0  # wall left between pocket and outer edge
BALLAST_COVER_THICKNESS = 1.2
BALLAST_COVER_CLEARANCE = 0.35  # per side vs pocket
BALLAST_COVER_LEDGE = 1.5  # radial shelf the cover rests on
# Die-cut felt / silicone pad recess on the underside (matching square).
FELT_PAD_SIDE = 110.0
FELT_PAD_CORNER_R = 12.0
FELT_PAD_RECESS = 1.0

# Top-face turf fuzzy paint (Studio: none + painted facets).
BASE_FUZZY_THICKNESS = 0.15
BASE_FUZZY_POINT_DISTANCE = 0.10

# Back-compat alias used by older reports / trench length math.
BASE_OD = BASE_SIDE

# --------------------------------------------------------------------------
# Matte PLA tee with integrated LED pocket
# --------------------------------------------------------------------------

TEE_FOOT_OD = SNAP_SHAFT_OD
TEE_FOOT_FLAT_H = 6.5
# Neck Ø24 around Ø18 bore → 3 mm wall (desk-lamp sufficient).
TEE_STEM_NARROW_OD = 24.0
TEE_STEM_NARROW_Z = 24.0
TEE_STEM_MID_OD = 30.0
TEE_STEM_MID_Z = 74.0
TEE_STEM_TOP_OD = 48.0

CUP_OD = 90.0
CUP_FLOOR = 4.0
CUP_SEAT_H = 4.0
CUP_H = CUP_SEAT_H + LED_POCKET_DEPTH + CUP_FLOOR  # 16.5
TEE_CUP_Z0 = 112.0
TEE_CUP_Z1 = TEE_CUP_Z0 + CUP_H
TEE_OVERALL_H = TEE_CUP_Z1

# White reflector cup lining the LED pocket (0.8 mm walls/floor).
REFLECTOR_WALL = 0.8
REFLECTOR_FLOOR = 0.8
REFLECTOR_RADIAL_CLEARANCE = 0.15
REFLECTOR_HEIGHT_CLEARANCE = 0.2

TEE_ASSEMBLED_Z0 = BASE_H - BASE_TEE_RECESS_DEPTH
TEE_CUP_WORLD_Z0 = TEE_ASSEMBLED_Z0 + TEE_CUP_Z0
TEE_CUP_WORLD_Z1 = TEE_ASSEMBLED_Z0 + TEE_CUP_Z1

BALL_ORIGIN_Z = TEE_CUP_WORLD_Z1 - BALL_SEAT_GROOVE_DEPTH - BALL_OPENING_Z
BALL_TOP_Z = BALL_ORIGIN_Z + BALL_R
OVERALL_H = BALL_TOP_Z


def ball_opening_radii() -> dict:
    outer_r = BALL_OPENING_R
    inner_r = math.sqrt(BALL_INNER_R * BALL_INNER_R - BALL_OPENING_Z * BALL_OPENING_Z)
    return {
        "outer_r": outer_r,
        "inner_r": inner_r,
        "wall_radial": outer_r - inner_r,
    }


def ballast_cover_side() -> float:
    return BASE_SIDE - 2.0 * BALLAST_OUTER_INSET - 2.0 * BALLAST_COVER_CLEARANCE


def ballast_cover_corner_r() -> float:
    return max(BASE_CORNER_R - BALLAST_OUTER_INSET - BALLAST_COVER_CLEARANCE, 4.0)


def reflector_outer_r() -> float:
    return LED_POCKET_DIA / 2.0 - REFLECTOR_RADIAL_CLEARANCE


def ball_seat_groove() -> dict:
    opening = ball_opening_radii()
    skirt = support_free_skirt()
    # Tee rebate matches the flat bed ring (no longer a spherical flare).
    groove_inner_r = opening["inner_r"] - BALL_SEAT_RADIAL_CLEARANCE
    groove_outer_r = skirt["bed_outer_r"] + BALL_SEAT_RADIAL_CLEARANCE
    seat_r = BALL_SEAT_OD / 2.0
    if groove_outer_r + BALL_SEAT_OUTER_LAND > seat_r:
        raise ValueError(
            f"ball seat OD {BALL_SEAT_OD} is too small for support-free bed ring "
            f"(need ≥ {(groove_outer_r + BALL_SEAT_OUTER_LAND) * 2:.1f})"
        )
    if CUP_SEAT_H - BALL_SEAT_GROOVE_DEPTH < 2.5:
        raise ValueError("seat under the ball groove is thinner than 2.5 mm")
    land = groove_inner_r - LED_POCKET_DIA / 2.0
    if land < LED_POCKET_SEAT_LAND:
        raise ValueError(
            f"only {land:.2f} mm land between LED pocket and ball groove; "
            f"need ≥{LED_POCKET_SEAT_LAND}"
        )
    pin_r = BAYONET_PCD / 2.0
    if pin_r <= LED_POCKET_DIA / 2.0 + BAYONET_PIN_DIA / 2.0 + 0.8:
        raise ValueError("bayonet PCD collides with the LED pocket")
    if pin_r + BAYONET_PIN_DIA / 2.0 + 0.5 >= groove_inner_r:
        raise ValueError("bayonet PCD collides with the ball seat groove")
    if BALL_WALL < 1.2:
        raise ValueError(f"ball wall {BALL_WALL} mm is thinner than 1.2 mm")
    if DIMPLE_DEPTH >= BALL_R * 0.05:
        raise ValueError(
            f"dimple depth {DIMPLE_DEPTH} mm is too deep for R={BALL_R}"
        )
    narrow_wall = (TEE_STEM_NARROW_OD - CABLE_BORE_DIA) / 2.0
    if narrow_wall < 2.5:
        raise ValueError(
            f"hollow tee stem wall is only {narrow_wall:.2f} mm at the neck"
        )
    if BAYONET_PIN_FILLET_R < 1.0:
        raise ValueError("bayonet pin root fillet must be ≥1.0 mm")
    if skirt["cone_height"] > 25.0:
        raise ValueError("support-free cone is taller than 25 mm — check opening size")
    ballast_half = BASE_SIDE / 2.0 - BALLAST_OUTER_INSET
    ballast_vol = (
        (2.0 * ballast_half) ** 2 - math.pi * BALLAST_INNER_R**2
    ) * BALLAST_DEPTH / 1000.0
    return {
        "style": "flat_ring_rebate",
        "groove_inner_diameter": round(groove_inner_r * 2.0, 3),
        "groove_outer_diameter": round(groove_outer_r * 2.0, 3),
        "groove_depth": BALL_SEAT_GROOVE_DEPTH,
        "seat_outer_diameter": BALL_SEAT_OD,
        "bed_ring_od": round(skirt["bed_outer_r"] * 2.0, 3),
        "support_free_cone_height": round(skirt["cone_height"], 2),
        "support_free_overhang_deg": SUPPORT_FREE_OVERHANG_DEG,
        "opening_outer_diameter": round(opening["outer_r"] * 2.0, 3),
        "opening_inner_diameter": round(opening["inner_r"] * 2.0, 3),
        "opening_wall_radial": round(opening["wall_radial"], 3),
        "led_pocket_seat_land": round(land, 2),
        "wall_thickness_constant": BALL_WALL,
        "dimple_depth": DIMPLE_DEPTH,
        "bayonet_pcd": BAYONET_PCD,
        "bayonet_twist_deg": BAYONET_TWIST_DEG,
        "bayonet_pin_dia": BAYONET_PIN_DIA,
        "bayonet_detent_h": BAYONET_DETENT_H,
        "ballast_pocket_cm3": round(ballast_vol, 1),
    }


def fibonacci_sphere(count: int) -> np.ndarray:
    """Unit directions with +z as the Fibonacci pole (shape (N, 3))."""
    golden = math.pi * (3.0 - math.sqrt(5.0))
    index = np.arange(count, dtype=np.float64)
    z = 1.0 - (2.0 * index + 1.0) / count
    radius = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    theta = golden * index
    return np.column_stack((radius * np.cos(theta), radius * np.sin(theta), z))


def dimple_unit_centers() -> np.ndarray:
    """Fibonacci dimple axes clear of the opening seat and support-free skirt."""
    skirt = support_free_skirt()
    opening_limit_z = skirt["z_blend"] + SUPPORT_FREE_BLEND_MARGIN_MM
    keep: list[np.ndarray] = []
    for unit in fibonacci_sphere(DIMPLE_COUNT):
        surface_z = float(unit[2] * BALL_R)
        if abs(surface_z) < DIMPLE_EQUATOR_KEEP_MM:
            continue
        if surface_z < opening_limit_z:
            continue
        keep.append(unit)
    if not keep:
        return np.zeros((0, 3), dtype=np.float64)
    return np.asarray(keep, dtype=np.float64)


def dimple_depth_field(unit_dirs: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Per-vertex radial indentation (mm). Same field drives outer and inner."""
    if centers.size == 0:
        return np.zeros(len(unit_dirs), dtype=np.float64)
    dots = np.clip(unit_dirs @ centers.T, -1.0, 1.0)
    angles = np.arccos(dots)
    x = np.clip(angles / DIMPLE_ALPHA_MAX, 0.0, 1.0)
    depths = DIMPLE_DEPTH * (1.0 - 3.0 * x * x + 2.0 * x * x * x)
    return depths.max(axis=1)


def summary() -> dict:
    groove = ball_seat_groove()
    skirt = support_free_skirt()
    return {
        "product": "Golf Tee LED lamp",
        "kit": "Bambu Lab LED Lamp Kit-001 (MH001)",
        "workflow": "all-PLA",
        "ball_od": BALL_OD,
        "ball_wall": BALL_WALL,
        "ball_opening_id": BALL_OPENING_ID,
        "ball_join": "3-lug bayonet 1/4-turn with detent",
        "support_free_skirt": {
            "overhang_deg": skirt["overhang_deg"],
            "cone_height": round(skirt["cone_height"], 2),
            "bed_ring_od": round(skirt["bed_outer_r"] * 2.0, 2),
            "ring_width": round(skirt["ring_width"], 2),
        },
        "dimple_target_count": DIMPLE_COUNT,
        "dimple_applied_count": int(len(dimple_unit_centers())),
        "dimple_depth": DIMPLE_DEPTH,
        "dimple_alpha_max_rad": DIMPLE_ALPHA_MAX,
        "dimple_surface_dia": DIMPLE_SURFACE_DIA,
        "dimple_style": (
            "constant-thickness dual-surface displacement; "
            f"{BALL_WALL} mm solid shell, 0% sparse infill"
        ),
        "tee_height": TEE_OVERALL_H,
        "led_pocket_in_tee": True,
        "reflector_insert": True,
        "separate_cradle": False,
        "separate_diffuser": False,
        "snap_fit": {
            "shaft_od": SNAP_SHAFT_OD,
            "bead_od": SNAP_BEAD_OD,
            "entry_od": SNAP_ENTRY_OD,
            "groove_od": SNAP_GROOVE_OD,
            "spring_slots": SNAP_SLOT_COUNT,
        },
        "base_side": BASE_SIDE,
        "base_corner_r": BASE_CORNER_R,
        "base_height": BASE_H,
        "ballast_pocket_cm3": groove["ballast_pocket_cm3"],
        "ballast_cover_thickness": BALLAST_COVER_THICKNESS,
        "felt_pad_side": FELT_PAD_SIDE,
        "cable_bore_dia": CABLE_BORE_DIA,
        "filaments": {
            "ball": BALL_FILAMENT_LABEL,
            "tee": TEE_FILAMENT_LABEL_OVERRIDE,
            "base": BASE_FILAMENT_ID,
            "ballast_cover": BASE_FILAMENT_ID,
            "reflector": REFLECTOR_FILAMENT_ID,
            "supports": (
                f"shade VLH baked ({VLH_BASE_LAYER_H:.2f}→{VLH_APEX_LAYER_H:.2f} mm "
                f"on top {int(VLH_FINE_FRACTION * 100)}%)"
            ),
        },
        "overall_height": round(OVERALL_H, 2),
        "ball_origin_z": round(BALL_ORIGIN_Z, 2),
        "cable_phase_deg": CABLE_PHASE_DEG,
        "ball_seat_groove": groove,
    }
