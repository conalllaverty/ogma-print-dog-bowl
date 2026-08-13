"""Retention and rate limiting.

Both exist to stop one caller taking the service down — by filling the volume,
or by monopolising the single build lock. Neither shows up in the goldens, and
neither is exercised by using the app normally, so they are the parts most
likely to be quietly wrong.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "studio", REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


@pytest.fixture
def studio(tmp_path, monkeypatch):
    """A studio whose jobs_root is a temp dir, with settings cache cleared."""
    monkeypatch.setenv("JOBS_ROOT", str(tmp_path))
    from api.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()


# --------------------------------------------------------------------------
# Job expiry
# --------------------------------------------------------------------------


def _make_job_dir(root: Path, name: str, *, age_hours: float) -> Path:
    d = root / name
    (d / "meshes").mkdir(parents=True)
    (d / f"{name}.3mf").write_bytes(b"x" * 1024)
    (d / "meshes" / "part.stl").write_bytes(b"y" * 2048)
    when = time.time() - age_hours * 3600
    import os

    os.utime(d, (when, when))
    return d


def test_old_jobs_are_removed_and_recent_ones_kept(studio, monkeypatch):
    from api.services import retention

    root = studio.jobs_root
    old = _make_job_dir(root, "old000000000", age_hours=studio.job_retention_hours + 1)
    new = _make_job_dir(root, "new000000000", age_hours=1)

    monkeypatch.setattr(retention, "active_job_ids", lambda: set(), raising=False)
    removed, freed = retention.sweep_jobs()

    assert removed == 1
    assert freed >= 3072
    assert not old.exists()
    assert new.exists()


def test_a_running_job_is_never_deleted(studio, monkeypatch):
    """The whole reason retention lives in-process rather than in a cron job."""
    from api.services import jobs, retention

    root = studio.jobs_root
    building = _make_job_dir(root, "busy00000000", age_hours=10_000)

    monkeypatch.setattr(jobs, "active_job_ids", lambda: {"busy00000000"})
    monkeypatch.setattr(
        "api.services.jobs.active_job_ids", lambda: {"busy00000000"}
    )
    removed, _ = retention.sweep_jobs()

    assert removed == 0
    assert building.exists(), "a job still being written was deleted underneath it"


def test_the_preview_cache_dir_is_not_mistaken_for_a_job(studio, monkeypatch):
    from api.services import retention

    root = studio.jobs_root
    previews = root / "_previews"
    previews.mkdir(parents=True)
    (previews / "abc.glb").write_bytes(b"z" * 512)
    import os

    when = time.time() - 10_000 * 3600
    os.utime(previews, (when, when))

    monkeypatch.setattr("api.services.jobs.active_job_ids", lambda: set())
    removed, _ = retention.sweep_jobs()

    assert removed == 0
    assert previews.exists()


# --------------------------------------------------------------------------
# Preview eviction
# --------------------------------------------------------------------------


def test_previews_evict_lru_down_to_budget(studio, monkeypatch):
    from api.services import previews as previews_mod
    from api.services import retention

    root = previews_mod.previews_root()
    import os

    # Four 1 MB previews against a 2 MB budget: the two least recently used go.
    names = ["a", "b", "c", "d"]
    for i, n in enumerate(names):
        p = root / f"{n}.glb"
        p.write_bytes(b"0" * (1024 * 1024))
        atime = time.time() - (len(names) - i) * 3600
        os.utime(p, (atime, atime))

    monkeypatch.setattr(studio.__class__, "preview_cache_max_mb", 2, raising=False)
    studio.preview_cache_max_mb = 2

    evicted, freed, kept = retention.sweep_previews()

    assert evicted == 2, f"expected 2 evictions, got {evicted}"
    assert not (root / "a.glb").exists()
    assert not (root / "b.glb").exists()
    assert (root / "c.glb").exists()
    assert (root / "d.glb").exists()
    assert kept <= 2 * 1024 * 1024


def test_eviction_drops_the_in_memory_entry(studio):
    """A `ready` status pointing at a deleted file would 404 forever."""
    from api.services import previews as previews_mod
    from api.services import retention

    root = previews_mod.previews_root()
    p = root / "stale.glb"
    p.write_bytes(b"0" * (1024 * 1024))
    previews_mod._previews["stale"] = previews_mod.Preview(
        key="stale", product="dog-bowl", status="ready"
    )

    studio.preview_cache_max_mb = 0
    retention.sweep_previews()

    assert not p.exists()
    assert "stale" not in previews_mod._previews


def test_under_budget_evicts_nothing(studio):
    from api.services import previews as previews_mod
    from api.services import retention

    root = previews_mod.previews_root()
    (root / "keep.glb").write_bytes(b"0" * 1024)
    studio.preview_cache_max_mb = 512

    evicted, freed, _ = retention.sweep_previews()
    assert (evicted, freed) == (0, 0)
    assert (root / "keep.glb").exists()


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_bucket_allows_capacity_then_refuses():
    from api.services.ratelimit import RateLimiter

    limiter = RateLimiter(capacity=3, per_seconds=3600)
    assert [limiter.check("ip", now=0.0) for _ in range(3)] == [0.0, 0.0, 0.0]

    wait = limiter.check("ip", now=0.0)
    assert wait > 0, "fourth request inside the window should have been refused"
    assert wait == pytest.approx(1200.0, rel=0.01)  # 1/3 of an hour


def test_bucket_refills_over_time():
    from api.services.ratelimit import RateLimiter

    limiter = RateLimiter(capacity=2, per_seconds=100)
    limiter.check("ip", now=0.0)
    limiter.check("ip", now=0.0)
    assert limiter.check("ip", now=0.0) > 0

    # One token every 50 s.
    assert limiter.check("ip", now=50.0) == 0.0


def test_callers_are_independent():
    from api.services.ratelimit import RateLimiter

    limiter = RateLimiter(capacity=1, per_seconds=3600)
    assert limiter.check("1.1.1.1", now=0.0) == 0.0
    assert limiter.check("1.1.1.1", now=0.0) > 0
    assert limiter.check("2.2.2.2", now=0.0) == 0.0, "one caller throttled another"


def test_a_burst_cannot_exceed_capacity_at_a_window_boundary():
    """What a fixed-window counter gets wrong.

    With a fixed window, capacity can be spent at the end of one window and
    again at the start of the next — 2x the budget back to back. A bucket
    refills continuously, so the second burst is only as large as what has
    actually accrued.
    """
    from api.services.ratelimit import RateLimiter

    limiter = RateLimiter(capacity=10, per_seconds=3600)
    for _ in range(10):
        assert limiter.check("ip", now=3599.0) == 0.0

    allowed = sum(1 for _ in range(10) if limiter.check("ip", now=3601.0) == 0.0)
    assert allowed <= 1, f"{allowed} allowed immediately after exhausting the budget"


def test_prune_forgets_only_fully_refilled_callers():
    from api.services.ratelimit import RateLimiter

    limiter = RateLimiter(capacity=2, per_seconds=100)
    limiter.check("spent", now=0.0)
    limiter.check("spent", now=0.0)
    limiter.check("partial", now=0.0)

    assert limiter.prune(now=10.0) == 0, "pruned a caller still holding a debt"
    assert limiter.prune(now=1000.0) == 2


def test_client_key_prefers_forwarded_for():
    """In the deployed topology every request arrives from the web container,
    so limiting on the socket peer would throttle all customers as one."""
    from api.services.ratelimit import client_key

    class Req:
        def __init__(self, headers, host):
            self.headers = headers
            self.client = type("C", (), {"host": host})()

    assert client_key(Req({"x-forwarded-for": "9.9.9.9, 10.0.0.1"}, "10.0.0.5")) == "9.9.9.9"
    assert client_key(Req({}, "10.0.0.5")) == "10.0.0.5"
