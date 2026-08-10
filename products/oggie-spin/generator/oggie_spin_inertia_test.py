#!/usr/bin/env python3
"""Heft and inertia A/B/C plate: which lever actually changes the spin?

The correction that produced this plate
---------------------------------------
Conall asked whether arm length, shape or density would move the spin or the
feel. I answered off the SOLID model and got the ranking backwards. I said the
core was "37% of the mass for 16% of the inertia" and called hollowing it the
free lever; I put length last.

Re-run against the part as PRINTED -- 5 walls, 6/6 shell layers, 25% gyroid,
calibrated so the model reproduces Bambu's own 16.74 g slice of a one-up Solo
(see _inertia_model.py) -- the ranking inverts:

    lever                          mass       I       spin    per gram
    ---------------------------------------------------------------
    infill 25% -> 100%           +10.0 g   +41.7%    x1.19    +4.2 %/g
    pocket out the middle         -1.1 g    -3.5%    x0.98    worthless
    arms +4 mm (OD 52.6 -> 60.3)  +3.4 g   +51.6%    x1.23   +15.2 %/g

Why I was wrong: the Solo is 80% shell. Only 3.3 g of the 16.7 g is infill, and
NONE of that infill lies beyond R23 -- the arms are so narrow that five walls
meet in the middle of them and they print solid whatever the density says. So
infill can only add mass to the core, at a mean radius of 15.2 mm, which is
INSIDE the body's own radius of gyration (18.65 mm). Every gram infill adds has
below-average leverage; that is why 60% more mass buys only 42% more inertia,
and why it drives k down from 18.65 to 17.56 mm.

And hollowing the middle fails for the same reason in reverse: the middle is
already mostly shell, and cutting a pocket into it just grows new shell around
the pocket walls. Measured, it loses 3.5% of the inertia to save 1.1 g. It is
not the free lever. It is not a lever at all. That variant is deliberately NOT
on this plate -- there is no point spending 40 minutes of printer time proving a
number I can already show is negative.

Length is the free lever, because length is the only one that puts mass where
r^2 is large. Note also k/R = 0.709 against a uniform disc's 0.707: as a
flywheel the five-arm silhouette is exactly as good as a plain disc of the same
diameter and no better. The shape is doing nothing for the spin. It is doing the
work for the LOOK, which is a fine reason to keep it -- just not a spin reason.

What is on the plate
--------------------
Three bodies, one plate, one filament, identified by dots on the underside:

  1 dot   Baseline        OD 52.6, 25% gyroid   16.7 g   reference
  2 dots  Heavy           OD 52.6, 100% gyroid  26.7 g   +42% I, x1.19 spin
  3 dots  Long arms       OD 60.3, 25% gyroid   20.1 g   +52% I, x1.23 spin

2 and 3 are the point of the plate: they land on essentially the SAME predicted
spin gain by opposite means, one by adding 10 g and one by adding 3.4 g. No
amount of arithmetic can tell you which of those is more fun to hold. Spinning
them back to back can, in about fifteen seconds.

The optical inlay is left off all three. It is 0.13 g at R22.5, which is 1.1% of
the inertia, and dropping it makes this a single-filament print: no prime tower,
no purge, roughly half the time. Colour is not the variable under test.

    .venv/bin/python products/oggie-spin/generator/oggie_spin_inertia_test.py \\
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
from shapely.affinity import rotate as _rotate
from shapely.affinity import translate as _translate
from shapely.geometry import Point as _Point
from shapely.geometry import Polygon
from shapely.ops import unary_union as _shapely_union

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
import oggie_spin_onepiece as solo  # noqa: E402
from ogma import printability  # noqa: E402
from ogma import inertia  # noqa: E402

# Captured BEFORE anything monkey-patches base, or the settings factory below
# would call itself: build_bambu_project reads base._model_settings at call
# time, and the factory is what we put there.
ORIGINAL_MODEL_SETTINGS = base._model_settings
ORIGINAL_FILAMENT_SLOTS = base._configure_filament_slots

OUTPUT_NAME = "Oggie_Spin_Inertia_Test_P2S.3mf"
MESH_DIR_NAME = "inertia-test-meshes"
REPORT_NAME = "inertia_test_report.json"

# (dots, label, arm extension mm, sparse infill)
VARIANTS = [
    (1, "Baseline", 0.0, "25%"),
    (2, "Heavy", 0.0, "100%"),
    (3, "Long arms", 4.0, "25%"),
]

ARM_EXTENSION_STEP = 0.25   # sweep resolution when lengthening an arm

# Identification dots go on the underside of the CORE disc, not the arms. My
# first attempt put them at R24 on an arm and the volume check caught it: the
# 0.40 mm bottom chamfer means the outermost 0.40 mm of every layer below
# Z 0.40 is inset, so a dot near the arm hangs partly over the chamfer and
# removes only 63% of its own volume. At R12 the underside is an uninterrupted
# disc on all three variants, and the dots are identical on all three so they
# cancel out of every comparison anyway.
MARK_RADIUS = 12.0
MARK_DIAMETER = 2.6
MARK_DEPTH = 0.40
MARK_PITCH_DEG = 18.0

SINGLE_FILAMENT = [("Marine Blue Matte", "#3A8FCF")]


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


def extended_profile(extension: float) -> Polygon:
    """The Solo silhouette with each arm pushed `extension` mm further out.

    The arm's outboard shadow is swept radially rather than translated. A plain
    translation detaches the lobe from the core the moment `extension` exceeds
    the overlap -- I tried it, and at 2 mm the union quietly returned just the
    R20 core disc with an area of exactly pi*400, which every downstream check
    would have passed. Sweeping leaves a stem of the arm's own cross-section
    behind it, so the arm gets LONGER without getting wider and without ever
    letting go of the core.
    """
    arm = complete.build_arm("arm length source")
    shadow = _shapely_union(
        [
            printability._footprint(arm, z)
            for z in np.linspace(0.3, base.CORE_HEIGHT - 0.3, 24)
            if printability._footprint(arm, z) is not None
        ]
    )
    core_disc = _Point(0.0, 0.0).buffer(base.CORE_DIAMETER / 2.0, resolution=64)
    outboard = shadow.difference(
        _Point(0.0, 0.0).buffer(base.CORE_DIAMETER / 2.0 - 0.15, resolution=64)
    )
    if extension > 0.0:
        steps = max(2, int(round(extension / ARM_EXTENSION_STEP)) + 1)
        outboard = _shapely_union(
            [
                _translate(outboard, xoff=extension * t)
                for t in np.linspace(0.0, 1.0, steps)
            ]
        )
    lobes = [
        _rotate(outboard, -90.0 + 72.0 * index, origin=(0.0, 0.0))
        for index in range(5)
    ]
    profile = _shapely_union([core_disc, *lobes])
    components = printability._components(profile)
    if len(components) != 1:
        raise RuntimeError(
            f"arm extension {extension} mm left {len(components)} disconnected "
            "islands; the lobes have come off the core"
        )
    profile = Polygon(components[0].exterior)
    if not profile.is_valid:
        profile = profile.buffer(0)
    return profile.buffer(solo.ROOT_FILLET, join_style=1).buffer(
        -solo.ROOT_FILLET, join_style=1
    )


def _bearing_cutters() -> list[trimesh.Trimesh]:
    """Exactly the Solo's bearing features -- shared so a variant cannot drift."""
    return [
        base._cylinder(
            base.BEARING_POCKET_DIAMETER / 2.0,
            complete.BEARING_RING_SEAT_Z - base.BEARING_SEAT_Z + 0.2,
            base.BEARING_SEAT_Z,
            sections=128,
        ),
        complete._loft_polygons(
            [
                (
                    complete.BEARING_RING_SEAT_Z - complete.BEARING_POCKET_LEAD_IN,
                    complete._circle(base.BEARING_POCKET_DIAMETER / 2.0),
                ),
                (
                    complete.BEARING_RING_SEAT_Z + 0.01,
                    complete._circle(
                        base.BEARING_POCKET_DIAMETER / 2.0
                        + complete.BEARING_POCKET_LEAD_IN
                    ),
                ),
            ]
        ),
        base._cylinder(
            complete.BEARING_RING_COUNTERBORE_D / 2.0,
            base.CORE_HEIGHT - complete.BEARING_RING_SEAT_Z + 0.2,
            complete.BEARING_RING_SEAT_Z,
            sections=128,
        ),
        base._cylinder(
            base.BEARING_SHOULDER_OPENING / 2.0,
            base.BEARING_SEAT_Z + 0.2,
            -0.1,
            sections=128,
        ),
    ]


