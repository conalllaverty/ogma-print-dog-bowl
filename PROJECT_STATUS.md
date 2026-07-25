# Ogma Print — Dog Bowl Project Status

**Repo:** https://github.com/conalllaverty/ogma-print-dog-bowl  
**Local path:** `/Users/conalllaverty/Documents/GitHub/ogma-print-dog-bowl`  
**Last updated:** 2026-07-24
**Status:** Local MVP — Cooper, Wave, and solid Honeycomb styles generating

---

## What this product is

A configurator for elevated dog-bowl stands (Bambu Lab P2S) that all seat the **same Cooper metal bowl** (Ø140 rim family):

1. User enters a dog name (2–8 letters A–Z)
2. Picks **stand style** (paw lattice · wave · honeycomb) + letter style + Matte colours
3. Generates a print-ready `.3mf`
4. Downloads and prints / assembles

| Style    | Status               | 3MF                                              |
| -------- | -------------------- | ------------------------------------------------ |
| `cooper` | **Live**             | 4 plates — base · paw panel · top ring · letters |
| `wave`   | **Live (first cut)** | 4 plates — lower · upper shell · seat · letters  |
| `hex`    | **Live (first cut)** | 2 plates — solid honeycomb body · letters        |

Bowl size is locked to Cooper’s insert — no multi-rim presets for now.

Companion / design origin lived in `Documents/Ogma Print Files` (`cooper_bowl_design.py` lineage). This repo is the productised app.

