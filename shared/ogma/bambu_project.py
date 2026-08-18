#!/usr/bin/env python3
"""Build a native, externally-referenced four-plate Bambu Studio 3MF.

This follows the package structure used by known-good local Bambu projects:
each embedded object has one mesh resource and no nested <build> element.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh

from ogma.paint import FuzzyPainter


from ogma import assets

log = logging.getLogger("ogma.bambu_project")

OUT = assets.OUT_ROOT / "cooper_dog_bowl"
MESH_DIR = OUT / "meshes"
WORK = assets.PLATE_PREVIEWS
TEMPLATE = assets.BLANK_PROJECT
OUTPUT = OUT / "Cooper_Paw_Lattice_P2S.3mf"

# Mutated by build_project() for each job.
OBJECTS: list[tuple[str, Path, int]] = []
BUILD_POSITIONS: list[tuple[float, float, float]] = []
# How many of OBJECTS are body parts; the rest are letters. Set by each
# configure_* function. The plate split used to be derived by sniffing OBJECTS[0]
# for the words "wave lower" or "honeycomb body", which cannot tell a one-piece
# paw lattice from a three-part one — they differ in count, not in name.
BODY_COUNT = 0

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
BAMBU = "http://schemas.bambulab.com/package/2021"


# --------------------------------------------------------------------------
# Letters are an optional part.
#
# The name is cut into the stand as pockets either way — that geometry belongs
# to the body mesh and never changes. What `include_letters` decides is whether
# the *glue-in* letters are printed alongside it. Off, the customer gets a
# single-colour stand with the name debossed; on, they get the second-colour
# inserts that drop into those pockets.
#
# Everything downstream keys off OBJECTS, so omitting them here is enough: no
# letter meshes, no letters plate, no per-letter print settings, and — because
# nothing is left referencing extruder 2 — a one-filament job.
# --------------------------------------------------------------------------


def _letter_objects(name: str) -> list[tuple[str, Path, int]]:
    """One object per character, on extruder 2.

    Labels are deduplicated so a name with a repeated character ("ANNA") gives
    "Letter N" and "Letter N 2" rather than two entries Studio shows identically.
    """
    objects: list[tuple[str, Path, int]] = []
    seen: dict[str, int] = {}
    for index, ch in enumerate(name, start=1):
        seen[ch] = seen.get(ch, 0) + 1
        label = f"Letter {ch}" if seen[ch] == 1 else f"Letter {ch} {seen[ch]}"
        objects.append((label, MESH_DIR / f"letter_{index}_{ch}.stl", 2))
    return objects


def _letter_positions(
    count: int, x0: float, y0: float, cols: int = 4
) -> list[tuple[float, float, float]]:
    """Lay `count` letters out on their own plate of the 312 mm grid."""
    return [
        (x0 + (i % cols) * 24.0, y0 + (i // cols) * 32.0, 0.0) for i in range(count)
    ]


def _filament_slots(
    *,
    stand_hex: str,
    letter_hex: str,
    stand_name: str,
    letter_name: str,
    include_letters: bool,
    upper_hex: str | None = None,
    upper_name: str | None = None,
) -> tuple[list[str], list[str]]:
    """`(filament_colour, filament_settings_id)` for the project's slots.

    Two slots normally — stand and letters. A third when the body is two-tone:
    the split wave's sine seam divides it into a lower and an upper shell that
    are separate objects on separate plates, so they can take separate filament.
    Slot order is stand, letters, upper, which keeps letters on extruder 2 for
    every style rather than shuffling them when a third colour appears.

    Slot 2 still exists on a one-colour job. `filament_ids` and `filament_type`
    are re-derived to match this length by the caller, and tests/audit_3mf.py
    requires all three arrays to agree — dropping a slot would desynchronise the
    settings rather than simplify them. What changes is what slot 2 *says*: with
    letters off nothing references extruder 2, so naming the stand colour twice
    is the honest description of a job that prints in one.
    """
    profile = "Bambu PLA Matte @Ogma {}".format
    if include_letters:
        colours = [stand_hex, letter_hex]
        names = [profile(stand_name), profile(letter_name)]
    else:
        colours = [stand_hex, stand_hex]
        names = [profile(stand_name)] * 2
    if upper_hex is not None:
        colours.append(upper_hex)
        names.append(profile(upper_name or "Upper"))
    return colours, names


def _apply_filaments(
    settings: dict, colours: list[str], names: list[str]
) -> None:
    """Write the filament arrays, keeping every per-slot list the same length.

    `filament_ids` and `filament_type` come from the template with two entries.
    A three-filament project has to extend them or the arrays disagree, which is
    exactly what tests/audit_3mf.py checks — and a mismatch there is the kind of
    thing that only shows up when Bambu Studio opens the file.
    """
    count = len(colours)
    settings["filament_colour"] = colours
    settings["default_filament_colour"] = [""] * count
    settings["filament_settings_id"] = names
    for key, fallback in (("filament_ids", "GFA01"), ("filament_type", "PLA")):
        existing = list(settings.get(key) or [fallback])
        settings[key] = (existing + [existing[-1]] * count)[:count]


def configure_objects(
    mesh_dir: Path,
    name: str,
    *,
    include_letters: bool = True,
    one_piece: bool = False,
) -> None:
    """Build OBJECTS + BUILD_POSITIONS for the Cooper paw-lattice layout."""
    global OBJECTS, BUILD_POSITIONS, MESH_DIR, BODY_COUNT
    MESH_DIR = Path(mesh_dir)
    if one_piece:
        objects: list[tuple[str, Path, int]] = [
            (f"{name} stand", MESH_DIR / "cooper_one_piece.ply", 1),
        ]
        positions: list[tuple[float, float, float]] = [(128.0, 128.0, 0.0)]
    else:
        objects = [
            (f"{name} bowl base", MESH_DIR / "cooper_base.stl", 1),
            (f"{name} paw panel", MESH_DIR / "cooper_paw_panel.stl", 1),
            (f"{name} top seat ring", MESH_DIR / "cooper_top_seat_ring.stl", 1),
        ]
        positions = [
            (128.0, 128.0, 0.0),
            (440.0, 128.0, 0.0),
            (128.0, -184.0, 0.0),
        ]
    BODY_COUNT = len(objects)
    if include_letters:
        objects += _letter_objects(name)
        positions += _letter_positions(len(name), 405.0, -196.0)
    OBJECTS = objects
    BUILD_POSITIONS = positions


def configure_wave_objects(
    mesh_dir: Path, name: str, *, include_letters: bool = True
) -> None:
    """Build OBJECTS + BUILD_POSITIONS for the split wave layout."""
    global OBJECTS, BUILD_POSITIONS, MESH_DIR, BODY_COUNT
    MESH_DIR = Path(mesh_dir)
    # Extruder 3 for the upper shell and the seat insert: the sine seam is the
    # whole point of this style, and it only reads as a seam if the two halves
    # can be different colours. The seat insert goes with the upper because that
    # is where it sits — a ring at the very top, its rim visible around the bowl.
    objects: list[tuple[str, Path, int]] = [
        (f"{name} wave lower", MESH_DIR / "wave_lower.ply", 1),
        (f"{name} wave upper shell — print inverted", MESH_DIR / "wave_upper.ply", 3),
        (f"{name} bowl-seat insert — print inverted", MESH_DIR / "wave_seat_insert.ply", 3),
    ]
    positions: list[tuple[float, float, float]] = [
        (128.0, 128.0, 0.0),
        (440.0, 128.0, 0.0),
        (128.0, -184.0, 0.0),
    ]
    BODY_COUNT = len(objects)
    if include_letters:
        objects += _letter_objects(name)
        # Letters occupy plate 4 on the second row of the 312 mm grid.
        positions += _letter_positions(len(name), 392.0, -220.0)
    OBJECTS = objects
    BUILD_POSITIONS = positions


def configure_hex_objects(
    mesh_dir: Path,
    name: str,
    body_mesh: str = "honeycomb_body.ply",
    body_label: str = "honeycomb body",
    *,
    include_letters: bool = True,
) -> None:
    """Build OBJECTS + BUILD_POSITIONS for a single-body drum layout.

    Shared by every drum style — honeycomb, fluted, and anything else that is
    one textured body plus a letters plate. Only the body mesh filename differs,
    so it is a parameter rather than a copy of this function.
    """
    global OBJECTS, BUILD_POSITIONS, MESH_DIR, BODY_COUNT
    MESH_DIR = Path(mesh_dir)
    objects: list[tuple[str, Path, int]] = [
        (f"{name} {body_label}", MESH_DIR / body_mesh, 1),
    ]
    positions: list[tuple[float, float, float]] = [
        (128.0, 128.0, 0.0),
    ]
    BODY_COUNT = len(objects)
    if include_letters:
        objects += _letter_objects(name)
        positions += _letter_positions(len(name), 392.0, 96.0)
    OBJECTS = objects
    BUILD_POSITIONS = positions


# --------------------------------------------------------------------------
# Assembly view
#
# Bambu Studio has an Assembly View that shows the parts of a project as the
# finished object rather than as plates. This package always declared one, and it
# was useless: every `assemble_item` carried an identity transform and a zero
# offset, so all four parts sat on top of each other at the origin.
#
# The information to fill it in has been on disk the whole time. Each generator
# writes every part twice — flat in print orientation, and again positioned in
# the finished assembly as `assembly_<part>.stl` — and the two files are the same
# mesh with the same vertex ordering, so the transform between them is exactly
# recoverable rather than estimated. Measured on the paw lattice: a pure
# translation of +9 mm in Z for the panel and +72 mm for the top seat ring, with
# a fit residual of 0.000000 mm.
#
# This affects the Assembly View only. Plates and slicing read `<plate>` and the
# per-object models, so a transform this code declines to compute costs a nicer
# preview and nothing else.
# --------------------------------------------------------------------------

# Above this, the two files are not the same rigid body and the pairing is wrong.
ASSEMBLY_FIT_TOLERANCE_MM = 1e-3


def _assembly_twin(print_path: Path) -> Path | None:
    """The `assembly_*` file for a print-orientation mesh, if there is one.

    Matched by *suffix*, not equality, for the reason given in
    ogma.preview.assembled_meshes: the paw lattice writes `cooper_paw_panel.stl`
    beside `assembly_paw_panel.stl`, while the fluted drum writes
    `fluted_body.ply` beside `assembly_fluted_body.stl`. The extensions differ
    too, so only the stem is compared.
    """
    directory = print_path.parent
    if not directory.is_dir():
        return None
    for candidate in directory.glob("assembly_*"):
        if print_path.stem.endswith(candidate.stem[len("assembly_") :]):
            return candidate
    return None


def _assembly_transform(print_path: Path):
    """Rigid transform taking the print-orientation part to its assembled pose.

    Both files are re-read here with `process=False` rather than reusing the
    mesh the caller already loaded. The caller loads with `process=True`, which
    merges and reorders vertices — and this fit relies on the two files having
    *the same vertex at the same index*. Reusing the processed copy silently
    destroyed the correspondence and every part came back identity.

    Returns None when the pose cannot be established — no twin, a different
    vertex count, or a fit that is not rigid. That is the honest answer: a wrong
    assembly is worse than an obviously unassembled one. It is also why a body
    written as `.ply` gets no pose — PLY shares vertices where STL repeats them
    per triangle, so the counts legitimately differ and there is no index
    correspondence to exploit.
    """
    twin = _assembly_twin(print_path)
    if twin is None:
        return None
    try:
        original = trimesh.load_mesh(print_path, process=False)
        assembled = trimesh.load_mesh(twin, process=False)
    except Exception:  # noqa: BLE001
        return None

    source = np.asarray(original.vertices)
    target = np.asarray(assembled.vertices)
    if source.shape != target.shape or len(source) < 3:
        return None

    # Kabsch. Correspondence is by index, which holds because the two files are
    # written from the same mesh object with a transform applied.
    src_c, dst_c = source.mean(axis=0), target.mean(axis=0)
    u, _, vt = np.linalg.svd((source - src_c).T @ (target - dst_c))
    flip = np.sign(np.linalg.det(vt.T @ u.T))
    rotation = vt.T @ np.diag([1.0, 1.0, flip]) @ u.T
    translation = dst_c - rotation @ src_c

    if np.abs(source @ rotation.T + translation - target).max() > ASSEMBLY_FIT_TOLERANCE_MM:
        return None
    return rotation, translation


def _assemble_attrs(rotation, translation) -> str:
    """Bambu's 12-float `transform`: three basis columns, then the translation."""
    values = [*rotation[:, 0], *rotation[:, 1], *rotation[:, 2], *translation]
    return " ".join(f"{v:.6f}" for v in values)