def _identification_dots(dots: int) -> list[trimesh.Trimesh]:
    """`dots` shallow marks on the UNDERSIDE of the core disc.

    The rib left between adjacent dots is a real printed feature and it has to
    be thick enough to exist. At 14 deg pitch the audit flagged it: centres
    2.93 mm apart on a 2.60 mm dot leaves a 0.33 mm rib, which at 0.42 mm line
    width does not print -- the dots would merge into one slot and 2 and 3 would
    become indistinguishable, quietly ruining the identification the whole plate
    depends on. Checked here rather than left to a warning nobody reads.
    """
    spacing = 2.0 * MARK_RADIUS * math.sin(math.radians(MARK_PITCH_DEG) / 2.0)
    rib = spacing - MARK_DIAMETER
    if rib < printability.PrintSpec().min_feature:
        raise RuntimeError(
            f"identification dots leave a {rib:.2f} mm rib between them; "
            f"below {printability.PrintSpec().min_feature} mm they will merge "
            "and the bodies stop being identifiable"
        )
    cutters = []
    for index in range(dots):
        angle = math.radians(
            -90.0 + (index - (dots - 1) / 2.0) * MARK_PITCH_DEG
        )
        # height MARK_DEPTH + 0.1 starting at -0.1 cuts exactly MARK_DEPTH into
        # the part, so the expected-volume check below is an equality rather
        # than an approximation
        cutter = base._cylinder(
            MARK_DIAMETER / 2.0, MARK_DEPTH + 0.1, -0.1, sections=48
        )
        cutter.apply_translation(
            [
                MARK_RADIUS * math.cos(angle),
                MARK_RADIUS * math.sin(angle),
                0.0,
            ]
        )
        cutters.append(cutter)
    return cutters


