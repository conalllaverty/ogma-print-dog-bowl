"""The name — pockets in the wall, and matching letter solids to print separately.

How this differs from the trimesh generator
-------------------------------------------
The Python generator rasterises each glyph to a pixel mask, traces it to a
shapely polygon, extrudes that polygon on a per-letter tangent frame, and cuts
the concave back with a cylinder. It reimplements text layout because it has to:
trimesh has no concept of a font on a curved surface.

Fusion does. `EmbossFeature` is the wrap-text-onto-a-curved-face command, so the
whole per-letter packing/tangent-frame apparatus collapses into two features:

    1. emboss the name INTO the wall at -pocket_depth      -> the pockets
    2. emboss the same name OUT of a thin backing shell,
       then split the shell away                            -> the letter solids

Step 2 is the only non-obvious bit. Emboss can add material in the shape of the
text but cannot keep the text and throw away the surround, so the letters are
grown off a sacrificial 0.5 mm shell whose outer surface sits exactly at the
pocket floor radius. Splitting at that radius leaves letter solids whose backs
are already the right concave cylinder — the same seating the generator gets by
booleaning against a cylinder, without a boolean.

Two deliberate consequences:

  * the letter's outer face is a coaxial cylinder rather than the generator's
    flat chord. Across a 15 mm cap height at R87 that is 0.3 mm of difference,
    and the curved version holds a more even proud height across the glyph.
  * letter spacing comes from the font's own metrics via `characterSpacing`
    rather than from `pack_letter_arc_centers`. The fit gate is still enforced,
    just measured from the laid-out text instead of predicted before it exists.
"""

from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from . import config as cfg
from .api import (
    collection,
    cut,
    largest_profile,
    offset_plane,
    pt,
    polyline,
    revolve,
    sketch_on,
    sketch_text,
    split_body,
    text_width_mm,
    v_mm,
)
from .units import cm


class NameFitError(ValueError):
    """The name is too wide for the wall it has to sit on."""


def normalise(name: str) -> str:
    """A-Z only, 2-8 characters — the same gate the generator applies."""
    cleaned = "".join(ch for ch in (name or "").upper() if ch.isalpha())
    if len(cleaned) < 2:
        raise NameFitError(
            "Name needs at least 2 letters (A-Z). Got {!r}.".format(name)
        )
    return cleaned[: cfg.MAX_NAME_LEN]


def resolve_font(ui, style_id: str):
    """(font_name, bold, warning_or_None) for a letter style id.

    Fusion substitutes a default face for an unknown fontName without telling
    you, so an uninstalled font produces a model that builds cleanly and looks
    wrong. There is no public font-enumeration API, so this cannot pre-check —
    it returns the intended family and lets the caller surface the note.
    """
    family, bold, description = cfg.FONT_STYLES.get(
        style_id, cfg.FONT_STYLES[cfg.DEFAULT_FONT_STYLE]
    )
    note = (
        "Letter style '{}' uses {}. If that family is not installed, Fusion "
        "will silently substitute another face — install it, or pick a "
        "different letter style.".format(style_id, description)
    )
    return family, bold, note


# --------------------------------------------------------------------------
# Layout measurement
# --------------------------------------------------------------------------

def _estimate_width_mm(name: str, height_mm: float) -> float:
    """Fallback width when the SketchText bounding box is unavailable.

    0.62 em per character is the mean advance width across the seven shipped
    letter faces at their tested weights; it is only ever used to keep the
    build alive when the measurement path fails.
    """
    return len(name) * height_mm * 0.62


def measure_name(component, name: str, height_mm: float, font_name: str,
                 bold: bool, spacing_mm: float):
    """Lay the name out once on a scratch sketch and measure it.

    The scratch sketch is deleted before returning, so it never reaches the
    timeline of the delivered model.
    """
    sketch = sketch_on(component, component.parentDesign.rootComponent.xZConstructionPlane,
                       "ogma_scratch_measure")
    try:
        estimate = _estimate_width_mm(name, height_mm)
        text = sketch_text(
            sketch, name, height_mm, font_name, bold,
            corner_mm=(-estimate, -height_mm),
            diagonal_mm=(estimate, height_mm),
        )
        width = text_width_mm(text, estimate)
    finally:
        try:
            sketch.deleteMe()
        except Exception:
            pass
    # setAsMultiLine centres the block, so inter-character spacing widens it by
    # one gap per join.
    return width + max(0, len(name) - 1) * spacing_mm


