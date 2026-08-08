# Session guide — ogma-print-studio

Read the product's own `AGENTS.md` before touching it. This file is house rules
only.

| Product | Guide |
|---|---|
| dog-bowl | [products/dog-bowl/AGENTS.md](products/dog-bowl/AGENTS.md) |
| oggie-spin | [products/oggie-spin/AGENTS.md](products/oggie-spin/AGENTS.md) |
| lamps | [products/lamps/STATUS.md](products/lamps/STATUS.md) |
| clickers | [products/clickers/county-package/DEVELOPMENT.md](products/clickers/county-package/DEVELOPMENT.md) |

Plan of record: [OGMA-PRINT-STUDIO-PLAN.md](OGMA-PRINT-STUDIO-PLAN.md).

## House rules

- **`shared/ogma` must not import any product.** Products depend on shared, never
  the reverse. If shared needs product knowledge, invert it — pass a protocol
  object in, the way `bambu_project.build_project()` takes a `FuzzyPainter`.
- **Run `tests/goldens.py` before and after any refactor** and diff the JSON. It
  is what proved the seam cuts and the restructure byte-neutral.
- **Every printed part must clear `shared/ogma/printability.py`.** It sections a
  mesh at every layer height and diffs each footprint against the one below, the
  way a slicer does. Geometric validators here compare a model to itself and are
  blind to anything that only exists once a part is oriented on a bed.
- **Verify against the artifact, not the model.** A "flip" written as a −1 axis
  scale is a *reflection*: self-consistent, every interference check still
  passes, and the exported part is a mirror image. That shipped once. Route
  orientation changes through `printability.assert_rigid()`.
- **Same-named helpers are not interchangeable.** `_union` and `_difference` are
  each defined five times across the products with four distinct behaviours.
  Do not consolidate them without per-product goldens.
- **Numbers come from code, not prose.** Force figures, clearances and volumes
  get derived in a function and asserted, never quoted from a previous doc.
- **Bambu Matte palette IDs only** — no free hex colour pickers.
- **Don't rewrite geometry in JavaScript.** The web app is a configurator.

## Adding a bowl style

One file: `products/dog-bowl/generator/styles/<id>.py` exposing
`STYLE = BowlStyle(...)`, plus one line in `styles/__init__._MODULES`. The API
catalogue, the CLI `--style` choices and the web configurator all derive from
the registry.
