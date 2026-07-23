#!/usr/bin/env python3
"""Generate multi-angle SVG concept sheets for the three scoped bowl styles."""

from __future__ import annotations

import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "style-previews"

INK = "#24343D"
MUTED = "#667982"
PAPER = "#F5F2EB"
CARD = "#FFFFFF"
STAND = "#8FCFD0"
STAND_DARK = "#55999B"
STAND_LIGHT = "#B8E3E2"
LETTER = "#D98E98"
GROOVE = "#4E8588"
LINE = "#CAD4D5"


def tag(name: str, attrs: dict[str, str | float], content: str = "") -> str:
    values = " ".join(f'{key}="{value}"' for key, value in attrs.items())
    return f"<{name} {values}>{content}</{name}>"


def text(x: float, y: float, value: str, cls: str = "label", anchor: str = "start") -> str:
    return tag("text", {"x": x, "y": y, "class": cls, "text-anchor": anchor}, value)


def hexagon(cx: float, cy: float, radius: float) -> str:
    points = []
    for i in range(6):
        angle = math.radians(60 * i)
        points.append(f"{cx + radius * math.cos(angle):.1f},{cy + radius * math.sin(angle):.1f}")
    return tag("polygon", {"points": " ".join(points), "class": "groove"})


def honeycomb(x: float, y: float, width: float, height: float, radius: float = 20.0) -> str:
    items = []
    dx = 1.5 * radius
    dy = math.sqrt(3.0) * radius
    col = 0
    cx = x - radius
    while cx <= x + width + radius:
        cy = y - radius + (0.5 * dy if col % 2 else 0.0)
        while cy <= y + height + radius:
            items.append(hexagon(cx, cy, radius))
            cy += dy
        col += 1
        cx += dx
    return "".join(items)


def paw(cx: float, cy: float, scale: float = 1.0) -> str:
    parts = [
        tag("ellipse", {"cx": cx, "cy": cy + 5 * scale, "rx": 8 * scale, "ry": 6 * scale}),
        tag("circle", {"cx": cx - 9 * scale, "cy": cy - 4 * scale, "r": 3.5 * scale}),
        tag("circle", {"cx": cx - 3 * scale, "cy": cy - 8 * scale, "r": 3.5 * scale}),
        tag("circle", {"cx": cx + 3 * scale, "cy": cy - 8 * scale, "r": 3.5 * scale}),
        tag("circle", {"cx": cx + 9 * scale, "cy": cy - 4 * scale, "r": 3.5 * scale}),
    ]
    return tag("g", {"class": "paw"}, "".join(parts))


def paw_field(x: float, y: float, cols: int, rows: int, dx: float, dy: float) -> str:
    items = []
    for row in range(rows):
        for col in range(cols):
            items.append(paw(x + col * dx + (dx * 0.5 if row % 2 else 0), y + row * dy, 0.85))
    return "".join(items)


def card(x: float, y: float, title_value: str, note: str) -> str:
    return (
        tag("rect", {"x": x, "y": y, "width": 700, "height": 380, "rx": 18, "class": "card"})
        + text(x + 24, y + 34, title_value, "view-title")
        + text(x + 676, y + 34, note, "note", "end")
    )


def dimension(x1: float, y1: float, x2: float, y2: float, label: str) -> str:
    horizontal = abs(y2 - y1) < abs(x2 - x1)
    tx = (x1 + x2) * 0.5
    ty = (y1 + y2) * 0.5 - (8 if horizontal else 0)
    return (
        tag("line", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "class": "dimension"})
        + tag("line", {"x1": x1, "y1": y1 - 7, "x2": x1, "y2": y1 + 7, "class": "dimension"})
        + tag("line", {"x1": x2, "y1": y2 - 7, "x2": x2, "y2": y2 + 7, "class": "dimension"})
        + text(tx, ty, label, "dimension-text", "middle")
    )


def front_view(style: str, x: float, y: float) -> str:
    left, top, width, height = x + 105, y + 72, 490, 238
    body = tag("rect", {"x": left, "y": top, "width": width, "height": height, "rx": 8, "class": "stand"})
    opening = (
        tag("ellipse", {"cx": left + width / 2, "cy": top + 3, "rx": width / 2, "ry": 35, "class": "rim"})
        + tag("ellipse", {"cx": left + width / 2, "cy": top + 2, "rx": 197, "ry": 25, "class": "bowl"})
    )
    pattern = ""
    if style == "cooper":
        pattern = tag(
            "g",
            {"clip-path": "url(#front-clip)"},
            paw_field(left + 36, top + 58, 10, 4, 49, 48),
        )
        rail = tag("rect", {"x": left + 139, "y": top + 88, "width": 212, "height": 82, "rx": 28, "class": "rail"})
    elif style == "wave":
        seam = (
            f"M {left} {top + 132} "
            f"C {left + 80} {top + 82}, {left + 165} {top + 182}, {left + 245} {top + 132} "
            f"S {left + 410} {top + 82}, {left + width} {top + 132}"
        )
        pattern = tag("path", {"d": seam, "class": "wave-seam"})
        rail = tag("rect", {"x": left + 139, "y": top + 63, "width": 212, "height": 82, "rx": 28, "class": "rail"})
    else:
        pattern = tag(
            "g",
            {"clip-path": "url(#front-clip)"},
            honeycomb(left - 5, top + 10, width + 10, height - 10, 22),
        )
        rail = tag("rect", {"x": left + 132, "y": top + 73, "width": 226, "height": 96, "rx": 30, "class": "name-window"})
    name = text(left + width / 2, top + 139, "MAX", "pet-name", "middle")
    return body + pattern + rail + opening + name + dimension(left, top + height + 35, left + width, top + height + 35, "170 mm OD")


