# Oggie Spin — session guide

<!-- Split out of the monolithic root PROJECT_STATUS.md / AGENTS.md on 2026-08-06.
     Content is verbatim: the constraint lists here were earned from physical
     prints and must not be paraphrased. -->

**Every part must clear `shared/ogma/printability.py` before export.**

Sibling product for Railway/filament patterns: `ogma-print-core`.

The standalone county-clicker side product is packaged under
`county-clickers/`. Its production generator remains
`backend/generator/county_clicker.py` so it can reuse the established MX and
3MF utilities. County clickers are individual handheld pieces, not
tessellating map tiles.

The standalone Oggie Spin prototype is under `design/modular-spinner/`.
`backend/generator/oggie_spin_bayonet.py` generates its first four-plate P2S
fit test: Ø40 five-slot core, R188 seat, M3 × 25 mm button-head/nyloc cartridge,
two permanent hubs and two removable thumb pads. Keep the 0.4 mm hub/core gaps,
three 30° bayonet tracks, and 0.06 mm radial detent interference until physical
results say otherwise. Its archived Ø12.86 bearing pocket proved loose in the
first complete physical core and is superseded by the complete generator.
`backend/generator/oggie_spin_complete.py` extends that mechanism into the
current hardware-free nine-plate prototype with five identical short wrap-around
clip-lock colour segments (R20.12–R24.5, ±20°), a Ø15.22 pressed outer-race ring
in a Ø15.15 counterbore, and a Bambu PLA Tough+ split-collet cartridge. The first Ø6.10 axle spun well but wobbled;
Ø6.25 and Ø6.30 reduced but did not eliminate the wobble. The current Ø6.40
axle is a deliberate 0.05 mm nominal interference trial in the Ø6.35 R188 bore;
it must install with controlled hand pressure, never a hammer or pliers. It has
four 8.1 mm fingers and a Ø6.80 retaining bead. The Ø6.48 receiver leaves the
fingers exposed for deliberate release after removing the upper pad. Keep the
revised 1.6 mm hub/core gaps and integrated Ø8.40 inner-race spacer bosses.
Both pads must remain the same 6.4 mm mesh with a Ø7.30 × 5.2 mm blind socket:
the receiver side needs the socket for the exposed collet tip, while carrying
it on both sides simplifies batch manufacturing. The earlier Ø7.0 socket
required pliers to fit and is superseded; both pads must install by hand. The
five arms must retain their identical 100% grid infill and 2 wall-loop
overrides; do not restore weight pods, 5-wall arms, or mix mechanical slicer
settings across colours. The R188 is the only non-printed part. The matched
core/arm revision uses **one solid dovetail tongue** (R14.00–20.75, uniform
0.18 mm/side) that passes the **full 14 mm height right through the core**, with
a tapered cantilever barb at the tongue's inner tip snapping into an **open
recess in the core's underside**. The three-rail split is retired: physical
testing said it does not work, and three rails meant three tolerance stacks and
three thin features that can shave. The underside battery-cover clip is retired
too — it had five separate welding defects and a 0.00 mm release margin. The
slot's old 2 mm bottom shelf is gone; a 45° push-through ledge (x 18.00→19.40,
1.30 mm rise) is what now stops the arm from sliding out the far side. Do not
restore friction ribs, rigid side detents, Pinch-Lok flex rails/barbs, legacy
barb recesses, the three-rail tongue, or the 2 mm slot shelf.
New cores and arms are a matched pair — do not claim old-arm or old-core
compatibility. Wrap radial clearance is
0.30 mm (0.12 mm was too tight); keep the arm's 0.4 mm bottom lead-in and the
core's continuously lofted 0.4 mm slot-mouth lead-in. **Export arms flush top
face UP — do not flip them.** The old flip existed to dodge an overhang above
the retired 2 mm shelf; with the shelf gone it instead lifts the clip beam's
first layer 10.35 mm into the air, which is the floating cantilever Bambu Studio
rejected. `_flip_arm_for_print()` is deliberately a no-op. Any "flip" written as
a −1 axis scale is a **reflection**, not a rotation: it keeps the model
self-consistent so every interference check still passes, while the exported
part is a mirror image and the chiral snap clip lands on the wrong side. That
shipped once. `printability.assert_rigid()` now rejects any transform with a
negative determinant; route every orientation change through it. Do not restore
the earlier long petal arms after physical testing showed easy lift/rattle and
uneven one-side lock. Do not call the complete 3MF production-ready
until the retaining ring, Tough+ collet, all five arm clip locks, both thumb locks
and free-spin behaviour pass physical testing. The current R188 pocket is
Ø12.82: Ø12.86 released the bearing under gravity, Ø12.68 would not install by
hand, and Ø12.78 remained too tight. The pocket now uses 0.12 mm nominal
diametral clearance and relies on the separate pressed outer-race ring for axial
capture.
`backend/generator/oggie_spin_broken_rings.py` owns the optical winner: keep the
proven 15/20/25 dash rings at R15.5 / R18.5 / R22.5 (1.1 mm width, 52% duty,
0.32 mm flush Ivory inlays), and reuse the matched through-slot
tongue + far-face snap-clip mechanism. The underside `BR` identifier is
**removed** (`IDENTIFIER = None`) — Broken Ring is the only live design, so it
distinguished nothing and read as noise. Do not add a fourth ring.
**Every part must clear `backend/generator/printability.py` before export.**
It sections each mesh at every layer height and diffs each footprint against the
one below, the way a slicer does. Geometric validators in this repo compare the
model to itself, so they are blind to anything that only exists once a part is
oriented on a bed — which is precisely the class of defect that kept reaching
the slicer. The key measure is **anchor ratio**, the fraction of a new region's
outline sitting on the layer below; distance-to-support cannot tell a bridge
from a cantilever. Under 18% is blocking and `generate()` raises rather than
writing a mesh. It is calibrated on the old flipped arm, which it blocks.