def build_variant(dots: int, extension: float) -> trimesh.Trimesh:
    blank = solo._stepped_body(extended_profile(extension))
    body = base._difference(
        blank, _bearing_cutters(), f"inertia variant {dots}"
    )
    body = complete._weld_shells(body, f"inertia variant {dots}")

    before = float(body.volume)
    body = base._difference(
        body, _identification_dots(dots), f"inertia variant {dots} dots"
    )
    # A dot that hangs off the edge of the arm removes less than a full
    # cylinder, and a dot placed off the arm entirely removes nothing at all --
    # either way the bodies stop being distinguishable and the whole plate is
    # wasted. Check the material actually came out.
    expected = dots * math.pi * (MARK_DIAMETER / 2.0) ** 2 * MARK_DEPTH
    removed = before - float(body.volume)
    if abs(removed - expected) > 0.02 * expected:
        raise RuntimeError(
            f"variant {dots}: identification dots removed {removed:.2f} mm3, "
            f"expected {expected:.2f} mm3 -- a dot is off the edge of the arm"
        )
    return complete._weld_shells(body, f"inertia variant {dots} marked")


def build_meshes() -> list[tuple[str, trimesh.Trimesh, int]]:
    built = []
    for dots, label, extension, _infill in VARIANTS:
        body = build_variant(dots, extension)
        built.append((f"{dots}dot {label}", body, 1))
    return built


# ---------------------------------------------------------------------------
# Bambu project
# ---------------------------------------------------------------------------


def _model_settings_factory(built):
    """Per-part sparse_infill_density.

    Same mechanism the shipped project already uses to give the arms 100% grid
    infill, so it is a proven key rather than a hopeful one. Everything else is
    pinned to the project default explicitly, so that a future change to the
    defaults cannot silently make two of these bodies differ by something other
    than the variable under test.
    """
    infill_by_id = {
        index: infill
        for index, (_d, _l, _e, infill) in enumerate(VARIANTS, start=1)
    }

    def _settings(objects, meshes) -> bytes:
        root = ET.fromstring(ORIGINAL_MODEL_SETTINGS(objects, meshes))
        for part_id, infill in infill_by_id.items():
            part = root.find(f".//part[@id='{part_id}']")
            if part is None:
                raise RuntimeError(f"missing body part {part_id}")
            _set(part, "sparse_infill_density", infill)
            _set(part, "sparse_infill_pattern", "gyroid")
            _set(part, "wall_loops", "5")
            _set(part, "top_shell_layers", "6")
            _set(part, "bottom_shell_layers", "6")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    return _settings


def _set(node: ET.Element, key: str, value: str) -> None:
    for meta in node.findall("./metadata"):
        if meta.get("key") == key:
            meta.set("value", value)
            return
    ET.SubElement(node, "metadata", {"key": key, "value": value})