def object_uuid(index: int, suffix: int = 0) -> str:
    return f"{index:08x}-89ab-4cde-9012-{suffix:012x}"


def mesh_model(
    mesh: trimesh.Trimesh,
    object_id: int,
    paint_fuzzy: np.ndarray | None = None,
) -> bytes:
    mesh = mesh.copy()
    # When a paint mask is supplied it is index-aligned with the caller's faces;
    # skip cleanup that could reorder topology.
    if paint_fuzzy is None:
        mesh.remove_unreferenced_vertices()
    elif len(paint_fuzzy) != len(mesh.faces):
        raise ValueError("paint mask length must match face count")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}" '
        f'xmlns:BambuStudio="{BAMBU}" xmlns:p="{PROD}" requiredextensions="p">',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        " <resources>",
        f'  <object id="{object_id}" p:UUID="{object_uuid(object_id, 0x123456789ABC)}" type="model">',
        "   <mesh>",
        "    <vertices>",
    ]
    lines.extend(
        f'     <vertex x="{x:.8f}" y="{y:.8f}" z="{z:.8f}"/>'
        for x, y, z in mesh.vertices
    )
    lines.extend(["    </vertices>", "    <triangles>"])
    for face_i, (a, b, c) in enumerate(mesh.faces):
        paint = ""
        if paint_fuzzy is not None and paint_fuzzy[face_i]:
            paint = ' paint_fuzzy_skin="4"'
        lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}"{paint}/>')
    lines.extend(
        [
            "    </triangles>",
            "   </mesh>",
            "  </object>",
            " </resources>",
            "</model>",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def top_model() -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE}" '
        f'xmlns:BambuStudio="{BAMBU}" xmlns:p="{PROD}" requiredextensions="p">',
        " <metadata name=\"Application\">BambuStudio-02.07.01.62</metadata>",
        " <metadata name=\"BambuStudio:3mfVersion\">1</metadata>",
        " <metadata name=\"Title\">Cooper Paw-Lattice Bowl</metadata>",
        " <resources>",
    ]
    for index in range(1, len(OBJECTS) + 1):
        top_id = 99 + index
        lines.extend(
            [
                f'  <object id="{top_id}" p:UUID="{object_uuid(top_id, 0xABCDEF123456)}" type="model">',
                "   <components>",
                f'    <component p:path="/3D/Objects/object_{index}.model" objectid="{index}" '
                f'p:UUID="{object_uuid(0x1000 + index, 0xABCDEF123456)}" '
                'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>',
                "   </components>",
                "  </object>",
            ]
        )
    lines.extend([" </resources>", f' <build p:UUID="{object_uuid(9999, 0xABCDEF123456)}">'])
    for index, (x, y, z) in enumerate(BUILD_POSITIONS, start=1):
        top_id = 99 + index
        lines.append(
            f'  <item objectid="{top_id}" p:UUID="{object_uuid(5000 + index, 0xABCDEF123456)}" '
            f'transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} {z:.3f}" printable="1"/>'
        )
    lines.extend([" </build>", "</model>"])
    return ("\n".join(lines) + "\n").encode()


