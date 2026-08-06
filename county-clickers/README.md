# Ireland County Clickers

Print-ready standalone MX-switch clickers for all 32 Irish counties.

## Start here

- `physical-test-revision/` — latest seven-county candidate awaiting physical approval
- `keychain/` — 2D Tyrone concept and compact-switch design notes
- `counties/<county>/<County>_County_Clicker_P2S.3mf` — ready-to-open Bambu Studio project
- `COUNTY_FILES.md` — direct links to all 32 projects
- `PRINTING_AND_ASSEMBLY.md` — printing, parts and assembly
- `FILAMENT_GUIDE.md` — closest Bambu Lab PLA Matte colours
- `BOUNDARY_SOURCES.md` — official datasets, licences and accuracy method
- `DEVELOPMENT.md` — regeneration and maintenance notes
- `QUALITY_REPORT.md` — validation performed on this package
- `counties/_fit_coupon/switch_fit_coupon.stl` — print this before committing to a full county

Each county folder also includes:

- `meshes/<county>_shell.stl`
- `meshes/<county>_top.stl`
- `dimensions_and_validation.json`

## Design

- Fixed shell follows the official county boundary.
- Moving top follows the recessed pocket with approximately 1.25 mm clearance
  per side. A small amount of wobble is intentional to prevent binding.
- Outemu/Gaote Blue 3-pin switch opening: 14.10 mm.
- MX socket: 5.86 mm boss, 4.20 × 1.55 mm cross, 5.00 mm deep.
- Shell height: 23.5 mm.
- Moving top sits approximately 2.5 mm above the shell at rest.
- The top prints face-down; turn it over before fitting it to the switch.

These are standalone handheld pieces. Narrow counties are enlarged for the
mechanism and the set is not intended to tessellate into a map.

The production generator now includes square-shoulder wall and moving-top
robustness gates. The complete `counties/` package remains the prior revision
until the focused projects in `physical-test-revision/` pass physical tests.

## County list

Antrim, Armagh, Carlow, Cavan, Clare, Cork, Derry, Donegal, Down, Dublin,
Fermanagh, Galway, Kerry, Kildare, Kilkenny, Laois, Leitrim, Limerick,
Longford, Louth, Mayo, Meath, Monaghan, Offaly, Roscommon, Sligo, Tipperary,
Tyrone, Waterford, Westmeath, Wexford and Wicklow.

## Reference files

`reference/` contains a geographic SVG and JSON. They are visual references
only, not a physical assembly plan.
