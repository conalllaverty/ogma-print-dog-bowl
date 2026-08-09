# Oggie Spin — Broken Ring Illusion (ACTIVE)

**This is the only live Oggie Spin design.** Everything in
[`../archive/`](../archive/) is superseded and must not be built from.

[`Oggie_Spin_Broken_Ring_Illusion_P2S.3mf`](./Oggie_Spin_Broken_Ring_Illusion_P2S.3mf)
is the complete printable spinner project for the Bambu Lab P2S — nine plates,
17 objects, seven filament slots.

Status: **rebuilt on a through-slot with the clip on the exposed far face,
slice-validated, physical approval pending.** The slot's 2 mm bottom shelf, the
underside battery-cover clip and its five welding defects, and two wrap-mounted
cantilever revisions are all gone; see [`../ARM-RETENTION-REVIEW.md`](../ARM-RETENTION-REVIEW.md)
for the diagnosis and the as-built numbers.

## Contents

| File | What |
| ---- | ---- |
| `Oggie_Spin_Broken_Ring_Illusion_P2S.3mf` | the nine-plate P2S project |
| `broken-ring-meshes/` | 17 printable STLs |
| `broken_ring_variant_validation.json` | dimensional + interference report |
| `release-sequence.png` | how an arm comes off, stepped through the built mesh |
| `oggie-spin-concept.svg` | current blueprint: assembly, joint, modules, bearing stack |
| `oggie-spin-thumb-mechanisms.svg` | the four finger-pad interfaces; **B, push-and-turn bayonet**, is what ships here |
| `snap-clip-sections.png` | sections through the arm latch, taken from the built mesh |

## The optical pattern

Two 1.1 mm broken tracks on the core and one on the five arms, as flush
0.32 mm-deep Ivory White Matte inlays. Load the optical inlays in **slot 7**.

The underside `BR` identifier is **removed**. It existed to tell printed optical
variants apart, and Broken Ring is now the only live design, so it distinguished
nothing — and the pixel font read as noise on the finished face. `IDENTIFIER` in
`oggie_spin_broken_rings.py` is set to `None`; put a code back there if a second
variant ever ships alongside this one. Plates 1 and 5–9 use two colour changes and a
prime tower.

| Ring | Radius (mm) | Dashes | Phase (°) | Target |
| ---- | ----------: | -----: | --------: | ------ |
| inner core | 15.5 | 15 | 0.0 | core |
| outer core | 18.5 | 20 | 9.0 | core |
| arm | 22.5 | 25 | 7.2 | arm |

Ring width 1.1 mm, duty 0.52, inlay depth 0.32 mm (2 × 0.16 mm layers).

**The dashes stand 0.32 mm proud of the top face**, on both the core and the
arms — they are no longer flush. `INLAY_PROUD` in `oggie_spin_broken_rings.py`
sets it; 0 restores the flush inlay. The raised cap is derived from the flush
inlay's own footprint at the top face, so it automatically respects wherever the
base actually exists: the arm slots cut the core's outer ring, and the arm ring
only spans ±20°. Volume added is recorded in the validation JSON, and the
base/inlay partition check subtracts it so it still verifies the partition.

**Keep the 15/20/25 pattern unchanged. Do not add a fourth ring.**

## Plates

1. Broken-ring core — five through-slots with open female pockets on the underside, entry channels, bottom-edge relief, top lead-in chamfer, R188 seat
2. Press-fit outer-race retaining ring
3. Tough+ split-collet through-axle hub + through-bore receiver hub
4. Two identical 6.4 mm socketed thumb pads
5. Marine Blue wrap-around clip-lock segment + arm-ring inlay
6. Lemon Yellow segment + inlay
7. Mandarin Orange segment + inlay
8. Grass Green segment + inlay
9. Lilac Purple segment + inlay
10. **Five-up arm batch, one colour** — five arms plus their five inlays on one
    plate, for stocking a pick-and-mix. Two filaments only, so the purge tower
    stays small and the colour change is confined to the top four layers. Run it
    five times in five colours. It replaces the old standalone
    `Oggie_Spin_5x_Broken_Ring_P2S.3mf`, which is no longer emitted.