def model_settings(meshes: list[trimesh.Trimesh]) -> bytes:
    wave_mode = "wave lower" in OBJECTS[0][0].lower()
    hex_mode = "honeycomb body" in OBJECTS[0][0].lower()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for index, ((name, source, extruder), mesh) in enumerate(zip(OBJECTS, meshes), start=1):
        top_id = 99 + index
        # Object overrides prioritise steady layer time + solid outer skin:
        # 4 walls (hides infill telegraphing / protects letter sockets), gyroid.
        if wave_mode or hex_mode:
            body_object = index <= 3 if wave_mode else index == 1
            if body_object:
                body_layer = "0.16" if hex_mode else "0.20"
                overrides = {
                    "layer_height": body_layer if index == 1 else "0.16",
                    "wall_loops": "4",
                    "sparse_infill_density": "15%",
                    "sparse_infill_pattern": "gyroid",
                    "outer_wall_speed": "100",
                    "inner_wall_speed": "200",
                    "small_perimeter_speed": "100%",
                    "top_shell_layers": "5",
                    "bottom_surface_pattern": "monotonic",
                    "top_surface_pattern": "monotonicline",
                    "seam_position": "back",
                    "fuzzy_skin": "none",
                }
                if wave_mode and index == 2:
                    overrides.update(
                        {
                            "enable_support": "1",
                            "support_type": "normal(auto)",
                            "support_style": "default",
                            "support_critical_regions_only": "1",
                            "support_on_build_plate_only": "0",
                            "support_interface_top_layers": "2",
                            "support_top_z_distance": "0.20",
                        }
                    )
            else:
                overrides = {
                    "layer_height": "0.10",
                    "wall_loops": "4",
                    "sparse_infill_density": "15%",
                    "sparse_infill_pattern": "gyroid",
                    "outer_wall_speed": "50",
                    "inner_wall_speed": "100",
                    "small_perimeter_speed": "50%",
                    "top_shell_layers": "6",
                    "bottom_shell_layers": "5",
                    "seam_position": "back",
                    "fuzzy_skin": "none",
                }
        elif index == 1:
            overrides = {
                "layer_height": "0.20",
                "wall_loops": "4",
                "sparse_infill_density": "15%",
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": "150",
                "inner_wall_speed": "250",
                "small_perimeter_speed": "100%",
                "top_shell_layers": "4",
                "bottom_surface_pattern": "monotonic",
                "top_surface_pattern": "monotonicline",
                "seam_position": "back",
                "fuzzy_skin": "external",
                "fuzzy_skin_thickness": "0.3",
                "fuzzy_skin_point_distance": "0.8",
            }
        elif index == 2:
            overrides = {
                "layer_height": "0.16",
                "wall_loops": "4",
                "sparse_infill_density": "15%",
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": "100",
                "inner_wall_speed": "200",
                "small_perimeter_speed": "100%",
                "top_shell_layers": "5",
                "bottom_surface_pattern": "monotonic",
                "top_surface_pattern": "monotonicline",
                "seam_position": "back",
                # "none" = Studio "None (allow paint)". Painted triangles carry
                # the fuzz; disabled_fuzzy would kill painting entirely.
                "fuzzy_skin": "none",
                "fuzzy_skin_thickness": "0.3",
                "fuzzy_skin_point_distance": "0.8",
            }
        elif index == 3:
            overrides = {
                "layer_height": "0.16",
                "wall_loops": "4",
                "sparse_infill_density": "15%",
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": "100",
                "inner_wall_speed": "200",
                "small_perimeter_speed": "100%",
                "top_shell_layers": "5",
                "bottom_surface_pattern": "monotonic",
                "top_surface_pattern": "monotonicline",
                "seam_position": "back",
                "fuzzy_skin": "none",
            }
        else:
            # Letters: fine layers for edges/curves; slower walls for outline quality.
            overrides = {
                "layer_height": "0.10",
                "wall_loops": "4",
                "sparse_infill_density": "15%",
                "sparse_infill_pattern": "gyroid",
                "outer_wall_speed": "50",
                "inner_wall_speed": "100",
                "small_perimeter_speed": "50%",
                "top_shell_layers": "6",
                "bottom_shell_layers": "5",
                "seam_position": "back",
                "fuzzy_skin": "none",
            }
        # Part ids must match component order / local mesh object ids.
        lines.extend(
            [
                f'  <object id="{top_id}">',
                f'    <metadata key="name" value="{escape(name)}"/>',
                f'    <metadata key="extruder" value="{extruder}"/>',
                *[
                    f'    <metadata key="{key}" value="{value}"/>'
                    for key, value in overrides.items()
                ],
                f'    <metadata face_count="{len(mesh.faces)}"/>',
                f'    <part id="{index}" subtype="normal_part">',
                f'      <metadata key="name" value="{escape(name)}"/>',
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'      <metadata key="source_file" value="{escape(source.name)}"/>',
                f'      <metadata key="source_object_id" value="{index - 1}"/>',
                f'      <metadata key="source_volume_id" value="{index - 1}"/>',
                f'      <metadata key="extruder" value="{extruder}"/>',
                f'      <mesh_stat face_count="{len(mesh.faces)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                "    </part>",
                "  </object>",
            ]
        )

    def plate(number: int, name: str, object_indices: list[int]) -> list[str]:
        result = [
            "  <plate>",
            f'    <metadata key="plater_id" value="{number}"/>',
            f'    <metadata key="plater_name" value="{escape(name)}"/>',
            '    <metadata key="locked" value="false"/>',
            '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
            f'    <metadata key="thumbnail_file" value="Metadata/plate_{number}.png"/>',
            f'    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_{number}.png"/>',
            f'    <metadata key="top_file" value="Metadata/top_{number}.png"/>',
            f'    <metadata key="pick_file" value="Metadata/pick_{number}.png"/>',
        ]
        for object_index in object_indices:
            result.extend(
                [
                    "    <model_instance>",
                    f'      <metadata key="object_id" value="{99 + object_index}"/>',
                    '      <metadata key="instance_id" value="0"/>',
                    f'      <metadata key="identify_id" value="{299 + object_index}"/>',
                    "    </model_instance>",
                ]
            )
        result.append("  </plate>")
        return result

    pet = OBJECTS[0][0].split()[0]

    def letters_plate(number: int, first_index: int) -> list[str]:
        """The letters plate, or nothing at all when letters are switched off.

        An empty plate is not the same as no plate: Studio opens a project whose
        last plate holds no instances and shows a blank bed the customer has to
        work out is intentional. Omitting it is what makes "no letters" read as
        a 3-plate job rather than a 4-plate job with one plate broken.
        """
        indices = list(range(first_index, len(OBJECTS) + 1))
        return plate(number, f"{pet} letters", indices) if indices else []

    # One plate per body, then the letters. Names are per style; the *count*
    # comes from BODY_COUNT, which is the only thing that distinguishes a
    # one-piece paw lattice from a three-part one.
    if wave_mode:
        names = ["Wave lower", "Wave upper shell — print inverted",
                 "Bowl-seat insert — print inverted"]
    elif hex_mode:
        names = ["Solid honeycomb body"]
    elif BODY_COUNT == 1:
        names = ["Stand — one piece, print upright"]
    else:
        names = ["Base", "Paw panel — print upright", "Top seat ring — print upright"]
    for index in range(BODY_COUNT):
        label = names[index] if index < len(names) else f"Part {index + 1}"
        lines.extend(plate(index + 1, label, [index + 1]))
    lines.extend(letters_plate(BODY_COUNT + 1, BODY_COUNT + 1))
    lines.append("  <assemble>")
    identity = (np.eye(3), np.zeros(3))
    for index, (_, source, _) in enumerate(OBJECTS, start=1):
        fitted = _assembly_transform(source)
        if fitted is None:
            log.debug("no assembly pose for %s — leaving it at the origin", source.name)
        rotation, translation = fitted or identity
        lines.append(
            f'    <assemble_item object_id="{99 + index}" instance_id="0" '
            f'transform="{_assemble_attrs(rotation, translation)}" offset="0 0 0"/>'
        )
    lines.extend(["  </assemble>", "</config>"])
    return ("\n".join(lines) + "\n").encode()