def three_quarter_view(style: str, x: float, y: float) -> str:
    left, top = x + 130, y + 72
    body_path = (
        f"M {left} {top + 32} "
        f"C {left} {top + 4}, {left + 420} {top + 4}, {left + 420} {top + 32} "
        f"L {left + 420} {top + 238} "
        f"C {left + 420} {top + 274}, {left} {top + 274}, {left} {top + 238} Z"
    )
    body = tag("path", {"d": body_path, "class": "stand"})
    rim = (
        tag("ellipse", {"cx": left + 210, "cy": top + 32, "rx": 210, "ry": 43, "class": "rim"})
        + tag("ellipse", {"cx": left + 210, "cy": top + 29, "rx": 168, "ry": 31, "class": "bowl"})
    )
    detail = ""
    if style == "cooper":
        detail = tag("g", {"clip-path": "url(#perspective-clip)"}, paw_field(left + 35, top + 83, 9, 4, 48, 43))
        detail += tag("path", {"d": f"M {left + 132} {top + 105} Q {left + 210} {top + 83} {left + 288} {top + 105} L {left + 280} {top + 175} Q {left + 210} {top + 190} {left + 140} {top + 175} Z", "class": "rail"})
    elif style == "wave":
        detail = tag("path", {"d": f"M {left} {top + 148} C {left + 70} {top + 105}, {left + 140} {top + 190}, {left + 210} {top + 148} S {left + 350} {top + 105}, {left + 420} {top + 148}", "class": "wave-seam"})
        detail += tag("path", {"d": f"M {left + 130} {top + 88} Q {left + 210} {top + 68} {left + 290} {top + 88} L {left + 282} {top + 155} Q {left + 210} {top + 170} {left + 138} {top + 155} Z", "class": "rail"})
    else:
        detail = tag("g", {"clip-path": "url(#perspective-clip)"}, honeycomb(left - 6, top + 52, 430, 200, 20))
        detail += tag("rect", {"x": left + 126, "y": top + 91, "width": 176, "height": 94, "rx": 28, "class": "name-window"})
    return body + detail + rim + text(left + 214, top + 151, "MAX", "pet-name", "middle")


def side_view(style: str, x: float, y: float) -> str:
    left, top, width, height = x + 170, y + 70, 360, 240
    body = tag("rect", {"x": left, "y": top, "width": width, "height": height, "rx": 8, "class": "stand"})
    opening = (
        tag("ellipse", {"cx": left + width / 2, "cy": top + 3, "rx": width / 2, "ry": 28, "class": "rim"})
        + tag("ellipse", {"cx": left + width / 2, "cy": top + 2, "rx": 145, "ry": 20, "class": "bowl"})
    )
    if style == "cooper":
        detail = tag("g", {"clip-path": "url(#side-clip)"}, paw_field(left + 30, top + 58, 7, 4, 52, 48))
    elif style == "wave":
        detail = tag("path", {"d": f"M {left} {top + 130} C {left + 90} {top + 82}, {left + 180} {top + 178}, {left + 270} {top + 130} S {left + 340} {top + 96}, {left + width} {top + 130}", "class": "wave-seam"})
    else:
        detail = tag("g", {"clip-path": "url(#side-clip)"}, honeycomb(left - 4, top + 12, width + 8, height - 12, 21))
    return body + detail + opening + dimension(left - 35, top, left - 35, top + height, "78 mm H")


def top_view(style: str, x: float, y: float) -> str:
    cx, cy = x + 350, y + 202
    rings = (
        tag("circle", {"cx": cx, "cy": cy, "r": 144, "class": "stand"})
        + tag("circle", {"cx": cx, "cy": cy, "r": 119, "class": "rim"})
        + tag("circle", {"cx": cx, "cy": cy, "r": 108, "class": "bowl"})
    )
    if style == "cooper":
        marker = tag("path", {"d": f"M {cx - 72} {cy + 117} Q {cx} {cy + 151} {cx + 72} {cy + 117}", "class": "rail-line"})
    elif style == "wave":
        marker = tag("path", {"d": f"M {cx - 110} {cy + 94} Q {cx} {cy + 151} {cx + 110} {cy + 94}", "class": "wave-seam"})
    else:
        marker = tag("path", {"d": f"M {cx - 65} {cy + 126} Q {cx} {cy + 150} {cx + 65} {cy + 126}", "class": "smooth-marker"})
    return rings + marker + dimension(cx - 119, cy - 168, cx + 119, cy - 168, "Ø140 bowl family")


