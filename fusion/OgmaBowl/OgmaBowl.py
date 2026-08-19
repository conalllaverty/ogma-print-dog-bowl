"""Ogma Bowl — Fusion add-in entry point.

Adds an "Ogma Bowl" button to Solid > Create. The dialog takes a dog name, a
style and a letter face, and rebuilds the active design from them.

Two Fusion facts shape this file, and both are the kind that fail silently
rather than loudly:

  * Event handlers must be held in a module-level list. An unreferenced handler
    is garbage collected, and a destroyed handler removes itself from the event
    it was attached to — so the dialog simply stops responding, with no error.
  * Documents cannot be saved from inside a command event; a command runs
    inside a transaction and a save cannot be transacted. Exporting .f3d and
    mesh files therefore lives in the separate OgmaBowlExport script, not here.
"""

import traceback

import adsk.core
import adsk.fusion

from .ogma_bowl import build as build_mod
from .ogma_bowl import config as cfg
from .ogma_bowl import letters as letters_mod
from .ogma_bowl import styles

CMD_ID = "OgmaBowlCreate"
CMD_NAME = "Ogma Bowl"
CMD_TOOLTIP = (
    "Build a parametric Ogma dog-bowl stand from a name and a style. "
    "Every dimension lands in Change Parameters as an editable value."
)
WORKSPACE_ID = "FusionSolidEnvironment"
PANEL_ID = "SolidCreatePanel"

# Held for the life of the add-in. See the note above — this is not optional.
_handlers = []

_app = None
_ui = None


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------

class _ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            inputs = args.firingEvent.sender.commandInputs
            design = adsk.fusion.Design.cast(_app.activeProduct)
            if not design:
                _ui.messageBox(
                    "Open a Design (not a Drawing or a CAM setup) and try again."
                )
                return

            options = {
                "name": inputs.itemById("bowlName").value,
                "style": _selected(inputs.itemById("bowlStyle")),
                "font_style": _selected(inputs.itemById("letterStyle")),
                "letter_spacing": inputs.itemById("letterSpacing").value * 10.0,
                "build_letters": inputs.itemById("makeLetters").value,
                "clear_existing": inputs.itemById("clearFirst").value,
            }

            result = build_mod.build_bowl(design, options)
            _report(result)
        except letters_mod.NameFitError as fit_error:
            _ui.messageBox(str(fit_error), "Ogma Bowl")
        except Exception:
            _ui.messageBox(
                "Ogma Bowl could not finish:\n\n{}".format(traceback.format_exc()),
                "Ogma Bowl",
            )


class _ValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            inputs = args.firingEvent.sender.commandInputs
            raw = inputs.itemById("bowlName").value or ""
            letters_only = "".join(ch for ch in raw.upper() if ch.isalpha())
            # areInputsValid is the correct property. Autodesk's own sample in
            # Commands_UM.htm writes `isValid` here, which is the generic
            # "object not deleted" flag and does nothing.
            args.areInputsValid = 2 <= len(letters_only) <= cfg.MAX_NAME_LEN
        except Exception:
            args.areInputsValid = False


class _CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isExecutedWhenPreEmpted = False
            inputs = cmd.commandInputs

            inputs.addStringValueInput("bowlName", "Dog name", "COOPER")

            style_input = inputs.addDropDownCommandInput(
                "bowlStyle", "Stand style",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for index, (style_id, label) in enumerate(styles.labels()):
                style_input.listItems.add(label, index == 0, "")

            letter_input = inputs.addDropDownCommandInput(
                "letterStyle", "Letter style",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for style_id in cfg.FONT_STYLES:
                letter_input.listItems.add(
                    style_id, style_id == cfg.DEFAULT_FONT_STYLE, ""
                )

            inputs.addValueInput(
                "letterSpacing", "Letter spacing", "mm",
                adsk.core.ValueInput.createByString(
                    "{} mm".format(cfg.LETTER_GAP)
                ),
            )
            inputs.addBoolValueInput(
                "makeLetters", "Build glue-in letter solids", True, "", True
            )
            inputs.addBoolValueInput(
                "clearFirst", "Clear the document first", True, "", True
            )

            note = inputs.addTextBoxCommandInput(
                "note", "", _intro_text(), 6, True
            )
            note.isFullWidth = True

            execute = _ExecuteHandler()
            cmd.execute.add(execute)
            _handlers.append(execute)

            validate = _ValidateHandler()
            cmd.validateInputs.add(validate)
            _handlers.append(validate)
        except Exception:
            _ui.messageBox(
                "Ogma Bowl dialog failed to open:\n\n{}".format(
                    traceback.format_exc()),
                "Ogma Bowl",
            )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _selected(dropdown):
    item = dropdown.selectedItem
    if item is None:
        return None
    label = item.name
    for style_id, style_label in styles.labels():
        if style_label == label:
            return style_id
    return label


def _intro_text():
    return (
        "Builds the stand, cuts the name pockets and produces the glue-in "
        "letters as separate bodies.<br/><br/>"
        "Afterwards, every dimension is in <b>Modify &gt; Change "
        "Parameters</b> under the <b>ogma...</b> prefix, and every step is in "
        "the timeline.<br/><br/>"
        "Names are 2-{} letters, A-Z.".format(cfg.MAX_NAME_LEN)
    )


def _report(result):
    lines = [
        "Built {} for '{}'.".format(result["label"], result["name"]),
        "",
        "{} bodies. Edit any dimension in Modify > Change Parameters "
        "(everything prefixed 'ogma').".format(len(result["parts"])),
    ]
    if result["notes"]:
        lines.append("")
        lines.extend("- {}".format(note) for note in result["notes"])
    _ui.messageBox("\n".join(lines), "Ogma Bowl")


# --------------------------------------------------------------------------
# Add-in lifecycle
# --------------------------------------------------------------------------

def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_TOOLTIP
        )

        created = _CreatedHandler()
        cmd_def.commandCreated.add(created)
        _handlers.append(created)

        panel = _ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(
            PANEL_ID
        )
        existing = panel.controls.itemById(CMD_ID)
        if existing:
            existing.deleteMe()
        control = panel.controls.addCommand(cmd_def)
        control.isPromoted = True
    except Exception:
        if _ui:
            _ui.messageBox(
                "Ogma Bowl failed to load:\n\n{}".format(traceback.format_exc())
            )


def stop(context):
    try:
        panel = _ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(
            PANEL_ID
        )
        control = panel.controls.itemById(CMD_ID)
        if control:
            control.deleteMe()
        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        _handlers.clear()
    except Exception:
        if _ui:
            _ui.messageBox(
                "Ogma Bowl failed to unload:\n\n{}".format(
                    traceback.format_exc())
            )
