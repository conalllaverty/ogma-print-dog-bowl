"""Ogma Bowl API — local and Railway."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # repo root
load_dotenv(find_dotenv(str(ROOT / ".env"), usecwd=True) or str(ROOT / ".env"))


class Settings(BaseSettings):
    app_env: str = "local"
    port: int = 8000
    jobs_root: Path = ROOT / "out"
    filament_palette_path: Path = ROOT / "shared" / "ogma" / "palette.json"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    public_api_url: str = "http://localhost:8000"

    # --- retention ---------------------------------------------------------
    # Nothing used to delete anything. Each job leaves its meshes, visuals and a
    # 1.7-5 MB .3mf behind for good, so the volume filled at the rate people
    # used the thing — and a full volume is an outage, not a slow day.
    job_retention_hours: int = 168  # 7 days
    preview_cache_max_mb: int = 512
    reaper_interval_minutes: int = 60

    # --- rate limiting -----------------------------------------------------
    # /generate and /preview both take the single global build lock, so one
    # caller in a loop is enough to queue every other customer behind them.
    # Generous by default: these are per-hour budgets for a shop with one
    # printer, not an API product.
    rate_limit_enabled: bool = True
    generate_per_hour: int = 20
    preview_per_hour: int = 120

    # SettingsConfigDict, not a nested `class Config`: the class-based form is
    # deprecated in Pydantic 2 and removed in 3, and it warned on every test run.
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
