# Bouclé Stack coupon results

Print in order and stop at the first failed gate. Do not print all four plates
as one batch.

Use the illustrated [coupon test guide](./COUPON_TEST_GUIDE.svg) while working
through Plates 1–4. After every gate passes, follow the
[exploded assembly guide](./ASSEMBLY_GUIDE.svg).

## Stage 0 — hardware preflight (before Plate 4)

- Actual MH001 diameter: **\_\_** mm (configured envelope: 60.0)
- Actual total height: **\_\_** mm (configured: 8.0)
- Screw-hole centre spacing: **\_\_** mm
- Module thickness under screw heads: **\_\_** mm
- Cable body: **\_\_** × **\_\_** mm
- Maximum lead / strain-relief width at LED edge: **\_\_** mm (slot: 6.8 mm)
- [ ] Dimensions have been checked against `dimensions_and_acceptance.json`
- [ ] Plate 4 may be printed

## Plate 1 — glow wall + Bone White diffuser geometry proxy

Smooth-wall measurements, three per sector:

- 1 dot / 1.2 mm: **\_\_** / **\_\_** / **\_\_** mm
- 2 dots / 1.6 mm: **\_\_** / **\_\_** / **\_\_** mm
- 3 dots / 2.0 mm: **\_\_** / **\_\_** / **\_\_** mm

- Selected wall: **\_\_** mm
- [ ] Selected wall is within ±0.15 mm of nominal
- [ ] Even glow under a fixed LED position/exposure
- [ ] No pinholes visible from 300 mm in the fuzzy half
- [ ] No unacceptable layer banding
- [ ] Baffle disc is flat; all three posts have equal height and intact locator pegs
- [ ] No LED die is directly visible at seated eye height
- [ ] Final Jade White project-06 diffuser also hides the LED dies

The 1.6 mm sector gates Shells A/B. The 1.2 mm sector separately gates the
brighter Shell C and must show no pinholes or unacceptable weakness.

## Plate 2 — A→B halo + shell/base seat arc

This arc validates the fit, slot, bonding surfaces, lower-shell rim
tab/notch and upper-shell clocking tab/notch. Inspect the continuous skirt,
twenty straight webs and bed-rooted collar separately on production project 04.

- Slot at three marked positions: **\_\_** / **\_\_** / **\_\_** mm
- [ ] All three are within 4.0 ±0.2 mm
- [ ] Ring enters by hand without forcing
- [ ] Outward skirt tab and Shell A's open rim notch are intact and free of brim
- [ ] Aligning the skirt tab with the rim notch clocks the ring by hand
- [ ] Tapered tab and Shell B's open-bottom notch are intact and free of brim
- [ ] With tab and notch aligned, Shell B drops onto the seat without binding
- [ ] Seated Shell B has no visible rotational misalignment or rocking
- [ ] No printed ring edge is visible at eye level
- [ ] No cracks, delamination or malformed 45° surfaces

Keep the shell A base arc for the Plate 4 interface check.

First-print observation — 28 July 2026:

- Light travel stringing occurred between the separate Plate 2 arcs.
- The user reported that the plate otherwise printed successfully.
- Remove the hairs before measuring or dry-fitting; they must not remain on a
  seat or slip surface.
- If it recurs materially, dry the Matte PLA and verify the stock P2S
  retraction/wipe settings before changing coupon geometry.

## Plate 3 — B→C halo

- Slot at three marked positions: **\_\_** / **\_\_** / **\_\_** mm
- [ ] All three are within 4.0 ±0.2 mm
- [ ] Ring enters by hand without forcing
- [ ] Outward skirt tab and Shell B's open rim notch are intact and free of brim
- [ ] Aligning the skirt tab with the rim notch clocks the ring by hand
- [ ] Tapered tab and Shell C's open-bottom notch are intact and free of brim
- [ ] With tab and notch aligned, Shell C drops onto the seat without binding
- [ ] Seated Shell C has no visible rotational misalignment or rocking
- [ ] No printed ring edge is visible at eye level
- [ ] No cracks, delamination or malformed 45° surfaces

## Plate 4 — LED cradle + plinth interface

The plinth gauge and production leg frame now have a narrow flange stop and
45° bore ramp; there is no sacrificial puck to remove.

- Cradle top relative to gauge top: **\_\_** mm (pass: flush within 0.3 mm)
- Measured lateral play at flange: **\_\_** mm
- [ ] Inverted stop/ramp printed cleanly with no loose chords in the bore
- [ ] Cradle's 45° flange and key tapers printed cleanly with no loose strands
- [ ] Cradle traverses the complete 28 mm bore without binding
- [ ] Outer 0.6 mm of the 4 mm flange stops the cradle; it cannot fall through
- [ ] Cradle lifts out by hand and has no obvious rattle
- [ ] Anti-rotation key engages by hand and keeps both channels aligned
- [ ] All three diffuser pegs enter the blind sockets by hand
- [ ] Ø6 post shoulders sit flat with no rocking; diffuser lifts out without tools
- [ ] Actual LED sits at the intended height on the uninterrupted Ø40 tape pad
- [ ] LED lowers while the attached lead lays sideways into both open-top slots
- [ ] Switch and USB plug remain outside; nothing is threaded through a printed part
- [ ] Cable exits without pinching
- [ ] Shell A arc drops into the 1.0 mm annular locate groove without rocking
- [ ] Shell A arc bridges the local 6.8 mm seat slot without damage
- [ ] After a dry fit, the cradle flange still passes through Shell A's opening
- [ ] Bond proof uses only the groove floor — no adhesive on the cradle
- [ ] Supplied screws were not installed without measured safe engagement

## Bond proof

- Adhesive: **\*\*\*\***\_\_\_\_**\*\*\*\***
- Cure time used: **\*\*\*\***\_\_\_\_**\*\*\*\***
- Coupon tested: A→B / B→C
- Slot before load: **\_\_** mm
- Slot after 500 g lateral load for 60 s: **\_\_** mm
- [ ] No separation or crack
- [ ] Permanent slot change ≤0.2 mm

## Full assembly (later)

- [ ] A→B's continuous 22 mm skirt has a straight lower edge with no split,
      delamination or loose underside
- [ ] A→B's complete skirt enters Shell A without forcing or rocking
- [ ] B→C's complete 5 mm band enters Shell B without contacting its lower
      register or the A→B ring
- [ ] Upper-part mass-dummy test passed before printing shells B/C
- [ ] 10° board test passed in every orientation
- Maximum PLA temperature after eight-hour Shell A test: **\_\_** °C (pass: <45°C)
- Maximum PLA temperature after 24-hour complete burn-in: **\_\_** °C (pass: <45°C)
- [ ] No smell, softening, colour change or cable heating
