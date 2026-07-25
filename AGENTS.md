# Agent / future session guide — ogma-print-dog-bowl

Read this at the start of any coding session on this repo. Prefer facts here over chat memory.

## Product in one line

Custom **paw-lattice dog bowl stand** configurator: name + Bambu Matte PLA colours → Bambu Studio `.3mf`.

## Canonical docs

| File                                                     | Use                                        |
| -------------------------------------------------------- | ------------------------------------------ |
| [PROJECT_STATUS.md](./PROJECT_STATUS.md)                 | Phase tracker, decisions, gaps, next steps |
| [README.md](./README.md)                                 | Local run + API overview                   |
| [.env.example](./.env.example)                           | Env contract (local + Railway)             |
| [county-clickers/README.md](./county-clickers/README.md) | Standalone 32-county clicker package       |

Sibling design sandbox (not this repo): `Documents/Ogma Print Files` — original Cooper meshes / print experiments.

Sibling product for Railway/filament patterns: `ogma-print-core`.

The standalone county-clicker side product is packaged under
`county-clickers/`. Its production generator remains
`backend/generator/county_clicker.py` so it can reuse the established MX and
3MF utilities. County clickers are individual handheld pieces, not
tessellating map tiles.

## Architecture (do not invent a parallel stack)

- **Local-first + Railway** — same codepaths; config via env only
- **FastAPI** (`backend/app`) — jobs on disk under `data/jobs/`
- **Generator** (`backend/generator/pipeline.py`) — calls design → STLs → `build_project` → painted 3MF
- **Next.js** (`web`) — rewrites `/api/v1/*` to `PIPELINE_API_URL`

Do **not** rewrite geometry in JavaScript. Do **not** add free hex colour pickers — Matte palette IDs only.

## Key entry points

```text
backend/generator/pipeline.py          # generate(name, job_dir, font_style, stand/letter filament ids)
backend/generator/cooper_bowl_design.py
backend/generator/wave_bowl_design.py
backend/generator/hex_bowl_design.py
backend/generator/wave_fit_test.py
backend/generator/build_bambu_project.py
backend/generator/paint_fuzzy_skin.py
backend/app/api/bowl.py
backend/app/services/jobs.py
web/src/app/page.tsx
backend/data/filament_palette.json
```

## Local commands

```bash
cp .env.example .env
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd web && npm install && cd ..

# API (from backend/)
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Web
cd web && PIPELINE_API_URL=http://127.0.0.1:8000 npm run dev

# CLI
.venv/bin/python backend/generator/pipeline.py --name MAX --out data/jobs/cli-max
```

Or `bash scripts/dev.sh`.

## Constraints to respect

- Name: 2–8 letters A–Z; packing must stay within `MAX_RAIL_OUTER_DEG` (45°)
- Letter styles: `bold` (Overpass) | `clean` (Source Sans) | `serif` (Lora) | `slab` (Roboto Slab) | `rounded` (Fredoka) | `playful` (Baloo 2) | `condensed` (Barlow Condensed)
- Filaments: IDs from `filament_palette.json` (Matte)
- Panel fuzzy paint: outer wall fuzzy; **exclude** paw silhouettes and name-rail plaque
- Letters: pocket fit + curved backs — no pin/socket regression
- Object id hygiene in 3MF: `object_N.model` ↔ local id `N` only
- Hex means the solid recessed-honeycomb drum; do not restore the open lattice or foot ring
- Honeycomb: keep the 4 mm hollow wall, 1 mm groove depth, ≥3 mm remaining web, and ≤45° seat ramp
- Honeycomb uses whole-cell suppression around the name; do not restore the long fade that produced ghost hexagons
- Honeycomb radial/Z profiles must be simple positive-area polygons before wrapping
- Honeycomb keeps 5 mm pattern-free edge bands with shallow border rings and 0.45 mm external bevels
- Wave: collar is a hollow 2.4 mm annulus rooted to the bed — never a solid cylinder
- Wave collar outer radius is 74 mm; the continuous upper receiver inner radius is 74.5 mm
- Wave sleeve clearance is locked at 0.5 mm/side after the revised R74/R74.5 coupon seated snugly with minimal wobble and easy hand separation
- Wave halves must use continuous wrapped profiles; per-sector boolean slabs create vertical wall grooves
- Reject any Wave radial/Z profile that is not a simple positive-area polygon
- Wave upper keeps ≥4 mm wall through the lettering zone; do not let its support bridge cross the exterior
- Wave bowl seat is a separate inverted-printing insert: R71.53 locator in the R71.83 shell opening, with its flange resting on the top rim
- Wave 3MFs use avoid-crossing-wall travel, unlimited detours, 0.8 mm / 30 mm/s retraction, layer-change retraction, and 2 mm wipe
- Wave has no name plaque: cut glyph pockets directly into the upper cone and use matching conical letter backs
- Wave letters sit on a large (low-seam) lobe, vertically centred between that seam and the shell top
- Wave upper uses critical-regions-only normal support for pocket-closing layers; remove it before fitting letters
- Use `wave_letter_test.py` to validate real cone pockets and letter backs before a full Wave print

## When changing the design

1. Edit `cooper_bowl_design.py` / paint / build
2. Run CLI generate for a short name (`MAX`) and a wide/long case
3. Open 3MF in Bambu Studio — check pockets, fuzzy, filaments
4. Update `PROJECT_STATUS.md` if a phase or decision changed

## Railway notes (from ogma-print-core lessons)

- Backend listens on `$PORT` (often 8080)
- Web must not hardcode `localhost` for downloads — use proxy / `PIPELINE_API_URL`
- Services do not share filesystem — plan volume or S3 for `JOBS_ROOT`
- Prefer Dockerfile builds over Nixpacks for the storefront

## What not to do

- Don’t commit `.env`, `.venv`, `node_modules`, or `data/jobs/*` outputs
- Don’t reintroduce letter pins or modifier-based fuzzy blockers
- Don’t expand scope to checkout until MVP generate/download is solid on Railway
