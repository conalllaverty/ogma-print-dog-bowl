#!/usr/bin/env python3
"""Bearing pocket gauge: measure the fit instead of guessing at it again.

Why this exists
---------------
The pocket has now been guessed at three times. The record:

    Ø12.68  will not install by hand
    Ø12.78  will not install by hand
    Ø12.82  slightly tight
    Ø12.84  needs pliers          <- current
    Ø12.86  falls out under gravity

Read that list again. Ø12.84 needs pliers and Ø12.86 falls out, and they are
0.02 mm apart. Those two results cannot both be properties of the same process:
0.02 mm is a twentieth of a line width. What they actually say is that the
print-to-print variation -- flow calibration, filament batch, how the bore
happens to land against the wall ordering -- is WIDER THAN THE WHOLE DESIGN
WINDOW. Every one of those data points came from a different print, so the
list is not a bracket, it is noise with a decimal point.

No further arithmetic will fix that. The only thing that will is one print
that puts the candidates side by side, on the same plate, in the same filament,
in the same twenty minutes, so the only variable left is the number itself.

What is on the plate
--------------------
Six pucks. Each carries the EXACT bearing feature stack from the real part --
same Ø10.60 shoulder opening, same seat height, same 4.76 mm pocket depth, same
0.40 mm lead-in at the mouth, same Ø15.15 retaining-ring counterbore above it --
so what you feel here is what the spinner will feel like.

    1 dot   Ø12.86
    2 dots  Ø12.90
    3 dots  Ø12.94
    4 dots  Ø12.98
    5 dots  Ø13.02
    6 dots  Ø12.94 RELIEVED -- see below

Dots are recessed into the underside, around R9, well clear of every feature.

The relieved one is the interesting one
---------------------------------------
Pucks 1-5 vary the number. Puck 6 changes the shape of the problem.

Right now the bearing has to slide through 4.76 mm of continuous bore. Every
one of those millimetres is friction, and the whole length has to be within
tolerance at once -- one high spot anywhere and it jams. Puck 6 keeps the bore
at the same nominal diameter but only for a 1.0 mm land at each end, and opens
the 2.76 mm in the middle by 0.30 mm. The bearing is still located by two
lands, which is all concentricity needs, but the sliding contact drops by 58%.

If puck 6 at Ø12.94 goes in with thumb pressure and puck 3 at the same Ø12.94
does not, then the answer was never the diameter -- it was the length of the
engagement, and the pocket should be relieved in the real part.

    .venv/bin/python products/oggie-spin/generator/oggie_spin_bearing_gauge.py \\
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

import numpy as np
import trimesh

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
from ogma import printability  # noqa: E402

OUTPUT_NAME = "Oggie_Spin_Bearing_Gauge_P2S.3mf"
MESH_DIR_NAME = "bearing-gauge-meshes"
REPORT_NAME = "bearing_gauge_report.json"

PUCK_DIAMETER = 26.0
# Only as tall as the features need. The counterbore has to be present because
# that is what the bearing drops through on its way in, but it does not need to
# be the full 14 mm of the real core.
PUCK_HEIGHT = 11.0

RELIEF_LAND = 1.0        # bore held to nominal for this much at each end
RELIEF_EXTRA_D = 0.30    # middle opened by this much on diameter

# (dots, pocket diameter, relieved)
VARIANTS = [
    (1, 12.86, False),
    (2, 12.90, False),
    (3, 12.94, False),
    (4, 12.98, False),
    (5, 13.02, False),
    (6, 12.94, True),
]

MARK_RADIUS = 9.0
MARK_DIAMETER = 2.6
MARK_DEPTH = 0.40
MARK_PITCH_DEG = 22.0

SINGLE_FILAMENT = [("Marine Blue Matte", "#3A8FCF")]

ORIGINAL_FILAMENT_SLOTS = base._configure_filament_slots


def _pocket_cutters(diameter: float, relieved: bool) -> list[trimesh.Trimesh]:
    """The bearing feature stack, identical to the real part except the bore."""
    seat_z = base.BEARING_SEAT_Z
    ring_seat_z = complete.BEARING_RING_SEAT_Z
    cutters = [
        # shoulder: the bearing outer race lands on this
        base._cylinder(
            base.BEARING_SHOULDER_OPENING / 2.0, seat_z + 0.2, -0.1, sections=128
        ),
        # lead-in at the mouth
        complete._loft_polygons(
            [
                (
                    ring_seat_z - complete.BEARING_POCKET_LEAD_IN,
                    complete._circle(diameter / 2.0),
                ),
                (
                    ring_seat_z + 0.01,
                    complete._circle(
                        diameter / 2.0 + complete.BEARING_POCKET_LEAD_IN
                    ),
                ),
            ]
        ),
        # retaining-ring counterbore, open to the top
        base._cylinder(
            complete.BEARING_RING_COUNTERBORE_D / 2.0,
            PUCK_HEIGHT - ring_seat_z + 0.2,
            ring_seat_z,
            sections=128,
        ),
    ]

    if not relieved:
        cutters.append(
            base._cylinder(
                diameter / 2.0, ring_seat_z - seat_z + 0.2, seat_z, sections=128
            )
        )
    else:
        depth = ring_seat_z - seat_z
        if depth <= 2.0 * RELIEF_LAND + 0.4:
            raise RuntimeError(
                f"pocket is only {depth:.2f} mm deep; two {RELIEF_LAND} mm lands "
                "leave nothing to relieve"
            )
        # nominal bore over the full depth...
        cutters.append(
            base._cylinder(diameter / 2.0, depth + 0.2, seat_z, sections=128)
        )
        # ...then open the middle. The step back IN at the top of the relief is
        # a downward-facing annular ledge 0.15 mm wide -- well under one
        # extrusion, so it prints as part of the wall rather than as a bridge.
        cutters.append(
            base._cylinder(
                (diameter + RELIEF_EXTRA_D) / 2.0,
                depth - 2.0 * RELIEF_LAND,
                seat_z + RELIEF_LAND,
                sections=128,
            )
        )
    return cutters


def _identification_dots(dots: int) -> list[trimesh.Trimesh]:
    spacing = 2.0 * MARK_RADIUS * math.sin(math.radians(MARK_PITCH_DEG) / 2.0)
    rib = spacing - MARK_DIAMETER
    if rib < printability.PrintSpec().min_feature:
        raise RuntimeError(
            f"identification dots leave a {rib:.2f} mm rib; they will merge"
        )
    cutters = []
    for index in range(dots):
        angle = math.radians(-90.0 + (index - (dots - 1) / 2.0) * MARK_PITCH_DEG)
        cutter = base._cylinder(
            MARK_DIAMETER / 2.0, MARK_DEPTH + 0.1, -0.1, sections=48
        )
        cutter.apply_translation(
            [MARK_RADIUS * math.cos(angle), MARK_RADIUS * math.sin(angle), 0.0]
        )
        cutters.append(cutter)
    return cutters


def build_puck(dots: int, diameter: float, relieved: bool) -> trimesh.Trimesh:
    blank = base._cylinder(PUCK_DIAMETER / 2.0, PUCK_HEIGHT, 0.0, sections=160)
    puck = base._difference(
        blank, _pocket_cutters(diameter, relieved), f"gauge {dots}"
    )

    before = float(puck.volume)
    puck = base._difference(puck, _identification_dots(dots), f"gauge {dots} dots")
    expected = dots * math.pi * (MARK_DIAMETER / 2.0) ** 2 * MARK_DEPTH
    removed = before - float(puck.volume)
    if abs(removed - expected) > 0.02 * expected:
        raise RuntimeError(
            f"gauge {dots}: dots removed {removed:.2f} mm3, expected "
            f"{expected:.2f} mm3 -- a dot is off the face"
        )
    return complete._weld_shells(puck, f"gauge {dots}")


def _measure_bore(mesh: trimesh.Trimesh, diameter: float, relieved: bool) -> dict:
    """Measure the bore off the built mesh, at the land and at the relief.

    The whole point of this plate is that the number in the file is the number
    on the plate. Checking the mesh rather than trusting the constant is how the
    12.8197 measurement was taken last time, and it was the one part of that
    round that was actually sound.
    """
    seat_z = base.BEARING_SEAT_Z
    ring_seat_z = complete.BEARING_RING_SEAT_Z
    result = {}
    probes = [("land_bottom", seat_z + RELIEF_LAND / 2.0)]
    if relieved:
        probes.append(("relief_middle", (seat_z + ring_seat_z) / 2.0))
    for label, z in probes:
        section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        planar, _ = section.to_planar()
        # the bore is the interior ring closest to the axis
        radii = []
        for entity in planar.entities:
            points = planar.vertices[entity.points]
            radii.append(float(np.hypot(points[:, 0], points[:, 1]).mean()))
        result[label + "_mm"] = round(2.0 * min(radii), 4)
    return result


def generate(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)

    built = []
    measurements = []
    for dots, diameter, relieved in VARIANTS:
        puck = build_puck(dots, diameter, relieved)
        if len(puck.split(only_watertight=False)) != 1:
            raise RuntimeError(f"gauge {dots} is not a single shell")
        measured = _measure_bore(puck, diameter, relieved)
        if abs(measured["land_bottom_mm"] - diameter) > 0.01:
            raise RuntimeError(
                f"gauge {dots} bore measures {measured['land_bottom_mm']} mm, "
                f"asked for {diameter} mm"
            )
        report = printability.audit(
            puck,
            printability.PrintSpec(layer_height=0.16, first_layer_height=0.20),
            name=f"gauge {dots}",
        )
        if report.blocking:
            raise RuntimeError(report.summary())
        built.append((f"Gauge {dots} d{diameter:.2f}", puck, 1))
        measurements.append(
            {
                "dots": dots,
                "nominal_pocket_mm": diameter,
                "relieved": relieved,
                "clearance_on_R188_mm": round(diameter - base.R188_OD, 3),
                **measured,
                "audit": report.summary(),
            }
        )

    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_')}.stl"
        mesh.export(path)
        objects.append((name, path, extruder))

    pitch = PUCK_DIAMETER + 8.0
    comps = []
    for index in range(len(built)):
        row, col = divmod(index, 3)
        comps.append(
            (index + 1, (col - 1) * pitch, (0.5 - row) * pitch, 0.0)
        )
    plates = [base.Plate("Bearing pocket gauge", tuple(comps), (128.0, 128.0, 0.0))]

    output = out_dir / OUTPUT_NAME
    previous = (base.PLATES, base.FILAMENTS, base._configure_filament_slots)

    def _slots(settings: dict) -> None:
        keep = base.FILAMENTS
        try:
            base.FILAMENTS = SINGLE_FILAMENT
            ORIGINAL_FILAMENT_SLOTS(settings)
        finally:
            base.FILAMENTS = keep

    try:
        base.PLATES = plates
        base.FILAMENTS = SINGLE_FILAMENT
        base._configure_filament_slots = _slots
        base.build_bambu_project(output, objects)
    finally:
        (base.PLATES, base.FILAMENTS, base._configure_filament_slots) = previous

    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("gauge 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = json.loads(package.read("Metadata/project_settings.config"))
        if settings["curr_bed_type"] != base.BED_TYPE:
            raise RuntimeError("gauge carries the wrong bed type")

    (out_dir / REPORT_NAME).write_text(
        json.dumps(
            {
                "project": output.name,
                "why": (
                    "the pocket has been guessed three times. 12.84 needs "
                    "pliers and 12.86 falls out, 0.02 mm apart -- the "
                    "print-to-print variation is wider than the design window, "
                    "so the existing numbers are noise, not a bracket. This "
                    "plate puts every candidate in one print."
                ),
                "bearing": {
                    "designation": "R188",
                    "outer_diameter_mm": base.R188_OD,
                    "width_mm": base.R188_WIDTH,
                },
                "current_shipped_pocket_mm": base.BEARING_POCKET_DIAMETER,
                "variants": measurements,
                "relief": {
                    "land_mm": RELIEF_LAND,
                    "extra_diameter_mm": RELIEF_EXTRA_D,
                    "sliding_contact_reduction": "58%",
                    "hypothesis": (
                        "if puck 6 seats by thumb and puck 3 at the same "
                        "diameter does not, the problem was engagement length, "
                        "not diameter, and the real pocket should be relieved"
                    ),
                },
                "how_to_judge": [
                    "use the SAME bearing in every puck, in order, and put it "
                    "in and out twice -- a pocket that is right the first time "
                    "and loose the second is shaving, not fitting",
                    "the one you want goes in with steady thumb pressure and "
                    "does not fall out when you turn the puck over and tap it",
                    "if two adjacent pucks both feel right, take the smaller",
                    "if NONE of 1-5 feel right but 6 does, tell me and I will "
                    "relieve the pocket in the real part rather than chase the "
                    "diameter any further",
                    "then give me the dot count and I will set the constant "
                    "from it once, with the measurement written down",
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