**Force figures must come from `clip_forces()` in `oggie_spin_complete.py`, never
from prose.** Two revisions carried a 2.20 N pull-off the geometry never
supported — derived from the barb's total 0.65 mm protrusion instead of the
0.45 mm deflection the core's retaining lip actually demands. As built it is
1.42 N. Related standing rule: compare bending stress to **flexural strength**,
never strain to tensile elongation at break; that error once reported a 12:1
margin where the real one was under 2:1.

**Print `oggie_spin_sanity_plate.py` before any nine-plate run.** It is a core
sector plus one arm, 6.7 g and about 15 minutes, and it re-loads the exported
STLs from disk and assembles them with rotations only. Four full revisions of
this joint were built on arithmetic alone; a mirrored export, a missing
push-through stop and a floating cantilever all reached the slicer or the bed,
and every one would have been caught by one arm against one slot.

`backend/generator/oggie_spin_optical_variants.py` owns seven separate
core-and-arm optical experiments under `design/modular-spinner/optical-variants/`:
full-body vortex (`VX`), spiral (`SP`), chevron (`CH`), strobe (`ST`), opposing
drift (`OD`), colour pulse (`CP`) and dashed ladder (`LD`). VX must keep five
1.8 mm tracks sweeping 70° from R10.6 to R24.5; keep its core phase at -90° so
the fivefold-symmetric arm pattern crosses every core-to-arm seam. Keep each
flush optical inlay 0.32 mm deep, preserve volume-matched arms and keep the
two-letter contrasting identifier on the core underside. Each two-plate project keeps all five arms
together in the proven centre-plus-four-corners layout with two walls, 100%
gyroid, 0.6 mm Slope Lift and the batch retraction/wipe profile. Keep the inlay
variants by layer. Keep colour pulse by object so its three full-arm colours
need four AMS changes instead of 174. These projects reuse the standard
retaining ring, cartridge and pads and remain physically untested.
`backend/generator/oggie_spin_shutter_infill.py` owns the separate `SH`
stationary-shutter experiment. Keep its thirteen 1.2 mm structural radial ribs
in the 1.6 mm-deep core recess, with narrower 0.8 mm × 0.32 mm Ivory flush
caps, and keep the split Ø46 × 1.8 mm shutter at twelve 6° slots. The shutter
ring snaps into the modified upper pad with 0.10 mm/side bead pass
interference; the groove must leave at least 1.20 mm outside the bayonet cavity.
Retain the 1.6 mm running gap and 1.5 mm radial margin inside the R24.5 arm
tips. Keep Plate 3's five included standard arms in the proven
centre-plus-four-corners layout with two walls, 100% gyroid and 0.6 mm Slope
Lift. The retaining ring, cartridge and lower pad are reused. This is
slice-validated only: do not call it safe or production-ready until snap
retention, deflection, rub-free spin and the naked-eye 13:12 moiré effect pass
physical tests.

