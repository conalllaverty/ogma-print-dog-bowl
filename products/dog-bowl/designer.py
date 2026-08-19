"""The dog bowl's designer spec.

Declares what a customer can configure and how to build it. The web app renders
this without knowing anything about bowls; the only bowl-specific thing it may
draw is the `bowl-fit` custom panel, and it degrades cleanly if it doesn't.
"""

from __future__ import annotations

import hashlib
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
    IntegerParam,
    ChoiceParam,
    FieldError,
    FilamentParam,
    Option,
    ProductSpec,
    TextParam,
    ValidationError,
    WhenEquals,
    WhenFlag,
)
from ogma.filaments import (  # noqa: E402
    DEFAULT_LETTERS,
    DEFAULT_STAND,
    DEFAULT_STAND_UPPER,
)
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


def _geometry_fingerprint() -> str:
    """Digest of every generator source file, for ProductSpec.geometry_version.

    Hashed rather than hand-versioned because a hand-maintained number is only
    correct until the first person who forgets to bump it — and the failure is
    invisible: the configurator keeps serving a cached preview of the previous
    shape, which looks like the change simply not working.

    Cheap: seven files, read once at import.
    """
    digest = hashlib.sha256()
    for path in sorted((PRODUCT_DIR / "generator").rglob("*.py")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _thumb_ref(style_id: str) -> str:
    """Relative path to a style icon, fingerprinted with its own contents.

    The asset route serves these `public, max-age=86400` — right for a file that
    almost never changes, wrong for one that just did. Regenerating the icons
    left every browser showing the previous set for a day, and a hard refresh
    does not fix it: the client requests them *after* hydration, so a reload's
    cache bypass never covers them.

    Hashing the bytes into the URL is what makes a long cache both safe and
    correct — the URL changes exactly when the picture does, and old entries are
    simply never asked for again. The route reads the path parameter only, so
    the query string costs nothing.

    Computed at import, which means regenerating icons needs an API restart to
    take effect. That is the right trade for a committed build-time asset, and
    it is the same bargain ogma.preview.PREVIEW_FORMAT_VERSION makes.
    """
    relative = f"styles/{style_id}.png"
    try:
        digest = hashlib.sha256((PRODUCT_DIR / "assets" / relative).read_bytes())
    except OSError:
        # A missing icon is the asset route's 404 to report, not ours to hide.
        return relative
    return f"{relative}?v={digest.hexdigest()[:10]}"


def _style_options() -> tuple[Option, ...]:
    """Derived from the style registry, so a new styles/<id>.py appears here."""
    return tuple(
        Option(
            id=s.id,
            name=s.name,
            description=s.description,
            available=s.available,
            # These flags are what drive conditional controls. The UI never
            # tests a style id — see WhenFlag in ogma.designer.
            flags=tuple(
                name
                for name, on in (
                    ("supports_fuzzy", s.supports_fuzzy),
                    ("two_tone_body", s.two_tone_body),
                    ("supports_one_piece", s.supports_one_piece),
                )
                if on
            ),
            # Rendered from the real meshes by tools/render_style_thumbs.py, so
            # the icon cannot drift from the geometry. Path is relative to the
            # product's asset root.
            meta={"thumb": _thumb_ref(s.id)},
        )
        for s in styles.all_styles()
    )


PARAMS = (
    TextParam(
        id="name",
        label="Pet name",
        help=(
            f"2–{MAX_NAME_LEN} letters. Capitals and lower case both print — "
            "the name is set the way you type it. Longer names need a "
            "condensed font."
        ),
        group="Design",
        default="Max",
        min_length=2,
        max_length=MAX_NAME_LEN,
        pattern="^[A-Za-z]+$",
        # No transform. It was "upper", which meant the field rewrote the
        # customer's name as they typed it and every stand shipped shouting.
        transform="none",
        placeholder="Max",
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
    IntegerParam(
        id="bowl_diameter_mm",
        label="Bowl diameter",
        help=(
            "Across the rim of your stainless bowl, in millimetres. A nominal "
            "5.5\" bowl measures 140 mm. Measure the widest point of the lip — "
            "the seat is cut to catch it."
        ),
        group="Design",
        default=int(design.DEFAULT_BOWL_RIM_OD),
        minimum=int(design.MIN_BOWL_RIM_OD),
        maximum=int(design.MAX_BOWL_RIM_OD),
        step=1,
    ),
    IntegerParam(
        id="bowl_body_mm",
        label="Bowl body diameter",
        help=(
            "Across the bowl just below the rim — the part that drops through "
            "the hole. Usually ~10 mm less than the rim. This one sets the "
            "opening; the rim measurement sets the seat that catches it."
        ),
        group="Design",
        default=int(design.DEFAULT_BOWL_RIM_OD * design.BOWL_BODY_RATIO),
        minimum=100,
        maximum=150,
        step=1,
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
        id="upper_filament_id",
        label="Upper colour",
        help=(
            "The split wave prints as two bodies that meet at the sine seam. "
            "This is the upper one, which also carries the name."
        ),
        group="Colour",
        default=DEFAULT_STAND_UPPER,
        role="stand_upper",
        # Only a style whose body is actually two printed parts can offer this.
        visible_when=WhenFlag("style", "two_tone_body"),
    ),
    BooleanParam(
        id="one_piece",
        label="Print as one piece",
        help=(
            "Off, the stand prints as three parts that key together. On, it is "
            "a single body — no joints to trap water, and nothing to assemble. "
            "One longer print instead of three shorter ones."
        ),
        group="Design",
        default=False,
        # Only a style that is actually multi-part can offer this.
        visible_when=WhenFlag("style", "supports_one_piece"),
    ),
    BooleanParam(
        id="letters_enabled",
        label="Glue-in letters",
        help=(
            "On, the name prints as separate letters in a second colour that "
            "glue into the pockets. Off, the pockets stay empty — the name is "
            "debossed into the stand and the whole thing prints in one colour."
        ),
        group="Colour",
        default=True,
    ),
    FilamentParam(
        id="letter_filament_id",
        label="Letter colour",
        group="Colour",
        default=DEFAULT_LETTERS,
        role="letters",
        # No letters, no second colour to pick. A boolean's value reaches the UI
        # as a string, which is why this is "true" rather than True.
        visible_when=WhenEquals("letters_enabled", ("true",)),
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
        # The bowl pair is a geometry gate the spec cannot declare: it is a
        # relationship between two fields, not a range on either. Checked here
        # so it lands under the control that caused it instead of surfacing as a
        # 500 from deep in the mesh build.
        try:
            design.configure_bowl(
                values.get("bowl_diameter_mm"), values.get("bowl_body_mm")
            )
        except ValueError as exc:
            raise ValidationError(
                [
                    FieldError(
                        "bowl_body_mm",
                        str(exc),
                        hint=(
                            "Measure the bowl just under the rim — it should be "
                            "several millimetres narrower than the rim itself."
                        ),
                    )
                ]
            ) from exc

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
                upper_filament_id=values.get("upper_filament_id"),
                letter_filament_id=values["letter_filament_id"],
                fuzzy_enabled=bool(values.get("fuzzy_enabled", False)),
                letters_enabled=bool(values.get("letters_enabled", True)),
                bowl_diameter_mm=values.get("bowl_diameter_mm"),
                bowl_body_mm=values.get("bowl_body_mm"),
                one_piece=bool(values.get("one_piece", False)),
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
            # Everything here except `output` becomes job.meta, which is what
            # the download route reads to decide what goes in the customer's
            # bundle. Renders that are not named here exist on disk and ship to
            # nobody.
            "renders": result.renders,
        }

    def warm(self) -> None:
        """Measure every lettering face's glyphs so the first fit check is fast.

        Ordered, and the order matters. The default font first, because that
        makes the *verdict* fast within a few seconds and the verdict is what
        gates the button. The other six after, because the *hint* names a style
        that fits, which means measuring the name in all of them — with only the
        default warm, a rejected name still took ~2.6 s to explain itself.

        ~110 s of background CPU at boot, on a daemon thread that holds no lock.
        Double what it was: names keep their case now, so each face has 52
        glyphs to measure rather than 26.
        """
        # By id, not by position: PARAMS is reordered whenever the form is.
        default = SPEC.param("font_style").default
        for style in (default, *(f for f in FONT_STYLES if f != default)):
            name_fit.warm_cache(font_style=style)

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
            bowl_diameter_mm=values.get("bowl_diameter_mm"),
            bowl_body_mm=values.get("bowl_body_mm"),
            one_piece=bool(values.get("one_piece", False)),
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
    # Deliberately vague on plates now that the paw lattice can be one piece
    # (2 plates) or three (4), and the drums are 2. A single number here was
    # only ever true for one configuration.
    print_note="~7.5 h print · 210–280 g · prints in 1–4 plates",
    # Only these three change the geometry. Colour and fuzzy are applied by the
    # viewer, so the whole palette shares one cached model.
    # Bowl diameter cuts the seat, so it is geometry, not colour.
    preview_keys=(
        "name", "style", "font_style", "bowl_diameter_mm", "bowl_body_mm",
        "one_piece",
    ),
    geometry_version=_geometry_fingerprint(),
    generator=DogBowlGenerator(),
)
