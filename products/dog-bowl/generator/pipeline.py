#!/usr/bin/env python3
"""Job pipeline: name + Matte colours → meshes + Bambu 3MF (local or Railway)."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parent
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ogma import assets  # noqa: E402

import cooper_bowl_design as design  # noqa: E402
import renders  # noqa: E402
import styles  # noqa: E402
from ogma.filaments import (  # noqa: E402
    DEFAULT_LETTERS,
    DEFAULT_STAND,
    DEFAULT_STAND_UPPER,
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
    #: The upper body colour on a two-tone style; equal to `stand` otherwise.
    upper: Filament
    job_dir: Path
    threemf_path: Path
    dimensions_path: Path
    rail_outer_deg: float
    #: Filenames under `job_dir/renders`. Empty when rendering was unavailable.
    renders: list[str]


def generate(
    name: str,
    job_dir: Path,
    *,
    style: str = DEFAULT_STYLE,
    font_style: str = "bold",
    stand_filament_id: str = DEFAULT_STAND,
    letter_filament_id: str = DEFAULT_LETTERS,
    upper_filament_id: str | None = None,
    bowl_diameter_mm: float | None = None,
    bowl_body_mm: float | None = None,
    one_piece: bool = False,
    fuzzy_enabled: bool = True,
    letters_enabled: bool = True,
) -> GenerateResult:
    """Generate printable meshes and a Bambu 3MF into job_dir.

    `letters_enabled=False` still cuts the name into the stand — the pockets are
    part of the body geometry — but leaves the glue-in letters off the plates, so
    the job prints as a single-colour stand with the name debossed.
    """
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
    # A style whose body is one part has no second colour to choose, so it
    # falls back to the stand's — which is what makes `upper` safe to read
    # unconditionally downstream.
    upper = resolve_filament(
        upper_filament_id or (DEFAULT_STAND_UPPER if bowl_style.two_tone_body else stand_filament_id),
        palette,
    ) if bowl_style.two_tone_body else stand

    work = assets.PLATE_PREVIEWS

    rail_outer = bowl_style.generate_meshes(
        job_dir, name, font_style,
        bowl_rim_od_mm=bowl_diameter_mm, bowl_body_od_mm=bowl_body_mm,
        one_piece=one_piece and bowl_style.supports_one_piece,
    )
    cleaned = design.NAME

    # Local time, not UTC: this name is read by whoever is standing at the
    # printer, and "which of these two ROCCO files did I export after the
    # bowl-depth change" is a question about their afternoon, not about UTC.
    # Seconds included because a customer re-exporting after a tweak can easily
    # land in the same minute, and the whole point is that the two files are
    # tellable apart in a downloads folder.
    created = datetime.now()
    stamp = created.strftime("%Y%m%d-%H%M%S")
    output = job_dir / f"{cleaned}_{bowl_style.output_suffix}_P2S_{stamp}.3mf"

    build_kwargs = dict(
        mesh_dir=meshes,
        output_path=output,
        name=cleaned,
        stand_hex=stand.hex,
        letter_hex=letters.hex,
        stand_name=stand.name,
        letter_name=letters.name,
        work_dir=work,
        template_path=assets.BLANK_PROJECT,
        include_letters=letters_enabled,
    )
    if bowl_style.supports_fuzzy:
        build_kwargs.update(dims_root=job_dir, fuzzy_enabled=fuzzy_enabled)
    if bowl_style.supports_one_piece:
        build_kwargs.update(one_piece=one_piece)
    if bowl_style.two_tone_body:
        build_kwargs.update(upper_hex=upper.hex, upper_name=upper.name)
    bowl_style.build_project(**build_kwargs)

    # Photoreal stills of the assembled stand. Deliberately last, and
    # deliberately non-fatal (see renders.build): the 3MF is the deliverable and
    # a machine without a GL stack must still be able to produce one.
    render_files = renders.build(
        job_dir,
        stand_hex=stand.hex,
        letter_hex=letters.hex,
        upper_hex=upper.hex,
        letters_enabled=letters_enabled,
    )

    dims_path = job_dir / "dimensions_and_validation.json"
    meta = {
        "name": cleaned,
        "style": style,
        "font_style": font_style,
        "stand_filament_id": stand.id,
        # Null rather than the untouched default: with letters off the customer
        # never chose a second colour, and job.json is what the shop reads to
        # decide which filaments to load.
        "letter_filament_id": letters.id if letters_enabled else None,
        "stand_hex": stand.hex,
        "letter_hex": letters.hex if letters_enabled else None,
        # Null on a single-body style, so job.json never implies the shop has a
        # third filament to load when it does not.
        "upper_filament_id": upper.id if bowl_style.two_tone_body else None,
        "upper_hex": upper.hex if bowl_style.two_tone_body else None,
        "bowl_diameter_mm": design.BOWL_RIM_OD,
        "bowl_body_mm": design.BOWL_BODY_OD,
        "bowl_opening_mm": design.BOWL_OPENING_D,
        "one_piece": one_piece and bowl_style.supports_one_piece,
        "letters_enabled": letters_enabled,
        "fuzzy_enabled": fuzzy_enabled if bowl_style.supports_fuzzy else False,
        "threemf": output.name,
        "renders": render_files,
        "created_at": created.isoformat(timespec="seconds"),
        "rail_outer_deg": rail_outer,
    }
    (job_dir / "job.json").write_text(json.dumps(meta, indent=2) + "\n")

    return GenerateResult(
        name=cleaned,
        font_style=font_style,
        style=style,
        stand=stand,
        letters=letters,
        upper=upper,
        job_dir=job_dir,
        threemf_path=output,
        dimensions_path=dims_path,
        rail_outer_deg=rail_outer,
        renders=render_files,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a custom bowl 3MF")
    parser.add_argument("--name", required=True)
    parser.add_argument("--style", default=DEFAULT_STYLE, choices=styles.STYLES)
    parser.add_argument("--font-style", default="bold", choices=FONT_STYLES)
    parser.add_argument("--stand", default=DEFAULT_STAND)
    parser.add_argument("--letters", default=DEFAULT_LETTERS)
    parser.add_argument("--one-piece", action="store_true",
                        help="Print as a single body instead of keyed parts.")
    parser.add_argument("--bowl-body", type=float, default=None,
                        help="Bowl body diameter just below the rim, in mm.")
    parser.add_argument("--bowl-diameter", type=float, default=None,
                        help="Bowl rim outer diameter in mm (127-152).")
    parser.add_argument(
        "--upper", default=None,
        help="Upper body colour; two-tone styles only (the split wave).",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-fuzzy", action="store_true")
    parser.add_argument(
        "--no-letters",
        action="store_true",
        help="Skip the glue-in letters; the name stays as recessed pockets.",
    )
    args = parser.parse_args()
    result = generate(
        args.name,
        args.out,
        style=args.style,
        font_style=args.font_style,
        stand_filament_id=args.stand,
        letter_filament_id=args.letters,
        upper_filament_id=args.upper,
        bowl_diameter_mm=args.bowl_diameter,
        bowl_body_mm=args.bowl_body,
        one_piece=args.one_piece,
        fuzzy_enabled=not args.no_fuzzy,
        letters_enabled=not args.no_letters,
    )
    print(result.threemf_path)