def relationships() -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for index in range(1, len(OBJECTS) + 1):
        lines.append(
            f' <Relationship Target="/3D/Objects/object_{index}.model" Id="rel-{index}" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        )
    lines.append("</Relationships>")
    return ("\n".join(lines) + "\n").encode()


def assert_object_id_hygiene(package: zipfile.ZipFile) -> None:
    """Loader requires object_N.model ↔ local id N, unique across the package."""
    seen: dict[str, str] = {}
    for name in package.namelist():
        if not (name.startswith("3D/Objects/object_") and name.endswith(".model")):
            continue
        expected = name.rsplit("_", 1)[1].removesuffix(".model")
        root = ET.fromstring(package.read(name))
        ids = [obj.get("id") for obj in root.iter(f"{{{CORE}}}object")]
        if ids != [expected]:
            raise ValueError(f"{name} must contain only local object id {expected}, got {ids}")
        for oid in ids:
            if oid in seen:
                raise ValueError(f"object id {oid} appears in both {seen[oid]} and {name}")
            seen[oid] = name


def build_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    name: str,
    stand_hex: str,
    letter_hex: str,
    stand_name: str = "Stand",
    letter_name: str = "Letters",
    work_dir: Path | None = None,
    template_path: Path | None = None,
    dims_root: Path | None = None,
    fuzzy_enabled: bool = True,
    include_letters: bool = True,
    one_piece: bool = False,
    painter: FuzzyPainter | None = None,
) -> Path:
    """Package meshes into a Bambu 3MF with Matte PLA filament colours.

    Four plates, or three when `include_letters` is False — see the note above
    `_letter_objects`.

    `painter` supplies the fuzzy-skin facet mask and its verification. It is
    required whenever fuzzy_enabled is True — this module deliberately knows
    nothing about paw silhouettes, so it cannot supply a default.
    """
    global OUTPUT, WORK, TEMPLATE
    mesh_dir = Path(mesh_dir)
    output_path = Path(output_path)
    work_dir = Path(work_dir or WORK)
    template_path = Path(template_path or TEMPLATE)
    dims_root = Path(dims_root or mesh_dir.parent)
    OUTPUT = output_path
    WORK = work_dir
    TEMPLATE = template_path

    configure_objects(
        mesh_dir, name.upper(), include_letters=include_letters, one_piece=one_piece
    )
    # The paw wall is its own object when the stand is three parts, and the
    # whole stand when it is one. Fuzzy skin is painted on whichever it is.
    paint_index = 0 if one_piece else 1

    meshes = []
    for _, path, _ in OBJECTS:
        # Same rule the wave and hex builders use: PLY carries exact vertices and
        # must not be re-welded, STL is triangle soup and needs it.
        process = path.suffix.lower() != ".ply"
        mesh = trimesh.load_mesh(path, process=process)
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold printable mesh: {path}")
        meshes.append(mesh)

    panel = meshes[paint_index]
    panel_paint = None
    if fuzzy_enabled:
        if painter is None:
            # Loud rather than silent: defaulting to "no paint" here would ship a
            # smooth panel that still looks correct in every geometric check.
            raise ValueError(
                "fuzzy_enabled=True requires a painter "
                "(pass paint_fuzzy_skin.COOPER_PAINTER for the Cooper panel)"
            )
        panel_paint = painter.mask(
            np.asarray(panel.vertices),
            np.asarray(panel.faces),
            dims_root,
        )

    with (
        zipfile.ZipFile(TEMPLATE) as template,
        zipfile.ZipFile(WORK / "cooper_base_plate.3mf") as base_preview,
        zipfile.ZipFile(WORK / "cooper_panel_plate.3mf") as panel_preview,
        zipfile.ZipFile(WORK / "cooper_top_ring_plate.3mf") as top_ring_preview,
        zipfile.ZipFile(WORK / "cooper_letters_plate.3mf") as letter_preview,
        zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", relationships())
        for index, mesh in enumerate(meshes, start=1):
            paint = panel_paint if index == paint_index + 1 else None
            output.writestr(
                f"3D/Objects/object_{index}.model",
                mesh_model(mesh, index, paint_fuzzy=paint),
            )
        # When fuzzy is off, force panel object to fuzzy_skin none without paint attrs.
        settings_bytes = model_settings(meshes)
        if not fuzzy_enabled:
            cfg = settings_bytes.decode()
            # Panel is object id 101; ensure fuzzy stays none (already default for paint mode).
            settings_bytes = cfg.encode()
        output.writestr("Metadata/model_settings.config", settings_bytes)

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["outer_wall_speed"][0] = "150"
        settings["inner_wall_speed"][0] = "250"
        settings["bridge_speed"][0] = "50"
        settings["overhang_1_4_speed"][0] = "50"
        settings["overhang_2_4_speed"][0] = "40"
        settings["overhang_3_4_speed"][0] = "30"
        settings["overhang_4_4_speed"][0] = "10"
        settings["small_perimeter_speed"][0] = "100%"
        settings["bottom_surface_pattern"] = "monotonic"
        settings["top_surface_pattern"] = "monotonicline"
        settings["reduce_crossing_wall"] = "0"
        settings["precise_outer_wall"] = "0"
        settings["no_slow_down_for_cooling_on_outwalls"] = ["0", "0"]
        settings["outer_wall_acceleration"] = ["5000", "5000"]
        settings["inner_wall_acceleration"] = ["0", "0"]
        settings["wall_sequence"] = "inner wall/outer wall"
        settings["seam_position"] = "back"
        settings["retraction_length"] = ["0.8", "0.8"]
        settings["filament_retraction_length"] = ["nil", "nil", "nil", "nil"]
        settings["retraction_speed"] = ["30", "30"]
        settings["filament_retraction_speed"] = ["nil", "nil", "nil", "nil"]
        settings["deretraction_speed"] = ["30", "30"]
        settings["filament_deretraction_speed"] = ["nil", "nil", "nil", "nil"]
        settings["retract_before_wipe"] = ["70%", "70%"]
        settings["filament_retract_before_wipe"] = ["nil", "nil", "nil", "nil"]
        settings["wipe_distance"] = ["2", "2"]
        settings["filament_wipe_distance"] = ["nil", "nil", "nil", "nil"]
        settings["reduce_infill_retraction"] = "1"
        settings["filament_flow_ratio"] = ["0.98", "0.98", "0.98", "0.98"]
        settings["nozzle_temperature"] = ["220", "220", "220", "220"]
        settings["nozzle_temperature_initial_layer"] = ["220", "220", "220", "220"]
        settings["fuzzy_skin"] = "none"
        settings["fuzzy_skin_thickness"] = "0.3"
        settings["fuzzy_skin_point_distance"] = "0.8"
        settings["fuzzy_skin_first_layer"] = "0"
        colours, filament_ids = _filament_slots(
            stand_hex=stand_hex,
            letter_hex=letter_hex,
            stand_name=stand_name,
            letter_name=letter_name,
            include_letters=include_letters,
        )
        _apply_filaments(settings, colours, filament_ids)
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))

        # One thumbnail per plate, in plate order — so the letters thumbnail is
        # dropped exactly when the letters plate is.
        # One thumbnail per plate, in plate order — so a one-piece stand gets the
        # panel's picture rather than three thumbnails for one plate.
        previews = (
            [panel_preview] if one_piece
            else [base_preview, panel_preview, top_ring_preview]
        )
        if include_letters:
            previews.append(letter_preview)
        for plate_number, preview in enumerate(previews, start=1):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )
            if "Metadata/plate_1_small.png" in preview.namelist():
                output.writestr(
                    f"Metadata/plate_{plate_number}_small.png",
                    preview.read("Metadata/plate_1_small.png"),
                )

    with zipfile.ZipFile(OUTPUT) as packaged:
        assert_object_id_hygiene(packaged)
        if fuzzy_enabled and panel_paint is not None:
            obj2 = packaged.read("3D/Objects/object_2.model").decode()
            cfg = packaged.read("Metadata/model_settings.config").decode()
            painter.verify(
                obj2,
                cfg,
                panel_paint,
                np.asarray(panel.vertices),
                np.asarray(panel.faces),
            )

    print(f"{OUTPUT}  (name={name}, stand={stand_hex}, letters={letter_hex})")
    return OUTPUT


