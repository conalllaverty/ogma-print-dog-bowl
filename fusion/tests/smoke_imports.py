#!/usr/bin/env python3
"""Import every module against a stubbed `adsk`, to catch Python-level errors.

Fusion's `adsk` package only exists inside Fusion, so an import error, a
misspelled helper or a bad relative import normally surfaces as a message box
after a full app launch. A recording stub gets the same answer in a second.

The stub returns a MagicMock-alike for anything, so this proves the module
graph loads and the pure-Python paths run — it does NOT prove the geometry is
right. That is what running it in Fusion is for.

    python3 fusion/tests/smoke_imports.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "OgmaBowl"


class Anything:
    """Accepts any attribute, call, index or comparison."""

    def __init__(self, name="adsk"):
        self._name = name

    def __getattr__(self, item):
        return Anything("{}.{}".format(self._name, item))

    def __call__(self, *args, **kwargs):
        return Anything(self._name + "()")

    def __iter__(self):
        return iter(())

    def __repr__(self):
        return "<{}>".format(self._name)


def install_stub():
    adsk = types.ModuleType("adsk")
    adsk.core = Anything("adsk.core")
    adsk.fusion = Anything("adsk.fusion")
    adsk.doEvents = lambda: None
    sys.modules["adsk"] = adsk
    sys.modules["adsk.core"] = adsk.core
    sys.modules["adsk.fusion"] = adsk.fusion

    # The handler base classes get subclassed, so they must be real classes.
    class _Handler:
        def __init__(self, *a, **k):
            pass

    for attribute in ("CommandEventHandler", "CommandCreatedEventHandler",
                      "ValidateInputsEventHandler"):
        setattr(adsk.core, attribute, _Handler)


def main() -> int:
    install_stub()
    sys.path.insert(0, str(ADDIN))

    failures = []
    modules = [
        "ogma_bowl", "ogma_bowl.units", "ogma_bowl.config", "ogma_bowl.api",
        "ogma_bowl.params", "ogma_bowl.letters", "ogma_bowl.styles",
        "ogma_bowl.styles.common", "ogma_bowl.styles.hex",
        "ogma_bowl.styles.fluted", "ogma_bowl.styles.cooper",
        "ogma_bowl.styles.wave", "ogma_bowl.build",
    ]
    for name in modules:
        try:
            __import__(name)
        except Exception as error:
            failures.append("{}: {}: {}".format(
                name, type(error).__name__, error))

    if failures:
        print("IMPORT FAILURES ({}):".format(len(failures)))
        for failure in failures:
            print("  " + failure)
        return 1
    print("all {} modules import".format(len(modules)))

    # Exercise the pure-Python logic that has no Fusion dependency.
    from ogma_bowl import config, letters, params, styles
    from ogma_bowl.units import cm, mm, to_mm

    checks = []

    checks.append(("mm round-trip", abs(to_mm(cm(78.0)) - 78.0) < 1e-12))
    checks.append(("mm expression", mm(1.4) == "1.400000 mm"))
    checks.append(("cm conversion", abs(cm(140.0) - 14.0) < 1e-12))

    checks.append(("style registry", styles.STYLE_IDS ==
                   ("cooper", "wave", "hex", "fluted")))
    checks.append(("style lookup", styles.get("HEX ").STYLE_ID == "hex"))

    checks.append(("name normalise", letters.normalise("  max! ") == "MAX"))
    checks.append(("name truncate",
                   letters.normalise("WILLIAMSON") == "WILLIAMS"))
    try:
        letters.normalise("A")
        checks.append(("short name rejected", False))
    except letters.NameFitError:
        checks.append(("short name rejected", True))

    # 8 letters at 15 mm on the Cooper rail must pass; a runaway must not.
    face_r = config.COOPER["name_rail_outer_r"] + config.LETTER_THICKNESS
    try:
        letters.check_fit(60.0, face_r)
        checks.append(("realistic name fits", True))
    except letters.NameFitError:
        checks.append(("realistic name fits", False))
    try:
        letters.check_fit(200.0, face_r)
        checks.append(("oversized name rejected", False))
    except letters.NameFitError:
        checks.append(("oversized name rejected", True))

    hc = config.honeycomb_params()
    checks.append(("honeycomb columns", hc["ncols"] == 36))
    checks.append(("honeycomb pitch closes",
                   abs(hc["ncols"] * hc["pitch_u"]
                       - 2 * 3.141592653589793 * hc["reference_r"]) < 1e-9))

    fl = config.flute_cutter()
    checks.append(("flute web positive", fl["web"] >= config.FLUTED["min_web"]))

    # Every parameter table entry must be a well-formed 4-tuple.
    well_formed = True
    for style_id in styles.STYLE_IDS:
        for row in params.SHARED + params.STYLE_TABLES[style_id]:
            if len(row) != 4 or not all(isinstance(x, str) for x in row):
                well_formed = False
    checks.append(("parameter tables well formed", well_formed))

    # No duplicate parameter names within a style.
    no_dupes = True
    for style_id in styles.STYLE_IDS:
        names = [row[0] for row in params.SHARED + params.STYLE_TABLES[style_id]]
        if len(names) != len(set(names)):
            no_dupes = False
    checks.append(("no duplicate parameter names", no_dupes))

    failed = [label for label, ok in checks if not ok]
    for label, ok in checks:
        print("  {} {}".format("ok  " if ok else "FAIL", label))
    if failed:
        print("\n{} check(s) failed".format(len(failed)))
        return 1
    print("\nall {} logic checks pass".format(len(checks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
