# Bouclé Stack lamp — production print

These are the complete ready-to-print parts for a Bambu Lab P2S with a 0.4 mm
nozzle. Shells and rings use Bambu PLA Matte Bone White; the hidden diffuser
uses Bambu PLA Basic Jade White for higher transmission; the leg frame and
removable LED cradle use Bambu PLA Matte Dark Chocolate.

Open `Boucle_Stack_Lamp_All_Plates_P2S.3mf`. It contains eight named plates,
one printable object per plate:

1. Shell A
2. Shell B
3. Shell C
4. A→B halo ring
5. B→C halo ring
6. LED diffuser baffle
7. Leg frame
8. LED cradle

The combined project has three preassigned filament slots: Bone White Matte
for Plates 1–5, Jade White PLA Basic for Plate 6, and Dark Chocolate Matte for
Plates 7–8. Map those three slots to the matching loaded spools before sending
each plate.

The individual projects remain under `plates/` as fallbacks. Every plate and
fallback file contains exactly one object. This intentionally removes the long
open-air travels between coupon pieces that produced the recurring strings.
The project also sets 0.8 mm retraction at 30 mm/s, layer-change retraction,
2 mm wipe, and avoid-crossing-wall travel. Bambu treats its infill-retraction
policy as project-wide, so the combined 3MF disables reduction on all eight
plates. The individual ring, leg-frame and cradle fallbacks also disable it;
eligible internal detours retract instead of using the stock `Auto`
suppression.

## Before printing

- Dry all PLA spools according to Bambu's guidance. Repeated fine strings on
  otherwise healthy prints are commonly moisture-sensitive.
- Do not auto-orient any part. Shells and cradle are base-down; the leg frame
  is intentionally inverted with its top seat on the bed and legs growing
  upward.
- Keep supports off.
- Keep the supplied 8 mm outer brim.
- The project selects **Textured PEI Plate** at the stock filament temperature.
- Plates 1–5 and 7–8 use stock `Bambu PLA Matte @BBL P2S`; Plate 6 uses stock
  `Bambu PLA Basic @BBL P2S`.
- Shell C is intentionally 1.2 mm. Confirm the 1.2 mm glow-coupon sector showed
  no pinholes or unacceptable weakness before committing to the full print.
- Plates 4–5 contain the new matching-band ring architecture. Print B→C first,
  then dry-fit both complete rings before committing adhesive or reusing the
  previous assembly procedure.
- No slicer setting can guarantee zero hairs from wet filament. If the dried
  Bone White spool still strings on B→C, run a temperature test before the
  longer A→B ring; do not compensate by increasing retraction beyond 0.8 mm
  without a controlled test.
- Confirm the real LED module, cable and strain relief passed the Plate-4
  hardware preflight before printing the full cradle.

## Surface and slicing

- Shells: 0.20 mm layers, Arachne, 0% sparse infill, 60 mm/s outer wall.
  Shells A/B are 1.6 mm; Shell C is 1.2 mm with its original reinforced 4 mm
  base/register interface retained.
- Exterior sidewalls only: fuzzy skin 0.30 mm thickness / 0.80 mm point
  distance.
- Smooth regions: interiors, bottom 4 mm, oblique rim 4 mm, and all joint
  surfaces.
- Halo rings: smooth, 0.16 mm layers, 15% gyroid, four walls.
- A→B uses a straight continuous 22 mm-deep conformal bond skirt, twenty
  1.2 mm straight radial webs and a bed-rooted central collar. The skirt
  replaces the former scarfed tabs and their visible triangular shadows; the
  straight collar architecture also removes the scalloped crown. The central
  light bore remains open without supports or floating layer islands. Its
  hidden tapered tab clocks Shell B to the correct rotation.
- B→C uses five evenly distributed bed-rooted radial webs. Its complete shallow
  band leaves 1.2 mm above Shell B's lower register, avoiding the A→B hardware
  without a cut-off outer wall. Its matching tab clocks Shell C. Both
  upper-shell notches are open-bottom and support-free.
- LED diffuser: Jade White, smooth Ø76 × 1.2 mm disc, 0.20 mm layers and six
  solid top/bottom layers. Its three Ø6 posts end in Ø3 × 2 mm locating pegs.
  Print disc-down with the pegs at the top, then flip it for assembly.
- Leg frame: Dark Chocolate, 0.20 mm layers, five walls and 20% gyroid. Its
  three embedded joints form one body and remain outside the cradle bore; the
  USB opening sits 20° beside the single rear leg, leaving the front gap open.
  The Ø116 × 4 mm seat carries a 1.0 mm annular locate groove for bonding
  Shell A; its outer wall clears the shell flare at groove depth (±0.25 mm per
  side). The seat ends in a 0.6 mm radial cradle stop followed by a 1.9 mm-high
  45° bore ramp. The inverted Ø94 wall therefore opens gradually without an
  unsupported cliff or sacrificial puck. Keep support off and bridge at
  20 mm/s: support generated the only unretracted >5 mm travels and caused
  stringing inside the inset.
