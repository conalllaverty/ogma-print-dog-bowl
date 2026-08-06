"""Bowl style registry.

To add a style: write styles/<id>.py exposing a `STYLE = BowlStyle(...)`, then
add it to _MODULES below. Nothing else needs editing — geometry_config's
STYLE_META, the API's STYLE_CATALOG and the web configurator's style list all
derive from what is registered here.

Order is the order the user sees in the configurator.
"""
from __future__ import annotations

from importlib import import_module

from .base import BowlStyle, StyleImpl

_MODULES = ("cooper", "wave", "hex")

_REGISTRY: dict[str, BowlStyle] = {}
for _m in _MODULES:
    _style = import_module(f"{__name__}.{_m}").STYLE
    if _style.id in _REGISTRY:
        raise RuntimeError(f"duplicate bowl style id {_style.id!r}")
    _REGISTRY[_style.id] = _style

STYLES: tuple[str, ...] = tuple(_REGISTRY)
DEFAULT_STYLE = STYLES[0]


def get(style_id: str) -> BowlStyle:
    key = (style_id or "").lower().strip()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown style '{style_id}'. Choose from {list(STYLES)}")
    return _REGISTRY[key]


def all_styles() -> tuple[BowlStyle, ...]:
    return tuple(_REGISTRY.values())


def meta() -> dict[str, dict]:
    return {s.id: s.meta() for s in _REGISTRY.values()}


def catalog() -> list[dict]:
    return [s.catalog_entry() for s in _REGISTRY.values()]


__all__ = ["BowlStyle", "StyleImpl", "STYLES", "DEFAULT_STYLE",
           "get", "all_styles", "meta", "catalog"]