Each segment has identical geometry and mass. Its tongue is now full height
(14 mm) and passes right through the core. Outside the slot it wraps flush
around the core (R20.30–R24.5, ±20°) for the full 14 mm core height. Reassign
any arm plate to another Bambu Matte colour without changing the mechanical
design.

## Print configuration

- Bambu Lab P2S, 0.4 mm nozzle
- Bambu PLA Matte for core, ring, pads and the five colour blocks
- Bambu PLA Tough+ for both cartridge hubs
- Bambu PLA Matte Ivory White for the optical inlays (slot 7)
- 0.16 mm layers, 6 top and bottom layers
- 5 walls on core / cartridge / pads / ring; **2 walls on the clip-lock blocks**
- 25% gyroid default infill; **100% grid infill on all five colour blocks**
- Supports off
- **Arms print flush top face UP — do not flip them.** The flip that earlier
  revisions called for existed to dodge an overhang above the retired 2 mm slot
  shelf. With the shelf gone it does the opposite: it lifts the clip beam's
  first layer 10.35 mm into the air, which is exactly the floating cantilever
  Bambu Studio warned about. `_flip_arm_for_print()` is now a no-op and
  `printability.assert_rigid()` will reject any transform that tries to bring it
  back as a mirror.

All nine plates slice in Bambu Studio 2.7.1 with empty warning fields.

## Additional hardware

1 × R188 bearing — 12.70 × 6.35 × 4.76 mm. **The only non-printed part.**

## Assembly

1. Insert the R188 into the Ø12.82 core pocket from the top with controlled
   hand pressure until its outer race reaches the lower shoulder.
2. Press the Ø15.22 retaining ring down the counterbore until it contacts only
   the bearing outer race.
3. Inspect the four Tough+ collet fingers. Reject the part if any root is
   cracked, fused across its 0.55 mm slots or visibly under-extruded.
4. Insert the split-collet hub from below; its Ø8.40 spacer stops on the R188
   inner race. Stop rather than hammering if the Ø6.40 axle binds.
5. Place the receiver hub from above and press the hubs together until the
   Ø6.80 bead emerges fully beyond the receiver's outer face. Confirm ~0.05 mm
   axial freedom and a 1.6 mm hub-to-core gap on both sides.
6. Install either pad on either side. Align with the three hub gates, seat by
   hand, rotate 30° into the terminal pockets. Pliers must not be required.
7. Align each solid dovetail tongue above a core slot and press down. The arm
   drops almost freely — the barb runs down the slot wall's entry channel
   without deflecting — then clicks over the retaining lip in the last 2 mm at
   about 0.8 N, one finger.

**To remove an arm, two ways.** Press the barb where you can see it — turn the
spinner over, put a nail into the open recess beside the barb and push it
outward 0.45 mm, then lift. Or just pull the arm straight up firmly: the 45°
retention face cams the barb out at about 1.4 N. There is no button, no tool and
nothing to aim at — that is deliberate. An earlier draft of this design claimed
a fingernail could be worked into the void to lever the tab out; it cannot. The
inner gap beside the beam is 0.35 mm and a fingernail is about 0.5 mm, and
widening it would leave a 0.2 mm wall. The straight pull is the release.

## The arm latch

**The tongue passes right through the core, and the clip lands on the exposed
far face.** The slot's old 2 mm bottom shelf is gone — that shelf stopped the
tongue short of the underside, which is why two earlier revisions had nowhere
visible to put the latch.

A male barb on a cantilever at the tongue's inner tip springs into a **female
pocket cut as an open recess in the core's underside**, and its top face catches
on the recess roof. Five of them, one per arm, at 72°. They read as five radial
features on that face.

Because the recess is open, the barb is visible when engaged and you can press
it. The recess is 1.60 mm deep against a 0.45 mm engagement — the extra 1.15 mm
is finger room, so a nail goes in beside the barb and pushes it outward.

