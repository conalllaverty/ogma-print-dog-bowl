# Agent / future session guide — ogma-print-dog-bowl

Read this at the start of any coding session on this repo. Prefer facts here over chat memory.

## Product in one line

Custom **paw-lattice dog bowl stand** configurator: name + Bambu Matte PLA colours → Bambu Studio `.3mf`.

## Canonical docs

| File                                                     | Use                                        |
| -------------------------------------------------------- | ------------------------------------------ |
| [PROJECT_STATUS.md](./PROJECT_STATUS.md)                 | Phase tracker, decisions, gaps, next steps |
| [README.md](./README.md)                                 | Local run + API overview                   |
| [.env.example](./.env.example)                           | Env contract (local + Railway)             |
| [county-clickers/README.md](./county-clickers/README.md) | Standalone 32-county clicker package       |

Sibling design sandbox (not this repo): `Documents/Ogma Print Files` — original Cooper meshes / print experiments.

Sibling product for Railway/filament patterns: `ogma-print-core`.

The standalone county-clicker side product is packaged under
`county-clickers/`. Its production generator remains
`backend/generator/county_clicker.py` so it can reuse the established MX and
3MF utilities. County clickers are individual handheld pieces, not
tessellating map tiles.

The standalone Oggie Spin prototype is under `design/modular-spinner/`.
`backend/generator/oggie_spin_bayonet.py` generates its first four-plate P2S
fit test: Ø40 five-slot core, R188 seat, M3 × 25 mm button-head/nyloc cartridge,
two permanent hubs and two removable thumb pads. Keep the 0.4 mm hub/core gaps,
three 30° bayonet tracks, and 0.06 mm radial detent interference until physical
results say otherwise. Its archived Ø12.86 bearing pocket proved loose in the
first complete physical core and is superseded by the complete generator.
`backend/generator/oggie_spin_complete.py` extends that mechanism into the
current hardware-free nine-plate prototype with five identical short wrap-around
solid-slide colour segments (R20.12–R24.5, ±20°), a Ø15.22 pressed outer-race ring
in a Ø15.15 counterbore, and a Bambu PLA Tough+ split-collet cartridge. The first Ø6.10 axle spun well but wobbled;
Ø6.25 and Ø6.30 reduced but did not eliminate the wobble. The current Ø6.40
axle is a deliberate 0.05 mm nominal interference trial in the Ø6.35 R188 bore;
it must install with controlled hand pressure, never a hammer or pliers. It has
four 8.1 mm fingers and a Ø6.80 retaining bead. The Ø6.48 receiver leaves the
fingers exposed for deliberate release after removing the upper pad. Keep the
revised 1.6 mm hub/core gaps and integrated Ø8.40 inner-race spacer bosses.
Both pads must remain the same 6.4 mm mesh with a Ø7.30 × 5.2 mm blind socket:
the receiver side needs the socket for the exposed collet tip, while carrying
it on both sides simplifies batch manufacturing. The earlier Ø7.0 socket
required pliers to fit and is superseded; both pads must install by hand. The
five arms must retain their identical 100% grid infill and 2 wall-loop
overrides; do not restore weight pods, 5-wall arms, or mix mechanical slicer
settings across colours. The R188 is the only non-printed part. The interim
maximum-stability arm uses one full-width solid trapezoidal dovetail from R14.0
to R21.4: no flex rails or snap barbs. Keep 0.12 mm nominal side clearance and
the shallow 0.02 mm/side friction ribs over installed Z11.8–13.5. Do not restore
the rigid 0.13 mm side detents: physical use in the earlier straight-slot core
required tools and trapped the arms. The detent-free arms must remain compatible
with those earlier cores. Legacy barb recesses remain. Wrap radial clearance is
0.12 mm; keep the arm's 0.4 mm bottom lead-in and the core's continuously
lofted 0.4 mm slot-mouth lead-in. Export wrap segments print-flipped with the flush top
face on the bed; wrap-bottom-down turns the slot tongue into an unsupported
overhang above the 2 mm shelf. Do not restore
the earlier long petal arms after physical testing showed easy lift/rattle and
uneven one-side lock. Do not call the complete 3MF production-ready
until the retaining ring, Tough+ collet, all five arm locks, both thumb locks
and free-spin behaviour pass physical testing. The current R188 pocket is
Ø12.82: Ø12.86 released the bearing under gravity, Ø12.68 would not install by
hand, and Ø12.78 remained too tight. The pocket now uses 0.12 mm nominal
diametral clearance and relies on the separate pressed outer-race ring for axial
capture.
`backend/generator/oggie_spin_optical_variants.py` owns seven separate
core-and-arm optical experiments under `design/modular-spinner/optical-variants/`:
full-body vortex (`VX`), spiral (`SP`), chevron (`CH`), strobe (`ST`), opposing
drift (`OD`), colour pulse (`CP`) and dashed ladder (`LD`). VX must keep five
1.8 mm tracks sweeping 70° from R10.6 to R24.5; keep its core phase at -90° so
the fivefold-symmetric arm pattern crosses every core-to-arm seam. Keep each
flush optical inlay 0.32 mm deep, preserve volume-matched arms and keep the
two-letter contrasting identifier on the core underside. Each two-plate project keeps all five arms
together in the proven centre-plus-four-corners layout with two walls, 100%
gyroid, 0.6 mm Slope Lift and the batch retraction/wipe profile. Keep the inlay
variants by layer. Keep colour pulse by object so its three full-arm colours
need four AMS changes instead of 174. These projects reuse the standard
retaining ring, cartridge and pads and remain physically untested.
`backend/generator/oggie_spin_shutter_infill.py` owns the separate `SH`
stationary-shutter experiment. Keep its thirteen 1.2 mm structural radial ribs
in the 1.6 mm-deep core recess, with narrower 0.8 mm × 0.32 mm Ivory flush
caps, and keep the split Ø46 × 1.8 mm shutter at twelve 6° slots. The shutter
ring snaps into the modified upper pad with 0.10 mm/side bead pass
interference; the groove must leave at least 1.20 mm outside the bayonet cavity.
Retain the 1.6 mm running gap and 1.5 mm radial margin inside the R24.5 arm
tips. Keep Plate 3's five included standard arms in the proven
centre-plus-four-corners layout with two walls, 100% gyroid and 0.6 mm Slope
Lift. The retaining ring, cartridge and lower pad are reused. This is
slice-validated only: do not call it safe or production-ready until snap
retention, deflection, rub-free spin and the naked-eye 13:12 moiré effect pass
physical tests.

