# County clicker physical-test revision

This folder contains ten focused P2S projects generated after the
printability review. It is a candidate revision, not yet the replacement for
the packaged 32-county set.

## What changed

- Switch centres optimize clearance around the actual 16.4 mm square shoulder,
  rather than only maximizing a circular inscribed radius.
- Counties enlarge without an arbitrary 10% limit until the shoulder has at
  least **1.50 mm** of material.
- Moving tops retain at least **45%** of shell area.
- Moving-top lobes that fail a **1.20 mm neck test** are trimmed from the top
  only. Fixed shell boundaries remain faithful to the official mainland data.
- Default moving clearance remains **1.25 mm** per side. Wicklow is the
  exception: its shell stays at geographic scale (**32.51 × 38.03 mm**) and
  only the moving top uses **0.75 mm** side clearance so the southwest pocket
  lobe stays connected (≥0.80 mm neck).
- 3MF files use the stock `Bambu PLA Matte @BBL P2S` profile.
- Prime tower is disabled because each plate uses one filament.

## Test projects

| County  |   New shell size | Shoulder wall | Why test                             |
| ------- | ---------------: | ------------: | ------------------------------------ |
| Tyrone  | 62.00 × 42.68 mm |      3.308 mm | Baseline for the latest revision     |
| Derry   | 43.85 × 44.29 mm |      1.500 mm | Minimum-wall threshold case          |
| Louth   | 55.47 × 65.43 mm |      1.500 mm | Largest total scale factor           |
| Sligo   | 61.89 × 59.26 mm |      1.500 mm | Moving-top lobe trimming             |
| Cavan   | 62.15 × 43.44 mm |      2.652 mm | Irregular narrow top, no extra scale |
| Donegal | 85.63 × 70.61 mm |      6.388 mm | Mainland top-recognition case        |
| Cork    | 95.00 × 64.72 mm |      8.458 mm | Largest overall print                |
| Dublin  | 40.55 × 61.84 mm |      1.564 mm | Narrow boosted mainland              |
| Mayo    | 68.64 × 60.12 mm |      4.912 mm | Complex coastline                    |
| Wicklow | 32.51 × 38.03 mm |      1.833 mm | Top fills SW lobe; shell unchanged   |

Every candidate has:

- watertight, single-component shell and top meshes;
- at least 1.50 mm around the switch shoulder;
- exact moving clearance ≥1.2467 mm for the default set; Wicklow ≈0.749 mm;
- zero shell/top overlap at released, midpoint and pressed positions;
- stock Bambu Matte profile metadata;
- no prime tower.

## Print order

1. Tyrone
2. Derry
3. Louth
4. Sligo
5. Cavan
6. Donegal
7. Cork
8. Dublin
9. Mayo
10. Wicklow

The switch/socket coupon is not part of this test cycle because that mechanism
has already been physically confirmed.

## Acceptance checks

For each print, record:

- shell has no holes or missing lines around the switch shoulder;
- switch flange seats flat and does not distort the shell;
- top installs without force;
- top completes at least 100 clicks without scraping or sticking;
- lateral wobble is acceptable;
- top lobes survive normal handling and light twisting;
- face-down top surface and brim cleanup are acceptable;
- county remains recognizable.

Do not regenerate the complete packaged set until the focused revision is
physically approved.
