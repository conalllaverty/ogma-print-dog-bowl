"""Studio routes — product-agnostic.

The old surface was /api/v1/bowl/... with bowl-shaped request bodies. It is now
/api/v1/products/{id}/... with a free-form `values` object validated against the
product's declared spec. The bowl routes remain as thin aliases so nothing that
already points at them breaks.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.config import get_settings
from api.registry import REGISTRY
from api.services.jobs import create_job, get_job
from ogma.designer import ValidationError

router = APIRouter(prefix="/api/v1")


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
    try:
        spec.generator.validate(values)
    except ValidationError as exc:
        return {"ok": False, "values": values, "errors": [e.to_json() for e in exc.errors]}
    return {"ok": True, "values": values, "errors": []}


@router.post("/products/{product_id}/generate")
def generate(product_id: str, body: ValuesRequest):
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
def bowl_generate(body: BowlRequest):
    return generate("dog-bowl", ValuesRequest(values=body.model_dump()))


@router.get("/bowl/jobs/{job_id}", deprecated=True)
def bowl_job(job_id: str):
    return job(job_id)


@router.get("/bowl/jobs/{job_id}/download.3mf", deprecated=True)
def bowl_download(job_id: str):
    return download(job_id)
