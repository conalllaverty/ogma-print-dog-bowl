#!/usr/bin/env python3
"""Render preview images of the assembled Bouclé Stack lamp.

A small painter's-algorithm rasteriser, so the repo needs no GPU or GL stack to
produce a picture of the lamp. It is for looking at, not for judging finish —
use Bambu Studio's preview for anything that matters.

    .venv/bin/python scripts/render_lamp_preview.py --out design/boucle-stack-lamp/assembly
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "generator"))

import boucle_lamp_assembly as asm  # noqa: E402
import boucle_lamp_config as cfg  # noqa: E402

SUPERSAMPLE = 3
KEY_LIGHT = (0.45, -0.85, 0.5)
FILL_LIGHT = (-0.7, -0.4, 0.15)
LED_POSITION = (0.0, 0.0, cfg.CRADLE_Z1 + 2.0)
GLOW = np.array([255, 214, 150], dtype=float)


def _unit(vector) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    return vector / np.linalg.norm(vector)


def _camera(eye, target, up=(0.0, 0.0, 1.0)):
    eye = np.asarray(eye, dtype=float)
    forward = _unit(np.asarray(target, dtype=float) - eye)
    right = _unit(np.cross(forward, up))
    return eye, np.array([right, np.cross(right, forward), -forward])


def _shade(piece, normals, centroids):
    """Matte PLA under two soft studio lights."""
    key, fill = _unit(KEY_LIGHT), _unit(FILL_LIGHT)
    level = (
        0.30
        + 0.62 * np.clip(normals @ key, 0.0, 1.0)
        + 0.22 * np.clip(normals @ fill, 0.0, 1.0)
    )
    return np.asarray(piece.colour[:3], dtype=float)[None, :] * level[:, None]


def _shade_lit(piece, normals, centroids):
    """Lamp switched on: one point source where the LED module sits.

    `transmit` fakes the wall glow — a face whose *back* is toward the LED
    still reads bright, which is most of the effect in 1.6 mm Matte PLA.
    """
    to_led = np.asarray(LED_POSITION, dtype=float)[None, :] - centroids
    distance = np.linalg.norm(to_led, axis=1)
    direction = to_led / distance[:, None]
    falloff = 26000.0 / (distance**2 + 900.0)

    cosine = np.einsum("ij,ij->i", normals, direction)
    direct = np.clip(cosine, 0.0, 1.0) * falloff
    through = piece.transmit * np.clip(-cosine, 0.0, 1.0) ** 0.6 * falloff

    ambient = 0.10 + 0.13 * np.clip(normals @ _unit((0.3, -0.9, 0.35)), 0.0, 1.0)
    base = np.asarray(piece.colour[:3], dtype=float)[None, :]
    return base * ambient[:, None] + GLOW[None, :] * np.clip(direct + through, 0.0, 1.4)[
        :, None
    ]


def render(
    pieces,
    size,
    eye,
    target,
    fov=26.0,
    background=(247, 245, 241),
    floor=(176, 170, 160),
    shader=_shade,
):
    width, height = size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE
    image = Image.new("RGB", (width, height), background)
    eye, basis = _camera(eye, target)
    focal = 0.5 * height / math.tan(math.radians(fov) / 2.0)
    centre = np.array([width / 2.0, height / 2.0])

    def project(points):
        camera_space = (points - eye) @ basis.T
        depth = np.maximum(-camera_space[:, 2], 1e-6)
        screen = np.stack(
            [
                centre[0] + focal * camera_space[:, 0] / depth,
                centre[1] - focal * camera_space[:, 1] / depth,
            ],
            axis=1,
        )
        return screen, depth

    if floor is not None:
        angles = np.linspace(0.0, 2.0 * np.pi, 96)
        disc = np.stack(
            [np.cos(angles) * 96.0, np.sin(angles) * 96.0, np.zeros_like(angles)], axis=1
        )
        screen, _ = project(disc)
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).polygon([tuple(p) for p in screen], fill=70)
        mask = mask.filter(ImageFilter.GaussianBlur(28 * SUPERSAMPLE))
        image.paste(Image.new("RGB", (width, height), floor), (0, 0), mask)

    triangles, colours, depths = [], [], []
    for piece in pieces:
        mesh = piece.mesh
        faces, normals = mesh.faces, mesh.face_normals
        centroids = mesh.vertices[faces].mean(axis=1)
        facing = np.einsum("ij,ij->i", normals, eye - centroids) > 0.0
        if not facing.any():
            continue
        faces, normals, centroids = faces[facing], normals[facing], centroids[facing]

        screen, depth = project(mesh.vertices)
        triangles.append(screen[faces])
        colours.append(np.clip(shader(piece, normals, centroids), 0, 255).astype(np.uint8))
        depths.append(depth[faces].mean(axis=1))

    triangles = np.concatenate(triangles)
    colours = np.concatenate(colours)
    depths = np.concatenate(depths)

    draw = ImageDraw.Draw(image)
    for index in np.argsort(-depths):
        tri = triangles[index]
        colour = (int(colours[index][0]), int(colours[index][1]), int(colours[index][2]))
        draw.polygon(
            [(tri[0][0], tri[0][1]), (tri[1][0], tri[1][1]), (tri[2][0], tri[2][1])],
            fill=colour,
            outline=colour,
        )

    return image.resize(size, Image.LANCZOS)


def half_section(pieces):
    """Cut the near half away so the LED, cradle and halo rings are visible."""
    cut = []
    for piece in pieces:
        mesh = piece.mesh.slice_plane(
            plane_origin=(0.0, 0.0, 0.0), plane_normal=(0.0, 1.0, 0.0), cap=True
        )
        if mesh is None or mesh.is_empty:
            continue
        cut.append(
            asm.Piece(piece.label, mesh, piece.colour, piece.extruder, transmit=piece.transmit)
        )
    return cut


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the assembled lamp")
    parser.add_argument("--out", type=Path, default=ROOT / "design/boucle-stack-lamp/assembly")
    args = parser.parse_args()
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    pieces, _report = asm.build_assembly()
    target = np.array([0.0, 0.0, 118.0])

    render(pieces, (760, 1000), [430.0, -720.0, 300.0], target, fov=26.0).save(
        out_dir / "preview_three_quarter.png"
    )
    render(pieces, (700, 1000), [0.0, -900.0, 150.0], target, fov=22.0).save(
        out_dir / "preview_elevation.png"
    )
    render(
        half_section(pieces),
        (700, 1000),
        [60.0, -880.0, 240.0],
        target,
        fov=22.0,
        background=(240, 238, 234),
    ).save(out_dir / "preview_section.png")
    render(
        pieces,
        (760, 1000),
        [430.0, -720.0, 240.0],
        target,
        fov=26.0,
        background=(20, 19, 23),
        floor=(46, 41, 38),
        shader=_shade_lit,
    ).save(out_dir / "preview_lit.png")

    for path in sorted(out_dir.glob("preview_*.png")):
        print(path)


if __name__ == "__main__":
    main()
