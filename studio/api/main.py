from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.api.studio import router
from api.config import get_settings
from api.registry import REGISTRY

log = logging.getLogger("ogma.studio")

settings = get_settings()


def _warm_caches() -> None:
    """Pay for the first customer's validation before they arrive.

    The bowl's fit check memoises one measurement per (letter, font) and answers
    in 9 ms once warm — but the very first name to trip the gate pays ~3 s while
    those glyphs are measured, and 3 s is long enough to read as "nothing
    happened".

    Runs in a daemon thread, so a slow warm-up never delays the server coming
    up, and deliberately does *not* take the build lock: the measurement path
    passes the font explicitly and touches no generator globals (see
    name_fit._letter_half_angle), so it cannot corrupt a running job. It only
    competes for CPU, and only for a few seconds at boot.
    """
    # Drop this thread's priority: speculative work for a customer who has not
    # arrived must never make a real request wait for a core.
    #
    # Linux only, and that restriction is the whole point. `nice()` is
    # per-thread on Linux but **per-process** on macOS — calling it here on a
    # Mac would permanently deprioritise the entire API server to speed up a
    # cache nobody is waiting for. On macOS we simply skip it; the warm-up is
    # under a minute and its worst case is the behaviour we had before it
    # existed.
    if sys.platform.startswith("linux"):
        try:
            os.nice(15)
        except (OSError, PermissionError):
            pass

    for spec in REGISTRY.all():
        warm = getattr(spec.generator, "warm", None)
        if warm is None:
            continue
        try:
            warm()
        except Exception:  # noqa: BLE001
            # A cold cache is a slower first request, never a broken one.
            log.warning("cache warm-up failed for %s", spec.id, exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # `@app.on_event("startup")` is deprecated in FastAPI; lifespan is the
    # supported hook and also gives us a place to shut things down later.
    threading.Thread(target=_warm_caches, daemon=True, name="warm-caches").start()
    yield


app = FastAPI(title="Ogma Print Studio", version="2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # The parsed list, not the raw comma-joined string. Starlette tests
    # `origin in self.allow_origins`, which on a str is a *substring* match:
    # with the string form, Origin `http://localhost:300` was answered with
    # Access-Control-Allow-Origin plus allow_credentials.
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
