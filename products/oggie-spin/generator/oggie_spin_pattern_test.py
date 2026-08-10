#!/usr/bin/env python3
"""A/B/C test plate: does the top-surface pattern change the optical illusion?

The question
------------
Conall set the Solo's top surface to Octagram Spiral and asked whether it would
help the broken-ring illusion. My arithmetic says no: the illusion lives on
ALBEDO, and Ivory White on Marine Blue is a 60% Michelson contrast, while
same-filament extrusion lines on MATTE PLA modulate luminance by roughly 3%.
Twenty times weaker, on a surface being smeared at speed.

But that is arithmetic, and the eye is the instrument that matters. This plate
settles it in one print.

Three bodies, identical in every way a caliper could measure, differing only in
top surface pattern:

  1 dot   octagramspiral  -- Conall's pick. 8-fold, decorative.
  2 dots  monotonicline   -- the shipped default. Best surface uniformity:
                             monotonic orders its lines so each overlaps the
                             last consistently, which is what removes the
                             glossy/matte banding other patterns leave.
  3 dots  concentric      -- my hypothesis, and the interesting one. A spinner
                             rotates about its own axis, so concentric lines are
                             ROTATIONALLY INVARIANT: they look identical at
                             every angle and therefore contribute nothing at all
                             to the spinning image. Every other pattern has a
                             direction, so its texture rotates with the part and
                             can only add noise. If any pattern helps, it is the
                             one that disappears.

Concentric has a real risk to balance that: 96% of the top face lies within 2 mm
of a dash pocket, and concentric fragments into small rings around obstacles.
It may print worse than it theorises. That is exactly what a test is for.

Identification is three shallow dots on the UNDERSIDE, so nothing is added to
the face under test. Bodies are otherwise bit-identical.

    .venv/bin/python products/oggie-spin/generator/oggie_spin_pattern_test.py \\
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
import oggie_spin_onepiece as solo  # noqa: E402

OUTPUT_NAME = "Oggie_Spin_Pattern_Test_P2S.3mf"
MESH_DIR_NAME = "pattern-test-meshes"
REPORT_NAME = "pattern_test_report.json"

# Bambu's internal enum values, taken from the shipped project's own
# project_settings.config rather than guessed.
VARIANTS = [
    (1, "octagramspiral", "Octagram Spiral -- Conall's pick, 8-fold decorative"),
    (2, "monotonicline", "Monotonic Line -- the shipped default, most uniform"),
    (3, "concentric", "Concentric -- rotationally invariant, vanishes when spun"),
]

MARK_RADIUS = 9.0       # between the bearing shoulder (R5.3) and the inner ring
MARK_DIAMETER = 3.0
MARK_DEPTH = 0.40       # underside only; never touches the face under test


def _identified_body(dots: int) -> trimesh.Trimesh:
    """The Solo body with `dots` shallow marks recessed into its underside."""
    # Pinned to the ORIGINAL Ø52.6 silhouette. The Solo shipped 4 mm longer
    # arms after the inertia plate, but this experiment is about which top
    # surface pattern reads best and it is already printed. Re-running it has
    # to produce the same parts, or the plate on the desk stops being the
    # thing the comparison is about.
    body = solo.build_body(extension=0.0)
    cutters = []
    for index in range(dots):
        # spread the dots over a small arc so they read as a count at a glance
        angle = math.radians(-90.0 + (index - (dots - 1) / 2.0) * 14.0)
        cutter = base._cylinder(
            MARK_DIAMETER / 2.0, MARK_DEPTH + 0.2, -0.1, sections=48
        )
        cutter.apply_translation(
            [MARK_RADIUS * math.cos(angle), MARK_RADIUS * math.sin(angle), 0.0]
        )
        cutters.append(cutter)
    marked = base._difference(body, cutters, f"Solo body, {dots} dot")
    return marked


def build_meshes() -> list[tuple[str, trimesh.Trimesh, int]]:
    dashes = trimesh.util.concatenate(
        [br._dash_volume(spec) for spec in br.RING_SPECS]
    )
    built: list[tuple[str, trimesh.Trimesh, int]] = []
    for dots, pattern, _blurb in VARIANTS:
        body = _identified_body(dots)
        part, inlay = br._split_flush_inlay(body, dashes, f"pattern test {dots}")
        inlay, _proud = br._raise_inlay(inlay, f"pattern test {dots} inlay")
        built.append((f"Body {dots}dot {pattern}", part, 1))
        built.append((f"Inlay {dots}dot", inlay, br.OPTICAL_EXTRUDER))
    return built


def _model_settings_factory(built):
    """Per-part top_surface_pattern.

    Process overrides on <part> are the same mechanism the shipped project uses
    to give the arms 2 walls and 100% grid infill, and that demonstrably prints.
    top_surface_pattern is the same class of key.

    It is still worth ten seconds of verification in the slicer -- see the
    report's `how_to_verify`. A silent no-op would make all three bodies
    identical and quietly waste the print.
    """
    pattern_by_id = {}
    for index, (name, _mesh, _ext) in enumerate(built, start=1):
        if name.startswith("Body "):
            pattern_by_id[index] = name.rsplit(" ", 1)[1]

    def _settings(objects, meshes) -> bytes:
        root = ET.fromstring(br.ORIGINAL_MODEL_SETTINGS(objects, meshes))
        for part_id, pattern in pattern_by_id.items():
            part = root.find(f".//part[@id='{part_id}']")
            if part is None:
                raise RuntimeError(f"missing body part {part_id}")
            br._set_metadata(part, "top_surface_pattern", pattern)
            # hold everything else identical so the pattern is the only variable
            br._set_metadata(part, "top_shell_layers", "7")
            br._set_metadata(part, "bottom_shell_layers", "6")
            br._set_metadata(part, "top_surface_density", "100%")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    return _settings


def _rewrite_wall_generator(path: Path) -> None:
    """Switch this plate to the Arachne wall generator.

    The leading suspect for the white stringing, and it is arithmetic rather
    than opinion. The dash pockets are RING_WIDTH = 1.1 mm wide. The project
    runs `wall_generator = classic` at a 0.42 mm outer wall, so a loop around a
    1.1 mm strip lays 0.42 mm in from each side and leaves 0.26 mm uncovered
    down the middle -- too narrow for another loop, so classic fills it with a
    gap-fill sliver. That is a separate, very short, very fast (250 mm/s)
    extrusion with its own start and stop, in EVERY one of the sixty dashes,
    on every white layer. Sixty extra pressure spikes per layer is a stringing
    machine.

    Arachne instead fits the strip with two variable-width beads of ~0.55 mm.
    No sliver, no second start-stop, and the dash comes out solid. It does not
    move the outer wall, so nothing dimensional changes on this plate.

    Scoped to THIS plate deliberately. Arachne would also change the modular
    spinner's 0.80 mm clip beam from one compressed loop to two 0.40 mm beads,
    which makes the beam slightly stiffer -- and the snap force, the fatigue
    margin and the 0.50 mm engagement ceiling were all computed against the
    beam as it prints today. That wants re-deriving before the main project
    moves, not a quiet flag flip.

    Thirty-second check before printing: open the plate, Preview, drag to the
    top layers, and look at a dash. Classic shows a thin line down the centre
    of each one in the gap-fill colour. If that line is not there, this theory
    is wrong and the temperature and retraction changes are doing the work.
    """
    temp_path = path.with_suffix(".tmp.3mf")
    with (
        zipfile.ZipFile(path, "r") as source,
        zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "Metadata/project_settings.config":
                settings = json.loads(data)
                settings["wall_generator"] = "arachne"
                # let a bead get thin enough to be worth printing rather than
                # falling back to gap fill again
                settings["min_bead_width"] = "70%"
                data = json.dumps(settings, indent=2, ensure_ascii=False).encode()
            target.writestr(item, data)
    temp_path.replace(path)


def generate(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)

    built = build_meshes()
    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_')}.stl"
        mesh.export(path)
        objects.append((name, path, extruder))

    # three bodies in a row, centred; each inlay shares its body's slot
    pitch = 58.6                      # 52.6 mm body + 6 mm gap
    comps = []
    for slot in range(3):
        x = (slot - 1) * pitch
        comps.append((1 + slot * 2, x, 0.0, 0.0))
        comps.append((2 + slot * 2, x, 0.0, 0.0))
    plates = [base.Plate("Top-surface pattern A/B/C", tuple(comps), (128.0, 128.0, 0.0))]

    output = out_dir / OUTPUT_NAME
    previous = (base.PLATES, base.FILAMENTS, base._preview_png,
                base._model_settings, base._configure_filament_slots)
    try:
        base.PLATES = plates
        base.FILAMENTS = br.VARIANT_FILAMENTS
        base._preview_png = br._preview_png
        base._model_settings = _model_settings_factory(built)
        base._configure_filament_slots = br._configure_variant_filaments
        base.build_bambu_project(output, objects)
    finally:
        (base.PLATES, base.FILAMENTS, base._preview_png,
         base._model_settings, base._configure_filament_slots) = previous
    br._rewrite_variant_project_settings(output)
    _rewrite_wall_generator(output)

    # --- validate -----------------------------------------------------------
    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("pattern test 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = ET.fromstring(package.read("Metadata/model_settings.config"))
        seen = {}
        for dots, pattern, _b in VARIANTS:
            part_id = 1 + (dots - 1) * 2
            part = settings.find(f".//part[@id='{part_id}']")
            value = next(
                (m.get("value") for m in part.findall("./metadata")
                 if m.get("key") == "top_surface_pattern"), None
            )
            if value != pattern:
                raise RuntimeError(
                    f"body {dots} carries top_surface_pattern={value!r}, expected {pattern!r}"
                )
            seen[dots] = value
        if len(set(seen.values())) != 3:
            raise RuntimeError("the three bodies do not carry three distinct patterns")

    # bodies must differ ONLY by their identification dots
    volumes = [m.volume for n, m, _e in built if n.startswith("Body ")]
    dot_volume = math.pi * (MARK_DIAMETER / 2.0) ** 2 * MARK_DEPTH
    for dots, (_d, _p, _b) in zip((1, 2, 3), VARIANTS):
        pass
    expected_spread = 2 * dot_volume       # 1 dot vs 3 dots
    spread = max(volumes) - min(volumes)
    if abs(spread - expected_spread) > 0.5:
        raise RuntimeError(
            f"bodies differ by {spread:.2f} mm3; only the {expected_spread:.2f} mm3 "
            "of identification dots should separate them"
        )

    for name, mesh, _e in built:
        if name.startswith("Body ") and len(mesh.split(only_watertight=False)) != 1:
            raise RuntimeError(f"{name} is not a single shell")

    report = {
        "project": output.name,
        "question": (
            "does the top-surface pattern contribute anything to the broken-ring "
            "illusion, or only to surface finish?"
        ),
        "prediction": (
            "no. Ivory on Marine Blue is 60% Michelson contrast; same-filament "
            "extrusion lines on MATTE PLA modulate luminance ~3%, about 20x "
            "weaker, and matte is formulated to kill exactly the directional "
            "sheen a pattern would need. Concentric is the one to watch: it is "
            "rotationally invariant, so it is the only pattern that cannot add "
            "noise to a spinning image."
        ),
        "variants": [
            {"dots": d, "top_surface_pattern": p, "why": b} for d, p, b in VARIANTS
        ],
        "held_constant": [
            "geometry (bodies differ only by underside identification dots)",
            "filaments: Marine Blue body, Ivory White inlay",
            "7 top shell layers, 6 bottom, 100% top surface density",
            "one plate, so identical thermal history and filament state",
        ],
        "identification": (
            f"{MARK_DIAMETER} mm dots recessed {MARK_DEPTH} mm into the UNDERSIDE "
            f"at R{MARK_RADIUS}; 1 = octagram, 2 = monotonic, 3 = concentric. "
            "Nothing is added to the face under test."
        ),
        "how_to_verify_before_printing": [
            "open the plate, switch the left panel to the Objects tab",
            "click each body in turn and read its Top surface pattern",
            "you should see octagramspiral, monotonicline, concentric",
            "if all three read the same, the per-part override did not take -- "
            "set it by hand on each object, or tell me and I will split them "
            "onto three plates where the override is proven",
        ],
        "how_to_judge": [
            "spin each on the same cartridge, under the same light, and look at "
            "the rings -- not the surface",
            "then look at the still top surface at a grazing angle for banding, "
            "blobs and start/stop marks around the 50 dash pockets",
            "concentric may lose on finish even if it wins on spin: 96% of the "
            "top face is within 2 mm of a pocket edge, and concentric fragments "
            "around obstacles",
        ],
        "body_volumes_mm3": [round(v, 2) for v in volumes],
        "identification_dot_volume_mm3": round(dot_volume, 3),
        "contrast_note": (
            "Marine Blue is the best pair you own at 60%. Scarlet -- already in "
            "the Filament Drop brand palette -- would give 77%, and black 99%. "
            "Contrast is the only channel that survives being spun, so that is "
            "where a real gain is, not in the extrusion pattern."
        ),
    }
    (out_dir / REPORT_NAME).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
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
