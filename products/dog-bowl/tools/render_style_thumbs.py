#!/usr/bin/env python3
"""Render the style-picker icons from the actual stands.

A hand-drawn icon set would be quicker and would start lying the day someone
changes a wall. These are rendered from the same meshes the generator prints, so
a new style gets a truthful icon by running this script — and an existing style
whose geometry changes gets a stale icon that is *visibly* stale.

Output: products/dog-bowl/assets/styles/<id>.png, transparent, 640x480.
Committed, because a web request must not trigger a mesh build.

Usage:  .venv/bin/python products/dog-bowl/tools/render_style_thumbs.py
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "products" / "dog-bowl" / "generator"))
sys.path.insert(0, str(REPO / "shared"))

import numpy as np  # noqa: E402

# Imported before pyrender, deliberately: ogma.render picks the offscreen GL
# backend by platform (EGL on Linux, pyglet's CGL on macOS) and applies the
# np.infty shim, both of which must happen before PyOpenGL is imported. This
# file used to force `PYOPENGL_PLATFORM=egl` unconditionally, which fails on a
# developer's Mac with "Unable to load EGL library".
from ogma import render as render_lib  # noqa: E402

import pyrender  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image  # noqa: E402

import styles  # noqa: E402
from ogma import preview as preview_lib  # noqa: E402
from preview import role_for  # noqa: E402

OUT = REPO / "products" / "dog-bowl" / "assets" / "styles"
W, H = 640, 480

# One colour per style, so the four cards are tellable apart at a glance.
#
# This reverses an earlier decision to render every style in the same neutral.
# The reasoning then was that colour is a second variable in a 90px picture; in
# practice the four cards sat next to each other in identical cream and the eye
# had to read the captions to tell a honeycomb from a fluted drum. Distinct hues
# do the separating, and the wall pattern still does the describing.
#
# Real Bambu Matte palette entries, not arbitrary swatches — and a label, not a
# claim: every style can be printed in every filament, the colour control is
# elsewhere in the form.
#
# Chosen on the same basis as DEFAULT_STAND: mid-luminance, because surface
# relief reads as a shading gradient and needs mid-tones. All four sit between
# 0.54 and 0.67, and their hues are far enough apart to survive a thumbnail.
STYLE_COLOURS = {
    "cooper": "#AE835B",   # Caramel      — warm brown
    "wave":   "#56B7E6",   # Sky Blue     — cyan
    "hex":    "#61C680",   # Grass Green  — green
    "fluted": "#AE96D4",   # Lilac Purple — violet
}
FALLBACK_COLOUR = "#9B9EA0"  # Ash Gray, for a style added without an entry

# Second colour for a two-tone body, keyed by the same style id.
#
# The split wave prints as two bodies meeting at the sine seam, and they can be
# different filament — that *is* the style, so an icon showing it in one colour
# describes the wrong product. Deeper blue rather than a contrasting hue: the
# card still has to read as "the blue one" against three siblings, so the seam
# is shown by a step in value, not by a second identity.
STYLE_UPPER_COLOURS = {
    "wave": "#0078BF",     # Marine Blue — lower body, under a Sky Blue upper
}

# Two letters, because the name is not what the icon is about but the geometry
# needs one. Kept short so the plaque doesn't dominate the crop.
SAMPLE_NAME = "AB"


def look_at(eye, target, up=(0, 0, 1)):
    eye = np.asarray(eye, float)
    target = np.asarray(target, float)
    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, np.asarray(up, float))
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[:3, 0] = s
    m[:3, 1] = u
    m[:3, 2] = -f
    m[:3, 3] = eye
    return m


def render(style_id: str) -> Image.Image:
    with tempfile.TemporaryDirectory() as td:
        with contextlib.redirect_stdout(io.StringIO()):
            styles.get(style_id).generate_meshes(Path(td), SAMPLE_NAME, "bold")
        meshes = [
            (trimesh.load_mesh(p), p.name)
            for p in preview_lib.assembled_meshes(Path(td) / "meshes")
            # The stainless bowl is the same in every style, so it carries no
            # information here and only steals the top third of the frame.
            if "REFERENCE_ONLY" not in p.name and "letter" not in p.name
        ]

    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.32] * 3)
    def material(hex_colour: str) -> pyrender.MetallicRoughnessMaterial:
        return pyrender.MetallicRoughnessMaterial(
            baseColorFactor=[*render_lib._srgb_to_linear(hex_colour), 1.0],
            metallicFactor=0.0,
            roughnessFactor=0.72,
        )

    # Grouped by the same role mapping the preview and the renderer use, so an
    # icon cannot disagree with the 3D view about which part is which colour.
    body = STYLE_COLOURS.get(style_id, FALLBACK_COLOUR)
    upper = STYLE_UPPER_COLOURS.get(style_id)
    groups: dict[str, list] = {}
    for mesh, name in meshes:
        groups.setdefault(role_for(name), []).append(mesh)

    for role, group in groups.items():
        # `stand_upper` only exists on a two-tone style; everything else is body.
        hex_colour = body if (role != "stand" or upper is None) else upper
        combined = trimesh.util.concatenate(group)
        # Crease-aware normals rather than flat shading: the pattern is the whole
        # point of the icon, and flat shading facets the drum it sits on. Same
        # 12° threshold the viewer and the offline renderer use.
        scene.add(
            pyrender.Mesh.from_trimesh(
                render_lib.creased_normals(combined),
                material=material(hex_colour),
                smooth=True,
            )
        )
    combined = trimesh.util.concatenate([m for g in groups.values() for m in g])

    centre = combined.bounds.mean(axis=0)
    extent = float(np.max(combined.bounds[1] - combined.bounds[0]))

    # Framed to show the silhouette *and* the wall. An earlier version stood
    # much closer and produced a crop of the wall: paws, hex and flutes were
    # legible but the split-wave style — whose signature is a seam across the
    # whole form — came out as a blank panel with one faint line.
    FOV = np.pi / 6           # 30 deg
    DISTANCE = extent * 2.25  # fits the stand with a little air
    direction = np.array([0.58, -1.0, 0.40])
    direction /= np.linalg.norm(direction)

    cam = pyrender.PerspectiveCamera(yfov=FOV)
    scene.add(cam, pose=look_at(centre + direction * DISTANCE, centre))

    scene.add(
        pyrender.DirectionalLight(color=[1, 0.97, 0.93], intensity=4.2),
        pose=look_at(centre + np.array([extent, -extent * 1.2, extent * 1.1]), centre),
    )
    scene.add(
        pyrender.DirectionalLight(color=[0.86, 0.9, 1.0], intensity=1.8),
        pose=look_at(centre + np.array([-extent, -extent * 0.5, extent * 0.4]), centre),
    )

    renderer = pyrender.OffscreenRenderer(W, H)
    colour, _ = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)
    renderer.delete()
    img = Image.fromarray(colour, "RGBA")
    # Trim transparent margin, then give it back a little — a card icon butted
    # right up against its own bounding box looks cramped.
    box = img.getbbox()
    if box:
        pad = 12
        img = img.crop(
            (max(0, box[0] - pad), max(0, box[1] - pad),
             min(W, box[2] + pad), min(H, box[3] + pad))
        )
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for style in styles.all_styles():
        if not style.generator_available:
            print(f"  {style.id}: no geometry yet, skipped")
            continue
        img = render(style.id)
        path = OUT / f"{style.id}.png"
        img.save(path, optimize=True)
        print(f"  {style.id}: {img.size[0]}x{img.size[1]}  {path.stat().st_size/1024:.0f} kB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
