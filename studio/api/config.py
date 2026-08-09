"""Ogma Bowl API — local and Railway."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[2]  # repo root
load_dotenv(find_dotenv(str(ROOT / ".env"), usecwd=True) or str(ROOT / ".env"))


class Settings(BaseSettings):
    app_env: str = "local"
    port: int = 8000
    jobs_root: Path = ROOT / "out"
    filament_palette_path: Path = ROOT / "shared" / "ogma" / "palette.json"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    public_api_url: str = "http://localhost:8000"

    class Config:
        env_file = str(ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if os.getenv("PORT"):
        settings.port = int(os.environ["PORT"])
    if os.getenv("JOBS_ROOT"):
        settings.jobs_root = Path(os.environ["JOBS_ROOT"]).expanduser().resolve()
    settings.jobs_root.mkdir(parents=True, exist_ok=True)
    return settings
