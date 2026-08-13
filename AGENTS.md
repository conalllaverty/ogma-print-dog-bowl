# Session guide — ogma-print-studio

Read the product's own `AGENTS.md` before touching it. This file is house rules
only.

| Product | Guide |
|---|---|
| dog-bowl | [products/dog-bowl/AGENTS.md](products/dog-bowl/AGENTS.md) |

The clickers, lamps, Oggie Spin and Squspi ball moved to `_other-products/` on
2026-08-13 and are leaving for their own repo. Do not build on them from here —
see [`_other-products/MIGRATION.md`](_other-products/MIGRATION.md).

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
- **Same-named helpers are not interchangeable.** This rule existed because
  `_union` and `_difference` were each defined five times across the products
  with four distinct behaviours. All ten definitions left with the products on
  2026-08-13; the bowl uses `boolean_union` / `boolean_difference`, defined once
  in `cooper_bowl_design.py`. Keep the rule in mind if a product ever returns —
  it still applies over in `_other-products/`.
- **Numbers come from code, not prose.** Force figures, clearances and volumes
  get derived in a function and asserted, never quoted from a previous doc.
- **Bambu Matte palette IDs only** — no free hex colour pickers.
- **Don't rewrite geometry in JavaScript.** The web app is a configurator.

## Adding a bowl style

One file: `products/dog-bowl/generator/styles/<id>.py` exposing
`STYLE = BowlStyle(...)`, plus one line in `styles/__init__._MODULES`. The API
catalogue, the CLI `--style` choices and the web configurator all derive from
the registry.
