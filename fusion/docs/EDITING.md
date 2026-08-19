# How to change each design

Three levels, cheapest first:

1. **Change a parameter.** `Modify > Change Parameters`, type a number, Enter.
   Everything in [PARAMETERS.md](PARAMETERS.md) works this way.
2. **Edit a feature.** Right-click a timeline step → *Edit Feature*, or
   double-click a sketch to redraw it. The rest of the timeline rebuilds.
3. **Change the recipe.** Edit the Python in `fusion/OgmaBowl/ogma_bowl/` and
   re-run the command. Use this for anything structural.

Whichever you use, **run `python3 fusion/tests/check_parity.py` after touching
`config.py`** — it is the only thing stopping the Fusion constants drifting
away from the trimesh generator's.

---

## Things that are locked, and why

These came from physical prints. Change them and you are re-opening a question
that has already cost a print.

| Value | Locked at | Why |
|---|---|---|
| Bowl seat diameter | 142 mm | The Cooper stainless insert. Every style seats it. |
| Bowl bore | 133 mm | Same insert. |
| Rim recess | 1.8 mm | The bowl nests slightly rather than perching. |
| Wave collar clearance | 0.5 mm/side | Passed physically on the P2S, 2026-07-23, at R74 into R74.5. Seated snugly, separated by hand. |
| Letter pocket depth | 0.85 mm | Seats a 1.4 mm letter without a trench. |
| Letter pocket clearance | 0.10 mm | Tighter than this and letters bind; looser and grey shows at the edges. |
| Paw recess depth | 0.7 mm | Deep enough to read, shallow enough not to swing layer time and band the wall. |
| Max name | 8 letters, ±45° | Past this the name stops reading as a word from a normal viewing angle. |
| Honeycomb web | ≥3 mm | 4 mm wall minus a 1 mm groove. |
| Fluted web | ≥2.5 mm | Enforced in code — the build refuses to go below it. |

---

## Honeycomb (`hex`)

### Make the cells bigger or smaller
`ogmaHexCellRadius`. **But** the column count is derived and then quantised to
an even number, so a small edit often changes nothing at all. The current
9.24 mm target gives 36 columns of 9.49 mm cells. To actually move it, aim for
a target that lands on a different even count — roughly, 8.7 mm gives 38
columns and 9.9 mm gives 34.

### Change the groove look
- `ogmaHexGrooveDepth` — how deep. Watch the web: wall (4 mm) minus this must
  stay ≥3 mm.
- `ogmaHexGrooveGap` — how wide the valley between tiles is.
- `ogmaHexGrooveChamfer` — how much the groove wall slopes. It is applied as
  the taper angle on the tile extrusion; the generator uses a smoothstep, this
  uses the straight equivalent (`atan2(chamfer, depth)`).

### Move or resize the name field
`ogmaHexLetterCenterZ` moves it up and down. `ogmaHexNameMargin` sets how much
clear space surrounds it.

The honeycomb is suppressed behind the name by a **filled patch** — find `Name
patch` in the timeline and edit its sketch to reshape it. The generator instead
suppresses whole honeycomb cells so the smooth area is bounded by complete cell
edges. Filling reads the same at arm's length and, unlike per-instance pattern
suppression, survives a change to the cell size.

### Rebuild the whole pattern differently
`ogma_bowl/styles/hex.py`, `_tile_column()`. Tiles are drawn as flat hexagons
on a tangent plane, patterned around and up, then trimmed flush to the true
cylinder. To make them a different shape, change `_hexagon_points()`.

---

## Fluted (`fluted`)

### Change flute count or depth
`ogmaFluteCount` and `ogmaFluteDepth`. The build refuses any depth that leaves
less than `ogmaFluteMinWeb` (2.5 mm), so it will tell you before it makes
something unprintable rather than after.

### The one real difference from the generator
The generator's flute is a sine:

```
offset(theta) = -flute_depth * (0.5 + 0.5 * sin(flute_count * theta))
```

A revolved sinusoid has no BRep form that stays editable when you change the
flute count, so each flute is cut with a **cylinder** sized from that sine's own
pitch and depth. Flute count, depth and remaining web are identical; the valley
floor is a circular arc instead of a sine crest — under 0.05 mm apart, an
eighth of a layer line.

To change the profile shape, edit `config.flute_cutter()`. To go back to a true
sine you would need a swept spline surface, and you would lose the live
parameter.

### Why this style needs no supports
Flutes are constant in Z, so every layer has an identical footprint. No
overhang anywhere on the wall, and — unlike the honeycomb — no layer-time
variation, which is the main driver of banding on a cylinder. Keep any change
constant in Z and that property holds.

---

## Cooper paw lattice (`cooper`)

Four printed parts: base, paw panel, top seat ring, letters.

### Change the paws
- `ogmaPawRecessDepth` — how deep the pads sit.
- `ogmaPawCount` — paws per row (default 16).
- `ogmaPawRow1Z` / `Row2Z` / `Row3Z` — row heights.

