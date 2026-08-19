"""Millimetre <-> Fusion database-unit conversion.

Fusion's API internal length unit is CENTIMETRES, always, regardless of what
the document's display units are set to:

    "These unit types are known as database units... For Design, these units
     are: Lengths - Centimeters (cm), Angles - Radians (rad)... The internal
     units always use these types without any exceptions."
    -- Fusion API Reference, Units_UM.htm

Every raw float handed to or read back from the API is therefore cm. The bowl
geometry is authored in mm. Rather than sprinkle `/ 10` through the builders,
this module is the only place the factor appears.

Two rules for the rest of the package:

  * geometry that should end up as a live, editable dimension goes in as a
    STRING expression (`mm(12.5)` -> "12.5 mm", or a parameter name) so the
    unit is explicit in the timeline and survives a document-unit change;
  * geometry that is a raw Point3D coordinate has no expression form, so it
    uses `cm()`.
"""

from __future__ import annotations

import math

MM_PER_CM = 10.0


def cm(millimetres: float) -> float:
    """mm -> Fusion database units (cm). Use for Point3D / raw doubles."""
    return float(millimetres) / MM_PER_CM


def to_mm(database_units: float) -> float:
    """Fusion database units (cm) -> mm. Use when reading values back."""
    return float(database_units) * MM_PER_CM


def mm(millimetres: float) -> str:
    """mm -> an explicit-unit expression string for ValueInput.createByString."""
    return "{:.6f} mm".format(float(millimetres))


def deg(degrees: float) -> str:
    """degrees -> an explicit-unit expression string."""
    return "{:.6f} deg".format(float(degrees))


def rad(degrees: float) -> float:
    """degrees -> radians. Angles read back from the API are always radians."""
    return math.radians(float(degrees))
