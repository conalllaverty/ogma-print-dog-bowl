#!/usr/bin/env python3
"""Assert the Fusion config matches the trimesh generator, number for number.

The Fusion side transcribes geometry_config.py by hand, because it cannot
import it — Fusion ships its own Python and the generator pulls in numpy,
trimesh and shapely. A transcription silently rots, so this compares the two
directly and fails loudly on any drift.

Run from the repo root:

    python3 fusion/tests/check_parity.py

Exit codes: 0 clean, 1 drift found. Safe to wire into CI; it imports nothing
from Fusion.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GENERATOR = REPO / "products" / "dog-bowl" / "generator"
FUSION_PKG = REPO / "fusion" / "OgmaBowl" / "ogma_bowl"

TOLERANCE = 1e-9


def _load(module_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    sys.path.insert(0, str(GENERATOR))
    gen = _load(GENERATOR / "geometry_config.py", "generator_geometry_config")
    fus = _load(FUSION_PKG / "config.py", "fusion_config")

    failures: list[str] = []
    checks = 0

    def compare(label, expected, actual):
        nonlocal checks
        checks += 1
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            if abs(float(expected) - float(actual)) > TOLERANCE:
                failures.append(
                    "{}: generator {!r} != fusion {!r}".format(
                        label, expected, actual)
                )
        elif expected != actual:
            failures.append(
                "{}: generator {!r} != fusion {!r}".format(label, expected, actual)
            )

    # --- module-level bowl + envelope constants -------------------------
    for attribute in (
        "BOWL_RIM_OD", "BOWL_BODY_OD", "BOWL_BASE_OD", "BOWL_DEPTH",
        "BOWL_OPENING_D", "BOWL_SEAT_D", "BOWL_RIM_RECESS",
    ):
        compare(attribute, getattr(gen, attribute), getattr(fus, attribute))

    compare("COOPER.stand_od", gen.COOPER.stand_od, fus.STAND_OD)
    compare("COOPER.stand_height", gen.COOPER.stand_height, fus.STAND_HEIGHT)
    compare("COOPER.wall_outer_r", gen.COOPER.wall_outer_r, fus.WALL_OUTER_R)
    compare("COOPER.wall_inner_r", gen.COOPER.wall_inner_r, fus.WALL_INNER_R)

    # --- dataclass styles ------------------------------------------------
    for label, dataclass_obj, table in (
        ("HEX", gen.HEX, fus.HEX),
        ("FLUTED", gen.FLUTED, fus.FLUTED),
        ("WAVE", gen.WAVE, fus.WAVE),
    ):
        for field in dataclass_obj.__dataclass_fields__:
            expected = getattr(dataclass_obj, field)
            if field not in table:
                # rows/sections are mesh tessellation counts with no BRep
                # meaning; letter_azimuth is baked into the wave seam phase.
                if field in ("rows", "sections", "letter_azimuth",
                             "rail_z0", "rail_z1", "rail_proud",
                             "sleeve_wall"):
                    continue
                failures.append("{}.{}: missing from the Fusion table".format(
                    label, field))
                continue
            compare("{}.{}".format(label, field), expected, table[field])

    # --- wave_derived ----------------------------------------------------
    gen_derived = gen.wave_derived()
    fus_derived = fus.wave_derived()
    for key, expected in gen_derived.items():
        compare("wave_derived[{}]".format(key), expected, fus_derived.get(key))

    # --- honeycomb lattice ----------------------------------------------
    # The generator computes these inside hex_bowl_design; recompute the same
    # expression here rather than importing it, since that module needs numpy,
    # trimesh and shapely.
    p = gen.HEX
    reference_r = 0.5 * (p.rb_out + p.rt_out)
    ncols = 2 * max(6, round(math.pi * reference_r / (1.5 * p.target_cell_radius)))
    radius = 2.0 * math.pi * reference_r / (1.5 * ncols)
    expected_hc = {
        "reference_r": reference_r,
        "ncols": ncols,
        "radius": radius,
        "pitch_u": 1.5 * radius,
        "pitch_z": math.sqrt(3.0) * radius,
        "apothem": math.sqrt(3.0) * 0.5 * radius,
    }
    actual_hc = fus.honeycomb_params()
    for key, expected in expected_hc.items():
        compare("honeycomb[{}]".format(key), expected, actual_hc.get(key))

    # --- cooper letter + joint constants --------------------------------
    cooper_src = (GENERATOR / "cooper_bowl_design.py").read_text()
    scraped = {}
    for line in cooper_src.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        if not key.isupper() or not key.replace("_", "").isalnum():
            continue
        value = rest.split("#")[0].strip()
        try:
            scraped[key] = float(value)
        except ValueError:
            continue

    cooper_map = {
        "LETTER_HEIGHT": fus.LETTER_HEIGHT,
        "LETTER_THICKNESS": fus.LETTER_THICKNESS,
        "LETTER_POCKET_DEPTH": fus.LETTER_POCKET_DEPTH,
        "LETTER_POCKET_CLEARANCE": fus.LETTER_POCKET_CLEARANCE,
        "LETTER_POCKET_FLOOR_GAP": fus.LETTER_POCKET_FLOOR_GAP,
        "LETTER_GAP": fus.LETTER_GAP,
        "LETTER_END_MARGIN": fus.LETTER_END_MARGIN,
        "MAX_RAIL_OUTER_DEG": fus.MAX_RAIL_OUTER_DEG,
        "MAX_NAME_LEN": fus.MAX_NAME_LEN,
        "STAND_OD": fus.STAND_OD,
        "STAND_HEIGHT": fus.STAND_HEIGHT,
        "WALL_OUTER_R": fus.WALL_OUTER_R,
        "WALL_INNER_R": fus.WALL_INNER_R,
        "BASE_HEIGHT": fus.COOPER["base_height"],
        "LATTICE_BOTTOM": fus.COOPER["lattice_bottom"],
        "LATTICE_TOP": fus.COOPER["lattice_top"],
        "TOP_BOTTOM": fus.COOPER["top_bottom"],
        "PAW_RECESS_DEPTH": fus.COOPER["paw_recess_depth"],
        "NAME_RAIL_OUTER_R": fus.COOPER["name_rail_outer_r"],
        "NAME_RAIL_FLAT_Z0": fus.COOPER["name_rail_z0"],
        "NAME_RAIL_FLAT_Z1": fus.COOPER["name_rail_z1"],
        "LETTER_CENTER_Z": fus.COOPER["letter_center_z"],
        "TOP_JOINT_PIN_COUNT": fus.COOPER["top_joint_pin_count"],
        "TOP_JOINT_PIN_RADIUS": fus.COOPER["top_joint_pin_radius"],
        "TOP_JOINT_HOLE_RADIUS": fus.COOPER["top_joint_hole_radius"],
        "TOP_JOINT_RADIUS": fus.COOPER["top_joint_radius"],
        "TOP_JOINT_PIN_HEIGHT": fus.COOPER["top_joint_pin_height"],
    }
    for key, actual in cooper_map.items():
        if key not in scraped:
            failures.append("cooper_bowl_design.{}: not found to compare".format(key))
            continue
        compare("cooper.{}".format(key), scraped[key], actual)

    # --- flute cutter sanity --------------------------------------------
    fl = fus.flute_cutter()
    checks += 1
    depth_check = fl["centre_r"] - fl["cutter_r"]
    expected_floor = fus.FLUTED["rb_out"] - fus.FLUTED["flute_depth"]
    if abs(depth_check - expected_floor) > 1e-9:
        failures.append(
            "flute cutter bottoms at R{:.4f}, expected R{:.4f}".format(
                depth_check, expected_floor)
        )
    checks += 1
    half_chord = math.sqrt(
        max(0.0, fl["cutter_r"] ** 2
            - (fl["centre_r"] - fus.FLUTED["rb_out"]) ** 2)
    )
    if abs(2.0 * half_chord - fl["pitch"]) > 1e-6:
        failures.append(
            "flute cutter opens {:.4f} mm wide at the wall, expected the "
            "{:.4f} mm pitch".format(2.0 * half_chord, fl["pitch"])
        )

    print("checked {} values".format(checks))
    if failures:
        print("\nDRIFT ({}):".format(len(failures)))
        for failure in failures:
            print("  " + failure)
        return 1
    print("Fusion config matches the generator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
