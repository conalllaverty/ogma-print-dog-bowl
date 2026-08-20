#!/usr/bin/env python3
"""Compare two golden fingerprints with tolerances that reflect measured drift.

`goldens.py` captures an exact fingerprint. Comparing two of them with `==` is
the right check on one machine, and the wrong one across machines: the geometry
kernels are not bit-reproducible across versions, so an exact baseline in CI
fails on an unrelated dependency bump and everyone learns to ignore it.

The tolerances below are measured, not guessed. Running all five cases on
macOS/Python 3.14/trimesh 4.12.2 and on Linux/Python 3.12/trimesh 5.0.0:

    cooper/MAX/bold             identical, every byte
    cooper/WILLIAMS/slab        identical
    hex/MAX/bold                identical
    fluted/MAX/bold             identical
    wave/LUNA/serif             DIFFERS

Only `wave` moves, and only in its boolean-heavy path — the cone-backed letters
and the wrapped upper. Worst observed drift there:

    volume     1.21e-05 relative   (letter_3_N: 183.226106 -> 183.223887 mm3)
    area       3.60e-05 relative
    triangles  2.59e-02 relative   (assembly_letter_4_A: 2004 -> 1952)
    bounds     4.00e-05 mm absolute
    watertight unchanged, mesh set unchanged

So the repo's long-standing note that "volume holds to 7 decimal places" is not
true for the wave style — it holds to about five significant decimals there. The
difference is 0.002 mm3 on a letter, which is orders of magnitude below what a
0.1 mm layer can express, so it is a reporting correction rather than a defect.

**Re-measured 2026-08-20, and the drift grew.** The mixed-case work replaced
every glyph — cap height became the ruler and each letter now carries its own
proportions — so the cone-backed wave letters, already the one unstable path
here, are different meshes than the ones the numbers above were taken from.
Same macOS/Linux split, same two letters, larger:

    triangles  8.53e-02 relative   (letter_2_U: 1664 -> 1522)
    vertices   8.53e-02 relative   (letter_2_U: 4992 -> 4566)
    volume     1.36e-04 relative   (letter_4_A: 138.34147 -> 138.32259 mm3)

Both of those sat *outside* the old thresholds, so the honest reading is that
the thresholds were measured against geometry that no longer exists. They are
re-measured below rather than nudged until CI passes, which is the failure mode
this file exists to avoid.

A tolerance this loose on triangle counts is worth being uncomfortable about:
at 1.2e-01 a real regression would have to change a letter's triangulation by
more than an eighth before it trips. What holds the line instead is that
`watertight` and the mesh *set* still compare exactly, volume stays at 2e-04,
and this drift is confined to one style's boolean path. If the wave's letters
move again, re-measure again — do not widen again.

The thresholds sit roughly an order of magnitude above the worst measured value
for everything except triangles and vertices, where the margin is deliberately
thinner.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Relative tolerance per fingerprint key; `None` means "must match exactly".
REL_TOLERANCE = {
    # 2e-4, from a measured 1.36e-4 on the wave's letter_4_A.
    "volume_mm3": 2e-4,
    "area_mm2": 1e-3,
    # 1.2e-1, from a measured 8.53e-2 on the wave's letter_2_U. See the
    # re-measurement note in the module docstring — and the reason not to
    # reach for this number again next time.
    "triangles": 0.12,
    "vertices": 0.12,
    # Never relaxed. A part that stops being a solid is not drift.
    "watertight": None,
}

# Absolute, in mm — bounds are coordinates, so relative tolerance is wrong near
# zero (a bound at 0.0 has no meaningful relative error).
BOUNDS_ABS_TOLERANCE = 1e-3

# Numbers with no specific rule (rail angles, recorded dimensions).
DEFAULT_REL_TOLERANCE = 1e-4


def _tolerance_for(key: str | None) -> float | None:
    """Tolerance for a fingerprint key.

    Matched by suffix, not equality: the generators record their own counts
    inside `dimensions_and_validation.json` under names like
    `upper_triangles`, and those are the same quantity as a mesh's `triangles`
    — subject to the same ~2.6% retriangulation drift. Keyed on exact names,
    the wave upper's count came back as a 1.3e-2 failure against the 1e-4
    default while the identical number under `meshes` passed.
    """
    if not key:
        return DEFAULT_REL_TOLERANCE
    if key in REL_TOLERANCE:
        return REL_TOLERANCE[key]
    for name, tol in REL_TOLERANCE.items():
        if key.endswith(f"_{name}"):
            return tol
    return DEFAULT_REL_TOLERANCE


def _close(a: float, b: float, rel: float) -> bool:
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-12)


def _compare(a, b, path: str, out: list[str], *, key: str | None = None) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: only in the new run")
            elif k not in b:
                out.append(f"{path}.{k}: missing from the new run")
            else:
                _compare(a[k], b[k], f"{path}.{k}", out, key=k)
        return

    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} -> {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _compare(x, y, f"{path}[{i}]", out, key=key)
        return

    # bool before int: bool is a subclass of int and must never be compared
    # with a tolerance.
    if isinstance(a, bool) or isinstance(b, bool):
        if a != b:
            out.append(f"{path}: {a} -> {b}")
        return

    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if key == "bounds" or path.endswith("]") and ".bounds" in path:
            if abs(a - b) > BOUNDS_ABS_TOLERANCE:
                out.append(f"{path}: {a} -> {b} (>{BOUNDS_ABS_TOLERANCE} mm)")
            return
        rel = _tolerance_for(key)
        if rel is None:
            if a != b:
                out.append(f"{path}: {a} -> {b} (must match exactly)")
            return
        if not _close(float(a), float(b), rel):
            delta = abs(a - b) / max(abs(a), abs(b), 1e-12)
            out.append(f"{path}: {a} -> {b} ({delta:.2e} > {rel:.0e})")
        return

    if a != b:
        out.append(f"{path}: {a!r} -> {b!r}")


def compare(baseline: dict, current: dict) -> list[str]:
    """Return a list of human-readable differences. Empty means it passed."""
    out: list[str] = []

    missing = sorted(set(baseline) - set(current))
    added = sorted(set(current) - set(baseline))
    for c in missing:
        out.append(f"case {c}: missing from the new run")
    for c in added:
        out.append(f"case {c}: not in the baseline")

    for case in sorted(set(baseline) & set(current)):
        base, cur = baseline[case], current[case]
        if "ERROR" in cur:
            out.append(f"case {case}: FAILED TO BUILD — {str(cur['ERROR'])[-300:]}")
            continue

        # The set of parts is structural: a missing plate is a regression no
        # tolerance should absorb.
        bm, cm = base.get("meshes", {}), cur.get("meshes", {})
        if set(bm) != set(cm):
            out.append(
                f"case {case}: mesh set changed — "
                f"missing {sorted(set(bm) - set(cm))}, new {sorted(set(cm) - set(bm))}"
            )

        for name in sorted(set(bm) & set(cm)):
            _compare(bm[name], cm[name], f"{case}/{name}", out)

        # 3MF member *names* must match exactly — a missing plate or settings
        # file is a real break. Their sha256s are deliberately not compared:
        # they hash mesh bytes, so they change whenever triangulation does, and
        # that is exactly the noise these tolerances exist to absorb.
        bt = {m for f in base.get("threemf", {}).values() for m in f}
        ct = {m for f in cur.get("threemf", {}).values() for m in f}
        if bt != ct:
            out.append(
                f"case {case}: 3MF members changed — "
                f"missing {sorted(bt - ct)}, new {sorted(ct - bt)}"
            )

        if "dimensions" in base or "dimensions" in cur:
            _compare(
                base.get("dimensions", {}), cur.get("dimensions", {}),
                f"{case}/dimensions", out,
            )

    return out


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: golden_compare.py BASELINE.json CURRENT.json", file=sys.stderr)
        return 2
    baseline = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    current = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

    diffs = compare(baseline, current)
    if not diffs:
        print(f"geometry matches the baseline ({len(baseline)} cases, within tolerance)")
        return 0

    print(f"{len(diffs)} difference(s) beyond tolerance:\n")
    for d in diffs:
        print(f"  {d}")
    print(
        "\nIf this is an intended geometry change, regenerate the baseline:\n"
        "  python tests/goldens.py tests/goldens-baseline.json /tmp/goldenjobs"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
