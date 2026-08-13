#!/usr/bin/env python3
"""Generate the broken-ring optical-illusion Oggie Spin project.

This is the optical winner: keep the proven 15/20/25 dash rings unchanged,
reuse the matched three-rail + underside-clip mechanism from
`oggie_spin_complete`, and stamp an underside `BR` identifier on the core.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings

import numpy as np
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import trimesh
from shapely.geometry import Polygon

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import oggie_spin_bayonet as base  # noqa: E402
import oggie_spin_complete as complete  # noqa: E402
import oggie_spin_optical_variants as optical  # noqa: E402


OUTPUT_NAME = "Oggie_Spin_Broken_Ring_Illusion_P2S.3mf"
BATCH_OUTPUT_NAME = "Oggie_Spin_5x_Broken_Ring_P2S.3mf"
MESH_DIR_NAME = "broken-ring-meshes"
REPORT_NAME = "broken_ring_variant_validation.json"
# The underside two-letter mark existed to tell printed optical variants apart.
# Broken Ring is now the only live design, so it distinguishes nothing -- and the
# pixel font read as noise on the finished face. Set to None to drop it; put the
# code back here if a second variant ever ships alongside this one.
IDENTIFIER = None
INLAY_DEPTH = 0.32  # two 0.16 mm layers, sunk into the base
# How far the optical dashes stand PROUD of the top face. 0 restores the flush
# inlay. 0.32 is two 0.16 mm layers, so the raised cap slices as whole layers.
INLAY_PROUD = 0.32
INLAY_TOP_OVERTRAVEL = 0.10
RING_WIDTH = 1.10
RING_DUTY = 0.52
OPTICAL_FILAMENT = ("Ivory White Matte optical inlay", "#FFFFFF")
VARIANT_FILAMENTS = [*complete.FILAMENTS, OPTICAL_FILAMENT]
OPTICAL_EXTRUDER = len(VARIANT_FILAMENTS)
TOUGH_EXTRUDER = 6

RING_SPECS = [
    {
        "name": "inner core",
        "radius_mm": 15.5,
        "dash_count": 15,
        "phase_deg": 0.0,
        "target": "core",
    },
    {
        "name": "outer core",
        "radius_mm": 18.5,
        "dash_count": 20,
        "phase_deg": 9.0,
        "target": "core",
    },
    {
        "name": "arm",
        "radius_mm": 22.5,
        "dash_count": 25,
        "phase_deg": 7.2,
        "target": "arm",
    },
]

ORIGINAL_MODEL_SETTINGS = base._model_settings
ORIGINAL_CONFIGURE_FILAMENTS = base._configure_filament_slots


# How many plates this project ships. Bambu Studio lays plates out in a grid of
# ceil(sqrt(n)) columns, so the column count CHANGES with the plate count -- 3
# columns at nine plates, 4 at ten. The old hardcoded 3 was silently correct
# only while there were exactly nine plates; adding the five-up batch moved
# every plate from 4 onward into the wrong bed, and plates 9 and 10 landed in no
# bed at all. Keep this in step with VARIANT_PLATES; the assertion below checks.
FLUSH_MIN = 140.0
FLUSH_MAX = 400

PLATE_COUNT = 10
PLATE_COLUMNS = math.ceil(math.sqrt(PLATE_COUNT))
PLATE_STRIDE = 312.0
BED_SIZE = 256.0


def _plate_position(number: int) -> tuple[float, float, float]:
    index = number - 1
    return (
        128.0 + (index % PLATE_COLUMNS) * PLATE_STRIDE,
        128.0 - (index // PLATE_COLUMNS) * PLATE_STRIDE,
        0.0,
    )


# Plate 10: five identical arms in one colour, for stocking a pick-and-mix.
# One colour means TWO filaments, so the purge tower stays small and the only
# colour change is in the top four layers where the optical dashes live.
#
# The arm mesh sits at x 13.30..25.35 in its own coordinates, so its centre is
# +19.325 off origin; the offsets below cancel that and place the group on the
# plate centre. Targets are a 3+2 quincunx on a 21 x 24 mm pitch, giving ~8 mm
# gaps around a 12.1 x 17.1 mm part -- tight enough to keep per-layer travel
# short, open enough for the fan and the nozzle skirt.
BATCH_PLATE_TARGETS = [
    (-21.0, 12.0),
    (0.0, 12.0),
    (21.0, 12.0),
    (-10.5, -12.0),
    (10.5, -12.0),
]
_ARM_MESH_X_CENTRE = 19.325
BATCH_PLATE_POSITIONS = [
    (tx - _ARM_MESH_X_CENTRE, ty) for tx, ty in BATCH_PLATE_TARGETS
]


VARIANT_PLATES = [
    base.Plate(
        "Broken-ring core · Marine Blue + Ivory White",
        ((1, 0.0, 0.0, 0.0), (2, 0.0, 0.0, 0.0)),
        _plate_position(1),
    ),
    base.Plate(
        "R188 outer-race retaining ring",
        ((3, 0.0, 0.0, 0.0),),
        _plate_position(2),
    ),
    base.Plate(
        "Tough+ split-collet cartridge",
        ((4, -13.0, 0.0, 0.0), (5, 13.0, 0.0, 0.0)),
        _plate_position(3),
    ),
    base.Plate(
        "Removable bayonet thumb pads",
        ((6, -13.0, 0.0, 0.0), (7, 13.0, 0.0, 0.0)),
        _plate_position(4),
    ),
    *[
        base.Plate(
            f"Broken-ring colour block {index}",
            (
                (8 + (index - 1) * 2, 0.0, 0.0, 0.0),
                (9 + (index - 1) * 2, 0.0, 0.0, 0.0),
            ),
            _plate_position(4 + index),
        )
        for index in range(1, 6)
    ],
    base.Plate(
        "Five-up arm batch \u00b7 one colour",
        tuple(
            component
            for index, (x, y) in enumerate(BATCH_PLATE_POSITIONS)
            for component in (
                (18 + index * 2, x, y, 0.0),
                (19 + index * 2, x, y, 0.0),
            )
        ),
        _plate_position(10),
    ),
]

if len(VARIANT_PLATES) != PLATE_COUNT:
    raise RuntimeError(
        f"PLATE_COUNT is {PLATE_COUNT} but VARIANT_PLATES has "
        f"{len(VARIANT_PLATES)} -- the plate grid would be laid out with the "
        "wrong number of columns and objects would land on the wrong beds"
    )

ARM_BASE_IDS = {8, 10, 12, 14, 16}
ARM_INLAY_IDS = {9, 11, 13, 15, 17}
# Plate 10 duplicates arm 1 five times: ids 18..27.
BATCH_PLATE_BASE_IDS = {18, 20, 22, 24, 26}
BATCH_PLATE_INLAY_IDS = {19, 21, 23, 25, 27}
BATCH_ARM_BASE_IDS = {1, 3, 5, 7, 9}
BATCH_ARM_INLAY_IDS = {2, 4, 6, 8, 10}
BATCH_FILAMENTS = [
    complete.FILAMENTS[0],
    OPTICAL_FILAMENT,
]
BATCH_POSITIONS = [
    (0.0, 0.0),
    (-70.0, -70.0),
    (70.0, -70.0),
    (70.0, 70.0),
    (-70.0, 70.0),
]
BATCH_PLATES = [
    base.Plate(
        "Five broken-ring optical colour blocks",
        tuple(
            component
            for index, (x, y) in enumerate(BATCH_POSITIONS)
            for component in (
                (1 + index * 2, x, y, 0.0),
                (2 + index * 2, x, y, 0.0),
            )
        ),
        (128.0, 128.0, 0.0),
    )
]


def _annular_sector(
    inner_r: float,
    outer_r: float,
    start_deg: float,
    end_deg: float,
    steps: int = 12,
) -> Polygon:
    start = math.radians(start_deg)
    end = math.radians(end_deg)
    outer = [
        (
            outer_r * math.cos(start + (end - start) * index / steps),
            outer_r * math.sin(start + (end - start) * index / steps),
        )
        for index in range(steps + 1)
    ]
    inner = [
        (
            inner_r * math.cos(start + (end - start) * index / steps),
            inner_r * math.sin(start + (end - start) * index / steps),
        )
        for index in range(steps, -1, -1)
    ]
    return Polygon(outer + inner)


def _dash_volume(spec: dict, depth: float | None = None) -> trimesh.Trimesh:
    """`depth` overrides INLAY_DEPTH for callers that want a shallower pocket.

    The Solo passes ONE LAYER. Two layers of pocket means the white islands are
    printed twice, and the island count is the whole stringing problem.
    """
    depth = INLAY_DEPTH if depth is None else depth
    pitch = 360.0 / spec["dash_count"]
    dash_angle = pitch * RING_DUTY
    inner_r = spec["radius_mm"] - RING_WIDTH / 2.0
    outer_r = spec["radius_mm"] + RING_WIDTH / 2.0
    z0 = base.CORE_HEIGHT - depth
    height = depth + INLAY_TOP_OVERTRAVEL
    pieces = []
    for index in range(spec["dash_count"]):
        centre = spec["phase_deg"] + index * pitch
        polygon = _annular_sector(
            inner_r,
            outer_r,
            centre - dash_angle / 2.0,
            centre + dash_angle / 2.0,
        )
        pieces.append(base._extrude(polygon, height, z0))
    mesh = trimesh.util.concatenate(pieces)
    return base._finish(mesh, f"{spec['name']} broken-ring cutting volume")


def _drop_tiny_components(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    components = [
        component
        for component in mesh.split(only_watertight=True)
        if abs(float(component.volume)) >= 0.002
    ]
    if not components:
        raise RuntimeError(f"{name} has no printable components")
    return base._finish(trimesh.util.concatenate(components), name)


def _raise_inlay(
    inlay: trimesh.Trimesh,
    name: str,
    proud: float = INLAY_PROUD,
) -> tuple[trimesh.Trimesh, float]:
    """Stand the dashes proud of the top face.

    The flush inlay is a prism with vertical walls, so its cross-section just
    below the top face IS its top face. Extrude that footprint upward and union
    it on. Taking the footprint from the inlay rather than from the nominal ring
    means the cap automatically respects wherever the base actually exists --
    the arm slots cut the core's outer ring, and the arm ring only spans +/-20
    degrees.
    """
    if proud <= 0.0:
        return inlay, 0.0
    section = inlay.section(
        plane_origin=[0.0, 0.0, base.CORE_HEIGHT - 0.02],
        plane_normal=[0.0, 0.0, 1.0],
    )
    if section is None:
        raise RuntimeError(f"{name}: no inlay footprint at the top face")
    planar, _ = section.to_planar(to_2D=np.eye(4), check=False)
    caps = [
        base._extrude(polygon, proud, base.CORE_HEIGHT)
        for polygon in planar.polygons_full
        if polygon.is_valid and polygon.area > 1e-9
    ]
    if not caps:
        raise RuntimeError(f"{name}: inlay footprint is empty")
    added = sum(float(cap.volume) for cap in caps)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        merged = trimesh.boolean.union([inlay, *caps], engine="manifold")
    if merged is None or merged.is_empty:
        raise RuntimeError(f"{name}: proud-inlay union failed")
    return base._finish(merged, name), added


def _split_flush_inlay(
    source: trimesh.Trimesh,
    dash_volume: trimesh.Trimesh,
    name: str,
) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        inlay = trimesh.boolean.intersection(
            [source, dash_volume],
            engine="manifold",
        )
        body = trimesh.boolean.difference(
            [source, dash_volume],
            engine="manifold",
        )
    if inlay is None or inlay.is_empty or body is None or body.is_empty:
        raise RuntimeError(f"{name} flush-inlay boolean failed")
    return (
        _drop_tiny_components(body, f"{name} base"),
        _drop_tiny_components(inlay, f"{name} optical inlay"),
    )


_PROUD_MM3 = {"core": 0.0, "arm": 0.0}


def _build_variant_meshes() -> list[tuple[str, trimesh.Trimesh, int]]:
    core = complete.build_complete_core()
    core_dashes = trimesh.util.concatenate(
        [
            _dash_volume(spec)
            for spec in RING_SPECS
            if spec["target"] == "core"
        ]
    )
    core_pattern = (
        core_dashes
        if IDENTIFIER is None
        else trimesh.util.concatenate(
            [core_dashes, optical._identifier_volume(IDENTIFIER)]
        )
    )
    core_base, core_inlay = _split_flush_inlay(
        core,
        core_pattern,
        "broken-ring core",
    )
    core_inlay, core_proud_mm3 = _raise_inlay(
        core_inlay, "broken-ring core optical inlay"
    )

    arm_spec = next(spec for spec in RING_SPECS if spec["target"] == "arm")
    arm_dashes = _dash_volume(arm_spec)
    installed_arm = complete._arm_installed_orientation(
        complete.build_arm("broken-ring arm")
    )
    arm_base_installed, arm_inlay_installed = _split_flush_inlay(
        installed_arm,
        arm_dashes,
        "broken-ring arm",
    )
    arm_base = complete._flip_arm_for_print(
        arm_base_installed,
        "broken-ring arm base",
    )
    arm_inlay = complete._flip_arm_for_print(
        arm_inlay_installed,
        "broken-ring arm inlay",
    )
    arm_inlay, arm_proud_mm3 = _raise_inlay(
        arm_inlay, "broken-ring arm optical inlay"
    )
    global _PROUD_MM3
    _PROUD_MM3 = {"core": core_proud_mm3, "arm": arm_proud_mm3}

    meshes: list[tuple[str, trimesh.Trimesh, int]] = [
        ("Broken-ring Oggie Spin core", core_base, 1),
        (
            "Ivory White core broken-ring inlay"
            + ("" if IDENTIFIER is None else f" + {IDENTIFIER}"),
            core_inlay,
            OPTICAL_EXTRUDER,
        ),
        ("R188 outer-race retaining ring", complete.build_bearing_ring(), 1),
        ("Tough+ split-collet through-axle hub", complete.build_collet_hub(), TOUGH_EXTRUDER),
        ("Tough+ through-bore receiver hub", complete.build_receiver_hub(), TOUGH_EXTRUDER),
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
    for index in range(1, 6):
        meshes.extend(
            [
                (
                    f"Broken-ring colour block {index}",
                    arm_base.copy(),
                    index,
                ),
                (
                    f"Ivory White arm-ring inlay {index}",
                    arm_inlay.copy(),
                    OPTICAL_EXTRUDER,
                ),
            ]
        )
    return meshes


def _set_metadata(node: ET.Element, key: str, value: str) -> None:
    for item in node.findall("./metadata"):
        if item.get("key") == key:
            item.set("value", value)
            return
    ET.SubElement(node, "metadata", {"key": key, "value": value})


def _variant_model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    root = ET.fromstring(ORIGINAL_MODEL_SETTINGS(objects, meshes))
    for part_id in ARM_BASE_IDS | BATCH_PLATE_BASE_IDS:
        part = root.find(f".//part[@id='{part_id}']")
        if part is None:
            raise RuntimeError(f"missing arm base part {part_id}")
        _set_metadata(part, "wall_loops", "2")
        _set_metadata(part, "sparse_infill_density", "100%")
        _set_metadata(part, "sparse_infill_pattern", "grid")
    for part_id in ARM_INLAY_IDS | BATCH_PLATE_INLAY_IDS:
        part = root.find(f".//part[@id='{part_id}']")
        if part is None:
            raise RuntimeError(f"missing arm inlay part {part_id}")
        _set_metadata(part, "wall_loops", "2")
    for obj in root.findall("./object"):
        part_ids = {int(part.get("id")) for part in obj.findall("./part")}
        if part_ids & (
            ARM_BASE_IDS
            | ARM_INLAY_IDS
            | BATCH_PLATE_BASE_IDS
            | BATCH_PLATE_INLAY_IDS
        ):
            _set_metadata(obj, "wall_loops", "2")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _batch_model_settings(
    objects: list[tuple[str, Path, int]],
    meshes: list[trimesh.Trimesh],
) -> bytes:
    root = ET.fromstring(ORIGINAL_MODEL_SETTINGS(objects, meshes))
    for part_id in BATCH_ARM_BASE_IDS:
        part = root.find(f".//part[@id='{part_id}']")
        if part is None:
            raise RuntimeError(f"missing batch optical arm base {part_id}")
        _set_metadata(part, "wall_loops", "2")
        _set_metadata(part, "sparse_infill_density", "100%")
        _set_metadata(part, "sparse_infill_pattern", "gyroid")
    for part_id in BATCH_ARM_INLAY_IDS:
        part = root.find(f".//part[@id='{part_id}']")
        if part is None:
            raise RuntimeError(f"missing batch optical inlay {part_id}")
        _set_metadata(part, "wall_loops", "2")
    for obj in root.findall("./object"):
        _set_metadata(obj, "wall_loops", "2")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _set_slot_group(
    settings: dict,
    key: str,
    slot_index: int,
    value: str,
) -> None:
    current = settings.get(key)
    if (
        not isinstance(current, list)
        or not current
        or len(current) % len(VARIANT_FILAMENTS)
    ):
        return
    group_size = len(current) // len(VARIANT_FILAMENTS)
    start = slot_index * group_size
    current[start : start + group_size] = [value] * group_size


def _configure_variant_filaments(settings: dict) -> None:
    ORIGINAL_CONFIGURE_FILAMENTS(settings)
    tough_index = TOUGH_EXTRUDER - 1
    settings["filament_settings_id"][tough_index] = "Bambu PLA Tough+ @BBL P2S"
    settings["filament_ids"][tough_index] = "GFA10"
    for key, value in (
        ("nozzle_temperature", "245"),
        ("nozzle_temperature_initial_layer", "245"),
        ("nozzle_temperature_range_low", "230"),
        ("nozzle_temperature_range_high", "260"),
        ("filament_max_volumetric_speed", "21"),
        ("filament_flow_ratio", "0.98"),
        ("filament_density", "1.21"),
    ):
        _set_slot_group(settings, key, tough_index, value)

    # --- the optical slot oozes, and the geometry makes it show ------------
    #
    # Sixty dashes per body means sixty island-to-island hops per white layer.
    # Measured off RING_SPECS: 184.6 mm extruded against 170.4 mm travelled --
    # a travel-to-extrusion ratio of 0.92. The white spends nearly half its
    # distance in the air. The blue, printing continuous perimeters, travels
    # almost not at all, which is why only the white strings even though both
    # are the same material at the same temperature. It is not a worse
    # filament; it is forty-five times more opportunities per layer.
    #
    # So the lever is ooze RATE, and the two things that set it are melt
    # viscosity and how much pressure is left in the nozzle during a hop.
    #
    # 210 C rather than the stock 220: the optical inlay is 2-4 top-surface
    # layers with no structural role, no bridge and no overhang, so the usual
    # reason to keep PLA hot does not apply here. Viscosity rises steeply on
    # the way down. Not lower than this without care -- the AMS cut and ram
    # depend on a clean tip, and a cold tip is how a multi-material print jams.
    #
    # Retraction 1.2 mm rather than 0.8: the stock value is short for the melt
    # zone on a direct drive. Faster (60 mm/s) so the extra distance does not
    # buy more airtime -- retract plus deretract currently costs 53 ms against
    # 34 ms of actual travel, so retraction, not travel, is most of each hop.
    #
    # If the dashes come out starved at their starts, back the length off to
    # 1.0 before touching anything else. A gap at the start of a dash is worse
    # than a string: the dash pattern IS the product, and a string can be
    # picked off.
    optical_index = OPTICAL_EXTRUDER - 1
    for key, value in (
        ("nozzle_temperature", "210"),
        ("nozzle_temperature_initial_layer", "210"),
        ("filament_retraction_length", "1.2"),
        ("filament_retraction_speed", "60"),
        ("filament_deretraction_speed", "60"),
        ("filament_retract_before_wipe", "70%"),
        ("filament_wipe", "1"),
    ):
        _set_slot_group(settings, key, optical_index, value)


def _preview_png(plate_number: int, size: int = 512) -> bytes:
    return complete._preview_png(plate_number, size)


def _rewrite_batch_project_settings(path: Path) -> None:
    temp_path = path.with_suffix(".tmp.3mf")
    with (
        zipfile.ZipFile(path, "r") as source,
        zipfile.ZipFile(
            temp_path,
            "w",
            zipfile.ZIP_DEFLATED,
            compresslevel=7,
        ) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "Metadata/project_settings.config":
                settings = json.loads(data)
                settings["print_sequence"] = "by layer"
                settings["z_hop"] = ["0.6", "0.6"]
                settings["z_hop_types"] = ["Slope Lift", "Slope Lift"]
                settings["reduce_crossing_wall"] = "1"
                settings["max_travel_detour_distance"] = "0"
                settings["retract_when_changing_layer"] = ["1", "1"]
                settings["retraction_length"] = ["0.8", "0.8"]
                settings["retraction_speed"] = ["30", "30"]
                settings["deretraction_speed"] = ["30", "30"]
                settings["retraction_minimum_travel"] = ["1", "1"]
                settings["retract_before_wipe"] = ["70%", "70%"]
                settings["wipe"] = ["1", "1"]
                settings["wipe_distance"] = ["2", "2"]
                settings["enable_prime_tower"] = "1"
                # a zero flush matrix means no purge at all between colours
                settings["flush_volumes_matrix"] = _flush_matrix()
                settings["flush_volumes_vector"] = [
                    str(FLUSH_MAX) for _ in VARIANT_FILAMENTS
                ]
                # send the purge into the arms' own 100% grid infill instead of
                # throwing all of it at the tower; the transitional colour ends
                # up buried where nothing can see it
                settings["flush_into_infill"] = "1"
                data = json.dumps(
                    settings,
                    indent=2,
                    ensure_ascii=False,
                ).encode()
            target.writestr(item, data)
    temp_path.replace(path)


def _write_meshes(
    out_dir: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> list[tuple[str, Path, int]]:
    mesh_dir = out_dir / MESH_DIR_NAME
    mesh_dir.mkdir(parents=True, exist_ok=True)
    objects = []
    for index, (name, mesh, extruder) in enumerate(built, start=1):
        path = mesh_dir / f"{index:02d}_{name.lower().replace(' ', '_')}.stl"
        mesh.export(path)
        reloaded = trimesh.load_mesh(path, process=True)
        base._finish(reloaded, f"serialized {name}")
        objects.append((name, path, extruder))
    return objects


def _flush_volume(src_hex: str, dst_hex: str) -> int:
    """Purge volume for one ordered filament transition, in mm3.

    The generated project shipped a flush_volumes_matrix of ALL ZEROS, which is
    what Bambu Studio warns about with "partial purging volume set to 0 ... may
    cause color mixing". Zero purge means the first millimetres of Ivory White
    come out tinted with whatever ran before it -- on a design whose entire
    point is a crisp white-on-colour optical pattern, that is not cosmetic.

    Bambu's own calculator scales purge with colour distance and penalises going
    to a LIGHTER colour, because covering a dark residue takes far more material
    than a light one. Same shape here.
    """
    def rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def luma(c: tuple[int, int, int]) -> float:
        return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0

    src, dst = rgb(src_hex), rgb(dst_hex)
    if src == dst:
        return 0
    distance = sum(abs(a - b) for a, b in zip(src, dst)) / (3.0 * 255.0)
    lightening = max(0.0, luma(dst) - luma(src))
    volume = FLUSH_MIN + distance * 140.0 + lightening * 240.0
    return int(round(min(FLUSH_MAX, volume)))


def _flush_matrix() -> list[str]:
    return [
        str(_flush_volume(a[1], b[1]))
        for a in VARIANT_FILAMENTS
        for b in VARIANT_FILAMENTS
    ]


def rewrite_project_settings(path: Path, changes: dict) -> None:
    """Apply project-settings changes to an already-written 3MF, in place.

    Opt-in and per-caller on purpose. The obvious place for these would be
    _rewrite_variant_project_settings, but that runs for the modular spinner
    too, and the settings below are chosen for a disc with sixty white islands
    on its top face. The modular arms are neither.
    """
    temp_path = path.with_suffix(".tmp.3mf")
    with (
        zipfile.ZipFile(path, "r") as source,
        zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "Metadata/project_settings.config":
                settings = json.loads(data)
                settings.update(changes)
                data = json.dumps(settings, indent=2, ensure_ascii=False).encode()
            target.writestr(item, data)
    temp_path.replace(path)


# The anti-stringing set for a top face made of many small white islands.
#
# arachne: with `classic`, a loop around a 1.10 mm dash pocket lays 0.42 mm in
# from each side and leaves 0.26 mm uncovered down the middle -- too narrow for
# another loop, so classic fills it with a separate gap-fill sliver at
# 250 mm/s. That is an extra start and stop inside EVERY dash, sixty-five per
# layer, 260 per part. Arachne fits the same strip with two ~0.55 mm beads: no
# sliver, no second start-stop, solid dash.
#
# top surface speed AND acceleration: the speed cap alone does almost nothing
# here, and it is worth being clear about why. A 3 mm dash accelerating at
# 2000 mm/s2 peaks at sqrt(a*d) = 77 mm/s and then decelerates -- it never
# comes near the 200 mm/s cap, so lowering the cap to 150 or 100 would change
# nothing at all. Dropping the cap to 50 and the acceleration to 800 gives
# sqrt(800*3) = 49 mm/s, about a third off the peak. Lower speed at the end of
# a dash means lower pressure left in the nozzle when the travel starts, which
# is the thing that oozes.
ANTI_STRINGING_SETTINGS = {
    "wall_generator": "arachne",
    "min_bead_width": "70%",
    "top_surface_speed": ["50", "50"],
    "top_surface_acceleration": ["800", "800"],
}


def _rewrite_variant_project_settings(path: Path) -> None:
    """Travel settings tuned for the five-up plate.

    Plate 10 prints five parts by layer, so the nozzle crosses finished walls
    constantly -- which the nine single-object plates never made it do. The
    stock 0.4 mm Auto Lift is not enough clearance once there are five 14 mm
    towers to catch a curled edge on.

    These are global (Bambu keeps travel and retraction in the print profile,
    not per plate), but none of them hurt a one-object plate: slope lift and
    wall avoidance cost a little time and nothing else.
    """
    temp_path = path.with_suffix(".tmp.3mf")
    with (
        zipfile.ZipFile(path, "r") as source,
        zipfile.ZipFile(
            temp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7
        ) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "Metadata/project_settings.config":
                settings = json.loads(data)
                # clear the parts, do not scrape over them
                settings["z_hop"] = ["0.6", "0.6"]
                settings["z_hop_types"] = ["Slope Lift", "Slope Lift"]
                # do not drag a travel move across a finished perimeter
                settings["reduce_crossing_wall"] = "1"
                settings["max_travel_detour_distance"] = "0"
                # five parts means long inter-object travels; wipe on the way out
                settings["retract_before_wipe"] = ["70%", "70%"]
                settings["wipe"] = ["1", "1"]
                settings["wipe_distance"] = ["2", "2"]
                settings["retract_when_changing_layer"] = ["1", "1"]
                settings["retraction_minimum_travel"] = ["1", "1"]
                settings["print_sequence"] = "by layer"
                settings["enable_prime_tower"] = "1"
                # a zero flush matrix means no purge at all between colours
                settings["flush_volumes_matrix"] = _flush_matrix()
                settings["flush_volumes_vector"] = [
                    str(FLUSH_MAX) for _ in VARIANT_FILAMENTS
                ]
                # send the purge into the arms' own 100% grid infill instead of
                # throwing all of it at the tower; the transitional colour ends
                # up buried where nothing can see it
                settings["flush_into_infill"] = "1"
                data = json.dumps(
                    settings, indent=2, ensure_ascii=False
                ).encode()
            target.writestr(item, data)
    temp_path.replace(path)


def _build_project(
    out_dir: Path,
    objects: list[tuple[str, Path, int]],
) -> Path:
    output = out_dir / OUTPUT_NAME
    # Plate 10 reuses arm 1's two STLs five times over. They are extra OBJECTS,
    # not extra meshes: nothing new is written to broken-ring-meshes/, and the
    # geometry is by construction identical to the arm that ships on plate 5.
    arm_base_object = objects[7]
    arm_inlay_object = objects[8]
    objects = list(objects) + [
        entry
        for index in range(5)
        for entry in (
            (f"Five-up arm batch block {index + 1}", arm_base_object[1], arm_base_object[2]),
            (
                f"Five-up arm batch inlay {index + 1}",
                arm_inlay_object[1],
                OPTICAL_EXTRUDER,
            ),
        )
    ]
    previous = (
        base.PLATES,
        base.FILAMENTS,
        base._preview_png,
        base._model_settings,
        base._configure_filament_slots,
    )
    try:
        base.PLATES = VARIANT_PLATES
        base.FILAMENTS = VARIANT_FILAMENTS
        base._preview_png = _preview_png
        base._model_settings = _variant_model_settings
        base._configure_filament_slots = _configure_variant_filaments
        base.build_bambu_project(output, objects)
    finally:
        (
            base.PLATES,
            base.FILAMENTS,
            base._preview_png,
            base._model_settings,
            base._configure_filament_slots,
        ) = previous
    _rewrite_variant_project_settings(output)
    return output


def _build_batch_project(
    out_dir: Path,
    complete_objects: list[tuple[str, Path, int]],
) -> Path:
    output = out_dir / BATCH_OUTPUT_NAME
    objects = []
    for index in range(5):
        base_object = complete_objects[7 + index * 2]
        inlay_object = complete_objects[8 + index * 2]
        objects.extend(
            [
                (
                    f"Broken-ring batch block {index + 1}",
                    base_object[1],
                    1,
                ),
                (
                    f"Ivory White broken-ring inlay {index + 1}",
                    inlay_object[1],
                    2,
                ),
            ]
        )
    previous = (
        base.PLATES,
        base.FILAMENTS,
        base._preview_png,
        base._model_settings,
        base._configure_filament_slots,
    )
    try:
        base.PLATES = BATCH_PLATES
        base.FILAMENTS = BATCH_FILAMENTS
        base._preview_png = complete._batch_preview_png
        base._model_settings = _batch_model_settings
        base._configure_filament_slots = ORIGINAL_CONFIGURE_FILAMENTS
        base.build_bambu_project(output, objects)
    finally:
        (
            base.PLATES,
            base.FILAMENTS,
            base._preview_png,
            base._model_settings,
            base._configure_filament_slots,
        ) = previous
    _rewrite_batch_project_settings(output)
    return output


def _validate_batch(output: Path) -> dict:
    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("broken-ring batch 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = ET.fromstring(
            package.read("Metadata/model_settings.config")
        )
        plates = settings.findall("./plate")
        if len(plates) != 1:
            raise RuntimeError("broken-ring batch must contain one plate")
        parts = settings.findall(".//part")
        if len(parts) != 10:
            raise RuntimeError("broken-ring batch must contain ten paired parts")
        project = json.loads(
            package.read("Metadata/project_settings.config")
        )
        if project.get("print_sequence") != "by layer":
            raise RuntimeError("broken-ring batch lost by-layer sequencing")
        if project.get("z_hop") != ["0.6", "0.6"]:
            raise RuntimeError("broken-ring batch lost 0.6 mm Z hop")
        if project.get("z_hop_types") != ["Slope Lift", "Slope Lift"]:
            raise RuntimeError("broken-ring batch lost slope Z hop")
        if project.get("enable_prime_tower") != "1":
            raise RuntimeError("broken-ring batch lost its prime tower")
        part_extruders = {
            int(part.get("id")): next(
                item.get("value")
                for item in part.findall("./metadata")
                if item.get("key") == "extruder"
            )
            for part in parts
        }
        if {
            part_id
            for part_id, extruder in part_extruders.items()
            if extruder == "2"
        } != BATCH_ARM_INLAY_IDS:
            raise RuntimeError("broken-ring batch inlays are not on slot 2")
    return {
        "project": output.name,
        "pieces": 5,
        "base_filament_slot": 1,
        "optical_filament_slot": 2,
        "print_sequence": "by layer",
        "z_hop_mm": 0.6,
        "z_hop_type": "Slope Lift",
        "infill": "100% gyroid",
        "prime_tower": True,
    }


def _assert_objects_on_their_plates(
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> dict:
    """Every object must land inside the bed of the plate it is assigned to.

    Bambu Studio positions plate n's bed at ceil(sqrt(plate_count)) columns of
    PLATE_STRIDE. If our plate positions use a different column count the model
    still opens, still slices, and still reports no warnings -- the objects are
    simply sitting on somebody else's bed, or on none. That is exactly what
    happened when the tenth plate took the grid from 3 columns to 4, and nothing
    in the build caught it. This does.
    """
    half = BED_SIZE / 2.0
    worst = 0.0
    for number, plate in enumerate(VARIANT_PLATES, start=1):
        px, py, _ = plate.position
        expected = _plate_position(number)
        if (px, py) != (expected[0], expected[1]):
            raise RuntimeError(
                f"plate {number} is at {(px, py)} but the {PLATE_COLUMNS}-column "
                f"grid puts it at {expected[:2]}"
            )
        for object_id, dx, dy, _dz in plate.components:
            mesh = built[object_id - 1][1] if object_id <= len(built) else None
            if mesh is None:
                # plate 10 duplicates arm 1; ids 18.. reuse its geometry
                mesh = built[7][1] if object_id % 2 == 0 else built[8][1]
            lo, hi = mesh.bounds[0], mesh.bounds[1]
            for span, offset in ((lo[0], dx), (hi[0], dx)):
                worst = max(worst, abs(span + offset))
            for span, offset in ((lo[1], dy), (hi[1], dy)):
                worst = max(worst, abs(span + offset))
            if (
                abs(lo[0] + dx) > half or abs(hi[0] + dx) > half
                or abs(lo[1] + dy) > half or abs(hi[1] + dy) > half
            ):
                raise RuntimeError(
                    f"plate {number} object {object_id} falls outside its "
                    f"{BED_SIZE:.0f} mm bed"
                )
    return {
        "plate_columns": PLATE_COLUMNS,
        "plate_stride_mm": PLATE_STRIDE,
        "worst_object_reach_from_plate_centre_mm": round(worst, 2),
        "bed_half_size_mm": half,
    }


def _validate(
    output: Path,
    built: list[tuple[str, trimesh.Trimesh, int]],
) -> dict:
    with zipfile.ZipFile(output) as package:
        if package.testzip() is not None:
            raise RuntimeError("broken-ring 3MF failed ZIP integrity")
        base.bambu.assert_object_id_hygiene(package)
        settings = ET.fromstring(
            package.read("Metadata/model_settings.config")
        )
        plates = settings.findall("./plate")
        if len(plates) != len(VARIANT_PLATES):
            raise RuntimeError("broken-ring 3MF lost its nine-plate layout")
        project = json.loads(
            package.read("Metadata/project_settings.config")
        )
        if len(project.get("filament_settings_id", [])) != len(
            VARIANT_FILAMENTS
        ):
            raise RuntimeError("broken-ring 3MF lost a filament slot")
        if (
            project["filament_settings_id"][TOUGH_EXTRUDER - 1]
            != "Bambu PLA Tough+ @BBL P2S"
        ):
            raise RuntimeError("broken-ring 3MF lost Tough+ cartridge profile")
        part_extruders = {
            int(part.get("id")): next(
                item.get("value")
                for item in part.findall("./metadata")
                if item.get("key") == "extruder"
            )
            for part in settings.findall(".//part")
        }
        expected_optical = {2, *ARM_INLAY_IDS, *BATCH_PLATE_INLAY_IDS}
        if {
            part_id
            for part_id, extruder in part_extruders.items()
            if extruder == str(OPTICAL_EXTRUDER)
        } != expected_optical:
            raise RuntimeError("optical inlays are not isolated on slot 7")

    plate_layout = _assert_objects_on_their_plates(built)

    arm_totals = []
    partition_overlaps = []
    for index in range(5):
        base_mesh = built[7 + index * 2][1]
        inlay_mesh = built[8 + index * 2][1]
        arm_totals.append(float(base_mesh.volume + inlay_mesh.volume))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            overlap = trimesh.boolean.intersection(
                [base_mesh, inlay_mesh],
                engine="manifold",
            )
        partition_overlaps.append(
            0.0 if overlap is None or overlap.is_empty else abs(float(overlap.volume))
        )
    if max(arm_totals) - min(arm_totals) > 1e-6:
        raise RuntimeError("broken-ring arms are not mass matched")
    original_core_volume = float(complete.build_complete_core().volume)
    variant_core_volume = float(built[0][1].volume + built[1][1].volume)
    original_arm_volume = float(
        complete.build_arm("validation reference arm").volume
    )
    # With proud dashes, base + inlay = original + the raised caps. Subtract the
    # caps so this still verifies the PARTITION, which is what it is really for.
    core_proud = _PROUD_MM3["core"]
    arm_proud = _PROUD_MM3["arm"]
    if abs(variant_core_volume - core_proud - original_core_volume) > 0.01:
        raise RuntimeError("core inlays do not reconstruct the original core volume")
    if any(
        abs(value - arm_proud - original_arm_volume) > 0.01 for value in arm_totals
    ):
        raise RuntimeError("arm inlays do not reconstruct the original arm volume")
    if max(partition_overlaps) > 0.001:
        raise RuntimeError("optical inlay overlaps its base geometry")
    return {
        "project": output.name,
        "status": (
            "through-slot arms with the snap clip on the exposed far face; "
            "slice- and printability-validated, physical gates pending"
        ),
        "plates": len(VARIANT_PLATES),
        "plate_layout": plate_layout,
        "meshes": len(built),
        "objects": len(built) + 10,  # plate 10 duplicates arm 1 five times
        "filament_slots": len(VARIANT_FILAMENTS),
        "optical_filament_slot": OPTICAL_EXTRUDER,
        "underside_identifier": IDENTIFIER,
        "inlay_depth_mm": INLAY_DEPTH,
        "inlay_proud_mm": INLAY_PROUD,
        "inlay_proud_volume_mm3": {
            "core": round(_PROUD_MM3["core"], 4),
            "arm": round(_PROUD_MM3["arm"], 4),
        },
        "ring_width_mm": RING_WIDTH,
        "ring_duty": RING_DUTY,
        "rings": RING_SPECS,
        "arm_total_volume_mm3": [round(value, 6) for value in arm_totals],
        "arm_volume_spread_mm3": round(max(arm_totals) - min(arm_totals), 9),
        "core_volume_difference_mm3": round(
            variant_core_volume - original_core_volume,
            9,
        ),
        "arm_volume_difference_mm3": round(
            arm_totals[0] - original_arm_volume,
            9,
        ),
        "maximum_base_inlay_overlap_mm3": round(
            max(partition_overlaps),
            9,
        ),
        "mechanical_geometry_source": (
            "Oggie Spin complete: solid dovetail tongue through a full-height "
            "core slot, tongue-tip cantilever barb into an open underside recess"
        ),
        "printability": complete.audit_printability(
            [(name, mesh) for name, mesh, _ in built]
        ),
        "original_projects_modified": False,
    }


def generate(out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    built = _build_variant_meshes()
    objects = _write_meshes(out_dir, built)
    output = _build_project(out_dir, objects)
    report = _validate(output, built)
    # The standalone Oggie_Spin_5x_Broken_Ring_P2S.3mf is retired: plate 10 of
    # the main project now carries the five-up arm batch, so there is no second
    # file to keep in step (or to remember to delete after every rebuild).
    report["five_piece_batch"] = "folded into plate 10 of the main project"
    (out_dir / REPORT_NAME).write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    stale_batch = out_dir / BATCH_OUTPUT_NAME
    if stale_batch.exists():
        stale_batch.unlink()
    return [output]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in generate(args.out):
        print(path)
