# Ogma Print Studio

Parametric generators that turn design parameters into print-ready Bambu Studio
`.3mf` projects. One repo, several products, one shared toolkit.

| Product | What it is | Where to start |
|---|---|---|
| **[dog-bowl](products/dog-bowl/)** | Named dog bowl stand configurator — 3 styles, FastAPI + Next.js | [STATUS](products/dog-bowl/STATUS.md) · [AGENTS](products/dog-bowl/AGENTS.md) |
| **[clickers](products/clickers/)** | 32 Irish county MX-switch clickers + salmon nigiri clicker | [county README](products/clickers/county-package/README.md) |
| **[lamps](products/lamps/)** | Bouclé Stack and Golf Tee, both on the Bambu LED Kit 001 | [STATUS](products/lamps/STATUS.md) |
| **[oggie-spin](products/oggie-spin/)** | Modular fidget spinner, Broken Ring Illusion | [STATUS](products/oggie-spin/STATUS.md) · [AGENTS](products/oggie-spin/AGENTS.md) |
| **[squspi-ball](products/squspi-ball/)** | Squspi ball reconstruction + twin-rail review | — |

Only the dog bowl has a web front end. Everything else is CLI-generated.

## Layout

```
shared/ogma/        the toolkit — knows nothing about any product
  filaments.py      Bambu Matte palette lookup
  bambu_project.py  mesh list -> painted, plated .3mf
  paint.py          fuzzy-skin triangle painting (FuzzyPainter protocol)
  printability.py   slicer-style layer audit — anchor ratio, not distance
  geom.py assets.py fonts/ palette.json bambu/
products/<name>/
  generator/        the parametric design
  coupons/          physical fit-test generators (dog bowl)
  app/ web/         API + configurator (dog bowl only)
  design/           concept sheets, renders, shipped packages
tests/              goldens.py, smoke_imports.py
out/                job output (gitignored)
```

`products` depend on `shared`. `shared` depends on nothing of ours — that
direction is enforced by `tests/smoke_imports.py` and is the reason a lamp no
longer imports the dog bowl.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# generate a bowl
.venv/bin/python products/dog-bowl/generator/pipeline.py \
  --name MAX --style cooper --out out/max

# API + web
cd products/dog-bowl && ../../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
cd products/dog-bowl/web && PIPELINE_API_URL=http://127.0.0.1:8000 npm run dev
```

## Before you change anything

```bash
.venv/bin/python tests/smoke_imports.py            # all generators still import
.venv/bin/python tests/goldens.py after.json /tmp/j  # then diff against a baseline
```

`goldens.py` fingerprints mesh volume/area/triangles/bounds/watertight plus a
sha256 of every member file inside each exported 3MF. Assert on **volume**, not
triangle count — trimesh versions shift counts ~1% while volume holds to 7dp.
