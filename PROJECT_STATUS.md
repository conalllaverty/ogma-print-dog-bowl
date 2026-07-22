# Ogma Print — Dog Bowl Project Status

**Repo:** https://github.com/conalllaverty/ogma-print-dog-bowl  
**Local path:** `/Users/conalllaverty/Documents/GitHub/ogma-print-dog-bowl`  
**Last updated:** 2026-07-22  
**Status:** Local MVP scaffold — generator + API + web UI working; Railway deploy not yet done

---

## What this product is

A configurator for the **paw-lattice dog bowl stand** (Bambu Lab P2S):

1. User enters a dog name (2–8 letters A–Z)
2. Picks letter style + two **Bambu Lab PLA Matte** colours
3. Generates a 4-plate print-ready `.3mf` (base, panel, top ring, letters)
4. Downloads and prints / assembles

Geometry comes from the parametric Python pipeline (recessed paw pads, letter **pockets** with curved backs, fuzzy-skin paint on the panel with smooth paws + name rail).

Companion / design origin lived in `Documents/Ogma Print Files` (`cooper_bowl_design.py` lineage). This repo is the productised app.

Related product: [`ogma-print-core`](https://github.com/conalllaverty/ogma-print-core) (map tiles) — reuse its Railway + Matte filament patterns.

---

## Phase tracker

| Phase | Status | Notes |
|-------|--------|-------|
| 0 — Parameterised generator | **Done** | `name`, `font_style`, Matte IDs, fit gate (±45°), fuzzy on/off |
| 1 — Local FastAPI + Next.js | **Done** | Generate → poll → download 3MF verified (`MAX`, `REX`) |
| 1b — Hybrid GLB preview | Not started | Client mock only in UI today |
| 2 — Railway deploy | Not started | Dockerfiles present; need services + volume for jobs |
| 2b — Filament stock / allow-lists | Not started | Optional; core already has this |
| 3 — Commerce / checkout | Not started | Deferred auth pattern from core if needed |

---

## Locked product decisions

| Topic | Decision |
|-------|----------|
| Max name | **8** characters + packing fit gate |
| Colours | **Bambu PLA Matte only** (`backend/data/filament_palette.json`) |
| Letter styles | `bold` (Arial Bold), `rounded` (Arial Rounded), `condensed` (Oswald Bold) |
| Letter mount | Shallow **glyph pockets** + concave cylindrical backs (no pins) |
| Fuzzy | Default on; paws + name-rail plaque unpainted |
| Hosting | Railway (same dual local/prod contract as core) |
| Auth | Anonymous for MVP |

---

## Repo layout

```
backend/
  app/                 FastAPI (health, filaments, generate, jobs, download)
  generator/           cooper_bowl_design + build_bambu_project + paint + pipeline
  data/filament_palette.json
  assets/fonts/        bold / rounded / condensed TTFs
  Dockerfile + railway.json
web/                   Next.js configurator (proxies /api/v1 → PIPELINE_API_URL)
data/jobs/             Job output (gitignored contents)
scripts/dev.sh
Makefile
README.md
PROJECT_STATUS.md      ← this file
AGENTS.md              ← instructions for future AI/human sessions
```

---

## Verified working

- CLI: `pipeline.py --name MAX …` → `MAX_Paw_Lattice_P2S.3mf`
- API: `POST /api/v1/bowl/generate` → job succeeds → `download.3mf`
- Matte palette: 25 filaments exposed via `GET /api/v1/filaments`

---

## Known gaps / risks

1. **Preview** is a CSS mock, not real GLB geometry  
2. **Arial fonts** in `assets/fonts` are not OFL — Docker falls back toward Liberation; prefer shipping only OFL fonts long-term  
3. **Job storage** is local disk / in-process threads — fine locally; Railway needs a volume or object storage + possibly a worker  
4. **No automated tests** yet  
5. Condensed style helps long names; packing still rejects if rail > ±45°  
6. Original design assets / print notes also live under `Ogma Print Files/cooper_dog_bowl/`

---

## Immediate next steps (priority)

1. Confirm fonts + `.gitignore` are acceptable for a public GitHub repo  
2. Add `preview.glb` export from generator; show in web viewer  
3. Deploy backend + web on Railway; set `PIPELINE_API_URL`, `JOBS_ROOT`, CORS  
4. Smoke-test a generated 3MF in Bambu Studio (pockets, fuzzy paint, filament colours)  
5. Optional: share filament palette / stock API with `ogma-print-core`