def _plate_layout(built) -> list[base.Plate]:
    radii = [
        float(np.hypot(mesh.vertices[:, 0], mesh.vertices[:, 1]).max())
        for _n, mesh, _e in built
    ]
    gap = 8.0
    xs = [0.0]
    for left, right in zip(radii[:-1], radii[1:]):
        xs.append(xs[-1] + left + right + gap)
    centre = (xs[0] + xs[-1]) / 2.0
    xs = [x - centre for x in xs]

    span = (xs[-1] + radii[-1]) - (xs[0] - radii[0])
    if span > 250.0:
        raise RuntimeError(f"three bodies span {span:.1f} mm; the bed is 256 mm")

    comps = tuple((index, x, 0.0, 0.0) for index, x in enumerate(xs, start=1))
    return [base.Plate("Inertia A/B/C", comps, (128.0, 128.0, 0.0))]


def _single_filament_slots(settings: dict) -> None:
    previous = base.FILAMENTS
    try:
        base.FILAMENTS = SINGLE_FILAMENT
        ORIGINAL_FILAMENT_SLOTS(settings)
    finally:
        base.FILAMENTS = previous


# ---------------------------------------------------------------------------
# Measurement and validation
# ---------------------------------------------------------------------------


def measure(built) -> list[dict]:
    rows = []
    for (dots, label, extension, infill), (_name, mesh, _e) in zip(VARIANTS, built):
        printed = inertia.PrintedBody(mesh)
        printed.set_shell(*inertia.calibrated_shell())
        summary = printed.summary(float(infill.rstrip("%")) / 100.0)
        rows.append(
            {
                "dots": dots,
                "label": label,
                "arm_extension_mm": extension,
                "sparse_infill": infill,
                "outer_diameter_mm": round(
                    2.0
                    * float(np.hypot(mesh.vertices[:, 0], mesh.vertices[:, 1]).max()),
                    2,
                ),
                "predicted_mass_g": round(summary["mass_g"], 2),
                "inertia_g_mm2": round(summary["inertia_g_mm2"]),
                "radius_of_gyration_mm": round(summary["radius_of_gyration_mm"], 2),
            }
        )
    reference = rows[0]["inertia_g_mm2"]
    for row in rows:
        ratio = row["inertia_g_mm2"] / reference
        row["inertia_vs_baseline"] = f"{100.0 * (ratio - 1.0):+.1f}%"
        # fixed flick energy, same bearing: t ~ sqrt(I)
        row["predicted_spin_time_vs_baseline"] = f"x{math.sqrt(ratio):.2f}"
    return rows


def _audit(built) -> list[dict]:
    spec = printability.PrintSpec(layer_height=0.16, first_layer_height=0.20)
    findings = []
    for name, mesh, _e in built:
        report = printability.audit(mesh, spec, name=name)
        if report.blocking:
            raise RuntimeError(f"{name} failed the printability audit:\n{report.summary()}")
        findings.append({"body": name, "audit": report.summary()})
    return findings


