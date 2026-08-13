#!/usr/bin/env python3
"""Render exact-mesh review evidence for the compact Squspi twin-rail joint."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
import squspi_ball_reconstruction as squspi


BACKGROUND = (247, 247, 245, 255)
INK = (38, 43, 47, 255)
MUTED = (92, 101, 108, 255)
SOURCE = (201, 206, 208, 255)
PANEL = (70, 133, 170, 255)
CARTRIDGE = (226, 135, 55, 255)
BASE = (126, 132, 136, 255)
REMOVED = (201, 67, 55, 255)
ADDED = (46, 145, 91, 255)


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
            if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf"
        ),
        (
            "/System/Library/Fonts/Supplemental/Helvetica.ttc"
        ),
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _shade(
    colour: tuple[int, int, int, int],
    amount: float,
) -> tuple[int, int, int, int]:
    amount = max(0.42, min(1.08, amount))
    return (
        min(255, int(colour[0] * amount)),
        min(255, int(colour[1] * amount)),
        min(255, int(colour[2] * amount)),
        colour[3],
    )


def _orthographic_render(
    objects: list[tuple[trimesh.Trimesh, tuple[int, int, int, int]]],
    *,
    camera: tuple[float, float, float],
    up_hint: tuple[float, float, float],
    size: tuple[int, int],
) -> Image.Image:
    """Render meshes with a deterministic triangle painter projection."""
    camera_v = np.asarray(camera, dtype=float)
    camera_v /= np.linalg.norm(camera_v)
    up_v = np.asarray(up_hint, dtype=float)
    up_v -= camera_v * float(np.dot(up_v, camera_v))
    up_v /= np.linalg.norm(up_v)
    right_v = np.cross(up_v, camera_v)
    right_v /= np.linalg.norm(right_v)
    up_v = np.cross(camera_v, right_v)

    projected_bounds = []
    prepared = []
    light = np.asarray([0.35, -0.55, 0.76], dtype=float)
    light /= np.linalg.norm(light)
    for mesh, colour in objects:
        vertices = np.asarray(mesh.vertices)
        projected = np.column_stack(
            [
                vertices @ right_v,
                vertices @ up_v,
                vertices @ camera_v,
            ]
        )
        projected_bounds.append(projected[:, :2])
        prepared.append((mesh, colour, projected))

    all_points = np.vstack(projected_bounds)
    low = all_points.min(axis=0)
    high = all_points.max(axis=0)
    span = np.maximum(high - low, 1e-6)
    width, height = size
    margin = 34
    scale = min(
        (width - 2 * margin) / span[0],
        (height - 2 * margin) / span[1],
    )
    centre = (low + high) / 2

    triangles = []
    for mesh, colour, projected in prepared:
        normals = np.asarray(mesh.face_normals)
        for index, face in enumerate(mesh.faces):
            points = projected[face]
            depth = float(np.mean(points[:, 2]))
            normal = normals[index]
            illumination = 0.62 + 0.34 * abs(float(np.dot(normal, light)))
            screen = [
                (
                    width / 2 + (point[0] - centre[0]) * scale,
                    height / 2 - (point[1] - centre[1]) * scale,
                )
                for point in points
            ]
            triangles.append((depth, screen, _shade(colour, illumination)))

    triangles.sort(key=lambda item: item[0])
    image = Image.new("RGBA", size, BACKGROUND)
    draw = ImageDraw.Draw(image, "RGBA")
    for _, points, colour in triangles:
        draw.polygon(points, fill=colour)
    return image


def _local_copy(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    result = mesh.copy()
    result.apply_transform(np.linalg.inv(squspi._real_keyed_panel_frame()[4]))
    return result


def _panel_with_title(
    content: Image.Image,
    title: str,
    subtitle: str,
) -> Image.Image:
    width, height = content.size
    result = Image.new("RGBA", (width, height + 92), BACKGROUND)
    result.alpha_composite(content, (0, 92))
    draw = ImageDraw.Draw(result)
    draw.text((18, 14), title, fill=INK, font=_font(25, bold=True))
    draw.text((18, 49), subtitle, fill=MUTED, font=_font(16))
    return result


def _compose_overlay(
    source: trimesh.Trimesh,
    panel: trimesh.Trimesh,
    cartridge: trimesh.Trimesh,
    base: trimesh.Trimesh,
    validation: dict,
) -> Image.Image:
    local_source = _local_copy(source)
    local_panel = _local_copy(panel)
    local_cartridge = _local_copy(cartridge)
    removed = trimesh.boolean.difference(
        [local_source, local_panel],
        engine="manifold",
    )
    added = trimesh.boolean.difference(
        [local_panel, local_source],
        engine="manifold",
    )
    removed = trimesh.util.concatenate(
        [
            component
            for component in removed.split(only_watertight=False)
            if abs(float(component.volume)) >= 1e-4
        ]
    )
    added = trimesh.util.concatenate(
        [
            component
            for component in added.split(only_watertight=False)
            if abs(float(component.volume)) >= 1e-4
        ]
    )

    camera = (1.15, -1.0, 0.75)
    up = (0.0, 1.0, 0.0)
    tile_size = (790, 580)
    tiles = [
        _panel_with_title(
            _orthographic_render(
                [(local_source, SOURCE)],
                camera=camera,
                up_hint=up,
                size=tile_size,
            ),
            "A. Exact source panel",
            "Cleaned source STL; no reconstructed shell",
        ),
        _panel_with_title(
            _orthographic_render(
                [
                    (local_panel, PANEL),
                    (local_cartridge, CARTRIDGE),
                ],
                camera=camera,
                up_hint=up,
                size=tile_size,
            ),
            "B. Compact twin-rail candidate",
            "Blue: source-derived panel  |  Orange: Tough+ cartridge",
        ),
        _panel_with_title(
            _orthographic_render(
                [
                    (local_panel, (205, 209, 211, 150)),
                    (removed, REMOVED),
                    (added, ADDED),
                ],
                camera=camera,
                up_hint=up,
                size=tile_size,
            ),
            "C. Exact boolean change volumes",
            "Red: removed  |  Green: added  |  Numerical slivers filtered",
        ),
    ]

    panel_pose = panel.copy()
    cartridge_pose = cartridge.copy()
    transform = squspi._real_keyed_panel_to_base_transform()
    panel_pose.apply_transform(transform)
    cartridge_pose.apply_transform(transform)
    assembled = _panel_with_title(
        _orthographic_render(
            [
                (base, BASE),
                (panel_pose, PANEL),
                (cartridge_pose, CARTRIDGE),
            ],
            camera=(1.0, -1.15, 0.70),
            up_hint=(0.0, 0.0, 1.0),
            size=tile_size,
        ),
        "D. Exact assembled neutral pose",
        "Ø4.50 tongue; Ø1.85 fixed ear; Ø1.90 running fits",
    )
    tiles.append(assembled)

    canvas = Image.new("RGBA", (1640, 1470), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (30, 20),
        "Squspi compact twin-rail — source fidelity review",
        fill=INK,
        font=_font(32, bold=True),
    )
    fidelity = validation["source_fidelity"]
    metric = (
        f"Removed {fidelity['removed_percent']:.3f}% of source volume  ·  "
        f"Added {fidelity['added_percent']:.3f}%  ·  "
        "source bounds unchanged"
    )
    draw.text((30, 62), metric, fill=MUTED, font=_font(19))
    positions = ((20, 105), (830, 105), (20, 790), (830, 790))
    for tile, position in zip(tiles, positions):
        canvas.alpha_composite(tile, position)
    return canvas


def _section_polygons(
    mesh: trimesh.Trimesh,
    *,
    axis: int,
    value: float,
    display_axes: tuple[int, int],
) -> list:
    normal = np.zeros(3)
    normal[axis] = 1.0
    origin = np.zeros(3)
    origin[axis] = value
    segments = trimesh.intersections.mesh_plane(
        mesh,
        plane_normal=normal,
        plane_origin=origin,
    )
    if len(segments) == 0:
        return []
    path = trimesh.load_path(segments[:, :, list(display_axes)])
    return [
        polygon
        for polygon in path.polygons_full
        if polygon.area > 1e-5
    ]


def _draw_section(
    source: trimesh.Trimesh,
    panel: trimesh.Trimesh,
    cartridge: trimesh.Trimesh,
    *,
    axis: int,
    value: float,
    display_axes: tuple[int, int],
    bounds: tuple[tuple[float, float], tuple[float, float]],
    labels: tuple[str, str],
    title: str,
    subtitle: str,
    size: tuple[int, int] = (760, 650),
) -> Image.Image:
    width, height = size
    margin_left, margin_right = 78, 28
    margin_top, margin_bottom = 76, 64
    x_range, y_range = bounds
    scale = min(
        (width - margin_left - margin_right) / (x_range[1] - x_range[0]),
        (height - margin_top - margin_bottom) / (y_range[1] - y_range[0]),
    )

    def screen(points: np.ndarray) -> list[tuple[float, float]]:
        return [
            (
                margin_left + (point[0] - x_range[0]) * scale,
                height - margin_bottom - (point[1] - y_range[0]) * scale,
            )
            for point in points
        ]

    image = Image.new("RGBA", size, BACKGROUND)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.text((18, 14), title, fill=INK, font=_font(24, bold=True))
    draw.text((18, 45), subtitle, fill=MUTED, font=_font(15))

    for tick in np.arange(math.ceil(x_range[0]), x_range[1] + 0.1, 1.0):
        x = margin_left + (tick - x_range[0]) * scale
        draw.line(
            [(x, margin_top), (x, height - margin_bottom)],
            fill=(224, 226, 226, 255),
            width=1,
        )
    for tick in np.arange(math.ceil(y_range[0]), y_range[1] + 0.1, 1.0):
        y = height - margin_bottom - (tick - y_range[0]) * scale
        draw.line(
            [(margin_left, y), (width - margin_right, y)],
            fill=(224, 226, 226, 255),
            width=1,
        )

    source_polygons = _section_polygons(
        source,
        axis=axis,
        value=value,
        display_axes=display_axes,
    )
    panel_polygons = _section_polygons(
        panel,
        axis=axis,
        value=value,
        display_axes=display_axes,
    )
    cartridge_polygons = _section_polygons(
        cartridge,
        axis=axis,
        value=value,
        display_axes=display_axes,
    )
    def fill_polygons(polygons: list, colour: tuple[int, int, int, int]) -> None:
        for polygon in polygons:
            draw.polygon(
                screen(np.asarray(polygon.exterior.coords)),
                fill=colour,
            )
            for interior in polygon.interiors:
                draw.polygon(
                    screen(np.asarray(interior.coords)),
                    fill=BACKGROUND,
                )

    fill_polygons(panel_polygons, (*PANEL[:3], 205))
    fill_polygons(cartridge_polygons, (*CARTRIDGE[:3], 235))
    for polygon in source_polygons:
        draw.line(
            screen(np.asarray(polygon.exterior.coords)),
            fill=INK,
            width=3,
            joint="curve",
        )
        for interior in polygon.interiors:
            draw.line(
                screen(np.asarray(interior.coords)),
                fill=INK,
                width=3,
                joint="curve",
            )

    draw.rectangle(
        (
            margin_left,
            margin_top,
            width - margin_right,
            height - margin_bottom,
        ),
        outline=(166, 171, 174, 255),
        width=2,
    )
    draw.text(
        (width / 2 - 20, height - 38),
        labels[0],
        fill=INK,
        font=_font(17, bold=True),
    )
    draw.text(
        (18, height / 2 - 10),
        labels[1],
        fill=INK,
        font=_font(17, bold=True),
    )
    return image


def _compose_sections(
    source: trimesh.Trimesh,
    panel: trimesh.Trimesh,
    cartridge: trimesh.Trimesh,
) -> Image.Image:
    source_local = _local_copy(source)
    panel_local = _local_copy(panel)
    cartridge_local = _local_copy(cartridge)
    tiles = [
        _draw_section(
            source_local,
            panel_local,
            cartridge_local,
            axis=1,
            value=-2.0,
            display_axes=(0, 2),
            bounds=((-7.0, 7.0), (-3.0, 7.0)),
            labels=("U (mm)", "W (mm)"),
            title="A. Transverse rail section",
            subtitle="Exact V = −2.00 mm mesh plane; source outline in black",
        ),
        _draw_section(
            source_local,
            panel_local,
            cartridge_local,
            axis=0,
            value=3.95,
            display_axes=(1, 2),
            bounds=((-7.0, 2.0), (-3.0, 7.0)),
            labels=("V (mm)", "W (mm)"),
            title="B. Primary rail and closed stop",
            subtitle="Exact U = +3.95 mm mesh plane",
        ),
        _draw_section(
            source_local,
            panel_local,
            cartridge_local,
            axis=2,
            value=0.45,
            display_axes=(0, 1),
            bounds=((-7.0, 7.0), (-7.0, 2.0)),
            labels=("U (mm)", "V (mm)"),
            title="C. Twin rails and latch plane",
            subtitle="Exact W = +0.45 mm mesh plane",
        ),
    ]
    canvas = Image.new("RGBA", (2360, 820), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (30, 20),
        "Exact connector sections — no hand-drawn geometry",
        fill=INK,
        font=_font(31, bold=True),
    )
    draw.text(
        (30, 60),
        "Black: original source boundary  ·  Blue: candidate panel  ·  "
        "Orange: Tough+ cartridge",
        fill=MUTED,
        font=_font(18),
    )
    for tile, x in zip(tiles, (20, 800, 1580)):
        canvas.alpha_composite(tile, (x, 120))
    return canvas


def _draw_arrow(
    image: Image.Image,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    colour: tuple[int, int, int, int] = INK,
    width: int = 8,
) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    start_v = np.asarray(start, dtype=float)
    end_v = np.asarray(end, dtype=float)
    vector = end_v - start_v
    length = float(np.linalg.norm(vector))
    if length <= 1e-6:
        return
    direction = vector / length
    normal = np.asarray([-direction[1], direction[0]])
    head_length = 22.0
    head_width = 13.0
    shaft_end = end_v - direction * head_length
    draw.line(
        [tuple(start_v), tuple(shaft_end)],
        fill=colour,
        width=width,
    )
    draw.polygon(
        [
            tuple(end_v),
            tuple(shaft_end + normal * head_width),
            tuple(shaft_end - normal * head_width),
        ],
        fill=colour,
    )


def _assembly_coupon_panel(source_panel: trimesh.Trimesh) -> trimesh.Trimesh:
    full_panel = squspi.build_real_keyed_panel_receiver(source_panel)
    crop = squspi._box((16.0, 18.0, 8.0), (2.0, 0.0, 16.0))
    return _local_copy(squspi._intersection([full_panel, crop]))


def _compose_coupon_assembly(
    source_panel: trimesh.Trimesh,
) -> Image.Image:
    printed_parts = squspi.build_twin_rail_curvature_coupon(source_panel)
    printed_objects = []
    printed_colours = (PANEL, CARTRIDGE, BASE)
    for index, ((_, mesh), colour) in enumerate(
        zip(printed_parts, printed_colours)
    ):
        shifted = mesh.copy()
        shifted.apply_translation([(index - 1) * 22.0, 0.0, 0.0])
        printed_objects.append((shifted, colour))

    panel = _assembly_coupon_panel(source_panel)
    cartridge = _local_copy(
        squspi._build_twin_rail_compliant_latch_cartridge(0.36, 2)
    )
    tongue = squspi.build_twin_rail_tongue_surrogate()
    tongue.apply_translation([0.0, 0.0, squspi.REAL_KEYED_PANEL_INWARD_OFFSET])
    pin = trimesh.creation.cylinder(
        radius=0.875,
        segment=np.asarray(
            [
                [-5.2, 0.0, squspi.REAL_KEYED_PANEL_INWARD_OFFSET],
                [5.2, 0.0, squspi.REAL_KEYED_PANEL_INWARD_OFFSET],
            ]
        ),
        sections=48,
    )

    exploded_cartridge = cartridge.copy()
    exploded_cartridge.apply_translation([0.0, 6.0, 0.0])
    exploded_pin = pin.copy()
    exploded_pin.apply_translation([4.0, 0.0, 0.0])

    tile_size = (790, 560)
    printed_tile = _orthographic_render(
        printed_objects,
        camera=(0.9, -1.0, 0.75),
        up_hint=(0.0, 0.0, 1.0),
        size=tile_size,
    )
    printed_draw = ImageDraw.Draw(printed_tile)
    printed_draw.text(
        (85, 510),
        "MATTE RECEIVER",
        fill=INK,
        font=_font(16, bold=True),
    )
    printed_draw.text(
        (330, 510),
        "TOUGH+ CARTRIDGE",
        fill=INK,
        font=_font(16, bold=True),
    )
    printed_draw.text(
        (615, 510),
        "MATTE TONGUE",
        fill=INK,
        font=_font(16, bold=True),
    )

    slide_tile = _orthographic_render(
        [(panel, PANEL), (exploded_cartridge, CARTRIDGE)],
        camera=(1.15, -1.0, 0.78),
        up_hint=(0.0, 1.0, 0.0),
        size=tile_size,
    )
    _draw_arrow(slide_tile, (500, 155), (440, 330), colour=REMOVED)
    slide_draw = ImageDraw.Draw(slide_tile)
    slide_draw.rounded_rectangle(
        (420, 35, 752, 105),
        radius=10,
        fill=(247, 247, 245, 235),
        outline=(166, 171, 174, 255),
        width=2,
    )
    slide_draw.text(
        (437, 48),
        "Slide both keys in together",
        fill=INK,
        font=_font(18, bold=True),
    )
    slide_draw.text(
        (437, 75),
        "toward the closed ends",
        fill=MUTED,
        font=_font(16),
    )

    pin_tile = _orthographic_render(
        [
            (cartridge, CARTRIDGE),
            (tongue, BASE),
            (exploded_pin, REMOVED),
        ],
        camera=(0.05, -1.0, 0.22),
        up_hint=(0.0, 0.0, 1.0),
        size=tile_size,
    )
    _draw_arrow(pin_tile, (675, 285), (510, 285), colour=REMOVED)
    pin_draw = ImageDraw.Draw(pin_tile)
    pin_draw.rounded_rectangle(
        (30, 35, 402, 112),
        radius=10,
        fill=(247, 247, 245, 235),
        outline=(166, 171, 174, 255),
        width=2,
    )
    pin_draw.text(
        (48, 48),
        "Place round tongue between ears",
        fill=INK,
        font=_font(18, bold=True),
    )
    pin_draw.text(
        (48, 78),
        "Insert pin from the loose Ø1.90 side",
        fill=MUTED,
        font=_font(16),
    )

    finished_tile = _orthographic_render(
        [(panel, PANEL), (cartridge, CARTRIDGE), (tongue, BASE), (pin, REMOVED)],
        camera=(1.15, -1.0, 0.72),
        up_hint=(0.0, 1.0, 0.0),
        size=tile_size,
    )
    finished_draw = ImageDraw.Draw(finished_tile)
    finished_draw.rounded_rectangle(
        (420, 38, 756, 105),
        radius=10,
        fill=(247, 247, 245, 235),
        outline=(166, 171, 174, 255),
        width=2,
    )
    finished_draw.text(
        (438, 51),
        "Finished: cartridge bottomed",
        fill=INK,
        font=_font(18, bold=True),
    )
    finished_draw.text(
        (438, 79),
        "and filament fixed in tight ear",
        fill=MUTED,
        font=_font(16),
    )

    tiles = [
        _panel_with_title(
            printed_tile,
            "1. Identify the three printed parts",
            "Exact print orientations from the supplied 3MF",
        ),
        _panel_with_title(
            slide_tile,
            "2. Slide — do not press vertically",
            "Circular ears stay above the curve; rails open for sliding",
        ),
        _panel_with_title(
            pin_tile,
            "3. Add tongue, align holes, insert filament",
            "Loose Ø1.90 ear → Ø2.05 tongue → tight Ø1.85 ear",
        ),
        _panel_with_title(
            finished_tile,
            "4. Check the completed coupon",
            "Latch retained; tongue pivots; pin does not migrate",
        ),
    ]
    canvas = Image.new("RGBA", (1640, 1460), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (30, 20),
        "Squspi twin-rail curvature coupon — assembly",
        fill=INK,
        font=_font(32, bold=True),
    )
    draw.text(
        (30, 62),
        "All component shapes below are rendered from the exact printable meshes.",
        fill=MUTED,
        font=_font(19),
    )
    for tile, position in zip(
        tiles,
        ((20, 105), (830, 105), (20, 785), (830, 785)),
    ):
        canvas.alpha_composite(tile, position)
    return canvas


def generate(source_dir: Path, output_dir: Path) -> list[Path]:
    source_paths = squspi._locate_masters(source_dir)
    source_panel = squspi.load_reference(source_paths["panel"])
    source_base = squspi.load_reference(source_paths["base"])
    selected_base = squspi.build_selected_source_base(source_base)
    panel = squspi.build_real_keyed_panel_receiver(source_panel)
    cartridge = squspi._build_twin_rail_compliant_latch_cartridge(0.36, 2)
    base = squspi.build_real_keyed_source_base(selected_base)
    validation = squspi.validate_real_keyed_joint(
        source_panel,
        panel,
        cartridge,
        base,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = output_dir / "twin-rail-source-overlay.png"
    section_path = output_dir / "twin-rail-sections.png"
    assembly_path = output_dir / "twin-rail-coupon-assembly.png"
    metrics_path = output_dir / "twin-rail-review-metrics.json"
    _compose_overlay(
        source_panel,
        panel,
        cartridge,
        base,
        validation,
    ).convert("RGB").save(overlay_path, quality=95)
    _compose_sections(
        source_panel,
        panel,
        cartridge,
    ).convert("RGB").save(section_path, quality=95)
    _compose_coupon_assembly(source_panel).convert("RGB").save(
        assembly_path,
        quality=95,
    )
    metrics_path.write_text(json.dumps(validation, indent=2) + "\n")
    return [overlay_path, section_path, assembly_path, metrics_path]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Render exact Squspi twin-rail review evidence"
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    for written_path in generate(arguments.source_dir, arguments.out):
        print(written_path)