def build_sheet(style: str, title_value: str, subtitle: str, construction: str) -> str:
    defs = f"""
    <defs>
      <clipPath id="front-clip"><rect x="145" y="192" width="490" height="238" rx="8"/></clipPath>
      <clipPath id="perspective-clip"><path d="M 890 224 C 890 196 1310 196 1310 224 L 1310 430 C 1310 466 890 466 890 430 Z"/></clipPath>
      <clipPath id="side-clip"><rect x="210" y="610" width="360" height="240" rx="8"/></clipPath>
      <style>
        .card{{fill:{CARD};stroke:{LINE};stroke-width:1.5}}
        .stand{{fill:{STAND};stroke:{INK};stroke-width:2.2}}
        .rim{{fill:{STAND_LIGHT};stroke:{INK};stroke-width:2}}
        .bowl{{fill:{PAPER};stroke:{INK};stroke-width:2}}
        .groove{{fill:none;stroke:{GROOVE};stroke-width:5;stroke-linejoin:round}}
        .paw{{fill:{STAND_DARK};stroke:{GROOVE};stroke-width:1.5}}
        .rail{{fill:{STAND_LIGHT};stroke:{STAND_DARK};stroke-width:2}}
        .name-window{{fill:{STAND};stroke:none}}
        .wave-seam{{fill:none;stroke:{INK};stroke-width:6;stroke-linecap:round}}
        .rail-line,.smooth-marker{{fill:none;stroke:{STAND_DARK};stroke-width:8;stroke-linecap:round}}
        .pet-name{{font:700 36px system-ui,sans-serif;fill:{LETTER};stroke:{INK};stroke-width:.7;paint-order:stroke}}
        .title{{font:700 34px system-ui,sans-serif;fill:{INK}}}
        .subtitle{{font:400 17px system-ui,sans-serif;fill:{MUTED}}}
        .view-title{{font:650 19px system-ui,sans-serif;fill:{INK}}}
        .note{{font:500 13px system-ui,sans-serif;fill:{MUTED}}}
        .label{{font:500 14px system-ui,sans-serif;fill:{INK}}}
        .dimension{{stroke:{MUTED};stroke-width:1.4}}
        .dimension-text{{font:500 13px system-ui,sans-serif;fill:{MUTED}}}
        .footer{{font:500 14px system-ui,sans-serif;fill:{MUTED}}}
      </style>
    </defs>
    """
    content = [
        tag("rect", {"x": 0, "y": 0, "width": 1500, "height": 1000, "fill": PAPER}),
        text(40, 54, title_value, "title"),
        text(40, 86, subtitle, "subtitle"),
        text(1460, 54, "CONCEPT REVIEW · NOT A MESH RENDER", "note", "end"),
        card(40, 120, "Front elevation", "name treatment + pattern"),
        front_view(style, 40, 120),
        card(760, 120, "Three-quarter", "overall silhouette"),
        three_quarter_view(style, 760, 120),
        card(40, 540, "Side elevation", "wall treatment"),
        side_view(style, 40, 540),
        card(760, 540, "Top view", "shared Cooper insert"),
        top_view(style, 760, 540),
        text(40, 962, construction, "footer"),
        text(1460, 962, "Ogma Print · Ø140 Cooper insert · Bambu PLA Matte", "footer", "end"),
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1000" viewBox="0 0 1500 1000" role="img">\n'
        f"<title>{title_value} multi-angle concept sheet</title>\n"
        f"<desc>{subtitle}</desc>\n"
        f"{defs}{''.join(content)}\n</svg>\n"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sheets = {
        "cooper-paw-multi-angle.svg": build_sheet(
            "cooper",
            "Cooper Paw",
            "Recessed paw field · curved proud name rail · modular four-part stand",
            "4 plates: base · paw panel · top seat ring · curved-back glue-in letters",
        ),
        "wave-multi-angle.svg": build_sheet(
            "wave",
            "Wave",
            "Solid sculptural wall · sine seam · curved name rail on upper half",
            "3 plates: lower body · upper body printed inverted · curved-back glue-in letters",
        ),
        "honeycomb-multi-angle.svg": build_sheet(
            "honeycomb",
            "Honeycomb",
            "Solid cylindrical wall · recessed hex grooves · smooth central name area",
            "2 plates: single-piece body · curved-back glue-in letters; no open lattice or foot ring",
        ),
    }
    for filename, svg in sheets.items():
        path = OUT / filename
        path.write_text(svg)
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