The standalone Bouclé Stack lamp is under `design/boucle-stack-lamp/`.
`backend/generator/boucle_lamp_shade.py` generates one eight-plate P2S project
plus eight individual fallback projects (three shells, two halo rings, the
1.2 mm LED diffuser, leg frame and removable cradle). Shells/rings use Bone
White Matte, the diffuser uses stock PLA Basic Jade White, and the base parts
use Dark Chocolate Matte.
Shells A/B are 1.6 mm; Shell C is 1.2 mm but retains the canonical 1.6 mm
base/register solid so the B→C interface does not change. Keep fuzzy paint at
0.30 mm thickness / 0.80 mm point distance with Classic noise and Displacement
mode, exterior sidewalls only. This is the physically preferred production
texture; do not replace it without a successful physical comparison.
Do not put multiple parts on one plate: physical coupon prints repeatedly strung
during inter-object travels. The combined 3MF must retain exactly one object on
each of its eight plates. Keep
`reduce_infill_retraction_mode=Disabled` project-wide in the combined 3MF and
on the individual ring, leg-frame and cradle fallbacks; Bambu applies this
policy globally and stock `Auto` suppresses retraction on long internal
detours. A→B uses a continuous 22 mm-deep conformal bond skirt with a straight
lower edge; this replaces the ten scarfed tabs whose triangular shadows were
visible through Shell A in the first lit assembly. Keep its twenty 1.2 mm
straight radial webs and bed-rooted central collar. Do not restore the scarfed
tabs, scalloped crown or solid funnel; the funnel materially reduces
upper-shell illumination. B→C retains its continuous shallow 5 mm outer band.
The straight A→B architecture is boolean/support validated but still needs a
physical print and lighting check.
The production leg frame must keep its three legs extended through the visible
plinth contact to `LEG_EMBED_R` / `LEG_EMBED_Z`, then clipped outside the
cradle bore. It prints inverted with its top seat on the bed. Keep the seat /
cradle flange at 4.0 mm. The Ø116 top seat carries a 1.0 mm annular locate
groove for Shell A's Ø112 × 1.6 mm base wall. The groove outer wall clears the
shell's flare at groove depth with ±0.25 mm per side. Keep Plate 7 support off:
the groove closes across only ~2.6 mm and the cradle-stop step is 0.8 mm, while
generated support introduced the only unretracted >5 mm travels and physically
strung inside the inset. Use 20 mm/s bridge speed, 0.9 mm Dark Chocolate
filament retraction, 3 mm wipe and disabled infill-retraction reduction. Bond
Shell A into the groove with a thin epoxy film; never glue the removable cradle. The cradle
flange must still pass through Shell A's inner opening after cure. The
flange bears on a 0.6 mm radial outer stop, then the Ø94 bore opens below it
through a 1.9 mm-high 45° ramp. The former full-width horizontal shoulder
started as an unsupported inward cliff and peeled into chords; do not restore
it or the later full breakaway puck. Ending a leg on the plinth tangent exposes
its slanted cap and also intrudes into the removable cradle.
Plate 8 must mirror the plinth ramp with 0.2 mm radial clearance: expand its
Ø93.6 body to Ø97.4 over a 1.9 mm-high 45° underside ramp, leaving only the
0.8 mm radial step into the Ø99 flange. Grow the anti-rotation key outward at
45° over its first 2 mm, then retain 2 mm at full depth. Do not restore the
flat flange or key cantilevers; they produced exposed bridge paths and
spaghetti at Z24.2.
Keep `CABLE_PHASE_DEG` 20° beside the single rear leg (currently 110° beside
the 90° leg), and rotate the cradle slot plus opposite anti-rotation key with
the plinth notch. This leaves the gap between the 210° and 330° front legs
visually open.
The diffuser is not gravity-located: each Ø6 post ends in a Ø3 × 2 mm peg that
engages one of three Ø3.6 × 2.4 mm blind cradle sockets. Keep 0.6 mm total
diametral clearance, 0.4 mm bottom clearance, ≥1.5 mm material to the LED
pocket, and one object per plate. Do not remove the post shoulders or turn the
blind sockets into through-holes.
Do not remove the 4 mm internal locating ledges from Shells B/C. Shell B is
only 10.2 mm tall on its short side, so B→C's outer band must remain 5 mm deep;
this leaves 1.2 mm above the lower register. Keep its central collar and five
evenly distributed bed-rooted radial webs. Deepening the full-circumference
band or restoring a funnel collides with the A→B joint.
Each halo ring has one hidden tapered clocking tab for the upper shell. Keep
the 3.0 × 1.0 × 3.2 mm tab and matching 3.8 × 1.4 mm open-bottom notch in
Shell B/C's register. The intended clearances are 0.8 mm tangential, 0.4 mm
radial and 0.8 mm above the tab, with ≥2.6 mm register material behind the
notch. Each ring also carries one outward skirt tab into an open rim notch in
the lower shell (A for A→B, B for B→C) so the halo can be felt into place
before bonding. Keep the 3.0 × 0.55 × 4.0 mm joint-frame tab and nominal
3.8 × 0.9 mm notch at shell-frame phase 36°, with 0.8 mm tangential and
0.35 mm radial clearance and ≥0.6 mm wall remaining behind the notch. The
notch cutter must follow the tapered inner wall and open only through the local
oblique rim height. Its shell-frame width expands to approximately 4.32 mm on
Shell A and 4.74 mm on Shell B to enclose the tilted key; never span from the
global short rim to the global long rim, which creates a long wall channel and
slicer floating regions. Build the skirt tab in the joint/print frame inside
the upper 5 mm of the skirt/band with a 45° underside; do not restore
multi-pin lower clocks or a skirt-only alignment.
`backend/generator/boucle_lamp_fusion.py` owns the full-resolution Fusion
interchange package. Keep its nine watertight OBJ bodies separately named and
at the finished assembly origin. It is mesh interchange, not parametric
F3D/STEP; fuzzy skin remains slicer metadata and must not be baked into fit
geometry.

