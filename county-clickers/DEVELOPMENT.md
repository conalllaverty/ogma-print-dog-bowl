# Development and regeneration

## Canonical source

County-specific source remains with the repository's Python generator so it
can reuse the established 3MF and MX-switch utilities:

- Generator: `backend/generator/county_clicker.py`
- GAA colour data: `backend/generator/county_gaa_colours.py`
- Official boundaries: `backend/generator/county_boundaries/`
- Boundary attribution: `backend/generator/county_boundaries/SOURCES.md`
- MX mechanism reference: `backend/generator/sushi_clicker.py`
- 3MF utilities/template: `backend/generator/build_bambu_project.py` and
  `backend/generator/blank_project.3mf`

## Environment

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

## Regenerate the package

All counties:

```bash
.venv/bin/python backend/generator/county_clicker.py \
  --out county-clickers/counties
```

Selected counties:

```bash
.venv/bin/python backend/generator/county_clicker.py \
  --out county-clickers/counties \
  --county Tyrone \
  --county Dublin
```

Fast 2D fit audit:

```bash
.venv/bin/python backend/generator/county_clicker.py \
  --out county-clickers/counties \
  --check-fit
```

Optional geographic reference:

```bash
.venv/bin/python backend/generator/county_clicker.py \
  --out county-clickers/reference \
  --layout-only
```

## Locked geometry decisions

- Standalone pieces; no tessellating-map requirement.
- No map seam inset; preserve the official source outline.
- Boundary fidelity gate: ≥99% IoU and ≤0.10 mm Hausdorff deviation at print
  scale after reversing intentional mechanism-size enlargement.
- Tyrone width anchor: 62 mm.
- Narrow counties enlarge independently to fit the mechanism.
- Pocket inset: 1.4 mm from shell outline.
- Moving top offset from actual pocket: 1.25 mm.
- Required exact minimum moving clearance: 1.20 mm.
- Small lateral wobble is intentional.
- Full top, including MX boss, must have zero shell collision at released,
  midpoint and fully pressed positions.
- Top prints face-down.

## Change procedure

1. Change the production generator, not generated STL/3MF files.
2. Run `--check-fit`.
3. Regenerate Tyrone plus the affected extreme/narrow counties first.
4. Inspect `dimensions_and_validation.json`.
5. Open the 3MF in Bambu Studio and slice both plates.
6. Print the fit coupon after changes to switch/socket dimensions.
7. Regenerate all 32 only after the focused checks pass.

Generation deliberately fails on invalid polygons, non-watertight meshes,
insufficient clearance, boolean errors, or travel collisions.
