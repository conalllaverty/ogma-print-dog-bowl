"""Orchestration — turn a name + style + options into a finished Fusion design.

One entry point, `build_bowl`. It is deliberately usable from three places:
the toolbar command, the batch export script, and a bare Fusion script, which
is why it takes a plain options dict and returns a plain result dict rather
than reaching for any UI.
"""

from __future__ import annotations

import math
import traceback

import adsk.core
import adsk.fusion

from . import config as cfg
from . import letters as letters_mod
from . import params as params_mod
from . import styles


DEFAULTS = {
    "name": "COOPER",
    "style": "cooper",
    "font_style": cfg.DEFAULT_FONT_STYLE,
    "letter_spacing": 1.2,
    "build_letters": True,
    "clear_existing": True,
}


def _clear(design):
    """Empty the document so a re-run replaces rather than stacks.

    Deleting the timeline entries is not enough on its own — bodies created by
    a base feature or left behind by a failed run survive it — so bodies and
    sketches get swept too.
    """
    root = design.rootComponent
    try:
        design.timeline.deleteAllAfterMarker()
    except Exception:
        pass
    try:
        while design.timeline.count:
            design.timeline.item(0).deleteMe(True)
    except Exception:
        pass
    for collection_name in ("bRepBodies", "sketches", "constructionPlanes"):
        try:
            items = getattr(root, collection_name)
            for i in range(items.count - 1, -1, -1):
                items.item(i).deleteMe()
        except Exception:
            pass


def build_bowl(design, options=None, progress=None):
    """Build one bowl. Returns a result dict; raises on a fatal problem.

    `progress` is an optional callable taking a status string, so the command
    and the batch script can each report in their own way.
    """
    opts = dict(DEFAULTS)
    opts.update(options or {})
    say = progress or (lambda _message: None)

    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        # Direct mode has no timeline, so nothing built here would be editable
        # afterwards — which is the entire point of the exercise.
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    name = letters_mod.normalise(opts["name"])
    style = styles.get(opts["style"])
    font_name, bold, font_note = letters_mod.resolve_font(None, opts["font_style"])

    if opts["clear_existing"]:
        say("Clearing the document")
        _clear(design)

    root = design.rootComponent
    say("Creating parameters")
    params_mod.create(design, style.STYLE_ID)

    say("Building {}".format(style.LABEL))
    ctx = {
        "name": name,
        "font_name": font_name,
        "bold": bold,
        "font_style": opts["font_style"],
        "letter_spacing": opts["letter_spacing"],
    }

    # Cooper sizes its name plaque from the packed word, so the width has to be
    # known before the panel is built. Every other style cuts into a wall that
    # already exists, so it measures after.
    if style.STYLE_ID == "cooper":
        width = letters_mod.measure_name(
            root, name, cfg.LETTER_HEIGHT, font_name, bold,
            opts["letter_spacing"],
        )
        face_r = cfg.COOPER["name_rail_outer_r"] + cfg.LETTER_THICKNESS
        flat_deg = math.degrees(
            (width * 0.5 + cfg.LETTER_END_MARGIN) / face_r
        )
        letters_mod.check_fit(width, face_r)
        ctx["rail_flat_deg"] = flat_deg
        ctx["rail_outer_deg"] = flat_deg + 1.5
        ctx["name_width"] = width

    result = style.build(root, ctx)
    notes = list(result.get("notes", []))
    parts = list(result.get("parts", []))

    wall_r = result["wall_radius"]
    centre_z = result["letter_center_z"]

    if opts["build_letters"]:
        say("Measuring the name")
        width = ctx.get("name_width") or letters_mod.measure_name(
            root, name, cfg.LETTER_HEIGHT, font_name, bold,
            opts["letter_spacing"],
        )
        half_angle = letters_mod.check_fit(width, wall_r + cfg.LETTER_THICKNESS)

        # Drum styles need the texture flattened behind the name first, or the
        # pockets would be cut into grooves and have no floor.
        fill = getattr(style, "fill_name_keepout", None)
        if fill and result.get("keepout_fill_depth"):
            say("Flattening the name field")
            margin = result.get("keepout_margin", 1.5)
            fill(
                root, result["body"], wall_r, centre_z,
                half_width=width * 0.5 + margin,
                half_height=cfg.LETTER_HEIGHT * 0.5 + margin,
                depth=result["keepout_fill_depth"],
            )

        say("Engraving the name")
        letters_mod.build_pockets(
            root, result["body"], wall_r, centre_z, name,
            cfg.LETTER_HEIGHT, font_name, bold, cfg.LETTER_POCKET_DEPTH,
            opts["letter_spacing"],
        )

        say("Building the letter solids")
        try:
            letter_bodies = letters_mod.build_letter_solids(
                root, wall_r, centre_z, name, cfg.LETTER_HEIGHT, font_name,
                bold, cfg.LETTER_POCKET_DEPTH, cfg.LETTER_THICKNESS,
                opts["letter_spacing"], half_angle,
            )
            parts.extend(letter_bodies)
            notes.append(
                "{} letter solids, {:.2f} mm proud, seating on a "
                "R{:.2f} mm pocket floor.".format(
                    len(letter_bodies), cfg.LETTER_THICKNESS,
                    wall_r - cfg.LETTER_POCKET_DEPTH)
            )
        except Exception:
            notes.append(
                "Letter solids failed — the pockets are cut but the glue-in "
                "letters were not produced:\n" + traceback.format_exc(limit=3)
            )

    notes.append(font_note)

    try:
        design.timeline.moveToEnd()
    except Exception:
        pass

    return {
        "name": name,
        "style": style.STYLE_ID,
        "label": style.LABEL,
        "suffix": style.OUTPUT_SUFFIX,
        "parts": parts,
        "notes": notes,
        "filename": "{}_{}_P2S".format(name, style.OUTPUT_SUFFIX),
    }
