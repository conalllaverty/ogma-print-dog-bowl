from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.bowl import router as bowl_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Ogma Bowl API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(bowl_router)


@app.get("/")
def root():
    return {"service": "ogma-bowl", "docs": "/docs", "health": "/api/v1/health"}
