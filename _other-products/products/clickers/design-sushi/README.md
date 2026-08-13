# Happy Salmon Nigiri Clicker

Pocket-size fidget clicker for an Outemu (Gaote) Blue 3-pin, 50 gf switch.

## Files

- Concept: [`../salmon-sushi-fidget-clicker-concept.svg`](../salmon-sushi-fidget-clicker-concept.svg)
- Parametric generator: [`../../backend/generator/sushi_clicker.py`](../../backend/generator/sushi_clicker.py)
- Generated project: `data/jobs/sushi-clicker/Happy_Salmon_Nigiri_Clicker_P2S.3mf`
- Dimensional report: `data/jobs/sushi-clicker/dimensions_and_validation.json`
- Individual STLs: `data/jobs/sushi-clicker/meshes/`

Regenerate from the repository root:

```bash
.venv/bin/python backend/generator/sushi_clicker.py \
  --out data/jobs/sushi-clicker
```

## Bambu Studio project

The 3MF targets the Bambu Lab P2S with a 0.4 mm nozzle and Bambu PLA Matte.

| AMS slot | Filament        |
| -------- | --------------- |
| 1        | Ivory White     |
| 2        | Mandarin Orange |
| 3        | Sakura Pink     |
| 4        | Charcoal        |

The project contains three plates:

1. Rice body with the Charcoal face and Sakura Pink cheeks.
2. Salmon button with five diagonal Sakura Pink marbling stripes.
3. Switch-opening and MX-stem tolerance coupon.

The rice body is smooth. Fuzzy skin and raised grain bumps are disabled because
both can trigger false floating-region checks on the small outer wall.

Before slicing Plate 1, confirm AMS flush settings were not recalculated by
Bambu Studio:

- Flush into object's infill: **off**
- Flush into object's support: **off**
- Wall loops: **4**
- Wall sequence: **Inner/Outer** (current Studio rejects Inner/Outer/Inner)
- Flushing multiplier: **1.4**
- Pink → Ivory and Charcoal → Ivory purge volumes remain high

Plate 2 is a hollow salmon cap with a 1.3 mm lower skirt and a projecting MX
boss. Its squarer 55.4 × 31.4 mm cavity stays nearly vertical through the first
7.2 mm, clearing the tapered rice shoulder throughout the switch stroke. It is
packaged top-down with the cavity open upward, supports and brim disabled, and
a 40 mm/s outer wall. The bed-facing top is a broad 51 × 27 mm surface; its two
transition stages expand at 45° or gentler. This removes both the broad internal
ceiling bridge that opened two through-holes when printed cavity-down and the
steep overhang/brim damage from the first top-down revision. The sealed rice
body does not generate internal support.

Every AMS colour part is contained within its host solid and finishes flush
with the surface. The generator fails if any colour part has volume outside its
host. The stripes are 0.6 mm deep and always leave at least 0.6 mm of solid
orange between the pink and the cap cavity, which is why they stop short of the
thin-walled shoulder instead of running to the rim.

## Print the coupon first

The three square openings are 13.95, 14.10, and 14.25 mm. One, two, or
three raised dots identify them in increasing order. Physical testing selected
opening 2 (14.10 mm) for the production rice body.

The loose socket gauge reproduces geometry measured directly from the supplied,
known-working CritterCRAFT Dumpling model: a 5.86 mm round boss with a
4.20 × 1.55 mm cross cavity, 5.00 mm deep. The salmon button uses the same
socket geometry.

The production switch shoulder is 1.0 mm lower than the first prototype. The
upper rice shoulder is also tapered inward to provide clearance for the cap's
intentional lateral wobble at full switch travel. Its visible taper starts at
Z12.8—1.5 mm above the eyes—and finishes on a broad 48 × 26 mm top plateau,
avoiding the steep pyramid profile of the earlier prototype.

The assembled switch stack is derived from the supplied 11.60 mm housing,
5.00 mm lower body and the tapered mount. At rest, the salmon rim overlaps the
rice top by at least 2 mm so the switch is hidden from every side view. Generation
fails if this concealment or the full-travel collision envelope regresses.

## Assembly

1. Insert the switch through the opening in the top of the rice body.
2. Glue the switch flange to the support-safe tapered mounting shoulder.
3. Keep both electrical pins and the central plastic locating pin straight;
   the sealed lower cavity leaves all three unobstructed.
4. Press the salmon button's central socket onto the MX stem. There are no
   lateral guides; a small playful wobble is intentional.

The switch and cap fits should be confirmed with the coupon before committing
to the multicolour body plates. Matte PLA shrinkage and first-layer expansion
vary by machine and build plate.
