#!/usr/bin/env python3
"""Job pipeline: name + Matte colours → meshes + Bambu 3MF (local or Railway)."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parent
BACKEND_DIR = GENERATOR_DIR.parent
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

import cooper_bowl_design as design  # noqa: E402
import styles  # noqa: E402
from ogma.filaments import (  # noqa: E402
    DEFAULT_LETTERS,
    DEFAULT_STAND,
    PALETTE_PATH,
    Filament,
    load_palette,
    resolve_filament,
)


FONT_STYLES = (
    "bold",
    "clean",
    "serif",
    "slab",
    "rounded",
    "playful",
    "condensed",
)
DEFAULT_STYLE = styles.DEFAULT_STYLE


@dataclass
class GenerateResult:
    name: str
    font_style: str
    style: str
    stand: Filament
    letters: Filament
    job_dir: Path
    threemf_path: Path
    dimensions_path: Path
    rail_outer_deg: float


def generate(
    name: str,
    job_dir: Path,
    *,
    style: str = DEFAULT_STYLE,
    font_style: str = "bold",
    stand_filament_id: str = DEFAULT_STAND,
    letter_filament_id: str = DEFAULT_LETTERS,
    fuzzy_enabled: bool = True,
) -> GenerateResult:
    """Generate printable meshes and a Bambu 3MF into job_dir."""
    bowl_style = styles.get(style)
    style = bowl_style.id
    if not bowl_style.generator_available:
        raise ValueError(
            f"Style '{style}' is not available yet ({bowl_style.description})."
        )

    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    meshes = job_dir / "meshes"
    if meshes.exists():
        shutil.rmtree(meshes)

    palette = load_palette()
    stand = resolve_filament(stand_filament_id, palette)
    letters = resolve_filament(letter_filament_id, palette)

    work = GENERATOR_DIR / "bambu_work"

    rail_outer = bowl_style.generate_meshes(job_dir, name, font_style)
    cleaned = design.NAME
    output = job_dir / f"{cleaned}_{bowl_style.output_suffix}_P2S.3mf"

    build_kwargs = dict(
        mesh_dir=meshes,
        output_path=output,
        name=cleaned,
        stand_hex=stand.hex,
        letter_hex=letters.hex,
        stand_name=stand.name,
        letter_name=letters.name,
        work_dir=work,
        template_path=GENERATOR_DIR / "blank_project.3mf",
    )
    if bowl_style.supports_fuzzy:
        build_kwargs.update(dims_root=job_dir, fuzzy_enabled=fuzzy_enabled)
    bowl_style.build_project(**build_kwargs)

    dims_path = job_dir / "dimensions_and_validation.json"
    meta = {
        "name": cleaned,
        "style": style,
        "font_style": font_style,
        "stand_filament_id": stand.id,
        "letter_filament_id": letters.id,
        "stand_hex": stand.hex,
        "letter_hex": letters.hex,
        "fuzzy_enabled": fuzzy_enabled if bowl_style.supports_fuzzy else False,
        "threemf": output.name,
        "rail_outer_deg": rail_outer,
    }
    (job_dir / "job.json").write_text(json.dumps(meta, indent=2) + "\n")

    return GenerateResult(
        name=cleaned,
        font_style=font_style,
        style=style,
        stand=stand,
        letters=letters,
        job_dir=job_dir,
        threemf_path=output,
        dimensions_path=dims_path,
        rail_outer_deg=rail_outer,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a custom bowl 3MF")
    parser.add_argument("--name", required=True)
    parser.add_argument("--style", default=DEFAULT_STYLE, choices=styles.STYLES)
    parser.add_argument("--font-style", default="bold", choices=FONT_STYLES)
    parser.add_argument("--stand", default=DEFAULT_STAND)
    parser.add_argument("--letters", default=DEFAULT_LETTERS)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-fuzzy", action="store_true")
    args = parser.parse_args()
    result = generate(
        args.name,
        args.out,
        style=args.style,
        font_style=args.font_style,
        stand_filament_id=args.stand,
        letter_filament_id=args.letters,
        fuzzy_enabled=not args.no_fuzzy,
    )
    print(result.threemf_path)
