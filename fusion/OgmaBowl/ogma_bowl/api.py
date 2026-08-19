"""Thin wrappers over the Fusion API calls this add-in relies on.

Every function here corresponds to a signature that was checked against the
Fusion API Reference (help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/).
Where Autodesk has retired a method the current replacement is used and the
retired one is named in the docstring, because a lot of sample code still in
circulation calls the old form:

    ExtrudeFeatureInput.setDistanceExtent   retired Sept 2022 -> setOneSideExtent
    SketchTexts.createInput2                retired Nov  2025 -> createInput3
    ExtrudeFeatures.createInput2            never existed

Keeping the wrappers in one module means a future API change is one edit here
rather than a scavenger hunt through four style builders.
"""

from __future__ import annotations

import adsk.core
import adsk.fusion

from .units import cm, mm, deg


# --------------------------------------------------------------------------
# Value inputs
# --------------------------------------------------------------------------

def vs(expression: str):
    """ValueInput from an expression string (units explicit, or a parameter)."""
    return adsk.core.ValueInput.createByString(expression)


def vr(value: float):
    """ValueInput from a raw real. Remember: database units, so cm for length."""
    return adsk.core.ValueInput.createByReal(float(value))


def v_mm(millimetres: float):
    """ValueInput for a length given in millimetres."""
    return vs(mm(millimetres))


def v_deg(degrees: float):
    """ValueInput for an angle given in degrees."""
    return vs(deg(degrees))


def pt(x_mm: float, y_mm: float, z_mm: float):
    """Point3D from millimetres."""
    return adsk.core.Point3D.create(cm(x_mm), cm(y_mm), cm(z_mm))


def collection(items):
    """ObjectCollection from an iterable."""
    oc = adsk.core.ObjectCollection.create()
    for item in items:
        oc.add(item)
    return oc


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------

def add_parameter(design, name: str, expression: str, unit: str, comment: str):
    """Create or update a User Parameter.

    UserParameters.add(name, ValueInput, units, comment) -- all four required.
    Re-running the command must not throw on an existing parameter, so an
    existing one is updated in place; that also means a value the user has
    edited by hand is overwritten deliberately, not silently ignored.
    """
    existing = design.userParameters.itemByName(name)
    if existing:
        existing.expression = expression
        if comment:
            existing.comment = comment
        return existing
    return design.userParameters.add(name, vs(expression), unit, comment)


# --------------------------------------------------------------------------
# Sketch helpers
# --------------------------------------------------------------------------

def sketch_on(component, plane, name: str = ""):
    sk = component.sketches.add(plane)
    if name:
        sk.name = name
    return sk


def polyline(sketch, points_mm, close: bool = True):
    """Draw a closed polyline from [(x_mm, y_mm), ...] on the sketch plane.

    Returns the list of created SketchLines. Sketch-plane coordinates, so for a
    sketch on XZ the tuple is (radius, height).
    """
    lines = sketch.sketchCurves.sketchLines
    created = []
    n = len(points_mm)
    last = n if close else n - 1
    for i in range(last):
        a = points_mm[i]
        b = points_mm[(i + 1) % n]
        created.append(
            lines.addByTwoPoints(pt(a[0], a[1], 0.0), pt(b[0], b[1], 0.0))
        )
    return created


def largest_profile(sketch):
    """The profile enclosing the greatest area.

    Profiles are explicitly documented as having no stable index order, so
    `profiles.item(0)` is a coin flip on any sketch that closes more than one
    region. Area is deterministic.
    """
    best = None
    best_area = -1.0
    for i in range(sketch.profiles.count):
        prof = sketch.profiles.item(i)
        area = prof.areaProperties(
            adsk.fusion.CalculationAccuracy.LowCalculationAccuracy
        ).area
        if area > best_area:
            best_area, best = area, prof
    if best is None:
        raise RuntimeError("sketch '{}' produced no closed profile".format(sketch.name))
    return best


def all_profiles(sketch):
    return collection([sketch.profiles.item(i) for i in range(sketch.profiles.count)])


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------

def revolve(component, profile, axis, operation, angle_deg: float = 360.0,
            name: str = ""):
    """Revolve a profile about an axis.

    setAngleExtent(isSymmetric, angle) -- bool FIRST. Note the documented trap:
    when isSymmetric is True the angle is the half-angle and the total sweep is
    twice it. This wrapper always passes isSymmetric=False and the full angle,
    so the number you pass is the number you get.
    """
    revolves = component.features.revolveFeatures
    inp = revolves.createInput(profile, axis, operation)
    inp.setAngleExtent(False, v_deg(angle_deg))
    feat = revolves.add(inp)
    if name:
        feat.name = name
    return feat