def check_fit(width_mm: float, face_radius_mm: float) -> float:
    """Half-angle the name subtends. Raises if it exceeds the locked gate.

    MAX_RAIL_OUTER_DEG is 45 deg and is a product decision, not a geometric
    limit: past it the name wraps far enough around the drum that it stops
    reading as a word from a normal viewing angle.
    """
    half_angle = math.degrees(
        (width_mm * 0.5 + cfg.LETTER_END_MARGIN) / face_radius_mm
    )
    if half_angle > cfg.MAX_RAIL_OUTER_DEG:
        raise NameFitError(
            "Name is too wide: it needs +/-{:.1f} deg of wall and the limit is "
            "+/-{:.0f} deg. Use fewer letters or the 'condensed' letter "
            "style.".format(half_angle, cfg.MAX_RAIL_OUTER_DEG)
        )
    return half_angle


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def _outer_cylindrical_faces(body, target_radius_mm: float, tol_mm: float = 0.35):
    """Every cylindrical face on `body` whose radius matches, within tol.

    Emboss needs the faces it is projecting onto. Picking them by radius rather
    than by index means the selection survives an edit that reorders faces,
    which reordering absolutely will happen the first time you change a
    parameter upstream.
    """
    hits = []
    want = cm(target_radius_mm)
    for i in range(body.faces.count):
        face = body.faces.item(i)
        geom = face.geometry
        if isinstance(geom, adsk.core.Cylinder):
            if abs(geom.radius - want) <= cm(tol_mm):
                hits.append(face)
    return hits


def _text_sketch(component, plane, name, height_mm, font_name, bold,
                 centre_z_mm, width_mm, spacing_mm, sketch_name):
    """Sketch the name centred at (0, centre_z) in world terms on `plane`.

    The sketch is created on a plane offset from XZ, so sketch-local X is world
    X and sketch-local Y is world Z. `setAsMultiLine` takes a corner and its
    diagonal and centres the block inside that rectangle, so the box is built
    symmetric about the intended centre and the alignment does the rest.
    """
    sketch = sketch_on(component, plane, sketch_name)
    half_w = max(width_mm, height_mm) * 0.75 + 5.0
    half_h = height_mm
    text = sketch_text(
        sketch, name, height_mm, font_name, bold,
        corner_mm=(-half_w, centre_z_mm - half_h),
        diagonal_mm=(half_w, centre_z_mm + half_h),
    )
    return sketch, text


def emboss(component, faces, sketch_text_obj, depth_mm: float, name: str = ""):
    """Wrap `sketch_text_obj` onto `faces`. Negative depth engraves.

    EmbossFeatures.createInput(profiles, faces, depth) -- profiles may be
    SketchText objects, which is exactly the case here. isTangentChain is left
    at its default True so a face that has been split by an earlier feature
    still takes the whole name.
    """
    embosses = component.features.embossFeatures
    inp = embosses.createInput(
        [sketch_text_obj], list(faces), v_mm(depth_mm)
    )
    feat = embosses.add(inp)
    if name:
        feat.name = name
    return feat


def build_pockets(component, body, wall_radius_mm, centre_z_mm, name,
                  height_mm, font_name, bold, pocket_depth_mm, spacing_mm,
                  plane_base=None):
    """Engrave the glyph pockets into `body`. Returns (feature, sketch, text)."""
    plane_base = plane_base or component.xZConstructionPlane
    width = measure_name(component, name, height_mm, font_name, bold, spacing_mm)
    check_fit(width, wall_radius_mm + cfg.LETTER_THICKNESS)

    # Sketch plane sits outside the wall so the text projects inward onto it.
    plane = offset_plane(component, plane_base, -(wall_radius_mm + 10.0),
                         "ogma_name_plane")
    sketch, text = _text_sketch(
        component, plane, name, height_mm, font_name, bold,
        centre_z_mm, width, spacing_mm, "ogma_name_text",
    )
    faces = _outer_cylindrical_faces(body, wall_radius_mm)
    if not faces:
        raise RuntimeError(
            "No cylindrical face at R{:.2f} mm to engrave the name on. The "
            "wall radius and the letter plane have drifted apart.".format(
                wall_radius_mm)
        )
    feat = emboss(component, faces, text, -abs(pocket_depth_mm),
                  "Name pockets")
    return feat, sketch, text, width


