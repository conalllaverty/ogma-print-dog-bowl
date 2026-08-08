# Oggie Spin — status

<!-- Split out of the monolithic root PROJECT_STATUS.md / AGENTS.md on 2026-08-06.
     Content is verbatim: the constraint lists here were earned from physical
     prints and must not be paraphrased. -->

Standalone Oggie Spin work lives under `design/modular-spinner/`, now split into
`active/` (the Broken Ring Illusion -- the only live design) and `archive/`
(everything superseded). The complete
nine-plate P2S prototype now includes the Ø40 core, pressed outer-race ring, two
removable three-lug thumb pads, five short wrap-around clip-lock colour segments,
and a fully printed Tough+ split-collet/receiver cartridge. The first long petal
arms lifted/rattled too easily, while multiple flex-rail/barb revisions remained
too rigid or mechanically fussy. Solid-slide with shallow friction ribs inserted
by hand but was hard to remove; a later rigid 0.13 mm side-detent trial required
tools and trapped the arms. The matched core/arm revision retires friction ribs,
rigid detents and legacy barb recesses. Each arm now uses a three-rail tongue
(central dovetail ~0.16 mm/side plus two tapered guide rails ~0.22 mm/side) and
an integrated underside Matte PLA battery-cover cantilever clip that snaps into
a core OD pocket; press the tip radially outward to release, then lift.

