# G1 — Real slice numbers for all three bowl styles

**Captured:** 2026-08-06, Bambu Studio, Bambu Lab P2S
**Process:** 0.20 mm Standard @BBL P2S · Bambu PLA Matte (Ogma Caramel body / Ogma Ivory White letters) · Textured PEI plate
**Status:** complete — all 10 plates across the three styles

---

## Summary — per finished stand

| | **cooper** (paw lattice) | **wave** | **hex** (honeycomb) |
|---|---:|---:|---:|
| Sample name | JOEY (4) | LUNA (4) | MAX (3) |
| Plates | 4 | 4 | **2** |
| Filament | 78.63 m | 88.54 m | 67.07 m |
| **Mass** | **249.65 g** | **281.11 g** | **212.96 g** |
| **Filament cost** | **6.24** | **7.03** | **5.32** |
| Model printing time | 7h02m | 6h39m | 7h41m |
| **Total time (incl. prep)** | **7h30m** | **7h07m** | **7h55m** |
| Longest single plate | 4h36m | 3h30m | **7h32m** |
| Support used | none | 2.20 g (plate 2) | none |
| AMS filament changes | 0 | 0 | 0 |

Studio is configured at ~€25/kg (6.24 ÷ 249.65 g = €0.025/g).

---

## The three findings that matter

### 1. Every style is a ~7–8 hour print. Throughput is the real constraint.

The spread between the cheapest and dearest style is 68 g and €1.71 — noise. The
spread in *time* is 48 minutes on a ~7.5 hour job — also noise. **All three styles
cost about the same to make, and that cost is dominated by a working day of
machine time, not by €5–7 of plastic.**

One P2S running flat out produces **at most ~3 stands per day**, realistically 2
once you account for plate changes and not printing overnight unattended. Twenty
stands for a market stall is **ten days of continuous printing** on one machine.
That is the number that should drive pricing and stock planning, and nothing in
the repo knew it before today.

### 2. Mass and time are *anti*-correlated. Pricing on filament would mislead you.

**hex uses 25% less filament than wave but takes 11% longer.** The honeycomb is
the lightest stand and the slowest one — its 1 mm recessed grooves are all fiddly
perimeter work at low flow, so it buys its lightness with tool-path time.

| Style | Mass rank | Time rank |
|---|---|---|
| hex | 1st (lightest) | 3rd (slowest) |
| cooper | 2nd | 2nd |
| wave | 3rd (heaviest) | **1st (fastest)** |

Rank the styles by filament and you get the exact opposite answer to ranking them
by time. Price on material cost and you will systematically underprice the
honeycomb — the one that occupies the printer longest.

### 3. hex is one 7h32m plate. That is a different operational risk.

cooper and wave split across 4 plates, longest 4h36m and 3h30m. hex is a **single
7h32m plate** plus a 23-minute letters plate.

- **In hex's favour:** two plate changes instead of four. Much less attended time,
  and it suits an overnight run.
- **Against it:** a failure at hour seven loses the whole stand. cooper's worst
  case loses 4h36m and you reprint one part; hex's worst case loses everything.

Worth deciding deliberately which risk profile you want before hex becomes the
lead SKU — and it argues for getting first-layer adhesion and the seat-ramp
overhang nailed on hex specifically, since it has the least forgiving failure mode.

---

## Plate-by-plate

### cooper — `data/jobs/joey-paw/JOEY_Paw_Lattice_P2S.3mf`

| Plate | Part | Filament | Mass | Cost | Model | Total |
|---|---|---:|---:|---:|---:|---:|
| 1 | Base | 18.34 m | 58.23 g | 1.46 | 1h21m | 1h28m |
| 2 | Paw panel (upright) | 48.50 m | **153.99 g** | 3.85 | 4h29m | **4h36m** |
| 3 | Top seat ring (upright) | 11.50 m | 36.52 g | 0.91 | 1h02m | 1h09m |
| 4 | JOEY letters | 0.29 m | 0.91 g | 0.02 | 10m24s | 17m26s |
| | **Total** | 78.63 m | **249.65 g** | **6.24** | 7h02m | **7h30m** |

