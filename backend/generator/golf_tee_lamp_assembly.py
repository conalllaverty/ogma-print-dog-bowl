#!/usr/bin/env python3
"""Assembled preview of the Golf Tee LED lamp.

Visualisation only — parts sit in finished positions as one multipart object.
Bambu Studio will orbit the whole lamp; this is not a print layout. Use
golf_tee_lamp.py for the bed-ready five-plate P2S project.

Run from the repository root:

    .venv/bin/python backend/generator/golf_tee_lamp_assembly.py \\
        --out design/golf-tee-lamp/assembly
"""

from __future__ import annotations

import argparse
import json
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

import build_bambu_project as bambu  # noqa: E402
import golf_tee_lamp as production  # noqa: E402
import golf_tee_lamp_config as cfg  # noqa: E402
import golf_tee_lamp_geometry as geo  # noqa: E402
from pipeline import load_palette, resolve_filament  # noqa: E402

BALL_COLOUR = [255, 255, 255, 220]
TEE_COLOUR = [174, 131, 91, 255]
GRASS_COLOUR = [97, 198, 128, 255]
REFLECTOR_COLOUR = [245, 245, 240, 255]
COVER_COLOUR = [72, 150, 96, 255]
LED_COLOUR = [120, 124, 130, 255]
MATTE_PROFILE = production.MATTE_PROFILE


@dataclass
class Piece:
    label: str
    mesh: trimesh.Trimesh
    colour: list
    extruder: int
    printed: bool = True
    transmit: float = 0.0


def build_led_module() -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(
        radius=cfg.LED_DIA / 2.0,
        height=cfg.LED_HEIGHT,
        sections=96,
    )
    # Seated on the reflector floor inside the tee cup pocket.
    mesh.apply_translation(
        [
            0.0,
            0.0,
            cfg.TEE_CUP_WORLD_Z1
            - cfg.LED_POCKET_DEPTH
            + cfg.REFLECTOR_FLOOR
            + cfg.LED_HEIGHT / 2.0,
        ]
    )
    return mesh


def build_assembly(include_dimples: bool = True) -> tuple[list[Piece], dict]:
    ball, ball_report = geo.build_ball_assembled(include_dimples=include_dimples)
    ball.apply_translation([0.0, 0.0, cfg.BALL_ORIGIN_Z])
    ball = geo._serialization_safe(ball, "Golf_Ball_Assembled")

    grass, grass_report = geo.build_grass_base()

    tee, tee_report = geo.build_tee_assembled()
    tee.apply_translation([0.0, 0.0, cfg.TEE_ASSEMBLED_Z0])

    reflector, reflector_report = geo.build_reflector_cup()
    reflector.apply_translation(
        [
            0.0,
            0.0,
            cfg.TEE_CUP_WORLD_Z1 - cfg.LED_POCKET_DEPTH,
        ]
    )

    cover, cover_report = geo.build_ballast_cover()
    # Cover sits on the underside ledge (assembled frame, underside at z=0).
    cover.apply_translation([0.0, 0.0, 0.0])

    led = build_led_module()

    pieces = [
        Piece("Grass base", grass, GRASS_COLOUR, 3, transmit=0.0),
        Piece("Ballast cover", cover, COVER_COLOUR, 3, transmit=0.0),
        Piece("Golf tee", tee, TEE_COLOUR, 2, transmit=0.0),
        Piece("LED reflector cup", reflector, REFLECTOR_COLOUR, 4, transmit=0.0),
        Piece("LED module (reference)", led, LED_COLOUR, 2, printed=False, transmit=0.0),
        Piece("Golf ball shade", ball, BALL_COLOUR, 1, transmit=0.35),
    ]
    report = {
        "product": "Golf Tee LED lamp",
        "summary": cfg.summary(),
        "ball": ball_report,
        "tee": {
            k: tee_report[k]
            for k in (
                "height",
                "foot_od",
                "snap_bead_od",
                "seat_od",
                "cable_phase_deg",
                "hollow_cable_bore_dia",
                "led_pocket",
                "bayonet",
            )
            if k in tee_report
        },
        "grass_base": {
            k: grass_report[k]
            for k in (
                "shape",
                "side",
                "corner_radius",
                "height",
                "snap",
                "cable_exit",
                "ballast",
                "felt_pad",
                "fuzzy_turf",
            )
            if k in grass_report
        },
        "ballast_cover": cover_report,
        "reflector": reflector_report,
        "parts": [piece.label for piece in pieces],
        "overall_bounds_mm": _bounds(pieces),
    }
    return pieces, report


def _bounds(pieces: list[Piece]) -> list[list[float]]:
    low = np.min([piece.mesh.bounds[0] for piece in pieces], axis=0)
    high = np.max([piece.mesh.bounds[1] for piece in pieces], axis=0)
    return [
        [round(float(v), 2) for v in low],
        [round(float(v), 2) for v in high],
    ]


