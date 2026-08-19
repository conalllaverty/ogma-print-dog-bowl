"""Batch-build every bowl style and write .f3d files to disk.

Run from Utilities > Scripts and Add-Ins > Scripts. This is a Script rather
than part of the add-in on purpose: saving and exporting are forbidden inside a
command event, because a command runs inside a transaction that a save cannot
join. A script has no such transaction, so it can write files.

Output per style:

    <NAME>_<Style>_P2S.f3d    Fusion archive - open this to edit
    <NAME>_<Style>_P2S.3mf    mesh, for the slicer
    <NAME>_<Style>_P2S.step   BRep interchange

Edit NAME and OUT_DIR below, or set them in the prompt the script opens with.
"""

import os
import sys
import traceback

import adsk.core
import adsk.fusion

# Make the sibling add-in package importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ADDIN = os.path.normpath(os.path.join(_HERE, os.pardir, "OgmaBowl"))
if _ADDIN not in sys.path:
    sys.path.insert(0, _ADDIN)

from ogma_bowl import build as build_mod  # noqa: E402
from ogma_bowl import styles  # noqa: E402


DEFAULT_NAME = "COOPER"
DEFAULT_OUT = os.path.expanduser("~/Documents/Claude/Projects/Ogma Print/fusion-bowls")


def _export(design, folder, stem, ui):
    """Write .f3d, .3mf and .step for the current design. Returns written paths."""
    manager = design.exportManager
    written = []

    f3d_path = os.path.join(folder, stem + ".f3d")
    try:
        options = manager.createFusionArchiveExportOptions(f3d_path)
        if manager.execute(options):
            written.append(f3d_path)
    except Exception:
        ui.messageBox("f3d export failed for {}:\n{}".format(
            stem, traceback.format_exc()))

    mesh_path = os.path.join(folder, stem + ".3mf")
    try:
        # createC3MFExportOptions, not create3MFExportOptions - the latter
        # does not exist. Note the argument order flips versus the archive
        # exporters: mesh formats take (geometry, filename).
        options = manager.createC3MFExportOptions(design.rootComponent, mesh_path)
        options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        if manager.execute(options):
            written.append(mesh_path)
    except Exception:
        pass

    step_path = os.path.join(folder, stem + ".step")
    try:
        options = manager.createSTEPExportOptions(step_path)
        if manager.execute(options):
            written.append(step_path)
    except Exception:
        pass

    return written


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        name_input, cancelled = ui.inputBox(
            "Dog name to build into every style (2-8 letters, A-Z):",
            "Ogma Bowl - batch export", DEFAULT_NAME,
        )
        if cancelled:
            return
        folder_dialog = ui.createFolderDialog()
        folder_dialog.title = "Where should the Fusion files go?"
        folder_dialog.initialDirectory = DEFAULT_OUT
        if folder_dialog.showDialog() != adsk.core.DialogResults.DialogOK:
            return
        out_dir = folder_dialog.folder
        os.makedirs(out_dir, exist_ok=True)

        report = []
        for style_module in styles.all_styles():
            doc = app.documents.add(
                adsk.core.DocumentTypes.FusionDesignDocumentType
            )
            design = adsk.fusion.Design.cast(app.activeProduct)
            design.designType = adsk.fusion.DesignTypes.ParametricDesignType
            try:
                result = build_mod.build_bowl(design, {
                    "name": name_input,
                    "style": style_module.STYLE_ID,
                    "clear_existing": False,
                })
                design.rootComponent.name = result["filename"]
                adsk.doEvents()
                written = _export(design, out_dir, result["filename"], ui)
                report.append("{}: {} file(s)".format(
                    style_module.LABEL, len(written)))
            except Exception:
                report.append("{}: FAILED\n{}".format(
                    style_module.LABEL, traceback.format_exc(limit=4)))
            finally:
                try:
                    doc.close(False)
                except Exception:
                    pass

        ui.messageBox(
            "Wrote to:\n{}\n\n{}".format(out_dir, "\n".join(report)),
            "Ogma Bowl - batch export",
        )
    except Exception:
        if ui:
            ui.messageBox("Batch export failed:\n\n{}".format(
                traceback.format_exc()))