To change the paw **shape**, edit `cfg.PAW_LOBES` in `config.py`. It is seven
tuples of `(du, dz, tangent_radius, vertical_radius, tilt_deg)` — three
metacarpal lobes then four digits — transcribed from the generator's
`iter_paw_pad_specs()`. `du` is millimetres of arc at an 80 mm reference
radius, so the shape stays correct if the wall radius changes.

Pads that fall inside the name-rail keepout are suppressed on the pattern, not
skipped at creation. That needs the timeline marker rolled back to the pattern
first, which `api.suppress_pattern_elements()` does — it is a documented
precondition, not a hack.

**Difference from the generator:** lobes are tapered elliptical cuts rather
than ellipsoid bites, so the pad floor is a shallow cone rather than a dish. At
0.7 mm deep the silhouette — which is the entire visual of the pad — is
identical, and it is one sketch and one cut per paw instead of 21 features.

### Change the name plaque
`ogmaRailOuterR` (how proud), `ogmaRailZ0`/`ogmaRailZ1` (the flat face), and
`ogmaRailInnerR` (how far it roots into the wall). Its **angular** size is
computed from the packed name, so a longer name widens it automatically.

The trapezoid profile gives the plaque its long Z blends. Do not square them
off: an abrupt ledge changes the layer cross-section in one step and prints as
a bright ring right around the cylinder.

**Difference from the generator:** the plaque's angular ends are square-cut,
where the generator eases them over 1.5°. If you want them softened, add a
Fillet on the two vertical edges after the `Add name plaque` timeline step.

### Change the panel/ring joint
`ogmaPinCount`, `ogmaPinRadius`, `ogmaPinHoleRadius`, `ogmaPinCircleR`,
`ogmaPinHeight`. The fit is the difference between pin and hole radius —
currently 0.25 mm.

---

## Wave (`wave`)

Three printed parts: lower half, upper shell, bowl seat insert.

### Change the wave
`ogmaWaveAmp` (amplitude), `ogmaWaveCount` (periods), `ogmaWaveSeamPercent`
(seam height as a percent of stand height).

**These three need the command re-run, not just a parameter edit.** The seam is
a sine wrapped on a cylinder; it is sampled into two closed 3-D splines at
build time and lofted into a ruled surface that splits the halves. Editing the
parameter updates the number in the dialog but not the splines.

Everything else on this style — radii, wall thicknesses, collar, seat insert —
is live.

### Change the collar fit
`ogmaWaveCollarClearance`. **Read the locked table above first.** 0.5 mm/side
at R74 into R74.5 is the pair that passed physically. If halves will not seat,
check for elephant's foot on the collar before changing this number.

### Change the shell profile
`ogmaWaveTopR`, `ogmaWaveBottomR`, `ogmaWaveWallThick`,
`ogmaWaveMinUpperWall`. The build asserts five envelope conditions and will
refuse with a specific message rather than producing a shell that violates one
— e.g. *"Wave seat flange must stay inside the exterior rim."* Those checks are
transcribed from the generator's `_wave_upper_dimensions()`.

### If the seam fails to build
You will get a note saying `SEAM FALLBACK` and two un-split halves. The loft
through closed 3-D splines is the least-certain call in the whole package.
Either re-run, or split by hand: `Modify > Split Body`, pick both halves, and
use the `Seam surface` bodies as the tool.

---

## The letters (all styles)

### Change the name
Re-run **Ogma Bowl**. Or edit the `ogma_name_text` sketch text in place — but
then edit `ogma_letter_text` to match, or the printed letters will spell the
old name.

Keep the single quotes. Sketch text is an *expression*, so `'LUNA'` is text and
`LUNA` is a parameter reference that evaluates to nothing.

### Change the letter fit
- `ogmaLetterPocketClearance` — raise it if letters bind, lower it if grey
  shows around the edges.
- `ogmaLetterPocketDepth` — how deep they seat.
- `ogmaLetterThickness` — how proud they stand.
- `ogmaLetterGap` — spacing between letters.

### Change the letter face
Re-run the command and pick a different letter style. See
[INSTALL.md](INSTALL.md#3-fonts) — the font must be installed or Fusion
silently substitutes another and the model looks wrong while building fine.

### How the letter solids are made
Emboss can add material in the shape of text but cannot keep the text and throw
away the surround. So the letters are grown off a sacrificial 0.5 mm shell
whose outer surface sits exactly at the pocket floor radius, then split free at
that radius — which leaves each letter with a concave back that already matches
its pocket, with no boolean involved.

If you want a flat-backed letter instead, delete the `Free the letters` split
and cut with a plane.

**Difference from the generator:** the letter's outer face is a coaxial
cylinder rather than a flat chord. Across a 15 mm cap height at R87 that is
0.3 mm, and the curved version holds a more even proud height across the glyph.
