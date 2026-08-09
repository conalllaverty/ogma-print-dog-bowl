"""The dog bowl's designer spec.

Declares what a customer can configure and how to build it. The web app renders
this without knowing anything about bowls; the only bowl-specific thing it may
draw is the `bowl-fit` custom panel, and it degrades cleanly if it doesn't.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PRODUCT_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in PRODUCT_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (PRODUCT_DIR / "generator", _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import name_fit  # noqa: E402
import styles  # noqa: E402
import cooper_bowl_design as design  # noqa: E402
from cooper_bowl_design import MAX_NAME_LEN, NameFitError  # noqa: E402
from preview import build as build_preview  # noqa: E402
from ogma.designer import (  # noqa: E402
    BooleanParam,
    ChoiceParam,
    FieldError,
    FilamentParam,
    Option,
    ProductSpec,
    TextParam,
    ValidationError,
    WhenFlag,
)
from ogma.filaments import DEFAULT_LETTERS, DEFAULT_STAND  # noqa: E402
from pipeline import FONT_STYLES, generate  # noqa: E402

FONT_LABELS = {
    "bold": ("Print-Safe Sans", "Overpass Bold — physically tested FDM default"),
    "clean": ("Clean Sans", "Source Sans 3 SemiBold — neutral"),
    "serif": ("Elegant Serif", "Lora Medium Italic — the original Wave styling"),
    "slab": ("Robust Slab", "Roboto Slab Bold — print-safe serif"),
    "rounded": ("Soft Rounded", "Fredoka SemiBold"),
    "playful": ("Playful", "Baloo 2 SemiBold"),
    "condensed": ("Condensed", "Barlow Condensed SemiBold — best for long names"),
}

# CSS weight to request from each face in the browser.
#
# Three of these files are variable fonts, and the generator picks a named
# instance from them (design.FONT_VARIATIONS). The browser has to be told the
# same thing or the sample is drawn at the default weight and the customer picks
# a lettering style by looking at the wrong one. The static files already carry
# their weight in the outlines, so they ask for 400 — requesting 600 there gets
# a synthetic emboldening that is not what prints.
_CSS_WEIGHT = {"Bold": 700, "SemiBold": 600}


def _font_meta(style: str) -> dict:
    path = design.FONT_STYLES[style]
    variation = design.FONT_VARIATIONS.get(style)
    return {
        # Relative to the API root; the client composes the URL.
        "font_url": f"/api/v1/fonts/{path.name}",
        "font_weight": _CSS_WEIGHT.get(variation or "", 400),
        "font_italic": "Italic" in path.name,
    }


def _style_options() -> tuple[Option, ...]:
    """Derived from the style registry, so a new styles/<id>.py appears here."""
    return tuple(
        Option(
            id=s.id,
            name=s.name,
            description=s.description,
            available=s.available,
            # This flag is what drives the fuzzy toggle's visibility. The UI
            # never tests a style id.
            flags=("supports_fuzzy",) if s.supports_fuzzy else (),
            # Rendered from the real meshes by tools/render_style_thumbs.py, so
            # the icon cannot drift from the geometry. Path is relative to the
            # product's asset root.
            meta={"thumb": f"styles/{s.id}.png"},
        )
        for s in styles.all_styles()
    )


PARAMS = (
    TextParam(
        id="name",
        label="Pet name",
        help=f"2–{MAX_NAME_LEN} letters, A–Z. Longer names need a condensed font.",
        group="Design",
        default="MAX",
        min_length=2,
        max_length=MAX_NAME_LEN,
        pattern="^[A-Za-z]+$",
        transform="upper",
        placeholder="MAX",
    ),
    ChoiceParam(
        id="style",
        label="Stand style",
        help="All styles seat the same stainless bowl.",
        group="Design",
        options=_style_options(),
        default=styles.DEFAULT_STYLE,
        display="cards",
    ),
    ChoiceParam(
        id="font_style",
        label="Lettering",
        help="Letters print separately at 0.10 mm and glue into pockets.",
        group="Design",
        options=tuple(
            Option(
                id=f,
                name=FONT_LABELS[f][0],
                description=FONT_LABELS[f][1],
                meta=_font_meta(f),
            )
            for f in FONT_STYLES
        ),
        default="bold",
        display="dropdown",
    ),
    FilamentParam(
        id="stand_filament_id",
        label="Stand colour",
        group="Colour",
        default=DEFAULT_STAND,
        role="stand",
    ),
    FilamentParam(
        id="letter_filament_id",
        label="Letter colour",
        group="Colour",
        default=DEFAULT_LETTERS,
        role="letters",
    ),
    BooleanParam(
        id="fuzzy_enabled",
        label="Fuzzy texture",
        help="Soft matte wall finish. Paw pads and the name plaque stay smooth.",
        group="Colour",
        default=True,
        # Only styles that supply a FuzzyPainter can offer this.
        visible_when=WhenFlag("style", "supports_fuzzy"),
    ),
)


class DogBowlGenerator:
    def validate(self, values: dict[str, Any]) -> None:
        """Only the gate the spec can't declare: do the letters physically pack?

        Length, character set and unknown options are all enforced by
        ProductSpec.check_declared() before this runs, so there is no second
        copy of those rules here.
        """
        name = str(values.get("name", ""))
        font_style = str(values.get("font_style", ""))

        fits, needed = name_fit.check(name, font_style)
        if fits:
            return

        # Name a style that actually works rather than guessing "try condensed"
        # — for some names nothing does, and saying so is more useful than
        # sending someone round a loop.
        alternative = name_fit.widest_fitting_font(name)
        if alternative is None:
            hint = f"No lettering style fits {len(name)} letters this wide — try a shorter name."
        elif alternative == font_style:
            hint = "Try a shorter name."
        else:
            hint = f"{FONT_LABELS[alternative][0]} lettering fits this name."

        raise ValidationError(
            [
                FieldError(
                    "name",
                    f"'{name}' is too wide for the rail in this lettering "
                    f"(needs ±{needed:.0f}°, the stand allows ±{name_fit.MAX_RAIL_OUTER_DEG:.0f}°).",
                    hint=hint,
                )
            ]
        )

    def generate(self, values: dict[str, Any], job_dir) -> dict:
        try:
            result = generate(
                values["name"],
                job_dir,
                style=values["style"],
                font_style=values["font_style"],
                stand_filament_id=values["stand_filament_id"],
                letter_filament_id=values["letter_filament_id"],
                fuzzy_enabled=bool(values.get("fuzzy_enabled", False)),
            )
        except NameFitError as exc:
            # validate() should have caught this via name_fit, which measures
            # with the same functions. Kept as a backstop so a drift between
            # the two lands under the name field instead of as a 500 — and so
            # this stays correct if someone posts straight to /generate.
            raise ValidationError(
                [
                    FieldError(
                        "name",
                        str(exc),
                        hint="Try the Condensed lettering, or a shorter name.",
                    )
                ]
            ) from exc
        return {
            "output": result.threemf_path.name,
            "style": result.style,
            "rail_outer_deg": result.rail_outer_deg,
        }

    def preview(self, values: dict[str, Any], out_path) -> dict:
        """A role-tagged GLB of the assembled stand.

        Note what is *not* passed: neither filament, nor the fuzzy flag. The
        viewer applies those. That is what `preview_keys` below encodes, and
        why walking the palette costs nothing.
        """
        return build_preview(
            values["name"],
            values["style"],
            values["font_style"],
            Path(out_path),
        )


SPEC = ProductSpec(
    id="dog-bowl",
    name="Named dog bowl stand",
    tagline="Their name, their bowl.",
    description=(
        "An elevated stand for a stainless dog bowl, with your dog's name in "
        "glue-in letters. Four wall styles, all seating the same bowl."
    ),
    params=PARAMS,
    available=True,
    custom_panels=("bowl-fit",),
    print_note="~7.5 h print · 210–280 g · 2–4 plates",
    # Only these three change the geometry. Colour and fuzzy are applied by the
    # viewer, so the whole palette shares one cached model.
    preview_keys=("name", "style", "font_style"),
    generator=DogBowlGenerator(),
)