def revolve_symmetric(component, profile, axis, operation, half_angle_deg: float,
                      name: str = ""):
    """Revolve symmetrically about the profile plane by +/- half_angle_deg."""
    revolves = component.features.revolveFeatures
    inp = revolves.createInput(profile, axis, operation)
    inp.setAngleExtent(True, v_deg(half_angle_deg))
    feat = revolves.add(inp)
    if name:
        feat.name = name
    return feat


def extrude(component, profile, operation, distance_mm: float,
            direction=None, taper_deg: float = 0.0, participants=None,
            name: str = ""):
    """One-sided extrude.

    Uses setOneSideExtent + DistanceExtentDefinition (the current API).
    `setDistanceExtent` was retired in September 2022 and is deliberately not
    used, even though most sample code still calls it.
    """
    extrudes = component.features.extrudeFeatures
    inp = extrudes.createInput(profile, operation)
    if direction is None:
        direction = adsk.fusion.ExtentDirections.PositiveExtentDirection
    extent = adsk.fusion.DistanceExtentDefinition.create(v_mm(abs(distance_mm)))
    taper = v_deg(taper_deg) if taper_deg else None
    inp.setOneSideExtent(extent, direction, taper)
    if participants:
        inp.participantBodies = list(participants)
    feat = extrudes.add(inp)
    if name:
        feat.name = name
    return feat


def extrude_symmetric(component, profile, operation, total_mm: float,
                      participants=None, name: str = ""):
    """Symmetric extrude, `total_mm` measured end to end.

    setSymmetricExtent(distance, isFullLength, taper) -- the bool is the SECOND
    argument here, the opposite way round from setAngleExtent. Passing
    isFullLength=True means total_mm is the whole length, not the half.
    """
    extrudes = component.features.extrudeFeatures
    inp = extrudes.createInput(profile, operation)
    inp.setSymmetricExtent(v_mm(total_mm), True, None)
    if participants:
        inp.participantBodies = list(participants)
    feat = extrudes.add(inp)
    if name:
        feat.name = name
    return feat


def combine(component, target_body, tool_bodies, operation,
            keep_tools: bool = False, name: str = ""):
    """Boolean. Valid operations: Join, Cut, Intersect (NOT NewBody)."""
    tools = tool_bodies if hasattr(tool_bodies, "count") else collection(tool_bodies)
    if tools.count == 0:
        return None
    combines = component.features.combineFeatures
    inp = combines.createInput(target_body, tools)
    inp.operation = operation
    inp.isKeepToolBodies = keep_tools
    inp.isNewComponent = False
    feat = combines.add(inp)
    if feat and name:
        feat.name = name
    return feat


def cut(component, target_body, tool_bodies, name: str = ""):
    return combine(component, target_body, tool_bodies,
                   adsk.fusion.FeatureOperations.CutFeatureOperation, name=name)


def join(component, target_body, tool_bodies, name: str = ""):
    return combine(component, target_body, tool_bodies,
                   adsk.fusion.FeatureOperations.JoinFeatureOperation, name=name)


def circular_pattern(component, entities, axis, quantity: int,
                     total_angle_deg: float = 360.0, name: str = ""):
    """Circular pattern. quantity/totalAngle are properties, not createInput args."""
    pats = component.features.circularPatternFeatures
    inp = pats.createInput(collection(entities), axis)
    inp.quantity = vr(quantity)
    inp.totalAngle = v_deg(total_angle_deg)
    inp.isSymmetric = False
    feat = pats.add(inp)
    if name:
        feat.name = name
    return feat


def rectangular_pattern(component, entities, direction_entity, quantity: int,
                        spacing_mm: float, name: str = ""):
    """Rectangular pattern along one direction, SPACING (not extent) distance."""
    pats = component.features.rectangularPatternFeatures
    inp = pats.createInput(
        collection(entities),
        direction_entity,
        vr(quantity),
        v_mm(spacing_mm),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType,
    )
    feat = pats.add(inp)
    if name:
        feat.name = name
    return feat


def suppress_pattern_elements(design, pattern_feature, indices):
    """Suppress individual pattern instances by index.

    PatternElement.isSuppressed is read/write, but the documented precondition
    is that the timeline marker sits immediately before the pattern feature —
    writing it with the marker at the end silently fails. Hence the rollTo /
    moveToEnd sandwich.
    """
    indices = [i for i in indices if 0 <= i < pattern_feature.patternElements.count]
    if not indices:
        return 0
    pattern_feature.timelineObject.rollTo(True)
    try:
        ids = [pattern_feature.patternElements.item(i).id for i in indices]
        pattern_feature.suppressedElementsIds = ids
    finally:
        design.timeline.moveToEnd()
    return len(indices)


