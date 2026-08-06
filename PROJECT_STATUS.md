# Ogma Print — Dog Bowl Project Status

**Repo:** https://github.com/conalllaverty/ogma-print-dog-bowl  
**Local path:** `/Users/conalllaverty/Documents/GitHub/ogma-print-dog-bowl`  
**Last updated:** 2026-08-05
**Status:** Local MVP — Cooper, Wave, and solid Honeycomb styles generating

---

## What this product is

A configurator for elevated dog-bowl stands (Bambu Lab P2S) that all seat the **same Cooper metal bowl** (Ø140 rim family):

1. User enters a dog name (2–8 letters A–Z)
2. Picks **stand style** (paw lattice · wave · honeycomb) + letter style + Matte colours
3. Generates a print-ready `.3mf`
4. Downloads and prints / assembles

| Style    | Status               | 3MF                                              |
| -------- | -------------------- | ------------------------------------------------ |
| `cooper` | **Live**             | 4 plates — base · paw panel · top ring · letters |
| `wave`   | **Print-proven**     | 4 plates — lower · upper shell · seat · letters  |
| `hex`    | **Live (first cut)** | 2 plates — solid honeycomb body · letters        |

Bowl size is locked to Cooper’s insert — no multi-rim presets for now.

Companion / design origin lived in `Documents/Ogma Print Files` (`cooper_bowl_design.py` lineage). This repo is the productised app.