def build_wave_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    name: str,
    stand_hex: str,
    letter_hex: str,
    stand_name: str = "Stand",
    letter_name: str = "Letters",
    work_dir: Path | None = None,
    template_path: Path | None = None,
    include_letters: bool = True,
    upper_hex: str | None = None,
    upper_name: str | None = None,
) -> Path:
    """Package wave lower/shell/seat insert (+ letters) into a 3- or 4-plate 3MF.

    `upper_hex` colours the upper shell and the seat insert, which print on
    extruder 3. Omitted, the whole body is one colour — the behaviour before the
    seam was made two-tone.
    """
    global OUTPUT, WORK, TEMPLATE
    mesh_dir = Path(mesh_dir)
    output_path = Path(output_path)
    work_dir = Path(work_dir or WORK)
    template_path = Path(template_path or TEMPLATE)
    OUTPUT = output_path
    WORK = work_dir
    TEMPLATE = template_path

    configure_wave_objects(mesh_dir, name.upper(), include_letters=include_letters)

    meshes = []
    for _, path, _ in OBJECTS:
        # Wave sector unions keep topology better without process=True.
        # Letters are simple extrusions and expect the usual cleanup.
        process = path.suffix.lower() != ".ply"
        mesh = trimesh.load_mesh(path, process=process)
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold printable mesh: {path}")
        meshes.append(mesh)

    with (
        zipfile.ZipFile(TEMPLATE) as template,
        zipfile.ZipFile(WORK / "cooper_base_plate.3mf") as base_preview,
        zipfile.ZipFile(WORK / "cooper_panel_plate.3mf") as panel_preview,
        zipfile.ZipFile(WORK / "cooper_top_ring_plate.3mf") as seat_preview,
        zipfile.ZipFile(WORK / "cooper_letters_plate.3mf") as letter_preview,
        zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr("Metadata/model_settings.config", model_settings(meshes))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        # Keep travel within printed regions where possible. A zero max detour
        # means unlimited detour length in Bambu Studio, not disabled detours.
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
        settings["fuzzy_skin"] = "none"
        colours, filament_ids = _filament_slots(
            stand_hex=stand_hex,
            letter_hex=letter_hex,
            stand_name=stand_name,
            letter_name=letter_name,
            include_letters=include_letters,
            upper_hex=upper_hex,
            upper_name=upper_name,
        )
        _apply_filaments(settings, colours, filament_ids)
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))

        previews = [base_preview, panel_preview, seat_preview]
        if include_letters:
            previews.append(letter_preview)
        for plate_number, preview in enumerate(previews, start=1):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )

    with zipfile.ZipFile(OUTPUT) as packaged:
        assert_object_id_hygiene(packaged)

    print(f"{OUTPUT}  (style=wave, name={name}, stand={stand_hex}, letters={letter_hex})")
    return OUTPUT


