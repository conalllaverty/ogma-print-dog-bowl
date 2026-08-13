> ⚠️ **ARCHIVED — not a live design.** The only active Oggie Spin design is
> [`../../active/`](../../active/). This document is kept for provenance;
> do not build from it or copy tolerances out of it without checking the active package.

# Oggie Spin optical variants

This folder contains seven two-plate core-and-arm experiments plus one separate
three-plate shutter experiment. The core-and-arm projects put one current Ø12.82
matched clip-lock core on Plate 1 and five current three-rail + underside-clip
arms on Plate 2. The shutter project instead contains a modified core, grooved
upper pad, snap-on shutter ring and five standard arms. Reuse the parts listed
in each section from the complete Oggie Spin project. The broken-ring optical
winner lives with the complete package under `../complete/`, not here.

Every core has a two-letter, contrasting flush inlay on its underside (the bed
face) so printed variants remain identifiable. Optical inlays are 0.32 mm deep
(two 0.16 mm layers). Every arm batch uses two wall loops, 100% gyroid infill,
0.6 mm Slope Lift Z hop, 0.8 mm / 30 mm/s retraction, layer-change retraction
and 2 mm wipe. The inlay variants print by layer. The colour-pulse batch prints
by object because by-layer printing would cause 174 AMS changes; the sequential
layout slices safely and reduces this to four changes.

## VX — full-body five-track vortex

[`Oggie_Spin_Optical_Full_Body_Vortex_P2S.3mf`](./full_body_vortex/Oggie_Spin_Optical_Full_Body_Vortex_P2S.3mf)
is the strongest naked-eye concept. Five broad 1.8 mm intertwined tracks begin
just outside the Ø20 thumb pad, sweep 70° from R10.6 to R24.5 and continue
across the core-to-arm seams. Fivefold symmetry keeps all arms identical,
interchangeable and volume matched; no numbered installation order is needed.

- Preset: Dark Chocolate Matte base + Ivory White Matte vortex
- Alternative: Marine Blue Matte + Ivory White Matte
- Alternative: Scarlet Red Matte + Lemon Yellow Matte

## SH — stationary shutter over exposed core infill

[`Oggie_Spin_Optical_Shutter_Exposed_Core_Infill_P2S.3mf`](./shutter_infill/Oggie_Spin_Optical_Shutter_Exposed_Core_Infill_P2S.3mf)
is the highest-risk optical experiment. Plate 1 carries a modified core with
thirteen 1.2 mm structural radial ribs standing in a 1.6 mm-deep annular recess.
Each rib has a narrower 0.8 mm Ivory White flush cap. Plate 2 carries a modified
socketed upper pad and a separate Ø46 × 1.8 mm Dark Chocolate shutter ring with
twelve 6° radial viewing slots. Plate 3 contains five standard Dark Chocolate
arms in the proven centre-plus-four-corners layout with two walls, 100% gyroid
infill and 0.6 mm Slope Lift.

Flex the shutter ring's split only enough to pass its bead over the grooved
upper pad, then seat the bead in the pad groove. Reuse the outer-race retaining
ring, Tough+ cartridge and standard lower pad. Before
spinning, confirm that the stationary ring remains flat and has the full 1.6 mm
running gap over every rotating face. Stop if it rubs, lifts or unclips.

- Preset: Dark Chocolate Matte core/shutter + Ivory White Matte rib caps
- Intended effect: the 13:12 count difference produces a slowly drifting moiré
  lobe through the stationary slots
- Status: slice-validated only; snap retention, deflection, free spin and
  naked-eye effect require physical testing

## SP — five-phase travelling spiral / wave

[`Oggie_Spin_Optical_Spiral_Wave_P2S.3mf`](./spiral_wave/Oggie_Spin_Optical_Spiral_Wave_P2S.3mf)
puts one broad curved stripe into each arm. Install all five in the same
orientation to form the travelling five-arm spiral.

- Preset: Marine Blue Matte base + Ivory White Matte inlay
- Alternative: Dark Chocolate Matte + Lemon Yellow Matte
- Alternative: Scarlet Red Matte + Ivory White Matte

