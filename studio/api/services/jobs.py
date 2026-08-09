"""Product-agnostic job service.

A job is: a product id, the values the customer chose, and a status. What the
generator does with those values is the product's business. This module used to
hardcode name/font_style/stand/letters/fuzzy — that is now just one product's
`values` dict.
"""

from __future__ import annotations

import json
import threading
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from api.config import get_settings
from api.registry import REGISTRY
from ogma.designer import ValidationError


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    product: str
    values: dict[str, Any]
    status: JobStatus
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    error: str | None = None
    # Field-addressed failures, so a late geometry rejection can still be shown
    # under the control that caused it.
    field_errors: list[dict] = field(default_factory=list)
    output: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def dir(self) -> Path:
        return get_settings().jobs_root / self.id

    def touch(self) -> None:
        self.updated_at = _now()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "status.json").write_text(json.dumps(asdict(self), indent=2) + "\n")

    def to_json(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


_jobs: dict[str, Job] = {}
_lock = threading.Lock()

# One build at a time. The bowl generator configures itself through module
# globals (NAME, FONT_PATH, NAME_RAIL_OUTER_DEG), so two concurrent jobs in one
# process would silently interleave and produce a stand with one name and
# letters for another. Serialising is also the honest model of a one-printer
# shop; it costs nothing until there are two customers at once, and the fix
# then is a real queue, not threads.
_build_lock = threading.Lock()


def build_lock() -> threading.Lock:
    """The one geometry builder. Previews take it too — see services/previews.py."""
    return _build_lock


def create_job(product_id: str, raw_values: dict[str, Any]) -> Job:
    """Coerce, validate, then queue. Raises ValidationError before any work."""
    spec = REGISTRY.get(product_id)
    if not spec.available or spec.generator is None:
        raise ValueError(f"{spec.name} is not available in the designer yet")

    values = spec.coerce(raw_values)
    declared = spec.check_declared(values)
    if declared:
        raise ValidationError(declared)
    spec.generator.validate(values)  # ValidationError propagates to the caller

    job = Job(
        id=uuid.uuid4().hex[:12],
        product=spec.id,
        values=values,
        status=JobStatus.queued,
    )
    with _lock:
        _jobs[job.id] = job
    job.touch()
    threading.Thread(target=_run_job, args=(job.id,), daemon=True).start()
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
    job = Job(**{**data, "status": JobStatus(data["status"])})
    with _lock:
        _jobs[job_id] = job
    return job


def _run_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    try:
        spec = REGISTRY.get(job.product)
        with _build_lock:
            # Status flips to running only once this job actually owns the
            # builder, so a queued job doesn't claim to be building.
            job.status = JobStatus.running
            job.touch()
            result = spec.generator.generate(job.values, job.dir)
        job.output = result.get("output")
        job.meta = {k: v for k, v in result.items() if k != "output"}
        job.status = JobStatus.succeeded
        job.error = None
    except ValidationError as exc:
        # A gate only the geometry could enforce — e.g. the bowl's letter
        # packing. Surface it as field errors, not a stack trace.
        job.status = JobStatus.failed
        job.error = str(exc)
        job.field_errors = [e.to_json() for e in exc.errors]
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.failed
        job.error = f"{exc}\n{traceback.format_exc()}"
    job.touch()
