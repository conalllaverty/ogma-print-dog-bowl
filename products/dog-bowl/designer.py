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

import styles  # noqa: E402
from cooper_bowl_design import MAX_NAME_LEN, NameFitError  # noqa: E402
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
            Option(id=f, name=FONT_LABELS[f][0], description=FONT_LABELS[f][1])
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
        errors: list[FieldError] = []
        name = str(values.get("name", ""))

        if not name.isalpha():
            errors.append(FieldError("name", "Letters A–Z only."))
        elif not (2 <= len(name) <= MAX_NAME_LEN):
            errors.append(
                FieldError("name", f"Use between 2 and {MAX_NAME_LEN} letters.")
            )

        style_id = str(values.get("style", ""))
        try:
            style = styles.get(style_id)
            if not style.available:
                errors.append(FieldError("style", f"{style.name} is not available yet."))
        except ValueError:
            errors.append(FieldError("style", f"Unknown style {style_id!r}."))

        if str(values.get("font_style")) not in FONT_STYLES:
            errors.append(FieldError("font_style", "Unknown lettering style."))

        if errors:
            raise ValidationError(errors)

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
            # The real gate: letters must pack inside MAX_RAIL_OUTER_DEG. Only
            # the geometry knows, so it surfaces here as a field error rather
            # than a 500.
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
    generator=DogBowlGenerator(),
)