| | | |
| --- | --- | --- |
| Beam | 0.80 → 0.40 mm tapered, 3.45 mm deep, 7.70 mm free | measured on the mesh |
| Barb lever arm | 6.40 mm root-to-barb | the barb is inboard of the beam tip |
| Engagement | **0.50 mm** | verified 0.500 on the exported mesh |
| Release travel | 0.80 mm — 0.30 mm of margin | |
| Entry / retention | 30° / 45° | |
| Insertion force | 0.88 – 1.54 N | bracket, see below |
| Pull-off force | **1.58 – 2.75 N** | bracket, see below |
| Surface strain | 1.06 % → 25.1 MPa | **2.11 : 1**, 47 % of flexural strength |
| Barb contact face | 12.7 mm² | +18 % over the first print |
| Radial play | **0.151 mm** | was 0.306 on the first print |
| Tongue inner clearance | **0.10 mm** | `SLIDE_INNER_RADIAL_CLEARANCE` — sets the rock |
| Axial free lift | 0.119 mm | barb top to lip underside |
| Tip wobble (pitch) | **0.85° → 0.36 mm at the tip** | was 1.68° / 0.72 mm |
| Yaw | ±0.018° | the dovetail; 40× tighter than the rock |
| Recess | 1.75 mm deep, open on the underside | |

**Forces are quoted as a bracket, and that is deliberate.** The standard tapered
cantilever formula puts the load at the beam's free tip; our barb sits 1.30 mm
inboard of it, so the real lever arm is 6.40 mm, not 7.70 mm. Force goes as
1/L³, so the two assumptions differ by 1.7×. The truth is between them and
nearer the upper figure. Earlier revisions quoted the lower number alone as if
it were exact.

Every force above is emitted by `clip_forces()` in `oggie_spin_complete.py` and
lands in the validation JSON under `snap_clip_forces`. **Do not hand-write a
force into this file.** Two earlier revisions carried a 2.20 N pull-off that the
geometry never supported — it had been derived from the barb's total 0.65 mm
protrusion instead of the 0.45 mm the core actually demands. The beam was also
described as 0.95 × 2.05 mm when it is built 0.80 × 3.45 mm; those two happen to
give almost the same `b·t³`, which is why the error survived so long.

### Why engagement stops at 0.50 mm

**`CLIP_ENGAGEMENT` must not go past ~0.50 mm on this beam.** Stress in the beam
goes as `t·y/L²`, so engagement buys wear budget at a linear cost in stress:

| Engagement | Peak stress | Margin | % of flexural strength |
| ---: | ---: | ---: | ---: |
| 0.45 mm | 21.9 MPa | 2.42 : 1 | 41 % |
| **0.50 mm** | **25.1 MPa** | **2.11 : 1** | **47 %** |
| 0.55 mm | 26.8 MPa | 1.98 : 1 | 51 % |
| 0.60 mm | 29.2 MPa | 1.81 : 1 | 55 % |

PLA's fatigue limit is roughly 30–40 % of static strength. Past ~0.50 mm the
**beam** becomes a life-limited part rather than just the barb, and the failure
mode changes from "gradually loosens" to "snaps off". 0.60 mm was tried and
rejected for exactly this reason. If more retention is genuinely needed, the
lever is beam *depth* (`CLIP_DEPTH`, linear in force, zero strain cost), not
engagement and not thickness.

Nothing protrudes past the underside: the barb sits 0.20 mm inside the recess.

Sized against the published Bambu PLA Matte data sheet: X-Y flexural modulus
2360 ± 250 MPa, flexural strength 53 ± 6 MPa, elongation at break 14.8 ± 4.2 %.
The Z figures are 1770 MPa / 29 MPa / 4.8 %, so keeping the beam in **in-plane**
bending is worth roughly 3× the ductility on the one part that flexes.

The geometry is Cartesian, not polar: the slot is a straight-edged trapezoid, so
its inner wall is the line x = 13.80, not an arc.

### Entry channel

The slot's inner wall carries a 1.60 mm channel from the core's top face down to
a 0.90 mm retaining lip above the recess. The barb drops through undeflected and
only cams over the lip in the last 2 mm — 1.9 mm of loaded travel instead of
dragging down the whole wall.

## The tongue

**One solid dovetail**, R14.00–20.75, uniform 0.18 mm clearance per side.

