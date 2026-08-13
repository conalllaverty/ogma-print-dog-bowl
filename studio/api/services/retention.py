"""Delete old jobs and cap the preview cache.

Nothing in the studio used to delete anything. A job leaves behind its meshes,
its visuals and a 1.7-5 MB `.3mf`; a preview leaves a GLB of 1-2 MB. Both live
under `JOBS_ROOT`, which on a deployment is a mounted volume of fixed size. So
the disk filled in proportion to how much the thing got used, and a full volume
is an outage rather than a slow day.

Two different policies, because the two caches mean different things:

- **Jobs expire by age.** A job is a record of something a customer asked for.
  It is worth keeping for a while so a download link survives a refresh and a
  failure can be looked at, and worthless long after that.

- **Previews are evicted by size, least-recently-used.** A preview is pure
  cache: the key is a hash of the geometry, so the bytes behind it can never be
  wrong, only absent. Rebuilding one costs a few seconds. Age tells you nothing
  useful here — a popular name stays popular — so the honest policy is a budget
  and eviction of whatever has gone longest untouched.

Deliberately not a cron job or an external sweeper: this runs in-process on a
daemon thread, because the thing that knows which jobs are still running is this
process.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from api.config import get_settings

log = logging.getLogger("ogma.retention")


@dataclass
class SweepResult:
    """What a sweep did. Returned so tests can assert on it and so the log line
    is built from measurements rather than intentions."""

    jobs_removed: int = 0
    job_bytes: int = 0
    previews_removed: int = 0
    preview_bytes: int = 0
    previews_kept_bytes: int = 0

    def __str__(self) -> str:
        return (
            f"jobs: {self.jobs_removed} removed ({self.job_bytes / 1e6:.1f} MB); "
            f"previews: {self.previews_removed} evicted "
            f"({self.preview_bytes / 1e6:.1f} MB), "
            f"{self.previews_kept_bytes / 1e6:.1f} MB kept"
        )


def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            # A file that vanished mid-walk is exactly what we were going to do
            # to it anyway.
            continue
    return total


def sweep_jobs(*, now: float | None = None) -> tuple[int, int]:
    """Remove job directories older than the retention window.

    Skips anything still queued or running. A job's directory is only safe to
    delete once no thread is writing into it, and this process is the only thing
    that knows — which is why retention lives here rather than in a cron job
    pointed at the volume.
    """
    from api.services.jobs import active_job_ids  # circular at module scope

    settings = get_settings()
    now = time.time() if now is None else now
    cutoff = now - settings.job_retention_hours * 3600
    root = settings.jobs_root
    active = active_job_ids()

    removed = freed = 0
    if not root.is_dir():
        return (0, 0)

    for entry in root.iterdir():
        # `_previews` is the preview cache, swept by size below. Anything else
        # starting with `_` is likewise not a job.
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        if entry.name in active:
            continue
        try:
            # mtime of the directory, which `Job.touch()` bumps on every status
            # change — so "old" means "nothing has happened to it", not "was
            # created long ago".
            if entry.stat().st_mtime >= cutoff:
                continue
            size = _dir_size(entry)
            shutil.rmtree(entry)
        except OSError as exc:
            log.warning("could not remove job dir %s: %s", entry.name, exc)
            continue
        removed += 1
        freed += size

    return removed, freed


def sweep_previews() -> tuple[int, int, int]:
    """Evict least-recently-used preview GLBs down to the size budget.

    Returns (evicted, bytes_freed, bytes_kept).
    """
    from api.services.previews import forget_preview, previews_root

    settings = get_settings()
    budget = settings.preview_cache_max_mb * 1024 * 1024
    root = previews_root()

    files = []
    for p in root.glob("*.glb"):
        try:
            st = p.stat()
        except OSError:
            continue
        files.append((st.st_atime, st.st_size, p))

    total = sum(size for _, size, _ in files)
    if total <= budget:
        return (0, 0, total)

    # Oldest access first. atime rather than mtime: the question is "when was
    # this last wanted", not "when was it built".
    files.sort(key=lambda t: t[0])

    evicted = freed = 0
    for _atime, size, path in files:
        if total <= budget:
            break
        try:
            path.unlink()
        except OSError as exc:
            log.warning("could not evict preview %s: %s", path.name, exc)
            continue
        # Drop the in-memory index entry too, or the next request is told the
        # preview is `ready` and then 404s fetching the file.
        forget_preview(path.stem)
        evicted += 1
        freed += size
        total -= size

    return evicted, freed, total


def sweep() -> SweepResult:
    """One full pass. Safe to call at any time."""
    from api.services.ratelimit import prune_all

    jobs_removed, job_bytes = sweep_jobs()
    previews_removed, preview_bytes, kept = sweep_previews()
    # Same class of leak, same sweep: the limiter's per-caller buckets would
    # otherwise be an unbounded map of every IP the service has ever seen.
    prune_all()
    return SweepResult(
        jobs_removed=jobs_removed,
        job_bytes=job_bytes,
        previews_removed=previews_removed,
        preview_bytes=preview_bytes,
        previews_kept_bytes=kept,
    )


def start_reaper() -> threading.Thread:
    """Run `sweep()` on an interval, forever, on a daemon thread."""
    settings = get_settings()
    interval = max(60, settings.reaper_interval_minutes * 60)

    def loop() -> None:
        while True:
            try:
                result = sweep()
                if result.jobs_removed or result.previews_removed:
                    log.info("retention sweep — %s", result)
            except Exception:  # noqa: BLE001
                # A sweep that fails is a disk that fills slightly sooner. It is
                # never a reason to take the server down with it.
                log.warning("retention sweep failed", exc_info=True)
            time.sleep(interval)

    thread = threading.Thread(target=loop, daemon=True, name="retention")
    thread.start()
    return thread
