"""Generate the 2D concept sheet for the Bouclé Stack table lamp.

The lamp is a stack of three shells of revolution. Each shell is cut by an
oblique plane; the next shell's axis is the normal of that plane, so the stack
zig-zags. Every shell therefore prints with its own base plane flat on the bed
and needs no supports — the lean only happens at assembly.

All model units are millimetres. World coordinates are (x, z) in a front
elevation: +x to the right, +z up, projection along -y.

Run from the repository root:

    python3 scripts/generate_lamp_concept_svg.py
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR_DIR = ROOT / "backend" / "generator"
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

from boucle_lamp_config import (  # noqa: E402
    CRADLE_DIA,
    CRADLE_FLANGE_DIA,
    CRADLE_FLANGE_H,
    CRADLE_Z0,
    CRADLE_Z1,
    HALO_GAP,
    LEG_COUNT,
    LEG_FOOT_DIA,
    LEG_FOOT_R,
    LEG_TOP_DIA,
    LEG_TOP_R,
    LED_CABLE_H,
    LED_CABLE_W,
    LED_DIA,
    LED_HEIGHT,
    LED_POCKET_DEPTH,
    LED_POCKET_DIA,
    LED_TAPE_DIA,
    PLINTH_OD,
    PLINTH_CABLE_CLEARANCE,
    PLINTH_TOP_SEAT_H,
    PLINTH_TOP_SEAT_OD,
    PLINTH_Z0,
    PLINTH_Z1,
    SHELL_A_SEAT_GROOVE_DEPTH,
    SHELL_A_SEAT_RADIAL_CLEARANCE,
    RING_RECESS,
    Shell,
    build_stack,
    overall_height,
    widest_diameter,
)

DEFAULT_OUT = ROOT / "design" / "boucle-stack-lamp" / "boucle-stack-lamp-concept.svg"

# --------------------------------------------------------------------------
# SVG plumbing
# --------------------------------------------------------------------------

W, H = 1600, 1100

PAPER = "#F6F3EE"
PANEL = "#FFFFFF"
INK = "#211D18"
MUTED = "#7A7367"
HAIR = "#DCD5C9"
ACCENT = "#C0632A"
GLOW = "#FFC06B"
IVORY = "#EFE9DC"
IVORY_D = "#C6BBA8"
CHOC = "#4D3324"
CHOC_L = "#6A4A36"


def n(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


class View:
    """Maps model millimetres onto sheet pixels."""

    def __init__(self, cx: float, base_y: float, scale: float):
        self.cx, self.base_y, self.scale = cx, base_y, scale

    def __call__(self, p):
        return (self.cx + p[0] * self.scale, self.base_y - p[1] * self.scale)

    def x(self, mx: float) -> float:
        return self.cx + mx * self.scale

    def y(self, mz: float) -> float:
        return self.base_y - mz * self.scale


def path_of(view: View, pts, close=True) -> str:
    d = []
    for i, p in enumerate(pts):
        sx, sy = view(p)
        d.append(f"{'M' if i == 0 else 'L'}{sx:.1f},{sy:.1f}")
    if close:
        d.append("Z")
    return "".join(d)


def card(x, y, w, h, title, radius=10):
    return (
        f'<rect class="card" x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}"/>'
        f'<text class="cardtitle" x="{x + 18}" y="{y + 25}">{title}</text>'
    )


def dim_v(x, y0, y1, text, side="left", tick=5):
    ty = (y0 + y1) / 2
    anchor = "end" if side == "left" else "start"
    tx = x - 8 if side == "left" else x + 8
    return (
        f'<path class="dim" d="M{x:.1f},{y0:.1f} L{x:.1f},{y1:.1f}" marker-start="url(#arrow)" marker-end="url(#arrow)"/>'
        f'<path class="dimtick" d="M{x - tick:.1f},{y0:.1f} L{x + tick:.1f},{y0:.1f} '
        f'M{x - tick:.1f},{y1:.1f} L{x + tick:.1f},{y1:.1f}"/>'
        f'<text class="dimtext" x="{tx:.1f}" y="{ty + 4:.1f}" text-anchor="{anchor}">{text}</text>'
    )


def dim_h(y, x0, x1, text, above=True, tick=5):
    tx = (x0 + x1) / 2
    ty = y - 7 if above else y + 15
    return (
        f'<path class="dim" d="M{x0:.1f},{y:.1f} L{x1:.1f},{y:.1f}" marker-start="url(#arrow)" marker-end="url(#arrow)"/>'
        f'<path class="dimtick" d="M{x0:.1f},{y - tick:.1f} L{x0:.1f},{y + tick:.1f} '
        f'M{x1:.1f},{y - tick:.1f} L{x1:.1f},{y + tick:.1f}"/>'
        f'<text class="dimtext" x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle">{text}</text>'
    )


def leader(x0, y0, x1, y1, text, anchor="start"):
    dx = 9 if anchor == "start" else -9
    return (
        f'<path class="lead" d="M{x0:.1f},{y0:.1f} L{x1:.1f},{y1:.1f}" marker-start="url(#dot)"/>'
        f'<text class="leadtext" x="{x1 + dx:.1f}" y="{y1 + 4:.1f}" text-anchor="{anchor}">{text}</text>'
    )


# --------------------------------------------------------------------------
# Base geometry (elevation)
# --------------------------------------------------------------------------


def leg_quads():
    out = []
    for i in range(LEG_COUNT):
        az = math.radians(30 + i * 120)
        out.append((LEG_FOOT_R * math.cos(az), LEG_TOP_R * math.cos(az), math.sin(az)))
    out.sort(key=lambda t: t[2], reverse=True)
    return out


def draw_base(view: View, glow=False) -> str:
    s = []
    for xf, xt, depth in leg_quads():
        back = depth > 0.2
        fill = CHOC_L if back else CHOC
        op = 0.55 if back else 1.0
        hf, ht = LEG_FOOT_DIA / 2, LEG_TOP_DIA / 2
        pts = [
            (xf - hf, 0.0),
            (xt - ht, PLINTH_Z0 + 3),
            (xt + ht, PLINTH_Z0 + 3),
            (xf + hf, 0.0),
        ]
        s.append(f'<path d="{path_of(view, pts)}" fill="{fill}" opacity="{op}"/>')

    body_r = PLINTH_OD / 2
    seat_r = PLINTH_TOP_SEAT_OD / 2
    shoulder_z = PLINTH_Z1 - PLINTH_TOP_SEAT_H
    plinth = [
        (-PLINTH_OD / 2 + 2, PLINTH_Z0),
        (-body_r, PLINTH_Z0 + 4),
        (-body_r, shoulder_z),
        (-seat_r, shoulder_z),
        (-seat_r, PLINTH_Z1),
        (seat_r, PLINTH_Z1),
        (seat_r, shoulder_z),
        (body_r, shoulder_z),
        (body_r, PLINTH_Z0 + 4),
        (PLINTH_OD / 2 - 2, PLINTH_Z0),
    ]
    s.append(f'<path d="{path_of(view, plinth)}" fill="{CHOC}"/>')
    if glow:
        gx, gy = view((0, PLINTH_Z1))
        s.append(
            f'<ellipse cx="{gx:.1f}" cy="{gy:.1f}" rx="{CRADLE_DIA / 2 * view.scale:.1f}" '
            f'ry="{CRADLE_DIA / 5 * view.scale:.1f}" fill="url(#ledglow)"/>'
        )
    return "".join(s)


def cord_path(view: View) -> str:
    x0, y0 = view((PLINTH_OD / 2 - 8, PLINTH_Z0 + 4))
    return (
        f'<path class="cord" d="M{x0:.1f},{y0:.1f} '
        f'C{x0 + 24:.1f},{y0 + 30:.1f} {x0 + 6:.1f},{y0 + 62:.1f} {x0 + 56:.1f},{y0 + 70:.1f}"/>'
    )


def draw_shells(view: View, shells, lit=False) -> str:
    s = []
    body_grad = "url(#shelllit)" if lit else "url(#shellgrad)"
    for shell in shells:
        d = path_of(view, shell.outline())
        s.append(f'<path d="{d}" fill="{body_grad}"/>')
        s.append(f'<path d="{d}" fill="url(#boucle)" opacity="0.85"/>')
        s.append(f'<path d="{d}" fill="none" stroke="{IVORY_D}" stroke-width="1.1"/>')
        rl, rr = view(shell.rim_l), view(shell.rim_r)
        s.append(f'<path class="rim" d="M{rl[0]:.1f},{rl[1]:.1f} L{rr[0]:.1f},{rr[1]:.1f}"/>')

    for lower, upper in zip(shells, shells[1:]):
        a, b = view(lower.rim_l), view(lower.rim_r)
        c, d2 = view(upper.right[0]), view(upper.left[0])
        quad = (
            f'M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} '
            f'L{c[0]:.1f},{c[1]:.1f} L{d2[0]:.1f},{d2[1]:.1f} Z'
        )
        if lit:
            s.append(f'<path d="{quad}" fill="url(#halograd)"/>')
        else:
            s.append(f'<path d="{quad}" fill="#FFF3DC" stroke="{ACCENT}" stroke-width="0.8" opacity="0.95"/>')
    return "".join(s)


# --------------------------------------------------------------------------
# Panels
# --------------------------------------------------------------------------


def panel_elevation(shells) -> str:
    X, Y, WI, HI = 40, 96, 452, 604
    view = View(cx=X + WI / 2 + 4, base_y=Y + 552, scale=2.0)
    s = [card(X, Y, WI, HI, "1 · FRONT ELEVATION — assembled, mm")]

    gy = view.y(0)
    s.append(f'<path class="ground" d="M{view.x(-92):.1f},{gy:.1f} L{view.x(92):.1f},{gy:.1f}"/>')
    s.append(f'<path class="axis" d="M{view.x(0):.1f},{view.y(-8):.1f} L{view.x(0):.1f},{view.y(258):.1f}"/>')
    s.append(cord_path(view))
    s.append(draw_base(view))
    s.append(draw_shells(view, shells))

    top = overall_height(shells)
    widest = widest_diameter(shells)
    wz = next(sh.max_radius_z for sh in shells if sh.max_radius * 2 == widest)

    s.append(dim_v(X + 28, view.y(top), view.y(0), n(top)))
    s.append(dim_v(X + 58, view.y(PLINTH_Z1), view.y(0), n(PLINTH_Z1)))
    s.append(dim_h(view.y(0) + 20, view.x(-LEG_FOOT_R), view.x(LEG_FOOT_R), f"Ø{n(LEG_FOOT_R * 2)} feet"))
    s.append(dim_h(view.y(wz), view.x(-widest / 2), view.x(widest / 2), f"Ø{n(widest)}"))

    for shell in shells:
        mx, my = view(shell.rim_mid)
        s.append(leader(mx, my, X + WI - 104, my, shell.label))
    jx, jy = view(shells[0].rim_mid)
    s.append(leader(jx * 0.6 + view.x(0) * 0.4, jy, X + WI - 104, jy + 34, f"{n(HALO_GAP)} halo slot ×2"))
    s.append(leader(view.x(0), view.y(PLINTH_Z0 + 12), X + WI - 104, view.y(46), "LED kit in plinth"))
    s.append(
        f'<text class="note" x="{X + 18}" y="{Y + HI - 12}">Axis lean alternates ±12° · rims are straight in true '
        f'elevation, the openings are ellipses</text>'
    )
    return "".join(s)


def panel_impression(shells) -> str:
    X, Y, WI, HI = 508, 96, 340, 604
    view = View(cx=X + WI / 2, base_y=Y + 552, scale=1.66)
    s = [card(X, Y, WI, HI, "2 · 3/4 IMPRESSION — lit")]
    s.append(f'<rect x="{X + 12}" y="{Y + 38}" width="{WI - 24}" height="{HI - 62}" rx="8" fill="url(#roomgrad)"/>')
    s.append(f'<clipPath id="impclip"><rect x="{X + 12}" y="{Y + 38}" width="{WI - 24}" height="{HI - 62}" rx="8"/></clipPath>')
    s.append('<g clip-path="url(#impclip)">')

    squash = 0.28

    def ellipse(pl, pr):
        """Screen ellipse for a rim seen slightly from above."""
        rx = math.hypot(pr[0] - pl[0], pr[1] - pl[1]) / 2
        return {
            "cx": (pl[0] + pr[0]) / 2,
            "cy": (pl[1] + pr[1]) / 2,
            "rx": rx,
            "ry": rx * squash,
            "rot": math.degrees(math.atan2(pr[1] - pl[1], pr[0] - pl[0])),
            "l": pl,
            "r": pr,
        }

    def arc_to(e, target, sweep):
        return f'A{e["rx"]:.1f},{e["ry"]:.1f} {e["rot"]:.2f} 0 {sweep} {target[0]:.1f},{target[1]:.1f}'

    s.append(draw_base(view, glow=True))
    s.append(cord_path(view))

    # Painter's algorithm: work up the stack so each shell occludes the joint
    # below it, otherwise the halo bands smear across the shell above.
    for i, shell in enumerate(shells):
        if i:
            lower = shells[i - 1]
            e1 = ellipse(view(lower.rim_l), view(lower.rim_r))
            e2 = ellipse(view(shell.left[0]), view(shell.right[0]))
            s.append(
                f'<path d="M{e1["l"][0]:.1f},{e1["l"][1]:.1f} {arc_to(e1, e1["r"], 1)} '
                f'L{e2["r"][0]:.1f},{e2["r"][1]:.1f} {arc_to(e2, e2["l"], 0)} Z" fill="url(#halograd)"/>'
            )
        e = ellipse(view(shell.rim_l), view(shell.rim_r))
        s.append(
            f'<ellipse cx="{e["cx"]:.1f}" cy="{e["cy"]:.1f}" rx="{e["rx"]:.1f}" ry="{e["ry"]:.1f}" '
            f'transform="rotate({e["rot"]:.2f} {e["cx"]:.1f} {e["cy"]:.1f})" fill="url(#interiorlit)"/>'
        )
        body = path_of(view, shell.outline(), close=False)
        closed = f'{body} {arc_to(e, e["l"], 0)} Z'
        s.append(f'<path d="{closed}" fill="url(#shelllit)"/>')
        s.append(f'<path d="{closed}" fill="url(#boucle)" opacity="0.95"/>')
        s.append(f'<path d="{closed}" fill="none" stroke="#B5A895" stroke-width="0.7" opacity="0.7"/>')
    s.append("</g>")
    s.append(
        f'<text class="note" x="{X + 18}" y="{Y + HI - 14}">Warm white 3 W · walls glow through 1.2–1.6 mm matte PLA</text>'
    )
    return "".join(s)


def panel_materials() -> str:
    X, Y, WI, HI = 868, 96, 692, 146
    s = [card(X, Y, WI, HI, "3 · MATERIALS — Bambu PLA")]
    rows = [
        ("#CBC6B8", "Bone White", "PLA Matte", "Shells A / B / C and halo rings — the bouclé colour"),
        ("#FFFFFF", "Jade White", "PLA Basic", "Hidden 1.2 mm diffuser — higher transmission"),
        (CHOC, "Dark Chocolate", "matte-dark-chocolate", "Tripod leg frame + LED cradle — the walnut read"),
    ]
    for i, (hexv, name, fid, note) in enumerate(rows):
        yy = Y + 46 + i * 33
        s.append(f'<rect x="{X + 18}" y="{yy}" width="30" height="24" rx="4" fill="{hexv}" stroke="{HAIR}"/>')
        s.append(f'<text class="kv" x="{X + 58}" y="{yy + 11}">{name}</text>')
        s.append(f'<text class="kvs" x="{X + 58}" y="{yy + 22}">{fid} — {note}</text>')
    return "".join(s)


def kv_card(x, y, w, h, title, facts, kw=92) -> str:
    s = [card(x, y, w, h, title)]
    for i, (k, v) in enumerate(facts):
        yy = y + 52 + i * 27
        s.append(f'<text class="kvs" x="{x + 18}" y="{yy}">{k}</text>')
        s.append(f'<text class="kv" x="{x + 18 + kw}" y="{yy}">{v}</text>')
    return "".join(s)


def panel_hardware() -> str:
    facts = [
        ("Kit", "LED Lamp Kit-001 (MH001)"),
        ("Module", f"Ø{n(LED_DIA)} × {n(LED_HEIGHT)} mm, 58 g"),
        ("Power", "DC 5 V · 3 W · warm white"),
        ("Cable", "1.5 m USB, Ø3.6 mm"),
        ("Fixing", f"Ø{n(LED_TAPE_DIA)} tape; screw pattern TBD"),
        ("Pocket", f"Ø{n(LED_POCKET_DIA)} × {n(LED_POCKET_DEPTH)} deep"),
    ]
    return kv_card(868, 258, 338, 222, "4 · LED HARDWARE", facts, kw=78)


def panel_fuzzy() -> str:
    facts = [
        ("Mode", "Painted triangles, not modifier"),
        ("Thickness", "0.30 mm"),
        ("Point dist.", "0.80 mm"),
        ("First layer", "off"),
        ("Painted", "Outer wall of A / B / C"),
        ("Excluded", "4 mm rim bands, all interiors"),
    ]
    return kv_card(1222, 258, 338, 222, "5 · FUZZY SKIN — bouclé", facts, kw=82)


def panel_schedule(shells) -> str:
    X, Y, WI, HI = 868, 496, 692, 204
    s = [card(X, Y, WI, HI, "6 · SHELL SCHEDULE — resolved geometry")]
    head = ["Part", "Base Ø", "Widest Ø", "Rim Ø", "Wall low", "Wall high", "Lean", "Draft"]
    cols = [X + 18, X + 132, X + 208, X + 292, X + 366, X + 452, X + 546, X + 604]
    for c, t in zip(cols, head):
        s.append(f'<text class="th" x="{c}" y="{Y + 52}">{t}</text>')
    s.append(f'<path class="hair" d="M{X + 18},{Y + 60} L{X + WI - 18},{Y + 60}"/>')
    for i, sh in enumerate(shells):
        yy = Y + 82 + i * 26
        vals = [
            sh.label,
            n(sh.base_radius * 2),
            n(sh.max_radius * 2),
            n(sh.rim_half * 2),
            n(sh.short_side),
            n(sh.long_side),
            f"{n(sh.axis_deg)}°",
            f"{n(sh.as_printed().draft_deg)}°",
        ]
        for c, t in zip(cols, vals):
            s.append(f'<text class="td" x="{c}" y="{yy}">{t}</text>')
    s.append(
        f'<text class="note" x="{X + 18}" y="{Y + 176}">Wall low / high = axial height on the short and tall side. '
        f'Draft = worst outward overhang when printed base-down.</text>'
    )
    s.append(
        f'<text class="note" x="{X + 18}" y="{Y + 192}">Bases are inset {n(shells[1].base_inset)} / '
        f'{n(shells[2].base_inset)} mm inside the rim below — absorbs the ellipse-vs-circle mismatch '
        f'and sets the wide–narrow–wide rhythm.</text>'
    )
    return "".join(s)


def panel_base_section() -> str:
    X, Y, WI, HI = 40, 716, 452, 344
    view = View(cx=X + 168, base_y=Y + 288, scale=2.0)
    s = [card(X, Y, WI, HI, "7 · BASE SECTION — LED cradle")]

    s.append(draw_base(view))
    px0, px1 = view.x(-PLINTH_OD / 2), view.x(PLINTH_OD / 2)
    pz0 = view.y(PLINTH_Z0)
    shoulder_y = view.y(PLINTH_Z1 - PLINTH_TOP_SEAT_H)
    s.append(
        f'<rect x="{px0:.1f}" y="{shoulder_y:.1f}" width="{px1 - px0:.1f}" '
        f'height="{pz0 - shoulder_y:.1f}" fill="url(#cut)"/>'
    )
    seat_x0, seat_x1 = (
        view.x(-PLINTH_TOP_SEAT_OD / 2),
        view.x(PLINTH_TOP_SEAT_OD / 2),
    )
    seat_y = view.y(PLINTH_Z1)
    s.append(
        f'<rect x="{seat_x0:.1f}" y="{seat_y:.1f}" width="{seat_x1 - seat_x0:.1f}" '
        f'height="{shoulder_y - seat_y:.1f}" fill="url(#cut)"/>'
    )

    cx0 = view.x(-CRADLE_DIA / 2)
    cx1 = view.x(CRADLE_DIA / 2)
    s.append(
        f'<rect x="{cx0:.1f}" y="{view.y(CRADLE_Z1):.1f}" width="{cx1 - cx0:.1f}" '
        f'height="{(CRADLE_Z1 - CRADLE_Z0) * view.scale:.1f}" fill="{CHOC_L}" stroke="{INK}" stroke-width="0.8"/>'
    )
    flange_x0, flange_x1 = (
        view.x(-CRADLE_FLANGE_DIA / 2),
        view.x(CRADLE_FLANGE_DIA / 2),
    )
    s.append(
        f'<rect x="{flange_x0:.1f}" y="{view.y(CRADLE_Z1):.1f}" '
        f'width="{flange_x1 - flange_x0:.1f}" '
        f'height="{CRADLE_FLANGE_H * view.scale:.1f}" fill="{CHOC_L}" '
        f'stroke="{INK}" stroke-width="0.8"/>'
    )
    led_top = CRADLE_Z1 - 2.0
    lx0, lx1 = view.x(-LED_POCKET_DIA / 2), view.x(LED_POCKET_DIA / 2)
    s.append(
        f'<rect x="{lx0:.1f}" y="{view.y(led_top):.1f}" width="{lx1 - lx0:.1f}" '
        f'height="{LED_HEIGHT * view.scale:.1f}" fill="#2C2822" stroke="{ACCENT}" stroke-width="1.3"/>'
    )
    s.append(
        f'<rect x="{view.x(-LED_TAPE_DIA / 2):.1f}" y="{view.y(led_top) - 3:.1f}" '
        f'width="{LED_TAPE_DIA * view.scale:.1f}" height="4" fill="{GLOW}"/>'
    )
    s.append(
        f'<path class="cordthin" d="M{view.x(LED_POCKET_DIA / 2):.1f},{view.y(led_top - LED_HEIGHT + 5):.1f} '
        f'L{view.x(PLINTH_OD / 2 + 3):.1f},{view.y(led_top - LED_HEIGHT + 5):.1f}"/>'
    )
    s.append(f'<path class="seat" d="M{view.x(-56):.1f},{view.y(PLINTH_Z1):.1f} L{view.x(56):.1f},{view.y(PLINTH_Z1):.1f}"/>')

    s.append(dim_h(view.y(led_top) - 28, lx0, lx1, f"Ø{n(LED_POCKET_DIA)} LED pocket"))
    s.append(dim_v(view.x(-PLINTH_OD / 2) - 18, view.y(PLINTH_Z1), view.y(PLINTH_Z0), n(PLINTH_Z1 - PLINTH_Z0)))
    s.append(dim_h(view.y(0) + 18, view.x(-LEG_FOOT_R), view.x(LEG_FOOT_R), f"Ø{n(LEG_FOOT_R * 2)}"))
    s.append(
        leader(
            view.x(0),
            view.y(led_top) + 4,
            X + 344,
            Y + 64,
            f"Ø{n(LED_TAPE_DIA)} tape pad",
        )
    )
    s.append(
        f'<text class="leadtext" x="{X + 353}" y="{Y + 78}">'
        "no screw pilots until hardware is measured</text>"
    )
    s.append(leader(view.x(PLINTH_OD / 2), view.y(led_top - LED_HEIGHT + 5), X + 344, Y + 132, "open-top cable slot"))
    s.append(
        f'<text class="leadtext" x="{X + 353}" y="{Y + 146}">'
        f'{n(LED_CABLE_W + PLINTH_CABLE_CLEARANCE)} mm wide · centred between front legs</text>'
    )
    s.append(
        leader(
            view.x(-PLINTH_TOP_SEAT_OD / 2 + 2),
            view.y(PLINTH_Z1),
            X + 344,
            Y + 200,
            f"Ø{n(PLINTH_TOP_SEAT_OD)} seat + {n(SHELL_A_SEAT_GROOVE_DEPTH)} mm bond groove",
        )
    )
    s.append(
        f'<text class="leadtext" x="{X + 353}" y="{Y + 214}">'
        f"locates Shell A · ±{n(SHELL_A_SEAT_RADIAL_CLEARANCE)} mm</text>"
    )
    s.append(
        f'<text class="note" x="{X + 18}" y="{Y + HI - 14}">Bond Shell A into the seat groove · '
        f'cradle stays removable through its opening · USB stays outside</text>'
    )
    return "".join(s)


def panel_joint() -> str:
    X, Y, WI, HI = 508, 716, 340, 344
    s = [card(X, Y, WI, HI, "8 · JOINT DETAIL — halo ring, section")]
    ox, oy, k = X + 222, Y + 180, 5.2

    def P(mx, mz):
        return (ox + mx * k, oy - mz * k)

    def poly(pts, fill, stroke=INK, sw=0.9):
        d = " L".join(f"{P(*p)[0]:.1f},{P(*p)[1]:.1f}" for p in pts)
        return f'<path d="M{d} Z" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'

    gx0, gy0 = P(0.5, 0)
    gx1, gy1 = P(11, HALO_GAP)
    s.append(f'<rect x="{gx0:.1f}" y="{gy1:.1f}" width="{gx1 - gx0:.1f}" height="{gy0 - gy1:.1f}" fill="url(#slotglow)"/>')
    for dz in (-2.5, 1, 4.5):
        a, b = P(1, 2), P(17, 2 + dz)
        s.append(f'<path class="rayline" d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f}"/>')

    s.append(poly([(-1.4, -24), (0.2, -24), (2.8, 0), (1.2, 0)], IVORY))
    s.append(poly([(-0.9, 4), (0.7, 4), (-1.9, 28), (-3.5, 28)], IVORY))
    s.append(
        poly(
            [
                (-13, -19), (-13, 10), (-9.6, 10), (-9.6, 4), (-0.4, 4),
                (-0.4, 0), (-9.6, 0), (-9.6, -15), (0.4, -15), (0.4, -19),
            ],
            IVORY_D,
        )
    )

    s.append(dim_v(P(15.5, 0)[0], P(0, HALO_GAP)[1], P(0, 0)[1], n(HALO_GAP), side="right"))
    s.append(f'<text class="kvs" x="{P(6, 0)[0]:.1f}" y="{Y + 118}">light out →</text>')

    s.append(leader(*P(-0.6, 16), X + 150, Y + 62, "1.6 mm wall,", anchor="end"))
    s.append(f'<text class="leadtext" x="{X + 141}" y="{Y + 76}" text-anchor="end">fuzzy skin outside</text>')
    s.append(leader(*P(-11.3, -6), X + 150, Y + 126, "halo ring, bonded", anchor="end"))
    s.append(f'<text class="leadtext" x="{X + 141}" y="{Y + 140}" text-anchor="end">into shell below</text>')
    s.append(leader(*P(-5, 2), X + 150, Y + 190, "shoulder sets the", anchor="end"))
    s.append(f'<text class="leadtext" x="{X + 141}" y="{Y + 204}" text-anchor="end">gap · 0.25 mm slip fit</text>')
    s.append(leader(*P(-11.3, 9), X + 150, Y + 254, f"recessed {n(RING_RECESS)} mm —", anchor="end"))
    s.append(f'<text class="leadtext" x="{X + 141}" y="{Y + 268}" text-anchor="end">never visible outside</text>')
    s.append(f'<text class="kvs" x="{P(-13, 0)[0]:.1f}" y="{Y + 300}">interior</text>')
    s.append(f'<text class="kvs" x="{P(3, 0)[0]:.1f}" y="{Y + 300}">exterior</text>')
    s.append(
        f'<text class="note" x="{X + 18}" y="{Y + HI - 14}">Hidden tapered tab clocks the upper shell; adhesive carries the cantilever</text>'
    )
    return "".join(s)


def panel_plates(shells) -> str:
    X, Y, WI, HI = 868, 716, 692, 344
    s = [card(X, Y, WI, HI, "9 · EIGHT-PLATE PROJECT — P2S, one object each, no supports")]
    plates = [
        ("P1", "Shell A", IVORY, "fuzzy painted"),
        ("P2", "Shell B", IVORY, "fuzzy painted"),
        ("P3", "Shell C", IVORY, "fuzzy painted"),
        ("P4", "A→B halo ring", IVORY, "open webs + clocking tab"),
        ("P5", "B→C halo ring", IVORY, "tall skirt + clocking tab"),
        ("P6", "1.2 mm diffuser", "#FFFFFF", "Jade White, locator tips up"),
        ("P7", "Leg frame", CHOC, "inverted, five walls"),
        ("P8", "LED cradle", CHOC, "base-down, 3 blind sockets"),
    ]
    for i, (pid, name, colour, note) in enumerate(plates):
        px = X + 18 + (i % 4) * 164
        py = Y + 44 + (i // 4) * 148
        s.append(f'<rect x="{px}" y="{py}" width="154" height="132" rx="8" fill="#FBF9F5" stroke="{HAIR}"/>')
        s.append(f'<rect x="{px + 14}" y="{py + 30}" width="126" height="86" rx="4" fill="#EFEBE3" stroke="{HAIR}" stroke-dasharray="3 3"/>')
        s.append(f'<text class="th" x="{px + 14}" y="{py + 21}">{pid} · {name}</text>')
        if i < 3:
            flat = shells[i].as_printed()
            sc = min(112 / (flat.max_radius * 2), 66 / flat.long_side)
            sub = View(cx=px + 77, base_y=py + 108, scale=sc)
            s.append(f'<path d="{path_of(sub, flat.outline())}" fill="{colour}" stroke="{IVORY_D}"/>')
            s.append(
                f'<path class="bed" d="M{sub.x(-flat.max_radius) - 8:.1f},{sub.y(0):.1f} '
                f'L{sub.x(flat.max_radius) + 8:.1f},{sub.y(0):.1f}"/>'
            )
            size = f"Ø{n(flat.max_radius * 2)} × {n(flat.long_side)}"
        else:
            s.append(f'<circle cx="{px + 77}" cy="{py + 73}" r="26" fill="{colour}" opacity="0.9"/>')
            size = "fits one plate"
        s.append(f'<text class="kvs" x="{px + 14}" y="{py + 128}">{size} · {note}</text>')
    return "".join(s)


# --------------------------------------------------------------------------
# Sheet
# --------------------------------------------------------------------------

DEFS = f"""
<defs>
  <linearGradient id="shellgrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#D3C9B7"/>
    <stop offset="0.30" stop-color="{IVORY}"/>
    <stop offset="0.68" stop-color="#FCFAF5"/>
    <stop offset="1" stop-color="#C7BCA9"/>
  </linearGradient>
  <linearGradient id="shelllit" x1="0" y1="0" x2="1" y2="0.25">
    <stop offset="0" stop-color="#B9AC97"/>
    <stop offset="0.26" stop-color="#F0E8DA"/>
    <stop offset="0.58" stop-color="#FFF7E7"/>
    <stop offset="1" stop-color="#AFA292"/>
  </linearGradient>
  <linearGradient id="roomgrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#26221E"/>
    <stop offset="1" stop-color="#463E36"/>
  </linearGradient>
  <linearGradient id="halograd" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{GLOW}" stop-opacity="0.4"/>
    <stop offset="0.5" stop-color="#FFF2D6"/>
    <stop offset="1" stop-color="{GLOW}" stop-opacity="0.4"/>
  </linearGradient>
  <linearGradient id="interiorlit" x1="0" y1="0" x2="0.25" y2="1">
    <stop offset="0" stop-color="#3B342D"/>
    <stop offset="0.35" stop-color="#7A6B5A"/>
    <stop offset="0.75" stop-color="#C9B394"/>
    <stop offset="1" stop-color="#FFE4B5"/>
  </linearGradient>
  <radialGradient id="ledglow">
    <stop offset="0" stop-color="#FFE6B4" stop-opacity="0.95"/>
    <stop offset="1" stop-color="{GLOW}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="slotglow" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#FFF4DC"/>
    <stop offset="1" stop-color="{GLOW}" stop-opacity="0.2"/>
  </linearGradient>
  <pattern id="cut" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <rect width="7" height="7" fill="{CHOC}"/>
    <path d="M0,0 L0,7" stroke="#8A6A50" stroke-width="1.3"/>
  </pattern>
  <pattern id="boucle" width="9" height="9" patternUnits="userSpaceOnUse">
    <circle cx="1.9" cy="1.7" r="1.5" fill="#FFFFFF" opacity="0.3"/>
    <circle cx="6.2" cy="3.4" r="1.1" fill="#A2977F" opacity="0.16"/>
    <circle cx="3.7" cy="6.6" r="1.6" fill="#FFFFFF" opacity="0.22"/>
    <circle cx="7.7" cy="7.8" r="0.9" fill="#8E8471" opacity="0.15"/>
    <circle cx="0.4" cy="5.1" r="0.8" fill="#FFFFFF" opacity="0.2"/>
  </pattern>
  <marker id="arrow" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
    <path d="M0,3.5 L7,1 L5.4,3.5 L7,6 Z" fill="{ACCENT}"/>
  </marker>
  <marker id="dot" markerWidth="6" markerHeight="6" refX="3" refY="3">
    <circle cx="3" cy="3" r="2" fill="{ACCENT}"/>
  </marker>