Related product: [`ogma-print-core`](https://github.com/conalllaverty/ogma-print-core) (map tiles) — reuse its Railway + Matte filament patterns.

---

## Phase tracker

| Phase                             | Status      | Notes                                                          |
| --------------------------------- | ----------- | -------------------------------------------------------------- |
| 0 — Parameterised generator       | **Done**    | `name`, `font_style`, Matte IDs, fit gate (±45°), fuzzy on/off |
| 1 — Local FastAPI + Next.js       | **Done**    | Generate → poll → download 3MF verified (`MAX`, `REX`)         |
| 1b — Hybrid GLB preview           | Not started | Client mock only in UI today                                   |
| 2 — Railway deploy                | Not started | Dockerfiles present; need services + volume for jobs           |
| 2b — Filament stock / allow-lists | Not started | Optional; core already has this                                |
| 3 — Commerce / checkout           | Not started | Deferred auth pattern from core if needed                      |

---

## Locked product decisions

| Topic               | Decision                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------------- |
| Max name            | **8** characters + packing fit gate                                                               |
| Colours             | **Bambu PLA Matte only** (`backend/data/filament_palette.json`)                                   |
| Letter styles       | `bold` = **Overpass Bold** (default), `clean`, `serif`, `slab`, `rounded`, `playful`, `condensed` |
| Letter size         | Height **15 mm**, proud **1.4 mm**, pocket clearance **0.10 mm**                                  |
| Letter print        | **0.10 mm** layers, slower outer walls                                                            |
| Letter mount        | Shallow **glyph pockets**, no pins; Wave mounts directly to its cone with matching conical backs  |
| Fuzzy               | Default on; paws + name-rail plaque unpainted                                                     |
| Honeycomb structure | 4 mm hollow wall; 1 mm grooves leave ≥3 mm web; ≤45° inner seat ramp                              |
| Wave collar         | Hollow 2.4 mm annulus at R74; **0.5 mm/side physically passed** on P2S, 2026-07-23                |
| Hosting             | Railway (same dual local/prod contract as core)                                                   |
| Auth                | Anonymous for MVP                                                                                 |

---

## Repo layout

```
backend/
  app/                 FastAPI (health, filaments, generate, jobs, download)
  generator/           cooper_bowl_design + build_bambu_project + paint + pipeline
  data/filament_palette.json
  assets/fonts/        bundled open-license production fonts + license texts
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
- Wave CLI: `--style wave` → 4-plate lower / upper shell / seat insert / letters project
- Honeycomb CLI: `--style hex` → 2-plate solid body / letters project
- API: `POST /api/v1/bowl/generate` → job succeeds → `download.3mf`
- Matte palette: 25 filaments exposed via `GET /api/v1/filaments`

Honeycomb generated outputs were topology-checked for `MAX`, `LUNA`, and wide
8-letter `WILLIAMS`. The wall is continuous: 1.0 mm recessed grooves leave
proud hex tiles around a whole-cell smooth letter area. The 208-row /
1056-section surface removes the old stair-stepped groove edges, while complete
boundary cells replace the former 12 mm field of broken ghost hexagons. Its
hollow shell remains 4.0 mm thick with a 3.0 mm minimum groove web and a 43.49°
internal seat ramp. Every radial/Z profile is now checked for intersections.
Five-millimetre pattern-free edge bands, shallow border rings, and 0.45 mm
external edge bevels give the drum deliberate top and bottom terminations.

The production font set now uses physically tested Overpass Bold as the default,
with Source Sans (`clean`), Lora italic (`serif`), Roboto Slab Bold (`slab`),
Fredoka SemiBold (`rounded`), Baloo 2 SemiBold (`playful`), and Barlow Condensed
SemiBold (`condensed`). All seven pass the eight-letter curved packing gate.

Cursive analysis selects Pacifico: at 15 mm it retains a 1.34 mm P20 stroke,
98.2% average connected-word area, and a 59.6 mm `Williams` width. It is not
live yet because it requires a title-case whole-word mesh, ligatures, and
deliberate bridges or keyed pockets for detached `i` dots.

Wave `LUNA` and `WILLIAMS` outputs use the 2.4 mm annular collar. The constrained
R74 rebuild has a 156,868 mm³ lower and 124,647 mm³ lettered upper, versus
976,604 mm³ for the defective early solid-collar prototype.

The Wave halves now use one continuous 256-column wrapped profile each. This
replaces the old per-sector boolean slabs, which were watertight but left deep
vertical grooves that appeared as holes in Bambu Studio. Revised `LUNA` and
`WILLIAMS` 3MFs have single-shell halves and smooth rendered exteriors.

Every Wave radial/Z profile is now checked as a simple positive-area polygon
before wrapping. This exposed and removed crossings in both the old lower inner
wall and upper bowl-support path. The upper has a continuous R74.5 receiver
wall with no horizontal shoulder, plus ≥4 mm wall through the lettering zone.

The bowl seat is now a separate 6.3 mm-high inverted-printing insert instead of
part of the inverted upper. Its R71.53 locator enters the R71.83 shell opening
(0.3 mm radial clearance), while its broad top flange rests on the shell rim.
This removes both the upper's large integrated internal seat and the unsupported
internal ledge from the first split attempt. Wave 3MFs also enable
avoid-crossing-wall travel with unlimited detours, 0.8 mm retraction at 30 mm/s,
layer-change retraction, and a 2 mm wipe.

Wave lettering now follows the original concept: Lora Medium Italic is
available as `serif`, glyph pockets are cut directly into the smooth upper
cone, and the separate proud name plaque has been removed. Letter backs and
pocket floors match the cone taper instead of using Cooper's cylindrical fit.
Plate 2 enables critical-regions-only normal support for the pocket-closing
layers; remove this support before fitting the letters.

Wave fit gate: `data/jobs/wave-collar-fit/Wave_Collar_Fit_Test_P2S.3mf`
contains the revised R74 lower collar and R74.5 upper sleeve on two plates.
The revised fit seated fully with a snug hand fit, minimal wobble, and easy
hand separation. Keep these radii and the 0.5 mm/side clearance.

Wave lettering gate:
`data/jobs/wave-letter-fit/LUNA_Wave_Letter_Fit_Test_P2S.3mf` contains a
71 × 14 × 23 mm crop of the real upper cone and its Lora letters. It uses the
production pockets, pocket floor, cone-backed letters, materials, and print
orientations. The LUNA pocket, seating, proudness, and removal checks passed.

---

## Known gaps / risks

1. **Preview** is a CSS mock, not real GLB geometry
2. **Cursive is research-only** — Pacifico needs a title-case whole-word mesh path and physical coupon
3. **Job storage** is local disk / in-process threads — fine locally; Railway needs a volume or object storage + possibly a worker
4. **No automated tests** yet
5. Condensed style helps long names; packing still rejects if rail > ±45°
6. Original design assets / print notes also live under `Ogma Print Files/cooper_dog_bowl/`

---

## Immediate next steps (priority)

1. Slice the four-plate Wave project and inspect upper-shell travel paths
2. Dry-fit the separate Wave bowl-seat insert before gluing its flange to the upper rim
3. Open Honeycomb 3MF in Bambu Studio; inspect wall paths, grooves, smooth name area, pockets, colours
4. Confirm fonts + `.gitignore` are acceptable for a public GitHub repo
5. Add `preview.glb` export from generator; show in web viewer
6. Deploy backend + web on Railway; set `PIPELINE_API_URL`, `JOBS_ROOT`, CORS