The standalone Golf Tee lamp is under `design/golf-tee-lamp/`.
`backend/generator/golf_tee_lamp.py` generates a five-plate all-PLA P2S project:
one-piece Ø175 Jade White PLA Basic shade with constant-thickness dimples
(1.6 mm solid shell, 0% sparse infill; 1.4 mm depth; dual-surface displacement)
and **0.4 mm bayonet lock detents**; a Caramel Matte tee with integrated MH001
pocket (widened to Ø62.1 for the reflector), continuous cup rim, **Ø18
floor-bore** cable path (clears the MH001 inline switch and USB plug; neck Ø24),
**Ø5 bayonet pins with R1.2 root fillets** on PCD 70, and a **4-slot spring snap
foot**; a Grass Green base (120 × 120 mm rounded square × 18 mm) with ballast
pocket + **1.2 mm printed cover ledge**, 110 mm square felt recess, 19 mm
underside cable trench, and top-face fuzzy turf paint that **clears the snap
entry**; plus an Ivory White **0.8 mm reflector cup**. The shade uses a **flat
bed ring + 45° self-supporting cone** into the sphere so exterior supports stay
off; the tee seat is a matching flat-ring rebate. **Variable Layer Height is
baked into Plate 1** (`layer_heights_profile.txt`: 0.20 mm → 0.08 mm on the top
~20%). Print the ball opening-down. One object per production plate. Not
production-ready until bayonet, snap, ballast and lit glow pass physical checks.

