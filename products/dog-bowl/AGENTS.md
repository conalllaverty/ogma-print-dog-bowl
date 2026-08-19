# Dog bowl — session guide

<!-- Split out of the monolithic root PROJECT_STATUS.md / AGENTS.md on 2026-08-06.
     Content is verbatim: the constraint lists here were earned from physical
     prints and must not be paraphrased. -->

## Product in one line


Custom **paw-lattice dog bowl stand** configurator: name + Bambu Matte PLA colours → Bambu Studio `.3mf`.


## Architecture


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


## Constraints to respect


- Name: 2–8 letters, either case, set as typed; packing must stay within `MAX_RAIL_OUTER_DEG` (45°)
- Letter styles: `bold` (Overpass) | `clean` (Source Sans) | `serif` (Lora) | `slab` (Roboto Slab) | `rounded` (Fredoka) | `playful` (Baloo 2)
- Filaments: IDs from `filament_palette.json` (Matte)
- Panel fuzzy paint: outer wall fuzzy; **exclude** paw silhouettes and name-rail plaque
- Letters: pocket fit + curved backs — no pin/socket regression
- Object id hygiene in 3MF: `object_N.model` ↔ local id `N` only
- Hex means the solid recessed-honeycomb drum; do not restore the open lattice or foot ring
- Honeycomb: keep the 4 mm hollow wall, 1 mm groove depth, ≥3 mm remaining web, and ≤45° seat ramp
- Honeycomb uses whole-cell suppression around the name; do not restore the long fade that produced ghost hexagons
- Honeycomb keepout derives from the packed glyph envelope with a 1.5 mm margin; do not restore the oversized fixed name field
- Honeycomb radial/Z profiles must be simple positive-area polygons before wrapping
- Honeycomb keeps 5 mm pattern-free edge bands, a 0.45 mm top bead, and a 0.35 mm inward bottom chamfer
- Honeycomb name is optically centred at Z37 within the staggered cell keepout; the safer internal support ramp starts at Z58
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


## When changing the design


1. Edit `cooper_bowl_design.py` / paint / build
2. Run CLI generate for a short name (`MAX`) and a wide/long case
3. Open 3MF in Bambu Studio — check pockets, fuzzy, filaments
4. Update `PROJECT_STATUS.md` if a phase or decision changed


## Railway notes


- Backend listens on `$PORT` (often 8080)
- Web must not hardcode `localhost` for downloads — use proxy / `PIPELINE_API_URL`
- Services do not share filesystem — plan volume or S3 for `JOBS_ROOT`
- Prefer Dockerfile builds over Nixpacks for the storefront


## What not to do


- Don’t commit `.env`, `.venv`, `node_modules`, or `data/jobs/*` outputs
- Don’t reintroduce letter pins or modifier-based fuzzy blockers
- Don’t expand scope to checkout until MVP generate/download is solid on Railway
