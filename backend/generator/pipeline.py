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
import build_bambu_project as bambu  # noqa: E402


FONT_STYLES = ("bold", "rounded", "condensed")
DEFAULT_STAND = "matte-caramel"
DEFAULT_LETTERS = "matte-ivory-white"
PALETTE_PATH = BACKEND_DIR / "data" / "filament_palette.json"


@dataclass(frozen=True)
class Filament:
    id: str
    name: str
    hex: str


def load_palette(path: Path = PALETTE_PATH) -> dict[str, Filament]:
    data = json.loads(path.read_text())
    return {
        item["id"]: Filament(id=item["id"], name=item["name"], hex=item["hex"].upper())
        for item in data["filaments"]
    }


def resolve_filament(filament_id: str, palette: dict[str, Filament] | None = None) -> Filament:
    palette = palette or load_palette()
    if filament_id not in palette:
        raise ValueError(f"Unknown filament '{filament_id}'. Use a Bambu PLA Matte swatch id.")
    return palette[filament_id]


@dataclass
class GenerateResult:
    name: str
    font_style: str
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
    font_style: str = "bold",
    stand_filament_id: str = DEFAULT_STAND,
    letter_filament_id: str = DEFAULT_LETTERS,
    fuzzy_enabled: bool = True,
) -> GenerateResult:
    """Generate printable meshes and a 4-plate Bambu 3MF into job_dir."""
    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    meshes = job_dir / "meshes"
    if meshes.exists():
        shutil.rmtree(meshes)

    palette = load_palette()
    stand = resolve_filament(stand_filament_id, palette)
    letters = resolve_filament(letter_filament_id, palette)

    design.configure_output(job_dir, name=name, font_style=font_style)
    cleaned = design.NAME
    design.main()

    dims_path = job_dir / "dimensions_and_validation.json"
    dims = json.loads(dims_path.read_text())
    rail_outer = float(dims["letters"]["name_rail_outer_deg"])

    work = GENERATOR_DIR / "bambu_work"
    output = job_dir / f"{cleaned}_Paw_Lattice_P2S.3mf"
    bambu.build_project(
        mesh_dir=meshes,
        output_path=output,
        name=cleaned,
        stand_hex=stand.hex,
        letter_hex=letters.hex,
        stand_name=stand.name,
        letter_name=letters.name,
        work_dir=work,
        template_path=GENERATOR_DIR / "blank_project.3mf",
        dims_root=job_dir,
        fuzzy_enabled=fuzzy_enabled,
    )

    meta = {
        "name": cleaned,
        "font_style": font_style,
        "stand_filament_id": stand.id,
        "letter_filament_id": letters.id,
        "stand_hex": stand.hex,
        "letter_hex": letters.hex,
        "fuzzy_enabled": fuzzy_enabled,
        "threemf": output.name,
        "rail_outer_deg": rail_outer,
    }
    (job_dir / "job.json").write_text(json.dumps(meta, indent=2) + "\n")

    return GenerateResult(
        name=cleaned,
        font_style=font_style,
        stand=stand,
        letters=letters,
        job_dir=job_dir,
        threemf_path=output,
        dimensions_path=dims_path,
        rail_outer_deg=rail_outer,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a custom paw-lattice bowl 3MF")
    parser.add_argument("--name", required=True)
    parser.add_argument("--font-style", default="bold", choices=FONT_STYLES)
    parser.add_argument("--stand", default=DEFAULT_STAND)
    parser.add_argument("--letters", default=DEFAULT_LETTERS)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-fuzzy", action="store_true")
    args = parser.parse_args()
    result = generate(
        args.name,
        args.out,
        font_style=args.font_style,
        stand_filament_id=args.stand,
        letter_filament_id=args.letters,
        fuzzy_enabled=not args.no_fuzzy,
    )
    print(result.threemf_path)
