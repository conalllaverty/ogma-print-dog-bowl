#!/usr/bin/env python3
"""Assembled preview of the Bouclé Stack table lamp.

This is a *visualisation*, not a print layout: every part sits where it lands
in the finished lamp, so the shells float 4 mm apart on their halo rings and
nothing here would print as arranged. Use `boucle_lamp_shade.py` for the
bed-ready shade/diffuser projects and `boucle_lamp_coupons.py` only for tests.

Geometry comes from `boucle_lamp_config`; shells and both joint architectures
come from `boucle_lamp_shade`, so the preview cannot drift from production.

Run from the repository root:

    .venv/bin/python backend/generator/boucle_lamp_assembly.py --out design/boucle-stack-lamp/assembly
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import trimesh

GENERATOR_DIR = Path(__file__).resolve().parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import boucle_lamp_config as cfg  # noqa: E402
import boucle_lamp_coupons as coupons  # noqa: E402
import boucle_lamp_shade as shade  # noqa: E402
import build_bambu_project as bambu  # noqa: E402
from pipeline import load_palette, resolve_filament  # noqa: E402

# Preview resolution. The printed parts use 288 sections and the full profile.
# This is picked to keep the exported files a sane size — going finer is not
# visible at the render sizes below, and these meshes are not for printing.
SECTIONS = 132
PROFILE_STRIDE = 6

SHELL_COLOUR = [214, 206, 190, 255]
DIFFUSER_COLOUR = [247, 247, 242, 255]
BASE_COLOUR = [77, 51, 36, 255]
RING_COLOUR = [198, 190, 174, 255]
LED_COLOUR = [120, 124, 130, 255]


@dataclass
class Piece:
    label: str
    mesh: trimesh.Trimesh
    colour: list
    extruder: int
    printed: bool = True
    # How much light the part passes, for the preview renderer only. Bone White
    # at the 1.6 mm shell wall glows; the 3 mm ring web much less; the base not
    # at all.
    transmit: float = 0.0


# --------------------------------------------------------------------------
# Placement
# --------------------------------------------------------------------------


def world_transform(shell: cfg.Shell) -> np.ndarray:
    """Where a shell's printed frame lands in the assembled lamp."""
    matrix = trimesh.transformations.rotation_matrix(
        math.radians(shell.axis_deg), [0.0, 1.0, 0.0]
    )
    matrix[0, 3] = shell.origin[0]
    matrix[2, 3] = shell.origin[1]
    return matrix


def tube(r0: float, r1: float, length: float, sections: int = 48) -> trimesh.Trimesh:
    """A truncated cone along +z, `r0` at the base."""
    profile = np.asarray(
        [(0.0, 0.0), (r0, 0.0), (r1, length), (0.0, length), (0.0, 0.0)]
    )
    return trimesh.creation.revolve(profile, sections=sections)


def annulus(
    r_inner: float, r_outer: float, height: float, z0: float = 0.0, sections: int = SECTIONS
) -> trimesh.Trimesh:
    profile = np.asarray(
        [
            (r_inner, z0),
            (r_outer, z0),
            (r_outer, z0 + height),
            (r_inner, z0 + height),
            (r_inner, z0),
        ]
    )
    return trimesh.creation.revolve(profile, sections=sections)


# --------------------------------------------------------------------------
# Parts that only exist in the assembly
# --------------------------------------------------------------------------


def build_base() -> trimesh.Trimesh:
    """Plinth ring plus three splayed legs with embedded, bore-safe joints."""
    base, _report = coupons.build_leg_frame()
    return base


def build_cradle() -> trimesh.Trimesh:
    mesh, _report = coupons.build_cradle_coupon()
    mesh.apply_translation([0.0, 0.0, cfg.CRADLE_Z0])
    return mesh


def build_led_module() -> trimesh.Trimesh:
    """Stand-in for the Bambu kit, so the interior reads in a cutaway."""
    mesh = tube(cfg.LED_DIA / 2.0, cfg.LED_DIA / 2.0, cfg.LED_HEIGHT, sections=96)
    mesh.apply_translation([0.0, 0.0, cfg.CRADLE_Z1 - cfg.LED_POCKET_DEPTH + 0.5])
    return mesh


