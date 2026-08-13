#!/usr/bin/env python3
"""Mass and inertia of the Solo as PRINTED, not as modelled.

Why this file exists
--------------------
I told Conall the core was "37% of the mass for 16% of the inertia" and called
shape "the free lever". That arithmetic was run on the SOLID mesh. The part he
prints is a 2-wall shell with 25% gyroid inside it, so the middle of the disc is
already mostly air -- there is far less mass sitting at small radius than the
solid model implies, and therefore far less to win by hollowing it.

This module redoes the sums on a shell+infill model so the recommendation is
quoted against the thing that comes off the plate.

Model
-----
Voxelise at PITCH, then classify each solid voxel as shell or infill using TWO
separate distance fields, because a printed shell is strongly anisotropic and a
single 3D distance transform gets both directions wrong at once:

  * wall distance -- measured in-plane, layer by layer, so a voxel just under
    the top face is not mistaken for a sidewall
  * face distance -- measured along Z only, so an overhang ceiling counts as a
    face exactly the way the slicer treats it

Calibration
-----------
Two corrections, both against something external rather than against my own
arithmetic:

1. Voxels overstate volume at the boundary (a 0.5 mm cube either is or is not
   inside; the real surface cuts through it). Normalised so a 100% part weighs
   exactly what the mesh says.
2. The geometric shell under-predicts what the slicer actually lays down --
   solid layers over sparse infill, ensure-vertical-shell-thickness, and thin
   features where the walls simply meet. `calibrated_shell()` returns the shell
   thickness fitted to reproduce Bambu's own 16.74 g slice of a one-up Solo.

Without (2) the model says 13.4 g for a part the slicer says is 16.7 g, and
every delta computed from it would be 20% out in the direction that flatters
the infill lever. Fitting to the slicer is not cheating -- it is the only number
in this file that came from outside my own head.

Inertia is about the spin axis: I = sum(m * r^2), r measured from Z.
Spin time under a hand flick scales as sqrt(I) at fixed input energy and fixed
bearing drag, so the honest headline is the sqrt, not the raw percentage.
"""

from __future__ import annotations

import numpy as np
import trimesh
from scipy import ndimage

PLA_DENSITY = 1.24e-3      # g/mm3, Bambu PLA Matte
PITCH = 0.5                # mm voxel

# The shipped Solo profile, read out of the project rather than assumed:
#   wall_loops 5 at 0.42 line width  -> 2.10 mm of sidewall
#   6 bottom + 6 top layers at 0.16  -> 0.96 mm each face
# The shell is strongly anisotropic, so a single distance transform gets it
# wrong in both directions at once. Walls and faces are measured separately.
WALL_MM = 5 * 0.42
TOP_MM = 6 * 0.16
BOTTOM_MM = 6 * 0.16

# Ground truth to calibrate against: Bambu sliced a one-up Solo at 16.74 g of
# model. Any model that cannot reproduce that number has no business predicting
# what happens when we change it.
SLICED_MASS_G = 16.74

# Fitted so the model reproduces SLICED_MASS_G on the shipped Solo at 25%
# gyroid: geometric shell x 1.5 lands at 16.68 g against the slicer's 16.74 g.
# Solved by sweep, not assumed -- see fit_shell_factor() to redo it if the print
# profile changes.
SHELL_FIT = 1.5


def calibrated_shell(factor: float = SHELL_FIT) -> tuple[float, float]:
    """(wall_mm, face_mm) to hand to PrintedBody.set_shell()."""
    return WALL_MM * factor, max(TOP_MM, BOTTOM_MM) * factor


