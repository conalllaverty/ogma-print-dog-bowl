#!/usr/bin/env python3
"""Generate illustrated coupon-test and lamp-assembly guides."""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "generator"))

import boucle_lamp_config as cfg  # noqa: E402


BG = "#F6F2EA"
INK = "#302C28"
MUTED = "#756D64"
BONE = "#E8DDC9"
BONE_DARK = "#C9B99E"
BASE = "#4B342D"
BASE_LIGHT = "#79584B"
HALO = "#E6A84A"
LIGHT = "#FFD77A"
PASS = "#4E765A"
FAIL = "#A34E46"
LINE = "#8C8175"


def text(x, y, value, cls="body", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">'
        f"{value}</text>"
    )


def wrapped_text(x, y, value, width=88, cls="body"):
    lines = textwrap.wrap(value, width=width)
    tspans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else 21}">{line}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text x="{x}" y="{y}" class="{cls}">{tspans}</text>'


def line(x1, y1, x2, y2, cls="line", marker=""):
    end = f' marker-end="url(#{marker})"' if marker else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}"{end}/>'


def panel(x, y, width, height, number, title):
    return "".join(
        [
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="18" class="panel"/>',
            f'<circle cx="{x + 36}" cy="{y + 38}" r="20" class="number"/>',
            text(x + 36, y + 45, number, "numberText", "middle"),
            text(x + 68, y + 45, title, "panelTitle"),
        ]
    )


def base_svg(width, height, title, subtitle):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
 viewBox="0 0 {width} {height}">
<defs>
  <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
    <path d="M0,0 L8,4 L0,8 Z" fill="{INK}"/>
  </marker>
  <marker id="lightArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
    <path d="M0,0 L8,4 L0,8 Z" fill="{HALO}"/>
  </marker>
  <filter id="glow"><feGaussianBlur stdDeviation="10"/></filter>
