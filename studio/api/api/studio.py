"""Studio routes — product-agnostic.

The old surface was /api/v1/bowl/... with bowl-shaped request bodies. It is now
/api/v1/products/{id}/... with a free-form `values` object validated against the
product's declared spec. The bowl routes remain as thin aliases so nothing that
already points at them breaks.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.config import get_settings
from api.registry import REGISTRY
from api.services.jobs import create_job, get_job
from api.services.previews import get_preview, request_preview
from api.services.ratelimit import enforce
from ogma import assets
from ogma.designer import ValidationError

router = APIRouter(prefix="/api/v1")

FONTS_DIR = Path(assets.FONTS)
PRODUCTS_DIR = Path(assets.REPO_ROOT) / "products"


class ValuesRequest(BaseModel):
    values: dict = Field(default_factory=dict)


def _spec_or_404(product_id: str):
    try:
        return REGISTRY.get(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown product '{product_id}'")


@router.get("/health")
def health():
    return {"ok": True, "env": get_settings().app_env}


@router.get("/filaments")
def filaments():
    """The Bambu Matte palette. Shared by every product, so it is not nested
    under one."""
    data = json.loads(Path(get_settings().filament_palette_path).read_text())
    return {
        "filaments": [
            {"id": f["id"], "name": f["name"], "hex": f["hex"], "material": f.get("material")}
            for f in data["filaments"]
        ]
    }


@router.get("/fonts/{filename}")
def font(filename: str):
    """Serve a bundled font so the designer can show each lettering style in
    its own typeface.

    Served from `shared/ogma/fonts` — the same files the generator rasterises —
    rather than a copy under web/public. Two copies of a font is how the picture
    and the print stop matching.

    All bundled faces are SIL OFL 1.1 or Apache 2.0; both permit web embedding.
    See shared/ogma/fonts/LICENSES.md.
    """
    if not filename.endswith((".ttf", ".otf")) or "/" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="Unknown font")
    path = (FONTS_DIR / filename).resolve()
    # Belt and braces: resolve() then confirm it is still inside the font dir.
    if not path.is_file() or FONTS_DIR.resolve() not in path.parents:
        raise HTTPException(status_code=404, detail="Unknown font")
    return FileResponse(
        path,
        media_type="font/ttf",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/products/{product_id}/assets/{asset_path:path}")
def product_asset(product_id: str, asset_path: str):
    """Static assets a product ships — style thumbnails, diagrams.

    The spec hands out *relative* paths (`styles/cooper.png`) and the client
    composes the URL, so a product never has to know its own route prefix.
    """
    spec = _spec_or_404(product_id)
    root = (PRODUCTS_DIR / spec.id / "assets").resolve()
    path = (root / asset_path).resolve()
    if not path.is_file() or root not in path.parents:
        raise HTTPException(status_code=404, detail="Unknown asset")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/products")
def products():
    """Catalogue for the picker — no parameters, so it stays small."""
    return {"products": REGISTRY.catalog()}


@router.get("/products/{product_id}")
def product_spec(product_id: str):
    """The full spec the designer renders from."""
    return _spec_or_404(product_id).to_json()


@router.post("/products/{product_id}/validate")
def validate(product_id: str, body: ValuesRequest):
    """Check values without building anything.

    Lets the UI show a fit problem under the offending field while the customer
    is still typing, rather than after a multi-minute generate.
    """
    spec = _spec_or_404(product_id)
    if spec.generator is None:
        raise HTTPException(status_code=409, detail=f"{spec.name} is not designable yet")
    values = spec.coerce(body.values)
    # Declared constraints first: if the name is the wrong length there is no
    # point asking the geometry whether it packs.
    declared = spec.check_declared(values)
    if declared:
        return {"ok": False, "values": values, "errors": [e.to_json() for e in declared]}
    try:
        spec.generator.validate(values)
    except ValidationError as exc:
        return {"ok": False, "values": values, "errors": [e.to_json() for e in exc.errors]}
    return {"ok": True, "values": values, "errors": []}


@router.post("/products/{product_id}/preview")
def preview(product_id: str, body: ValuesRequest, request: Request):
    """Ask for a 3D preview of these values.

    Returns immediately. If an identical *geometry* has been built before —
    same name, style and lettering, any colour — this is a cache hit and comes
    back `ready` on the first call.
    """
    # Rate-limited before the cache lookup, deliberately: a miss is what costs
    # the build lock, and the caller does not get to find out which it was by
    # spending someone else's throughput.
    enforce(request, "preview")
    spec = _spec_or_404(product_id)
    try:
        return request_preview(spec.id, body.values).to_json()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/previews/{key}.glb")
def preview_model(key: str):
    found = get_preview(key)
    if not found or found.status != "ready" or not found.path.is_file():
        raise HTTPException(status_code=404, detail="Preview not ready")
    return FileResponse(
        found.path,
        media_type="model/gltf-binary",
        # The key is a hash of the geometry, so the bytes behind it can never
        # change. Cache hard.
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/previews/{key}")
def preview_status(key: str):
    found = get_preview(key)
    if not found:
        raise HTTPException(status_code=404, detail="Unknown preview")
    return found.to_json()


@router.post("/products/{product_id}/generate")
def generate(product_id: str, body: ValuesRequest, request: Request):
    enforce(request, "generate")
    spec = _spec_or_404(product_id)
    try:
        job = create_job(spec.id, body.values)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"errors": [e.to_json() for e in exc.errors]},
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"job_id": job.id, "status": job.status.value}


@router.get("/jobs/{job_id}")
def job(job_id: str):
    j = get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Unknown job")
    return j.to_json()


@router.get("/jobs/{job_id}/download")
def download(job_id: str):
    j = get_job(job_id)
    if not j or j.status.value != "succeeded" or not j.output:
        raise HTTPException(status_code=404, detail="No output for this job")
    path = j.dir / j.output
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Output missing on disk")
    return FileResponse(path, media_type="model/3mf", filename=j.output)


# --- Backwards-compatible bowl aliases -------------------------------------
# Nothing is deployed, but keeping these costs three lines and means an older
# client or bookmark still works.


class BowlRequest(BaseModel):
    name: str
    style: str = "cooper"
    font_style: str = "bold"
    stand_filament_id: str = "matte-caramel"
    letter_filament_id: str = "matte-ivory-white"
    fuzzy_enabled: bool = True


@router.post("/bowl/generate", deprecated=True)
def bowl_generate(body: BowlRequest, request: Request):
    # Forwards the Request so the alias is limited on the same budget as the
    # route it delegates to — otherwise it is a way around the limiter.
    return generate("dog-bowl", ValuesRequest(values=body.model_dump()), request)


@router.get("/bowl/jobs/{job_id}", deprecated=True)
def bowl_job(job_id: str):
    return job(job_id)


@router.get("/bowl/jobs/{job_id}/download.3mf", deprecated=True)
def bowl_download(job_id: str):
    return download(job_id)