## CH — chevron reversal / barber-pole band

[`Oggie_Spin_Optical_Chevron_Barber_Pole_P2S.3mf`](./chevron/Oggie_Spin_Optical_Chevron_Barber_Pole_P2S.3mf)
uses two nested high-contrast chevrons on every arm. The repeated angled marks
should reverse apparent travel direction as the spinner slows.

- Preset: Dark Chocolate Matte base + Lemon Yellow Matte inlay
- Alternative: Marine Blue Matte + Ivory White Matte
- Alternative: Scarlet Red Matte + Ivory White Matte

## ST — phone / LED strobe animation disk

[`Oggie_Spin_Optical_Strobe_Animation_P2S.3mf`](./strobe/Oggie_Spin_Optical_Strobe_Animation_P2S.3mf)
places ten equal-size comet frames around the core at sinusoidally changing
radii. View through phone video or a safely configured LED strobe; the plain
arms keep attention on the animated core track.

- Preset: Marine Blue Matte base + Ivory White Matte animation marks
- Alternative: Dark Chocolate Matte + Lemon Yellow Matte
- Alternative: Scarlet Red Matte + Ivory White Matte

Avoid directly viewing high-intensity flashing light. Do not use a strobe if
you or a viewer may be photosensitive.

## OD — dual-radius opposing drift rings

[`Oggie_Spin_Optical_Opposing_Drift_P2S.3mf`](./opposing_drift/Oggie_Spin_Optical_Opposing_Drift_P2S.3mf)
uses a coarse 12-dash core ring against a fine 30-dash arm ring. Their different
spatial frequencies and phases are intended to produce opposing apparent drift.

- Preset: Dark Chocolate Matte base + Ivory White Matte inlays
- Alternative: Marine Blue Matte + Ivory White Matte
- Alternative: Scarlet Red Matte + Lemon Yellow Matte

## CP — high-contrast colour pulse sequence

[`Oggie_Spin_Optical_Colour_Pulse_P2S.3mf`](./colour_pulse/Oggie_Spin_Optical_Colour_Pulse_P2S.3mf)
uses five plain, mass-matched arms. Install arm objects 1–5 clockwise in their
project order; the starting slot does not matter.

- Preset clockwise: Ivory White / Marine Blue / Ivory White / Marine Blue /
  Lemon Yellow Matte
- Alternative: Ivory White / Dark Chocolate / Ivory White / Dark Chocolate /
  Mandarin Orange Matte
- Alternative: Ivory White / Scarlet Red / Ivory White / Scarlet Red /
  Lemon Yellow Matte

## LD — expanding / contracting dashed ladder

[`Oggie_Spin_Optical_Dashed_Ladder_P2S.3mf`](./dashed_ladder/Oggie_Spin_Optical_Dashed_Ladder_P2S.3mf)
continues a sequence of varying-length radial bars from the core onto the arms.
The envelope expands and contracts twice per revolution.

- Preset: Scarlet Red Matte base + Ivory White Matte inlay
- Alternative: Marine Blue Matte + Lemon Yellow Matte
- Alternative: Dark Chocolate Matte + Ivory White Matte

## Validation

All seven core-and-arm projects contain two plates and slice successfully in
Bambu Studio 2.7.1: 14/14 plates have empty warning fields. Package integrity, object-id
hygiene, five distinct arm objects per batch plate, batch print overrides,
watertight geometry, original core/arm volume reconstruction, identical arm
volume, the Ø12.82 bearing pocket and underside identifier placement are checked by
[`optical_variants_validation.json`](./optical_variants_validation.json).
The SH project's three additional plates also slice with empty warning fields.
Its 13 ribs, 12 slots, Ø46 shutter, 1.6 mm running clearance, 1.4 mm minimum
pad-groove wall and package integrity are checked by
[`shutter_infill_validation.json`](./shutter_infill/shutter_infill_validation.json).
All optical effects still require physical testing.
