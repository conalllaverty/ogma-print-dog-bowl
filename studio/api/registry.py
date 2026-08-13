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

from ogma.designer import ProductRegistry  # noqa: E402

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


# There used to be two "coming soon" entries here — a lamp and Oggie Spin —
# declared inline so the picker could show the range before either had a
# generator. Both products now live outside this repo, under `_other-products/`,
# so advertising them would promise a designer that nothing here can ever build.
#
# If one comes back, it returns the way the spec intends: a `designer.py` in its
# own product directory and one entry in the loop above. A placeholder declared
# here is not a step towards that — it is a second place to keep in sync.
