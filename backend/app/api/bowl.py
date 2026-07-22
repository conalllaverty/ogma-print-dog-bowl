from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.jobs import create_job, get_job

router = APIRouter(prefix="/api/v1")


class GenerateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=8)
    font_style: str = "bold"
    stand_filament_id: str = "matte-caramel"
    letter_filament_id: str = "matte-ivory-white"
    fuzzy_enabled: bool = True


@router.get("/health")
def health():
    settings = get_settings()
    return {"ok": True, "env": settings.app_env}


@router.get("/filaments")
def filaments():
    path = get_settings().filament_palette_path
    data = json.loads(Path(path).read_text())
    return {
        "filaments": [
            {"id": f["id"], "name": f["name"], "hex": f["hex"], "material": f.get("material")}
            for f in data["filaments"]
        ],
        "font_styles": [
            {"id": "bold", "name": "Bold Sans", "description": "Thick even strokes — default"},
            {"id": "rounded", "name": "Rounded Bold", "description": "Softer corners"},
            {"id": "condensed", "name": "Condensed Bold", "description": "Narrower — better for long names"},
        ],
        "constraints": {"min_letters": 2, "max_letters": 8, "alphabet": "A–Z"},
    }


@router.post("/bowl/generate")
def bowl_generate(body: GenerateRequest):
    try:
        job = create_job(
            name=body.name,
            font_style=body.font_style,
            stand_filament_id=body.stand_filament_id,
            letter_filament_id=body.letter_filament_id,
            fuzzy_enabled=body.fuzzy_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job_id": job.id, "status": job.status}


@router.get("/bowl/jobs/{job_id}")
def bowl_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "name": job.name,
        "font_style": job.font_style,
        "stand_filament_id": job.stand_filament_id,
        "letter_filament_id": job.letter_filament_id,
        "fuzzy_enabled": job.fuzzy_enabled,
        "error": job.error,
        "threemf_name": job.threemf_name,
        "rail_outer_deg": job.rail_outer_deg,
        "download_url": f"/api/v1/bowl/jobs/{job.id}/download.3mf"
        if job.status == "succeeded"
        else None,
    }


@router.get("/bowl/jobs/{job_id}/download.3mf")
def bowl_download(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "succeeded" or not job.threemf_name:
        raise HTTPException(status_code=409, detail="Job not ready")
    path = job.dir / job.threemf_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(
        path,
        media_type="application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        filename=job.threemf_name,
    )