def build_baffle() -> trimesh.Trimesh:
    """Flip the support-free print part into its installed orientation."""
    mesh, _report = coupons.build_baffle()
    mesh.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0])
    )
    mesh.apply_translation(
        [0.0, 0.0, cfg.CRADLE_Z1 + cfg.BAFFLE_POST_H + cfg.BAFFLE_WALL]
    )
    return mesh


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def build_assembly(
    sections: int = SECTIONS,
    profile_stride: int = PROFILE_STRIDE,
    ring_steps: int = 70,
    include_led_reference: bool = True,
) -> tuple[list[Piece], dict]:
    shells = cfg.build_stack()
    leg_phases = [
        (
            cfg.LEG_PHASE_DEG
            + 360.0 * index / cfg.LEG_COUNT
        )
        % 360.0
        for index in range(cfg.LEG_COUNT)
    ]
    front_leg_phases = [leg_phases[1], leg_phases[2]]
    intended_cable_phase = (
        leg_phases[0] + cfg.CABLE_REAR_LEG_OFFSET_DEG
    ) % 360.0
    cable_phase_error = (
        (cfg.CABLE_PHASE_DEG - intended_cable_phase + 180.0) % 360.0
    ) - 180.0
    if abs(cable_phase_error) > 1e-6:
        raise RuntimeError(
            "cable slot is not aligned beside the rear leg"
        )
    base = build_base()
    cradle = build_cradle()
    baffle = build_baffle()
    base_cradle_overlap = trimesh.boolean.intersection(
        [base, cradle], engine="manifold"
    )
    if len(base_cradle_overlap.faces):
        triangles = base_cradle_overlap.triangles
        base_cradle_overlap_mm3 = abs(
            float(
                np.einsum(
                    "ij,ij->i",
                    triangles[:, 0],
                    np.cross(triangles[:, 1], triangles[:, 2]),
                ).sum()
                / 6.0
            )
        )
        overlap_z_span = float(
            np.ptp(base_cradle_overlap.bounds[:, 2])
        )
    else:
        base_cradle_overlap_mm3 = 0.0
        overlap_z_span = 0.0
    if (
        base_cradle_overlap_mm3 > 0.01
        and not (
            overlap_z_span < 0.05
            and base_cradle_overlap_mm3 < 10.0
        )
    ):
        raise RuntimeError(
            "embedded legs intrude into the removable LED cradle: "
            f"{base_cradle_overlap_mm3:.3f} mm³"
        )
    baffle_cradle_overlap = trimesh.boolean.intersection(
        [baffle, cradle], engine="manifold"
    )
    if len(baffle_cradle_overlap.faces):
        triangles = baffle_cradle_overlap.triangles
        baffle_cradle_overlap_mm3 = abs(
            float(
                np.einsum(
                    "ij,ij->i",
                    triangles[:, 0],
                    np.cross(triangles[:, 1], triangles[:, 2]),
                ).sum()
                / 6.0
            )
        )
    else:
        baffle_cradle_overlap_mm3 = 0.0
    if baffle_cradle_overlap_mm3 > 0.01:
        raise RuntimeError(
            "diffuser locator pegs interfere with their cradle sockets: "
            f"{baffle_cradle_overlap_mm3:.3f} mm³"
        )
    pieces: list[Piece] = [
        Piece("Leg frame", base, BASE_COLOUR, 2),
        Piece("LED cradle", cradle, BASE_COLOUR, 2),
        Piece(
            "Diffuser baffle",
            baffle,
            DIFFUSER_COLOUR,
            1,
            transmit=0.8,
        ),
    ]

    for index, shell in enumerate(shells):
        mesh = shade.production_shell(
            shell,
            add_register=index > 0,
            sections=sections,
            stride=profile_stride,
            wall_thickness=shade.shell_wall_thickness(shell),
        )
        mesh.apply_transform(world_transform(shell))
        pieces.append(
            Piece(
                f"Shell {shell.key[-1].upper()}",
                mesh,
                SHELL_COLOUR,
                1,
                transmit=0.72 if shell.key == "shell_c" else 0.62,
            )
        )

        if index + 1 < len(shells):
            upper = shells[index + 1]
            if index == 1:
                ring, _report = shade.compact_bc_ring(
                    shell,
                    upper,
                    sections=sections,
                    steps=ring_steps,
                )
            else:
                ring, _report = shade.open_ab_ring(
                    shell,
                    upper,
                    sections=sections,
                    steps=ring_steps,
                )
            ring.apply_transform(world_transform(upper))
            pieces.append(
                Piece(
                    f"Halo ring {shell.key[-1].upper()}–{upper.key[-1].upper()}",
                    ring, RING_COLOUR, 1, transmit=0.28,
                )
            )

    if include_led_reference:
        pieces.append(
            Piece(
                "LED module (reference)",
                build_led_module(),
                LED_COLOUR,
                2,
                printed=False,
            )
        )

    combined = trimesh.util.concatenate([p.mesh for p in pieces])
    low, high = combined.bounds
    report = {
        "model": "Bouclé Stack table lamp — assembled preview",
        "units": "mm",
        "note": "Preview only: parts sit where they land in the finished lamp.",
        "mesh_resolution": {
            "circumferential_sections": sections,
            "shell_profile_stride": profile_stride,
            "ring_envelope_steps": ring_steps,
        },
        "overall_height": round(float(high[2] - low[2]), 2),
        "widest_diameter": round(float(max(high[0] - low[0], high[1] - low[1])), 2),
        "joint_clocking": {
            "A_to_B": coupons.joint_clocking_report(
                shells[1]
            ),
            "B_to_C": coupons.joint_clocking_report(
                shells[2]
            ),
            "role": (
                "One hidden tapered ring tab enters the upper "
                "shell's open-bottom register notch; adhesive "
                "remains structural."
            ),
        },
        "base_validation": {
            "connected_components": len(base.split(only_watertight=False)),
            "leg_joint": "embedded through outer contact and clipped clear of bore",
            "leg_embed_endpoint": [
                cfg.LEG_EMBED_R,
                cfg.LEG_EMBED_Z,
            ],
            "base_cradle_collision_volume_mm3": round(
                base_cradle_overlap_mm3, 6
            ),
            "diffuser_cradle_collision_volume_mm3": round(
                baffle_cradle_overlap_mm3, 6
            ),
            "diffuser_locator_clearance_total_mm": round(
                cfg.BAFFLE_SOCKET_DIA
                - cfg.BAFFLE_LOCATOR_DIA,
                2,
            ),
            "diffuser_locator_bottom_clearance_mm": round(
                cfg.BAFFLE_SOCKET_DEPTH
                - cfg.BAFFLE_LOCATOR_H,
                2,
            ),
            "leg_phases_deg": leg_phases,
            "front_leg_phases_deg": front_leg_phases,
            "cable_phase_deg": cfg.CABLE_PHASE_DEG,
            "rear_leg_phase_deg": leg_phases[0],
            "cable_to_rear_leg_deg": (
                cfg.CABLE_REAR_LEG_OFFSET_DEG
            ),
            "front_open_midpoint_deg": (
                cfg.LEG_PHASE_DEG + 180.0
            ) % 360.0,
            "passed": True,
        },
        "parts": [
            {
                "name": piece.label,
                "printed": piece.printed,
                "filament": (
                    "Jade White"
                    if piece.label == "Diffuser baffle"
                    else "Bone White"
                    if piece.extruder == 1
                    else "Dark Chocolate"
                ),
                "volume_cm3": round(float(piece.mesh.volume) / 1000.0, 1),
            }
            for piece in pieces
        ],
    }
    return pieces, report


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def write_scene(pieces: list[Piece], out_dir: Path) -> dict[str, Path]:
    scene = trimesh.Scene()
    for piece in pieces:
        mesh = piece.mesh.copy()
        mesh.visual = trimesh.visual.ColorVisuals(
            mesh, face_colors=np.tile(piece.colour, (len(mesh.faces), 1))
        )
        scene.add_geometry(mesh, node_name=piece.label, geom_name=piece.label)

    glb = out_dir / "boucle_stack_lamp_assembly.glb"
    glb.write_bytes(scene.export(file_type="glb"))

    stl = out_dir / "boucle_stack_lamp_assembly.stl"
    trimesh.util.concatenate([p.mesh for p in pieces if p.printed]).export(stl)
    return {"glb": glb, "stl": stl}


