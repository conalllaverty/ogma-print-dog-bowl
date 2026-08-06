#!/usr/bin/env python3
"""One-arm sanity plate: a core sector plus a single arm, on one plate.

Why this exists
---------------
Four full revisions of the arm joint were built on arithmetic alone, and three
separate defects — a mirrored export, a missing push-through stop and a floating
cantilever — were found by eye in the slicer or would only have shown up on the
bed. Any one of them would have been caught by printing a single arm against a
single slot.

This is that print. It is a ~15 minute, few-gram part that answers the questions
arithmetic cannot:

  1. Does the barb actually snap into its pocket?
  2. Does the arm stop when you push it, or slide through?
  3. Does it pull off at roughly the predicted force?
  4. Does the clip beam print cleanly, or does its first layer droop?
  5. Is the barb visible and reachable in the recess on the far face?

Run it before committing to the nine-plate project, not after.

    .venv/bin/python backend/generator/oggie_spin_sanity_plate.py \\
        --out design/modular-spinner/active/sanity-plate
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Polygon

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
import printability  # noqa: E402

SECTOR_HALF_DEG = 46.0        # comfortably wider than the arm's +/-20 deg
KEEP_INNER_R = 8.0            # keep enough hub to be rigid, drop the bearing seat


def _sector_wedge() -> trimesh.Trimesh:
    """A pie slice of the full core, centred on slot 0."""
    steps = 64
    angles = np.linspace(
        math.radians(-90.0 - SECTOR_HALF_DEG),
        math.radians(-90.0 + SECTOR_HALF_DEG),
        steps + 1,
    )
    outer = [(30.0 * math.cos(a), 30.0 * math.sin(a)) for a in angles]
    poly = Polygon([(0.0, 0.0)] + outer)
    return base._extrude(poly, base.CORE_HEIGHT + 2.0, -1.0)


def build_sector() -> trimesh.Trimesh:
    """The real core, cut down to one slot. Nothing about the slot is changed."""
    core = complete.build_complete_core()
    wedge = _sector_wedge()
    sector = trimesh.boolean.intersection([core, wedge], engine="manifold")
    if sector is None or sector.is_empty:
        raise RuntimeError("sector intersection failed")
    # Fill the bearing bore back in: this coupon has no bearing and the thin
    # remaining hub would be fragile.
    plug = base._cylinder(KEEP_INNER_R, base.CORE_HEIGHT, 0.0, sections=96)
    plug = trimesh.boolean.intersection([plug, wedge], engine="manifold")
    merged = trimesh.boolean.union([sector, plug], engine="manifold")
    return base._finish(merged, "sanity core sector")


def generate(out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    sector = build_sector()
    arm = complete.build_arm("sanity arm")

    parts = [("01_core_sector_one_slot", sector), ("02_single_arm", arm)]
    report = complete.audit_printability([(n, m) for n, m in parts])

    for name, mesh in parts:
        mesh.export(mesh_dir / f"{name}.stl")

    # Prove the pair actually assembles, using only rigid motions on the meshes
    # that were just written to disk.
    reloaded = {n: trimesh.load(mesh_dir / f"{n}.stl") for n, _ in parts}
    placed = reloaded["02_single_arm"].copy()
    placed.apply_transform(
        printability.assert_rigid(
            trimesh.transformations.rotation_matrix(
                math.radians(-90.0), [0.0, 0.0, 1.0]
            ),
            "arm into slot 0",
        )
    )

    def clash(a, b) -> float:
        hit = trimesh.boolean.intersection([a, b], engine="manifold")
        return 0.0 if hit is None or hit.is_empty else round(float(hit.volume), 6)

    seated = clash(reloaded["01_core_sector_one_slot"], placed)
    pushed = placed.copy()
    pushed.apply_translation([0.0, 0.0, -0.50])
    lifted = placed.copy()
    lifted.apply_translation([0.0, 0.0, 0.30])

    checks = {
        "seated_interference_mm3": seated,
        "push_through_0.50mm_interference_mm3": clash(
            reloaded["01_core_sector_one_slot"], pushed
        ),
        "lift_0.30mm_interference_mm3": clash(
            reloaded["01_core_sector_one_slot"], lifted
        ),
        "verified_on": "the exported STLs, moved by rotations only",
    }
    if seated > 0.001:
        raise RuntimeError(f"sanity pair does not seat: {seated} mm³")
    if checks["push_through_0.50mm_interference_mm3"] <= 0.5:
        raise RuntimeError("no push-through stop: the arm slides through")
    if checks["lift_0.30mm_interference_mm3"] <= 0.0:
        raise RuntimeError("no retention: the barb does not bite on lift")

    summary = {
        "purpose": "physical sanity check before the nine-plate project",
        "parts": [n for n, _ in parts],
        "print": {
            "material": "any Bambu PLA Matte; colour is irrelevant",
            "layer_height_mm": 0.16,
            "supports": "OFF",
            "note": "both parts print in the same orientation as the real ones",
        },
        "what_to_check": [
            "the arm snaps into the slot with about 1.2 N, one finger",
            "push hard: the ledge stops it, the arm does not slide through",
            "pull straight up: it releases at about 2.2 N with no tool",
            "turn it over: the barb is visible in its recess and reachable",
            "look at the clip beam's first layers: no droop, no weld to the tongue",
        ],
        "geometry_checks": checks,
        "printability": report,
    }
    (out_dir / "sanity_plate.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("design/modular-spinner/active/sanity-plate"),
    )
    args = parser.parse_args()
    summary = generate(args.out)
    print(json.dumps(summary["geometry_checks"], indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
