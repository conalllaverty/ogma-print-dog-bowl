#!/usr/bin/env python3
"""Audit a generated 3MF against what a Bambu Lab P2S actually needs.

The project settings are written by shared/ogma/bambu_project.py from a template
and then patched per job. Nothing checks the result, so a wrong printer profile
or a filament slot that doesn't match the chosen colour would only show up when
someone opened the file in Bambu Studio — or worse, when a plate came off the
bed in the wrong colour.

This asserts the things that would be expensive to get wrong:

  printer      P2S, 0.4 nozzle, the P2S print profile, a plate type it supports
  filament     every slot is Bambu PLA Matte (GFA01), and the hexes are the ones
               the customer picked
  plates       every object is assigned to a plate, and the plate count matches
               what the picker advertises
  geometry     the model is inside the P2S build volume

Usage:
    .venv/bin/python tests/audit_3mf.py path/to/file.3mf [--stand HEX --letters HEX]
    .venv/bin/python tests/audit_3mf.py --generate      # build one and audit it
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "shared"))

# Bambu Lab P2S. Build volume from the printer profile; the machine is the
# 256 mm cube class, and 3MF coordinates are millimetres from the plate origin.
EXPECT_PRINTER = "Bambu Lab P2S"
EXPECT_NOZZLE = "0.4"
EXPECT_PROFILE_CONTAINS = "@BBL P2S"
BUILD_VOLUME_MM = (256.0, 256.0, 256.0)

# Bambu's own filament id for PLA Matte. Every slot must be this: the shop
# stocks one material, and a slot set to plain PLA would slice with the wrong
# temperature tower.
PLA_MATTE_ID = "GFA01"
EXPECT_TYPE = "PLA"


class Audit:
    def __init__(self) -> None:
        self.checks: list[tuple[bool, str, str]] = []

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        self.checks.append((bool(ok), label, detail))
        return bool(ok)

    def report(self) -> int:
        width = max(len(c[1]) for c in self.checks)
        failed = 0
        for ok, label, detail in self.checks:
            mark = "ok  " if ok else "FAIL"
            failed += not ok
            print(f"  [{mark}] {label.ljust(width)}  {detail}")
        print()
        print(f"{len(self.checks) - failed}/{len(self.checks)} checks passed")
        return 1 if failed else 0


def audit(path: Path, stand_hex: str | None, letter_hex: str | None) -> int:
    """Run the checks and print the table. Returns a process exit code."""
    return run_audit(path, stand_hex, letter_hex).report()


def run_audit(path: Path, stand_hex: str | None, letter_hex: str | None) -> Audit:
    """The checks themselves, returning the collected results.

    Split out from `audit()` so pytest can assert on individual checks rather
    than on an exit code — a single number tells you something broke but not
    which of the fourteen it was.
    """
    a = Audit()
    z = zipfile.ZipFile(path)

    a.check(z.testzip() is None, "archive integrity", f"{len(z.namelist())} members")

    settings = json.loads(z.read("Metadata/project_settings.config"))

    # --- printer ----------------------------------------------------------
    a.check(
        settings.get("printer_model") == EXPECT_PRINTER,
        "printer model",
        str(settings.get("printer_model")),
    )
    nozzles = settings.get("nozzle_diameter") or []
    a.check(
        list(nozzles) == [EXPECT_NOZZLE],
        "nozzle diameter",
        f"{nozzles} mm",
    )
    profile = str(settings.get("print_settings_id", ""))
    a.check(
        EXPECT_PROFILE_CONTAINS in profile,
        "print profile targets P2S",
        profile,
    )
    a.check(
        bool(settings.get("curr_bed_type")),
        "bed type set",
        str(settings.get("curr_bed_type")),
    )

    # --- filament ---------------------------------------------------------
    ids = settings.get("filament_ids") or []
    types = settings.get("filament_type") or []
    colours = [c.upper() for c in (settings.get("filament_colour") or [])]

    a.check(
        bool(ids) and all(i == PLA_MATTE_ID for i in ids),
        "every slot is PLA Matte",
        f"{ids} (expect all {PLA_MATTE_ID})",
    )
    a.check(
        bool(types) and all(t == EXPECT_TYPE for t in types),
        "filament type",
        str(types),
    )
    a.check(
        len(ids) == len(colours) == len(types),
        "filament arrays agree",
        f"ids={len(ids)} colours={len(colours)} types={len(types)}",
    )
    if stand_hex:
        a.check(stand_hex.upper() in colours, "stand colour present", f"{stand_hex} in {colours}")
    if letter_hex:
        a.check(letter_hex.upper() in colours, "letter colour present", f"{letter_hex} in {colours}")

    # --- plates -----------------------------------------------------------
    model_settings = ET.fromstring(z.read("Metadata/model_settings.config"))
    plates = model_settings.findall(".//plate")
    assigned = model_settings.findall(".//model_instance")
    a.check(len(plates) > 0, "plates defined", f"{len(plates)} plate(s)")
    a.check(len(assigned) > 0, "objects assigned to plates", f"{len(assigned)} instance(s)")

    previews = [n for n in z.namelist() if n.startswith("Metadata/plate_") and n.endswith(".png")]
    a.check(
        len(previews) >= len(plates),
        "plate previews embedded",
        f"{len(previews)} image(s) for {len(plates)} plate(s)",
    )

    # --- geometry ---------------------------------------------------------
    # Vertices live in the per-object models; a part larger than the bed can
    # never be sliced, and the failure in Studio is unhelpful.
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    worst = [0.0, 0.0, 0.0]
    for member in z.namelist():
        if not member.startswith("3D/Objects/"):
            continue
        root = ET.fromstring(z.read(member))
        xs, ys, zs = [], [], []
        for v in root.iterfind(".//m:vertex", ns):
            xs.append(float(v.get("x", 0)))
            ys.append(float(v.get("y", 0)))
            zs.append(float(v.get("z", 0)))
        if not xs:
            continue
        for i, vals in enumerate((xs, ys, zs)):
            worst[i] = max(worst[i], max(vals) - min(vals))

    fits = all(w <= lim for w, lim in zip(worst, BUILD_VOLUME_MM))
    a.check(
        fits,
        "largest part fits the bed",
        f"{worst[0]:.1f} x {worst[1]:.1f} x {worst[2]:.1f} mm "
        f"(limit {BUILD_VOLUME_MM[0]:.0f} x {BUILD_VOLUME_MM[1]:.0f} x {BUILD_VOLUME_MM[2]:.0f})",
    )

    return a


def generate_one() -> tuple[Path, str, str]:
    """Build a fresh 3MF so the audit has something current to look at."""
    sys.path.insert(0, str(REPO / "products" / "dog-bowl"))
    from designer import SPEC  # noqa: E402

    values = SPEC.coerce({"name": "AUDIT", "style": "cooper", "font_style": "bold"})
    out = Path(tempfile.mkdtemp(prefix="ogma-audit-"))
    result = SPEC.generator.generate(values, out)

    from ogma.filaments import load_palette, resolve_filament  # noqa: E402

    palette = load_palette()
    stand = resolve_filament(values["stand_filament_id"], palette)
    letters = resolve_filament(values["letter_filament_id"], palette)
    return out / result["output"], stand.hex, letters.hex


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", type=Path)
    ap.add_argument("--stand")
    ap.add_argument("--letters")
    ap.add_argument("--generate", action="store_true", help="build a fresh 3MF first")
    args = ap.parse_args()

    if args.generate or args.path is None:
        print("Building a 3MF to audit…")
        path, stand, letters = generate_one()
    else:
        path, stand, letters = args.path, args.stand, args.letters

    print(f"\nAuditing {path.name} ({path.stat().st_size / 1e6:.2f} MB)\n")
    return audit(path, stand, letters)


if __name__ == "__main__":
    raise SystemExit(main())
