"""Generate the 2D concept sheet for the Oggie Spin modular fidget spinner.

Run from the repository root:

    python3 scripts/generate_spinner_concept_svg.py
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "design" / "modular-spinner" / "active" / "oggie-spin-concept.svg"

W, H = 1600, 1100

PAPER = "#0B1220"
PANEL = "#121C2E"
INK = "#E8EEF8"
MUTED = "#8FA0B8"
HAIR = "#2A3A55"
ACCENT = "#FF6A3D"
ACCENT_SOFT = "#FFB089"
CORE = "#6EC6FF"
CORE_D = "#3A8FCF"
ARM_A = "#5BB8F5"
ARM_B = "#FF8A4C"
ARM_C = "#F0C14A"
ARM_D = "#5DDBA0"
ARM_E = "#A78BFA"
STEEL = "#C5D0DE"
STEEL_D = "#7A8799"
OK = "#5DDBA0"


def n(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def svg_header() -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
        "<title id=\"title\">Oggie Spin modular fidget spinner — concept</title>",
        "<desc id=\"desc\">Oggie Spin concept using the Lok Core platform: "
        "a larger round core with five radial-capturing dovetail slots, R188 "
        "bearing, thumb caps, and identical short colour-block arms.</desc>",
        "<defs>",
        f'  <linearGradient id="coreGrad" x1="0" y1="0" x2="1" y2="1">',
        f'    <stop offset="0" stop-color="{CORE}"/>',
        f'    <stop offset="1" stop-color="{CORE_D}"/>',
        "  </linearGradient>",
        f'  <linearGradient id="armGrad" x1="0" y1="0" x2="1" y2="1">',
        f'    <stop offset="0" stop-color="{ARM_A}"/>',
        f'    <stop offset="1" stop-color="#2E6FA0"/>',
        "  </linearGradient>",
        f'  <linearGradient id="armWarm" x1="0" y1="0" x2="1" y2="1">',
        f'    <stop offset="0" stop-color="{ARM_B}"/>',
        f'    <stop offset="1" stop-color="#B84A20"/>',
        "  </linearGradient>",
        f'  <radialGradient id="spot" cx="35%" cy="30%" r="70%">',
        f'    <stop offset="0" stop-color="#1A2740"/>',
        f'    <stop offset="1" stop-color="{PAPER}"/>',
        "  </radialGradient>",
        f'  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">',
        '    <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.35"/>',
        "  </filter>",
        f'  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        f'    <path d="M 0 0 L 10 5 L 0 10 Z" fill="{MUTED}"/>',
        "  </marker>",
        "</defs>",
        f'<rect width="{W}" height="{H}" fill="url(#spot)"/>',
    ]


def panel(x: float, y: float, w: float, h: float, title: str) -> list[str]:
    return [
        f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="14" '
        f'fill="{PANEL}" stroke="{HAIR}" stroke-width="1.2"/>',
        f'<text x="{n(x + 18)}" y="{n(y + 28)}" fill="{MUTED}" '
        f'font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="12" '
        f'font-weight="600" letter-spacing="1.5">{title.upper()}</text>',
    ]


def label(x: float, y: float, text: str, *, size: float = 12, fill: str = MUTED) -> str:
    return (
        f'<text x="{n(x)}" y="{n(y)}" fill="{fill}" '
        f'font-family="IBM Plex Sans, Segoe UI, sans-serif" font-size="{n(size)}">{text}</text>'
    )


def dim_line(x1: float, y1: float, x2: float, y2: float, text: str, *, above: bool = True) -> list[str]:
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ty = my - 8 if above else my + 14
    return [
        f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" '
        f'stroke="{ACCENT}" stroke-width="1"/>',
        f'<circle cx="{n(x1)}" cy="{n(y1)}" r="2" fill="{ACCENT}"/>',
        f'<circle cx="{n(x2)}" cy="{n(y2)}" r="2" fill="{ACCENT}"/>',
        label(mx, ty, text, size=11, fill=ACCENT_SOFT),
    ]


# --------------------------------------------------------------------------
# Geometry helpers — top view spinner
# --------------------------------------------------------------------------

def dovetail_male_2d(cx: float, cy: float, angle_deg: float, scale: float = 1.0) -> str:
    """Male dovetail + arm petal in top view, rotated around centre."""
    a = math.radians(angle_deg)
    # Local points: dovetail root near core, short rounded block outward.
    local = [
        (14.5, -3.5),
        (19, -5.5),
        (20, -7),
        (31, -7),
        (35, -5),
        (37, 0),
        (35, 5),
        (31, 7),
        (20, 7),
        (19, 5.5),
        (14.5, 3.5),
    ]
    pts = []
    for lx, ly in local:
        lx *= scale
        ly *= scale
        x = cx + (lx * math.cos(a) - ly * math.sin(a))
        y = cy + (lx * math.sin(a) + ly * math.cos(a))
        pts.append(f"{n(x)},{n(y)}")
    return " ".join(pts)


def core_slot_cut(cx: float, cy: float, angle_deg: float, r_in: float = 9.5, r_out: float = 15) -> str:
    a = math.radians(angle_deg)
    # Female dovetail mouth (simplified top view notch)
    half = math.radians(14)
    pts = []
    for t in (a - half, a - half * 0.55, a, a + half * 0.55, a + half):
        r = r_out if abs(t - a) < half * 0.4 else r_in
        # flare: middle deeper
        if abs(t - a) < 0.02:
            r = r_out
        elif abs(t - a) < half * 0.7:
            r = r_in + 2.2
        else:
            r = r_in
        pts.append(f"{n(cx + r * math.cos(t))},{n(cy + r * math.sin(t))}")
    # close with outer arc back
    return " ".join(pts)


def draw_assembled_top(cx: float, cy: float, s: float) -> list[str]:
    out: list[str] = []
    # Arms under / around core
    # An assembled spinner always uses a mass-matched arm set. Module variants
    # are shown separately below rather than implying that arbitrary arms mix.
    colors = ["url(#armGrad)", "url(#armWarm)", ARM_C, ARM_D, ARM_E]
    angles = (270, 342, 54, 126, 198)
    for i, ang in enumerate(angles):
        fill = colors[i % 3]
        out.append(
            f'<polygon points="{dovetail_male_2d(cx, cy, ang, s / 40)}" '
            f'fill="{fill}" stroke="{INK}" stroke-width="0.8" opacity="0.95" filter="url(#soft)"/>'
        )
    # Core disc
    r = 20 * (s / 40)
    out.append(
        f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="url(#coreGrad)" '
        f'stroke="{INK}" stroke-width="1.2" filter="url(#soft)"/>'
    )
    # Slot accents
    for ang in angles:
        a = math.radians(ang)
        x1 = cx + 14.5 * (s / 40) * math.cos(a)
        y1 = cy + 14.5 * (s / 40) * math.sin(a)
        x2 = cx + 19.8 * (s / 40) * math.cos(a)
        y2 = cy + 19.8 * (s / 40) * math.sin(a)
        out.append(
            f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" '
            f'stroke="{PAPER}" stroke-width="3.5" stroke-linecap="round" opacity="0.35"/>'
        )
    # Bearing
    br = 6.35 * (s / 40)
    ir = 3.175 * (s / 40)
    out.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(br)}" fill="{STEEL}" stroke="{STEEL_D}" stroke-width="1"/>')
    out.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(ir)}" fill="{PANEL}" stroke="{STEEL_D}" stroke-width="0.8"/>')
    # Ø20 top thumb cap; it covers the smaller R188 in the assembled product.
    cap_r = 10 * (s / 40)
    out.append(
        f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(cap_r)}" fill="{ACCENT}" '
        f'stroke="{ACCENT_SOFT}" stroke-width="1.2" filter="url(#soft)"/>'
    )
    out.append(f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(cap_r * 0.68)}" fill="none" stroke="{PANEL}" stroke-width="1" opacity="0.35"/>')
    return out


def draw_exploded(cx: float, cy: float) -> list[str]:
    out: list[str] = []
    # Through-bore receiver hub and removable pad — top.
    out.append(f'<ellipse cx="{n(cx)}" cy="{n(cy - 150)}" rx="28" ry="8" fill="{ACCENT}" opacity="0.95"/>')
    out.append(
        f'<ellipse cx="{n(cx)}" cy="{n(cy - 150)}" rx="7" ry="3" '
        f'fill="{PANEL}" stroke="{OK}" stroke-width="0.8"/>'
    )
    out.append(label(cx + 36, cy - 146, "Tough+ through-bore receiver", size=11))

    # Bearing
    out.append(f'<ellipse cx="{n(cx)}" cy="{n(cy - 100)}" rx="20" ry="7" fill="{STEEL}"/>')
    out.append(f'<ellipse cx="{n(cx)}" cy="{n(cy - 93)}" rx="20" ry="7" fill="{STEEL_D}"/>')
    out.append(f'<ellipse cx="{n(cx)}" cy="{n(cy - 100)}" rx="10" ry="3.5" fill="{PANEL}"/>')
    out.append(label(cx + 30, cy - 95, "R188 bearing", size=11))

    # Core
    out.append(
        f'<ellipse cx="{n(cx)}" cy="{n(cy - 40)}" rx="48" ry="16" fill="url(#coreGrad)" '
        f'stroke="{INK}" stroke-width="1" filter="url(#soft)"/>'
    )
    out.append(
        f'<ellipse cx="{n(cx)}" cy="{n(cy - 25)}" rx="48" ry="16" fill="{CORE_D}" '
        f'stroke="{INK}" stroke-width="1"/>'
    )
    for dx in (-48, 48):
        out.append(
            f'<rect x="{n(cx + dx - 6)}" y="{n(cy - 47)}" width="12" height="28" rx="2" '
            f'fill="{PAPER}" opacity="0.45"/>'
        )
    out.append(
        f'<rect x="{n(cx - 6)}" y="{n(cy - 60)}" width="12" height="20" rx="2" '
        f'fill="{PAPER}" opacity="0.45"/>'
    )
    out.append(label(cx + 58, cy - 30, "core · 5× Lok slots", size=11))

    # Identical colour blocks flying out; three shown to keep the stack legible.
    arm_specs = [
        (cx - 130, cy + 35, "url(#armGrad)", "colour block"),
        (cx, cy + 50, "url(#armWarm)", "same geometry"),
        (cx + 130, cy + 35, ARM_C, "five total"),
    ]
    for ax, ay, fill, name in arm_specs:
        out.append(
            f'<path d="M {n(ax - 14)} {n(ay)} L {n(ax - 6)} {n(ay - 10)} L {n(ax + 6)} {n(ay - 10)} '
            f'L {n(ax + 14)} {n(ay)} L {n(ax + 18)} {n(ay + 8)} '
            f'Q {n(ax)} {n(ay + 48)} {n(ax - 18)} {n(ay + 8)} Z" '
            f'fill="{fill}" stroke="{INK}" stroke-width="0.8" filter="url(#soft)"/>'
        )
        out.append(
            f'<path d="M {n(ax - 8)} {n(ay - 10)} L {n(ax - 11)} {n(ay - 22)} '
            f'L {n(ax + 11)} {n(ay - 22)} L {n(ax + 8)} {n(ay - 10)} Z" '
            f'fill="{STEEL_D}" stroke="{INK}" stroke-width="0.6"/>'
        )
        out.append(label(ax - 28, ay + 62, name, size=11))

    # Split-collet hub and integrated spacer from bottom.
    out.append(
        f'<rect x="{n(cx - 6)}" y="{n(cy + 95)}" width="12" height="55" rx="3" '
        f'fill="{ACCENT_SOFT}" stroke="{ACCENT}" stroke-width="0.8"/>'
    )
    for dx in (-4.5, -1.5, 1.5, 4.5):
        out.append(
            f'<line x1="{n(cx + dx)}" y1="{n(cy + 82)}" x2="{n(cx + dx)}" y2="{n(cy + 105)}" '
            f'stroke="{OK}" stroke-width="2" stroke-linecap="round"/>'
        )
    out.append(f'<ellipse cx="{n(cx)}" cy="{n(cy + 150)}" rx="28" ry="8" fill="{ACCENT}" opacity="0.95"/>')
    out.append(label(cx + 36, cy + 170, "Tough+ split-collet hub", size=11))
    out.append(label(cx + 36, cy + 186, "Ø6.40 axle · 4 fingers", size=10, fill=OK))

    # Stack guides — continuous axle path
    out.append(
        f'<line x1="{n(cx)}" y1="{n(cy - 143)}" x2="{n(cx)}" y2="{n(cy + 95)}" '
        f'stroke="{OK}" stroke-width="1.2" stroke-dasharray="3 4" opacity="0.65"/>'
    )
    out.append(label(cx - 110, cy - 70, "printed axle through R188", size=10, fill=OK))
    return out


def draw_joint_section(ox: float, oy: float) -> list[str]:
    """Cross-section of radial dovetail plus the paired Pinch-Lok release."""
    out: list[str] = []
    # Core body (left)
    out.append(
        f'<path d="M {n(ox)} {n(oy)} L {n(ox + 70)} {n(oy)} L {n(ox + 70)} {n(oy + 20)} '
        f'L {n(ox + 52)} {n(oy + 20)} L {n(ox + 58)} {n(oy + 55)} L {n(ox + 42)} {n(oy + 90)} '
        f'L {n(ox + 70)} {n(oy + 90)} L {n(ox + 70)} {n(oy + 110)} L {n(ox)} {n(oy + 110)} Z" '
        f'fill="url(#coreGrad)" stroke="{INK}" stroke-width="1"/>'
    )
    # Female dovetail void edge highlight
    out.append(
        f'<path d="M {n(ox + 70)} {n(oy + 20)} L {n(ox + 52)} {n(oy + 20)} '
        f'L {n(ox + 58)} {n(oy + 55)} L {n(ox + 42)} {n(oy + 90)} L {n(ox + 70)} {n(oy + 90)}" '
        f'fill="none" stroke="{ACCENT}" stroke-width="2"/>'
    )
    # Arm male
    out.append(
        f'<path d="M {n(ox + 72)} {n(oy + 22)} L {n(ox + 54)} {n(oy + 22)} '
        f'L {n(ox + 60)} {n(oy + 55)} L {n(ox + 46)} {n(oy + 88)} L {n(ox + 72)} {n(oy + 88)} '
        f'L {n(ox + 160)} {n(oy + 95)} L {n(ox + 175)} {n(oy + 55)} '
        f'L {n(ox + 160)} {n(oy + 15)} Z" '
        f'fill="url(#armWarm)" stroke="{INK}" stroke-width="1" filter="url(#soft)"/>'
    )
    # One of the paired axial-retention barbs, shown in section.
    out.append(
        f'<path d="M {n(ox + 58)} {n(oy + 48)} L {n(ox + 68)} {n(oy + 52)} '
        f'L {n(ox + 58)} {n(oy + 58)} Z" fill="{OK}" stroke="{INK}" stroke-width="0.5"/>'
    )
    out.append(
        f'<circle cx="{n(ox + 64)}" cy="{n(oy + 36)}" r="3" fill="none" '
        f'stroke="{OK}" stroke-width="1.2"/>'
    )
    out.append(label(ox + 72, oy + 32, "paired barbs · one shown", size=11, fill=OK))

    # Callouts
    out += [
        f'<line x1="{n(ox + 50)}" y1="{n(oy + 18)}" x2="{n(ox + 30)}" y2="{n(oy - 8)}" '
        f'stroke="{ACCENT}" stroke-width="1"/>',
        label(ox + 8, oy - 12, "drop-in from top", size=11, fill=ACCENT_SOFT),
        f'<line x1="{n(ox + 48)}" y1="{n(oy + 90)}" x2="{n(ox + 20)}" y2="{n(oy + 125)}" '
        f'stroke="{ACCENT}" stroke-width="1"/>',
        label(ox + 8, oy + 140, "radial capture — cannot fly out", size=11, fill=ACCENT_SOFT),
        f'<path d="M {n(ox + 130)} {n(oy + 70)} L {n(ox + 200)} {n(oy + 70)}" '
        f'stroke="{MUTED}" stroke-width="1.5" marker-end="url(#arrow)"/>',
        label(ox + 132, oy + 64, "centrifugal load →", size=11),
    ]

    # Pinch-release inset, viewed from above.
    ix, iy = ox + 240, oy + 20
    out.append(
        f'<rect x="{n(ix)}" y="{n(iy)}" width="220" height="165" rx="10" '
        f'fill="{PAPER}" stroke="{HAIR}"/>'
    )
    out.append(label(ix + 12, iy + 22, "PINCH-LOK RELEASE", size=11, fill=INK))
    out.append(
        f'<rect x="{n(ix + 55)}" y="{n(iy + 50)}" width="110" height="58" rx="14" '
        f'fill="url(#armWarm)" stroke="{INK}" stroke-width="1"/>'
    )
    # Flexure isolation slots and textured squeeze pads.
    out.append(f'<line x1="{n(ix + 75)}" y1="{n(iy + 55)}" x2="{n(ix + 75)}" y2="{n(iy + 103)}" stroke="{PANEL}" stroke-width="3"/>')
    out.append(f'<line x1="{n(ix + 145)}" y1="{n(iy + 55)}" x2="{n(ix + 145)}" y2="{n(iy + 103)}" stroke="{PANEL}" stroke-width="3"/>')
    out.append(f'<rect x="{n(ix + 49)}" y="{n(iy + 66)}" width="12" height="26" rx="4" fill="{ACCENT_SOFT}"/>')
    out.append(f'<rect x="{n(ix + 159)}" y="{n(iy + 66)}" width="12" height="26" rx="4" fill="{ACCENT_SOFT}"/>')
    out.append(f'<path d="M {n(ix + 15)} {n(iy + 79)} L {n(ix + 48)} {n(iy + 79)}" stroke="{OK}" stroke-width="2" marker-end="url(#arrow)"/>')
    out.append(f'<path d="M {n(ix + 205)} {n(iy + 79)} L {n(ix + 172)} {n(iy + 79)}" stroke="{OK}" stroke-width="2" marker-end="url(#arrow)"/>')
    out.append(label(ix + 82, iy + 44, "SQUEEZE", size=11, fill=OK))
    out.append(label(ix + 60, iy + 130, "squeeze + lift ↑", size=13, fill=ACCENT_SOFT))
    out.append(label(ix + 32, iy + 150, "squeeze alone cannot eject", size=10, fill=MUTED))

    # Legend box
    out.append(
        f'<rect x="{n(ox)}" y="{n(oy + 155)}" width="210" height="52" rx="8" '
        f'fill="{PAPER}" stroke="{HAIR}"/>'
    )
    out.append(label(ox + 12, oy + 175, "press down → paired barbs click", size=11, fill=INK))
    out.append(label(ox + 12, oy + 193, "pinch both sides + lift to remove", size=11, fill=MUTED))
    return out


def draw_solid_infill_blocks(ox: float, oy: float) -> list[str]:
    out: list[str] = []
    colours = (ARM_A, ARM_B, ARM_C, "#5DDBA0", "#A98BF3")
    for i, color in enumerate(colours):
        x = ox + i * 132
        out.append(
            f'<rect x="{n(x)}" y="{n(oy)}" width="116" height="168" rx="10" '
            f'fill="{PANEL}" stroke="{HAIR}"/>'
        )
        out.append(label(x + 12, oy + 24, f"BLOCK {i + 1}", size=13, fill=INK))
        out.append(label(x + 12, oy + 42, "100% infill", size=11, fill=OK))
        out.append(
            f'<rect x="{n(x + 30)}" y="{n(oy + 58)}" width="56" height="84" rx="8" '
            f'fill="{color}" opacity="0.82" stroke="{color}" stroke-width="1.5"/>'
        )
        for y_offset in range(66, 138, 8):
            out.append(
                f'<line x1="{n(x + 34)}" y1="{n(oy + y_offset)}" '
                f'x2="{n(x + 82)}" y2="{n(oy + y_offset)}" '
                f'stroke="{PAPER}" stroke-width="1" opacity="0.55"/>'
            )
        out.append(label(x + 18, oy + 158, "same geometry", size=10, fill=MUTED))
    return out


def draw_bearing_stack(ox: float, oy: float) -> list[str]:
    out: list[str] = []
    # Top pad, through-bore receiver and exposed releasable collet tips.
    out.append(f'<rect x="{n(ox + 30)}" y="{n(oy)}" width="100" height="12" rx="4" fill="{ACCENT}"/>')
    out.append(f'<rect x="{n(ox + 68)}" y="{n(oy + 12)}" width="24" height="20" rx="3" fill="{ACCENT_SOFT}"/>')
    for x in (74, 78, 82, 86):
        out.append(f'<rect x="{n(ox + x)}" y="{n(oy + 2)}" width="2" height="12" rx="1" fill="{OK}"/>')
    out.append(label(ox + 136, oy + 12, "receiver + exposed fingers", size=11, fill=ACCENT_SOFT))

    # Air gap top
    out.append(
        f'<rect x="{n(ox + 22)}" y="{n(oy + 24)}" width="116" height="4" fill="none" '
        f'stroke="{OK}" stroke-width="1" stroke-dasharray="2 2"/>'
    )
    out.append(label(ox + 136, oy + 26, "1.6 mm gap", size=11, fill=OK))

    # Core and R188. Tough+ bosses contact only the inner race.
    out.append(f'<rect x="{n(ox)}" y="{n(oy + 28)}" width="160" height="52" rx="4" fill="url(#coreGrad)"/>')
    out.append(f'<rect x="{n(ox + 50)}" y="{n(oy + 32)}" width="60" height="44" rx="2" fill="{STEEL}"/>')
    out.append(f'<rect x="{n(ox + 68)}" y="{n(oy + 32)}" width="24" height="44" fill="{STEEL_D}"/>')
    out.append(f'<rect x="{n(ox + 72)}" y="{n(oy + 30)}" width="16" height="48" rx="2" fill="{ACCENT_SOFT}" stroke="{ACCENT}"/>')
    out.append(f'<rect x="{n(ox + 76)}" y="{n(oy + 4)}" width="8" height="100" rx="2" fill="{OK}" stroke="{ACCENT_SOFT}"/>')
    # Shoulder below and removable three-lug retainer represented in section above.
    out.append(f'<rect x="{n(ox + 46)}" y="{n(oy + 72)}" width="22" height="8" fill="{CORE_D}"/>')
    out.append(f'<rect x="{n(ox + 92)}" y="{n(oy + 72)}" width="22" height="8" fill="{CORE_D}"/>')
    out.append(f'<rect x="{n(ox + 46)}" y="{n(oy + 28)}" width="12" height="8" rx="2" fill="{OK}"/>')
    out.append(f'<rect x="{n(ox + 102)}" y="{n(oy + 28)}" width="12" height="8" rx="2" fill="{OK}"/>')
    out.append(label(ox + 136, oy + 52, "Ø6.40 printed axle", size=11, fill=ACCENT_SOFT))
    out.append(label(ox + 136, oy + 69, "shoulder + press ring", size=10, fill=OK))

    # Air gap bottom + split-collet hub.
    out.append(
        f'<rect x="{n(ox + 22)}" y="{n(oy + 82)}" width="116" height="4" fill="none" '
        f'stroke="{OK}" stroke-width="1" stroke-dasharray="2 2"/>'
    )
    out.append(f'<rect x="{n(ox + 68)}" y="{n(oy + 80)}" width="24" height="16" rx="3" fill="{ACCENT_SOFT}"/>')
    out.append(f'<rect x="{n(ox + 30)}" y="{n(oy + 96)}" width="100" height="12" rx="4" fill="{ACCENT}"/>')
    out.append(label(ox + 136, oy + 104, "Tough+ split-collet hub", size=11, fill=ACCENT_SOFT))

    rows = [
        (oy + 130, "hardware", "R188 only"),
        (oy + 150, "axle → inner race", "Ø6.40 / 0.05 press"),
        (oy + 170, "retention bead", "Ø6.80 · 4 fingers"),
        (oy + 190, "caps ↛ core", "1.6 mm gaps"),
        (oy + 210, "service", "pinch tips to release"),
    ]
    for y, a, b in rows:
        out.append(label(ox, y, a, size=12, fill=INK))
        out.append(label(ox + 118, y, b, size=12, fill=ACCENT_SOFT))
    return out


def build() -> str:
    parts: list[str] = []
    parts += svg_header()

    # Title block
    parts.append(label(48, 48, "OGGIE SPIN", size=34, fill=INK))
    parts.append(
        label(
            48,
            72,
            "Lok Core platform  ·  5 colour-swap blocks  ·  R188  ·  no glue",
            size=14,
            fill=MUTED,
        )
    )
    parts.append(
        f'<rect x="48" y="84" width="72" height="4" rx="2" fill="{ACCENT}"/>'
    )

    # Panel 1 — assembled top
    parts += panel(40, 110, 420, 460, "01  assembled · top")
    parts += draw_assembled_top(250, 340, 155)
    parts.append(label(60, 530, "5 identical blocks @ 72°  ·  colour-mix freely  ·  balanced geometry", size=12))
    parts += dim_line(250 - 143, 490, 250 + 143, 490, "tip Ø ~74 mm", above=False)

    # Panel 2 — exploded
    parts += panel(480, 110, 520, 460, "02  explode · lego stack")
    parts += draw_exploded(740, 300)

    # Panel 3 — joint
    parts += panel(1020, 110, 540, 460, "03  pinch-lok · top-down")
    parts += draw_joint_section(1060, 160)

    # Panel 4 — solid-infill, mass-matched colour blocks.
    parts += panel(40, 590, 760, 470, "04  mass-matched arms · slicer weighted")
    parts += draw_solid_infill_blocks(70, 640)
    parts.append(label(70, 1020, "No weight pods · identical geometry + 100% grid infill across all five.", size=12))

    # Panel 5 — bearing
    parts += panel(820, 590, 420, 470, "05  bearing stack")
    parts += draw_bearing_stack(860, 650)

    # Panel 6 — notes
    parts += panel(1260, 590, 300, 470, "06  decisions")
    notes = [
        "• Top-down block→core",
        "• Pinch + lift release",
        "• Tough+ split-collet axle",
        "• R188 is only hardware",
        "• Dovetail captures radially",
        "• Caps never rub core",
        "• R188 default; 608 optional",
        "• Shoulder + bayonet ring",
        "• 5 identical blocks @ 72°",
        "• Colour mixing is unrestricted",
    ]
    for i, line in enumerate(notes):
        parts.append(label(1280, 640 + i * 29, line, size=13, fill=INK))
    parts.append(label(1280, 940, "100% infill matched ×5", size=12, fill=OK))
    parts.append(label(1280, 980, "next: collet + life coupons", size=12, fill=ACCENT_SOFT))

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build(), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
