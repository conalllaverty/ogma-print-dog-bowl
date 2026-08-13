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

## Retention

Nothing used to delete anything. A single completed job leaves **14.1 MB** on
the volume — meshes, visuals and the `.3mf` — measured, not estimated. At that
rate a modest volume fills in a few hundred orders, and a full volume is an
outage.

A reaper runs in-process on a daemon thread, sweeping on `REAPER_INTERVAL_MINUTES`
(default 60, floored at 60 s). Two policies, because the two caches mean
different things:

| | Policy | Setting |
|---|---|---|
| Jobs | expire by age | `JOB_RETENTION_HOURS` (default 168 = 7 days) |
| Previews | LRU eviction to a size budget | `PREVIEW_CACHE_MAX_MB` (default 512) |

Jobs expire because a job is a record of something a customer asked for — worth
keeping while a download link might be reused, worthless long after. Previews
are pure cache: the key is a hash of the geometry so the bytes can never be
wrong, only absent, and rebuilding costs a few seconds. Age tells you nothing
there, so the policy is a budget and eviction by least-recently-*accessed*.

It runs in-process rather than as a cron job on the volume because the sweep has
to skip jobs that are still building, and this process is the only thing that
knows which those are.

## Rate limiting

`/generate` and `/preview` both take the single global build lock, so throughput
is one build at a time for the whole service and one anonymous caller in a loop
can queue everyone behind them.

```
RATE_LIMIT_ENABLED=true      # default
GENERATE_PER_HOUR=20         # default
PREVIEW_PER_HOUR=120         # default
```

A token bucket per caller, not a fixed window — a fixed window lets someone
spend a full budget at the end of one window and again at the start of the next.
Over budget returns **429** with a `Retry-After`.

Callers are identified by the left-most `x-forwarded-for` entry, because in this
topology every request reaches the API from the web container and limiting on
the socket peer would throttle all customers as one. **That trust is only safe
while the API has no public domain.** If you ever expose it directly, this has
to become a trusted-proxy check — otherwise a caller sets the header themselves
and the limit means nothing.

Counters are in-process, so they reset on deploy and are not shared between
replicas. The API is pinned to one replica anyway; if that ever changes it needs
a real queue first.

## Still missing

- **No authentication.** Anonymous by design for the MVP, per the product
  decisions in `products/dog-bowl/STATUS.md`. The rate limit is the only thing
  standing between the build lock and the open internet.
- **Bambu Studio has still never opened a generated 3MF.** `tests/audit_3mf.py`
  passes 14/14 against a P2S profile, but that is not the same as the slicer
  accepting the file. This is the largest unverified risk in the stack.
