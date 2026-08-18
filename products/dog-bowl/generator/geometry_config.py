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

# Style ids, display names and availability now live with the styles themselves,
# in the `styles` registry package — this module is geometry only. Importing the
# registry from here would be circular: styles/wave.py imports wave_bowl_design,
# which imports this module.


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
    # Where the name goes, and — since the seam phase is derived from this — the
    # azimuth of a low-seam lobe. The letters have to sit on a low lobe because
    # that is where the upper shell is tallest; on a high lobe there is no room.
    #
    # 0 = the -Y design front, so the name faces the same way as every other
    # style's. It was π/2, which put the name on the +X lobe: the front
    # elevation in the viewer and the `front` render then showed a blank wall
    # while the name sat round the side. With `waves = 2` there is a low lobe
    # every 180°, so the front is a valid choice and this is a pure 90° rotation
    # of the body — same shape, same fit, same printability.
    letter_azimuth: float = 0.0  # -Y front, on a low-seam lobe
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
    support_start_z: float = 58.0
    groove_depth: float = 1.0
    groove_gap: float = 2.7
    groove_chamfer: float = 1.30
    target_cell_radius: float = 9.24
    rows: int = 208
    sections: int = 1056
    pattern_edge_band: float = 5.0
    pattern_border_width: float = 1.4
    pattern_border_depth: float = 0.45
    name_keepout_margin: float = 1.5
    top_edge_bead: float = 0.45
    top_edge_height: float = 1.2
    bottom_edge_chamfer: float = 0.35
    bottom_edge_height: float = 1.2
    # The staggered whole-cell keepout around Z39 has its visual midpoint near
    # Z37; use that optical centre so top/bottom letter clearance is balanced.
    letter_center_z: float = 37.0


HEX = HexParams()


@dataclass(frozen=True)
class FlutedParams:
    """Fluted drum — same envelope and seat as the honeycomb, different texture.

    Flutes are cut INWARD. The archived Named Bowl v4.5 generator pushed them
    outward (`r += fa*(0.5+0.5*sin(fn*th))`), which grows the outside diameter
    by 2*fa and would foul the letter pockets, since those are cut at a fixed
    LETTER_FACE_R. Cutting inward keeps the 170 mm envelope and leaves the wall
    arithmetic identical to the honeycomb's.
    """

    h: float = 78.0
    rb_out: float = COOPER.wall_outer_r
    rt_out: float = COOPER.wall_outer_r
    wall_inner_r: float = COOPER.wall_inner_r
    support_start_z: float = 58.0

    # v4.5 shipped fn=64 / fa=1.1 as its defaults. 64 flutes at R81.6 is a
    # 8.0 mm pitch — comfortably above the 0.42 mm line width, so each flute
    # still gets real perimeters rather than becoming slicer noise.
    flute_count: int = 64
    flute_depth: float = 1.1

    # Remaining web = 4.0 mm wall - flute_depth. Keep >= 2.5 mm.
    min_web: float = 2.5

    rows: int = 208
    sections: int = 1056
    pattern_edge_band: float = 5.0
    pattern_border_width: float = 1.4
    pattern_border_depth: float = 0.45
    # Flutes fade out over this distance rather than stopping at a hard edge —
    # a step would leave a visible seam beside every letter.
    name_keepout_margin: float = 2.5
    name_fade: float = 6.0
    top_edge_bead: float = 0.45
    top_edge_height: float = 1.2
    bottom_edge_chamfer: float = 0.35
    bottom_edge_height: float = 1.2
    # No staggered cell field here, so the name sits at the true drum midpoint.
    letter_center_z: float = 39.0


FLUTED = FlutedParams()


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