The standalone Bouclé Stack lamp is under `design/boucle-stack-lamp/`.
`backend/generator/boucle_lamp_shade.py` generates one eight-plate P2S project
plus eight individual fallback projects (three shells, two halo rings, the
1.2 mm LED diffuser, leg frame and removable cradle). Shells/rings use Bone
White Matte, the diffuser uses stock PLA Basic Jade White, and the base parts
use Dark Chocolate Matte.
Shells A/B are 1.6 mm; Shell C is 1.2 mm but retains the canonical 1.6 mm
base/register solid so the B→C interface does not change. Keep fuzzy paint at
0.30 mm thickness / 0.80 mm point distance with Classic noise and Displacement
mode, exterior sidewalls only. This is the physically preferred production
texture; do not replace it without a successful physical comparison.
Do not put multiple parts on one plate: physical coupon prints repeatedly strung
during inter-object travels. The combined 3MF must retain exactly one object on
each of its eight plates. Keep
`reduce_infill_retraction_mode=Disabled` project-wide in the combined 3MF and
on the individual ring, leg-frame and cradle fallbacks; Bambu applies this
policy globally and stock `Auto` suppresses retraction on long internal
detours. A→B uses a continuous 22 mm-deep conformal bond skirt with a straight
lower edge; this replaces the ten scarfed tabs whose triangular shadows were
visible through Shell A in the first lit assembly. Keep its twenty 1.2 mm
straight radial webs and bed-rooted central collar. Do not restore the scarfed
tabs, scalloped crown or solid funnel; the funnel materially reduces
upper-shell illumination. B→C retains its continuous shallow 5 mm outer band.
The straight A→B architecture is boolean/support validated but still needs a
physical print and lighting check.
The production leg frame must keep its three legs extended through the visible
plinth contact to `LEG_EMBED_R` / `LEG_EMBED_Z`, then clipped outside the
cradle bore. It prints inverted with its top seat on the bed. Keep the seat /
cradle flange at 4.0 mm. The Ø116 top seat carries a 1.0 mm annular locate
groove for Shell A's Ø112 × 1.6 mm base wall. The groove outer wall clears the
shell's flare at groove depth with ±0.25 mm per side. Keep Plate 7 support off:
the groove closes across only ~2.6 mm and the cradle-stop step is 0.8 mm, while
generated support introduced the only unretracted >5 mm travels and physically
strung inside the inset. Use 20 mm/s bridge speed, 0.9 mm Dark Chocolate
filament retraction, 3 mm wipe and disabled infill-retraction reduction. Bond
Shell A into the groove with a thin epoxy film; never glue the removable cradle. The cradle
flange must still pass through Shell A's inner opening after cure. The
flange bears on a 0.6 mm radial outer stop, then the Ø94 bore opens below it
through a 1.9 mm-high 45° ramp. The former full-width horizontal shoulder
started as an unsupported inward cliff and peeled into chords; do not restore
it or the later full breakaway puck. Ending a leg on the plinth tangent exposes
its slanted cap and also intrudes into the removable cradle.
Plate 8 must mirror the plinth ramp with 0.2 mm radial clearance: expand its
Ø93.6 body to Ø97.4 over a 1.9 mm-high 45° underside ramp, leaving only the
0.8 mm radial step into the Ø99 flange. Grow the anti-rotation key outward at
45° over its first 2 mm, then retain 2 mm at full depth. Do not restore the
flat flange or key cantilevers; they produced exposed bridge paths and
spaghetti at Z24.2.
Keep `CABLE_PHASE_DEG` 20° beside the single rear leg (currently 110° beside
the 90° leg), and rotate the cradle slot plus opposite anti-rotation key with
the plinth notch. This leaves the gap between the 210° and 330° front legs
visually open.
The diffuser is not gravity-located: each Ø6 post ends in a Ø3 × 2 mm peg that
engages one of three Ø3.6 × 2.4 mm blind cradle sockets. Keep 0.6 mm total
diametral clearance, 0.4 mm bottom clearance, ≥1.5 mm material to the LED
pocket, and one object per plate. Do not remove the post shoulders or turn the
blind sockets into through-holes.
Do not remove the 4 mm internal locating ledges from Shells B/C. Shell B is
only 10.2 mm tall on its short side, so B→C's outer band must remain 5 mm deep;
this leaves 1.2 mm above the lower register. Keep its central collar and five
evenly distributed bed-rooted radial webs. Deepening the full-circumference
band or restoring a funnel collides with the A→B joint.
Each halo ring has one hidden tapered clocking tab for the upper shell. Keep
the 3.0 × 1.0 × 3.2 mm tab and matching 3.8 × 1.4 mm open-bottom notch in
Shell B/C's register. The intended clearances are 0.8 mm tangential, 0.4 mm
radial and 0.8 mm above the tab, with ≥2.6 mm register material behind the
notch. Each ring also carries one outward skirt tab into an open rim notch in
the lower shell (A for A→B, B for B→C) so the halo can be felt into place
before bonding. Keep the 3.0 × 0.55 × 4.0 mm joint-frame tab and nominal
3.8 × 0.9 mm notch at shell-frame phase 36°, with 0.8 mm tangential and
0.35 mm radial clearance and ≥0.6 mm wall remaining behind the notch. The
notch cutter must follow the tapered inner wall and open only through the local
oblique rim height. Its shell-frame width expands to approximately 4.32 mm on
Shell A and 4.74 mm on Shell B to enclose the tilted key; never span from the
global short rim to the global long rim, which creates a long wall channel and
slicer floating regions. Build the skirt tab in the joint/print frame inside
the upper 5 mm of the skirt/band with a 45° underside; do not restore
multi-pin lower clocks or a skirt-only alignment.
`backend/generator/boucle_lamp_fusion.py` owns the full-resolution Fusion
interchange package. Keep its nine watertight OBJ bodies separately named and
at the finished assembly origin. It is mesh interchange, not parametric
F3D/STEP; fuzzy skin remains slicer metadata and must not be baked into fit
geometry.