County clicker physical gates: 1.25 mm moving-top clearance, ≥1.50 mm material
around the 16.4 mm switch shoulder, ≥45% moving-top area retention, and a
1.20 mm moving-top neck test. Counties may enlarge without a fixed cap to pass
these gates. Keep official mainland shell boundaries; trim fragile lobes from
the moving top only. The seven projects in `county-clickers/physical-test-revision/`
must pass before replacing the complete 32-county package.

## Architecture (do not invent a parallel stack)

- **Local-first + Railway** — same codepaths; config via env only
- **FastAPI** (`backend/app`) — jobs on disk under `data/jobs/`
- **Generator** (`backend/generator/pipeline.py`) — calls design → STLs → `build_project` → painted 3MF
- **Next.js** (`web`) — rewrites `/api/v1/*` to `PIPELINE_API_URL`

Do **not** rewrite geometry in JavaScript. Do **not** add free hex colour pickers — Matte palette IDs only.

## Key entry points

```text
backend/generator/pipeline.py          # generate(name, job_dir, font_style, stand/letter filament ids)
backend/generator/cooper_bowl_design.py
backend/generator/wave_bowl_design.py
backend/generator/hex_bowl_design.py
backend/generator/wave_fit_test.py
backend/generator/build_bambu_project.py
backend/generator/paint_fuzzy_skin.py
backend/app/api/bowl.py
backend/app/services/jobs.py
web/src/app/page.tsx
backend/data/filament_palette.json
```

## Local commands

