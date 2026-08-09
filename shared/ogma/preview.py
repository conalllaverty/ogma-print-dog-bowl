"""Turn printable meshes into something a browser can show.

The designer needs a picture of what it will print. The obvious way — render an
image server-side per configuration — is wrong here, because the thing a
customer changes most often is *colour*, and colour is not geometry. Re-running
a 2-8 s mesh build to show Caramel instead of Ivory White would be absurd.

So the preview asset is geometry only, and it carries the *role* of each part
rather than its colour:

    stand__assembly_paw_panel      letters__assembly_letter_1_O      bowl__…

The viewer groups by that prefix and assigns materials at draw time. Changing a
filament is then a material swap in the browser — instant, no server, no
rebuild. The asset is keyed on what actually changes it (name, style,
lettering) and nothing else.

Roles are encoded in the node name because glTF node names survive round-trips
that drop custom extras. The separator is `__` and that is not cosmetic:
three.js runs every node name through `PropertyBinding.sanitizeNodeName`, which
strips the characters its animation-binding syntax reserves — `. : / [ ]` and
whitespace. An earlier `::` separator arrived in the browser as `standpaw_panel`
and every part silently fell back to one material, so the whole model rendered
in a single colour. Underscores survive.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import trimesh

# A printed stand is ~150k triangles. Below roughly this the model still reads
# as itself at screen size, and the GLB stays under ~2 MB — small enough that
# the download is never the thing the customer waits for.
DEFAULT_TRIANGLE_BUDGET = 90_000

# Separator between role and part in a node name. Must contain no character
# three.js's PropertyBinding.sanitizeNodeName strips (`. : / [ ]`, whitespace).
ROLE_SEP = "__"

# Never decimate a part below this: small parts (letters, seat rings) lose their
# silhouette long before large ones do, and the letters are the product.
MIN_FACES_PER_PART = 600


@dataclass(frozen=True)
class Part:
    """One piece of the assembled product."""

    role: str  # "stand", "letters", "bowl" — whatever the product's viewer knows
    name: str  # human-ish id, unique within the preview
    mesh: trimesh.Trimesh

    @property
    def node_name(self) -> str:
        # See the module docstring: `__`, never `::`.
        return f"{self.role}{ROLE_SEP}{self.name}"


def _budgeted_face_counts(
    parts: Sequence[Part], budget: int
) -> dict[str, int]:
    """Share the triangle budget out in proportion to each part's size.

    Proportional rather than equal: on a paw-lattice stand one panel carries 85%
    of the triangles and the letters almost none. An equal split would smash the
    panel flat while leaving the letters untouched.
    """
    total = sum(len(p.mesh.faces) for p in parts)
    if total <= budget:
        return {p.node_name: len(p.mesh.faces) for p in parts}

    counts: dict[str, int] = {}
    for p in parts:
        share = len(p.mesh.faces) / total
        counts[p.node_name] = max(MIN_FACES_PER_PART, int(budget * share))
    return counts


def to_glb(
    parts: Iterable[Part],
    out_path: Path,
    *,
    triangle_budget: int = DEFAULT_TRIANGLE_BUDGET,
) -> dict:
    """Write a role-tagged GLB. Returns stats worth logging."""
    parts = list(parts)
    if not parts:
        raise ValueError("nothing to preview")

    targets = _budgeted_face_counts(parts, triangle_budget)
    scene = trimesh.Scene()
    before = after = 0

    for part in parts:
        mesh = part.mesh
        before += len(mesh.faces)
        target = targets[part.node_name]
        if len(mesh.faces) > target:
            try:
                mesh = mesh.simplify_quadric_decimation(face_count=target)
            except Exception:
                # Decimation is a nicety. A part that refuses to simplify (open
                # edges, degenerate faces) should still appear in the preview at
                # full resolution rather than vanish from it.
                pass
        after += len(mesh.faces)
        scene.add_geometry(
            mesh, node_name=part.node_name, geom_name=part.node_name
        )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(scene.export(file_type="glb"))

    return {
        "parts": len(parts),
        "triangles_before": before,
        "triangles": after,
        "bytes": out_path.stat().st_size,
        "roles": sorted({p.role for p in parts}),
    }


def assembled_meshes(mesh_dir: Path) -> list[Path]:
    """Pick the assembled view out of a mesh directory.

    Generators write each part twice — once flat in print orientation, once
    positioned in the finished assembly (`assembly_<part>.stl`). A preview wants
    the second. Parts that exist only once (a base that prints in the same
    orientation it sits in) have no `assembly_` twin and are taken as they are.

    Pairing is by *suffix*, not equality, because the two names don't always
    match: the paw lattice writes `cooper_paw_panel.stl` alongside
    `assembly_paw_panel.stl`, while the fluted drum writes `fluted_body.stl`
    alongside `assembly_fluted_body.stl`. Requiring equality would silently drag
    every flat-packed print copy into the preview, laid over the assembly.

    `OPTIONAL_*` is a fit gauge, not part of the product.
    """
    mesh_dir = Path(mesh_dir)
    stls = sorted(p for p in mesh_dir.glob("*.stl") if not p.name.startswith("OPTIONAL_"))
    assembled = [p for p in stls if p.name.startswith("assembly_")]
    assembled_stems = [p.stem[len("assembly_") :] for p in assembled]

    out = list(assembled)
    for p in stls:
        if p.name.startswith("assembly_"):
            continue
        if any(p.stem.endswith(stem) for stem in assembled_stems):
            continue  # the print-orientation twin of a part we already have
        out.append(p)
    return sorted(out)
