#!/usr/bin/env python3
"""Capture a behaviour fingerprint of the bowl generators.

Run before and after a refactor; the two JSON files must be identical.
Fingerprints mesh geometry AND the 3MF package contents, because a refactor can
preserve meshes while breaking the project file (or vice versa).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PIPELINE = REPO / "products" / "dog-bowl" / "generator" / "pipeline.py"
PY = sys.executable

CASES = [
    ("cooper", "MAX", "bold"),
    ("cooper", "WILLIAMS", "condensed"),   # 8-letter worst case for the packing gate
    ("wave", "LUNA", "serif"),
    ("hex", "MAX", "bold"),
    ("fluted", "MAX", "bold"),
    # Mixed case, in the face with the deepest descender. Carries the three
    # things capitals never exercise: a plaque lowered to cover the 'y', a
    # second body for the tittle on the 'i', and glyphs of three different
    # heights sharing one baseline.
    ("cooper", "Bailey", "serif"),
]


def mesh_fingerprint(path: Path) -> dict:
    import trimesh
    m = trimesh.load(path, process=False)
    return {
        "triangles": int(len(m.faces)),
        "vertices": int(len(m.vertices)),
        "volume_mm3": round(float(m.volume), 6),
        "area_mm2": round(float(m.area), 6),
        "watertight": bool(m.is_watertight),
        "bounds": [[round(float(v), 6) for v in row] for row in m.bounds],
    }


def threemf_fingerprint(path: Path) -> dict:
    """Hash each member's bytes. Ignores zip timestamps/ordering."""
    out = {}
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            data = z.read(name)
            out[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()[:16]}
    return out


# --------------------------------------------------------------------------
# Volatile fields.
#
# The export filename carries a creation timestamp and job.json records the same
# instant, so two runs of identical code produce different bytes in those two
# places and nowhere else. A fingerprint that included them would report a
# difference on every single run, which is the fastest way to teach everyone to
# ignore this harness.
#
# Normalised rather than dropped: the *shape* of the name still gets compared,
# so losing the suffix or the style token is still caught. Only the instant is
# blanked.
# --------------------------------------------------------------------------

TIMESTAMP_IN_NAME = re.compile(r"_\d{8}-\d{6}(?=\.3mf$)")
# `renders` is environment-dependent, not behavioural: CI has no GL stack, so
# renders.build returns an empty list there while a dev machine returns four
# filenames. Fingerprinting it would make the comparison fail on the machine
# rather than on the code, which is the opposite of what this harness is for.
VOLATILE_JOB_KEYS = ("created_at", "renders")


def stable_name(filename: str) -> str:
    return TIMESTAMP_IN_NAME.sub("_<timestamp>", filename)


def stable(job: dict) -> dict:
    out = {k: v for k, v in job.items() if k not in VOLATILE_JOB_KEYS}
    if isinstance(out.get("threemf"), str):
        out["threemf"] = stable_name(out["threemf"])
    return out


def run_case(style: str, name: str, font: str, outroot: Path) -> dict:
    job = outroot / f"{style}-{name}-{font}"
    proc = subprocess.run(
        [PY, str(PIPELINE), "--name", name, "--style", style,
         "--font-style", font, "--out", str(job)],
        capture_output=True, text=True, timeout=2400,
    )
    if proc.returncode != 0:
        return {"ERROR": proc.stderr[-2500:]}

    rec: dict = {}
    dims = job / "dimensions_and_validation.json"
    if dims.exists():
        rec["dimensions"] = json.loads(dims.read_text())
    jj = job / "job.json"
    if jj.exists():
        rec["job"] = stable(json.loads(jj.read_text()))

    rec["meshes"] = {
        p.name: mesh_fingerprint(p) for p in sorted((job / "meshes").glob("*.stl"))
    }
    threemf = sorted(job.glob("*.3mf"))
    rec["threemf"] = {stable_name(p.name): threemf_fingerprint(p) for p in threemf}
    return rec


def main() -> int:
    outroot = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/goldenjobs")
    outroot.mkdir(parents=True, exist_ok=True)
    result = {}
    for style, name, font in CASES:
        key = f"{style}/{name}/{font}"
        print(f"  running {key} ...", flush=True)
        result[key] = run_case(style, name, font, outroot)
        if "ERROR" in result[key]:
            print(f"    !! FAILED\n{result[key]['ERROR'][-900:]}", flush=True)
        else:
            nm = len(result[key]["meshes"])
            vol = sum(m["volume_mm3"] for m in result[key]["meshes"].values())
            print(f"    ok — {nm} meshes, total volume {vol:,.1f} mm3", flush=True)
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
