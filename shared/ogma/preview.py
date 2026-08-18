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

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import trimesh

log = logging.getLogger("ogma.preview")

# Bump whenever this module changes what it puts in the GLB.
#
# The preview URL is `/previews/<key>.glb` where the key hashes the *geometry
# parameters* — name, style, lettering — and the response is served
# `immutable, max-age=31536000`. That was sound only while the bytes behind a
# key could never change. They can: this module decides decimation, welding and
# what a part is called, and changing any of that produces a different file at
# the same URL. A year-long immutable cache then pins every returning browser
# to the old one.
#
# It happened. Fixing the decimation collapse changed the GLB and not the key,
# so a browser that had loaded the broken shell kept serving it from disk and
# the fix appeared to have done nothing.
#
# Feeding this into the key means a pipeline change abandons the old URLs
# instead of overwriting them. Old files age out of the cache on their own.
#
# 1: original
# 2: decimation validated against volume/watertightness; budget 90k -> 200k
# 3: letters seat on the wall (the stale-default face_r bug), budget -> 320k
PREVIEW_FORMAT_VERSION = 3

# A printed stand is 120k-510k triangles.
#
# This was 90k, chosen when decimation silently never ran, so nothing tested it.
# Once it did run, 90k was far too tight: it drove the wave upper to 12% of its
# volume, and the visible faceting on the wave lower was decimation flattening a
# 256-column wrapped profile that was already near its minimum.
#
# 320k leaves the paw lattice and the wave untouched entirely, and asks the
# honeycomb and fluted drums for a reduction of about a third. Measured: both
# simplify without damage down to 100k faces and only fail below ~66k, so this
# is well inside the safe range — it is set by how much groove detail survives,
# not by how far the simplifier can go. The grooves are chamfered rather than
# square, and they are the first thing a reduction softens.
DEFAULT_TRIANGLE_BUDGET = 320_000

# How much volume a decimation may move before it is treated as damage.
# Well-behaved simplification of these parts lands within 0.1%; the failures are
# not marginal, they are 12% and 40%.
MAX_VOLUME_DRIFT = 0.02

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


def _damage(original: trimesh.Trimesh, simplified: trimesh.Trimesh) -> str | None:
    """Why this simplification should be rejected, or None if it is sound.

    Checked rather than trusted, because the failure mode is silent: the
    simplifier returns a perfectly well-formed mesh of the wrong shape. Two
    signals catch it, and both are cheap next to the decimation itself.
    """
    if len(simplified.faces) == 0:
        return "no faces left"

    # A part that was a closed solid and no longer is has had its surfaces
    # driven through each other. Nothing about a preview justifies that.
    if original.is_watertight and not simplified.is_watertight:
        return "was watertight, no longer is"

    # Volume is the cheap proxy for "same shape". Only meaningful when both are
    # closed — an open mesh's volume is not a quantity.
    if original.is_watertight and simplified.is_watertight and original.volume:
        drift = abs(simplified.volume - original.volume) / abs(original.volume)
        if drift > MAX_VOLUME_DRIFT:
            return f"volume moved {drift * 100:.1f}%"

    return None


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
    undecimated: list[str] = []

    for part in parts:
        mesh = part.mesh
        before += len(mesh.faces)
        target = targets[part.node_name]
        if len(mesh.faces) > target:
            try:
                simplified = mesh.simplify_quadric_decimation(face_count=target)
                reason = _damage(mesh, simplified)
                if reason:
                    # Keep the original. Quadric decimation has a floor for any
                    # given shape, and pushed past it `fast_simplification` does
                    # not fail — it returns a mesh. On the wave upper, a thin
                    # wrapped shell, asking for 68,823 faces gave back 79,534
                    # faces enclosing 12% of the volume, with the inner and
                    # outer surfaces passing through each other. That is what
                    # was on screen: a collapsed, holed shell.
                    #
                    # A preview may be heavier than budgeted. It may not be a
                    # different shape from the thing that prints.
                    log.warning(
                        "rejected decimation of %s (%d -> %d faces): %s",
                        part.node_name, len(mesh.faces), len(simplified.faces), reason,
                    )
                    undecimated.append(part.node_name)
                else:
                    mesh = simplified
            except Exception as exc:  # noqa: BLE001
                # Decimation is a nicety. A part that refuses to simplify (open
                # edges, degenerate faces) should still appear in the preview at
                # full resolution rather than vanish from it.
                #
                # But it must not fail *quietly*. `fast_simplification` was
                # missing from requirements.txt, so this raised for every part of
                # every preview and the budget above was never once applied — an
                # 8.4 MB honeycomb went out looking exactly like a 2 MB one, and
                # the only evidence was triangles_before == triangles in a stats
                # dict nobody reads. Say so, and report it in the stats.
                log.warning(
                    "could not decimate %s (%d faces, target %d): %s",
                    part.node_name, len(mesh.faces), target, exc,
                )
                undecimated.append(part.node_name)
        after += len(mesh.faces)
        # Exported without normals, with vertices welded. The viewer rebuilds
        # them with a crease angle (three's `toCreasedNormals`), which keeps
        # hard edges hard and curved surfaces smooth.
        #
        # Doing that here instead would mean splitting vertices along every
        # crease and writing a NORMAL accessor — measured at roughly double the
        # file size (the honeycomb went 5.4 MB to 10.2 MB) for a result the
        # browser can compute in milliseconds from the compact form.
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
        # Empty is the healthy case. Non-empty means the asset is bigger than
        # the budget promises and the reason is in the log.
        "undecimated": undecimated,
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