def build_hex_project(
    *,
    mesh_dir: Path,
    output_path: Path,
    name: str,
    stand_hex: str,
    letter_hex: str,
    stand_name: str = "Stand",
    letter_name: str = "Letters",
    work_dir: Path | None = None,
    template_path: Path | None = None,
    body_mesh: str = "honeycomb_body.ply",
    body_label: str = "honeycomb body",
    include_letters: bool = True,
) -> Path:
    """Package a single textured drum body (+ letters) into a 1- or 2-plate 3MF."""
    global OUTPUT, WORK, TEMPLATE
    mesh_dir = Path(mesh_dir)
    output_path = Path(output_path)
    work_dir = Path(work_dir or WORK)
    template_path = Path(template_path or TEMPLATE)
    OUTPUT = output_path
    WORK = work_dir
    TEMPLATE = template_path

    configure_hex_objects(
        mesh_dir,
        name.upper(),
        body_mesh=body_mesh,
        body_label=body_label,
        include_letters=include_letters,
    )

    meshes = []
    for _, path, _ in OBJECTS:
        process = path.suffix.lower() != ".ply"
        mesh = trimesh.load_mesh(path, process=process)
        if not mesh.is_watertight or not mesh.is_volume:
            raise ValueError(f"Non-manifold printable mesh: {path}")
        meshes.append(mesh)

    with (
        zipfile.ZipFile(TEMPLATE) as template,
        zipfile.ZipFile(WORK / "cooper_panel_plate.3mf") as body_preview,
        zipfile.ZipFile(WORK / "cooper_letters_plate.3mf") as letter_preview,
        zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", top_model())
        output.writestr("3D/_rels/3dmodel.model.rels", relationships())
        for index, mesh in enumerate(meshes, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                mesh_model(mesh, index, paint_fuzzy=None),
            )
        output.writestr("Metadata/model_settings.config", model_settings(meshes))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["wall_loops"] = "4"
        settings["sparse_infill_density"] = "15%"
        settings["sparse_infill_pattern"] = "gyroid"
        settings["enable_support"] = "0"
        settings["seam_position"] = "back"
        settings["fuzzy_skin"] = "none"
        colours, filament_ids = _filament_slots(
            stand_hex=stand_hex,
            letter_hex=letter_hex,
            stand_name=stand_name,
            letter_name=letter_name,
            include_letters=include_letters,
        )
        _apply_filaments(settings, colours, filament_ids)
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))

        previews = [body_preview]
        if include_letters:
            previews.append(letter_preview)
        for plate_number, preview in enumerate(previews, start=1):
            for stem in ("plate", "plate_no_light", "top", "pick"):
                output.writestr(
                    f"Metadata/{stem}_{plate_number}.png",
                    preview.read(f"Metadata/{stem}_1.png"),
                )

    with zipfile.ZipFile(OUTPUT) as packaged:
        assert_object_id_hygiene(packaged)

    print(
        f"{OUTPUT}  (style=hex-honeycomb, name={name}, "
        f"stand={stand_hex}, letters={letter_hex})"
    )
    return OUTPUT


def build():
    configure_objects(MESH_DIR, "COOPER")
    return build_project(
        mesh_dir=MESH_DIR,
        output_path=OUTPUT,
        name="COOPER",
        stand_hex="#AE835B",
        letter_hex="#FFFFFF",
        stand_name="Caramel",
        letter_name="Ivory White",
        work_dir=WORK,
        template_path=TEMPLATE,
        dims_root=OUT,
        fuzzy_enabled=True,
    )


if __name__ == "__main__":
    build()
