# Ogma Print Studio — dog bowl

A parametric generator that turns design parameters into print-ready Bambu
Studio `.3mf` projects, with a web configurator in front of it.

| Product | What it is | Where to start |
|---|---|---|
| **[dog-bowl](products/dog-bowl/)** | Named dog bowl stand configurator — 4 styles, FastAPI + Next.js | [STATUS](products/dog-bowl/STATUS.md) · [AGENTS](products/dog-bowl/AGENTS.md) |

This repo used to carry five products. On 2026-08-13 the other four — clickers,
lamps, Oggie Spin and the Squspi ball — moved to `_other-products/`, on their way
to a repo of their own. See [`_other-products/MIGRATION.md`](_other-products/MIGRATION.md).

The split was clean because of the seam work that preceded it: nothing outside
`products/` imported a product, and no product imported another. The toolkit is
still built to that rule.

## Layout

```
shared/ogma/        the toolkit — knows nothing about any product
  filaments.py      Bambu Matte palette lookup
  bambu_project.py  mesh list -> painted, plated .3mf
  paint.py          fuzzy-skin triangle painting (FuzzyPainter protocol)
  printability.py   slicer-style layer audit — anchor ratio, not distance
  geom.py assets.py fonts/ palette.json bambu/
products/dog-bowl/
  generator/        the parametric design + the style registry
  coupons/          physical fit-test generators
  designer.py       the configurator spec the studio renders from
  assets/           style thumbnails, rendered from the real meshes
  design/           concept sheets, renders, shipped packages
studio/
  api/              FastAPI — product-agnostic, composes the catalogue
  web/              Next.js configurator — no product knowledge in it
tests/              goldens.py, smoke_imports.py, audit_3mf.py, test_name_fit.py
out/                job output (gitignored)
_other-products/    on its way out — see MIGRATION.md
```

`products` depend on `shared`. `shared` depends on nothing of ours — that
direction is enforced by `tests/smoke_imports.py`, and it is what made the
2026-08-13 split a move rather than an untangling.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# generate a bowl
.venv/bin/python products/dog-bowl/generator/pipeline.py \
  --name MAX --style cooper --out out/max

# API + web together — installs anything missing, refuses a busy port
make dev            # API on :8000, configurator on :3000
```

`make api` and `make web` run the two halves separately if you need them apart.

## Before you change anything

```bash
make pytest                                        # 46 unit tests, ~17 s
.venv/bin/python tests/smoke_imports.py            # all generators still import

# geometry regression check, against the committed baseline
.venv/bin/python tests/goldens.py /tmp/g.json /tmp/j
.venv/bin/python tests/golden_compare.py tests/goldens-baseline.json /tmp/g.json
```

`goldens.py` fingerprints mesh volume/area/triangles/bounds/watertight plus a
sha256 of every member file inside each exported 3MF. `golden_compare.py` diffs
two of those with tolerances, because the geometry kernels are not
bit-reproducible across versions.

The tolerances are measured. Running all five cases on macOS/trimesh 4.12.2
against Linux/trimesh 5.0.0, **four of five are identical in every byte**; only
`wave` moves, and only in its boolean-heavy path:

| | worst drift |
|---|---|
| volume | 1.21e-05 relative |
| area | 3.60e-05 relative |
| triangles | 2.59e-02 relative |
| bounds | 4.00e-05 mm |

Watertightness and the set of parts never move, and are compared exactly.

This refines the older note that "volume holds to 7 decimal places". That is
true where it was originally measured — the wave *upper*, which agrees to about
1.7e-12 relative — but it does not generalise. The cone-backed *letters* on the
same style hold to roughly five significant decimals (183.226106 → 183.223887
mm³). That is 0.002 mm³ on a letter, far below what a 0.1 mm layer can express,
so it is a reporting correction rather than a defect — but a comparison written
to 7dp would have failed on it.
