# The studio API.
#
# Build from the REPO ROOT, not from studio/:
#
#     docker build -f studio/Dockerfile -t ogma-studio-api .
#
# It has to be the root because the API composes three trees that sit beside
# each other — studio/api serves it, products/dog-bowl generates the geometry,
# and shared/ogma is the toolkit both depend on. `shared/ogma/assets.py` derives
# every asset path from `shared/../`, so the layout inside the image must mirror
# the repo exactly. See .dockerignore for what is kept out of that context.
#
# This file replaces studio/api-Dockerfile, which copied `app/ generator/ data/
# assets/` and ran `uvicorn app.main:app` — the layout from before the monorepo
# restructure in 290f64b. None of those paths had existed for weeks; it could
# not have built.

FROM python:3.12-slim

# libgl1 + libglib2.0-0: trimesh's optional native paths link against them.
# The old image also installed fonts-liberation and copied it over Arial —
# dropped, because the generator now rasterises the bundled faces in
# shared/ogma/fonts and never asks the system for a font.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall manifold3d and scipy.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Mirror the repo layout. assets.REPO_ROOT resolves to /app, so studio.py finds
# /app/products and the generator finds /app/shared/ogma/{fonts,bambu,palette.json}.
COPY shared   ./shared
COPY products ./products
COPY studio/api ./studio/api

# `from api.api.studio import router` — the package root is studio/, not /app.
ENV PYTHONPATH=/app/studio \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    JOBS_ROOT=/data/jobs

# Jobs and the preview cache live on a mounted volume. Without one they land on
# the container filesystem and vanish on the next deploy — including the preview
# GLBs, which are the cache, not a copy of it.
# Not -r: a system account is capped at SYS_UID_MAX (999), and asking for both
# warns and gives you a normal account anyway. Being non-root is the point.
RUN mkdir -p /data/jobs \
    && useradd -u 10001 -m -s /usr/sbin/nologin ogma \
    && chown -R ogma:ogma /data /app
USER ogma
VOLUME ["/data"]

EXPOSE 8080
# `sh -c` because ${PORT} is supplied by the platform at run time and plain exec
# form would pass it through as a literal. `exec` because without it uvicorn is
# a child of the shell, PID 1 is /bin/sh, and SIGTERM on redeploy goes to the
# shell instead of the server — the container then gets killed mid-request
# rather than draining.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
