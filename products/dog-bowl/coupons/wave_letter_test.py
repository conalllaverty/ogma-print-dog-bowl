#!/usr/bin/env python3
"""Production-cone Wave lettering fit coupon.

Plate 1 is a cropped section of the real Wave upper, including its direct
glyph pockets. Plate 2 contains the matching cone-backed letters.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import trimesh

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
# Coupons are physical fit-test generators for this product — they import its
# design modules from the sibling generator/ dir.
for _p in (GENERATOR_DIR, GENERATOR_DIR.parent / "generator", _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import cooper_bowl_design as design  # noqa: E402
import wave_bowl_design as wave  # noqa: E402
from letter_test import build_letter_test_project  # noqa: E402
from ogma.filaments import (  # noqa: E402
    DEFAULT_LETTERS,
    DEFAULT_STAND,
    load_palette,
    resolve_filament,
)
from pipeline import FONT_STYLES  # noqa: E402


COUPON_MARGIN_X = 8.0
COUPON_MARGIN_Z = 4.0
COUPON_Y_MIN = -84.0
COUPON_Y_MAX = -66.0


def crop_wave_letter_coupon(
    upper: trimesh.Trimesh,
    letter_data: list[dict],
) -> tuple[trimesh.Trimesh, dict]:
    """Crop the production upper around its front lettering zone."""
    assembled_letters = [wave._wave_assembly_letter(item) for item in letter_data]
    letter_bounds = np.asarray(
        [
            [mesh.bounds[0] for mesh in assembled_letters],
            [mesh.bounds[1] for mesh in assembled_letters],
        ]
    )
    x0 = float(np.min(letter_bounds[:, :, 0])) - COUPON_MARGIN_X
    x1 = float(np.max(letter_bounds[:, :, 0])) + COUPON_MARGIN_X
    z0 = (
        design.LETTER_CENTER_Z
        - design.LETTER_HEIGHT * 0.5
        - COUPON_MARGIN_Z
    )
    z1 = (
        design.LETTER_CENTER_Z
        + design.LETTER_HEIGHT * 0.5
        + COUPON_MARGIN_Z
    )

    crop = trimesh.creation.box(
        extents=[x1 - x0, COUPON_Y_MAX - COUPON_Y_MIN, z1 - z0],
        transform=trimesh.transformations.translation_matrix(
            [
                0.5 * (x0 + x1),
                0.5 * (COUPON_Y_MIN + COUPON_Y_MAX),
                0.5 * (z0 + z1),
            ]
        ),
    )
    coupon = trimesh.boolean.intersection([upper, crop], engine="manifold")
    if coupon is None or coupon.is_empty:
        raise RuntimeError("Wave lettering crop produced an empty mesh")
    parts = [
        part
        for part in coupon.split(only_watertight=False)
        if part.is_watertight and part.is_volume
    ]
    if not parts:
        raise RuntimeError("Wave lettering crop produced no watertight volume")
    coupon = max(parts, key=lambda part: abs(float(part.volume))).copy()
    coupon.remove_unreferenced_vertices()

    centre_xy = 0.5 * (coupon.bounds[0, :2] + coupon.bounds[1, :2])
    coupon.apply_translation(
        [-centre_xy[0], -centre_xy[1], -float(coupon.bounds[0, 2])]
    )
    coupon.metadata["name"] = "Wave_Production_Cone_Letter_Coupon"
    if not coupon.is_watertight or not coupon.is_volume:
        raise RuntimeError("Wave lettering coupon is not a watertight volume")

    return coupon, {
        "source_z_range": [z0, z1],
        "source_x_range": [x0, x1],
        "source_y_range": [COUPON_Y_MIN, COUPON_Y_MAX],
        "bounds": coupon.bounds.round(3).tolist(),
    }


def generate_wave_letter_test(
    name: str,
    job_dir: Path,
    *,
    font_style: str = "serif",
    stand_filament_id: str = DEFAULT_STAND,
    letter_filament_id: str = DEFAULT_LETTERS,
) -> Path:
    """Generate a two-plate production Wave lettering fit test."""
    job_dir = Path(job_dir)
    mesh_dir = job_dir / "meshes"
    if mesh_dir.exists():
        shutil.rmtree(mesh_dir)
    mesh_dir.mkdir(parents=True)

    palette = load_palette()
    stand = resolve_filament(stand_filament_id, palette)
    letter_filament = resolve_filament(letter_filament_id, palette)

    design.configure_output(job_dir, name=name, font_style=font_style)
    wave._configure_wave_letters()
    letters = design.build_letters()
    for item in letters:
        item["mesh"] = wave._wave_letter_mesh(
            item["polygon"],
            item["arc_center"],
        )

    upper = wave.build_wave_upper(letters)
    coupon, crop_report = crop_wave_letter_coupon(upper, letters)
    coupon_filename = "wave_letter_coupon.stl"
    coupon.export(mesh_dir / coupon_filename)
    for index, item in enumerate(letters, start=1):
        item["mesh"].export(
            mesh_dir / f"letter_{index}_{item['character']}.stl"
        )

    report = {
        "test": "Wave production-cone lettering",
        "name": design.NAME,
        "font_style": font_style,
        "coupon": crop_report,
        "letters": {
            "height": design.LETTER_HEIGHT,
            "proud_thickness": design.LETTER_PROUD,
            "pocket_depth": design.LETTER_POCKET_DEPTH,
            "pocket_outline_clearance": design.LETTER_POCKET_CLEARANCE,
            "pocket_floor_gap": design.LETTER_POCKET_FLOOR_GAP,
            "back_surface": "production Wave cone",
        },
        "acceptance": (
            "Each letter starts by hand, seats to the pocket floor without "
            "rocking, remains approximately 1.4 mm proud, and can be removed "
            "before gluing."
        ),
    }
    report_path = job_dir / "dimensions_and_acceptance.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    output = job_dir / f"{design.NAME}_Wave_Letter_Fit_Test_P2S.3mf"
    build_letter_test_project(
        mesh_dir=mesh_dir,
        output_path=output,
        name=design.NAME,
        stand_hex=stand.hex,
        letter_hex=letter_filament.hex,
        stand_name=stand.name,
        letter_name=letter_filament.name,
        coupon_filename=coupon_filename,
        coupon_label="Wave cone lettering coupon",
    )
    (job_dir / "job.json").write_text(
        json.dumps(
            {
                "name": design.NAME,
                "font_style": font_style,
                "stand_filament_id": stand.id,
                "letter_filament_id": letter_filament.id,
                "threemf": output.name,
                "kind": "wave_letter_test",
            },
            indent=2,
        )
        + "\n", encoding="utf-8"
    )
    print(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Wave production-cone lettering fit test"
    )
    parser.add_argument("--name", default="LUNA")
    parser.add_argument("--font-style", default="serif", choices=FONT_STYLES)
    parser.add_argument("--stand", default=DEFAULT_STAND)
    parser.add_argument("--letters", default=DEFAULT_LETTERS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    generate_wave_letter_test(
        args.name,
        args.out,
        font_style=args.font_style,
        stand_filament_id=args.stand,
        letter_filament_id=args.letters,
    )