The standalone Golf Tee lamp is under `design/golf-tee-lamp/`.
`backend/generator/golf_tee_lamp.py` generates a five-plate all-PLA P2S project:
one-piece Ø175 Jade White PLA Basic shade with constant-thickness dimples
(1.6 mm solid shell, 0% sparse infill; 1.4 mm depth; relaxed equal-area layout;
exact centre/profile samples; dual-surface displacement)
and **0.4 mm bayonet lock detents**; a Caramel Matte tee with integrated MH001
pocket (widened to Ø62.1 for the reflector), a radial 7.5 × 5.5 mm floor chase
for the puck's side-exit lead, and a **21 × 12 mm rounded controller passage**
through the Ø28 neck. The controller is 55.7 × 19.65 × 10.65 mm; do not restore
the Ø18 circular bore, which cannot pass its ~22.35 mm diagonal. The matching
reflector must retain its aligned 8.1 mm side notch. Feed the rigid controller
straight through the tee and base centre; only the flexible lead occupies the
7.2 mm underside trench. The tee also carries
**Ø5 bayonet pins with R1.2 root fillets** on PCD 70, and a **4-slot spring snap
foot**. The physically too-tight Ø74/Ø77 snap is superseded by a Ø73.4 shaft /
Ø76.4 bead, Ø75.8 insertion throat, Ø76.8 mouth and Ø77.4 groove: 0.8 mm
diametral shaft clearance, 0.30 mm/side throat interference and 0.50 mm/side
groove clearance. The first revised base still narrowed to the Ø74.2 shaft
socket above the groove and would not accept the tee; never restore that
pre-groove throat. Print the
tee **snap-foot-down** with its 8 mm brim and supports off.
Its Ø48→Ø90 cup underside and Ø90→Ø110 seat underside are 45° self-supporting
flares, and its bead has a 45° lower lead-in. Never restore the former
seat-down orientation: the three pins extend below the inverted seat and were
the only first-layer islands, causing immediate spaghetti. A Grass Green base
(120 × 120 mm rounded square × 18 mm) has a ballast pocket + **1.2 mm
111.7→109.3 mm tapered cover**, 110 mm square felt recess, 7.2 mm
underside cable trench, and top-face fuzzy turf paint that **clears the snap
entry**. Print the base **underside on bed** with **tree supports** for the
ballast pocket roof; the cover seat narrows inward over a **45° × 1.2 mm
lofted ramp** (no horizontal ledge cantilever). Insert the cover small-face
first until its large outward face settles behind the felt. Snap groove lips
use a **45° upper chamfer**. Plus an
Ivory White **0.8 mm reflector cup**. The shade uses a **flat
bed ring + 45° self-supporting cone** into the sphere so exterior supports stay
off; the tee seat is a matching flat-ring rebate. **Variable Layer Height is
baked into Plate 1** (`layer_heights_profile.txt`: 0.20 mm → 0.08 mm on the top
~20%). Plate 1 seams are **Back + scarf Contour and Hole**, **Arachne**,
**Inner/Outer** wall order, and **4 mm wipe** — never Random on the dimpled
sphere. Shade fuzzy is **outer walls only** at **0.04 mm / 0.08 mm** so dimple
edges stay sharp and the bayonet seat stays crisp. Print the ball opening-down.
The 1.2 mm ballast cover and 0.8 mm reflector are fully solid from their shell
layers and wall loops; keep sparse infill at 0%. Do not restore 100% gyroid:
Bambu Studio 2.7 rejects that combination. One object per production plate. Not
production-ready until bayonet, snap, ballast and lit glow pass physical checks.

County clicker physical gates: 1.25 mm moving-top clearance, ≥1.50 mm material
around the 16.4 mm switch shoulder, ≥45% moving-top area retention, and a
1.20 mm moving-top neck test. Counties may enlarge without a fixed cap to pass
these gates. Keep official mainland shell boundaries; trim fragile lobes from
the moving top only. The seven projects in `county-clickers/physical-test-revision/`
must pass before replacing the complete 32-county package.