- LED cradle: Dark Chocolate, 0.20 mm layers, four walls and 15% gyroid. Its
  retaining flange is 4 mm to match the deeper seat. A 1.9 mm-high 45°
  underside ramp leaves only a 0.8 mm final lip, and the anti-rotation key
  reaches full depth through its own 2 mm-high 45° ramp. Three Ø3.6 × 2.4 mm
  blind sockets positively locate the diffuser with 0.6 mm total diametral
  clearance and 0.4 mm bottom clearance.
- Supports and prime tower: off.

The verified combined-project P2S slice totals approximately **356.51 g** and
**14 h 32 min**:

- Shell A: 48.54 g / 2 h 12 min
- Shell B: 35.00 g / 1 h 35 min
- Shell C: 28.33 g / 1 h 26 min
- A→B halo ring: 64.94 g / 2 h 54 min
- B→C halo ring: 24.20 g / 54 min
- LED diffuser baffle: 10.24 g / 32 min
- Leg frame: 75.54 g / 3 h 01 min
- LED cradle: 69.72 g / 1 h 58 min

All eight CLI slices returned `Success` with empty project warning fields and
no generated support. Studio's CLI still prints its known non-fatal `Invalid T
command (T65535)` preview-parser line after export. Every model travel of at
least 5 mm is retracted in the generated G-code. Both halo rings generated no
bridge, overhang-wall or support feature. Plate 7's Shell A locate groove is a
1.0 mm bed-face recess; its short ~2.6 mm radial floor bridges at 20 mm/s after
the inner and outer lands, and the Ø94 bore still opens on the narrow stop plus
45° ramp. The support-free Plate 7 G-code has zero unretracted model travels
of at least 5 mm.
Plate 8 likewise generated zero bridge moves at its former flange/key failure
layer (Z24.2).

## Dry assembly

Remove the brim and any isolated hairs from every smooth fit surface. Dry-fit
the complete stack without adhesive first, then bond Shell A to the plinth
before the halo joints:

Stand the leg frame on its three feet with the two-leg gap facing forward. Dry-fit
the cradle, diffuser and Shell A: Shell A's 1.6 mm wall must drop into the
1.0 mm annular locate groove, and the cradle flange must still pass through
Shell A's opening. Then remove the cradle and diffuser before any adhesive.

Wipe a thin two-part epoxy film on the groove floor only. Seat Shell A, wipe
squeeze-out from the inner and outer lands, and leave it undisturbed until
cured. Do not get adhesive on the cradle flange, bore or key.

After cure, reinstall the cradle: lay the attached lead sideways into the slot,
align both USB openings beside the single rear leg, and lower it until the
flange stops on the narrow outer land. Flip the diffuser, rotate until all three
Ø3 pegs enter the blind sockets, and confirm the Ø6 shoulders sit flat with no
rocking.

1. Leg frame
2. Dry-fit cradle, diffuser and Shell A; then remove cradle/diffuser
3. Bond Shell A into the plinth locate groove
4. Reinstall LED cradle, LED module and diffuser through Shell A
5. A→B halo ring
6. Shell B
7. B→C halo ring
8. Shell C

At each halo joint, lower the complete 5 mm band evenly into the shell below.
A→B's ten deeper tabs should enter together without forcing; B→C has no open or
cut-off side. Before seating each ring, align its outward skirt tab with the
open rim notch in the lower shell (Shell A for A→B, Shell B for B→C). That
hand-clock replaces guessing from the conformal band alone.

At both joints, also find the small tapered tab on top of the ring collar and
the open notch on the inside of the upper shell's register. Align them before
lowering Shell B or C. Each tab is only an orientation key: it must enter by
hand, the shell must still land on the full annular seat, and adhesive remains
the structural fixing. Do not pack either notch with adhesive; use a wiped film
on the surrounding land so squeeze-out cannot stop the key seating.

Both slots should remain 4.0 ±0.2 mm and neither ring should be visible at eye
level. Only bond after the complete dry stack seats without force or rocking.
Keep adhesive out of the halo light windows.

Shells B and C include the required 4 mm internal locating ledges. Do not trim
the ledges, clocking notches or ring tabs. A→B's 22 mm skirt and B→C's 5 mm
band must each be continuous around 360°. On A→B, inspect the straight lower
edge, twenty radial webs and bed-rooted central collar. On B→C, all five
1.6 mm radial webs must be fully joined to the central collar and outer band.
Remove only loose hairs or brim obstructing a fit surface.

The revised optical model estimates roughly 138 lm leaving the lamp centrally,
with Shell C increasing from about 6.0 to 9.2 lm versus the prior all-Matte,
1.6 mm-C package. This remains an accent lamp, not a reading light. A
purpose-made translucent white diffuser could improve transmission further,
but requires its own temperature and hotspot check.

See [`../coupons/ASSEMBLY_GUIDE.svg`](../coupons/ASSEMBLY_GUIDE.svg) for the
exploded orientation.

`production_report.json` records generated dimensions, fuzzy-paint coverage,
fit checks, and output filenames. `meshes/` contains matching STLs for
inspection; use the 3MF projects for printing because they carry the painted
fuzzy regions and P2S profiles.
