"""Bowl style registry — the Fusion mirror of generator/styles/__init__.py.

Adding a style is the same one-file job it is on the Python side: write
styles/<id>.py exposing STYLE_ID, LABEL, OUTPUT_SUFFIX and build(component,
ctx), then add the module name to _MODULES. The command dialog's style list,
the batch exporter and the parameter tables all derive from what is registered
here.

Order is the order the user sees in the dialog.
"""

from __future__ import annotations

from importlib import import_module

_MODULES = ("cooper", "wave", "hex", "fluted")

_REGISTRY = {}
for _name in _MODULES:
    _module = import_module("{}.{}".format(__name__, _name))
    if _module.STYLE_ID in _REGISTRY:
        raise RuntimeError("duplicate bowl style id {!r}".format(_module.STYLE_ID))
    _REGISTRY[_module.STYLE_ID] = _module

STYLE_IDS = tuple(_REGISTRY)
DEFAULT_STYLE = STYLE_IDS[0]


def get(style_id: str):
    key = (style_id or "").lower().strip()
    if key not in _REGISTRY:
        raise ValueError(
            "Unknown bowl style {!r}. Choose from {}.".format(
                style_id, list(STYLE_IDS))
        )
    return _REGISTRY[key]


def all_styles():
    return tuple(_REGISTRY.values())


def labels():
    return [(m.STYLE_ID, m.LABEL) for m in _REGISTRY.values()]
