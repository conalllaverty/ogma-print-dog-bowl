"""Canonical locations of the shared binary assets.

Before the restructure, twelve modules each built their own
`GENERATOR_DIR / "blank_project.3mf"` and `GENERATOR_DIR / "bambu_work"`.
That worked only because every generator lived in one flat directory. Import
these instead of reconstructing paths — moving an asset should be a one-line
change here, not a grep across six products.
"""
from __future__ import annotations

from pathlib import Path

OGMA_DIR = Path(__file__).resolve().parent
SHARED_DIR = OGMA_DIR.parent
REPO_ROOT = SHARED_DIR.parent

FONTS = OGMA_DIR / "fonts"
PALETTE = OGMA_DIR / "palette.json"

BAMBU_DIR = OGMA_DIR / "bambu"
BLANK_PROJECT = BAMBU_DIR / "blank_project.3mf"

# Read-only 3MFs whose plate preview thumbnails get embedded in every exported
# project. Named "bambu_work" until 2026-08-06, which read as scratch and got
# them untracked once — they are inputs. Nothing writes them.
PLATE_PREVIEWS = BAMBU_DIR / "plate_previews"

# Default job output. Overridden per-run by the CLI --out / the API's JOBS_ROOT.
OUT_ROOT = REPO_ROOT / "out"