**Arm latch -- FIXED (rebuilt on a tapered cantilever snap-tab).** Reported
symptom was: the clips are too tight and hard to remove. Root cause is not the mechanism -- the beam is soft on paper (0.92 N,
0.69% strain). Five modelling defects weld the cantilever to the wrap: the stem
block swallows the hook and jams 0.50 mm into un-pocketed core, the release pad
is unioned into un-relieved wrap, a 0.25 mm skin caps the clip with an
unprintable 0.05 mm gap, the 37 deg entry ramp does not exist in the mesh, and
release travel margin is 0.00 mm. Note this is the THIRD latch generation to
fail on removal (solid-slide + friction ribs was hard to remove; the 0.13 mm
rigid side detent required tools). The replacement is a 34 deg tapered cantilever (1.05 -> 0.525 x 4.50 mm),
0.45 mm engagement, 0.70 mm release travel with 0.25 mm margin, a real 30 deg
entry ramp and a 45 deg retention face giving a 2.14 N straight-pull release.
Surface strain 0.56%; the tab bottoms out at 0.90 mm (0.72%) so it cannot be
over-flexed by hand. Seated interference with the core is 0.000 mm3 on all five
arms. Change 0 also landed: wrap clearance 0.12 -> 0.30 mm, 45 deg lead-in
chamfers on the wrap bore and core top edge, and a bottom-edge relief on the
core OD for elephant foot. The validator no longer masks the hook zone and now
walks the beam span asserting open air on both faces. Diagnosis, as-built
numbers and the rated alternatives are in
`design/modular-spinner/ARM-RETENTION-REVIEW.md`. Physical gates remain open. A true
lofted 0.4 mm slot-mouth lead-in is paired with the arm's 0.4 mm tongue lead-in,
while 0.12 mm wrap clearance limits slap. New cores and arms are a matched pair
— do not claim old-arm or old-core compatibility.
Arms export print-flipped with the flush top on the bed so the slot tongue is
not an unsupported overhang. The R188 is the only
non-printed component. The four 7.8 mm collet fingers retain with a Ø6.80 bead
and remain accessible for deliberate release after the upper pad is removed.
All five arm objects use identical 100% grid infill and 2-wall overrides; there
are no weight pods. All eleven meshes are watertight. The cartridge has zero
installed interference; each clip-lock arm has only the intended underside-hook
engagement, with zero unexpected overlap, clear adjacent arms and verified
hook-clearance after 0.35 mm radial release travel. All nine
plates slice in Bambu Studio 2.7.1 with empty warning fields.
The separate `Oggie_Spin_Broken_Ring_Illusion_P2S.3mf` is the optical winner:
it reuses the matched three-rail + underside-clip mechanism and keeps the
proven 15/20/25 dash rings as flush 0.32 mm Ivory White inlays, with an
underside `BR` identifier only. Its nine plates and the matching
`Oggie_Spin_5x_Broken_Ring_P2S.3mf` batch plate slice with empty warning fields.
Clip click, pinch-tab release, 100-cycle lock and free-spin remain physical
gates. The plain five-block batch is now `Oggie_Spin_5x_Clip_Lock_P2S.3mf`.
Seven more physically untested optical projects live under
`design/modular-spinner/optical-variants/`: full-body five-track vortex (`VX`),
five-phase spiral/wave (`SP`), chevron reversal (`CH`), phone/LED strobe
animation (`ST`), dual-radius opposing drift (`OD`), high-contrast colour pulse
(`CP`) and expanding dashed ladder (`LD`). VX uses five 1.8 mm tracks with a
70° sweep from R10.6 to R24.5; a -90° core phase matches the first slot while
fivefold symmetry keeps every arm identical and the core-to-arm paths
continuous. Each project carries its two-letter identifier as a flush
contrasting inlay on the core underside and includes only the core plus five arms; the
standard retaining ring, cartridge and thumb pads are reused. Each project now
uses one core plate and one centre-plus-four-corners five-arm plate. All arm
plates retain two walls, 100% gyroid, 0.6 mm Slope Lift and the proven batch
retraction/wipe profile. Six variants print by layer; colour pulse prints by
object to reduce AMS changes from 174 to four. Their fourteen total plates slice
in Bambu Studio 2.7.1 with empty warning fields. Flush optical inlays remain
0.32 mm deep and all five arms in each project remain volume matched.
An eighth, separate `SH` shutter experiment uses a modified core rather than an
arm pattern. Thirteen 1.2 mm radial ribs stand in a 1.6 mm-deep annular recess
and carry narrower 0.8 mm Ivory flush caps. A split Ø46 × 1.8 mm Dark Chocolate
ring snaps into a groove in the modified upper pad and samples those ribs
through twelve 6° slots, creating a 13:12 moiré beat. Its third plate contains
five standard Dark Chocolate arms in the proven two-wall, 100% gyroid batch
layout. All three plates slice with empty warning fields. The ring remains inside the R24.5 arm tips by 1.5 mm,
retains the canonical 1.6 mm face gap and leaves 1.4 mm material outside the
pad's bayonet entry cavity. This experiment reuses the retaining ring, cartridge
and lower pad. Snap fit, ring deflection, running clearance and
the naked-eye effect are physically untested; do not use it if the ring rubs,
lifts or unclips.
Physical bearing/ring fit, collet creep,
free-spin behaviour and all 100-cycle lock tests remain pending, so this is a
complete prototype rather than production.
The first printed complete core's Ø12.86 bearing pocket released the R188 under
gravity, while Ø12.68 would not accept it by hand. The regenerated project now
uses Ø12.82 after Ø12.78 also remained too tight, giving 0.12 mm nominal
diametral clearance; the separate pressed outer-race ring provides axial
capture. Hand insertion, ring retention and free-spin still need physical
confirmation.
The first Tough+ split collet spun well, but its Ø6.10 axle and 0.15 mm axial
play allowed wobble and intermittent hub/core contact. Its collet-side thumb
pad fitted, while the same pad could not seat on the receiver because the
exposed collet tip occupied its shallow blind cavity. A Ø6.25 axle still showed
some wobble, and the first 6.4 mm receiver pad's Ø7.0 socket required pliers.
Ø6.30 still left a small amount of axle wobble. The current revision uses a
Ø6.40 axle as a 0.05 mm nominal bearing-bore interference trial, a Ø6.48
receiver, 0.05 mm axial play and 1.6 mm face gaps. Both sides use the exact same
6.4 mm pad mesh with a
Ø7.30 × 5.2 mm socket, providing 0.50 mm nominal diametral tip clearance and
simplifying batch manufacture. These revised parts remain unprinted.

---

