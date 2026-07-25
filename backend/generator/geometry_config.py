#!/usr/bin/env python3
"""Shared geometry for Ogma bowl styles — Cooper metal bowl locked.

All styles seat the same stainless insert used by the paw-lattice Cooper stand.
Do not reintroduce multi-rim presets here until that product decision returns.
"""

from __future__ import annotations

from dataclasses import dataclass


# --- Locked metal bowl (same insert as Cooper) ---
BOWL_RIM_OD = 140.0
BOWL_BODY_OD = 130.0
BOWL_BASE_OD = 100.0
BOWL_DEPTH = 35.0
BOWL_OPENING_D = 133.0
BOWL_SEAT_D = 142.0
BOWL_RIM_RECESS = 1.8

# --- Style ids ---
STYLE_COOPER = "cooper"
STYLE_WAVE = "wave"
STYLE_HEX = "hex"
STYLES = (STYLE_COOPER, STYLE_WAVE, STYLE_HEX)

STYLE_META = {
    STYLE_COOPER: {
        "name": "Paw lattice",
        "description": "Recessed paws + curved name rail (default)",
        "available": True,
    },
    STYLE_WAVE: {
        "name": "Split wave",
        "description": "Sine seam · separate bowl seat · glue-in letters",
        "available": True,
    },
    STYLE_HEX: {
        "name": "Honeycomb",
        "description": "Solid drum · recessed hex pattern · glue-in letters",
        "available": True,
    },
}


@dataclass(frozen=True)
class CooperEnvelope:
    """Outer envelope shared with the Cooper paw stand."""

    stand_od: float = 170.0
    stand_height: float = 78.0
    wall_outer_r: float = 81.6
    wall_inner_r: float = 77.6


COOPER = CooperEnvelope()


@dataclass(frozen=True)
class WaveParams:
    """Split wave stand at Cooper bowl size / Cooper height family."""

    h: float = 78.0
    amp: float = 8.0
    waves: int = 2
    seam_p: float = 45.0  # percent of H
    # Outer radii from Named Bowl §2 with rim=140, rounded to Cooper OD family.
    rt_out: float = 75.6
    rb_out: float = 85.7
    wall_thick: float = 5.5
    collar_clearance: float = 0.5  # per side — print-proven
    collar_outer_r: float = 74.0
    sleeve_wall: float = 2.2
    min_upper_wall: float = 4.0
    seat_insert_clearance: float = 0.3
    seat_flange_edge_inset: float = 0.3
    shadow_chamfer: float = 0.6
    seam_gap: float = 0.7  # lower stops this far below the sine
    sectors: int = 64
    # Letters sit on a large (low-seam) lobe. azimuth = π/2 maps packing
    # center arc=0 onto +X, where the sine seam is at its lowest.
    letter_azimuth: float = 1.5707963267948966  # π/2 — large +X lobe
    # Vertically centred on that large upper face (seam_low+gap → shell top).
    letter_center_z: float = 52.0
    rail_z0: float = 42.5
    rail_z1: float = 61.5
    rail_proud: float = 4.0


WAVE = WaveParams()


@dataclass(frozen=True)
class HexParams:
    """Solid recessed-honeycomb drum at Cooper bowl size."""

    h: float = 78.0
    rb_out: float = COOPER.wall_outer_r
    rt_out: float = COOPER.wall_outer_r
    wall_inner_r: float = COOPER.wall_inner_r
    support_start_z: float = 60.0
    groove_depth: float = 1.0
    groove_gap: float = 2.7
    groove_chamfer: float = 1.30
    target_cell_radius: float = 9.24
    rows: int = 208
    sections: int = 1056
    pattern_edge_band: float = 5.0
    pattern_border_width: float = 1.4
    pattern_border_depth: float = 0.45
    edge_bevel: float = 0.45
    edge_bevel_height: float = 1.2
    letter_center_z: float = 40.5


HEX = HexParams()


def wave_derived(p: WaveParams = WAVE) -> dict[str, float]:
    """Derived wave seam / collar numbers (Named Bowl §2, Cooper-sized)."""
    seam_y = p.h * p.seam_p / 100.0
    seam_y = max(p.amp + 18.0, min(p.h - 24.0 - p.amp, seam_y))
    s_min = seam_y - p.amp
    s_max = seam_y + p.amp
    y2 = s_max + 4.0
    rb_in = p.rb_out - p.wall_thick
    # Keep the collar far enough inside the tapered upper wall for a real
    # sleeve and support bridge. The old rb_in - 1.6 value crossed the upper
    # exterior near Y2.
    rc = p.collar_outer_r
    return {
        "seam_y": seam_y,
        "s_min": s_min,
        "s_max": s_max,
        "y2": y2,
        "rb_in": rb_in,
        "rc": rc,
        "seat_z": p.h - BOWL_RIM_RECESS,
    }
