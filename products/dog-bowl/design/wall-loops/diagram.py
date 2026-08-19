import sys
sys.path.insert(0,"products/dog-bowl/generator"); sys.path.insert(0,"shared")
import cooper_bowl_design as d

OW, IW, LOOPS = 0.42, 0.45, 4
WALL = d.WALL_OUTER_R - d.WALL_INNER_R
PAD  = WALL - d.PAW_RECESS_DEPTH

S = 92.0                       # px per mm
INK="#1c1a17"; MUT="#6f675e"; BG="#faf7f2"
OUTER="#c2410c"; INNER="#d9a441"; FILL="#7ba3b8"; BAD="#b3261e"; GOOD="#2f6b4f"

def loops_mm(n): return OW + (n-1)*IW

def band(x, w, y, h, fill, label=None, tiny=False):
    o = [f'<rect x="{x:.1f}" y="{y}" width="{w*S:.1f}" height="{h}" fill="{fill}" stroke="#00000022"/>']
    if label and w*S > 26:
        o.append(f'<text x="{x + w*S/2:.1f}" y="{y+h/2+3.5}" class="{"tw" if tiny else "t"}" text-anchor="middle">{label}</text>')
    return o

def section(x0, y, wall_mm, n_loops, title, note, note_cls="n"):
    o=[f'<text x="{x0}" y="{y-30}" class="h">{title}</text>',
       f'<text x="{x0}" y="{y-13}" class="s">{note}</text>']
    H=76
    per = loops_mm(n_loops)
    total_w = wall_mm*S
    # the wall itself
    o.append(f'<rect x="{x0}" y="{y}" width="{total_w:.1f}" height="{H}" fill="#ffffff" stroke="{INK}" stroke-width="1.6"/>')
    # loops from the outer face
    cx = x0
    for i in range(n_loops):
        w = OW if i==0 else IW
        o += band(cx, w, y, H, OUTER if i==0 else INNER, f"{w}", tiny=True)
        cx += w*S
    # loops from the inner face
    cx2 = x0 + total_w
    for i in range(n_loops):
        w = OW if i==0 else IW
        cx2 -= w*S
        o += band(cx2, w, y, H, OUTER if i==0 else INNER, f"{w}", tiny=True)
    gap = wall_mm - 2*per
    if gap > 0.01:
        o += band(x0+per*S, gap, y, H, FILL, "infill")
    else:
        # the two stacks collide
        ox = x0 + (wall_mm-per)*S
        o.append(f'<rect x="{ox:.1f}" y="{y}" width="{(2*per-wall_mm)*S:.1f}" height="{H}" fill="{BAD}" opacity="0.75"/>')
        o.append(f'<text x="{x0+total_w/2:.1f}" y="{y+H+30}" class="bad" text-anchor="middle">'
                 f'overlap {2*per-wall_mm:.2f} mm — perimeters do not fit</text>')
    # dimension across the wall
    o.append(f'<line x1="{x0}" y1="{y+H+12}" x2="{x0+total_w:.1f}" y2="{y+H+12}" class="dm"/>')
    o.append(f'<line x1="{x0}" y1="{y+H+7}" x2="{x0}" y2="{y+H+17}" class="dm"/>')
    o.append(f'<line x1="{x0+total_w:.1f}" y1="{y+H+7}" x2="{x0+total_w:.1f}" y2="{y+H+17}" class="dm"/>')
    o.append(f'<text x="{x0+total_w/2:.1f}" y="{y+H+9}" class="d" text-anchor="middle">{wall_mm:.2f} mm of wall</text>')
    o.append(f'<text x="{x0-14}" y="{y+H/2+4}" class="d" text-anchor="end">outside</text>')
    o.append(f'<text x="{x0+total_w+14:.1f}" y="{y+H/2+4}" class="d">inside</text>')
    if gap > 0.01:
        o.append(f'<text x="{x0+total_w/2:.1f}" y="{y+H+30}" class="{note_cls}" text-anchor="middle">'
                 f'{n_loops} loops each side = {2*per:.2f} mm, leaving {gap:.2f} mm — fits</text>')
    return o

W,Hh = 1180, 880
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{Hh}" viewBox="0 0 {W} {Hh}">',
   f'<rect width="{W}" height="{Hh}" fill="{BG}"/>','<style>',
   f'.ti{{font:600 22px Helvetica;fill:{INK}}} .st{{font:13px Helvetica;fill:{MUT}}}',
   f'.h{{font:600 15px Helvetica;fill:{INK}}} .s{{font:11.5px Helvetica;fill:{MUT}}}',
   f'.d{{font:11px Helvetica;fill:{MUT}}} .dm{{stroke:{MUT};stroke-width:.8}}',
   f'.t{{font:11px Helvetica;fill:#123}} .tw{{font:9px Helvetica;fill:#1a1a1a}}',
   f'.n{{font:12px Helvetica;fill:{GOOD}}} .bad{{font:600 12px Helvetica;fill:{BAD}}}',
   '</style>',
   '<text x="44" y="44" class="ti">What a “loop” is, and why the paws show lines</text>',
   '<text x="44" y="66" class="st">A loop is one lap the nozzle makes around the outline of a layer before filling the middle. '
   'Bambu calls them walls. Sections through the drum wall, seen from above.</text>']

# legend
lx, ly = 44, 96
o.append(f'<rect x="{lx}" y="{ly}" width="26" height="14" fill="{OUTER}"/><text x="{lx+32}" y="{ly+11}" class="d">outer loop (0.42 mm)</text>')
o.append(f'<rect x="{lx+190}" y="{ly}" width="26" height="14" fill="{INNER}"/><text x="{lx+222}" y="{ly+11}" class="d">inner loops (0.45 mm)</text>')
o.append(f'<rect x="{lx+400}" y="{ly}" width="26" height="14" fill="{FILL}"/><text x="{lx+432}" y="{ly+11}" class="d">sparse infill</text>')
o.append(f'<rect x="{lx+560}" y="{ly}" width="26" height="14" fill="{BAD}" opacity="0.75"/><text x="{lx+592}" y="{ly+11}" class="d">no room — gap infill and squashed walls</text>')

o += section(150, 210, WALL, 4, "A · open wall, away from a paw", "4 loops each side, as configured today")
o += section(150, 420, PAD, 4, "B · at a paw pad — the problem", f"the {d.PAW_RECESS_DEPTH} mm recess takes the wall down to {PAD:.2f} mm", "bad")
o += section(150, 640, PAD, 3, "C · proposed fix — 3 loops on the panel", "same geometry, one fewer lap each side")
o.append('</svg>')
open("/tmp/loops/loops.svg","w").write("\n".join(o))
print("wrote /tmp/loops/loops.svg")
print(f"  wall {WALL:.2f} mm, at a pad {PAD:.2f} mm, 4 loops need {2*loops_mm(4):.2f}, 3 loops need {2*loops_mm(3):.2f}")