Related product: [`ogma-print-core`](https://github.com/conalllaverty/ogma-print-core) (map tiles) — reuse its Railway + Matte filament patterns.

Standalone design package: `design/boucle-stack-lamp/production/` now contains
one ready-to-print eight-plate P2S project plus eight individual fallbacks:
three fuzzy Bone White shells, two smooth halo rings, a Jade White PLA Basic
diffuser, and Dark Chocolate leg-frame/cradle parts. Every plate contains one
object. Shell C is 1.2 mm for higher transmission while retaining its original
reinforced base/register interface. A→B now uses a straight continuous 22 mm
conformal bond skirt, replacing the ten scarfed tabs whose triangular shadows
were visible in the first lit assembly. Its twenty straight radial webs now
join a bed-rooted central collar without the former scalloped crown. B→C keeps
its continuous 5 mm outer band, five evenly spaced webs and 1.2 mm clearance
above Shell B's lower register.
All parts pass fit, complete-stack collision, connectivity and support-free
slice checks. The matching-band revision still requires a physical dry-fit and
bond check before replacing the previously successful rings. The production
legs embed through
the plinth wall as one watertight frame without entering the removable cradle
bore; the aligned USB path runs 20° beside the single rear leg, leaving the
two-leg front gap open. The inverted leg-frame seat/flange is 4 mm with a Ø116 outer lip and a 1.0 mm
annular locate groove that captures Shell A's Ø112 base for epoxy bonding while
keeping the cradle removable through the shell opening. A 0.6 mm radial flange
stop is followed by a 1.9 mm-high 45° bore ramp, so the Ø94 wall no longer
starts as an unsupported inward cliff and needs no breakaway puck. The removable
cradle mirrors that ramp with 0.2 mm radial clearance, leaving a 0.8 mm printable
flange lip; its key also grows outward at 45° instead of starting as a
cantilever. Plate 7 support is now explicitly off after a physical print
strung inside the supported inset: the groove and stop are short bridges, and
the support-free G-code retracts every model travel of at least 5 mm. The
diffuser uses three reduced locator pegs in
matching blind cradle sockets rather than resting loose under gravity; the
assembled clearance model has zero interference. Each halo ring carries one
outward skirt tab into a short conformal open-rim notch in its lower shell
(A or B) for hand-align before bonding, plus one hidden tapered tab into an
open-bottom notch in Shell B/C's internal register for upper-shell rotation —
without multi-pin over-constraint. The lower notches now follow each tapered
inner wall at the local rim height; the former global short-to-long cutter
caused Shell A floating-region warnings and a long channel down Shell B.
Painted shell sidewalls use the physically preferred Classic Displacement
texture at 0.30 mm thickness / 0.80 mm point distance; interiors and 4 mm
base/rim bands remain smooth.
The combined project disables infill-retraction reduction globally because
Studio ignores per-object values for that setting; the individual ring/base
fallbacks also disable it. Both final ring G-code files and all six other plates
retract every model travel of at least 5 mm. It is not wired into the
storefront.
`design/boucle-stack-lamp/fusion/` also carries a full-resolution Autodesk
Fusion mesh package: nine named watertight bodies (eight printed parts plus the
LED reference), millimetre OBJ/3MF assembly files, individual component OBJs
and a Fusion importer script. It is a 584,856-triangle mesh reference rather
than a native parametric F3D/STEP model; fuzzy skin remains slicer metadata.

Standalone Golf Tee lamp work lives under `design/golf-tee-lamp/`. The revised
five-plate all-PLA P2S package uses a one-piece Ø175 Jade White translucent ball
(solid 1.6 mm shell, exact-depth relaxed dimples, 45° support-free skirt), a
Caramel Matte tee with an MH001 side-lead chase / notched reflector / 21 × 12 mm
controller passage, 3-lug bayonet with detents, and slotted spring snap. The
former Ø18 bore could not pass the supplied 19.65 × 10.65 mm controller. The
first Ø74/Ø77 snap was also physically too tight; V2 uses a Ø73.4 shaft,
Ø76.4 bead, Ø75.8 insertion throat, Ø76.8 mouth and Ø77.4 groove. The first
revised Plate 3 incorrectly narrowed to Ø74.2 before the groove and also failed
physical insertion; the corrected socket keeps Ø75.8 through that throat.
Plate 2 prints snap-foot-down with an
8 mm brim and dual 45° self-supporting cup/seat flares; this replaces the failed
seat-down orientation that put only the three protruding pins on the first
layer. The Grass Green base has a **45° inward-narrowing ballast seat** and a
matching 111.7→109.3 mm tapered cover that installs behind the felt, plus tree
supports for the pocket roof, felt recess, and fuzzy turf. See
`design/golf-tee-lamp/SPEC.md`. The first two snap sockets failed insertion;
the corrected throat remains physically unverified. The revised cable path,
bayonet,
ballast and lit-glow gates also remain open.

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

## Phase tracker

| Phase                             | Status      | Notes                                                          |
| --------------------------------- | ----------- | -------------------------------------------------------------- |
| 0 — Parameterised generator       | **Done**    | `name`, `font_style`, Matte IDs, fit gate (±45°), fuzzy on/off |
| 1 — Local FastAPI + Next.js       | **Done**    | Generate → poll → download 3MF verified (`MAX`, `REX`)         |
| 1b — Hybrid GLB preview           | Not started | Client mock only in UI today                                   |
| 2 — Railway deploy                | Not started | Dockerfiles present; need services + volume for jobs           |
| 2b — Filament stock / allow-lists | Not started | Optional; core already has this                                |
| 3 — Commerce / checkout           | Not started | Deferred auth pattern from core if needed                      |

---

## Locked product decisions

| Topic               | Decision                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------------- |
| Max name            | **8** characters + packing fit gate                                                               |
| Colours             | **Bambu PLA Matte only** (`backend/data/filament_palette.json`)                                   |
| Letter styles       | `bold` = **Overpass Bold** (default), `clean`, `serif`, `slab`, `rounded`, `playful`, `condensed` |
| Letter size         | Height **15 mm**, proud **1.4 mm**, pocket clearance **0.10 mm**                                  |
| Letter print        | **0.10 mm** layers, slower outer walls                                                            |
| Letter mount        | Shallow **glyph pockets**, no pins; Wave mounts directly to its cone with matching conical backs  |
| Fuzzy               | Default on; paws + name-rail plaque unpainted                                                     |
| Honeycomb structure | 4 mm hollow wall; 1 mm grooves leave ≥3 mm web; ≤45° inner seat ramp                              |
| Wave collar         | Hollow 2.4 mm annulus at R74; **0.5 mm/side physically passed** on P2S, 2026-07-23                |
| Hosting             | Railway (same dual local/prod contract as core)                                                   |
| Auth                | Anonymous for MVP                                                                                 |

---

## Repo layout

```
backend/
  app/                 FastAPI (health, filaments, generate, jobs, download)
  generator/           cooper_bowl_design + build_bambu_project + paint + pipeline
  data/filament_palette.json
  assets/fonts/        bundled open-license production fonts + license texts
  Dockerfile + railway.json
web/                   Next.js configurator (proxies /api/v1 → PIPELINE_API_URL)
data/jobs/             Job output (gitignored contents)
scripts/dev.sh
Makefile
README.md
PROJECT_STATUS.md      ← this file
AGENTS.md              ← instructions for future AI/human sessions
```

---

## Verified working

- CLI: `pipeline.py --name MAX …` → `MAX_Paw_Lattice_P2S.3mf`
- Wave CLI: `--style wave` → 4-plate lower / upper shell / seat insert / letters project
- Honeycomb CLI: `--style hex` → 2-plate solid body / letters project
- API: `POST /api/v1/bowl/generate` → job succeeds → `download.3mf`
- Matte palette: 25 filaments exposed via `GET /api/v1/filaments`

Honeycomb generated outputs were topology-checked for `MAX`, `LUNA`, and wide
8-letter `WILLIAMS`. The wall is continuous: 1.0 mm recessed grooves leave
proud hex tiles around a whole-cell smooth letter area. The keepout now derives
from the actual packed glyph envelope with a 1.5 mm margin; for `MAX` this
reduces the estimated smooth field from 75.8 × 37.4 mm to 63.6 × 34.4 mm.
The 208-row / 1056-section surface removes the old stair-stepped groove edges,
while complete boundary cells replace the former field of broken ghost
hexagons. The 4.0 mm wall retains a 3.0 mm minimum groove web. Moving the
support start from Z60 to Z58 reduces the internal seat ramp from 43.49° to
39.02°. The staggered whole-cell field is visually asymmetric around the drum
midpoint, so the name is optically centred at Z37 for balanced top/bottom
clearance. Five-millimetre edge bands terminate in a 0.45 mm top bead and a
0.35 mm bottom elephant-foot chamfer.

The production font set now uses physically tested Overpass Bold as the default,
with Source Sans (`clean`), Lora italic (`serif`), Roboto Slab Bold (`slab`),
Fredoka SemiBold (`rounded`), Baloo 2 SemiBold (`playful`), and Barlow Condensed
SemiBold (`condensed`). All seven pass the eight-letter curved packing gate.

Cursive analysis selects Pacifico: at 15 mm it retains a 1.34 mm P20 stroke,
98.2% average connected-word area, and a 59.6 mm `Williams` width. It is not
live yet because it requires a title-case whole-word mesh, ligatures, and
deliberate bridges or keyed pockets for detached `i` dots.

Wave `LUNA` and `WILLIAMS` outputs use the 2.4 mm annular collar. The constrained
R74 rebuild has a 156,868 mm³ lower and 124,647 mm³ lettered upper, versus
976,604 mm³ for the defective early solid-collar prototype.

The Wave halves now use one continuous 256-column wrapped profile each. This
replaces the old per-sector boolean slabs, which were watertight but left deep
vertical grooves that appeared as holes in Bambu Studio. Revised `LUNA` and
`WILLIAMS` 3MFs have single-shell halves and smooth rendered exteriors.

Every Wave radial/Z profile is now checked as a simple positive-area polygon
before wrapping. This exposed and removed crossings in both the old lower inner
wall and upper bowl-support path. The upper has a continuous R74.5 receiver
wall with no horizontal shoulder, plus ≥4 mm wall through the lettering zone.

The bowl seat is now a separate 6.3 mm-high inverted-printing insert instead of
part of the inverted upper. Its R71.53 locator enters the R71.83 shell opening
(0.3 mm radial clearance), while its broad top flange rests on the shell rim.
This removes both the upper's large integrated internal seat and the unsupported
internal ledge from the first split attempt. Wave 3MFs also enable
avoid-crossing-wall travel with unlimited detours, 0.8 mm retraction at 30 mm/s,
layer-change retraction, and a 2 mm wipe.

Wave lettering now follows the original concept: Lora Medium Italic is
available as `serif`, glyph pockets are cut directly into the smooth upper
cone, and the separate proud name plaque has been removed. Letter backs and
pocket floors match the cone taper instead of using Cooper's cylindrical fit.
Plate 2 enables critical-regions-only normal support for the pocket-closing
layers; remove this support before fitting the letters.

Wave fit gate: `data/jobs/wave-collar-fit/Wave_Collar_Fit_Test_P2S.3mf`
contains the revised R74 lower collar and R74.5 upper sleeve on two plates.
The revised fit seated fully with a snug hand fit, minimal wobble, and easy
hand separation. Keep these radii and the 0.5 mm/side clearance.

Wave lettering gate:
`data/jobs/wave-letter-fit/LUNA_Wave_Letter_Fit_Test_P2S.3mf` contains a
71 × 14 × 23 mm crop of the real upper cone and its Lora letters. It uses the
production pockets, pocket floor, cone-backed letters, materials, and print
orientations. The LUNA pocket, seating, proudness, and removal checks passed.

---

## Known gaps / risks

1. **Preview** is a CSS mock, not real GLB geometry
2. **Cursive is research-only** — Pacifico needs a title-case whole-word mesh path and physical coupon
3. **Job storage** is local disk / in-process threads — fine locally; Railway needs a volume or object storage + possibly a worker
4. **No automated tests** yet
5. Condensed style helps long names; packing still rejects if rail > ±45°
6. Original design assets / print notes also live under `Ogma Print Files/cooper_dog_bowl/`

---

## Immediate next steps (priority)

1. Print revised `MAX_Honeycomb_P2S.3mf`; inspect grooves, tighter name field, bottom chamfer, seat underside, and pocket fit
2. Confirm the Honeycomb print before locking the style as print-proven
3. Preserve the print-proven Wave geometry while moving on to product preview work
4. Confirm fonts + `.gitignore` are acceptable for a public GitHub repo
5. Add `preview.glb` export from generator; show in web viewer
6. Deploy backend + web on Railway; set `PIPELINE_API_URL`, `JOBS_ROOT`, CORS
