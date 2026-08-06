"""Product-agnostic geometry helpers."""
from __future__ import annotations

import numpy as np


def unwrap_cylinder_u(x, y, r_mid: float, seam_deg: float = 0.0):
    """Map XY onto unwrapped arc-length u at radius `r_mid`.

    `seam_deg` chooses where the 0/360 discontinuity falls — put it somewhere
    the caller has no features, or shapes straddling the seam get torn in half.

    Moved out of cooper_bowl_design so the paint machinery doesn't have to
    import the dog bowl to unwrap a cylinder. The bowl keeps a thin wrapper that
    supplies its own PAW_PAINT_R_MID / PAW_PAINT_SEAM_DEG defaults.
    """
    th = np.degrees(np.arctan2(y, x))
    th = np.where(th < seam_deg, th + 360.0, th)
    return np.radians(th) * r_mid