```bash
cp .env.example .env
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd web && npm install && cd ..

# API (from backend/)
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Web
cd web && PIPELINE_API_URL=http://127.0.0.1:8000 npm run dev

# CLI
.venv/bin/python backend/generator/pipeline.py --name MAX --out data/jobs/cli-max
```

Or `bash scripts/dev.sh`.

## Constraints to respect

- Name: 2–8 letters A–Z; packing must stay within `MAX_RAIL_OUTER_DEG` (45°)
- Letter styles: `bold` (Overpass) | `clean` (Source Sans) | `serif` (Lora) | `slab` (Roboto Slab) | `rounded` (Fredoka) | `playful` (Baloo 2) | `condensed` (Barlow Condensed)
- Filaments: IDs from `filament_palette.json` (Matte)
- Panel fuzzy paint: outer wall fuzzy; **exclude** paw silhouettes and name-rail plaque
- Letters: pocket fit + curved backs — no pin/socket regression
- Object id hygiene in 3MF: `object_N.model` ↔ local id `N` only
- Hex means the solid recessed-honeycomb drum; do not restore the open lattice or foot ring
- Honeycomb: keep the 4 mm hollow wall, 1 mm groove depth, ≥3 mm remaining web, and ≤45° seat ramp
- Honeycomb uses whole-cell suppression around the name; do not restore the long fade that produced ghost hexagons
- Honeycomb keepout derives from the packed glyph envelope with a 1.5 mm margin; do not restore the oversized fixed name field
- Honeycomb radial/Z profiles must be simple positive-area polygons before wrapping
- Honeycomb keeps 5 mm pattern-free edge bands, a 0.45 mm top bead, and a 0.35 mm inward bottom chamfer
- Honeycomb name is optically centred at Z37 within the staggered cell keepout; the safer internal support ramp starts at Z58
- Wave: collar is a hollow 2.4 mm annulus rooted to the bed — never a solid cylinder
- Wave collar outer radius is 74 mm; the continuous upper receiver inner radius is 74.5 mm
- Wave sleeve clearance is locked at 0.5 mm/side after the revised R74/R74.5 coupon seated snugly with minimal wobble and easy hand separation
- Wave halves must use continuous wrapped profiles; per-sector boolean slabs create vertical wall grooves
- Reject any Wave radial/Z profile that is not a simple positive-area polygon
- Wave upper keeps ≥4 mm wall through the lettering zone; do not let its support bridge cross the exterior
- Wave bowl seat is a separate inverted-printing insert: R71.53 locator in the R71.83 shell opening, with its flange resting on the top rim
- Wave 3MFs use avoid-crossing-wall travel, unlimited detours, 0.8 mm / 30 mm/s retraction, layer-change retraction, and 2 mm wipe
- Wave has no name plaque: cut glyph pockets directly into the upper cone and use matching conical letter backs
- Wave letters sit on a large (low-seam) lobe, vertically centred between that seam and the shell top
- Wave upper uses critical-regions-only normal support for pocket-closing layers; remove it before fitting letters
- Use `wave_letter_test.py` to validate real cone pockets and letter backs before a full Wave print

## When changing the design

1. Edit `cooper_bowl_design.py` / paint / build
2. Run CLI generate for a short name (`MAX`) and a wide/long case
3. Open 3MF in Bambu Studio — check pockets, fuzzy, filaments
4. Update `PROJECT_STATUS.md` if a phase or decision changed

## Railway notes (from ogma-print-core lessons)

- Backend listens on `$PORT` (often 8080)
- Web must not hardcode `localhost` for downloads — use proxy / `PIPELINE_API_URL`
- Services do not share filesystem — plan volume or S3 for `JOBS_ROOT`
- Prefer Dockerfile builds over Nixpacks for the storefront

## What not to do

- Don’t commit `.env`, `.venv`, `node_modules`, or `data/jobs/*` outputs
- Don’t reintroduce letter pins or modifier-based fuzzy blockers
- Don’t expand scope to checkout until MVP generate/download is solid on Railway
