"""The golden comparator has to do two opposing things well.

It must absorb the drift that geometry kernels produce between versions, and
still fail on a real geometry change. A comparator that only does the first is
a test that always passes — which is worse than no test, because it looks like
cover.

These run in milliseconds against synthetic fingerprints. The expensive part —
actually building the cases — happens in CI, which then calls
`golden_compare.py` against the committed baseline.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "tests") not in sys.path:
    sys.path.insert(0, str(REPO / "tests"))

from golden_compare import compare  # noqa: E402
from goldens import CASES  # noqa: E402


def _mesh(volume=100.0, area=50.0, triangles=1000, vertices=3000, watertight=True):
    return {
        "volume_mm3": volume,
        "area_mm2": area,
        "triangles": triangles,
        "vertices": vertices,
        "watertight": watertight,
        "bounds": [[0.0, 0.0, 0.0], [10.0, 10.0, 10.0]],
    }


def _fingerprint(**mesh_kwargs):
    return {
        "style/NAME/font": {
            "meshes": {"part.stl": _mesh(**mesh_kwargs)},
            "threemf": {"Out.3mf": {"3D/3dmodel.model": {"bytes": 1, "sha256": "aa"}}},
        }
    }


def test_identical_fingerprints_pass():
    a = _fingerprint()
    assert compare(a, copy.deepcopy(a)) == []


# --- must absorb: measured cross-version drift ----------------------------


def test_absorbs_the_measured_triangle_drift():
    """2.59e-2 was the worst observed between trimesh 4.12.2 and 5.0.0."""
    base = _fingerprint(triangles=2004, vertices=6012)
    new = _fingerprint(triangles=1952, vertices=5856)
    assert compare(base, new) == []


def test_absorbs_the_measured_volume_drift():
    """1.21e-5 relative, on the wave style's cone-backed letters."""
    base = _fingerprint(volume=183.226106)
    new = _fingerprint(volume=183.223887)
    assert compare(base, new) == []


def test_absorbs_counts_recorded_under_other_key_names():
    """`upper_triangles` in dimensions is the same quantity as `triangles`.

    Keyed on exact names this was a false failure: the wave upper's count came
    back as 1.3e-2 against the 1e-4 default while the identical number under
    `meshes` passed.
    """
    base = {"c": {"meshes": {}, "dimensions": {"stand": {"upper_triangles": 93156}}}}
    new = {"c": {"meshes": {}, "dimensions": {"stand": {"upper_triangles": 94398}}}}
    assert compare(base, new) == []


# --- must catch: real regressions -----------------------------------------


def test_catches_a_one_percent_volume_change():
    base = _fingerprint(volume=209261.13)
    new = _fingerprint(volume=209261.13 * 1.01)
    diffs = compare(base, new)
    assert diffs and "volume_mm3" in diffs[0]


def test_catches_a_missing_part():
    base = _fingerprint()
    new = copy.deepcopy(base)
    new["style/NAME/font"]["meshes"] = {}
    diffs = compare(base, new)
    assert any("mesh set changed" in d for d in diffs)


def test_catches_a_part_that_stopped_being_watertight():
    """No tolerance may ever absorb this — it is the difference between a
    printable solid and one the slicer will guess at."""
    base = _fingerprint(watertight=True)
    new = _fingerprint(watertight=False)
    diffs = compare(base, new)
    assert any("watertight" in d for d in diffs)


def test_catches_a_moved_part():
    base = _fingerprint()
    new = copy.deepcopy(base)
    new["style/NAME/font"]["meshes"]["part.stl"]["bounds"][1][2] = 12.0
    diffs = compare(base, new)
    assert diffs, "a part 2 mm taller was absorbed"


def test_catches_a_dropped_3mf_member():
    base = _fingerprint()
    new = copy.deepcopy(base)
    new["style/NAME/font"]["threemf"]["Out.3mf"] = {}
    diffs = compare(base, new)
    assert any("3MF members changed" in d for d in diffs)


def test_catches_a_case_that_failed_to_build():
    base = _fingerprint()
    new = {"style/NAME/font": {"ERROR": "Traceback ... NameFitError"}}
    diffs = compare(base, new)
    assert any("FAILED TO BUILD" in d for d in diffs)


def test_catches_a_missing_case():
    base = _fingerprint()
    assert any("missing" in d for d in compare(base, {}))


def test_a_changed_sha_alone_is_not_a_failure():
    """3MF member hashes cover mesh bytes, so they move whenever triangulation
    does. Their *names* are checked; their contents are not."""
    base = _fingerprint()
    new = copy.deepcopy(base)
    new["style/NAME/font"]["threemf"]["Out.3mf"]["3D/3dmodel.model"]["sha256"] = "ff"
    assert compare(base, new) == []


def test_the_committed_baseline_matches_itself():
    """Guards against a corrupt or truncated baseline being committed."""
    import json

    path = REPO / "tests" / "goldens-baseline.json"
    data = json.loads(path.read_text())
    # Against the case list itself, not a number written here as well. A count
    # in two files is a count that goes stale the first time a case is added,
    # and it fails as "the baseline is corrupt" — which is the opposite of what
    # happened.
    expected = {f"{style}/{name}/{font}" for style, name, font in CASES}
    assert set(data) == expected, f"baseline cases {set(data) ^ expected} differ from goldens.CASES"
    assert compare(data, copy.deepcopy(data)) == []
    for case, rec in data.items():
        assert "ERROR" not in rec, f"baseline case {case} was captured from a failed build"
        assert rec.get("meshes"), f"baseline case {case} has no meshes"
