# Ogma Print — Dog Bowl

Custom paw-lattice dog bowl stand configurator. Enter a name, pick **Bambu Lab PLA Matte** colours, download a print-ready Bambu Studio `.3mf`.

Runs **fully locally** and deploys to **Railway** with the same env contract.

- **Status / roadmap:** [PROJECT_STATUS.md](./PROJECT_STATUS.md)
- **Future session guide:** [AGENTS.md](./AGENTS.md)

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
  --font-style bold \
  --stand matte-caramel \
  --letters matte-ivory-white \
  --out data/jobs/cli-max
```

## Options

| Control | Values |
|---------|--------|
| Name | 2–8 letters A–Z |
| Letter style | `bold` · `rounded` · `condensed` |
| Stand / letter colour | Bambu PLA Matte palette (`backend/data/filament_palette.json`) |
| Fuzzy wall | on/off (paws + name rail stay smooth when on) |

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
