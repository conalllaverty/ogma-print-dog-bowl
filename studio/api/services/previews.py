"""On-demand 3D previews, cached on the geometry that produced them.

A preview costs 2-8 s of mesh building, so the two things that matter are: never
build the same thing twice, and never build at all for a change that isn't
geometric. Both fall out of `ProductSpec.preview_key()`, which hashes only the
parameters a product declares as geometry-affecting. Walking the whole 25-colour
palette produces one cache key and therefore one build.

Previews share the generator's build lock with jobs. They must: the bowl
generator configures itself through module globals, so a preview running
alongside a job would corrupt the job — the customer's actual order. A paying
job should not lose to someone spinning the viewer.
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api.config import get_settings
from api.registry import REGISTRY
from api.services.jobs import build_lock


@dataclass
class Preview:
    key: str
    product: str
    status: str = "building"  # building | ready | failed
    error: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return previews_root() / f"{self.key}.glb"

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "product": self.product,
            "status": self.status,
            "error": self.error,
            "stats": self.stats,
            "url": f"/api/v1/previews/{self.key}.glb" if self.status == "ready" else None,
        }


def previews_root() -> Path:
    root = get_settings().jobs_root / "_previews"
    root.mkdir(parents=True, exist_ok=True)
    return root


_previews: dict[str, Preview] = {}
_lock = threading.Lock()


def request_preview(product_id: str, raw_values: dict[str, Any]) -> Preview:
    """Return a cached preview, or start building one. Never blocks."""
    spec = REGISTRY.get(product_id)
    if not spec.has_preview:
        raise ValueError(f"{spec.name} has no 3D preview")

    values = spec.coerce(raw_values)
    declared = spec.check_declared(values)
    if declared:
        # A preview of an invalid configuration is meaningless, and for the bowl
        # it would raise deep in the glyph code. Let the caller show the field
        # errors it already has instead.
        raise ValueError("configuration is not valid")

    key = spec.preview_key(values)

    with _lock:
        existing = _previews.get(key)
        if existing and existing.status != "failed":
            return existing
        # Survives a restart: the file on disk is the cache, the dict is a
        # cheap index over it.
        preview = Preview(key=key, product=spec.id)
        if preview.path.is_file():
            preview.status = "ready"
            preview.stats = {"bytes": preview.path.stat().st_size, "cached": True}
            _previews[key] = preview
            return preview
        _previews[key] = preview

    threading.Thread(
        target=_build, args=(spec.id, key, values), daemon=True
    ).start()
    return preview


def get_preview(key: str) -> Preview | None:
    with _lock:
        preview = _previews.get(key)
    if preview:
        return preview
    path = previews_root() / f"{key}.glb"
    if not path.is_file():
        return None
    # Built by an earlier process. We no longer know which product it was, but
    # the file is what the caller wants.
    preview = Preview(key=key, product="", status="ready", stats={"cached": True})
    with _lock:
        _previews[key] = preview
    return preview


def _build(product_id: str, key: str, values: dict[str, Any]) -> None:
    preview = get_preview(key)
    if preview is None:
        return
    tmp = previews_root() / f".{key}.partial"
    try:
        spec = REGISTRY.get(product_id)
        with build_lock():
            stats = spec.generator.preview(values, tmp)
        # Publish atomically, so a concurrent reader never sees a half-written
        # GLB at the real path.
        tmp.replace(preview.path)
        preview.stats = stats
        preview.status = "ready"
        preview.error = None
    except Exception as exc:  # noqa: BLE001
        preview.status = "failed"
        preview.error = f"{exc}\n{traceback.format_exc()}"
        tmp.unlink(missing_ok=True)
