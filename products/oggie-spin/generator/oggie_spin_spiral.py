#!/usr/bin/env python3
"""Oggie Spin Solo SPIRAL -- a full prototype with a vortex optical pattern.

Why this exists
---------------
Conall found a stock spiral-dash pattern and asked whether it would do anything
visually. Simulated, the answer split in two, and both halves matter:

  AT SPEED it does nothing the current rings do not. Rotation about the centre
  maps every point to another point at the SAME radius, so the time-averaged
  image is a function of radius alone -- the angular duty cycle at each r.
  Twist, lean and phase all cancel. A spun spiral is concentric grey bands, and
  so is a spun set of plain dashed rings.

  BELOW that it does two things plain rings physically cannot. A rotating
  spiral reads as flowing inward or outward rather than merely turning, and it
  produces the spiral AFTEREFFECT -- look away after twenty seconds and the
  world swells or shrinks. That is involuntary, it works in ordinary light with
  no stroboscopic flicker, and it outlasts the look. For a fidget toy, spending
  most of its life stationary or turning slowly in someone's hand, that regime
  is arguably the one that matters.

So this is not a replacement for the broken-ring design. It is the other
illusion, and the point of this plate is to hold both in the hand.

The pattern
-----------
Self-similar, which is what the reference images actually are and what a first
simulation got wrong: every feature scales with radius, so ring spacing is
geometric rather than even, dash arc length grows because the ANGULAR extent is
held constant, and radial thickness grows with it.

  five core rings, R9.0 -> R18.1 geometric, 16 dashes each, 9 deg of twist per
  ring -- constant count plus progressive phase is what makes arms appear
  one arm ring at R22.5, 25 dashes, which is the shipped outer ring

Thickness is floored at two extrusion widths. Without the floor the inner rings
come out at 0.7 mm and print as broken dots.

What it costs
-------------
95 whole dashes against 65 on the shipped pattern, and 275 mm of white travel
against 183 mm. That is the stringing problem we spent a day on, up by half
again. Set against that, the arm ring's phase is retuned to 10.8 deg, which
gives ZERO partial dashes -- the shipped pattern has several stubs straddling
the arm edges, so on that count this plate is cleaner than production.

    .venv/bin/python products/oggie-spin/generator/oggie_spin_spiral.py \\
        --out products/oggie-spin/design/active
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_broken_rings as br  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
import oggie_spin_onepiece as solo  # noqa: E402
from ogma import printability  # noqa: E402

OUTPUT_NAME = "Oggie_Spin_Solo_Spiral_P2S.3mf"
MESH_DIR_NAME = "spiral-meshes"
REPORT_NAME = "spiral_report.json"

LINE_WIDTH = 0.42

# --- the spiral ------------------------------------------------------------
# The inner limit is set by the THUMB PAD, not by the bearing counterbore.
# The pad is O20 and sits 0.4 mm above the face, so everything inside R10.00 is
# hidden looking straight down -- and much more than that at any oblique angle:
# the pad is 6.4 mm tall, so at 45 deg it occludes the far side out to R16.4.
#
# The first version started at R9.00. Sixteen of its ninety-five dashes were
# under the pad and could never be seen from any angle, while still costing
# their full share of the white travel that causes the stringing. They are gone.
#
# R10.8 puts the innermost ring's inner edge at R10.38, just clear of the pad.
#
# Worth being honest about what this costs the illusion: the reference spirals
# all converge to a point, and this one cannot. There is a 20 mm thumb pad in
# the middle of it. The Solo's spiral is an annulus, not a vortex, and that is
# structural rather than something a different pattern would fix.
CORE_INNER_R = 10.8
CORE_OUTER_R = 18.1         # stays on the core disc, nothing to clip
CORE_RINGS = 4              # was 5; the innermost lived under the thumb pad
CORE_COUNT = 16             # CONSTANT per ring -- this is what forms the arms
# 12 deg over four rings preserves the 36 deg of total spiral arc that five
# rings gave at 9 deg. Fewer rings with the same twist would have straightened
# the arms out, which is the whole point of the pattern.
CORE_TWIST_DEG = 12.0
CORE_DUTY = 0.50
THICKNESS_PER_RADIUS = 0.078
MIN_THICKNESS = 2 * LINE_WIDTH   # below this the inner rings print as dots

# The shipped outer ring, kept so the arm tips are not bare. Its phase is
# retuned: 10.8 deg is the centre of a 9.2-12.4 window in which every dash
# lands whole inside an arm. The shipped 7.2 deg leaves stubs straddling the
# arm edges -- not an error, since clipping is by intersection, but it looks
# like one on the finished part.
ARM_RING = {"radius_mm": 22.5, "dash_count": 25, "phase_deg": 10.8,
            "duty": br.RING_DUTY, "thickness_mm": br.RING_WIDTH}


def spiral_rings() -> list[dict]:
    ratio = (CORE_OUTER_R / CORE_INNER_R) ** (1.0 / (CORE_RINGS - 1))
    rings = []
    for index in range(CORE_RINGS):
        radius = CORE_INNER_R * ratio ** index
        rings.append(
            {
                "radius_mm": radius,
                "dash_count": CORE_COUNT,
                "phase_deg": index * CORE_TWIST_DEG,
                "duty": CORE_DUTY,
                "thickness_mm": max(
                    MIN_THICKNESS, THICKNESS_PER_RADIUS * radius
                ),
            }
        )
    rings.append(dict(ARM_RING))
    return rings


def dash_polygons(rings: list[dict]):
    """Every dash as a 2D annular sector, in build order."""
    out = []
    for ring in rings:
        pitch = 360.0 / ring["dash_count"]
        extent = pitch * ring["duty"]
        half_t = ring["thickness_mm"] / 2.0
        for index in range(ring["dash_count"]):
            centre = ring["phase_deg"] + index * pitch
            out.append(
                (
                    ring,
                    br._annular_sector(
                        ring["radius_mm"] - half_t,
                        ring["radius_mm"] + half_t,
                        centre - extent / 2.0,
                        centre + extent / 2.0,
                    ),
                )
            )
    return out


def dash_volume(rings: list[dict]) -> trimesh.Trimesh:
    # ONE layer deep, at the Solo's 0.20 mm. Two layers meant every white
    # island was printed twice, which is the whole stringing budget.
    z0 = base.CORE_HEIGHT - solo.SOLO_INLAY_DEPTH
    height = solo.SOLO_INLAY_DEPTH + br.INLAY_TOP_OVERTRAVEL
    pieces = [base._extrude(poly, height, z0) for _ring, poly in dash_polygons(rings)]
    return base._finish(trimesh.util.concatenate(pieces), "spiral cutting volume")


# --- build -----------------------------------------------------------------


def build_meshes(rings: list[dict]):
    body = solo.build_body(extension=0.0)
    base_body, inlay = br._split_flush_inlay(
        body, dash_volume(rings), "Oggie Spin Solo spiral"
    )
    # flush, exactly as the shipping Solo -- the proud cap doubled the white
    # layers and every one of them is a layer of free-standing islands
    inlay, _proud = br._raise_inlay(inlay, "spiral inlay", proud=0.0)
    return [
        ("Oggie Spin Solo spiral body", base_body, 1),
        ("Ivory White spiral inlay", inlay, br.OPTICAL_EXTRUDER),
        ("R188 outer-race retaining ring", complete.build_bearing_ring(), 1),
        ("Tough+ split-collet through-axle hub", complete.build_collet_hub(),
         br.TOUGH_EXTRUDER),
        ("Tough+ through-bore receiver hub", complete.build_receiver_hub(),
         br.TOUGH_EXTRUDER),
        ("Socketed thumb pad 1", complete.build_printed_thumb_pad(
            "socketed thumb pad 1", height=complete.RECEIVER_CAP_HEIGHT,
            central_socket_depth=complete.RECEIVER_CAP_SOCKET_DEPTH), 2),
        ("Socketed thumb pad 2", complete.build_printed_thumb_pad(
            "socketed thumb pad 2", height=complete.RECEIVER_CAP_HEIGHT,
            central_socket_depth=complete.RECEIVER_CAP_SOCKET_DEPTH), 2),
    ]


def audit(rings: list[dict]) -> dict:
    """Measured off the real silhouette, not reasoned about."""
    profile = solo._assembled_silhouette(0.0)
    whole = partial = clipped = 0
    thinnest = float("inf")
    for ring, poly in dash_polygons(rings):
        kept = poly.intersection(profile).area
        if kept >= 0.995 * poly.area:
            whole += 1
        elif kept <= 0.005 * poly.area:
            clipped += 1
        else:
            partial += 1
        arc = math.radians(360.0 / ring["dash_count"] * ring["duty"]) * ring["radius_mm"]
        thinnest = min(thinnest, ring["thickness_mm"], arc)

    extruded = sum(
        math.radians(360.0 / r["dash_count"] * r["duty"]) * r["radius_mm"] * r["dash_count"]
        for r in rings
    )
    travelled = sum(
        2 * math.pi * r["radius_mm"]
        - math.radians(360.0 / r["dash_count"] * r["duty"]) * r["radius_mm"] * r["dash_count"]
        for r in rings
    )
    return {
        "dashes_drawn": whole + partial + clipped,
        "whole_dashes": whole,
        "partial_dashes": partial,
        "clipped_away": clipped,
        "smallest_feature_mm": round(thinnest, 2),
        "white_extruded_mm_per_layer": round(extruded, 1),
        "white_travelled_mm_per_layer": round(travelled, 1),
        "travel_to_extrusion_ratio": round(travelled / extruded, 2),
    }


def generate(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)

    rings = spiral_rings()
    report = audit(rings)
    if report["partial_dashes"]:
        raise RuntimeError(
            f"{report['partial_dashes']} dashes straddle an arm edge; they will "
            "print as stubs. Retune ARM_RING phase_deg"
        )
    if report["smallest_feature_mm"] < MIN_THICKNESS - 1e-6:
        raise RuntimeError(
            f"smallest dash feature is {report['smallest_feature_mm']} mm, "
            f"below {MIN_THICKNESS} mm -- it will print as broken dots"
        )

    built = build_meshes(rings)
    body, inlay = built[0][1], built[1][1]
    if len(body.split(only_watertight=False)) != 1:
        raise RuntimeError("spiral body is not a single shell")
    if not body.is_watertight:
        raise RuntimeError("spiral body is not watertight")
    section = printability._footprint(body, base.CORE_HEIGHT / 2.0)
    hull_ratio = section.area / section.convex_hull.area
    if hull_ratio > 0.90:
        raise RuntimeError(f"arms swallowed into a disc ({hull_ratio:.3f})")

    audits = []
    for name, mesh, _e in built:
        if "inlay" in name.lower():
            # An optical inlay IS many separate islands -- 95 of them here, one
            # per dash, each sitting in its own pocket and held by the body
            # around it rather than by its neighbours. The detached-shells check
            # is right for a body and meaningless for this, which is why
            # complete.audit_printability skips inlays too.
            continue
        rep = printability.audit(
            mesh,
            printability.PrintSpec(layer_height=solo.LAYER_HEIGHT, first_layer_height=0.20),
            name=name,
        )
        if rep.blocking:
            raise RuntimeError(rep.summary())
        audits.append({"part": name, "audit": rep.summary()})

    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_')}.stl"
        mesh.export(path)
        objects.append((name, path, extruder))

    plates = [
        base.Plate(title, comps, solo._plate_position(number, 4))
        for number, (title, comps) in enumerate(solo.SOLO_PLATES_SPEC, start=1)
    ]

    output = out_dir / OUTPUT_NAME
    previous = (base.PLATES, base.FILAMENTS, base._preview_png,
                base._model_settings, base._configure_filament_slots)
    try:
        base.PLATES = plates
        base.FILAMENTS = br.VARIANT_FILAMENTS
        base._preview_png = br._preview_png
        base._model_settings = solo._solo_model_settings(1)
        base._configure_filament_slots = br._configure_variant_filaments
        base.build_bambu_project(output, objects)
    finally:
        (base.PLATES, base.FILAMENTS, base._preview_png,
         base._model_settings, base._configure_filament_slots) = previous
    br._rewrite_variant_project_settings(output)
    br.rewrite_project_settings(
        output,
        {**br.ANTI_STRINGING_SETTINGS, "layer_height": str(solo.LAYER_HEIGHT)},
    )

    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("spiral 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = json.loads(package.read("Metadata/project_settings.config"))
        if settings["curr_bed_type"] != base.BED_TYPE:
            raise RuntimeError("wrong bed type")
        if settings["wall_generator"] != "arachne":
            raise RuntimeError("arachne did not take")

    shipped = {"whole": 65, "extruded": 198.5, "travelled": 183.2}
    (out_dir / REPORT_NAME).write_text(json.dumps({
        "project": output.name,
        "what": (
            "complete Solo prototype carrying a self-similar spiral optical "
            "pattern instead of the three broken rings. Everything else is the "
            "shipping configuration: O52.6, 100% body infill, flush dashes, "
            "concentric top surface, arachne walls, textured PEI, O12.88 pocket."
        ),
        "the_two_regimes": (
            "at speed a spiral is indistinguishable from plain rings -- rotation "
            "preserves radius, so the time-average is the angular duty cycle at "
            "each radius and all angular structure cancels. Below that it gives "
            "apparent radial flow and the spiral aftereffect, neither of which "
            "concentric dashes can produce at any speed."
        ),
        "rings": [
            {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}
            for r in rings
        ],
        "measured": report,
        "against_the_shipped_pattern": {
            "whole_dashes": f"{report['whole_dashes']} vs {shipped['whole']}",
            "white_travel_mm": f"{report['white_travelled_mm_per_layer']} vs {shipped['travelled']}",
            "cost": (
                "about half again more white islands and travel per layer, which "
                "is the stringing budget. Against that, zero partial dashes -- "
                "the shipped arm ring leaves stubs at the arm edges."
            ),
        },
        "how_to_judge": [
            "stationary first, in good light, at arm's length -- this is where a "
            "spiral earns its keep and where the toy spends most of its life",
            "then spin it SLOWLY, about one turn a second, and look for flow "
            "rather than rotation",
            "then stare at it turning for twenty seconds and look at your hand. "
            "If it swells or shrinks, that is the spiral aftereffect and no "
            "version of the ring pattern can do it",
            "then spin it hard. It should look like the current one, because at "
            "speed it is the current one",
            "finally check the top face for stringing against the ring version -- "
            "half again more travel is the price of this pattern",
        ],
        "printability": audits,
    }, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        print(generate(args.out))


if __name__ == "__main__":
    main()