The three-rail split — central dovetail plus two thin guide rails — is retired:
physical testing said it does not work well and a single solid piece does. Three
rails meant three independent tolerance stacks and three thin features that can
shave, and the gaps between them let the arm rock before any one rail took load.
One solid tongue is a single surface pair, engages the whole slot wall, and
cannot rock. It carries all the centrifugal load; axial hold is the snap clip's job. No friction ribs, no interference anywhere on this face.

### The rocking, and why a second rail is the wrong fix

The arm's remaining looseness is **rocking in the radial–vertical plane** — the
tip nodding up and down — and it is set by exactly one number:
`SLIDE_INNER_RADIAL_CLEARANCE`, the gap between the tongue's inner face and the
slot's inner wall at x 13.80. Tip wobble is linear in it:

| clearance | pitch | tip wobble |
| ---: | ---: | ---: |
| 0.20 mm (first print) | 1.68° | 0.72 mm |
| 0.14 mm | 1.18° | 0.51 mm |
| **0.10 mm (shipped)** | **0.85°** | **0.36 mm** |
| 0.08 mm | 0.68° | 0.29 mm |

It changes nothing else: engagement stays 0.50 (`CLIP_BARB_TIP_X` is defined off
the wall, not off this face), and the push-through stop and retention bite are
untouched.

**Two things that look like fixes and are not.** A second dovetail rail
constrains *yaw*, which is already ±0.018° — forty times tighter than the rock.
It would add a third tolerance stack and another thin feature to print, for zero
gain on the axis that actually moves. And the wrap clearance has no effect at
all: measured across 0.30 → 0.18 with the inner clearance held, the pitch does
not move by a thousandth of a degree. The wrap is not a bearing surface.

## Barb wear — the life-limiting mode

**First print wore the barb visibly after ~80 insert/remove cycles.** For a
product whose whole premise is swappable arms, that is the number that matters
most, and it is nowhere near enough.

The wear is on the **arm**, not the core. That is the correct side — arms are the
replaceable part and the core is not — but it still has to last.

**What is doing the damage:** the straight-pull release drags the barb across the
retaining lip through the full engagement depth under full spring load, every
single time. Insert plus remove is roughly 1 mm of loaded sliding per cycle, so
80 cycles is ~80 mm of sliding on a feature a couple of millimetres across. Both
of the barb's ramps run in Z, so they are stair-stepped across layer lines, and
those step corners are what shear off first.

Wear depth is volume over area (Archard), so **contact area is the free lever** —
it costs nothing in force, stress or release feel:

- barb widened from 2.20 to 2.60 mm (`CLIP_BARB_HALF_WIDTH` 1.10 → 1.30), contact
  face 10.7 → **12.7 mm²**, so the same wear volume costs ~18 % less depth
- engagement 0.45 → 0.50 mm, so there is 11 % more to lose before it stops holding
- radial play halved, which removes the rocking that worked the barb sideways

**Print the arms' bottom 3.5 mm at 0.08 mm layers.** This is a slicer height
range, not a geometry change, and it is the single cheapest thing to try — it
halves the stair-step height on both ramps, which is where the abrasion starts.
It costs a couple of minutes per arm.

If that is not enough, the next levers in order are: radius the barb crest and
ramp transitions; a second barb on the far side of the tongue tip to halve the
per-barb load; and only then a material change for the arms.

## Printability

`backend/generator/printability.py` runs a layer-by-layer manufacturability
audit on every part before it is exported, in the same shape a slicer does:
section at each layer height, diff each footprint against the one below, and
classify anything new.

The measure that matters is **anchor ratio** — what fraction of a new region's
outline actually sits on the layer below. Distance-to-support cannot tell a
bridge from a cantilever: a beam floating in the middle of a 1.85 mm void is
only ~1 mm from solid material either side, so a distance metric calls it a
short bridge. It is not — nothing is under it. Anything under 18 % anchored is
**blocking** and the build raises rather than writing a mesh.

It is calibrated against the one case we know the answer to: fed the old flipped
arm, it blocks with *"4.41 mm² of new material with only 5 % of its outline on
the layer below"*. Fed the shipped orientation, it passes.