def _model_settings(pieces: list[Piece]) -> bytes:
    """Describe one multipart object, not several independently movable ones.

    Bambu Studio automatically drops each top-level object to the plate. The
    assembly meshes already contain their finished world Z positions, so making
    every piece top-level collapses the lamp into a pile. Keeping all parts
    under object 100 preserves their relative positions while retaining
    per-volume names and extruders.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<config>",
        '  <object id="100">',
        '    <metadata key="name" value="Bouclé Stack lamp — assembled preview"/>',
        '    <metadata key="extruder" value="1"/>',
        f'    <metadata face_count="{sum(len(piece.mesh.faces) for piece in pieces)}"/>',
    ]
    for index, piece in enumerate(pieces, start=1):
        lines.extend(
            [
                f'    <part id="{index}" subtype="normal_part">',
                f'      <metadata key="name" value="{escape(piece.label)}"/>',
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'      <metadata key="source_object_id" value="{index - 1}"/>',
                f'      <metadata key="source_volume_id" value="{index - 1}"/>',
                f'      <metadata key="extruder" value="{piece.extruder}"/>',
                f'      <mesh_stat face_count="{len(piece.mesh.faces)}" edges_fixed="0" '
                'degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
                "    </part>",
            ]
        )
    lines.append("  </object>")

    lines.extend(
        [
            "  <plate>",
            '    <metadata key="plater_id" value="1"/>',
            '    <metadata key="plater_name" value="Assembled preview — not a print layout"/>',
            '    <metadata key="locked" value="false"/>',
            '    <metadata key="filament_map_mode" value="Auto For Flush"/>',
            '    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>',
            '    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>',
            '    <metadata key="top_file" value="Metadata/top_1.png"/>',
            '    <metadata key="pick_file" value="Metadata/pick_1.png"/>',
            "    <model_instance>",
            '      <metadata key="object_id" value="100"/>',
            '      <metadata key="instance_id" value="0"/>',
            '      <metadata key="identify_id" value="300"/>',
            "    </model_instance>",
            "  </plate>",
            "  <assemble>",
            '    <assemble_item object_id="100" instance_id="0" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0" offset="0 0 0"/>',
            "  </assemble>",
            "</config>",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def _top_model(
    piece_count: int,
    title: str = "Bouclé Stack lamp — assembled preview",
    build_offset: tuple[float, float, float] = (128.0, 128.0, 0.0),
) -> bytes:
    """Top-level 3MF model containing one multipart assembly."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{bambu.CORE}" '
        f'xmlns:BambuStudio="{bambu.BAMBU}" xmlns:p="{bambu.PROD}" requiredextensions="p">',
        ' <metadata name="Application">BambuStudio-02.07.01.62</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        f' <metadata name="Title">{escape(title)}</metadata>',
        " <resources>",
        f'  <object id="100" p:UUID="{bambu.object_uuid(100, 0xABCDEF123456)}" type="model">',
        "   <components>",
    ]
    for index in range(1, piece_count + 1):
        lines.append(
            f'    <component p:path="/3D/Objects/object_{index}.model" objectid="{index}" '
            f'p:UUID="{bambu.object_uuid(0x1000 + index, 0xABCDEF123456)}" '
            'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        )
    lines.extend(
        [
            "   </components>",
            "  </object>",
            " </resources>",
            f' <build p:UUID="{bambu.object_uuid(9999, 0xABCDEF123456)}">',
            f'  <item objectid="100" p:UUID="{bambu.object_uuid(5001, 0xABCDEF123456)}" '
            f'transform="1 0 0 0 1 0 0 0 1 '
            f'{build_offset[0]:.3f} {build_offset[1]:.3f} '
            f'{build_offset[2]:.3f}" printable="0"/>',
            " </build>",
            "</model>",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def write_project(
    pieces: list[Piece],
    out_dir: Path,
    shell_hex: str,
    base_hex: str,
    output_name: str = "Boucle_Stack_Lamp_Assembly.3mf",
    title: str = "Bouclé Stack lamp — assembled preview",
    include_reference: bool = False,
    build_offset: tuple[float, float, float] = (128.0, 128.0, 0.0),
) -> Path:
    """A 3MF that opens in Bambu Studio purely so the lamp can be orbited."""
    selected = pieces if include_reference else [p for p in pieces if p.printed]
    # The shared utility uses OBJECTS to enumerate relationships to child
    # model files. They are components of one object here, not build items.
    bambu.OBJECTS = [(p.label, Path(p.label), p.extruder) for p in selected]
    output_path = out_dir / output_name
    template_path = GENERATOR_DIR / "blank_project.3mf"
    preview_path = GENERATOR_DIR / "bambu_work" / "cooper_base_plate.3mf"
    with (
        zipfile.ZipFile(template_path) as template,
        zipfile.ZipFile(preview_path) as preview,
        zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr(
            "3D/3dmodel.model",
            _top_model(
                len(selected),
                title=title,
                build_offset=build_offset,
            ),
        )
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, piece in enumerate(selected, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model", bambu.mesh_model(piece.mesh, index)
            )
        output.writestr("Metadata/model_settings.config", _model_settings(selected))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        settings["filament_colour"] = [shell_hex, base_hex]
        settings["default_filament_colour"] = ["", ""]
        settings["filament_settings_id"] = ["Bambu PLA Matte @BBL P2S"] * 2
        settings["enable_prime_tower"] = "0"
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            output.writestr(filename, template.read(filename))
        thumbnail_sources = {
            "plate": out_dir / "preview_three_quarter.png",
            "plate_no_light": out_dir / "preview_three_quarter.png",
            "top": out_dir / "preview_elevation.png",
            "pick": out_dir / "preview_three_quarter.png",
        }
        for stem, source in thumbnail_sources.items():
            image = (
                source.read_bytes()
                if source.exists()
                else preview.read(f"Metadata/{stem}_1.png")
            )
            output.writestr(f"Metadata/{stem}_1.png", image)

    with zipfile.ZipFile(output_path) as package:
        bambu.assert_object_id_hygiene(package)
    return output_path


def generate_assembly(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pieces, report = build_assembly()
    written = write_scene(pieces, out_dir)

    palette = load_palette()
    written["3mf"] = write_project(
        pieces,
        out_dir,
        resolve_filament(coupons.SHELL_FILAMENT, palette).hex,
        resolve_filament(coupons.BASE_FILAMENT, palette).hex,
    )

    (out_dir / "assembly.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assembled preview of the Bouclé Stack lamp")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for kind, path in generate_assembly(args.out).items():
        print(f"{kind:4} {path}")
