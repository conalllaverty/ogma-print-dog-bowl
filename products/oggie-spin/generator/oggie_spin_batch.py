#!/usr/bin/env python3
"""Batch-manufacturing project: N complete Oggie Spins per plate set.

Why this exists
---------------
The shipped nine-plate project makes exactly ONE spinner, with one or two parts
alone on a 256 x 256 bed. That is right for validating a design and absurd for
production: you pay a full bed heat, purge, start/end sequence and an operator
trip to the printer for a single 12 g core.

This emits the same geometry packed for production. Nothing about any part
changes -- the meshes come straight from the shipped generator, so a batch part
is bit-identical to a validated one.

Where the win actually is
-------------------------
Packing, not print settings. Ten cores on one plate is a 10x reduction in
per-run overhead. Coarsening layers looked attractive but the arithmetic kills
it: the parts that could safely take 0.20 mm are 18 % of the batch volume, so
the whole saving is ~3-4 % of run time, and it buys that by introducing an
untested variable into the one part with spring fingers. See LAYER_HEIGHTS.

Filament grouping is the second win. Three of the eight plates are SINGLE
filament, which means zero purge on them:

    hubs   -- Tough+ only
    pads   -- one colour only
    (rings ride along on the core plate: same filament as the core body)

    .venv/bin/python products/oggie-spin/generator/oggie_spin_batch.py \\
        --out products/oggie-spin/design/active --units 10
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

import trimesh

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_broken_rings as br  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
from ogma import printability  # noqa: E402

BED = 256.0
# Bambu's nominal 256 x 256 is not all usable: there are exclusion zones at the
# edges and the purge chute at the back. 18 mm keeps every part inside 110 mm of
# the plate centre, which leaves real clearance rather than nominal clearance.
MARGIN = 18.0
GAP = 6.0
USABLE = BED - 2.0 * MARGIN

OUTPUT_TEMPLATE = "Oggie_Spin_Batch_x{units}_P2S.3mf"
REPORT_NAME = "batch_manufacturing_report.json"

# Per-plate layer height. Everything is 0.16 except the thumb pads.
#
# The tempting move is to coarsen every "hidden" part. Two of them should not
# be coarsened and the third is not worth it:
#
#   collet hub  -- four spring fingers with 0.55 mm slots. Same class of part as
#                  the arm clip beam, and layer definition is what makes a
#                  printed spring behave. Held at 0.16.
#   retaining   -- press fit, 0.07 mm interference. Its critical dimension is an
#     ring         XY diameter so layer height would not hurt it, but it is
#                  1.1 cm3 across the whole batch: the saving is seconds.
#   core / arms -- carry the optical inlay (0.32 mm = exactly two 0.16 layers)
#                  and the clip beam. Untouchable.
#
# That leaves the pads: 28 cm3, no springs, no inlay, and their functional
# surface is a bayonet socket that is XY-defined.
LAYER_HEIGHTS = {
    "pads": "0.20",
}
DEFAULT_LAYER_HEIGHT = "0.16"


def _mesh_footprint(mesh: trimesh.Trimesh) -> tuple[float, float, float, float]:
    """(width, depth, x-centre, y-centre) of the mesh in its own coordinates."""
    lo, hi = mesh.bounds[0], mesh.bounds[1]
    return (
        float(hi[0] - lo[0]),
        float(hi[1] - lo[1]),
        float((lo[0] + hi[0]) / 2.0),
        float((lo[1] + hi[1]) / 2.0),
    )


def _grid_offsets(
    count: int,
    width: float,
    depth: float,
    cx: float,
    cy: float,
    gap: float = GAP,
) -> list[tuple[float, float]]:
    """Component offsets that lay `count` parts out on a centred grid.

    Returns offsets, not positions: each one already cancels the mesh's own
    off-origin centre, so the part lands where the grid says it should.
    """
    cols = max(1, int((USABLE + gap) // (width + gap)))
    cols = min(cols, count)
    rows = math.ceil(count / cols)
    if rows * (depth + gap) - gap > USABLE:
        raise RuntimeError(
            f"{count} parts of {width:.1f} x {depth:.1f} mm do not fit the bed"
        )
    pitch_x, pitch_y = width + gap, depth + gap
    span_x = (cols - 1) * pitch_x
    span_y = (rows - 1) * pitch_y
    offsets = []
    for index in range(count):
        row, col = divmod(index, cols)
        # last row is centred rather than left-aligned, so the plate looks
        # deliberate and the centre of mass stays near the middle of the bed
        in_row = min(cols, count - row * cols)
        row_span = (in_row - 1) * pitch_x
        tx = -row_span / 2.0 + col * pitch_x
        ty = span_y / 2.0 - row * pitch_y
        offsets.append((tx - cx, ty - cy))
    return offsets


def _plate_position(number: int, total: int) -> tuple[float, float, float]:
    """Bambu lays plates out in ceil(sqrt(n)) columns, stride 312 mm."""
    cols = math.ceil(math.sqrt(total))
    index = number - 1
    return (128.0 + (index % cols) * 312.0, 128.0 - (index // cols) * 312.0, 0.0)


def _source_meshes() -> dict:
    """Pull the shipped geometry. Nothing here is rebuilt or re-tuned."""
    built = br._build_variant_meshes()
    by_name = {name: (mesh, extruder) for name, mesh, extruder in built}

    def pick(fragment: str):
        for name, value in by_name.items():
            if fragment.lower() in name.lower():
                return name, value
        raise RuntimeError(f"no shipped mesh matching {fragment!r}")

    parts = {
        "core": pick("Oggie Spin core"),
        "core_inlay": pick("core broken-ring inlay"),
        "ring": pick("retaining ring"),
        "collet": pick("split-collet"),
        "receiver": pick("receiver hub"),
        "pad": pick("thumb pad 1"),
    }
    arms = []
    for index in range(1, 6):
        arms.append(
            (
                pick(f"colour block {index}"),
                pick(f"arm-ring inlay {index}"),
            )
        )
    return parts, arms


def build_plan(units: int) -> dict:
    """Object list and plate layout for `units` complete spinners."""
    parts, arms = _source_meshes()

    objects: list[tuple[str, trimesh.Trimesh, int]] = []
    plates: list[dict] = []

    def add(label: str, entry, count: int) -> list[int]:
        """Append `count` duplicate objects, return their 1-based ids."""
        name, (mesh, extruder) = entry
        ids = []
        for n in range(count):
            objects.append((f"{label} {n + 1}", mesh, extruder))
            ids.append(len(objects))
        return ids

    def layout(ids: list[int], entry) -> list[tuple[int, float, float, float]]:
        _name, (mesh, _ext) = entry
        w, d, cx, cy = _mesh_footprint(mesh)
        offs = _grid_offsets(len(ids), w, d, cx, cy)
        return [(i, x, y, 0.0) for i, (x, y) in zip(ids, offs)]

    def paired(ids_a, entry_a, ids_b, entry_b):
        """Base + inlay share one grid slot, so they stay registered."""
        _n, (mesh_a, _e) = entry_a
        w, d, cx, cy = _mesh_footprint(mesh_a)
        offs = _grid_offsets(len(ids_a), w, d, cx, cy)
        comps = []
        for ia, ib, (x, y) in zip(ids_a, ids_b, offs):
            comps.append((ia, x, y, 0.0))
            comps.append((ib, x, y, 0.0))
        return comps

    # --- plate 1: cores + retaining rings -----------------------------------
    # The ring is the same filament as the core body, so it rides along free:
    # no extra plate, no extra purge, no extra bed heat.
    core_ids = add("Core", parts["core"], units)
    core_inlay_ids = add("Core inlay", parts["core_inlay"], units)
    comps = paired(core_ids, parts["core"], core_inlay_ids, parts["core_inlay"])
    ring_ids = add("Retaining ring", parts["ring"], units)
    # tuck the rings into the strip below the core grid
    _n, (ring_mesh, _e) = parts["ring"]
    rw, rd, rcx, rcy = _mesh_footprint(ring_mesh)
    _n2, (core_mesh, _e2) = parts["core"]
    _cw, cd, _ccx, _ccy = _mesh_footprint(core_mesh)
    core_rows = math.ceil(units / max(1, int((USABLE + GAP) // (_cw + GAP))))
    ring_y = -(core_rows * (cd + GAP)) / 2.0 - (rd + GAP) / 2.0
    ring_offs = _grid_offsets(units, rw, rd, rcx, rcy)
    comps += [(i, x, ring_y - rcy, 0.0) for i, (x, _y) in zip(ring_ids, ring_offs)]
    plates.append({"title": f"Cores x{units} + retaining rings x{units}",
                   "components": comps, "key": "core"})

    # --- plate 2: both cartridge hubs, Tough+ only, zero purge --------------
    collet_ids = add("Collet hub", parts["collet"], units)
    recv_ids = add("Receiver hub", parts["receiver"], units)
    _n, (collet_mesh, _e) = parts["collet"]
    hw, hd, hcx, hcy = _mesh_footprint(collet_mesh)
    hub_offs = _grid_offsets(units * 2, hw, hd, hcx, hcy)
    comps = [(i, x, y, 0.0) for i, (x, y) in zip(collet_ids + recv_ids, hub_offs)]
    plates.append({"title": f"Tough+ cartridge hubs x{units * 2}",
                   "components": comps, "key": "hubs"})

    # --- plate 3: thumb pads, one colour, zero purge ------------------------
    pad_ids = add("Thumb pad", parts["pad"], units * 2)
    plates.append({"title": f"Thumb pads x{units * 2}",
                   "components": layout(pad_ids, parts["pad"]), "key": "pads"})

    # --- plates 4-8: one colour of arm each ---------------------------------
    for index, (arm_entry, inlay_entry) in enumerate(arms, start=1):
        a_ids = add(f"Arm c{index}", arm_entry, units)
        i_ids = add(f"Arm c{index} inlay", inlay_entry, units)
        plates.append({
            "title": f"Arms x{units} - colour {index}",
            "components": paired(a_ids, arm_entry, i_ids, inlay_entry),
            "key": "arms",
        })

    return {"units": units, "objects": objects, "plates": plates}


def _write_shared_meshes(out_dir: Path, plan: dict) -> list[tuple[str, Path, int]]:
    """One STL per UNIQUE mesh; duplicates reference the same file.

    170 objects, 17 files. Writing 170 copies of geometry that is identical by
    construction would bloat the project and invite exactly the drift this whole
    design has been fighting.
    """
    mesh_dir = out_dir / "batch-meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    written: dict[int, Path] = {}
    objects: list[tuple[str, Path, int]] = []
    for name, mesh, extruder in plan["objects"]:
        key = id(mesh)
        if key not in written:
            stem = name.rsplit(" ", 1)[0].lower().replace(" ", "_").replace("+", "plus")
            path = mesh_dir / f"{len(written) + 1:02d}_{stem}.stl"
            mesh.export(path)
            written[key] = path
        objects.append((name, written[key], extruder))
    return objects


def _batch_model_settings_factory(plan: dict):
    """Per-plate layer height, plus the arm overrides the shipped project uses."""
    arm_base_ids = {
        index
        for index, (name, _m, _e) in enumerate(plan["objects"], start=1)
        if name.startswith("Arm c") and "inlay" not in name
    }
    arm_inlay_ids = {
        index
        for index, (name, _m, _e) in enumerate(plan["objects"], start=1)
        if name.startswith("Arm c") and "inlay" in name
    }

    def _settings(objects, meshes) -> bytes:
        root = ET.fromstring(br.ORIGINAL_MODEL_SETTINGS(objects, meshes))
        for number, plate in enumerate(plan["plates"], start=1):
            node = root.find(f".//object[@id='{99 + number}']")
            if node is None:
                raise RuntimeError(f"missing plate object {99 + number}")
            height = LAYER_HEIGHTS.get(plate["key"], DEFAULT_LAYER_HEIGHT)
            br._set_metadata(node, "layer_height", height)
        # arms must keep the exact settings the mass matching was validated on
        for part_id in arm_base_ids:
            part = root.find(f".//part[@id='{part_id}']")
            if part is None:
                raise RuntimeError(f"missing arm part {part_id}")
            br._set_metadata(part, "wall_loops", "2")
            br._set_metadata(part, "sparse_infill_density", "100%")
            br._set_metadata(part, "sparse_infill_pattern", "grid")
        for part_id in arm_inlay_ids:
            part = root.find(f".//part[@id='{part_id}']")
            if part is not None:
                br._set_metadata(part, "wall_loops", "2")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    return _settings


def _rewrite_batch_settings(path: Path) -> None:
    """Production travel settings. Same shape as the shipped project's."""
    temp = path.with_suffix(".tmp.3mf")
    with (
        zipfile.ZipFile(path, "r") as src,
        zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as dst,
    ):
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "Metadata/project_settings.config":
                s = json.loads(data)
                # every plate here is a dense multi-object plate
                s["z_hop"] = ["0.6", "0.6"]
                s["z_hop_types"] = ["Slope Lift", "Slope Lift"]
                s["reduce_crossing_wall"] = "1"
                s["max_travel_detour_distance"] = "0"
                s["retract_before_wipe"] = ["70%", "70%"]
                s["wipe"] = ["1", "1"]
                s["wipe_distance"] = ["2", "2"]
                s["retract_when_changing_layer"] = ["1", "1"]
                s["retraction_minimum_travel"] = ["1", "1"]
                s["print_sequence"] = "by layer"
                s["enable_prime_tower"] = "1"
                s["flush_volumes_matrix"] = br._flush_matrix()
                s["flush_volumes_vector"] = [
                    str(br.FLUSH_MAX) for _ in br.VARIANT_FILAMENTS
                ]
                s["flush_into_infill"] = "1"
                data = json.dumps(s, indent=2, ensure_ascii=False).encode()
            dst.writestr(item, data)
    temp.replace(path)