def _model_settings(pieces: list[Piece]) -> bytes:
    """Keep every part under object 100 so relative world Z is preserved."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<config>",
        '  <object id="100">',
        '    <metadata key="name" value="Golf Tee lamp — assembled preview"/>',
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
    lines.extend(
        [
            "  </object>",
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
    title: str = "Golf Tee LED lamp — assembled preview",
    build_offset: tuple[float, float, float] = (128.0, 128.0, 0.0),
) -> bytes:
    """One multipart assembly object — Studio must not drop parts to the bed."""
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


def write_assembly_3mf(
    pieces: list[Piece],
    out_path: Path,
    *,
    include_reference: bool = True,
) -> Path:
    """A 3MF that opens in Bambu Studio so the finished lamp can be orbited."""
    selected = pieces if include_reference else [piece for piece in pieces if piece.printed]
    bambu.OBJECTS = [(piece.label, Path(piece.label), piece.extruder) for piece in selected]
    bambu.BUILD_POSITIONS = [(0.0, 0.0, 0.0)] * len(selected)

    palette = load_palette()
    caramel = resolve_filament(cfg.TEE_FILAMENT_ID, palette)
    grass = resolve_filament(cfg.BASE_FILAMENT_ID, palette)
    filament_slots = [
        (cfg.BALL_FILAMENT_HEX, cfg.BALL_FILAMENT_PROFILE),
        (caramel.hex, MATTE_PROFILE),
        (grass.hex, MATTE_PROFILE),
    ]

    template_path = GENERATOR_DIR / "blank_project.3mf"
    preview_path = GENERATOR_DIR / "bambu_work" / "cooper_base_plate.3mf"
    with (
        zipfile.ZipFile(template_path) as template,
        zipfile.ZipFile(preview_path) as preview,
        zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=7) as output,
    ):
        output.writestr("[Content_Types].xml", template.read("[Content_Types].xml"))
        output.writestr("_rels/.rels", template.read("_rels/.rels"))
        output.writestr("3D/3dmodel.model", _top_model(len(selected)))
        output.writestr("3D/_rels/3dmodel.model.rels", bambu.relationships())
        for index, piece in enumerate(selected, start=1):
            output.writestr(
                f"3D/Objects/object_{index}.model",
                bambu.mesh_model(piece.mesh, index, paint_fuzzy=None),
            )
        output.writestr("Metadata/model_settings.config", _model_settings(selected))

        settings = json.loads(template.read("Metadata/project_settings.config"))
        production.configure_filament_slots(settings, filament_slots)
        settings["filament_colour"] = [colour for colour, _ in filament_slots]
        settings["filament_settings_id"] = [profile for _, profile in filament_slots]
        settings["enable_prime_tower"] = "0"
        output.writestr(
            "Metadata/project_settings.config",
            json.dumps(settings, indent=4, ensure_ascii=False).encode(),
        )
        for filename in ("Metadata/slice_info.config", "Metadata/filament_sequence.json"):
            if filename in template.namelist():
                output.writestr(filename, template.read(filename))
        for stem in ("plate", "plate_no_light", "top", "pick"):
            output.writestr(f"Metadata/{stem}_1.png", preview.read(f"Metadata/{stem}_1.png"))

    with zipfile.ZipFile(out_path) as package:
        bambu.assert_object_id_hygiene(package)
    return out_path


def generate(out_dir: Path, include_dimples: bool = True) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pieces, report = build_assembly(include_dimples=include_dimples)

    mesh_dir = out_dir / "meshes"
    mesh_dir.mkdir(exist_ok=True)
    for stale in mesh_dir.glob("*.stl"):
        stale.unlink()

    scene_meshes = []
    for index, piece in enumerate(pieces, start=1):
        stem = piece.label.lower().replace(" ", "_").replace("(", "").replace(")", "")
        path = mesh_dir / f"{index:02d}_{stem}.stl"
        piece.mesh.export(path)
        coloured = piece.mesh.copy()
        coloured.visual.vertex_colors = piece.colour
        scene_meshes.append(coloured)

    scene = trimesh.Scene(scene_meshes)
    scene.export(out_dir / "golf_tee_lamp_assembly.glb")
    combined = trimesh.util.concatenate([piece.mesh for piece in pieces])
    combined.export(out_dir / "golf_tee_lamp_assembly.stl")

    assembly_3mf = write_assembly_3mf(pieces, out_dir / "Golf_Tee_Lamp_Assembly.3mf")
    report["outputs"] = {
        "3mf": str(assembly_3mf.relative_to(out_dir)),
        "glb": "golf_tee_lamp_assembly.glb",
        "stl": "golf_tee_lamp_assembly.stl",
    }
    (out_dir / "assembly.json").write_text(json.dumps(report, indent=2) + "\n")
    return assembly_3mf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("design/golf-tee-lamp/assembly"),
    )
    parser.add_argument("--no-dimples", action="store_true")
    args = parser.parse_args()
    path = generate(args.out, include_dimples=not args.no_dimples)
    print(f"3mf {path}")


if __name__ == "__main__":
    main()
