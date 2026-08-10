#!/usr/bin/env python3
"""Oggie Spin Solo -- core and arms as one printed body, no arm joint at all.

What this is
------------
The same spinner silhouette, printed as a single piece. Every part of the
interlocking system is gone: no slots, no dovetail tongues, no clip beam, no
barb, no pockets, no entry channels, no push-through ledge. The bearing,
retaining ring, Tough+ cartridge and thumb pads are unchanged and still work
exactly as they do on the modular version.

Why you would want it
---------------------
1. **It removes the detachable small parts.** The modular arm (~11 x 17 x 14 mm)
   fits inside the EN 71-1 small parts cylinder, which is what forces the 3+ age
   grade and the choking warning. A one-piece body is Ø52.6 mm and cannot fit any
   part of it. The bearing and cartridge remain small parts, but they are captive
   rather than designed to be removed by the user. This does not make the toy
   compliant on its own -- EN 71-1 also has torque and tension tests for whether
   captive parts come free -- but it removes the one hazard that was designed in.
2. **Four plates instead of ten**, and no assembly of arms.
3. **Nothing to wear out.** The barb wore visibly after ~80 cycles; here there is
   no barb.
4. **Better balance by construction.** Five separately printed arms can vary in
   mass; five arms that are the same solid cannot.

What it costs
-------------
The pick-and-mix colour range, which is the modular product's whole point. The
arms and the core are one body, so they are one colour: the arms coexist with
the core at every layer, and giving them separate filaments would mean a colour
change on all ~87 layers. Rough arithmetic put that at more purge than the part
weighs. The optical inlay survives because it lives only in the top 0.64 mm.

Treat this as a second SKU, not a replacement.

    .venv/bin/python products/oggie-spin/generator/oggie_spin_onepiece.py \\
        --out products/oggie-spin/design/active
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import trimesh
from shapely.geometry import Polygon

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_broken_rings as br  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
from ogma import printability  # noqa: E402

OUTPUT_NAME = "Oggie_Spin_Solo_OnePiece_P2S.3mf"
MESH_DIR_NAME = "onepiece-meshes"
REPORT_NAME = "onepiece_validation.json"

# Fillet radius where an arm meets the core. The modular design never needed one
# -- the arm sat in a slot and the joint was a sliding fit. Fused, that junction
# is a sharp inside corner: a stress riser exactly where the bending load from a
# dropped spinner concentrates, and it looks like two parts glued together.
#
# Measured across radii, this only grows the arm root: the gap between arms stays
# at exactly R20.00 even at 3.5 mm, so there is no risk of webbing the arms
# together. 2.5 mm adds 7 % section area at mid height.
ROOT_FILLET = 2.5

EDGE_CHAMFER = 0.40   # top and bottom, follows the lobed profile
CHAMFER_HEIGHT = 0.40


def _assembled_silhouette() -> Polygon:
    """The Solo outline: a solid R20 core disc plus the arms' outer envelope.

    An earlier version took a Z-section through the assembled modular spinner
    and filled its holes. That is fragile and it failed twice. The assembly has
    features that change with height -- the clip beam exists only below Z 3.45,
    so a section at mid height shows an open void where a section at Z 2 shows
    solid -- and any leftover void that happens to connect to the outside
    becomes part of the exterior ring rather than an interior hole, so filling
    holes does not remove it.

    This builds the profile from first principles instead:

      * the core is simply a disc at its own OD, so slots cannot survive
      * each arm contributes only what lies OUTSIDE that disc, which discards
        the tongue, the beam, the barb and the wrap clearance in one cut
      * the arm's contribution is its shadow over the whole height, not one
        slice, so nothing depends on where you cut

    Then a morphological closing rounds the concave corner at each arm root.
    """
    from shapely.affinity import rotate as _rotate
    from shapely.geometry import Point as _Point
    from shapely.ops import unary_union as _union

    arm = complete.build_arm("solo silhouette source")
    shadow = _union(
        [
            printability._footprint(arm, z)
            for z in np.linspace(0.3, base.CORE_HEIGHT - 0.3, 24)
            if printability._footprint(arm, z) is not None
        ]
    )
    core_disc = _Point(0.0, 0.0).buffer(base.CORE_DIAMETER / 2.0, resolution=64)
    # keep only the part of the arm outboard of the core, with a hair of
    # overlap so the union welds rather than kisses
    outboard = shadow.difference(
        _Point(0.0, 0.0).buffer(base.CORE_DIAMETER / 2.0 - 0.15, resolution=64)
    )
    lobes = [
        _rotate(outboard, -90.0 + 72.0 * index, origin=(0.0, 0.0))
        for index in range(5)
    ]
    profile = _union([core_disc, *lobes])
    if profile.geom_type != "Polygon":
        profile = max(printability._components(profile), key=lambda p: p.area)
    profile = Polygon(profile.exterior)
    if not profile.is_valid:
        profile = profile.buffer(0)
    # morphological closing: adds material in concave corners only
    return profile.buffer(ROOT_FILLET, join_style=1).buffer(
        -ROOT_FILLET, join_style=1
    )


CHAMFER_STEPS = 3


def _stepped_body(profile: Polygon) -> trimesh.Trimesh:
    """Extrude the profile with a stepped chamfer at both ends.

    NOT via complete._loft_polygons: that lofts by convex hull, which is fine
    for the small convex features it was written for and destroys a concave
    one. Fed this five-arm profile it returns a decagon -- the arms vanish into
    the hull and you get a solid disc. Straight extrusions of the real polygon
    are the only safe way to carry a concave outline into 3D.

    The chamfer is stepped rather than smooth because at 0.16 mm layers a
    0.40 mm chamfer is two and a half layers: the printer quantises it to a
    staircase regardless, so building one costs nothing and keeps every section
    a true extrusion of the profile.
    """
    slabs = []
    step_z = CHAMFER_HEIGHT / CHAMFER_STEPS
    for index in range(CHAMFER_STEPS):
        inset = EDGE_CHAMFER * (CHAMFER_STEPS - index) / CHAMFER_STEPS
        ring = profile.buffer(-inset, join_style=1)
        if ring.is_empty or ring.geom_type != "Polygon":
            raise RuntimeError("edge chamfer collapsed the profile")
        z0 = index * step_z
        slabs.append(base._extrude(ring, step_z, z0))
        slabs.append(
            base._extrude(ring, step_z, base.CORE_HEIGHT - z0 - step_z)
        )
    slabs.append(
        base._extrude(
            profile,
            base.CORE_HEIGHT - 2.0 * CHAMFER_HEIGHT,
            CHAMFER_HEIGHT,
        )
    )
    return base._union(slabs, "Solo body blank")


def build_body() -> trimesh.Trimesh:
    """The one-piece core-and-arms body."""
    profile = _assembled_silhouette()
    body = _stepped_body(profile)

    # Bearing features, identical to the modular core including the lead-in
    # chamfer at the pocket mouth.
    cutters = [
        base._cylinder(
            base.BEARING_POCKET_DIAMETER / 2.0,
            complete.BEARING_RING_SEAT_Z - base.BEARING_SEAT_Z + 0.2,
            base.BEARING_SEAT_Z,
            sections=128,
        ),
        complete._loft_polygons(
            [
                (
                    complete.BEARING_RING_SEAT_Z - complete.BEARING_POCKET_LEAD_IN,
                    complete._circle(base.BEARING_POCKET_DIAMETER / 2.0),
                ),
                (
                    complete.BEARING_RING_SEAT_Z + 0.01,
                    complete._circle(
                        base.BEARING_POCKET_DIAMETER / 2.0
                        + complete.BEARING_POCKET_LEAD_IN
                    ),
                ),
            ]
        ),
        base._cylinder(
            complete.BEARING_RING_COUNTERBORE_D / 2.0,
            base.CORE_HEIGHT - complete.BEARING_RING_SEAT_Z + 0.2,
            complete.BEARING_RING_SEAT_Z,
            sections=128,
        ),
        base._cylinder(
            base.BEARING_SHOULDER_OPENING / 2.0,
            base.BEARING_SEAT_Z + 0.2,
            -0.1,
            sections=128,
        ),
    ]
    solo = base._difference(body, cutters, "Oggie Spin Solo body")
    return complete._weld_shells(solo, "Oggie Spin Solo body")


SMALL_PARTS_CYLINDER_D = 31.77   # EN 71-1 small parts cylinder
SMALL_PARTS_CYLINDER_L = 57.10


def _fits_small_parts_cylinder(mesh: trimesh.Trimesh) -> bool:
    """Could this part be swallowed? EN 71-1 8.2, conservatively.

    A part fits if some orientation lets it drop fully inside a 31.77 mm bore.
    Bounding-box test: take the two smallest extents -- the best case for
    fitting -- and see whether that rectangle is enclosed by the bore circle.
    Erring toward 'it fits' is the safe direction for a hazard check.
    """
    extents = sorted(float(v) for v in mesh.extents)
    diagonal = math.hypot(extents[0], extents[1])
    return diagonal <= SMALL_PARTS_CYLINDER_D and extents[2] <= SMALL_PARTS_CYLINDER_L


def build_meshes() -> list[tuple[str, trimesh.Trimesh, int]]:
    """Solo body split into base + optical inlay, plus the unchanged hardware."""
    body = build_body()
    # All three broken rings now live on ONE body: the R22.5 arm ring simply
    # stops where the arms stop, which is what it did before across five parts.
    dashes = trimesh.util.concatenate(
        [br._dash_volume(spec) for spec in br.RING_SPECS]
    )
    solo_base, solo_inlay = br._split_flush_inlay(body, dashes, "Oggie Spin Solo")
    solo_inlay, proud = br._raise_inlay(solo_inlay, "Oggie Spin Solo optical inlay")

    global _PROUD_MM3
    _PROUD_MM3 = proud

    return [
        ("Oggie Spin Solo one-piece body", solo_base, 1),
        ("Ivory White Solo optical inlay", solo_inlay, br.OPTICAL_EXTRUDER),
        ("R188 outer-race retaining ring", complete.build_bearing_ring(), 1),
        (
            "Tough+ split-collet through-axle hub",
            complete.build_collet_hub(),
            br.TOUGH_EXTRUDER,
        ),
        (
            "Tough+ through-bore receiver hub",
            complete.build_receiver_hub(),
            br.TOUGH_EXTRUDER,
        ),
        (
            "Socketed thumb pad 1",
            complete.build_printed_thumb_pad(
                "socketed thumb pad 1",
                height=complete.RECEIVER_CAP_HEIGHT,
                central_socket_depth=complete.RECEIVER_CAP_SOCKET_DEPTH,
            ),
            2,
        ),
        (
            "Socketed thumb pad 2",
            complete.build_printed_thumb_pad(
                "socketed thumb pad 2",
                height=complete.RECEIVER_CAP_HEIGHT,
                central_socket_depth=complete.RECEIVER_CAP_SOCKET_DEPTH,
            ),
            2,
        ),
    ]


_PROUD_MM3 = 0.0

SOLO_PLATES_SPEC = [
    ("Solo one-piece body + Ivory inlay", ((1, 0.0, 0.0, 0.0), (2, 0.0, 0.0, 0.0))),
    ("R188 outer-race retaining ring", ((3, 0.0, 0.0, 0.0),)),
    ("Tough+ split-collet cartridge", ((4, -13.0, 0.0, 0.0), (5, 13.0, 0.0, 0.0))),
    ("Removable bayonet thumb pads", ((6, -13.0, 0.0, 0.0), (7, 13.0, 0.0, 0.0))),
]


def _plate_position(number: int, total: int) -> tuple[float, float, float]:
    cols = math.ceil(math.sqrt(total))
    index = number - 1
    return (128.0 + (index % cols) * 312.0, 128.0 - (index // cols) * 312.0, 0.0)


def _validate(output: Path, built) -> dict:
    body = built[0][1]
    inlay = built[1][1]

    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("Solo 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = ET.fromstring(package.read("Metadata/model_settings.config"))
        if len(settings.findall("./plate")) != len(SOLO_PLATES_SPEC):
            raise RuntimeError("Solo 3MF lost a plate")

    # --- the arm joint really is gone ---------------------------------------
    # Solid all the way through where the five slots used to be.
    section = printability._footprint(body, base.CORE_HEIGHT / 2.0)
    from shapely.geometry import Point
    for index in range(5):
        angle = math.radians(-90.0 + 72.0 * index)
        for radius in (14.5, 16.0, 18.0, 19.5):
            probe = Point(radius * math.cos(angle), radius * math.sin(angle))
            if not section.contains(probe):
                raise RuntimeError(
                    f"slot {index} is still open at R{radius} -- this is not one piece"
                )

    # --- the ARMS are still there -------------------------------------------
    # The first build of this variant lost them silently: the profile was right,
    # but it was carried into 3D by a convex-hull loft and came out a solid
    # decagon. Every check written at the time passed, because they all tested
    # what was supposed to be filled and none tested what was supposed to stay
    # open. Only rendering it caught it. So: measure the concavity.
    hull_ratio = section.area / section.convex_hull.area
    if hull_ratio > 0.90:
        raise RuntimeError(
            f"body section is {hull_ratio:.3f} of its convex hull -- the five "
            "arms have been swallowed into a disc"
        )
    from shapely.geometry import LineString as _Line
    for index in range(5):
        angle = math.radians(-90.0 + 36.0 + 72.0 * index)   # between two arms
        ray = _Line([(0.0, 0.0), (40.0 * math.cos(angle), 40.0 * math.sin(angle))])
        hit = ray.intersection(section)
        reach = 0.0
        if not hit.is_empty:
            coords = (
                np.array(hit.coords) if hit.geom_type == "LineString"
                else np.vstack([np.array(g.coords) for g in hit.geoms])
            )
            reach = float(np.hypot(coords[:, 0], coords[:, 1]).max())
        if reach > base.CORE_DIAMETER / 2.0 + 0.05:
            raise RuntimeError(
                f"gap {index} between arms is filled: material reaches R{reach:.2f} "
                f"where the core OD is R{base.CORE_DIAMETER / 2.0:.2f}"
            )

    if len(body.split(only_watertight=False)) != 1:
        raise RuntimeError("Solo body is not a single shell")
    if not body.is_watertight:
        raise RuntimeError("Solo body is not watertight")

    report = complete.audit_printability([(n, m) for n, m, _e in built])

    # --- small parts ---------------------------------------------------------
    hazards = {
        name: _fits_small_parts_cylinder(mesh)
        for name, mesh, _e in built
        if "inlay" not in name.lower()
    }
    if hazards["Oggie Spin Solo one-piece body"]:
        raise RuntimeError("the one-piece body fits the small parts cylinder")

    volume = float(body.volume + inlay.volume)
    return {
        "project": output.name,
        "status": (
            "one-piece core-and-arms variant; no arm joint. Geometry validated, "
            "physical gates open."
        ),
        "plates": len(SOLO_PLATES_SPEC),
        "objects": len(built),
        "body_volume_cm3": round(body.volume / 1000.0, 2),
        "body_mass_g_at_1_24": round(volume / 1000.0 * 1.24, 1),
        "body_outer_diameter_mm": round(
            2.0 * float(np.hypot(body.vertices[:, 0], body.vertices[:, 1]).max()), 2
        ),
        "root_fillet_mm": ROOT_FILLET,
        "section_area_over_convex_hull": round(hull_ratio, 3),
        "inlay_proud_mm": br.INLAY_PROUD,
        "inlay_proud_volume_mm3": round(_PROUD_MM3, 4),
        "removed_from_the_modular_design": [
            "five arm slots", "dovetail tongues", "clip cantilever beams",
            "snap barbs", "underside clip pockets", "entry channels",
            "retaining lips", "push-through ledges", "wrap clearance",
        ],
        "unchanged_from_the_modular_design": [
            "R188 bearing pocket and lead-in chamfer",
            "retaining ring counterbore and press fit",
            "Tough+ split-collet cartridge",
            "bayonet thumb pads",
            "broken-ring optical pattern (15/20/25 dashes)",
        ],
        "small_parts_cylinder": {
            "bore_mm": SMALL_PARTS_CYLINDER_D,
            "depth_mm": SMALL_PARTS_CYLINDER_L,
            "fits_cylinder": hazards,
            "note": (
                "the one-piece body cannot fit, which is the point: the modular "
                "arm could. The bearing, hubs, ring and pads still fit and are "
                "still small parts -- they are captive rather than user-removable, "
                "and EN 71-1 torque and tension tests decide whether that holds."
            ),
        },
        "printability": report,
    }


def generate(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    mesh_dir = out_dir / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)

    built = build_meshes()
    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_').replace('+','plus')}.stl"
        mesh.export(path)
        base._finish(trimesh.load_mesh(path, process=True), f"serialized {name}")
        objects.append((name, path, extruder))

    total = len(SOLO_PLATES_SPEC)
    plates = [
        base.Plate(title, comps, _plate_position(n, total))
        for n, (title, comps) in enumerate(SOLO_PLATES_SPEC, start=1)
    ]

    output = out_dir / OUTPUT_NAME
    previous = (
        base.PLATES, base.FILAMENTS, base._preview_png,
        base._model_settings, base._configure_filament_slots,
    )
    try:
        base.PLATES = plates
        base.FILAMENTS = br.VARIANT_FILAMENTS
        base._preview_png = br._preview_png
        base._model_settings = br.ORIGINAL_MODEL_SETTINGS
        base._configure_filament_slots = br._configure_variant_filaments
        base.build_bambu_project(output, objects)
    finally:
        (
            base.PLATES, base.FILAMENTS, base._preview_png,
            base._model_settings, base._configure_filament_slots,
        ) = previous
    br._rewrite_variant_project_settings(output)

    report = _validate(output, built)
    (out_dir / REPORT_NAME).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--units",
        type=int,
        default=0,
        help="emit a batch project of N complete Solos instead of a single unit",
    )
    args = parser.parse_args()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if args.units:
            print(generate_batch(args.out, args.units))
        else:
            print(generate(args.out))


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Batch: N complete Solos per plate set
# ---------------------------------------------------------------------------

BATCH_OUTPUT_TEMPLATE = "Oggie_Spin_Solo_Batch_x{units}_P2S.3mf"
BATCH_MESH_DIR = "solo-batch-meshes"
BATCH_REPORT_NAME = "solo_batch_report.json"


def build_batch_plan(units: int) -> dict:
    """Plate layout for `units` complete Solo spinners.

    Same shape as the modular batch: group by filament so whole plates purge
    nothing, and let the retaining rings ride on the body plate because they
    share the body's filament. The prime tower is a per-PLATE cost, and on a
    one-up Solo plate it is 18% of all filament -- that is the entire reason
    this exists.
    """
    from oggie_spin_batch import _grid_offsets, _mesh_footprint

    built = build_meshes()
    by = {name: (mesh, ext) for name, mesh, ext in built}
    body = next(v for k, v in by.items() if "one-piece body" in k)
    inlay = next(v for k, v in by.items() if "optical inlay" in k)
    ring = next(v for k, v in by.items() if "retaining ring" in k)
    collet = next(v for k, v in by.items() if "split-collet" in k)
    recv = next(v for k, v in by.items() if "receiver hub" in k)
    pad = next(v for k, v in by.items() if "thumb pad 1" in k)

    objects: list[tuple[str, trimesh.Trimesh, int]] = []
    plates: list[dict] = []

    def add(label, entry, count):
        mesh, ext = entry
        ids = []
        for n in range(count):
            objects.append((f"{label} {n + 1}", mesh, ext))
            ids.append(len(objects))
        return ids

    def grid(ids, entry):
        mesh, _ = entry
        w, d, cx, cy = _mesh_footprint(mesh)
        return [(i, x, y, 0.0) for i, (x, y) in zip(ids, _grid_offsets(len(ids), w, d, cx, cy))]

    # plate 1: bodies + their inlays, plus the rings on the same filament
    body_ids = add("Solo body", body, units)
    inlay_ids = add("Solo inlay", inlay, units)
    bw, bd, bcx, bcy = _mesh_footprint(body[0])
    offs = _grid_offsets(units, bw, bd, bcx, bcy)
    comps = []
    for ib, ii, (x, y) in zip(body_ids, inlay_ids, offs):
        comps.append((ib, x, y, 0.0))
        comps.append((ii, x, y, 0.0))
    ring_ids = add("Retaining ring", ring, units)
    rw, rd, rcx, rcy = _mesh_footprint(ring[0])
    rows = math.ceil(units / max(1, int((220.0 + 6.0) // (bw + 6.0))))
    ring_y = -(rows * (bd + 6.0)) / 2.0 - (rd + 6.0) / 2.0
    for i, (x, _y) in zip(ring_ids, _grid_offsets(units, rw, rd, rcx, rcy)):
        comps.append((i, x, ring_y - rcy, 0.0))
    plates.append({"title": f"Solo bodies x{units} + retaining rings x{units}", "components": comps})

    # plate 2: both hubs, Tough+ only -> zero purge
    hub_ids = add("Collet hub", collet, units) + add("Receiver hub", recv, units)
    plates.append({"title": f"Tough+ cartridge hubs x{units * 2}",
                   "components": grid(hub_ids, collet)})

    # plate 3: thumb pads, one colour -> zero purge
    plates.append({"title": f"Thumb pads x{units * 2}",
                   "components": grid(add("Thumb pad", pad, units * 2), pad)})

    return {"units": units, "objects": objects, "plates": plates}


def generate_batch(out_dir: Path, units: int = 9) -> Path:
    out_dir = Path(out_dir)
    plan = build_batch_plan(units)
    mesh_dir = out_dir / BATCH_MESH_DIR
    mesh_dir.mkdir(parents=True, exist_ok=True)

    written: dict[int, Path] = {}
    objects = []
    for name, mesh, ext in plan["objects"]:
        key = id(mesh)
        if key not in written:
            stem = name.rsplit(" ", 1)[0].lower().replace(" ", "_")
            path = mesh_dir / f"{len(written) + 1:02d}_{stem}.stl"
            mesh.export(path)
            written[key] = path
        objects.append((name, written[key], ext))

    total = len(plan["plates"])
    plates = [
        base.Plate(p["title"], tuple(p["components"]), _plate_position(n, total))
        for n, p in enumerate(plan["plates"], start=1)
    ]
    output = out_dir / BATCH_OUTPUT_TEMPLATE.format(units=units)
    previous = (base.PLATES, base.FILAMENTS, base._preview_png,
                base._model_settings, base._configure_filament_slots)
    try:
        base.PLATES = plates
        base.FILAMENTS = br.VARIANT_FILAMENTS
        base._preview_png = br._preview_png
        base._model_settings = br.ORIGINAL_MODEL_SETTINGS
        base._configure_filament_slots = br._configure_variant_filaments
        base.build_bambu_project(output, objects)
    finally:
        (base.PLATES, base.FILAMENTS, base._preview_png,
         base._model_settings, base._configure_filament_slots) = previous
    br._rewrite_variant_project_settings(output)

    # --- validate ---------------------------------------------------------
    from shapely.geometry import box as _box
    half = 128.0
    worst = 0.0
    for number, plate in enumerate(plan["plates"], start=1):
        rects = []
        for oid, dx, dy, _dz in plate["components"]:
            name, mesh, _e = plan["objects"][oid - 1]
            lo, hi = mesh.bounds[0], mesh.bounds[1]
            for v in (lo[0] + dx, hi[0] + dx, lo[1] + dy, hi[1] + dy):
                worst = max(worst, abs(v))
                if abs(v) > half:
                    raise RuntimeError(f"plate {number} object {oid} falls off its bed")
            if "inlay" not in name.lower():
                rects.append(_box(lo[0] + dx, lo[1] + dy, hi[0] + dx, hi[1] + dy))
        for a in range(len(rects)):
            for b in range(a + 1, len(rects)):
                hit = rects[a].intersection(rects[b])
                if not hit.is_empty and hit.area > 1e-9:
                    raise RuntimeError(f"plate {number}: parts overlap by {hit.area:.3f} mm2")

    counts: dict[str, int] = {}
    for name, _m, _e in plan["objects"]:
        counts[name.rsplit(" ", 1)[0]] = counts.get(name.rsplit(" ", 1)[0], 0) + 1
    expected = {"Solo body": units, "Solo inlay": units, "Retaining ring": units,
                "Collet hub": units, "Receiver hub": units, "Thumb pad": units * 2}
    for key, want in expected.items():
        if counts.get(key) != want:
            raise RuntimeError(f"not a matched set: {want}x {key} expected, {counts.get(key)} present")

    volume = sum(float(m.volume) for _n, m, _e in plan["objects"]) / 1000.0
    report = {
        "project": output.name,
        "units_per_batch": units,
        "plates": len(plan["plates"]),
        "objects": len(plan["objects"]),
        "unique_meshes": len(written),
        "single_filament_plates": [plan["plates"][1]["title"], plan["plates"][2]["title"]],
        "worst_object_reach_from_plate_centre_mm": round(worst, 2),
        "batch_volume_cm3": round(volume, 2),
        "batch_mass_g_at_1_24": round(volume * 1.24, 1),
        "parts_per_batch": counts,
        "note": (
            "the prime tower is a per-plate fixed cost. Bambu sliced a one-up "
            "Solo at 3.87 g of tower against 16.74 g of model -- 18% of all "
            "filament, for 0.13 g of ivory in the part. Nine-up amortises it to "
            "0.43 g each."
        ),
    }
    (out_dir / BATCH_REPORT_NAME).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output
