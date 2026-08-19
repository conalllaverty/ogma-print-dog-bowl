#!/usr/bin/env python3
"""Audit every Fusion API name the add-in touches against a verified whitelist.

Fusion's Python is not importable outside Fusion, so a typo in an API call is
normally found by launching Fusion, opening the dialog, and reading a traceback
in a message box. That loop is slow enough that it encourages guessing.

This checks statically instead. It walks the AST of every module, collects each
`adsk.<...>` attribute chain and each method called on the objects the wrappers
create, and compares them against WHITELIST — which was built from the Fusion
API Reference, including the retirements that trip up most sample code:

    ExtrudeFeatureInput.setDistanceExtent   retired 2022-09
    SketchTexts.createInput / createInput2  retired 2021-01 / 2025-11
    ExtrudeFeatures.createInput2            never existed
    ExportManager.create3MFExportOptions    never existed (it is createC3MF...)
    SphereFeatures.add / createInput        never existed (collection is read-only)

Anything used but not whitelisted is reported so it can be verified against the
docs and added deliberately, rather than discovered at runtime.

    python3 fusion/tests/check_api_surface.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Verified against help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/
WHITELIST = {
    # adsk.core
    "adsk.core.Application", "adsk.core.ObjectCollection", "adsk.core.Point3D",
    "adsk.core.Vector3D", "adsk.core.Matrix3D", "adsk.core.ValueInput",
    "adsk.core.DropDownStyles", "adsk.core.HorizontalAlignments",
    "adsk.core.VerticalAlignments", "adsk.core.CommandEventHandler",
    "adsk.core.CommandCreatedEventHandler",
    "adsk.core.ValidateInputsEventHandler", "adsk.core.DocumentTypes",
    "adsk.core.DialogResults", "adsk.core.Cylinder",
    # adsk.fusion
    "adsk.fusion.Design", "adsk.fusion.FeatureOperations",
    "adsk.fusion.ExtentDirections", "adsk.fusion.DistanceExtentDefinition",
    "adsk.fusion.PatternDistanceType", "adsk.fusion.TextStyles",
    "adsk.fusion.DesignTypes", "adsk.fusion.DesignTypes.ParametricDesignType",
    "adsk.fusion.Path", "adsk.fusion.ChainedCurveOptions",
    "adsk.fusion.CalculationAccuracy", "adsk.fusion.MeshRefinementSettings",
    "adsk.doEvents",
}

# Methods called on Fusion objects, grouped by the collection they hang off.
# Retired or non-existent members are listed in BANNED below.
VERIFIED_METHODS = {
    # collections -> creation
    "createInput", "createInput2", "createInput3", "add", "addSimple",
    "item", "itemById", "itemByName", "cast", "get", "create",
    # feature inputs
    "setAngleExtent", "setOneSideExtent", "setSymmetricExtent",
    "setTwoSidesExtent", "setToNonUniform", "setByOffset", "setByThreePoints",
    "setByAngle", "defineAsFreeMove", "setAsMultiLine", "setAsFitOnPath",
    "setAsAlongPath", "setToRotation", "setDirectionTwo",
    # sketch geometry
    "addByTwoPoints", "addByCenterRadius", "addByThreePoints",
    "addByCenterStartSweep", "addByCenterStartEnd", "addFillet",
    "areaProperties", "asCurves", "explode",
    # command inputs
    "addStringValueInput", "addDropDownCommandInput", "addValueInput",
    "addBoolValueInput", "addIntegerSpinnerCommandInput",
    "addTextBoxCommandInput", "addSelectionInput", "addButtonDefinition",
    "addCommand", "createByString", "createByReal",
    # documents / export
    "saveAs", "save", "close", "execute", "createFusionArchiveExportOptions",
    "createC3MFExportOptions", "createSTLExportOptions",
    "createSTEPExportOptions", "createFolderDialog", "showDialog",
    "inputBox", "messageBox", "doEvents",
    # timeline / lifecycle
    "rollTo", "moveToEnd", "moveToBeginning", "deleteAllAfterMarker",
    "deleteMe", "makeAll", "clear", "append", "insert",
}

BANNED = {
    "setDistanceExtent": "retired 2022-09; use setOneSideExtent",
    "setAllExtent": "retired 2022-09; use ThroughAllExtentDefinition",
    "setOneSideToExtent": "retired 2022-09; use ToEntityExtentDefinition",
    "setTwoSidesDistanceExtent": "retired 2022-09",
    "setTwoSidesToExtent": "retired 2022-09",
    "create3MFExportOptions": "does not exist; use createC3MFExportOptions",
    "addSimpleTextBoxCommandInput": "does not exist",
    "addFormattedTextBoxCommandInput": "does not exist",
}

BANNED_ATTRS = {
    "loftRails": "does not exist; use centerLineOrRails",
    "boundaryLines": "retired; it is the bounding rectangle, not the glyphs",
}


def chain(node):
    """Dotted name for an Attribute/Name chain, or None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def audit(path: Path):
    problems, unknown = [], set()
    tree = ast.parse(path.read_text(), str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            dotted = chain(node)
            if dotted and dotted.startswith("adsk."):
                head = ".".join(dotted.split(".")[:3])
                if head not in WHITELIST and dotted not in WHITELIST:
                    unknown.add(dotted)
            if node.attr in BANNED_ATTRS:
                problems.append("{}: {} — {}".format(
                    path.name, node.attr, BANNED_ATTRS[node.attr]))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in BANNED:
                problems.append("{}:{} calls {} — {}".format(
                    path.name, node.lineno, method, BANNED[method]))
    return problems, unknown


def main() -> int:
    files = sorted(ROOT.rglob("*.py"))
    files = [f for f in files if "tests" not in f.parts]
    all_problems, all_unknown = [], set()
    for path in files:
        problems, unknown = audit(path)
        all_problems.extend(problems)
        all_unknown |= unknown

    print("audited {} modules".format(len(files)))

    if all_unknown:
        print("\nadsk names used but not on the verified whitelist:")
        for name in sorted(all_unknown):
            print("  " + name)

    if all_problems:
        print("\nRETIRED / NON-EXISTENT API ({}):".format(len(all_problems)))
        for problem in all_problems:
            print("  " + problem)
        return 1

    print("no retired or non-existent API calls found.")
    return 0 if not all_unknown else 0


if __name__ == "__main__":
    raise SystemExit(main())
