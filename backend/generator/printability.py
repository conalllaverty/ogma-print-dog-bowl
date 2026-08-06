#!/usr/bin/env python3
"""Manufacturability checks for FDM parts, run before anything is exported.

Why this exists
---------------
Every geometric validator in this repo compares the model to itself. That
catches interference and clearance bugs, and it caught plenty. What it cannot
catch is anything that only exists once the part is oriented on a bed and built
layer by layer -- and that is precisely the class of defect that kept reaching
the slicer:

* a cantilever whose first layer hangs in air, anchored at one end
* a wall thinner than two extrusion widths
* a void that would need support with no way to remove it
* an orientation transform that is secretly a mirror

The slicer finds these. So should we, before we ship a mesh.

The island/overhang analysis here is deliberately the same shape as a slicer's:
section the mesh at every layer height and compare each layer's footprint to the
one below it.

Usage:

    from printability import audit, PrintSpec
    report = audit(mesh, PrintSpec(), name="arm")
    if report.blocking:
        raise RuntimeError(report.summary())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union


@dataclass
class PrintSpec:
    """The machine and profile the part will actually be built on."""

    nozzle: float = 0.40
    layer_height: float = 0.16
    first_layer_height: float = 0.20
    # Beyond this the surface needs support. 45 deg is the usual FDM rule.
    overhang_limit_deg: float = 45.0
    # A wall this thin cannot be printed reliably; two extrusion widths.
    min_feature: float = 0.80
    # An unsupported region reaching further than this off the layer below will
    # droop. Note this measure distinguishes a bridge from a cantilever on its
    # own: a span anchored on two opposite sides reports half its width, while a
    # cantilever anchored at one end reports its full length.
    max_overhang_reach: float = 1.00
    block_overhang_reach: float = 5.00
    # Fraction of a new region's outline that must sit on the layer below for it
    # to count as supported. Below this it is a cantilever.
    min_anchor_ratio: float = 0.18
    # Islands smaller than this are meshing noise, not real features.
    min_island_area: float = 0.05


@dataclass
class Finding:
    kind: str
    detail: str
    z: float | None = None
    value: float | None = None
    blocking: bool = False
    layers: int = 1


@dataclass
class Report:
    name: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return any(f.blocking for f in self.findings)

    def add(self, *args, **kwargs) -> None:
        self.findings.append(Finding(*args, **kwargs))

    def summary(self) -> str:
        if not self.findings:
            return f"{self.name}: printable, no findings"
        lines = [f"{self.name}:"]
        for f in self.findings:
            mark = "BLOCK" if f.blocking else " warn"
            where = f" @Z{f.z:.2f}" if f.z is not None else ""
            span = f"  [{f.layers} layer{'s' if f.layers != 1 else ''}]" if f.z is not None else ""
            lines.append(f"  [{mark}]{where} {f.kind}: {f.detail}{span}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "blocking": self.blocking,
            "findings": [
                {
                    "kind": f.kind,
                    "detail": f.detail,
                    "z": None if f.z is None else round(f.z, 3),
                    "value": None if f.value is None else round(f.value, 4),
                    "blocking": f.blocking,
                    "layers": f.layers,
                }
                for f in self.findings
            ],
        }


def assert_rigid(matrix: np.ndarray, what: str = "transform") -> np.ndarray:
    """Reject a reflection posing as an orientation change.

    Scaling an axis by -1 to 'flip' a part has determinant -1. The model stays
    self-consistent if the same transform is used to undo it, so interference
    checks pass -- but the exported part is a mirror image, and a chiral feature
    like a snap clip then lands on the wrong side. Turning a real part over is a
    rotation; insist on one.
    """
    det = float(np.linalg.det(np.asarray(matrix)[:3, :3]))
    if det < 0.0:
        raise RuntimeError(
            f"{what} has determinant {det:+.3f} -- it is a REFLECTION, not a "
            "rotation. The exported part would be a mirror image."
        )
    if abs(det - 1.0) > 1e-6:
        raise RuntimeError(f"{what} is not rigid (determinant {det:.4f})")
    return matrix


def _layer_heights(mesh: trimesh.Trimesh, spec: PrintSpec) -> list[float]:
    z0, z1 = float(mesh.bounds[0][2]), float(mesh.bounds[1][2])
    heights = [z0 + spec.first_layer_height * 0.5]
    z = z0 + spec.first_layer_height + spec.layer_height * 0.5
    while z < z1:
        heights.append(z)
        z += spec.layer_height
    return heights


def _footprint(mesh: trimesh.Trimesh, z: float):
    section = mesh.section(plane_origin=[0.0, 0.0, z], plane_normal=[0.0, 0.0, 1.0])
    if section is None:
        return None
    try:
        planar, _ = section.to_planar(
            to_2D=np.eye(4), check=False
        )
    except Exception:
        return None
    polys = [p for p in planar.polygons_full if p.is_valid and p.area > 1e-9]
    if not polys:
        return None
    return unary_union(polys)


def _components(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def _anchor_ratio(region: Polygon, support) -> float:
    """What fraction of this region's outline actually sits on the layer below.

    This is what separates a bridge from a cantilever, and measuring distance to
    support does not: a beam floating in the middle of a 1.85 mm void is only
    ~1 mm from supported material on either side, so a distance metric calls it
    a short bridge. It isn't -- nothing is under it, and the slicer prints its
    first perimeter into air.

    A span anchored along two opposite edges has a high anchor ratio. A
    cantilever touching only at its root has a very low one.
    """
    if support is None or support.is_empty:
        return 0.0
    boundary = region.boundary
    if boundary.length <= 0.0:
        return 0.0
    free = boundary.difference(support.buffer(0.02))
    return max(0.0, 1.0 - free.length / boundary.length)


def _reach(region: Polygon, support) -> float:
    """How far this region extends beyond the material below it."""
    if support is None or support.is_empty:
        return float("inf")
    lo, hi = 0.0, 12.0
    if region.difference(support.buffer(hi)).is_empty is False:
        return hi
    for _ in range(16):
        mid = (lo + hi) / 2.0
        if region.difference(support.buffer(mid)).is_empty:
            hi = mid
        else:
            lo = mid
    return hi


def audit(
    mesh: trimesh.Trimesh,
    spec: PrintSpec | None = None,
    name: str = "part",
) -> Report:
    """Layer-by-layer printability audit of a mesh in PRINT orientation."""
    spec = spec or PrintSpec()
    report = Report(name=name)

    # --- detached shells ---------------------------------------------------
    # A part exported as several kissing shells still slices solid in Bambu
    # Studio, so this never shows up as a warning there -- but it is one
    # clearance change away from loose parts on the bed.
    shells = mesh.split(only_watertight=False)
    if len(shells) > 1:
        volumes = sorted((abs(float(s.volume)) for s in shells), reverse=True)
        report.add(
            "detached-shells",
            f"exported as {len(shells)} separate shells "
            f"(largest {volumes[0]:.1f} mm3, smallest {volumes[-1]:.2f} mm3) -- "
            "weld them or they may print as loose islands",
            value=float(len(shells)),
            blocking=True,
        )

    # --- surface overhang, the cheap global signal -------------------------
    normals = mesh.face_normals
    areas = mesh.area_faces
    centres = mesh.triangles_center
    limit = math.cos(math.radians(90.0 - spec.overhang_limit_deg))
    steep = (normals[:, 2] < -limit) & (centres[:, 2] > mesh.bounds[0][2] + 0.30)
    steep_area = float(areas[steep].sum())
    if steep_area > 0.5:
        report.add(
            "overhang-surface",
            f"{steep_area:.1f} mm² of downward faces steeper than "
            f"{spec.overhang_limit_deg:.0f}° ({steep_area / mesh.area * 100:.1f}% of the part)",
            value=steep_area,
        )

    # --- layer analysis, the one that actually catches cantilevers ---------
    previous = None
    for z in _layer_heights(mesh, spec):
        current = _footprint(mesh, z)
        if current is None:
            previous = None
            continue
        if previous is None:
            previous = current
            continue

        fresh = current.difference(previous)
        for region in _components(fresh):
            if region.area < spec.min_island_area:
                continue
            touching = region.intersection(previous.buffer(1e-6))
            if touching.is_empty:
                report.add(
                    "unsupported-island",
                    f"{region.area:.2f} mm² of material begins with nothing "
                    "beneath it — the slicer will call this a floating "
                    "cantilever and it will droop",
                    z=z,
                    value=region.area,
                    blocking=True,
                )
                continue
            anchor = _anchor_ratio(region, previous)
            reach = _reach(region, previous)
            if anchor < spec.min_anchor_ratio:
                report.add(
                    "floating-cantilever",
                    f"{region.area:.2f} mm² of new material with only "
                    f"{anchor * 100:.0f}% of its outline on the layer below — "
                    "it is a cantilever hanging in air, not a bridge, and its "
                    "first perimeter will be extruded into nothing",
                    z=z,
                    value=region.area,
                    blocking=True,
                )
            elif reach > spec.max_overhang_reach:
                report.add(
                    "overhang-reach",
                    f"{region.area:.2f} mm² reaches {reach:.2f} mm beyond the "
                    f"layer below, anchored on {anchor * 100:.0f}% of its "
                    "outline (a bridge, but a long one)",
                    z=z,
                    value=reach,
                    blocking=reach > spec.block_overhang_reach,
                )

        # --- thin features -------------------------------------------------
        eroded = current.buffer(-spec.min_feature / 2.0)
        if eroded.is_empty:
            report.add(
                "thin-feature",
                f"entire layer is thinner than {spec.min_feature:.2f} mm "
                f"({spec.min_feature / spec.nozzle:.0f} extrusion widths)",
                z=z,
                blocking=True,
            )
        else:
            lost = current.difference(eroded.buffer(spec.min_feature / 2.0))
            for region in _components(lost):
                if region.area < 0.20:
                    continue
                report.add(
                    "thin-feature",
                    f"{region.area:.2f} mm² narrower than {spec.min_feature:.2f} mm",
                    z=z,
                    value=region.area,
                )
        previous = current

    # collapse repeat findings so a tall thin wall is one line, not eighty
    return _collapse(report)


def _collapse(report: Report) -> Report:
    """One line per kind of problem, not one per layer."""
    merged: dict[str, Finding] = {}
    order: list[str] = []
    for f in report.findings:
        key = f.kind if f.z is not None else f"{f.kind}|{f.detail}"
        if key not in merged:
            merged[key] = Finding(
                kind=f.kind,
                detail=f.detail,
                z=f.z,
                value=f.value,
                blocking=f.blocking,
            )
            order.append(key)
            continue
        existing = merged[key]
        existing.layers += 1
        existing.blocking = existing.blocking or f.blocking
        # keep the worst example as the representative
        if f.value is not None and (existing.value is None or f.value > existing.value):
            existing.detail = f.detail
            existing.z = f.z
            existing.value = f.value
    out = Report(name=report.name)
    out.findings = [merged[k] for k in order]
    return out
