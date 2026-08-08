#!/usr/bin/env python3
"""Generate the Oggie Spin arm-retention review sheet.

Companion diagram for design/modular-spinner/ARM-RETENTION-REVIEW.md.

Run from the repository root:

    python3 scripts/generate_spinner_retention_sheet.py
"""

import argparse
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = (
    ROOT / "design" / "modular-spinner" / "oggie-spin-arm-retention.svg"
)

INK="#252A32"; MUTE="#6B7480"; LINE="#B9C0C8"; PAPER="#FBFBF9"
BAD="#D64545"; GOOD="#2E8B57"; BLUE="#3A8FCF"; AMBER="#D08A2C"
W,H=1700,1220; o=[]
def a(s): o.append(s)
def txt(x,y,s,sz=12,fill=INK,anc="start",wt="400"):
    s=s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    a(f'<text x="{x:.1f}" y="{y:.1f}" font-family="DejaVu Sans,Helvetica,sans-serif" font-size="{sz}" fill="{fill}" text-anchor="{anc}" font-weight="{wt}">{s}</text>')
def rect(x,y,w,h,f="none",s=LINE,sw=1.0,r=0,d=None):
    a(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" height="{max(h,0):.1f}" fill="{f}" stroke="{s}" stroke-width="{sw}" rx="{r}"'+(f' stroke-dasharray="{d}"' if d else '')+'/>')
def line(x1,y1,x2,y2,c=LINE,w=1.0,d=None):
    a(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{w}"'+(f' stroke-dasharray="{d}"' if d else '')+'/>')
def poly(pts,f,s=INK,sw=1.3):
    a('<path d="M '+" L ".join(f"{x:.2f},{y:.2f}" for x,y in pts)+f' Z" fill="{f}" stroke="{s}" stroke-width="{sw}" stroke-linejoin="round"/>')
def flag(x,y,n,c=BAD):
    a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8.5" fill="{c}"/>'); txt(x,y+3.8,str(n),10.5,"#FFF","middle","700")
def note(x,y,n,head,lines,c=BAD,lh=15.5):
    flag(x,y,n,c); txt(x+15,y+4,head,11.5,c,"start","700")
    for i,l in enumerate(lines): txt(x+15,y+4+lh*(i+1),l,11,INK)

a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
rect(0,0,W,H,PAPER,"none",0)
txt(56,56,"OGGIE SPIN — ARM RETENTION",25,INK,"start","700")
txt(56,81,"Why the clip on the Broken Ring Illusion is too tight to remove, and the proposed replacement",13.5,MUTE)
txt(W-56,56,"REVIEW SHEET",12.5,MUTE,"end","700")
txt(W-56,78,"all mm · arm-local, Z=0 at installed core bottom",10.5,MUTE,"end")
line(56,98,W-56,98,LINE,1.4)

RC=22.30
DEV_OFF=[5.4]
def dev(x0,y0,S,adeg,r):   # developed: x = arc at RC, y = radius
    return x0+(math.radians(adeg)*RC+DEV_OFF[0])*S, y0-(r-19.3)*S
def dband(x0,y0,S,a0,a1,r0,r1,f,s=INK,sw=1.3):
    p0=dev(x0,y0,S,a0,r0); p1=dev(x0,y0,S,a1,r1)
    rect(min(p0[0],p1[0]),min(p0[1],p1[1]),abs(p1[0]-p0[0]),abs(p1[1]-p0[1]),f,s,sw)

# ══ PANEL A ══
PX,PY,PW,PH=56,120,790,505
rect(PX,PY,PW,PH,"#FFFFFF",LINE,1.2,6)
txt(PX+24,PY+32,"A · AS BUILT — arm underside, developed flat",15,INK,"start","700")
txt(PX+24,PY+53,"The cantilever is fused to the wrap in three places, so it cannot flex.",11.5,MUTE)
S=40.0; ox,oy=PX+28,PY+310
dband(ox,oy,S,-13,18,19.30,20.00,"#E7EAEE",MUTE,1.3); txt(ox+30,oy-8,"CORE  (R20 OD)",10,MUTE,"start","700")
dband(ox,oy,S,-13,18,20.12,24.50,"#DCE9F4",BLUE,1.4)
txt(ox+30,dev(ox,oy,S,0,24.0)[1]+4,"ARM WRAP   R20.12 – 24.50   (0.12 clearance)",10,BLUE,"start","700")
dband(ox,oy,S,7.0,17.0,19.60,20.00,"#FFFFFF",MUTE,1.1)
txt(*dev(ox,oy,S,12,19.72),"pocket",9,MUTE,"middle")
dband(ox,oy,S,-13,18,20.00,20.12,PAPER,"none",0)
dband(ox,oy,S,-11,12.8,21.45,23.15,"#F5F6F7",LINE,0.9)   # relief
dband(ox,oy,S,-11,12,21.80,22.80,"#FFFFFF",INK,1.4)      # beam
txt(*dev(ox,oy,S,0,22.28),"cantilever beam  1.00 × 2.40",9.5,INK,"middle","600")
dband(ox,oy,S,8.5,15.5,19.65,21.95,"#FBDADA",BAD,1.4)    # stem
dband(ox,oy,S,8.0,13.0,21.45,23.35,"#FBDADA",BAD,1.4)    # pad
dband(ox,oy,S,8.0,13.0,23.15,23.35,BAD,BAD,0.8)          # weld
dband(ox,oy,S,-13,18,24.50,25.00,PAPER,"none",0)
line(*dev(ox,oy,S,-13,24.5),*dev(ox,oy,S,18,24.5),BLUE,2.2)
txt(ox+PW-70,dev(ox,oy,S,0,24.72)[1],"R24.50  outer face",10,BLUE,"end","700")
txt(*dev(ox,oy,S,-12,21.15),"root",9.5,MUTE,"start")
note(PX+28,PY+352,1,"Stem block swallows the hook.",
     ["Union emits a plain rib — 90° at both ends.","The 37° entry ramp does not exist in the mesh."])
note(PX+28,PY+420,5,"No lever.",
     ["Pad sits 1.15 mm inside the R24.5 face,","0.70 mm tall, in a 0.35 mm slot."])
note(PX+420,PY+352,3,"Free tip welded to the wrap.",
     ["Pad reaches R23.35; the relief that frees it","only reaches R23.15. 0.20 mm of solid weld.","It is a fixed-fixed arch, not a cantilever."])
txt(PX+420,PY+443,"Beam on paper:  0.92 N · 0.69 % strain",11.5,MUTE,"start","700")
txt(PX+420,PY+461,"The spring was never the problem.",11.5,MUTE)

# ══ PANEL B ══
QX,QY=878,120; QW,QH=766,505
rect(QX,QY,QW,QH,"#FFFFFF",LINE,1.2,6)
txt(QX+24,QY+32,"B · AS BUILT — radial section through the hook",15,INK,"start","700")
txt(QX+24,QY+53,"The stem overruns the pocket into solid core and jams.",11.5,MUTE)
sx,sy,SS=QX+70,QY+300,62.0
def rz(r,z): return sx+(r-19.3)*SS, sy-z*SS
def box(r0,r1,z0,z1,f,s=INK,sw=1.3,d=None):
    x0,y1=rz(r0,z0); x1,y0=rz(r1,z1); rect(x0,y0,x1-x0,y1-y0,f,s,sw,0,d)
box(19.30,20.00,0.00,3.30,"#E7EAEE",MUTE,1.4); txt(*rz(19.62,-0.22),"CORE",10,MUTE,"middle","700")
box(19.60,20.00,0.45,2.10,"#FFFFFF",MUTE,1.1,"4 3")
txt(*rz(19.05,1.28),"pocket",9.5,MUTE,"end"); txt(*rz(19.05,0.95),"Z 0.45–2.10",9,MUTE,"end")
box(19.65,21.95,0.40,2.60,"#FBDADA",BAD,1.4)
box(19.65,20.00,2.10,2.60,BAD,BAD,1.0); box(19.65,20.00,0.40,0.45,BAD,BAD,1.0)
txt(*rz(21.0,1.30),"stem",10,BAD,"middle","700")
box(21.80,22.80,0.30,2.70,"#FFFFFF",INK,1.3); txt(*rz(22.3,2.86),"beam",9.5,INK,"middle","600")
box(21.45,23.15,0.00,0.25,"#FBDADA",BAD,1.2)
box(21.45,23.35,0.30,1.00,"#F1F3F4",MUTE,1.0); txt(*rz(22.4,0.55),"pad",9.5,MUTE,"middle")
line(*rz(19.85,2.36),*rz(20.30,3.02),BAD,1.0)
txt(*rz(20.34,3.04),"0.50 mm buried in solid core",10,BAD,"start","700")
line(*rz(23.15,0.12),*rz(23.6,-0.30),BAD,1.0); txt(*rz(23.65,-0.32),"0.25 mm skin, 0.05 mm gap",10,BAD,"start","700")
bx=QX+30
note(bx,QY+352,2,"Stem Z 0.40–2.60 vs pocket Z 0.45–2.10.",
     ["≈ 0.26 mm³ of hard jam against solid core.",
      "Reported \"seated engagement\" = 0.3268 mm³.",
      "That number IS the jam, not hook retention."])
note(bx,QY+436,4,"0.05 mm gap under a 0.25 mm skin.",
     ["At 0.16 mm layers it prints fused. The release pad is unreachable."])
tb=QX+452
rect(tb-14,QY+352,QW-(tb-QX)-30,92,"#FDF3F3",BAD,1.0,4)
txt(tb,QY+375,"RELEASE TRAVEL",11,INK,"start","700")
txt(tb,QY+398,"hook needs 0.32, allowed 0.35",10.5,INK); txt(tb+190,QY+398,"margin +0.03",10.5,AMBER,"start","700")
txt(tb,QY+417,"stem needs 0.35, allowed 0.35",10.5,INK); txt(tb+190,QY+417,"margin  0.00",10.5,BAD,"start","700")
txt(tb,QY+436,"On an FDM part, 0.00 mm of margin is negative.",10.5,BAD,"start","600")

# ══ PANEL C ══
RX,RY,RW,RH=56,648,790,505
rect(RX,RY,RW,RH,"#FFFFFF",LINE,1.2,6)
txt(RX+24,RY+32,"C · PROPOSED — tapered snap-tab with thumb scallop",15,GOOD,"start","700")
txt(RX+24,RY+53,"Longer tapered beam, engagement above print tolerance, and something to push.",11.5,MUTE)
DEV_OFF[0]=7.6
S2=34.0
ox2,oy2=RX+28,RY+300
dband(ox2,oy2,S2,-19,20,19.30,20.00,"#E7EAEE",MUTE,1.3); txt(ox2+30,oy2-8,"CORE  (R20 OD)",10,MUTE,"start","700")
dband(ox2,oy2,S2,-19,20,20.30,24.50,"#DFF0E6",GOOD,1.4)
txt(ox2+30,dev(ox2,oy2,S2,0,24.0)[1]+4,"ARM WRAP   R20.30 – 24.50   (clearance 0.12 → 0.30)",10,GOOD,"start","700")
dband(ox2,oy2,S2,14.5,19.5,19.55,20.00,"#FFFFFF",MUTE,1.1); txt(*dev(ox2,oy2,S2,17,19.70),"pocket",9,MUTE,"middle")
dband(ox2,oy2,S2,-19,20,20.00,20.30,PAPER,"none",0)
dband(ox2,oy2,S2,-17,18.6,21.10,23.60,"#F5F6F7",LINE,0.9)
pts=[]; N=40
for i in range(N+1):
    f=i/N; ang=-17+34*f; t=1.30-0.65*f; pts.append(dev(ox2,oy2,S2,ang,RC+t/2))
for i in range(N,-1,-1):
    f=i/N; ang=-17+34*f; t=1.30-0.65*f; pts.append(dev(ox2,oy2,S2,ang,RC-t/2))
poly(pts,"#FFFFFF",INK,1.5)
txt(*dev(ox2,oy2,S2,-2,22.28),"tapered beam  1.30 → 0.65",9.5,INK,"middle","600")
dband(ox2,oy2,S2,15,19,19.55,20.45,"#CBE9D6",GOOD,1.5); txt(*dev(ox2,oy2,S2,17,20.72),"hook 0.45",9.5,GOOD,"middle","700")
dband(ox2,oy2,S2,15.5,19.5,23.30,24.50,"#FFF1DA",AMBER,1.5)
lx,ly=dev(ox2,oy2,S2,19.5,23.9)
line(lx,ly,lx+34,ly-26,AMBER,1.1)
txt(lx+38,ly-28,"thumb scallop",10.5,AMBER,"start","700")
txt(lx+38,ly-14,"3.0 × 1.2 into the wrap OD",9.5,AMBER,"start")
txt(lx+38,ly+2,"gives a thumbnail purchase",9.5,AMBER,"start")
dband(ox2,oy2,S2,-19,20,24.50,25.10,PAPER,"none",0)
line(*dev(ox2,oy2,S2,-19,24.5),*dev(ox2,oy2,S2,15.5,24.5),GOOD,2.2)
line(*dev(ox2,oy2,S2,19.5,24.5),*dev(ox2,oy2,S2,20,24.5),GOOD,2.2)
txt(*dev(ox2,oy2,S2,-18,21.10),"root",9.5,MUTE,"start")
tbl=[("Beam arc","23°","34°"),("Effective length","8.71","12.47"),("Thickness","1.00","1.30 → 0.65"),
     ("Engagement","0.22","0.45"),("Release travel","0.35","0.70   margin 0.25"),
     ("Entry ramp","64° actual","30°"),("Retention face","90° locked","45°"),
     ("Spring force","0.92 N","1.00 N"),("Surface strain","0.69 %","0.64 %   (max 1.5)"),
     ("Insertion","1.38 N","1.16 N"),("Pull-off","impossible","2.07 N")]
tx,ty=RX+30,RY+368
txt(tx,ty-13,"PARAMETER",9.5,MUTE,"start","700"); txt(tx+140,ty-13,"NOW",9.5,MUTE,"start","700"); txt(tx+215,ty-13,"PROPOSED",9.5,GOOD,"start","700")
line(tx,ty-7,tx+345,ty-7,LINE,1.0)
for i,(k,v1,v2) in enumerate(tbl):
    col=i//6; row=i%6
    cx=tx+col*385; cy=ty+9+row*20.5
    if col: 
        if row==0: txt(cx,ty-13,"PARAMETER",9.5,MUTE,"start","700"); txt(cx+140,ty-13,"NOW",9.5,MUTE,"start","700"); txt(cx+215,ty-13,"PROPOSED",9.5,GOOD,"start","700"); line(cx,ty-7,cx+345,ty-7,LINE,1.0)
    txt(cx,cy,k,10.5,INK); txt(cx+140,cy,v1,10.5,MUTE); txt(cx+215,cy,v2,10.5,GOOD,"start","700")
    line(cx,cy+6,cx+345,cy+6,"#EEF0F2",0.8)

# ══ PANEL D ══
SX,SY,SW,SH=878,648,766,505
rect(SX,SY,SW,SH,"#FFFFFF",LINE,1.2,6)
txt(SX+24,SY+32,"D · PROPOSED — hook profile and dual-mode release",15,GOOD,"start","700")
txt(SX+24,SY+53,"30° in, 45° out. Thumbnail for the deliberate swap, firm pull as override.",11.5,MUTE)
hx,hy,HS=SX+80,SY+300,80.0
def hz(r,z): return hx+(r-19.3)*HS, hy-z*HS
x0,y0=hz(19.3,0); x1,y1=hz(20.0,3.05); rect(x0,y1,x1-x0,y0-y1,"#E7EAEE",MUTE,1.4)
txt(*hz(19.65,-0.22),"CORE",10,MUTE,"middle","700")
px0,py0=hz(19.45,0.55); px1,py1=hz(20.00,2.45); rect(px0,py1,px1-px0,py0-py1,"#FFFFFF",MUTE,1.1,0,"4 3")
poly([hz(19.55,1.05),hz(20.45,1.80),hz(20.45,2.00),hz(19.55,2.45),hz(21.75,2.45),hz(21.75,1.05)],"#DFF0E6",GOOD,1.6)
txt(*hz(21.1,1.72),"hook",10,GOOD,"middle","700")
line(*hz(20.45,1.80),*hz(21.2,1.20),AMBER,1.1); txt(*hz(21.25,1.16),"30° entry ramp",10.5,GOOD,"start","700")
line(*hz(20.0,2.30),*hz(21.2,2.85),AMBER,1.1); txt(*hz(21.25,2.87),"45° retention face",10.5,GOOD,"start","700")
line(*hz(20.00,0.62),*hz(20.45,0.62),BAD,1.6)
line(*hz(20.00,0.52),*hz(20.00,0.74),BAD,1.0); line(*hz(20.45,0.52),*hz(20.45,0.74),BAD,1.0)
line(*hz(20.45,0.62),*hz(21.30,0.30),BAD,1.0)
txt(*hz(21.35,0.28),"0.45 engagement",10,BAD,"start","700")
txt(*hz(21.35,0.02),"(was 0.22)",9.5,BAD,"start")
bx2=SX+30; yy=SY+338
for head,lines in [
 ("WHY 45° AND NOT 90°",["The dovetail carries every bit of spin load; the latch only resists axial lift.",
                          "A 45° face gives a defined 2.07 N pull-off — far above anything a spinning arm",
                          "generates, and a firm deliberate tug by hand. Removal stops being lever-only."]),
 ("WHY 0.45 mm AND NOT 0.22",["P2S feature tolerance is ±0.10–0.15 mm. At 0.22 nominal, as-printed engagement",
                          "lands anywhere from 0.07 to 0.37 mm — 32 % to 168 %. 0.45 mm is ~3× tolerance."]),
 ("WHY TAPER THE BEAM",["Uniform strain along the span and ~1.6× the deflection for the same peak stress.",
                          "That is what pays for the bigger engagement: spring force barely moves, 0.92 → 1.00 N."])]:
    txt(bx2,yy,head,11,INK,"start","700")
    for i,l in enumerate(lines): txt(bx2,yy+16+i*15.0,l,10.5,INK)
    yy+=16+len(lines)*15.0+12

txt(56,H-26,"Change 0 — wrap clearance 0.12→0.30, core OD relief, lead-in chamfers and validator fixes — is required whatever mechanism wins.",11,MUTE)
txt(W-56,H-26,"Ogma Print",11,MUTE,"end","700")
a("</svg>")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(o), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