def _validate(output: Path, plan: dict, objects) -> dict:
    units = plan["units"]
    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("batch 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = ET.fromstring(package.read("Metadata/model_settings.config"))
        plates = settings.findall("./plate")
        if len(plates) != len(plan["plates"]):
            raise RuntimeError("batch 3MF lost a plate")
        heights = {}
        for number, plate in enumerate(plan["plates"], start=1):
            node = settings.find(f".//object[@id='{99 + number}']")
            value = next(
                m.get("value") for m in node.findall("./metadata")
                if m.get("key") == "layer_height"
            )
            expected = LAYER_HEIGHTS.get(plate["key"], DEFAULT_LAYER_HEIGHT)
            if value != expected:
                raise RuntimeError(
                    f"plate {number} layer height is {value}, expected {expected}"
                )
            heights[plate["title"]] = value
        project = json.loads(package.read("Metadata/project_settings.config"))
        matrix = project["flush_volumes_matrix"]
        n = len(br.VARIANT_FILAMENTS)
        if any(int(matrix[i * n + j]) == 0 for i in range(n) for j in range(n) if i != j):
            raise RuntimeError("batch 3MF has a zero purge pair")

    # --- every object must land on its own bed -----------------------------
    total = len(plan["plates"])
    half = BED / 2.0
    worst = 0.0
    for number, plate in enumerate(plan["plates"], start=1):
        for object_id, dx, dy, _dz in plate["components"]:
            mesh = plan["objects"][object_id - 1][1]
            lo, hi = mesh.bounds[0], mesh.bounds[1]
            for value in (lo[0] + dx, hi[0] + dx, lo[1] + dy, hi[1] + dy):
                worst = max(worst, abs(value))
                if abs(value) > half:
                    raise RuntimeError(
                        f"plate {number} object {object_id} falls off its bed"
                    )

    # --- no two parts on a plate may overlap -------------------------------
    from shapely.geometry import box as _box
    for number, plate in enumerate(plan["plates"], start=1):
        rects = []
        for object_id, dx, dy, _dz in plate["components"]:
            name = plan["objects"][object_id - 1][0]
            if "inlay" in name:
                continue  # inlays sit inside their base by design
            mesh = plan["objects"][object_id - 1][1]
            lo, hi = mesh.bounds[0], mesh.bounds[1]
            rects.append(_box(lo[0] + dx, lo[1] + dy, hi[0] + dx, hi[1] + dy))
        for a in range(len(rects)):
            for b in range(a + 1, len(rects)):
                hit = rects[a].intersection(rects[b])
                if not hit.is_empty and hit.area > 1e-9:
                    raise RuntimeError(
                        f"plate {number}: parts {a} and {b} overlap by "
                        f"{hit.area:.3f} mm2"
                    )

    # --- matched quantities ------------------------------------------------
    counts: dict[str, int] = {}
    for name, _mesh, _ext in plan["objects"]:
        key = name.rsplit(" ", 1)[0]
        counts[key] = counts.get(key, 0) + 1
    expected = {
        "Core": units, "Core inlay": units, "Retaining ring": units,
        "Collet hub": units, "Receiver hub": units, "Thumb pad": units * 2,
    }
    for index in range(1, 6):
        expected[f"Arm c{index}"] = units
        expected[f"Arm c{index} inlay"] = units
    for key, want in expected.items():
        if counts.get(key) != want:
            raise RuntimeError(
                f"batch is not a matched set: {want} x {key} expected, "
                f"{counts.get(key)} present"
            )

    volume = sum(float(m.volume) for _n, m, _e in plan["objects"]) / 1000.0
    unique = len({id(m) for _n, m, _e in plan["objects"]})
    return {
        "project": output.name,
        "units_per_batch": units,
        "plates": len(plan["plates"]),
        "objects": len(plan["objects"]),
        "unique_meshes": unique,
        "single_filament_plates": [
            p["title"] for p in plan["plates"] if p["key"] in ("hubs", "pads")
        ],
        "layer_height_by_plate": heights,
        "worst_object_reach_from_plate_centre_mm": round(worst, 2),
        "bed_half_size_mm": half,
        "batch_volume_cm3": round(volume, 2),
        "batch_mass_g_at_1_24": round(volume * 1.24, 1),
        "mass_per_spinner_g": round(volume * 1.24 / units, 2),
        "parts_per_batch": counts,
        "geometry_source": (
            "identical meshes to the shipped single-unit project; nothing "
            "re-tuned for batch"
        ),
    }


def generate(out_dir: Path, units: int = 10) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = build_plan(units)
    objects = _write_shared_meshes(out_dir, plan)

    total = len(plan["plates"])
    plates = [
        base.Plate(p["title"], tuple(p["components"]), _plate_position(n, total))
        for n, p in enumerate(plan["plates"], start=1)
    ]

    output = out_dir / OUTPUT_TEMPLATE.format(units=units)
    previous = (
        base.PLATES, base.FILAMENTS, base._preview_png,
        base._model_settings, base._configure_filament_slots,
    )
    try:
        base.PLATES = plates
        base.FILAMENTS = br.VARIANT_FILAMENTS
        base._preview_png = br._preview_png
        base._model_settings = _batch_model_settings_factory(plan)
        base._configure_filament_slots = br._configure_variant_filaments
        base.build_bambu_project(output, objects)
    finally:
        (
            base.PLATES, base.FILAMENTS, base._preview_png,
            base._model_settings, base._configure_filament_slots,
        ) = previous
    _rewrite_batch_settings(output)

    report = _validate(output, plan, objects)
    (out_dir / REPORT_NAME).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--units", type=int, default=10,
                        help="complete spinners per batch run")
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        path = generate(args.out, args.units)
    print(path)


if __name__ == "__main__":
    main()