All 11 non-inlay parts are clean. The warnings that remain are understood:

| Part | Warning | What it actually is |
| --- | --- | --- |
| core | 5 × 4.16 mm² flat ceiling at Z 2.32 | the roof of the five clip recesses — a 1.30 mm bridge anchored on 70 % of its outline. This is the retention face the barb catches, so check it on the sanity plate. |
| core | 0.72 mm sliver at Z 0.44, 5 places | the outboard tip of the push-through ledge, where its 45° ramp tapers out. Fully supported, merges into thick material. |
| core | 61 mm² at 30–45° below Z 0.55 | the bottom-edge foot relief chamfer. Under 45°, prints unsupported. |
| arms | 0.41–0.73 mm feature over Z 0.2–3.4 | the clip beam itself. It is a spring; it is *meant* to be thin. The 0.40 mm tip is one extrusion width and will print as a single bead. |

## Sanity plate

`sanity-plate/` is a core sector plus one arm — **6.7 g, about 15 minutes**.
Print it before committing to the nine plates.

Four full revisions of this joint were built on arithmetic alone, and a mirrored
export, a missing push-through stop and a floating cantilever all reached the
slicer or the bed. Every one of them would have been caught by one arm against
one slot.

```bash
.venv/bin/python backend/generator/oggie_spin_sanity_plate.py \
  --out design/modular-spinner/active/sanity-plate
```

What to check, in order:

1. the arm snaps in with light finger pressure (~0.8 N)
2. push hard — the ledge stops it, the arm does not slide through
3. pull straight up — it should release at about **1.4 N**, no tool. This is the
   number to trust least; if it feels wrong, see `CLIP_ROOT_THICK` above.
4. turn it over — the barb is visible in its recess and you can press it
5. look at the clip beam's first layers — no droop, not welded to the tongue
6. look at the recess ceiling — the 1.30 mm bridge should be flat, not sagging

The script re-loads the exported STLs from disk and assembles them with
rotations only, so what it validates is the file you are about to print, not the
in-memory model it came from.

## Validation

`broken_ring_variant_validation.json` and the report from
`oggie_spin_complete.py` record:

- **seated interference with the core: 0.000 mm³** on all five arms. A correct
  snap-fit touches nothing; the retired clip reported 0.327 mm³ and that number
  was the jam.
- **a layer-by-layer printability audit of every part**, under `printability`.
  The build now *refuses to export* a part the slicer would reject.
- **single-shell check.** The core used to export as six shells — the body plus
  five push-through ledges touching the slot walls with zero gap and zero
  overlap. Bambu Studio unions per-layer footprints so it sliced solid and this
  never surfaced as a warning, but an STL of kissing shells is one clearance
  change away from five loose parts on the bed. `_weld_shells()` fuses them and
  the audit now blocks on detached shells. Optical inlays are exempt: they are
  genuinely 30 and 4 separate dashes.
- single solid dovetail tongue, 0.18 mm/side, R14.00–20.75, full 14 mm height
- release margin 0.25 mm against a 0.20 mm floor; minimum travel space 1.00 mm
- retention bite confirmed non-zero under lift; clip free on both faces
- arm volume spread **0.0 mm³** across all five arms
- maximum base/inlay overlap 0.0 mm³
- release margin 0.25 mm against a 0.20 mm floor
- minimum inner gap 0.35 mm, minimum travel space 0.95 mm along the beam span
- retention bite confirmed non-zero under lift
- adjacent arms clear, 17 watertight meshes, 9 plates, 7 filament slots

The validator no longer masks the hook zone before measuring, and it now walks
the beam span asserting open air on both faces — a weld adds no interference,
so no volume check alone can catch one.

## Shared mechanical dimensions

The tolerances this design shares with the retired clip-lock package — bearing
seat, cartridge, thumb bayonet, rail clearances — are recorded in
[`../archive/clip-lock-complete/dimensions_and_validation.json`](../archive/clip-lock-complete/dimensions_and_validation.json).
That file is archived because its 3MF is archived; it remains the dimensional
reference for the mechanism.

