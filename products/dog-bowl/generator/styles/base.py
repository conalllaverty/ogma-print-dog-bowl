"""One bowl style = one object implementing this protocol.

Adding a style used to mean four coordinated edits: a constant + tuple entry +
STYLE_META block in geometry_config, an if/elif branch in pipeline, and a
configure_*_objects / build_*_project pair in build_bambu_project. Miss one and
the failure is a KeyError somewhere unrelated.

Now a style is one module implementing `BowlStyle` plus one line in the
registry. `STYLE_META`, `STYLES` and the API's `STYLE_CATALOG` all derive from
the registry, so the backend and the web configurator pick a new style up with
no further edits.

Note this deliberately does NOT unify the three build_*_project functions in
build_bambu_project.py. They differ in plate composition, not just parameters,
and collapsing them is a separate change that wants its own verification pass.
The registry removes the dispatch duplication; the builder dedup is still owed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


class StyleImpl(Protocol):
    def generate_meshes(self, job_dir: Path, name: str, font_style: str) -> float:
        """Write meshes into job_dir/meshes. Return the name-rail outer angle."""
        ...

    def build_project(self, **kwargs) -> Path:
        """Package those meshes into a Bambu 3MF."""
        ...


@dataclass(frozen=True)
class BowlStyle:
    """Everything the pipeline, the API and the web UI need to know."""

    id: str
    name: str
    description: str
    available: bool
    # Fuzzy skin is painted per-facet from a product-specific mask; only styles
    # that supply a FuzzyPainter can offer it. The web UI hides the toggle when
    # this is False rather than hard-coding `style === "cooper"`.
    supports_fuzzy: bool
    # Goes into the filename: {NAME}_{output_suffix}_P2S.3mf
    output_suffix: str
    generate_meshes: Callable[..., float]
    build_project: Callable[..., Path]
    # Set False for a style whose geometry is not wired up yet, so it can appear
    # in the catalogue as "coming soon" without the pipeline accepting a job.
    generator_available: bool = True

    def meta(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "available": self.available,
            "generator_available": self.generator_available,
        }

    def catalog_entry(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "available": self.available,
            "supports_fuzzy": self.supports_fuzzy,
        }
