> ⚠️ **ARCHIVED — not a live design.** The only active Oggie Spin design is
> [`../../active/`](../../active/). This document is kept for provenance;
> do not build from it or copy tolerances out of it without checking the active package.

# Oggie Spin — R188 + axial-lock bayonet fit test

This is the first printable mechanism prototype, not an approved production
spinner. It validates the Ø40 five-slot core, R188 seat, permanent M3 hub
cartridge, and removable three-lug thumb pads.

## Print file

Open [`Oggie_Spin_Bayonet_Fit_Test_P2S.3mf`](./Oggie_Spin_Bayonet_Fit_Test_P2S.3mf)
in Bambu Studio.

The project contains four prepared Bambu Lab P2S plates:

1. Five-slot core and R188 seat
2. M3 centring sleeve and two inner-race spacer tubes
3. Screw-side and captive-nut permanent bayonet hubs
4. Two removable axial-lock thumb pads

Configured process:

- Bambu Lab P2S, 0.4 mm nozzle
- Bambu PLA Matte
- 0.16 mm layers
- 5 walls
- 6 top / bottom layers
- 25% gyroid infill
- Supports off
- Thumb pads print finished-face-down with their bayonet cavities upward

The supplied colours are only plate identifiers. Reassign any Bambu Matte
colours in Studio.

## Additional hardware

- 1 × R188 bearing — 12.70 × 6.35 × 4.76 mm
- 1 × M3 × 25 mm low-profile or button-head machine screw
- 1 × M3 nyloc nut

A normal tall M3 socket-head cap screw will not sit in the 2.3 mm-deep head
pocket.

## Assembly

1. Press the R188 into the core from the top until its **outer race** rests on
   the shoulder. Apply force only to the outer race. Stop if the core begins to
   whiten or crack.
2. Insert the Ø6.18 centring sleeve through the bearing inner race.
3. Put one 5.02 mm spacer tube on each side. Each tube must bear on the inner
   race, not the shield or outer race.
4. Fit the screw-side and nut-side permanent hubs. Insert the M3 button-head
   screw and captive nyloc.
5. Tighten only until the cartridge has no axial movement. Confirm both hub
   flanges retain a visible 0.4 mm gap from the core and the bearing spins
   freely.
6. Align a thumb pad's three entry gates with the hub lugs. Seat the pad and
   rotate it 30° until the three flex nubs settle into the wider terminal
   pockets.
7. Remove a pad by twisting it 30° back past the detents, then lifting it
   straight off. The M3 cartridge stays installed.

## Acceptance gates

- Bearing reaches the shoulder without cracking the core
- Bearing outer race does not move during gentle hand spinning
- Tightening the cartridge does not increase bearing drag
- Neither permanent hub can touch the spinning core
- Both pads reach the terminal stop and cannot pull straight off
- Reverse twist remains deliberate but possible without tools
- No lug whitening, cracking, or chipped cavity edges
- Complete 100 lock / unlock cycles before approving the interface

The generated geometry has a clear 0–30° rigid-body lock path, plus 0.06 mm
radial detent interference that intentionally flexes during rotation. See
[`dimensions_and_validation.json`](./dimensions_and_validation.json) for the
full dimensions and mesh/package checks.

## Safety limit

This archived fit test uses the superseded Ø12.86 pocket, which released the
R188 under gravity in the first complete physical core. Use the current
complete project with its Ø12.82 hand-fit pocket and outer-race ring for further tests.
Do not perform high-speed or drill-driven testing if the bearing can move by
hand.

Regenerate from the repository root:

```bash
.venv/bin/python backend/generator/oggie_spin_bayonet.py \
  --out design/modular-spinner/archive/bayonet-fit-test
```