## Regenerate

```bash
.venv/bin/python backend/generator/oggie_spin_broken_rings.py \
  --out design/modular-spinner/active
```

> The standalone `Oggie_Spin_5x_Broken_Ring_P2S.3mf` is retired — the five-up
> batch is plate 10 of the main project now, so there is no second file to keep
> in step. A rebuild deletes any stale copy.

### Plate grid — the one that bit us

**Bambu Studio lays plates out in a grid of `ceil(sqrt(plate_count))` columns.**
That is 3 columns at nine plates and **4 at ten**, so adding the five-up batch
silently moved every plate from 4 onward onto somebody else's bed, and plates 9
and 10 onto no bed at all. The project still opened, still sliced and still
reported no warnings — the objects were just in the wrong place.

`PLATE_COUNT` now drives `PLATE_COLUMNS`, a mismatch against `VARIANT_PLATES`
raises at import, and `_assert_objects_on_their_plates()` checks every object
lands inside its own 256 mm bed before export. Worst current reach from a plate
centre is 27.0 mm.

### Purge volumes

The project shipped a `flush_volumes_matrix` of **all zeros** — Bambu's
"partial purging volume set to 0 … may cause color mixing" warning. Zero purge
means the first millimetres of Ivory White carry the previous colour, which on a
white-on-colour optical pattern is not a cosmetic problem. `_flush_matrix()` now
generates it from the actual filament hex codes, scaling with colour distance
and penalising transitions to a *lighter* colour: 149–268 mm³ between the
colours, **306–323 mm³ into Ivory White**. `flush_into_infill` is on, so the
purge is buried in the arms' 100 % grid infill instead of all going to the tower.

### Five-up plate layout and travel settings

The five arms sit in a 3+2 quincunx on a 21 × 24 mm pitch: a 54 × 41 mm group
with a 6.9 mm minimum gap, centred on the plate. Tight keeps per-layer travel
short; the gaps keep the fan and nozzle skirt clear. Printing five at once also
gives each layer roughly five times as long to cool, which is a real quality win
for the 0.40 mm clip beam and the recess bridge.

Because the nozzle now crosses finished walls constantly — which the nine
single-object plates never made it do — the project settings are tuned for it:
`z_hop` 0.6 mm **Slope Lift** (up from 0.4 Auto Lift; 0.4 is not enough
clearance once there are five 14 mm towers to catch a curled edge on),
`reduce_crossing_wall` on, `retract_before_wipe` 70 %, prime tower on, print by
layer. These live in the print profile so they are global, but none of them hurt
a one-object plate.

## Batch manufacturing project

`Oggie_Spin_Batch_x10_P2S.3mf` makes **ten complete spinners** in eight plates,
against the shipped project's ten plates for one. Regenerate with:

```bash
.venv/bin/python backend/generator/oggie_spin_batch.py \
  --out design/modular-spinner/active --units 10
```

`--units` is free: 5 for a cautious first run, 20 still fits one plate per part
type. The generator refuses to emit a plate whose parts overlap or fall off the
bed, and it refuses to emit a batch that is not a **matched set** — 1 core,
1 ring, 2 hubs, 2 pads and 5 arms per unit, or it raises.

| Plate | Contents | Filaments | Layer |
| ----- | -------- | --------- | ----- |
| 1 | 10 cores + 10 retaining rings | 2 | 0.16 |
| 2 | 20 Tough+ cartridge hubs | **1 — zero purge** | 0.16 |
| 3 | 20 thumb pads | **1 — zero purge** | 0.20 |
| 4–8 | 10 arms + inlays, one colour each | 2 | 0.16 |

**The geometry is byte-identical to the shipped project** — all 16 unique meshes
hash the same as their single-unit counterparts. A batch part is a validated
part; nothing was re-tuned for production.

### Where the win is, and where it isn't

**Packing.** Ten cores on one plate is a 10× cut in per-run overhead — bed heat,
purge, start/end sequence, and a trip to the printer. That is the whole prize.

**Filament grouping** is second. The rings ride on the core plate because they
use the same filament as the core body, which removes a plate for free, and two
plates are single-filament so they purge nothing at all.

