"""Generate Oggie Spin interchangeable thumb-pad mechanism visuals.

Run from the repository root:

    python3 scripts/generate_spinner_thumb_options_svg.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = (
    ROOT / "design" / "modular-spinner" / "active" / "oggie-spin-thumb-mechanisms.svg"
)

W, H = 1600, 1100
PAPER = "#0B1220"
PANEL = "#121C2E"
INK = "#E8EEF8"
MUTED = "#8FA0B8"
HAIR = "#2A3A55"
ACCENT = "#FF6A3D"
ACCENT_SOFT = "#FFB089"
CORE = "#55ADE5"
CORE_D = "#2F7EBA"
PAD = "#F0C14A"
PAD_D = "#B58516"
STEEL = "#C5D0DE"
STEEL_D = "#6E7B8E"
OK = "#5DDBA0"
WARN = "#FFB45E"


def text(x: float, y: float, value: str, size: int = 12, fill: str = MUTED,
         weight: int = 400, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" text-anchor="{anchor}" '
        'font-family="IBM Plex Sans, Segoe UI, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{value}</text>'
    )


def panel(x: int, y: int, w: int, h: int, number: str, title: str,
          badge: str, badge_fill: str) -> list[str]:
    return [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
        f'fill="{PANEL}" stroke="{HAIR}" stroke-width="1.4"/>',
        text(x + 22, y + 34, f"{number}  {title.upper()}", 13, MUTED, 700),
        f'<rect x="{x + w - 178}" y="{y + 18}" width="156" height="26" '
        f'rx="13" fill="{badge_fill}" opacity="0.16"/>',
        text(x + w - 100, y + 36, badge, 11, badge_fill, 700, "middle"),
    ]


def defs() -> list[str]:
    return [
        "<defs>",
        '  <linearGradient id="coreGrad" x1="0" y1="0" x2="1" y2="1">',
        f'    <stop offset="0" stop-color="{CORE}"/>',
        f'    <stop offset="1" stop-color="{CORE_D}"/>',
        "  </linearGradient>",
        '  <linearGradient id="padGrad" x1="0" y1="0" x2="1" y2="1">',
        f'    <stop offset="0" stop-color="{PAD}"/>',
        f'    <stop offset="1" stop-color="{PAD_D}"/>',
        "  </linearGradient>",
        '  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">',
        f'    <path d="M 0 0 L 10 5 L 0 10 Z" fill="{OK}"/>',
        "  </marker>",
        "</defs>",
    ]


def common_hub(x: int, y: int) -> list[str]:
    """Permanent R188 cartridge shown in section."""
    return [
        f'<rect x="{x}" y="{y + 42}" width="250" height="64" rx="8" '
        'fill="url(#coreGrad)"/>',
        f'<rect x="{x + 70}" y="{y + 48}" width="110" height="52" rx="3" '
        f'fill="{STEEL}"/>',
        f'<rect x="{x + 98}" y="{y + 48}" width="54" height="52" '
        f'fill="{STEEL_D}"/>',
        f'<rect x="{x + 108}" y="{y + 20}" width="34" height="112" rx="5" '
        f'fill="{ACCENT_SOFT}" stroke="{ACCENT}" stroke-width="1.2"/>',
        f'<rect x="{x + 120}" y="{y + 12}" width="10" height="128" rx="3" '
        f'fill="{STEEL}" stroke="{STEEL_D}" stroke-width="1"/>',
        f'<rect x="{x + 90}" y="{y + 103}" width="70" height="13" rx="3" '
        f'fill="{ACCENT}"/>',
        text(x + 270, y + 66, "R188 outer race → core", 12),
        text(x + 270, y + 86, "Tough+ axle → inner race", 12, ACCENT_SOFT),
        text(x + 270, y + 106, "structural hub remains installed", 12, OK),
    ]


def base_section(x: int, y: int) -> list[str]:
    """Core, bearing and permanent hub base shared by each option."""
    return [
        f'<rect x="{x}" y="{y + 138}" width="300" height="58" rx="6" '
        'fill="url(#coreGrad)"/>',
        f'<rect x="{x + 94}" y="{y + 143}" width="112" height="48" rx="3" '
        f'fill="{STEEL}"/>',
        f'<rect x="{x + 122}" y="{y + 143}" width="56" height="48" '
        f'fill="{STEEL_D}"/>',
        f'<rect x="{x + 131}" y="{y + 112}" width="38" height="88" rx="4" '
        f'fill="{ACCENT_SOFT}" stroke="{ACCENT}" stroke-width="1.1"/>',
        f'<rect x="{x + 145}" y="{y + 105}" width="10" height="105" rx="2" '
        f'fill="{STEEL}"/>',
        f'<line x1="{x + 72}" y1="{y + 130}" x2="{x + 228}" y2="{y + 130}" '
        f'stroke="{OK}" stroke-dasharray="3 3"/>',
        text(x + 238, y + 134, "0.4 mm", 10, OK),
    ]


def o_ring_panel(x: int, y: int) -> list[str]:
    out = panel(x, y, 740, 390, "A", "keyed O-ring push-fit",
                "BEST START", OK)
    sx, sy = x + 55, y + 64
    out += base_section(sx, sy)
    # Removable pad with keyed blind socket and pull lips.
    out += [
        f'<path d="M {sx + 62} {sy + 20} Q {sx + 150} {sy - 2} {sx + 238} {sy + 20} '
        f'L {sx + 230} {sy + 70} L {sx + 178} {sy + 70} L {sx + 173} {sy + 104} '
        f'L {sx + 127} {sy + 104} L {sx + 122} {sy + 70} L {sx + 70} {sy + 70} Z" '
        'fill="url(#padGrad)" stroke="#E8EEF8" stroke-width="1"/>',
        f'<rect x="{sx + 128}" y="{sy + 68}" width="44" height="40" rx="5" '
        f'fill="{PANEL}" stroke="{PAD}" stroke-width="1"/>',
        f'<ellipse cx="{sx + 150}" cy="{sy + 94}" rx="21" ry="5" '
        f'fill="none" stroke="{OK}" stroke-width="5"/>',
        f'<path d="M {sx + 150} {sy + 2} L {sx + 150} {sy + 55}" '
        f'stroke="{OK}" stroke-width="2" marker-end="url(#arrow)"/>',
        text(sx + 150, sy - 8, "PUSH", 11, OK, 700, "middle"),
        text(sx + 330, sy + 30, "Keyed blind socket", 12, INK, 600),
        text(sx + 330, sy + 52, "prevents pad rotation", 11),
        text(sx + 330, sy + 90, "Replaceable O-ring", 12, OK, 600),
        text(sx + 330, sy + 112, "absorbs tolerance variation", 11),
        text(sx + 330, sy + 150, "Underside pull lip", 12, INK, 600),
        text(sx + 330, sy + 172, "pad pulls off; hub stays", 11),
        text(sx + 28, sy + 242, "Interaction", 11, MUTED, 700),
        text(sx + 28, sy + 266, "push to seat  ·  pull lip to remove", 14, INK, 600),
        text(sx + 28, sy + 304, "Strength", 11, MUTED, 700),
        text(sx + 28, sy + 326, "fastest swaps · no printed flexure · cheap wear part", 12, OK),
    ]
    return out


def bayonet_panel(x: int, y: int) -> list[str]:
    out = panel(x, y, 740, 390, "B", "push-and-turn bayonet",
                "MOST SECURE", OK)
    sx, sy = x + 55, y + 64
    out += base_section(sx, sy)
    out += [
        f'<path d="M {sx + 62} {sy + 20} Q {sx + 150} {sy - 2} {sx + 238} {sy + 20} '
        f'L {sx + 230} {sy + 74} L {sx + 174} {sy + 74} L {sx + 174} {sy + 106} '
        f'L {sx + 126} {sy + 106} L {sx + 126} {sy + 74} L {sx + 70} {sy + 74} Z" '
        'fill="url(#padGrad)" stroke="#E8EEF8" stroke-width="1"/>',
        f'<path d="M {sx + 125} {sy + 88} L {sx + 138} {sy + 88} '
        f'L {sx + 138} {sy + 102} L {sx + 162} {sy + 102} L {sx + 162} {sy + 88} '
        f'L {sx + 175} {sy + 88}" fill="none" stroke="{OK}" stroke-width="4"/>',
        f'<path d="M {sx + 103} {sy + 36} A 52 36 0 0 1 {sx + 198} {sy + 36}" '
        f'fill="none" stroke="{OK}" stroke-width="2" marker-end="url(#arrow)"/>',
        text(sx + 150, sy + 22, "PUSH + 25°", 11, OK, 700, "middle"),
        text(sx + 330, sy + 30, "Three short lugs", 12, INK, 600),
        text(sx + 330, sy + 52, "share axial finger load", 11),
        text(sx + 330, sy + 90, "Shallow preload ramp", 12, OK, 600),
        text(sx + 330, sy + 112, "removes cap movement", 11),
        text(sx + 330, sy + 150, "Positive end detent", 12, INK, 600),
        text(sx + 330, sy + 172, "resists accidental reverse turn", 11),
        text(sx + 28, sy + 242, "Interaction", 11, MUTED, 700),
        text(sx + 28, sy + 266, "align · push · quarter-turn · click", 14, INK, 600),
        text(sx + 28, sy + 304, "Trade-off", 11, MUTED, 700),
        text(sx + 28, sy + 326, "strongest retention · more geometry and print tuning", 12, OK),
    ]
    return out


def snap_panel(x: int, y: int) -> list[str]:
    out = panel(x, y, 740, 390, "C", "annular printed snap",
                "ALL PRINTED", WARN)
    sx, sy = x + 55, y + 64
    out += base_section(sx, sy)
    out += [
        f'<path d="M {sx + 62} {sy + 20} Q {sx + 150} {sy - 2} {sx + 238} {sy + 20} '
        f'L {sx + 230} {sy + 72} L {sx + 176} {sy + 72} '
        f'Q {sx + 176} {sy + 104} {sx + 164} {sy + 108} L {sx + 136} {sy + 108} '
        f'Q {sx + 124} {sy + 104} {sx + 124} {sy + 72} L {sx + 70} {sy + 72} Z" '
        'fill="url(#padGrad)" stroke="#E8EEF8" stroke-width="1"/>',
        f'<path d="M {sx + 132} {sy + 100} Q {sx + 150} {sy + 88} {sx + 168} {sy + 100}" '
        f'fill="none" stroke="{OK}" stroke-width="4"/>',
        f'<path d="M {sx + 150} {sy + 2} L {sx + 150} {sy + 55}" '
        f'stroke="{OK}" stroke-width="2" marker-end="url(#arrow)"/>',
        text(sx + 150, sy - 8, "PUSH TO SNAP", 11, OK, 700, "middle"),
        text(sx + 330, sy + 30, "Mushroom hub bead", 12, INK, 600),
        text(sx + 330, sy + 52, "cap lip flexes over once", 11),
        text(sx + 330, sy + 90, "Single-material interface", 12, WARN, 600),
        text(sx + 330, sy + 112, "sensitive to filament and layer direction", 11),
        text(sx + 330, sy + 150, "Wear concentrates at lip", 12, INK, 600),
        text(sx + 330, sy + 172, "retention falls over repeated swaps", 11),
        text(sx + 28, sy + 242, "Interaction", 11, MUTED, 700),
        text(sx + 28, sy + 266, "push to click  ·  pull firmly to remove", 14, INK, 600),
        text(sx + 28, sy + 304, "Use", 11, MUTED, 700),
        text(sx + 28, sy + 326, "lowest part count · suitable economy variant", 12, WARN),
    ]
    return out


def magnet_panel(x: int, y: int) -> list[str]:
    out = panel(x, y, 740, 390, "D", "captive magnet coupling",
                "NOT V1", WARN)
    sx, sy = x + 55, y + 64
    out += base_section(sx, sy)
    out += [
        f'<path d="M {sx + 62} {sy + 20} Q {sx + 150} {sy - 2} {sx + 238} {sy + 20} '
        f'L {sx + 230} {sy + 72} L {sx + 174} {sy + 72} L {sx + 174} {sy + 104} '
        f'L {sx + 126} {sy + 104} L {sx + 126} {sy + 72} L {sx + 70} {sy + 72} Z" '
        'fill="url(#padGrad)" stroke="#E8EEF8" stroke-width="1"/>',
        f'<rect x="{sx + 128}" y="{sy + 78}" width="44" height="12" rx="3" '
        f'fill="{STEEL_D}" stroke="{STEEL}"/>',
        f'<rect x="{sx + 128}" y="{sy + 104}" width="44" height="10" rx="3" '
        f'fill="{STEEL_D}" stroke="{STEEL}"/>',
        f'<line x1="{sx + 132}" y1="{sy + 96}" x2="{sx + 168}" y2="{sy + 96}" '
        f'stroke="{OK}" stroke-width="2" stroke-dasharray="3 3"/>',
        text(sx + 150, sy + 64, "N", 10, INK, 700, "middle"),
        text(sx + 150, sy + 125, "S", 10, INK, 700, "middle"),
        text(sx + 330, sy + 30, "Captive magnet pockets", 12, INK, 600),
        text(sx + 330, sy + 52, "must be mechanically closed", 11),
        text(sx + 330, sy + 90, "Excellent tactile swap", 12, OK, 600),
        text(sx + 330, sy + 112, "no alignment force after key engages", 11),
        text(sx + 330, sy + 150, "Small-part and polarity risk", 12, WARN, 600),
        text(sx + 330, sy + 172, "validate interaction with steel bearing", 11),
        text(sx + 28, sy + 242, "Interaction", 11, MUTED, 700),
        text(sx + 28, sy + 266, "bring near to attach  ·  pull directly away", 14, INK, 600),
        text(sx + 28, sy + 304, "Decision", 11, MUTED, 700),
        text(sx + 28, sy + 326, "premium experiment only · exclude from first build", 12, WARN),
    ]
    return out


def build() -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
        '<title id="title">Oggie Spin interchangeable thumb-pad mechanisms</title>',
        '<desc id="desc">Four ways to attach removable finger pads to a permanent '
        'R188 bearing hub: keyed O-ring, bayonet, printed snap and magnets.</desc>',
    ]
    parts += defs()
    parts += [
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        text(48, 52, "OGGIE SPIN · THUMB INTERFACES", 32, INK, 500),
        text(48, 80, "One permanent R188 hub cartridge · four interchangeable pad mechanisms", 14),
        f'<rect x="48" y="94" width="78" height="4" rx="2" fill="{ACCENT}"/>',
        text(970, 48, "COMMON ARCHITECTURE", 11, MUTED, 700),
    ]
    parts += common_hub(970, 46)
    parts += o_ring_panel(40, 220)
    parts += bayonet_panel(820, 220)
    parts += snap_panel(40, 630)
    parts += magnet_panel(820, 630)
    parts += [
        text(48, 1060, "Prototype first", 12, MUTED, 700),
        text(150, 1060, "A · keyed O-ring", 13, OK, 700),
        text(310, 1060, "and", 12),
        text(345, 1060, "B · bayonet", 13, OK, 700),
        text(475, 1060, "— compare pull force, wobble and 100-cycle wear.", 12, INK),
        "</svg>",
    ]
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build(), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