Plate 2 alone is **62% of the mass and 61% of the time.** If cooper needs to get
cheaper or faster, the paw panel is the only lever worth pulling.

### wave — `data/jobs/luna-wave-split-seat/LUNA_Wave_P2S.3mf`

| Plate | Part | Filament | Mass | Cost | Model | Total |
|---|---|---:|---:|---:|---:|---:|
| 1 | Wave lower | 51.92 m | **164.83 g** | 4.12 | 3h23m | **3h30m** |
| 2 | Upper shell (inverted) | 32.59 m | 103.47 g† | 2.59 | 2h45m | 2h52m |
| 3 | Bowl-seat insert (inverted) | 3.80 m | 12.07 g | 0.30 | 20m53s | 27m55s |
| 4 | LUNA letters | 0.23 m | 0.74 g | 0.02 | 9m49s | 16m52s |
| | **Total** | 88.54 m | **281.11 g** | **7.03** | 6h39m | **7h07m** |

† 101.27 g model + **2.20 g support** — this is the critical-regions-only support
for the pocket-closing layers that `AGENTS.md` specifies. Confirmed present and
costing almost nothing. Wave is the only style using any support.

Wave is the **fastest** style despite being the heaviest, and its longest plate is
only 3h30m — the most forgiving schedule of the three.

### hex — `data/jobs/max-honeycomb/MAX_Honeycomb_P2S.3mf`

| Plate | Part | Filament | Mass | Cost | Model | Total |
|---|---|---:|---:|---:|---:|---:|
| 1 | Solid honeycomb body | 66.65 m | **211.62 g** | 5.29 | 7h25m | **7h32m** |
| 2 | MAX letters | 0.42 m | 1.34 g | 0.03 | 16m9s | 23m11s |
| | **Total** | 67.07 m | **212.96 g** | **5.32** | 7h41m | **7h55m** |

---

## Correction to the plan's density estimate

`OGMA-PRINT-STUDIO-PLAN.md` guessed printed mass would be **45–65%** of the
solid-volume upper bound. That was too pessimistic. Measured against the mesh
volumes in each `dimensions_and_validation.json`:

| Style | Solid volume | Printed volume (mass ÷ 1.24) | Ratio |
|---|---:|---:|---:|
| cooper | 269.2 cm³ | 200.6 cm³ | **75%** |
| hex | 209.3 cm³ | 170.7 cm³ | **82%** |
| wave | 258.1 cm³ | 224.3 cm³ | **87%** |

Per part, the pattern is clear — **thin walls print nearly solid**:

| Part | Solid | Printed | Ratio |
|---|---:|---:|---:|
| cooper paw panel | 130.7 cm³ | 124.2 cm³ | **95%** |
| cooper top ring | 48.7 cm³ | 29.5 cm³ | 61% |
| cooper base | 89.8 cm³ | 47.0 cm³ | 52% |

A 4 mm wall at 0.42 mm line width is essentially all perimeter — there is nowhere
to put sparse infill. Chunkier parts (base, ring) get real infill savings.

**Rule of thumb for new styles: assume ~80% of solid volume, and ~95% for any
thin-wall body.** A style that looks lighter will not be meaningfully cheaper
unless its *wall* changes.

## Letters are free — stop worrying about them

| Style | Letters | Mass | Time |
|---|---|---:|---:|
| cooper | JOEY (4) | 0.91 g | 17m26s |
| wave | LUNA (4) | 0.74 g | 16m52s |
| hex | MAX (3) | 1.34 g | 23m11s |

Under 1.5 g and under 25 minutes in every case — **well under 1% of the cost of a
stand.** Name length is commercially irrelevant. Offering more fonts, or longer
names, costs nothing but the packing gate. The 8-character limit is a geometry
constraint, not an economic one.

## Method

Open project → **Preview** tab → click each plate thumbnail in the left strip.
Plates auto-slice on selection; read the **Slicing Result** panel top-right. No
need to press *Slice plate* per plate. On open, Studio asks to confirm the
customised `@Ogma Caramel` / `@Ogma Ivory White` presets — that dialog is benign.
