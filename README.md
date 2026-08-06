# Ogma Print — Dog Bowl

Custom paw-lattice dog bowl stand configurator. Enter a name, pick **Bambu Lab PLA Matte** colours, download a print-ready Bambu Studio `.3mf`.

Runs **fully locally** and deploys to **Railway** with the same env contract.

- **Status / roadmap:** [PROJECT_STATUS.md](./PROJECT_STATUS.md)
- **Future session guide:** [AGENTS.md](./AGENTS.md)
- **Ireland county clickers:** [county-clickers/README.md](./county-clickers/README.md)
- **Bouclé Stack lamp:** [ready-to-print P2S shade](./design/boucle-stack-lamp/production/README.md)

## Quick start (local)

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd web && npm install && cd ..

# Terminal 1 — API
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Web
cd web && PIPELINE_API_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000

Or: `bash scripts/dev.sh`

### CLI generate (no UI)

```bash
.venv/bin/python backend/generator/pipeline.py \
  --name MAX \
  --style cooper \
  --font-style bold \
  --stand matte-caramel \
  --letters matte-ivory-white \
  --out data/jobs/cli-max
```

### Letter-fit test (cropped rail + letters only)

```bash
.venv/bin/python backend/generator/letter_test.py \
  --name COOPER \
  --stand matte-ash-gray \
  --letters matte-ivory-white \
  --out data/jobs/letter-test
```

Output: `*_Letter_Test_P2S.3mf` (plate 1 = rail coupon, plate 2 = letters).

### Wave collar-fit test

Print the production-radius R74 collar and R74.5 sleeve before committing to a
full Wave:

```bash
.venv/bin/python backend/generator/wave_fit_test.py \
  --stand matte-caramel \
  --out data/jobs/wave-collar-fit
```

Output: `Wave_Collar_Fit_Test_P2S.3mf` (lower collar and upper sleeve on
separate plates, 0.16 mm layers). Accept when the sleeve starts by hand, seats
without tools or rocking, and can still be separated before gluing.
The R74/R74.5 coupon physically passed this gate on a P2S on 2026-07-23.

### Wave lettering-fit test

Print the real conical wall pockets and matching cone-backed letters before the
complete Wave:

```bash
.venv/bin/python backend/generator/wave_letter_test.py \
  --name LUNA \
  --font-style serif \
  --stand matte-caramel \
  --letters matte-ivory-white \
  --out data/jobs/wave-letter-fit
```

Output: `LUNA_Wave_Letter_Fit_Test_P2S.3mf` (plate 1 = upright production-cone
coupon, plate 2 = face-down letters). Accept when every letter starts by hand,
seats without rocking, remains approximately 1.4 mm proud, and can be removed
before gluing.

## Options

| Control               | Values                                                                    |
| --------------------- | ------------------------------------------------------------------------- |
| Name                  | 2–8 letters A–Z                                                           |
| Stand style           | `cooper` · `wave` · `hex` (solid recessed honeycomb)                      |
| Letter style          | `bold` · `clean` · `serif` · `slab` · `rounded` · `playful` · `condensed` |
| Stand / letter colour | Bambu PLA Matte palette (`backend/data/filament_palette.json`)            |
| Fuzzy wall            | on/off (paws + name rail stay smooth when on)                             |

## Style concept sheets

Multi-angle SVGs for design review before geometry changes:

- `design/style-previews/cooper-paw-multi-angle.svg`
- `design/style-previews/wave-multi-angle.svg`
- `design/style-previews/honeycomb-multi-angle.svg`

Regenerate them with `python3 scripts/generate_bowl_style_svgs.py`.

Wave uses direct glyph pockets in the upper cone rather than a name plaque.
The `serif` option is the original concept's Lora Medium Italic treatment;
Wave letter backs are conical so they seat flush against the tapered wall.
Both halves use validated, non-self-intersecting wrapped profiles. The upper
keeps at least 4 mm of wall through the lettering zone.

Wave outputs four plates: lower, inverted cosmetic upper shell, inverted
bowl-seat insert, and letters. Dry-fit the insert's locator into the top of the
upper shell; its 0.3 mm radial clearance should let the broad flange settle
flat onto the shell rim. Glue the flange to that rim only after the fit check.
The Wave project enables avoid-crossing-wall travel with unlimited detours,
0.8 mm retraction at 30 mm/s, layer-change retraction, and a 2 mm wipe. Nozzle
temperature remains controlled by the selected Bambu PLA Matte filament profile.
Plate 2 also enables critical-regions-only normal support for the pocket-closing
layers; remove this small support before fitting the letters.

Honeycomb uses a 4 mm hollow drum with 1 mm recessed grooves. Its name area
derives a tight keepout from the packed glyph envelope, then suppresses complete
honeycomb cells so there are no clipped or fading groove fragments. The name is
optically centred at Z37 within the staggered whole-cell field. Pattern-free
edge bands and shallow border rings end in a 0.45 mm top bead and a 0.35 mm
bottom elephant-foot chamfer. The internal seat ramp starts at Z58 and stays
near 39°.

`bold` is Overpass Bold, selected from physical FDM font testing. `rounded`
uses Fredoka SemiBold, `playful` uses Baloo 2 SemiBold, `condensed` uses Barlow
Condensed SemiBold, and `slab` uses Roboto Slab Bold. `clean` retains the
previous Source Sans treatment.

## API

- `GET /api/v1/health`
- `GET /api/v1/filaments`
- `POST /api/v1/bowl/generate` → `{ job_id }`
- `GET /api/v1/bowl/jobs/{id}`
- `GET /api/v1/bowl/jobs/{id}/download.3mf`

## Railway

Two services (same pattern as `ogma-print-core`):

1. **backend** — Dockerfile in `backend/`, `$PORT` (8080), volume or disk for `JOBS_ROOT`
2. **web** — Dockerfile in `web/`, `PIPELINE_API_URL` = public backend URL

Env keys match `.env.example` (`APP_ENV=production`, `CORS_ORIGINS` = your web origin).

## Layout

```
backend/app/           FastAPI
backend/generator/     parametric bowl → 3MF
backend/data/          Matte filament palette
web/                   Next.js configurator
data/jobs/             local job output
```
