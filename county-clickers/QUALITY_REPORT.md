# Quality report

Generated and checked on 2026-07-25.

## Package inventory

- 32 Bambu Studio `.3mf` projects
- 32 per-county validation reports
- 64 STL meshes (shell and moving top for each county)
- 1 switch/socket fit coupon
- Geographic reference SVG and JSON

## Automated results

- County projects generated successfully: **32 / 32**
- Valid ZIP/3MF containers: **32 / 32**
- Watertight positive-volume meshes: **64 / 64**
- 2D top-inside-pocket checks: **32 / 32 passed**
- Official open-data boundary fidelity checks: **32 / 32 passed**
- Boundary accuracy range (IoU): **99.255–99.767%**
- Maximum boundary deviation at print scale: **0.0807 mm**
- Exact minimum side-clearance range: **1.2467–1.2481 mm**
- Required minimum side clearance: **1.20 mm**
- Full moving-top/shell overlap at released position: **0 mm³**
- Full moving-top/shell overlap at travel midpoint: **0 mm³**
- Full moving-top/shell overlap when pressed: **0 mm³**
- Validation failures: **0**

The 3D travel test includes the complete moving top and MX socket boss. Boolean
errors fail generation; they are not treated as successful checks.

Boundary accuracy compares each printable shell with its OSNI or Tailte Éireann
source polygon. Intentional uniform enlargement for the MX mechanism is
reversed before calculating IoU and Hausdorff deviation. See
`BOUNDARY_SOURCES.md` for methodology and attribution.

## Boundary accuracy by county

| County    | Source         | IoU accuracy | Max deviation |
| --------- | -------------- | -----------: | ------------: |
| Antrim    | OSNI           |      99.767% |     0.0785 mm |
| Armagh    | OSNI           |      99.655% |     0.0792 mm |
| Carlow    | Tailte Éireann |      99.422% |     0.0788 mm |
| Cavan     | Tailte Éireann |      99.546% |     0.0800 mm |
| Clare     | Tailte Éireann |      99.710% |     0.0793 mm |
| Cork      | Tailte Éireann |      99.613% |     0.0800 mm |
| Derry     | OSNI           |      99.691% |     0.0799 mm |
| Donegal   | Tailte Éireann |      99.409% |     0.0800 mm |
| Down      | OSNI           |      99.538% |     0.0795 mm |
| Dublin    | Tailte Éireann |      99.255% |     0.0800 mm |
| Fermanagh | OSNI           |      99.583% |     0.0800 mm |
| Galway    | Tailte Éireann |      99.592% |     0.0799 mm |
| Kerry     | Tailte Éireann |      99.520% |     0.0800 mm |
| Kildare   | Tailte Éireann |      99.595% |     0.0795 mm |
| Kilkenny  | Tailte Éireann |      99.653% |     0.0799 mm |
| Laois     | Tailte Éireann |      99.630% |     0.0799 mm |
| Leitrim   | Tailte Éireann |      99.550% |     0.0800 mm |
| Limerick  | Tailte Éireann |      99.686% |     0.0799 mm |
| Longford  | Tailte Éireann |      99.602% |     0.0800 mm |
| Louth     | Tailte Éireann |      99.313% |     0.0791 mm |
| Mayo      | Tailte Éireann |      99.527% |     0.0799 mm |
| Meath     | Tailte Éireann |      99.630% |     0.0800 mm |
| Monaghan  | Tailte Éireann |      99.532% |     0.0800 mm |
| Offaly    | Tailte Éireann |      99.606% |     0.0796 mm |
| Roscommon | Tailte Éireann |      99.643% |     0.0798 mm |
| Sligo     | Tailte Éireann |      99.472% |     0.0807 mm |
| Tipperary | Tailte Éireann |      99.732% |     0.0799 mm |
| Tyrone    | OSNI           |      99.732% |     0.0800 mm |
| Waterford | Tailte Éireann |      99.524% |     0.0795 mm |
| Westmeath | Tailte Éireann |      99.696% |     0.0798 mm |
| Wexford   | Tailte Éireann |      99.618% |     0.0796 mm |
| Wicklow   | Tailte Éireann |      99.641% |     0.0794 mm |

## Physical verification still required

Automated geometry checks cannot prove printer-specific fit. Before batch
production:

1. Print the shared switch/socket coupon.
2. Print one representative county—Tyrone is the physically iterated reference.
3. Confirm switch retention, stem socket grip and free top travel.
4. Inspect first-layer flare on the face-down top.
5. Slice each new printer/material combination in Bambu Studio before printing.

If a physical print disagrees with this report, record printer, nozzle, layer
height, filament and measured interference before changing global dimensions.
