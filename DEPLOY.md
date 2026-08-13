# Deploying the studio

Two services out of one repo: the API and the configurator. Everything below
was built and run locally with Docker before being written down — image sizes,
port numbers and the failure modes are measured, not assumed.

```
browser ──▶ web service (Next, :3000) ──▶ api service (FastAPI, :8080) ──▶ /data volume
                    the only public origin        internal only
```

The browser never talks to the API. `studio/web/src/app/api/v1/[...path]/route.ts`
proxies `/api/v1/*` through the web server, so there is one origin, no CORS in
the browser, and no API URL in the client bundle.

## Build locally first

```bash
docker build -f studio/Dockerfile -t ogma-studio-api .   # from the repo root
docker build -t ogma-studio-web studio/web
```

The API image is ~210 MB, the web image ~216 MB. The API **must** build from the
repo root: it composes `studio/api`, `products/dog-bowl` and `shared/ogma`, and
`shared/ogma/assets.py` derives every asset path from `shared/../`, so the
layout inside the image mirrors the repo. `.dockerignore` keeps that context at
~7 MB rather than ~1.3 GB.

## Service 1 — API

| Setting | Value |
|---|---|
| Root directory | `/` (repo root) |
| Dockerfile | `studio/Dockerfile` (set in `railway.json`) |
| Health check | `/api/v1/health` |
| Replicas | **1 — see below** |
| Volume | mount at `/data` |

Environment:

```
JOBS_ROOT=/data/jobs        # already the image default
CORS_ORIGINS=https://<your-web-domain>
```

`PORT` is injected by the platform; the container reads it.

**One replica, and this is not a tuning preference.** The bowl generator
configures itself through module globals, so two concurrent builds in one
process produce a stand with one name and letters for another. `jobs.py`
serialises them behind a `threading.Lock` — which is per-process. A second
replica is a second process with its own lock, and no lock at all between them.
`railway.json` pins `numReplicas: 1`; if you ever need more throughput the fix
is a real queue and a worker, not more replicas.

**The volume is not optional.** Jobs and the preview cache both live under
`JOBS_ROOT`, and the preview cache *is* the cache — `previews.py` treats the
file on disk as the source of truth and the in-memory dict as an index over it.
Without a volume every deploy throws away every built preview and every
customer's generated `.3mf`.

## Service 2 — Web

| Setting | Value |
|---|---|
| Root directory | `studio/web` |
| Dockerfile | `Dockerfile` (set in `studio/web/railway.json`) |
| Public domain | yes — this is the only thing the internet touches |

Environment:

```
PIPELINE_API_URL=http://<api-service>.railway.internal:8080
```

Point it at the API's **internal** address. Do not give the API a public domain;
nothing needs to reach it directly.

### Why this variable is read at run time

It used to be a `rewrites()` entry in `next.config.ts`, and `rewrites()` is
evaluated at **build** time — `next build` bakes the resolved destination into
`.next/routes-manifest.json`. A container that read `PIPELINE_API_URL` from its
environment had no effect at all: it proxied to whatever URL existed on the
build machine, which inside a container is the container itself, and every call
failed with `ECONNREFUSED 127.0.0.1:8000`.

The proxy is a route handler now, so the variable is read per request. One image
runs in any environment, and changing the API URL is a restart, not a rebuild.

## CORS, and why it barely matters here

The proxy is server-side, so the API never sees a browser `Origin` and CORS is
not in the request path at all. `CORS_ORIGINS` only governs direct calls to the
API. Set it anyway — it was until recently handed to Starlette as a raw
comma-joined **string**, which turns the origin check into a substring match
(`http://localhost:300` was accepted). Fixed, but the setting deserves a real
value rather than the localhost default.

## Verified before writing this

Both images built, run on a shared network with a volume, and exercised through
the web container alone:

- pages `/` and `/design/dog-bowl` — 200
- `/api/v1/health`, `/products`, `/filaments` (25 colours) — proxied fine
- style thumbnail (PNG) and bundled font (TTF) — correct content types
- preview: honeycomb built at 92,206 triangles / 1.66 MB, `immutable` cache
  header preserved through the proxy
- generate → download: `LUNA_Honeycomb_P2S.3mf`, 5.05 MB, `content-disposition`
  filename intact, valid 21-member zip with CRC checks passing
- a 3MF generated in the container is **byte-identical** to one generated on
  macOS — all 34 members — despite trimesh 5.0.0 in the image against 4.12.2
  locally. One case (`cooper`/`REX`/`bold`), so treat it as strong evidence
  rather than proof across every style.

## Still missing before this should take public traffic

Neither is a blocker for a private or unadvertised URL; both are for anything
linked publicly.

- **No disk reaper.** Every job writes its meshes, visuals and a `.3mf` (1.7–5 MB)
  and nothing ever deletes them. The in-memory `_jobs` dict grows for the life of
  the process too. A volume that fills takes the site down.
- **No rate limit.** `/generate` and `/preview` are anonymous and share one
  global build lock, so a single visitor in a loop queues everyone behind them.
