#!/usr/bin/env python3
"""Bowl-seat fit coupons for the one-piece stand.

Three 60° sectors of the *proposed* seat — a 45° self-supporting cone instead of
the current horizontal ledge — at three candidate opening diameters. Offer the
real stainless bowl to each and keep the one that seats.

Why sectors: the question is radial, so a sixth of the ring answers it for a
sixth of the plastic and about a twentieth of the time. Each is printed in the
same orientation the real part would be, so it also proves the cone prints
without support rather than only that it models cleanly.

Ø133 is the current opening and is there as the control: if the bowl seats on
that one too, the opening was never the constraint and the redesign is free.

    .venv/bin/python products/dog-bowl/coupons/bowl_seat_test.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

COUPON_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in COUPON_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (COUPON_DIR, COUPON_DIR.parent / "generator", _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

import cooper_bowl_design as design  # noqa: E402

OUT = _REPO / "out" / "coupons"

SECTOR_DEG = 60.0
WALL_STUB = 8.0          # drum wall below the cone, so it prints as it would
CONE_DEG = 45.0          # the angle the whole exercise is about
LABEL_HEIGHT = 6.0
LABEL_PROUD = 0.6
FOOT_HEIGHT = 2.0        # coupon-only bed flange, see build_ring

# Ø133 current · Ø136 proposed · Ø139 margin
OPENINGS_MM = (133.0, 136.0, 139.0)


def _sector(opening_d: float, sweep_deg: float | None = None) -> trimesh.Trimesh:
    """A wedge — or, with sweep_deg=None, the whole ring — of the proposed seat.

    Standing the way it would on the stand, so the print also proves the cone
    is self-supporting rather than only that it models cleanly.
    """
    r_open = opening_d / 2.0
    r_in = design.WALL_INNER_R
    r_wall = design.WALL_OUTER_R
    r_out = design.STAND_OD / 2.0
    r_seat = design.BOWL_SEAT_D / 2.0

    rise = (r_in - r_open) * math.tan(math.radians(CONE_DEG))
    z_cone = 0.0                      # coupon starts where the cone starts
    z_top_ring = z_cone + rise        # where the ledge used to be (stand z=72)
    z_top = z_top_ring + (design.STAND_HEIGHT - design.TOP_BOTTOM)
    z_seat = z_top - design.BOWL_RIM_RECESS

    profile = np.array([
        [r_in,   -WALL_STUB],
        [r_wall, -WALL_STUB],
        [r_wall, z_top_ring - (r_out - r_wall)],   # 45° flare, also self-supporting
        [r_out,  z_top_ring],
        [r_out,  z_top],
        [r_seat, z_top],
        [r_seat, z_seat],
        [r_open, z_top_ring],                      # seat cone the rim lands on
        [r_in,   z_cone],                          # <-- the 45° underside
        [r_in,   -WALL_STUB],
    ])
    sweep = SECTOR_DEG if sweep_deg is None else sweep_deg
    full = sweep >= 360.0
    wedge = trimesh.creation.revolve(
        profile,
        angle=None if full else math.radians(sweep),
        sections=256 if full else 96,
        cap=not full,
    )
    wedge.apply_translation([0.0, 0.0, WALL_STUB])   # sit on the bed
    return wedge


def _label(text: str, r_mid: float, z_top: float) -> trimesh.Trimesh | None:
    """Emboss the opening diameter on the flat top, so they can't be mixed up.

    Placed on +X, which is where the wedge is *after* it has been rotated to
    straddle that axis. `revolve` sweeps from 0 to +60°, so putting the digits on
    +Y — the obvious-looking choice — leaves them floating in mid-air beside the
    part: they union into a second disconnected body whose flat underside is a
    90° overhang, and the coupon quietly needs support to print.
    """
    solids = []
    advance = 0.0
    for ch in text:
        poly = design.glyph_polygon(ch, target_height=LABEL_HEIGHT)
        poly = poly[0] if isinstance(poly, tuple) else poly
        body = trimesh.creation.extrude_polygon(poly, height=LABEL_PROUD, engine="earcut")
        body.apply_translation([advance, 0.0, 0.0])
        advance += (poly.bounds[2] - poly.bounds[0]) + 1.2
        solids.append(body)
    if not solids:
        return None
    glyphs = trimesh.util.concatenate(solids)
    # Centre the run of digits on the origin, stand them tangentially, then move
    # out to the middle of the top annulus on +X.
    glyphs.apply_translation([-(advance - 1.2) / 2.0, 0.0, 0.0])
    glyphs.apply_transform(
        trimesh.transformations.rotation_matrix(math.radians(90.0), [0, 0, 1])
    )
    glyphs.apply_translation([r_mid, 0.0, z_top - LABEL_PROUD / 2.0])
    return glyphs


def build() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    plate: list[trimesh.Trimesh] = []

    for index, opening in enumerate(OPENINGS_MM):
        wedge = _sector(opening)
        wedge.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(-SECTOR_DEG / 2.0), [0, 0, 1]
            )
        )
        z_top = float(wedge.bounds[1][2])
        r_mid = (design.BOWL_SEAT_D / 2.0 + design.STAND_OD / 2.0) / 2.0
        text = _label(f"{opening:.0f}", r_mid, z_top)
        if text is not None:
            wedge = trimesh.boolean.union([wedge, text], engine="manifold")

        path = OUT / f"bowl_seat_coupon_{opening:.0f}.stl"
        wedge.export(path)
        written.append(path)

        copy = wedge.copy()
        copy.apply_translation([(index - 1) * 95.0, 0.0, 0.0])
        plate.append(copy)

    combined = trimesh.util.concatenate(plate)
    plate_path = OUT / "bowl_seat_coupons_PLATE.stl"
    combined.export(plate_path)
    written.append(plate_path)

    for w in written:
        print(f"  {w.relative_to(_REPO)}")
    m = trimesh.util.concatenate(plate)
    lo, hi = m.bounds
    print(f"\n  plate footprint {hi[0]-lo[0]:.0f} x {hi[1]-lo[1]:.0f} x {hi[2]-lo[2]:.0f} mm")
    print(f"  total volume    {m.volume/1000:.1f} cm3")
    return written


def build_ring(opening_d: float) -> Path:
    """A full 360° ring at one opening — the test the sectors cannot do.

    A 60° sector has no ring for the bowl to fall through, so it is silent on
    the two things that actually decide the opening: whether the bowl drops
    through, and whether it centres itself rather than sitting off to one side.
    That is worth a longer print exactly once, on the diameter the sectors
    narrowed us to.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    ring = _sector(opening_d, sweep_deg=360.0)

    # A foot, for the coupon only.
    #
    # Cut short, the ring stands 25 mm tall on a 4 mm-wide annulus — about
    # 2,000 mm² of bed contact on a 170 mm diameter, which is asking it to lift
    # at the edges and take the seat geometry out of round with it. On the real
    # stand the whole drum is underneath and none of this applies, so this is
    # test scaffolding rather than a design feature. Kept to 2 mm so it snaps or
    # trims off without disturbing what is being measured.
    foot = trimesh.creation.cylinder(
        radius=design.STAND_OD / 2.0, height=FOOT_HEIGHT, sections=256
    )
    foot.apply_translation([0.0, 0.0, FOOT_HEIGHT / 2.0])
    bore = trimesh.creation.cylinder(
        radius=design.WALL_INNER_R, height=FOOT_HEIGHT * 3, sections=256
    )
    bore.apply_translation([0.0, 0.0, FOOT_HEIGHT / 2.0])
    ring = trimesh.boolean.union(
        [ring, trimesh.boolean.difference([foot, bore], engine="manifold")],
        engine="manifold",
    )
    r_mid = (design.BOWL_SEAT_D / 2.0 + design.STAND_OD / 2.0) / 2.0
    text = _label(f"{opening_d:.0f}", r_mid, float(ring.bounds[1][2]))
    if text is not None:
        ring = trimesh.boolean.union([ring, text], engine="manifold")
    path = OUT / f"bowl_seat_RING_{opening_d:.0f}.stl"
    ring.export(path)
    lo, hi = ring.bounds
    print(f"  {path.relative_to(_REPO)}")
    print(f"    {hi[0]-lo[0]:.0f} x {hi[1]-lo[1]:.0f} x {hi[2]-lo[2]:.0f} mm, "
          f"{ring.volume/1000:.1f} cm3, watertight={ring.is_watertight}")
    return path


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ring", type=float, default=None,
                    help="Build one full ring at this opening Ø instead of the sectors.")
    a = ap.parse_args()
    if a.ring is not None:
        build_ring(a.ring)
    else:
        build()
