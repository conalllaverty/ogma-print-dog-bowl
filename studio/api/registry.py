"""The studio's product catalogue.

This is the one place that knows which products exist. `shared/ogma` must not
import products, and no product should import another — so the composition
happens here, at the app layer: shared <- products <- studio.

Adding a product to the designer is one import plus one register() call.
"""

from __future__ import annotations

import sys
from pathlib import Path

STUDIO_DIR = Path(__file__).resolve().parent.parent
REPO = STUDIO_DIR.parent
PRODUCTS = REPO / "products"

for _p in (REPO / "shared",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ogma.designer import ProductRegistry, ProductSpec  # noqa: E402

REGISTRY = ProductRegistry()


def _load(product_dir: str):
    """Import <product>/designer.py under its own sys.path entry.

    Products keep flat intra-product imports (`import cooper_bowl_design`), so
    each needs its own directory on the path. Importing by file location rather
    than package name keeps that working without turning every product into an
    installable package.
    """
    import importlib.util

    path = PRODUCTS / product_dir / "designer.py"
    if not path.is_file():
        return None
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"{product_dir}_designer", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SPEC


# Live products — these have a generator wired up.
for _dir in ("dog-bowl",):
    _spec = _load(_dir)
    if _spec is not None:
        REGISTRY.register(_spec)


# Declared but not yet designable. They appear in the picker so the range is
# visible, and each carries a real spec, so wiring one later is generator work
# rather than UI work.
REGISTRY.register(
    ProductSpec(
        id="lamp",
        name="Solas lamp",
        tagline="Light, shaped.",
        description=(
            "Parametric shades for the Bambu LED Kit 001. Two designs exist as "
            "print packages today; the configurator is not wired up yet."
        ),
        params=(),
        available=False,
        print_note="8 plates · not yet configurable",
    )
)
REGISTRY.register(
    ProductSpec(
        id="oggie-spin",
        name="Oggie Spin",
        tagline="Broken Ring Illusion.",
        description=(
            "Modular fidget spinner with swappable colour arms. Printed and "
            "working; the configurator is not wired up yet."
        ),
        params=(),
        available=False,
        print_note="9 plates · not yet configurable",
    )
)