def build_letter_solids(component, wall_radius_mm, centre_z_mm, name,
                        height_mm, font_name, bold, pocket_depth_mm,
                        letter_thickness_mm, spacing_mm, half_angle_deg,
                        plane_base=None):
    """Grow the printable letters off a sacrificial shell and split them free.

    Returns the list of letter BRepBody objects.
    """
    plane_base = plane_base or component.xZConstructionPlane
    root = component
    floor_r = wall_radius_mm - pocket_depth_mm
    shell_thickness = 0.5
    span_deg = 2.0 * half_angle_deg + 8.0
    z0 = centre_z_mm - height_mm
    z1 = centre_z_mm + height_mm

    # 1. sacrificial backing shell, outer surface exactly at the pocket floor
    sketch = sketch_on(root, root.xZConstructionPlane, "ogma_letter_stock")
    polyline(sketch, [
        (floor_r - shell_thickness, z0),
        (floor_r, z0),
        (floor_r, z1),
        (floor_r - shell_thickness, z1),
    ])
    stock_feat = revolve(
        root, largest_profile(sketch), root.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=span_deg, name="Letter stock shell",
    )
    stock = stock_feat.bodies.item(0)
    stock.name = "ogma_letter_stock"

    # The revolve sweeps from the sketch plane in one direction only, so rotate
    # it back by half the span to centre the shell on the name.
    _rotate_body(root, stock, -span_deg * 0.5)

    # 2. grow the letters off it
    width = measure_name(root, name, height_mm, font_name, bold, spacing_mm)
    plane = offset_plane(root, plane_base, -(floor_r + 10.0),
                         "ogma_letter_plane")
    _sk, text = _text_sketch(
        root, plane, name, height_mm, font_name, bold,
        centre_z_mm, width, spacing_mm, "ogma_letter_text",
    )
    faces = _outer_cylindrical_faces(stock, floor_r)
    if not faces:
        raise RuntimeError(
            "Letter stock has no face at the pocket-floor radius "
            "R{:.2f} mm.".format(floor_r)
        )
    emboss(root, faces, text, pocket_depth_mm + letter_thickness_mm,
           "Letter solids")

    # 3. split the shell away at the pocket floor radius
    tool_sketch = sketch_on(root, root.xZConstructionPlane, "ogma_split_tool")
    polyline(tool_sketch, [
        (floor_r, z0 - 5.0),
        (floor_r + 0.01, z0 - 5.0),
        (floor_r + 0.01, z1 + 5.0),
        (floor_r, z1 + 5.0),
    ])
    tool_feat = revolve(
        root, largest_profile(tool_sketch), root.zConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        angle_deg=360.0, name="Letter split tool",
    )
    tool_body = tool_feat.bodies.item(0)
    split_face = _outer_cylindrical_faces(tool_body, floor_r)
    if split_face:
        split_body(root, [stock], split_face[0], True, "Free the letters")
    tool_body.deleteMe()

    letters = []
    for i in range(root.bRepBodies.count):
        body = root.bRepBodies.item(i)
        if body.name.startswith("ogma_letter_stock"):
            letters.append(body)
    # The backing shell is the piece that still reaches the inner radius.
    kept = []
    for body in letters:
        bbox = body.boundingBox
        outer = max(
            abs(bbox.maxPoint.x), abs(bbox.minPoint.x),
            abs(bbox.maxPoint.y), abs(bbox.minPoint.y),
        )
        if outer > cm(floor_r + letter_thickness_mm * 0.5):
            kept.append(body)
        else:
            body.deleteMe()
    for index, body in enumerate(kept, start=1):
        body.name = "Letter_{}".format(index)
    return kept


def _rotate_body(component, body, angle_deg: float):
    """Rotate a body about the Z axis in place."""
    if abs(angle_deg) < 1e-9:
        return None
    matrix = adsk.core.Matrix3D.create()
    matrix.setToRotation(
        math.radians(angle_deg),
        adsk.core.Vector3D.create(0, 0, 1),
        adsk.core.Point3D.create(0, 0, 0),
    )
    moves = component.features.moveFeatures
    inp = moves.createInput2(collection([body]))
    inp.defineAsFreeMove(matrix)
    return moves.add(inp)
