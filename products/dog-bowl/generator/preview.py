"""Build the dog bowl's browser preview: one role-tagged GLB.

The expensive half of a generate is the mesh build; the 3MF packaging on top of
it is what a preview doesn't need. So this runs `generate_meshes` into a scratch
directory and stops there.

Nothing here depends on colour. That is the point — see shared/ogma/preview.py.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import cooper_bowl_design as design
import styles
from ogma import preview as preview_lib

# Which filament colours each part of the finished stand. The viewer reads these
# off the node names, so this mapping is the whole contract between the
# generator and the 3D view.
LETTER_PART = "letter"
REFERENCE_PREFIX = "REFERENCE_ONLY"


def _role_for(mesh_name: str) -> str:
    if REFERENCE_PREFIX in mesh_name:
        # The stainless bowl the stand holds. Not printed, not a filament — the
        # viewer gives it a metal material. Shown because a stand without its
        # bowl reads as an odd hollow ring.
        return "bowl"
    if LETTER_PART in mesh_name:
        return "letters"
    return "stand"


def _clean_name(mesh_path: Path) -> str:
    stem = mesh_path.stem
    for prefix in ("assembly_", "REFERENCE_ONLY_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
    return stem


def build(
    name: str,
    style: str,
    font_style: str,
    out_path: Path,
    *,
    triangle_budget: int = preview_lib.DEFAULT_TRIANGLE_BUDGET,
) -> dict:
    """Generate meshes for this configuration and write a GLB to out_path."""
    import trimesh

    bowl_style = styles.get(style)
    if not bowl_style.generator_available:
        raise ValueError(f"Style {style!r} has no geometry yet")

    scratch = Path(tempfile.mkdtemp(prefix="ogma-preview-"))
    try:
        rail_outer = bowl_style.generate_meshes(scratch, name, font_style)
        mesh_dir = scratch / "meshes"

        parts = []
        have_bowl = False
        for path in preview_lib.assembled_meshes(mesh_dir):
            role = _role_for(path.name)
            have_bowl = have_bowl or role == "bowl"
            parts.append(
                preview_lib.Part(
                    role=role, name=_clean_name(path), mesh=trimesh.load_mesh(path)
                )
            )

        if not have_bowl:
            # Only the paw lattice exports the reference bowl as a mesh file.
            # Every style seats the *same* stainless bowl, so build it here
            # rather than teach three generators to write a file they don't
            # otherwise need — which would change their golden fingerprints for
            # a preview-only reason.
            parts.append(
                preview_lib.Part(role="bowl", name="metal_bowl", mesh=design.visual_bowl())
            )

        stats = preview_lib.to_glb(parts, out_path, triangle_budget=triangle_budget)
        stats["rail_outer_deg"] = rail_outer
        stats["style"] = bowl_style.id
        return stats
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Build a preview GLB")
    ap.add_argument("--name", default="MAX")
    ap.add_argument("--style", default=styles.DEFAULT_STYLE)
    ap.add_argument("--font-style", default="bold")
    ap.add_argument("--out", default="preview.glb")
    a = ap.parse_args()
    print(json.dumps(build(a.name, a.style, a.font_style, Path(a.out)), indent=2))