class PrintedBody:
    """A voxelised body, split into shell and interior once.

    Voxelising costs ~45 s, so it is done exactly once per geometry and then
    queried for as many infill densities as we like. Every earlier bug in this
    project that survived review did so because two derived numbers were
    computed from two different snapshots of the same thing; caching the grid
    means every density below is answering about the identical solid.
    """

    def __init__(
        self,
        mesh: trimesh.Trimesh,
        pitch: float = PITCH,
        wall_mm: float = WALL_MM,
        top_mm: float = TOP_MM,
        bottom_mm: float = BOTTOM_MM,
    ) -> None:
        vox = mesh.voxelized(pitch=pitch).fill()
        filled = np.asarray(vox.matrix, dtype=bool)

        # Walls: in-plane distance to the outside, computed layer by layer, so a
        # voxel near the top face is not mistaken for wall.
        wall_dist = np.zeros(filled.shape, dtype=float)
        for k in range(filled.shape[2]):
            layer = np.pad(filled[:, :, k], 1, constant_values=False)
            wall_dist[:, :, k] = ndimage.distance_transform_edt(layer)[1:-1, 1:-1]

        # Faces: distance along Z only, so an overhang ceiling counts as a face
        # exactly the way the slicer treats it.
        up = np.pad(filled, ((0, 0), (0, 0), (1, 1)), constant_values=False)
        face_dist = ndimage.distance_transform_edt(
            up, sampling=(1e6, 1e6, pitch)
        )[:, :, 1:-1]

        indices = np.argwhere(filled)
        self._wall_dist = wall_dist[filled] * pitch
        self._face_dist = face_dist[filled]

        self.pitch = pitch
        self.voxel_mass = pitch ** 3 * PLA_DENSITY
        self.set_shell(wall_mm, max(top_mm, bottom_mm))
        points = vox.indices_to_points(indices)
        # spin axis is the bearing bore, which is the mesh's own XY centre
        centre = mesh.bounding_box.centroid
        self.r = np.hypot(points[:, 0] - centre[0], points[:, 1] - centre[1])
        self.z = points[:, 2]
        self.solid_volume_mm3 = float(mesh.volume)

        # Voxels overstate volume at the boundary (a 0.5 mm cube either is or is
        # not inside; the real surface cuts through it). Normalise so a 100%
        # part weighs exactly what the mesh says it weighs, and every density
        # below inherits the correction.
        self.calibration = self.solid_volume_mm3 / (
            filled.sum() * pitch ** 3
        )
        self.voxel_mass *= self.calibration

    def set_shell(self, wall_mm: float, face_mm: float) -> None:
        """Re-threshold the cached distance fields. Voxelising costs ~50 s;
        changing shell thickness costs nothing, so sweeps stay affordable."""
        self.wall_mm = wall_mm
        self.face_mm = face_mm
        self.is_shell = (self._wall_dist <= wall_mm) | (self._face_dist <= face_mm)

    def _weights(self, infill: float) -> np.ndarray:
        return np.where(self.is_shell, 1.0, infill)

    def summary(self, infill: float) -> dict:
        w = self._weights(infill)
        mass = float(w.sum() * self.voxel_mass)
        inertia = float((w * self.r ** 2).sum() * self.voxel_mass)
        return {
            "infill": infill,
            "mass_g": mass,
            "inertia_g_mm2": inertia,
            "shell_mass_g": float(self.is_shell.sum() * self.voxel_mass),
            "infill_mass_g": float((~self.is_shell).sum() * infill * self.voxel_mass),
            "radius_of_gyration_mm": float(np.sqrt(inertia / mass)),
            "solid_volume_mm3": self.solid_volume_mm3,
        }

    def bands(self, infill: float, edges) -> list[dict]:
        """Where the mass and the inertia actually live, band by band."""
        w = self._weights(infill)
        total_m = (w * self.voxel_mass).sum()
        total_i = (w * self.r ** 2 * self.voxel_mass).sum()
        rows = []
        for low, high in zip(edges[:-1], edges[1:]):
            sel = (self.r >= low) & (self.r < high)
            m = (w[sel] * self.voxel_mass).sum()
            i = (w[sel] * self.r[sel] ** 2 * self.voxel_mass).sum()
            rows.append(
                {
                    "band_mm": f"R{low:g}-{high:g}",
                    "mass_g": round(float(m), 2),
                    "mass_pct": round(100.0 * float(m / total_m), 1),
                    "inertia_pct": round(100.0 * float(i / total_i), 1),
                }
            )
        return rows


def fit_shell_factor(
    mesh: trimesh.Trimesh,
    target_mass_g: float = SLICED_MASS_G,
    infill: float = 0.25,
    candidates=None,
) -> float:
    """Solve for the shell multiplier that reproduces a known slicer mass.

    Re-run this whenever the print profile changes -- wall count, layer height
    or shell layers all move it, and a stale factor would quietly bias every
    delta computed afterwards.
    """
    body = PrintedBody(mesh)
    best, best_error = None, float("inf")
    for factor in candidates or np.arange(0.8, 2.6, 0.05):
        body.set_shell(*calibrated_shell(float(factor)))
        error = abs(body.summary(infill)["mass_g"] - target_mass_g)
        if error < best_error:
            best, best_error = float(factor), error
    return best
