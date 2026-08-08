"""In-process job runner with local filesystem storage."""

from __future__ import annotations

import json
import sys
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from app.config import get_settings

PRODUCT_DIR = Path(__file__).resolve().parents[2]
GENERATOR_DIR = PRODUCT_DIR / "generator"
SHARED_DIR = PRODUCT_DIR.parents[1] / "shared"
for _p in (GENERATOR_DIR, SHARED_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline import FONT_STYLES, generate  # noqa: E402
from cooper_bowl_design import NameFitError  # noqa: E402
import styles  # noqa: E402

# Derived from the registry: a new styles/<id>.py appears in the API and the web
# configurator with no edit here.
STYLE_CATALOG = styles.catalog()


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


@dataclass
class Job:
    id: str
    status: JobStatus
    name: str
    font_style: str
    stand_filament_id: str
    letter_filament_id: str
    style: str = styles.DEFAULT_STYLE
    fuzzy_enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str | None = None
    threemf_name: str | None = None
    rail_outer_deg: float | None = None

    @property
    def dir(self) -> Path:
        return get_settings().jobs_root / self.id

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "status.json").write_text(json.dumps(asdict(self), indent=2) + "\n")


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def create_job(
    name: str,
    font_style: str,
    stand_filament_id: str,
    letter_filament_id: str,
    fuzzy_enabled: bool = True,
    style: str = styles.DEFAULT_STYLE,
) -> Job:
    if font_style not in FONT_STYLES:
        raise ValueError(f"font_style must be one of {list(FONT_STYLES)}")
    style = style.lower().strip()
    if style not in styles.STYLES:
        raise ValueError(f"style must be one of {list(styles.STYLES)}")
    if not styles.get(style).available:
        raise ValueError(f"Style '{style}' is not available yet")
    job = Job(
        id=uuid.uuid4().hex[:12],
        status=JobStatus.queued,
        name=name,
        font_style=font_style,
        stand_filament_id=stand_filament_id,
        letter_filament_id=letter_filament_id,
        style=style,
        fuzzy_enabled=fuzzy_enabled,
    )
    with _lock:
        _jobs[job.id] = job
    job.touch()
    thread = threading.Thread(target=_run_job, args=(job.id,), daemon=True)
    thread.start()
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        job = _jobs.get(job_id)
    if job:
        return job
    status_path = get_settings().jobs_root / job_id / "status.json"
    if not status_path.is_file():
        return None
    data = json.loads(status_path.read_text())
    # Older status.json files may omit style.
    data.setdefault("style", styles.DEFAULT_STYLE)
    job = Job(**{**data, "status": JobStatus(data["status"])})
    with _lock:
        _jobs[job_id] = job
    return job


def _run_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    job.status = JobStatus.running
    job.touch()
    try:
        result = generate(
            job.name,
            job.dir,
            style=job.style,
            font_style=job.font_style,
            stand_filament_id=job.stand_filament_id,
            letter_filament_id=job.letter_filament_id,
            fuzzy_enabled=job.fuzzy_enabled,
        )
        job.status = JobStatus.succeeded
        job.threemf_name = result.threemf_path.name
        job.rail_outer_deg = result.rail_outer_deg
        job.error = None
    except (NameFitError, ValueError) as exc:
        job.status = JobStatus.failed
        job.error = str(exc)
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.failed
        job.error = f"{exc}\n{traceback.format_exc()}"
    job.touch()