**Layer height is not where the win is**, and the arithmetic is worth recording
so nobody re-litigates it. The parts that could safely take 0.20 mm are 18 % of
the batch by volume, so the entire saving is 3–4 % of run time. Only the thumb
pads take it. Held at 0.16:

- **collet hub** — four spring fingers with 0.55 mm slots. Same class of part as
  the arm clip beam, and layer definition is what makes a printed spring behave.
  Not worth an untested variable for ~4 minutes.
- **retaining ring** — a press fit; its critical dimension is an XY diameter so
  layer height would not hurt it, but it is 1.1 cm³ across the whole batch.
- **cores and arms** — the optical inlay is 0.32 mm, exactly two 0.16 layers.

Arms keep 2 walls and 100 % grid infill, unchanged, because the five-arm mass
match depends on it.

### Batch figures

309 g per batch of ten, 30.9 g per spinner. Every part sits at least 25 mm
inside the bed edge, clear of the exclusion zones and the purge chute.

## Solo — one-piece variant

`Oggie_Spin_Solo_OnePiece_P2S.3mf` is the same spinner with the core and arms as
**one printed body**. Four plates instead of ten. Regenerate with:

```bash
.venv/bin/python backend/generator/oggie_spin_onepiece.py \
  --out design/modular-spinner/active
```

Gone: five arm slots, dovetail tongues, clip cantilever beams, snap barbs,
underside pockets, entry channels, retaining lips, push-through ledges, wrap
clearance. Unchanged: the R188 pocket and its lead-in, the retaining ring press
fit, the Tough+ cartridge, the bayonet thumb pads and the broken-ring pattern.

**Ø52.6 mm, 26.7 g, single shell, printability audit clean with no findings.**

### Why it might matter more than it looks

The modular arm fits inside the EN 71-1 small parts cylinder, and that is what
forces the 3+ age grade and the choking warning. The Solo body cannot fit —
the generator asserts it. That does **not** make the toy compliant on its own:
the bearing, hubs, ring and pads are still small parts, they are merely captive
rather than designed to come off, and EN 71-1's torque and tension tests decide
whether captive holds. But it removes the one hazard that was designed in.

It also has nothing to wear out, and it is balanced by construction — five
separately printed arms can vary in mass, five arms that are one solid cannot.

**What it costs is the pick-and-mix colour range**, which is the modular
product's whole point. Arms and core coexist at every layer, so separate
filaments would mean a colour change on all ~87 layers — more purge than the
part weighs. The optical inlay survives because it only occupies the top
0.64 mm. Treat Solo as a second SKU, not a replacement.

### The root fillet, and two bugs worth remembering

`ROOT_FILLET = 2.5` mm rounds the corner where each arm meets the core. The
modular design never needed one — the arm sat in a slot. Fused, that junction is
a sharp inside corner: a stress riser exactly where a drop test loads it. The
fillet only grows the arm root; the gap between arms stays at R20.00 even at
3.5 mm. Lower it to ~1.5 mm for a crisper silhouette at some cost in root
strength.

Two things went wrong building this, both caught only by **rendering the result**:

1. **`complete._loft_polygons()` lofts by convex hull.** Fine for the small
   convex features it was written for; fed a five-arm profile it returns a
   solid decagon. The arms vanished and every check still passed. The Solo body
   is built from straight extrusions of the real polygon instead, with a stepped
   chamfer — at 0.16 mm layers a 0.40 mm chamfer is 2.5 layers, so the printer
   quantises it to a staircase anyway.
2. **Arms seat at −90 + 72k, not 72k.** `_arm_installed_orientation()` does not
   rotate about Z. Assembling with 72k alone leaves every arm stuck to the
   outside of the core at the wrong angle with all five slots still open —
   386 mm³ of interference per arm. The generator now asserts each arm's
   interference with the core is zero before using it.

The validator now measures **section area over convex hull** (0.756; anything
above 0.90 means the arms have been swallowed) and checks that all five gaps
between arms still reach the core OD. Both were written after the fact — the
original checks all tested what was supposed to be *filled* and none tested what
was supposed to stay *open*.