</defs>
<style>
  svg {{ background:{BG}; font-family:Inter,Arial,sans-serif; color:{INK}; }}
  .title {{ font-size:36px; font-weight:750; fill:{INK}; }}
  .subtitle {{ font-size:17px; fill:{MUTED}; }}
  .panel {{ fill:#FFFDF9; stroke:#D8CFC4; stroke-width:2; }}
  .panelTitle {{ font-size:22px; font-weight:700; fill:{INK}; }}
  .number {{ fill:{INK}; }}
  .numberText {{ font-size:18px; font-weight:750; fill:white; }}
  .body {{ font-size:16px; fill:{INK}; }}
  .small {{ font-size:13px; fill:{MUTED}; }}
  .label {{ font-size:14px; font-weight:650; fill:{INK}; }}
  .pass {{ font-size:14px; font-weight:650; fill:{PASS}; }}
  .fail {{ font-size:14px; font-weight:650; fill:{FAIL}; }}
  .line {{ stroke:{INK}; stroke-width:2; fill:none; }}
  .thin {{ stroke:{LINE}; stroke-width:1.4; fill:none; }}
  .dim {{ stroke:{HALO}; stroke-width:2; fill:none; }}
  .bone {{ fill:{BONE}; stroke:{INK}; stroke-width:2; }}
  .ring {{ fill:{HALO}; stroke:{INK}; stroke-width:2; }}
  .base {{ fill:{BASE}; stroke:{INK}; stroke-width:2; }}
  .light {{ stroke:{HALO}; stroke-width:3; fill:none; }}
  .glow {{ fill:{LIGHT}; opacity:.45; filter:url(#glow); }}
</style>
<rect width="{width}" height="{height}" fill="{BG}"/>
{text(56, 62, title, "title")}
{text(56, 92, subtitle, "subtitle")}
"""


def coupon_guide() -> str:
    out = [
        base_svg(
            1600,
            1120,
            "Bouclé Stack lamp — coupon test guide",
            "Print one plate at a time. Stop at the first failed gate; do not compensate by forcing parts.",
        )
    ]

    # Plate 1
    out.append(panel(48, 126, 738, 430, "1", "Glow wall + diffuser geometry proxy"))
    out.extend(
        [
            '<path d="M125 475 A170 170 0 0 1 425 300 L405 315 A145 145 0 0 0 145 465 Z" class="bone"/>',
            '<path d="M145 465 A145 145 0 0 1 405 315" stroke="#A89B8A" stroke-width="9" stroke-dasharray="2 10" fill="none"/>',
            text(107, 506, "1 dot", "label"),
            text(237, 369, "2 dots", "label"),
            text(390, 287, "3 dots", "label"),
            text(108, 526, "1.2 mm", "small"),
            text(237, 389, "1.6 mm", "small"),
            text(390, 307, "2.0 mm", "small"),
            '<circle cx="270" cy="482" r="36" class="glow"/>',
            '<circle cx="270" cy="482" r="23" fill="#FFF2C3" stroke="#C88A28" stroke-width="2"/>',
            text(270, 487, "LED", "label", "middle"),
            line(278, 452, 312, 390, "light", "lightArrow"),
            line(250, 450, 222, 402, "light", "lightArrow"),
            '<ellipse cx="520" cy="305" rx="82" ry="24" class="bone"/>',
            '<rect x="444" y="305" width="152" height="9" fill="#C9B99E"/>',
            '<rect x="472" y="314" width="8" height="42" fill="#C9B99E"/>',
            '<rect x="516" y="314" width="8" height="42" fill="#C9B99E"/>',
            '<rect x="560" y="314" width="8" height="42" fill="#C9B99E"/>',
            text(560, 265, "Bone proxy: disc down, locator tips up", "label", "middle"),
            line(520, 368, 520, 421, "line", "arrow"),
            '<circle cx="520" cy="454" r="28" fill="#FFF2C3" stroke="#C88A28" stroke-width="2"/>',
            text(520, 459, "LED", "label", "middle"),
            text(456, 508, "PASS  even glow · no pinholes at 300 mm", "pass"),
            text(456, 530, "PASS  LED die hidden at seated eye height", "pass"),
            text(80, 200, "Measure each smooth lower half at 3 points.", "body"),
            text(80, 225, "Light all sectors from the same position/exposure.", "body"),
        ]
    )

    # Plate 2
    out.append(panel(814, 126, 738, 430, "2", "A→B halo joint + Shell A base seat"))
    out.extend(
        [
            '<path d="M910 474 Q1010 430 1110 474 L1096 505 Q1010 472 924 505 Z" class="bone"/>',
            text(1010, 527, "Shell A rim coupon", "label", "middle"),
            '<path d="M930 353 Q1010 325 1090 353 L1070 390 Q1010 370 950 390 Z" class="ring"/>',
            '<rect x="1006" y="326" width="8" height="16" rx="2" class="ring"/>',
            text(1010, 316, "A→B halo ring", "label", "middle"),
            '<path d="M945 230 L1075 230 L1090 270 Q1010 285 930 270 Z" class="bone"/>',
            text(1010, 258, "Shell B base coupon", "label", "middle"),
            line(1010, 285, 1010, 318, "line", "arrow"),
            line(1010, 404, 1010, 430, "line", "arrow"),
            '<path d="M1190 455 Q1280 420 1370 455 L1360 480 Q1280 452 1200 480 Z" class="bone"/>',
            '<path d="M1210 390 Q1280 370 1350 390 L1338 425 Q1280 410 1222 425 Z" class="ring"/>',
            '<path d="M1224 330 L1336 330 L1350 370 Q1280 383 1210 370 Z" class="bone"/>',
            line(1377, 372, 1377, 421, "dim"),
            line(1366, 372, 1388, 372, "dim"),
            line(1366, 421, 1388, 421, "dim"),
            text(1395, 402, "4.0 ±0.2 mm", "label"),
            text(1185, 508, "measure at 3 points", "small"),
            '<rect x="1198" y="236" width="176" height="16" rx="3" class="base"/>',
            '<path d="M1224 212 L1348 212 L1341 236 L1231 236 Z" class="bone"/>',
            text(1286, 232, "Shell A base arc", "label", "middle"),
            text(1286, 274, "full wall supported; no rocking", "pass", "middle"),
            text(850, 200, "Align the tapered ring tab with Shell B's inner notch; dry-fit only.", "body"),
        ]
    )

    # Plate 3
    out.append(panel(48, 580, 738, 430, "3", "B→C halo joint"))
    out.extend(
        [
            '<path d="M115 928 Q240 882 365 928 L348 960 Q240 928 132 960 Z" class="bone"/>',
            '<path d="M140 820 Q240 786 340 820 L315 858 Q240 836 165 858 Z" class="ring"/>',
            '<rect x="236" y="787" width="8" height="16" rx="2" class="ring"/>',
            '<path d="M160 720 L320 720 L342 765 Q240 786 138 765 Z" class="bone"/>',
            line(240, 778, 240, 802, "line", "arrow"),
            line(240, 870, 240, 900, "line", "arrow"),
            text(240, 710, "Shell C base", "label", "middle"),
            text(240, 807, "B→C ring", "label", "middle"),
            text(240, 982, "Shell B rim", "label", "middle"),
            '<path d="M435 892 Q530 856 625 892 L612 918 Q530 892 448 918 Z" class="bone"/>',
            '<path d="M455 832 Q530 810 605 832 L592 862 Q530 848 468 862 Z" class="ring"/>',
            '<path d="M468 775 L592 775 L606 810 Q530 822 454 810 Z" class="bone"/>',
            line(634, 812, 634, 860, "dim"),
            text(650, 841, "4.0 ±0.2 mm", "label"),
            text(431, 950, "repeat all Plate 2 checks", "pass"),
            text(80, 650, "Align the tapered ring tab with Shell C's inner notch.", "body"),
            text(80, 675, "Use only the B→C pieces; the A→B ring is not interchangeable.", "fail"),
            text(455, 724, "assembled check", "label"),
        ]
    )

    # Plate 4
    out.append(panel(814, 580, 738, 430, "4", "LED cradle + plinth interface"))
    out.extend(
        [
            '<path d="M900 700 L900 920 L990 920 L990 875 L1095 875 L1095 920 L1185 920 L1185 700 L1135 700 L1135 850 L950 850 L950 700 Z" class="base"/>',
            '<path d="M970 670 L1115 670 L1115 842 L1095 842 L1095 858 L990 858 L990 842 L970 842 Z" fill="#79584B" stroke="#302C28" stroke-width="2"/>',
            '<rect x="998" y="700" width="89" height="68" rx="6" fill="#FFF2C3" stroke="#C88A28" stroke-width="2"/>',
            text(1042, 740, "LED", "label", "middle"),
            line(1042, 668, 1042, 694, "line", "arrow"),
            line(1115, 788, 1180, 788, "thin"),
            text(1192, 793, "4 mm flange · 45° underside ramp", "small"),
            line(970, 820, 915, 820, "thin"),
            text(835, 825, "key opposite cable", "small"),
            '<path d="M1087 753 L1175 753" stroke="#E6A84A" stroke-width="9" fill="none"/>',
            text(1182, 758, "slot runs beside the single rear leg", "label"),
            '<path d="M932 684 L1152 684 L1142 700 L942 700 Z" class="bone"/>',
            text(1042, 674, "Shell A arc on outer seat", "small", "middle"),
            text(850, 966, "PASS  flush within 0.3 mm · lifts out · no rattle · no pinching", "pass"),
            text(1160, 680, "No puck: inspect the 45° bore ramp before fitting.", "fail"),
        ]
    )

    out.extend(
        [
            text(48, 1050, "After both halo joints pass: bond the less-favourable coupon, cure fully, then apply 500 g sideways for 60 s.", "body"),
            text(48, 1078, "PASS: no crack/separation and permanent slot change ≤0.2 mm.", "pass"),
            text(1552, 1078, "See TEST_RESULTS.md for the recording checklist.", "small", "end"),
            "</svg>",
        ]
    )
    return "".join(out)


def assembly_guide() -> str:
    out = [
        base_svg(
            1600,
            1120,
            "Bouclé Stack lamp — test-to-assembly guide",
            "Final assembly starts only after Plates 1–4 and the bond proof pass.",
        ),
        panel(48, 126, 650, 920, "A", "Exploded order — bottom to top"),
    ]

    cx = 365
    # Exploded stack
    out.extend(
        [
            '<path d="M215 956 L245 875 L485 875 L515 956 L472 956 L450 913 L280 913 L258 956 Z" class="base"/>',
            '<ellipse cx="365" cy="874" rx="120" ry="24" fill="#79584B" stroke="#302C28" stroke-width="2"/>',
            text(535, 922, "plinth + legs", "label"),
            '<path d="M314 826 L416 826 L416 875 L398 875 L398 885 L332 885 L332 875 L314 875 Z" fill="#79584B" stroke="#302C28" stroke-width="2"/>',
            '<rect x="337" y="842" width="56" height="32" rx="5" fill="#FFF2C3" stroke="#C88A28" stroke-width="2"/>',
            text(535, 853, "keyed cradle + LED", "label"),
            '<ellipse cx="365" cy="781" rx="82" ry="18" class="bone"/>',
            '<rect x="321" y="781" width="8" height="30" fill="#C9B99E"/>',
            '<rect x="361" y="781" width="8" height="30" fill="#C9B99E"/>',
            '<rect x="401" y="781" width="8" height="30" fill="#C9B99E"/>',
            '<rect x="323" y="811" width="4" height="7" fill="#C9B99E"/>',
            '<rect x="363" y="811" width="4" height="7" fill="#C9B99E"/>',
            '<rect x="403" y="811" width="4" height="7" fill="#C9B99E"/>',
            text(535, 788, "Diffuser: engage all 3 cradle sockets", "label"),
            '<path d="M235 685 Q365 622 495 685 L465 760 Q365 710 265 760 Z" class="bone"/>',
            text(535, 708, "Shell A", "label"),
            '<path d="M275 580 Q365 545 455 580 L432 625 Q365 603 298 625 Z" class="ring"/>',
            '<rect x="361" y="544" width="8" height="16" rx="2" class="ring"/>',
            text(535, 595, "A→B halo ring", "label"),
            '<path d="M274 458 L456 458 L480 530 Q365 560 250 530 Z" class="bone"/>',
            text(535, 495, "Shell B", "label"),
            '<path d="M292 354 Q365 326 438 354 L418 395 Q365 378 312 395 Z" class="ring"/>',
            '<rect x="361" y="325" width="8" height="16" rx="2" class="ring"/>',
            text(535, 370, "B→C halo ring", "label"),
            '<path d="M292 213 L438 213 L464 302 Q365 328 266 302 Z" class="bone"/>',
            text(535, 263, "Shell C", "label"),
        ]
    )
    for y1, y2 in [(853, 813), (772, 748), (672, 632), (568, 538), (444, 403), (342, 310)]:
        out.append(line(cx, y1, cx, y2, "line", "arrow"))

    out.extend(
        [
            text(80, 990, "Orange = bonded joints. Bond Shell A to the plinth groove, not the cradle.", "label"),
            text(80, 1015, "Cradle stays removable through Shell A; dry-fit before any glue.", "fail"),
        ]
    )

    # Sequence cards
    cards = [
        (
            "1",
            "Install cradle + LED",
            "Keep the two-leg gap at the front. Confirm the 45° bore ramp is clean, align both open-top slots beside the single rear leg, engage the opposite key, and lower the LED while laying its lead sideways. No support material needs removal.",
        ),
        (
            "2",
            "Fit the diffuser baffle",
            "Use the Jade White 1.2 mm part only: disc above the LED, posts toward the module. Rotate until all three reduced pegs enter the blind cradle sockets and the Ø6 shoulders sit flat without force or rocking. Confirm the cable remains free and the LED die is hidden at seated eye height.",
        ),
        (
            "3",
            "Bond Shell A to the plinth",
            "Dry-fit first: Shell A's 1.6 mm wall must drop into the 1.0 mm annular groove. Remove the cradle and diffuser, wipe a thin epoxy film on the groove floor only, seat Shell A, and wipe squeeze-out. Never glue the cradle flange — it must still pass through Shell A after cure.",
        ),
        (
            "4",
            "Reinstall cradle and run the safety gate",
            "After Shell A cures, lower the cradle and diffuser back through its opening. Power for 8 hours; PLA must stay below 45°C. Add upper-stack mass dummies and pass a 10° board test in every direction.",
        ),
        (
            "5",
            "Bond the A→B joint",
            "Seat the conformal skirt in Shell A, then align the tapered ring tab with Shell B's open inner notch. Apply a thin adhesive film only to contact zones and clamp at 4.0 ±0.2 mm.",
        ),
        (
            "6",
            "Bond the B→C joint",
            "Lower the complete 5 mm band evenly into Shell B, then align the tapered tab with Shell C's open inner notch. Dry-seat first and keep glue out of the halo window.",
        ),
        (
            "7",
            "Final powered validation",
            "Run 24 hours. Recheck slot widths, stability, glare, cable temperature and PLA temperature; stop for smell, softening or colour change.",
        ),
    ]
    x, y, width, height = 736, 126, 816, 112
    for number, title_value, description in cards:
        out.extend(
            [
                f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="16" class="panel"/>',
                f'<circle cx="{x + 38}" cy="{y + 38}" r="20" class="number"/>',
                text(x + 38, y + 45, number, "numberText", "middle"),
                text(x + 72, y + 35, title_value, "panelTitle"),
                wrapped_text(x + 72, y + 66, description),
            ]
        )
        if number == "5":
            out.extend(
                [
                    f'<rect x="1330" y="{y + 16}" width="182" height="34" rx="7" fill="#FFF4E2" stroke="#E6A84A"/>',
                    text(
                        1421,
                        y + 39,
                        f"target gap {cfg.HALO_GAP:.1f} mm",
                        "label",
                        "middle",
                    ),
                ]
            )
        y += 126

    out.extend(
        [
            '<rect x="736" y="1016" width="816" height="50" rx="12" fill="#FCE9E5" stroke="#C87970"/>',
            text(758, 1047, "Never block the cable path, glue the removable cradle, or close either halo light window.", "fail"),
            "</svg>",
        ]
    )
    return "".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "design" / "boucle-stack-lamp" / "coupons",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    files = {
        "COUPON_TEST_GUIDE.svg": coupon_guide(),
        "ASSEMBLY_GUIDE.svg": assembly_guide(),
    }
    for filename, contents in files.items():
        path = args.out / filename
        path.write_text(contents)
        print(path)


if __name__ == "__main__":
    main()
