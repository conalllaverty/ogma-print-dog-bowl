"""The common designer spec — how any product describes its configurator.

A product declares *what* can be configured; the web app decides *how* to draw
it. That split is what lets one designer UI serve a dog bowl and a lamp without
either knowing about the other.

This module is product-agnostic by rule (see AGENTS.md): it must not import a
bowl, a lamp or anything else under products/.

Design notes worth keeping:

- **Filament is its own kind, not a colour picker.** A house rule is that only
  Bambu Matte palette IDs are selectable. Modelling it as `FilamentParam` makes
  that structural rather than a convention someone can forget.

- **Options carry flags, and visibility keys off them.** The bowl's fuzzy toggle
  only applies to styles that paint fuzzy skin. Rather than the web app testing
  `style === "cooper"`, the style option carries `supports_fuzzy` and the toggle
  declares `visible_when=WhenFlag("style", "supports_fuzzy")`. A new style turns
  its own toggle on with no UI change — the same inversion the BowlStyle
  registry made on the backend.

- **Validation is server-side and field-addressed.** Cheap constraints (length,
  pattern) are declared so the UI can check as you type, but the real gates live
  in geometry — the bowl rejects a name whose letters can't pack inside ±45 deg,
  and only the generator knows that. `validate()` returns errors keyed by
  parameter id so the UI can put the message under the offending control instead
  of failing at generate time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence

from ogma.filaments import load_palette, resolve_filament

# --------------------------------------------------------------------------
# Conditional visibility
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WhenFlag:
    """Show this parameter only when the chosen option of `param` sets `flag`."""

    param: str
    flag: str

    def to_json(self) -> dict:
        return {"type": "flag", "param": self.param, "flag": self.flag}


@dataclass(frozen=True)
class WhenEquals:
    """Show this parameter only when `param` currently equals one of `values`."""

    param: str
    values: tuple[str, ...]

    def to_json(self) -> dict:
        return {"type": "equals", "param": self.param, "values": list(self.values)}


Visibility = WhenFlag | WhenEquals


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Option:
    """One entry in a ChoiceParam.

    `flags` is how an option advertises a capability to the rest of the spec —
    see WhenFlag. `meta` is free-form passthrough for the UI (swatch, preview
    image, plate count) and is never interpreted here.
    """

    id: str
    name: str
    description: str = ""
    available: bool = True
    flags: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "available": self.available,
            "flags": list(self.flags),
            **({"meta": self.meta} if self.meta else {}),
        }


@dataclass(frozen=True)
class _BaseParam:
    id: str
    label: str
    help: str = ""
    group: str = "Design"
    visible_when: Visibility | None = None

    def _common(self) -> dict:
        out = {
            "id": self.id,
            "label": self.label,
            "help": self.help,
            "group": self.group,
        }
        if self.visible_when is not None:
            out["visible_when"] = self.visible_when.to_json()
        return out


@dataclass(frozen=True)
class TextParam(_BaseParam):
    default: str = ""
    min_length: int = 0
    max_length: int = 64
    # Applied client-side for immediate feedback; the server re-applies it.
    pattern: str = ""
    transform: Literal["none", "upper", "lower"] = "none"
    placeholder: str = ""
    # Leading/trailing whitespace is never meaningful in these fields and would
    # otherwise reach the geometry as a glyph.
    strip: bool = True

    def to_json(self) -> dict:
        return {
            **self._common(),
            "kind": "text",
            "default": self.default,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "pattern": self.pattern,
            "transform": self.transform,
            "placeholder": self.placeholder,
            "strip": self.strip,
        }


@dataclass(frozen=True)
class ChoiceParam(_BaseParam):
    options: tuple[Option, ...] = ()
    default: str = ""
    # "cards" for a handful of visual styles, "dropdown" past ~8 options.
    display: Literal["cards", "dropdown"] = "cards"

    def to_json(self) -> dict:
        return {
            **self._common(),
            "kind": "choice",
            "options": [o.to_json() for o in self.options],
            "default": self.default,
            "display": self.display,
        }


@dataclass(frozen=True)
class FilamentParam(_BaseParam):
    """A slot that takes one Bambu Matte palette ID.

    Deliberately not a colour picker: the palette is what the shop can actually
    print. `role` names the part it colours ("stand", "letters") so a product
    can have several slots without the UI guessing.
    """

    default: str = ""
    role: str = "body"

    def to_json(self) -> dict:
        return {
            **self._common(),
            "kind": "filament",
            "default": self.default,
            "role": self.role,
        }


@dataclass(frozen=True)
class BooleanParam(_BaseParam):
    default: bool = False

    def to_json(self) -> dict:
        return {**self._common(), "kind": "boolean", "default": self.default}


@dataclass(frozen=True)
class IntegerParam(_BaseParam):
    default: int = 0
    minimum: int = 0
    maximum: int = 100
    step: int = 1

    def to_json(self) -> dict:
        return {
            **self._common(),
            "kind": "integer",
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
        }


Param = TextParam | ChoiceParam | FilamentParam | BooleanParam | IntegerParam


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldError:
    """A validation failure addressed to a parameter, so the UI can place it."""

    param: str
    message: str
    # Advice the user can act on, when the failure has an obvious remedy
    # ("try a narrower lettering style", "shorten the name").
    hint: str = ""

    def to_json(self) -> dict:
        return {"param": self.param, "message": self.message, "hint": self.hint}


class ValidationError(Exception):
    """Raised by a product's validate() with one or more FieldErrors."""

    def __init__(self, errors: Sequence[FieldError]):
        self.errors = list(errors)
        super().__init__("; ".join(f"{e.param}: {e.message}" for e in self.errors))


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------