def generate(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)

    built = build_meshes()

    # --- anti-regression: the arms must still be arms ------------------------
    for (dots, label, extension, _i), (name, mesh, _e) in zip(VARIANTS, built):
        if len(mesh.split(only_watertight=False)) != 1:
            raise RuntimeError(f"{name} is not a single shell")
        if not mesh.is_watertight:
            raise RuntimeError(f"{name} is not watertight")
        section = printability._footprint(mesh, base.CORE_HEIGHT / 2.0)
        ratio = section.area / section.convex_hull.area
        # a solid disc scores 1.0; losing the arms to a convex hull is how the
        # Solo silhouette failed silently once already
        if ratio > 0.85:
            raise RuntimeError(
                f"{name} section fills {ratio:.3f} of its convex hull; the arms "
                "have merged into a disc"
            )
        gap_reaches_core = section.buffer(-0.01).intersection(
            _Point(0.0, 0.0).buffer(base.CORE_DIAMETER / 2.0 + 1.0)
        )
        if gap_reaches_core.area >= math.pi * (base.CORE_DIAMETER / 2.0 + 1.0) ** 2:
            raise RuntimeError(f"{name}: the gaps between arms have webbed over")

    audits = _audit(built)
    rows = measure(built)

    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_')}.stl"
        mesh.export(path)
        objects.append((name, path, extruder))

    plates = _plate_layout(built)
    output = out_dir / OUTPUT_NAME
    previous = (base.PLATES, base._model_settings, base._configure_filament_slots)
    try:
        base.PLATES = plates
        base._model_settings = _model_settings_factory(built)
        base._configure_filament_slots = _single_filament_slots
        base.build_bambu_project(output, objects)
    finally:
        (base.PLATES, base._model_settings, base._configure_filament_slots) = previous

    # --- validate the package -----------------------------------------------
    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("inertia test 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = ET.fromstring(package.read("Metadata/model_settings.config"))
        seen = []
        for index, (_d, _l, _e, infill) in enumerate(VARIANTS, start=1):
            part = settings.find(f".//part[@id='{index}']")
            value = next(
                (
                    m.get("value")
                    for m in part.findall("./metadata")
                    if m.get("key") == "sparse_infill_density"
                ),
                None,
            )
            if value != infill:
                raise RuntimeError(
                    f"body {index} carries sparse_infill_density={value!r}, "
                    f"expected {infill!r}"
                )
            seen.append(value)
        if len(set(seen)) < 2:
            raise RuntimeError("all three bodies carry the same infill density")
        project = json.loads(package.read("Metadata/project_settings.config"))
        if len(project["filament_colour"]) != 1:
            raise RuntimeError("plate is not single-filament; a prime tower will appear")

    report = {
        "project": output.name,
        "question": (
            "arm length, shape or density -- which one actually changes the "
            "spin and the feel?"
        ),
        "correction": (
            "I first answered this off the SOLID model and got the ranking "
            "backwards. The printed Solo is 80% shell: only 3.3 g of 16.7 g is "
            "infill, and none of it lies beyond R23, because five walls meet "
            "in the middle of the arms and they print solid at any density. "
            "Infill can therefore only load the core, at a mean radius of "
            "15.2 mm -- inside the body's own radius of gyration of 18.65 mm. "
            "Hollowing the middle fails in reverse: measured, an R9-17.5 x 9 mm "
            "underside pocket loses 3.5% of the inertia to save 1.1 g, because "
            "the pocket grows its own shell. Shape is not the free lever. "
            "Length is."
        ),
        "model": (
            "voxel shell+infill model calibrated so it reproduces Bambu's own "
            "16.74 g slice of a one-up Solo; spin time taken as proportional to "
            "sqrt(I) at fixed flick energy and fixed bearing drag"
        ),
        "variants": rows,
        "levers_measured": {
            "infill 25% -> 100%": "+10.0 g, +41.7% I, x1.19 spin, +4.2 %I per gram",
            "underside pocket R9-17.5 x 9 mm": "-1.1 g, -3.5% I, x0.98 spin -- NOT on the plate",
            "arms +4 mm, OD 52.6 -> 60.3": "+3.4 g, +51.6% I, x1.23 spin, +15.2 %I per gram",
            "arms +4 mm AND 100% infill": "+15.9 g, +118% I, x1.48 spin",
        },
        "shape_note": (
            "k/R is 0.709 against a uniform disc's 0.707. As a flywheel the "
            "five-arm silhouette is exactly as good as a plain disc of the same "
            "diameter and no better. Keep the shape for the look; it is not "
            "buying spin."
        ),
        "held_constant": [
            "one plate, so identical thermal history and filament state",
            "one filament, no inlay, no prime tower",
            "5 walls, 6 top and 6 bottom layers, 0.16 mm, gyroid",
            "identical bearing pocket, shoulder and retaining-ring counterbore",
        ],
        "identification": (
            f"{MARK_DIAMETER} mm dots recessed {MARK_DEPTH} mm into the "
            f"UNDERSIDE of one arm at R{MARK_RADIUS}; "
            "1 = baseline, 2 = heavy, 3 = long arms"
        ),
        "how_to_judge": [
            "same bearing swapped between all three, or the comparison is "
            "measuring bearings rather than bodies",
            "flick each the same way and time it; 2 and 3 should land close to "
            "each other and clearly ahead of 1",
            "then ignore the stopwatch and just hold them. 2 is +10 g, 3 is "
            "+3.4 g and 15% wider. Which one is more fun is not a number",
            "check 3 still fits the hand and the pocket -- OD 60.3 is a real "
            "size change and it also moves the R22.5 optical ring off the arm "
            "tip, so the broken-ring artwork would need re-cutting to suit",
        ],
        "printability": audits,
        "if_you_only_change_one_thing": (
            "lengthen the arms. It is the only lever that puts mass where r^2 "
            "is large, it costs 3.4 g against 10 g for the same spin gain, and "
            "it is free in filament terms. The cost is size, not weight."
        ),
    }
    (out_dir / REPORT_NAME).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
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
