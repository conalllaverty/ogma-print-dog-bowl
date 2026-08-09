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

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol, Sequence

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
    # ("try a condensed font", "shorten the name").
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
    generator: Generator | None = None

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
        if include_params:
            out["params"] = [p.to_json() for p in self.params]
            out["groups"] = list(dict.fromkeys(p.group for p in self.params))
        return out

    def defaults(self) -> dict[str, Any]:
        return {p.id: getattr(p, "default") for p in self.params}

    def param(self, param_id: str) -> Param:
        for p in self.params:
            if p.id == param_id:
                return p
        raise KeyError(param_id)

    def coerce(self, values: dict[str, Any]) -> dict[str, Any]:
        """Fill defaults, drop unknown keys, apply text transforms.

        Runs before validate() so a product's validator only ever sees a
        complete, typed dict — not whatever the browser happened to post.
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
                v = v[: p.max_length]
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