class Generator(Protocol):
    """What a product must implement to be designable in the browser."""

    def validate(self, values: dict[str, Any]) -> None:
        """Raise ValidationError if these values cannot be built."""
        ...

    def generate(self, values: dict[str, Any], job_dir) -> dict:
        """Build into job_dir. Return metadata including 'output' (a filename)."""
        ...

    def preview(self, values: dict[str, Any], out_path) -> dict:
        """Optional. Write a role-tagged GLB to out_path; return stats.

        Only the parameters listed in ProductSpec.preview_keys may affect the
        result — see that field. A product without this simply has no 3D view.
        """
        ...


@dataclass(frozen=True)
class ProductSpec:
    """Everything the designer needs to render and run one product."""

    id: str
    name: str
    tagline: str
    description: str
    params: tuple[Param, ...]
    # False = shown in the picker but not designable yet. The spec is still
    # declared, so wiring it later is generator work rather than UI work.
    available: bool = True
    # Optional bespoke panel the web app renders alongside the generic controls
    # (a preview, a fit warning). Unknown ids are ignored, so the backend can
    # ship one before the frontend implements it.
    custom_panels: tuple[str, ...] = ()
    # Rough guidance shown in the picker; from measured slice data where known.
    print_note: str = ""
    # Which parameters actually change the 3D preview's *geometry*.
    #
    # This is the field that makes an on-demand preview affordable. Colour and
    # surface-finish parameters are applied by the viewer at draw time, so a
    # customer can walk the whole palette without rebuilding anything; only a
    # change to one of these invalidates the cached model. Empty means the
    # product has no preview.
    #
    # Getting this wrong is a correctness bug in one direction only: omitting a
    # parameter that does change geometry shows a stale model. Including a
    # colour merely wastes a rebuild.
    preview_keys: tuple[str, ...] = ()
    # Fingerprint of the code that builds the meshes, folded into preview_key.
    #
    # preview_keys covers what the *customer* changed. This covers what *we*
    # changed. Without it a geometry edit invalidates nothing: the cached GLB
    # for (ROCCO, cooper, bold) keeps its key, and since previews are served
    # `immutable, max-age=31536000` the old shape survives on disk and in every
    # browser that has seen it. That is not hypothetical — making the letters
    # flush left the preview showing them still standing 1.6 mm proud.
    #
    # PREVIEW_FORMAT_VERSION does the same job for ogma.preview itself, but it
    # cannot see a product's generator. A product supplies this; empty means the
    # product has opted out and accepts stale previews.
    geometry_version: str = ""
    generator: Generator | None = None

    @property
    def has_preview(self) -> bool:
        return bool(self.preview_keys) and hasattr(self.generator, "preview")

    def preview_key(self, values: dict[str, Any]) -> str:
        """Stable id for the preview these values produce.

        Includes the preview format version, not just the geometry parameters.
        The GLB is served `immutable` for a year, so a key that ignores how the
        file was built pins every returning browser to whatever the pipeline
        produced the first time — see ogma.preview.PREVIEW_FORMAT_VERSION.
        """
        import hashlib
        import json as _json

        from ogma.preview import PREVIEW_FORMAT_VERSION

        payload = _json.dumps(
            {
                "product": self.id,
                "v": PREVIEW_FORMAT_VERSION,
                "geometry": self.geometry_version,
                **{k: values.get(k) for k in self.preview_keys},
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_json(self, *, include_params: bool = True) -> dict:
        out = {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "description": self.description,
            "available": self.available,
            "custom_panels": list(self.custom_panels),
            "print_note": self.print_note,
        }
        out["has_preview"] = self.has_preview
        if include_params:
            out["preview_keys"] = list(self.preview_keys)
            out["params"] = [p.to_json() for p in self.params]
            out["groups"] = list(dict.fromkeys(p.group for p in self.params))
        return out

    def defaults(self) -> dict[str, Any]:
        return {p.id: getattr(p, "default") for p in self.params}

    def check_declared(self, values: dict[str, Any]) -> list[FieldError]:
        """Enforce the constraints the spec itself declares.

        The UI checks these as you type (maxLength, pattern), but a browser is
        not a gate — anything can POST to the API. Running them server-side is
        what makes `max_length` a rule rather than a hint, and it means a
        product's own validate() can assume the cheap constraints already hold
        and concentrate on the ones only it knows (geometry, packing, fit).
        """
        errors: list[FieldError] = []
        for p in self.params:
            v = values.get(p.id)
            if isinstance(p, TextParam):
                s = str(v or "")
                if len(s) < p.min_length or len(s) > p.max_length:
                    errors.append(
                        FieldError(
                            p.id,
                            f"Use between {p.min_length} and {p.max_length} characters.",
                        )
                    )
                elif p.pattern and not re.fullmatch(p.pattern, s):
                    errors.append(FieldError(p.id, "That contains characters we can't print."))
            elif isinstance(p, ChoiceParam):
                match = next((o for o in p.options if o.id == str(v)), None)
                if match is None:
                    errors.append(FieldError(p.id, f"Unknown option {v!r}."))
                elif not match.available:
                    errors.append(FieldError(p.id, f"{match.name} is not available yet."))
            elif isinstance(p, FilamentParam):
                # The palette is the constraint, and it lives in this same
                # package — so this belongs here rather than in every product.
                # Without it an unknown id validated clean and then raised
                # `Unknown filament` deep in the build, turning a typo into a
                # failed job with a stack trace instead of a message on the
                # colour control.
                try:
                    resolve_filament(str(v), load_palette())
                except (ValueError, KeyError):
                    errors.append(
                        FieldError(p.id, f"{v!r} is not a colour we stock.")
                    )
            elif isinstance(p, IntegerParam):
                try:
                    n = int(v)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    errors.append(FieldError(p.id, "Must be a whole number."))
                    continue
                if not (p.minimum <= n <= p.maximum):
                    errors.append(
                        FieldError(p.id, f"Must be between {p.minimum} and {p.maximum}.")
                    )
        return errors

    def param(self, param_id: str) -> Param:
        for p in self.params:
            if p.id == param_id:
                return p
        raise KeyError(param_id)

    def coerce(self, values: dict[str, Any]) -> dict[str, Any]:
        """Fill defaults, drop unknown keys, apply text transforms.

        Runs before validate() so a product's validator only ever sees a
        complete, typed dict — not whatever the browser happened to post.

        Coercion normalises; it must never change what the customer asked for.
        Text is *not* truncated to max_length: an over-long name is a
        validation failure the customer must see, not something to silently
        shorten. (This once let POST name="WILLIAMSON" return ok with
        name="WILLIAMS" — on a personalised product, that ships the wrong
        item.) Integers are clamped because a slider cannot express intent
        outside its own range; a text field can.
        """
        out = self.defaults()
        for p in self.params:
            if p.id not in values or values[p.id] is None:
                continue
            v = values[p.id]
            if isinstance(p, TextParam):
                v = str(v)
                if p.strip:
                    v = v.strip()
                if p.transform == "upper":
                    v = v.upper()
                elif p.transform == "lower":
                    v = v.lower()
            elif isinstance(p, BooleanParam):
                v = bool(v)
            elif isinstance(p, IntegerParam):
                v = max(p.minimum, min(p.maximum, int(v)))
            else:
                v = str(v)
            out[p.id] = v
        return out


class ProductRegistry:
    """The catalogue the studio API serves.

    Products register themselves here; the registry knows nothing about any of
    them beyond the spec they hand over.
    """

    def __init__(self) -> None:
        self._specs: dict[str, ProductSpec] = {}

    def register(self, spec: ProductSpec) -> ProductSpec:
        if spec.id in self._specs:
            raise RuntimeError(f"duplicate product id {spec.id!r}")
        self._specs[spec.id] = spec
        return spec

    def get(self, product_id: str) -> ProductSpec:
        if product_id not in self._specs:
            raise KeyError(product_id)
        return self._specs[product_id]

    def all(self) -> tuple[ProductSpec, ...]:
        return tuple(self._specs.values())

    def catalog(self) -> list[dict]:
        return [s.to_json(include_params=False) for s in self._specs.values()]