</defs>
"""

CSS = f"""
<style>
  text {{ font-family: 'Inter','Helvetica Neue',Arial,sans-serif; fill: {INK}; }}
  .h1 {{ font-size: 30px; font-weight: 700; letter-spacing: -0.4px; }}
  .h2 {{ font-size: 13px; fill: {MUTED}; }}
  .badge {{ font-size: 11px; font-weight: 700; fill: {ACCENT}; letter-spacing: 1.4px; }}
  .card {{ fill: {PANEL}; stroke: {HAIR}; stroke-width: 1; }}
  .cardtitle {{ font-size: 11.5px; font-weight: 700; letter-spacing: 1px; fill: {MUTED}; }}
  .kv {{ font-size: 12px; font-weight: 600; }}
  .kvs {{ font-size: 11px; fill: {MUTED}; }}
  .th {{ font-size: 10px; font-weight: 700; letter-spacing: 0.6px; fill: {MUTED}; }}
  .td {{ font-size: 12px; }}
  .note {{ font-size: 10.5px; fill: {MUTED}; }}
  .dim {{ stroke: {ACCENT}; stroke-width: 1; fill: none; }}
  .dimtick {{ stroke: {ACCENT}; stroke-width: 1; opacity: 0.55; }}
  .dimtext {{ font-size: 11px; font-weight: 600; fill: {ACCENT}; }}
  .lead {{ stroke: {ACCENT}; stroke-width: 0.85; fill: none; opacity: 0.75; }}
  .leadtext {{ font-size: 11px; fill: {INK}; }}
  .ground {{ stroke: {HAIR}; stroke-width: 2; }}
  .axis {{ stroke: {MUTED}; stroke-width: 0.7; stroke-dasharray: 9 4 2 4; opacity: 0.45; }}
  .rim {{ stroke: #A99C88; stroke-width: 1; opacity: 0.8; }}
  .hair {{ stroke: {HAIR}; stroke-width: 1; }}
  .cord {{ stroke: #2B2723; stroke-width: 3; fill: none; stroke-linecap: round; }}
  .cordthin {{ stroke: #2B2723; stroke-width: 2.2; fill: none; }}
  .seat {{ stroke: {ACCENT}; stroke-width: 2.2; }}
  .rayline {{ stroke: {GLOW}; stroke-width: 1.8; opacity: 0.75; }}
  .bed {{ stroke: {ACCENT}; stroke-width: 1.8; opacity: 0.6; }}
</style>
"""


def build_svg(shells) -> str:
    top = overall_height(shells)
    widest = widest_diameter(shells)
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            'role="img" aria-labelledby="title desc">',
            '<title id="title">Bouclé Stack table lamp — 2D concept</title>',
            '<desc id="desc">A three-shell stacked table lamp for Bambu PLA Matte with fuzzy-skin boucle texture, '
            'a dark chocolate tripod base and a Bambu Lab LED Lamp Kit-001 module.</desc>',
            DEFS,
            CSS,
            f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
            '<text class="h1" x="40" y="50">Bouclé Stack — table lamp</text>',
            f'<text class="h2" x="40" y="72">Three oblique-cut shells · fuzzy-skin bouclé in Bambu PLA Matte · '
            f'Bambu Lab LED Lamp Kit-001 · {n(top)} mm tall, Ø{n(widest)} mm widest</text>',
            f'<text class="badge" x="{W - 40}" y="44" text-anchor="end">CONCEPT 01 · 2D · NOT CAD</text>',
            f'<text class="h2" x="{W - 40}" y="66" text-anchor="end">design/boucle-stack-lamp</text>',
            panel_elevation(shells),
            panel_impression(shells),
            panel_materials(),
            panel_hardware(),
            panel_fuzzy(),
            panel_schedule(shells),
            panel_base_section(),
            panel_joint(),
            panel_plates(shells),
            "</svg>",
        ]
    )


def report(shells) -> str:
    lines = ["part            base_d  max_d  rim_d   low   high   lean  cut_local  draft  origin"]
    for sh in shells:
        flat = sh.as_printed()
        lines.append(
            f"{sh.key:<15} {sh.base_radius * 2:6.1f} {sh.max_radius * 2:6.1f} "
            f"{sh.rim_half * 2:6.1f} {sh.short_side:5.1f} {sh.long_side:6.1f} "
            f"{sh.axis_deg:6.1f} {sh.local_cut()[0]:10.1f} {flat.draft_deg:6.1f}  "
            f"({sh.origin[0]:.1f}, {sh.origin[1]:.1f})"
        )
    top = overall_height(shells)
    widest = widest_diameter(shells)
    lines += [
        "",
        f"overall height   {top:.1f} mm",
        f"widest diameter  {widest:.1f} mm",
        f"foot circle      {LEG_FOOT_R * 2:.1f} mm",
        f"top rim x-extent left {shells[-1].rim_l[0]:.1f}  right {shells[-1].rim_r[0]:.1f}",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    shells = build_stack()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_svg(shells), encoding="utf-8")
    print(report(shells))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