def scale_non_uniform(component, body, origin_point, sx: float, sy: float, sz: float,
                      name: str = ""):
    """Non-uniform scale of a BRep body.

    setToNonUniform fails outright if the input collection contains sketches or
    components, so this only ever takes a single body. `origin_point` must be a
    BRepVertex / SketchPoint / ConstructionPoint — a Point3D is rejected.
    """
    scales = component.features.scaleFeatures
    inp = scales.createInput(collection([body]), origin_point, vr(1.0))
    inp.setToNonUniform(vr(sx), vr(sy), vr(sz))
    feat = scales.add(inp)
    if name:
        feat.name = name
    return feat


def move_body(component, body, matrix, name: str = ""):
    moves = component.features.moveFeatures
    inp = moves.createInput2(collection([body]))
    inp.defineAsFreeMove(matrix)
    feat = moves.add(inp)
    if name:
        feat.name = name
    return feat


def offset_plane(component, base_plane, offset_mm: float, name: str = ""):
    planes = component.constructionPlanes
    inp = planes.createInput()
    inp.setByOffset(base_plane, v_mm(offset_mm))
    plane = planes.add(inp)
    if name:
        plane.name = name
    return plane


def plane_by_three_points(component, p1, p2, p3, name: str = ""):
    """Construction plane through three sketch/construction points."""
    planes = component.constructionPlanes
    inp = planes.createInput()
    inp.setByThreePoints(p1, p2, p3)
    plane = planes.add(inp)
    if name:
        plane.name = name
    return plane


def split_body(component, bodies, tool, extend: bool = True, name: str = ""):
    splits = component.features.splitBodyFeatures
    target = bodies if hasattr(bodies, "count") else collection(bodies)
    inp = splits.createInput(target, tool, extend)
    feat = splits.add(inp)
    if name:
        feat.name = name
    return feat


def loft_surface(component, sections, name: str = ""):
    """Loft a SURFACE through open 3D curves.

    LoftSections.add rejects a bare SketchFittedSpline — the accepted types are
    BRepFace / Profile / Path / SketchPoint / ConstructionPoint. A 3D spline has
    to be wrapped in a Path first, which is also the only way to give a loft a
    genuinely three-dimensional section.
    """
    lofts = component.features.loftFeatures
    inp = lofts.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    inp.isSolid = False
    for curve in sections:
        path = adsk.fusion.Path.create(
            curve, adsk.fusion.ChainedCurveOptions.noChainedCurves
        )
        inp.loftSections.add(path)
    feat = lofts.add(inp)
    if name:
        feat.name = name
    return feat


def fitted_spline(sketch, points_mm_xyz):
    """3D fitted spline through world-space (x, y, z) millimetre tuples."""
    pts = collection([pt(x, y, z) for (x, y, z) in points_mm_xyz])
    return sketch.sketchCurves.sketchFittedSplines.add(pts)


# --------------------------------------------------------------------------
# Sketch text
# --------------------------------------------------------------------------

def sketch_text(sketch, text: str, height_mm: float, font_name: str,
                bold: bool, corner_mm, diagonal_mm):
    """Create a multi-line sketch text laid out inside a rectangle.

    createInput3(expression, ValueInput) is the current form; createInput2 was
    retired in November 2025 and createInput in January 2021.

    The `expression` argument is an EXPRESSION, not a literal — plain text has
    to arrive wrapped in single quotes or Fusion tries to evaluate it as a
    parameter reference and the text silently comes out empty.
    """
    texts = sketch.sketchTexts
    inp = texts.createInput3("'{}'".format(text.replace("'", "")), v_mm(height_mm))
    inp.setAsMultiLine(
        pt(corner_mm[0], corner_mm[1], 0.0),
        pt(diagonal_mm[0], diagonal_mm[1], 0.0),
        adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
        adsk.core.VerticalAlignments.MiddleVerticalAlignment,
        0.0,
    )
    inp.fontName = font_name
    if bold:
        inp.textStyle = adsk.fusion.TextStyles.TextStyleBold
    return texts.add(inp)


def text_width_mm(sketch_text_obj, fallback_mm: float) -> float:
    """Measured width of a SketchText, in millimetres.

    Sketch text never appears in sketch.profiles and has no public outline
    collection, so the width has to come from the entity's bounding box.
    `asCurves()` is the documented second route — it returns transient Curve3D
    objects, useless as feature input but fine to measure. If both are
    unavailable the caller's estimate is used rather than raising, because a
    slightly mis-packed name is a far better failure than no model at all.
    """
    try:
        bbox = sketch_text_obj.boundingBox
        if bbox:
            width = (bbox.maxPoint.x - bbox.minPoint.x)
            if width > 0:
                return width * 10.0
    except Exception:
        pass
    try:
        curves = sketch_text_obj.asCurves()
        xs = []
        for curve in curves:
            bbox = curve.boundingBox
            xs.extend([bbox.minPoint.x, bbox.maxPoint.x])
        if xs:
            return (max(xs) - min(xs)) * 10.0
    except Exception:
        pass
    return fallback_mm
