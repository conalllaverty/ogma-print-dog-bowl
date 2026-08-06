# Ogma Print — dog bowl cleanup & production plan

**Written:** 2026-08-06 · **Repo audited:** `ogma-print-dog-bowl` @ `42c1ac4` (branch `oggie-spin`)

Decisions taken before writing this (yours):

1. **Monorepo** — rename to `ogma-print-studio`, restructure as `products/` + `shared/`
2. **Production-ready = sellable SKUs** — close the physical gates, not the Railway deploy
3. **Archive the old bowl track** — Named Bowl v4.5 and the SVG paw-lattice are dead
4. **New designs = more bowl styles** in the existing configurator

---

## Part 0 — What's actually there

### The repo is three things wearing one name

`ogma-print-dog-bowl` contains **seven products** and 29,281 lines of generator code. The dog bowl
is 2,471 of those lines — 8%. (Counting the bowl-specific half of `build_bambu_project.py` and the
three coupon generators, the honest figure is ~4,100 lines, or 14%. Either way: the repo's name
describes a minority of its contents.)

| Product | Generator LOC | Design assets | State |
|---|---:|---|---|
| **Dog bowl** (cooper / wave / hex) | 2,471 | `design/style-previews/` | 3 styles generating, 0 complete prints recorded |
| County clickers | 1,397 | `county-clickers/` 22 MB | 32 counties packaged, 7-county revision awaiting physical approval |
| Bouclé stack lamp | 6,234 | `design/boucle-stack-lamp/` 325 MB | 8-plate package, dry-fit pending |
| Golf Tee lamp | 3,039 | `design/golf-tee-lamp/` 28 MB | 5-plate package, snap socket failed twice |
| Oggie Spin | 6,615 | `design/modular-spinner/` 22 MB | Broken Ring printed & working, physical gates open |
| Squspi ball | 6,477 | `design/squspi-ball/` 580 KB | Reconstruction + fit-test workflow |
| Sushi clicker | 1,051 | `design/sushi-clicker/` 8 KB | — |

Only the dog bowl has a FastAPI backend and a Next.js front end. Everything else is CLI-generated
design packages. That asymmetry is fine — but it should be *visible* in the folder structure, and
right now it isn't.

### Git state — this is the urgent bit

```
branch:        oggie-spin  (not main)
unpushed:      4 commits ahead of origin/main
dirty:         40 files (12 modified, 28 untracked)
origin/main:   last updated 2026-07-25 — 12 days stale
```

**Everything since 25 July exists only on your MacBook.** The Bouclé lamp (6,234 lines), the Squspi
twin-rail review, the county keychain, the physical-test revision, five new scripts — none of it is
on GitHub. One disk failure and it's gone. This is the single highest-severity finding in the audit
and it costs about ten minutes to fix.

### Disk

```
working tree   3.2 GB
├─ data/jobs   2.5 GB   ← gitignored output; _tmp/ alone is 2.2 GB
├─ design/     375 MB   ← mostly untracked
├─ .venv       268 MB
├─ county-…     22 MB
└─ .git         51 MB

tracked content ~72 MB:  STL 32 MB · 3MF 15 MB · PNG 14 MB · GLB 2.2 MB · TTF 2.1 MB · code 0.8 MB
```

Also present: seven `.fuse_hidden*` files (artifacts of editing `AGENTS.md` / `PROJECT_STATUS.md`
over the device bridge), a `_to_delete/` scratch folder, a stray `result.json`, and
`backend/generator/bambu_work/*.3mf` — 4 MB of **intermediate build artifacts committed to git**.

### Two licensing problems

1. **`backend/assets/fonts/Arial-Bold.ttf` (750 KB) and `Arial-Rounded-Bold.ttf`** are Monotype
   proprietary, and are not listed in `LICENSES.md`. **No code loads these bundled files** — the
   seven `FONT_STYLES` map to the OFL/Apache families only, and the "Arial" strings in
   `cooper_bowl_design.py` are `font-family` attributes in an SVG preview, which embed nothing.
   Redistributing the binaries in a GitHub repo is a straightforward licence breach. Delete them.
   `Oswald-Bold.ttf` is OFL but also unused and undocumented.
   *Separate but related:* `squspi_twin_rail_review.py:31` hard-codes
   `/System/Library/Fonts/Supplemental/Arial Bold.ttf` and genuinely loads it via
   `ImageFont.truetype`. That's the macOS system copy, so deleting the bundled files won't break it —
   but it's a machine-specific path that will fail on any other machine or in CI. Point it at a
   bundled OFL face while you're in there.
2. **There is no `LICENSE` file at the repo root.** No licence means all-rights-reserved by default,
   which is probably what you want commercially — but it should be a deliberate, stated choice, and
   it interacts with the OFL/Apache font bundle.

### The docs have become sediment

`PROJECT_STATUS.md` is 22.6 KB and `AGENTS.md` is 24.3 KB. Both are structurally *dog bowl*
documents into which four unrelated products have been poured as unbroken prose. The Bouclé lamp
occupies a 40-line paragraph inside "Repo layout". The Oggie Spin arm-latch history runs for 60 lines
inside "Canonical docs". Every fact in them looks correct — the problem is retrieval, not accuracy.
Nobody, human or model, can find the honeycomb seat-ramp angle in there without grep.

### The style system fights you every time you add a style

Adding one new bowl style today means editing **five files in lockstep**:

```
geometry_config.py     STYLE_<X>, STYLES tuple, STYLE_META entry
pipeline.py            a new branch in the if/elif chain
build_bambu_project.py configure_<x>_objects()  +  build_<x>_project()
app/services/jobs.py   STYLE_CATALOG
web/src/app/page.tsx   any style-conditional UI (e.g. showFuzzy)
```

You said you want more designs. This is the thing standing in the way, and it's a two-day fix.

### Four tangled import seams

The module graph has the shared toolkit depending on the dog bowl, rather than the other way round:

| Seam | Current | Why it's wrong |
|---|---|---|
| **A** | `build_bambu_project` → `paint_fuzzy_skin` → `cooper_bowl_design` | The generic 3MF writer imports paw silhouettes. Every lamp and spinner drags the dog bowl in transitively. |
| **B** | 9 modules → `pipeline.load_palette` | Filament lookup lives inside the *bowl job pipeline*. Lamps import the bowl to read a colour swatch. |
| **C** | `county_clicker` → `sushi_clicker` | The MX-switch geometry lives in whichever clicker was written first. |
| **D** | `golf_tee_lamp_geometry` → `boucle_lamp_coupons` | Same pattern: shared lamp maths parked in the older lamp. |

**Outcome.** A and B are cut and verified byte-neutral. C and D were investigated and
**deliberately not cut** — they are not toolkit-leaking-into-products, they are two designs in one
product family sharing internals (two clickers; two lamps that use the same Bambu LED kit parts).
Forcing an extraction there would move ~3,300 lines for no architectural gain. The fix is structural:
one `products/clickers/` and one `products/lamps/` in §1.3, each with its own internal shared module.

**A trap found while investigating them.** `_union` and `_difference` are each defined **five times**
across five modules — and have **four distinct implementations**. Some handle a list result from the
boolean engine, some call `merge_vertices()`, one validates watertightness and takes a name. They
look like copy-paste duplication and are not. Deduplicating them onto one implementation would
silently change geometry in four products. Any consolidation needs per-product golden tests first,
and today only the dog bowl has them. Same for `_cylinder`: three definitions, three different
signatures. **Do not "clean these up" without goldens.**

### The bowl product itself — where it really stands

`PROJECT_STATUS.md` shows cooper "Live", wave "Print-proven", hex "Live (first cut)". Reading what's
actually recorded:

| | Geometry | Coupon prints | Complete stand printed & assembled |
|---|---|---|---|
| **cooper** (paw lattice) | ✅ 4 plates | letter/rail coupons passed | **not recorded** |
| **wave** | ✅ 4 plates | collar R74/R74.5 ✅ 2026-07-23 · LUNA letter fit ✅ | **not recorded** |
| **hex** (honeycomb) | ✅ 2 plates | none | **not recorded** |

So "print-proven" means *the joints are print-proven*, which is a real and valuable result — but no
complete stand of any style is on record as printed, assembled, and loaded. That is the gap between
here and a sellable SKU, and it's mostly bench work rather than code.

Measured solid volumes from the job files:

| Style | Parts | Solid volume | Solid-equivalent mass @1.24 g/cm³ |
|---|---|---:|---:|
| cooper | base 89.8 + panel 130.7 + ring 48.7 cm³ | 269 cm³ | ≤334 g |
| wave | lower 156.9 + upper 92.0 + seat 9.3 cm³ | 258 cm³ | ≤320 g |
| hex | body 209.3 cm³ | 209 cm³ | ≤260 g |

**UPDATE 2026-08-06 — all three styles have now been sliced. See `G1-slice-results.md`.** The real
figures: cooper **249.65 g / 7h30m**, wave **281.11 g / 7h07m**, hex **212.96 g / 7h55m**, at €5.32–7.03
of filament each. My "45–65% of solid" guess below was too pessimistic — actual is **75–87%**, and a
4 mm wall prints at **95%** because it's all perimeter with nowhere to put infill.

The headline: **all three styles cost about the same, and that cost is a working day of machine time,
not €6 of plastic.** One P2S makes at most ~3 stands/day. Mass and time are *anti*-correlated — hex
uses 25% less filament than wave and takes 11% longer — so pricing on material would systematically
underprice the style that occupies the printer longest.

---

## Part 1 — Cleanup: `ogma-print-dog-bowl` → `ogma-print-studio`

### 1.0 — Stop the bleeding (do this today, ~15 min)

Nothing else in this plan matters if the disk dies first.

```bash
cd ~/Documents/GitHub/ogma-print-dog-bowl

# Bridge/OS junk — safe to delete, they are stale copies of AGENTS.md & PROJECT_STATUS.md
rm -f .fuse_hidden* result.json
rm -rf _to_delete/

# 2.2 GB of scratch that nothing reads
rm -rf data/jobs/_tmp

# .fuse_hidden* should never come back
printf '\n# Device-bridge artefacts\n.fuse_hidden*\n' >> .gitignore

git add -A
git commit -m "wip: Bouclé lamp, Squspi twin-rail, county keychain + physical-test revision"
git push -u origin oggie-spin
```

Then open a PR from `oggie-spin` → `main` and merge it. The branch name has outlived its contents —
it now carries a lamp, a keychain and a clicker revision. Land it and delete it.

**Also confirm the GitHub repo's visibility before the next push.** If it's public, the Arial fonts
(§1.1) are already exposed and should come out in the same commit.

### 1.1 — Untrack what shouldn't be tracked (~30 min)

```bash
# Intermediate build artifacts — regenerated on every run
git rm -r --cached backend/generator/bambu_work
printf 'backend/generator/bambu_work/\n' >> .gitignore

# Proprietary fonts the generator never loads
git rm backend/assets/fonts/Arial-Bold.ttf \
       backend/assets/fonts/Arial-Rounded-Bold.ttf \
       backend/assets/fonts/Oswald-Bold.ttf
```

Then decide on the 32 MB of tracked STLs. STL is a *derived* format — every one is regenerated by a
`.py` in seconds. The `.3mf` files are the actual deliverables (they carry the slicer settings, which
is the hard-won part). Recommendation: **keep `.3mf`, drop `.stl` and `.glb`, keep hero PNGs and drop
the 2 MB render dumps.** That takes tracked content from 72 MB to about 30 MB. Add a
`LICENSE` file in the same commit.

### ~~1.2 — Cut the four import seams~~ ✅ **A and B DONE 2026-08-06 (`f06832b`); C and D reclassified**

This is the only genuinely engineering-shaped part of the restructure. Do it **before** moving files,
so each seam is a small reviewable diff against a familiar tree.

**Seam A — un-couple the 3MF writer from the dog bowl.** `paint_fuzzy_skin` currently reaches into
`cooper_bowl_design` for `LATTICE_BOTTOM`, `NAME_RAIL_FLAT_Z0/Z1`, `NAME_RAIL_OUTER_DEG`,
`WALL_OUTER_R`, `paw_paint_silhouettes` and `unwrap_cylinder_u`. Invert it:

```python
# shared/ogma/bambu/paint.py
class PaintMask(Protocol):
    def regions(self, mesh: trimesh.Trimesh) -> list[Polygon]: ...
    def exclusions(self, mesh: trimesh.Trimesh) -> list[Polygon]: ...

def paint_mask_for_mesh(mesh, mask: PaintMask): ...
```

`unwrap_cylinder_u` is generic cylinder maths and moves to `shared/ogma/geom.py`. The paw silhouettes
and rail constants stay with cooper, which supplies a `CooperPaintMask` at call time. Net effect: the
lamps stop importing the dog bowl.

**Seam B — filaments become shared.** Move `load_palette`, `resolve_filament`, `Filament` and
`filament_palette.json` out of `pipeline.py` into `shared/ogma/filaments.py`. Nine modules change one
import line each. This is the cheapest seam and unblocks the other three.

**Seam C — extract MX-switch geometry.** Whatever `county_clicker` imports from `sushi_clicker` moves
to `shared/ogma/mx.py`. If the two clickers share more than switch pockets, keep them as siblings
under `products/clickers/` instead of two products.

**Seam D — extract shared lamp maths.** `golf_tee_lamp_geometry` importing `boucle_lamp_coupons` is
the same shape as C. Either `shared/ogma/lamp.py`, or accept one `products/lamps/` with two designs
inside. Given both lamps target the same Bambu LED kit, **one `products/lamps/` product is probably
the honest modelling.**

Verification gate for the whole step: regenerate one known-good output per product and diff the mesh
volumes against the committed `dimensions_and_validation.json`. If `MAX_Honeycomb` still reports
209,261.13 mm³ and the Broken Ring plates still slice clean, the refactor is behaviour-neutral.

### 1.3 — Move to the monorepo layout (~half a day)

```
ogma-print-studio/
├── README.md               one table: product · status · where to start
├── LICENSE
├── AGENTS.md               house rules only + links to per-product AGENTS.md
├── pyproject.toml          single venv; installs shared/ as an editable package
├── Makefile
├── .github/workflows/ci.yml
│
├── shared/ogma/            the toolkit — knows nothing about any product
│   ├── bambu/project.py        ← build_bambu_project.py
│   ├── bambu/paint.py          ← paint_fuzzy_skin.py (mask-callback form)
│   ├── bambu/blank_project.3mf
│   ├── filaments.py            ← from pipeline.py
│   ├── palette.json            ← backend/data/filament_palette.json
│   ├── printability.py         unchanged — this module is already clean
│   ├── geom.py                 unwrap_cylinder_u + friends
│   ├── text/glyphs.py          glyph→mesh + curved packing (from cooper_bowl_design)
│   └── fonts/                  7 licensed families + LICENSES.md
│
├── products/
│   ├── dog-bowl/           ← the only product with a web app
│   │   ├── AGENTS.md  SPEC.md  STATUS.md
│   │   ├── styles/             cooper.py · wave.py · hex.py  (see §1.4)
│   │   ├── generator/          geometry_config.py · pipeline.py
│   │   ├── tests/              fit tests: letter · wave_collar · wave_letter
│   │   ├── api/                ← backend/app
│   │   ├── web/                ← web/
│   │   └── design/             ← design/style-previews
│   ├── county-clickers/
│   ├── lamps/                  boucle-stack · golf-tee
│   ├── oggie-spin/
│   ├── squspi-ball/
│   └── sushi-clicker/
└── out/                    gitignored — replaces data/jobs/
```

Use `git mv` throughout so history follows the files. Rename the GitHub repo last (GitHub redirects
the old URL, so nothing breaks).

**Split the two sediment docs as part of the move.** `PROJECT_STATUS.md` and `AGENTS.md` decompose
almost cleanly along product lines — the Bouclé paragraph goes to `products/lamps/STATUS.md`, the
Oggie Spin latch history to `products/oggie-spin/AGENTS.md`, and so on. What stays at root is a
20-line index. The per-product `AGENTS.md` files keep the "do not restore X" constraint lists
verbatim; those are expensively-earned and must not be paraphrased.

### ~~1.4 — Make styles pluggable~~ ✅ **DONE 2026-08-06 (`d44fd93`)**

Replace the five-file edit with a single style module implementing one protocol:

```python
# products/dog-bowl/styles/base.py
@dataclass(frozen=True)
class BowlStyle:
    id: str                     # "cooper"
    name: str                   # "Paw lattice"
    description: str
    available: bool
    supports_fuzzy: bool
    plates: tuple[PlateSpec, ...]           # replaces configure_*_objects()
    def generate(self, ctx: StyleContext) -> StyleReport: ...
```

`pipeline.py` becomes a registry lookup instead of an `if/elif` chain. `build_bambu_project`'s three
near-identical builders — `build_project` (152 lines, the cooper original) plus `build_wave_project`
(100) and `build_hex_project` (87), which are derivatives of it — collapse into one that consumes
`style.plates`. Same for the three `configure_*_objects`. That's roughly 250 lines of duplication out
of a 785-line module, and it's also what makes that module genuinely generic: today 6 of its
functions are bowl-style-specific, which is why calling it "the shared 3MF writer" is only half true. `STYLE_CATALOG` and
`STYLE_META` derive from the registry, so the API and the web UI update themselves.

**Both acceptance criteria met.** Registering a throwaway style — one new file, one line in
`styles/__init__._MODULES` — put it in the API catalogue, the CLI `--style` choices and the web
configurator, and it generated a valid 3MF with no other edit. Regenerating cooper/wave/hex is
byte-identical: 58 meshes and 124 3MF member files unchanged.

Shipped as `backend/generator/styles/` (`base.py` + one module per style). `geometry_config` keeps
geometry only; the catalogue moved to the registry, and that split is load-bearing — `styles/wave.py`
imports `wave_bowl_design` which imports `geometry_config`, so `geometry_config` importing the
registry would be circular. The API serves `supports_fuzzy` per style and `page.tsx` reads it rather
than testing `style === "cooper"`.

**Correction:** the "five files" claim above was slightly wrong — `STYLE_CATALOG` already derived
from `STYLE_META`, so the real edit surface was four sites.

**Still owed:** `build_bambu_project` keeps three near-identical builders (152 / 100 / 87 lines) and
three `configure_*_objects`. They differ in plate composition, not just parameters, so collapsing
them onto `style.plates` is a separate change wanting its own verification pass.

### ~~1.5 — Minimum test harness~~ ◐ **PARTLY DONE 2026-08-06 — `tests/` shipped in `f06832b`**

`tests/goldens.py` and `tests/smoke_imports.py` now exist and are what the whole refactor above was
verified against. `goldens.py` covers items 1 and 2 below (golden volumes, watertight) plus a sha256
of every member file inside each exported 3MF, across 4 cases including the 8-letter `WILLIAMS`
worst case. `smoke_imports.py` imports all 31 generator modules in fresh interpreters — it is what
catches a broken import in lamp or spinner code that no bowl test loads.

**Still to do: items 3 and 4 below (wire `printability.audit()` in; the full 7-font packing sweep),
convert both scripts to pytest, and add CI.** Also still true: `letter_test.py`, `wave_fit_test.py`
and `wave_letter_test.py` are *physical* coupon generators, not software tests — good things,
wrongly named, and they belong under `products/dog-bowl/tests/coupons/`.

One environment note for CI: the generators run clean on trimesh 5.0.0 / numpy 2.4.6 and reproduce
Conall's committed mesh volumes **exactly**. Triangle counts can differ by ~1% on the wave upper
across trimesh versions while volume holds to 7 decimal places — so **assert on volume, not
triangle count**, or pin trimesh.

Four pytest tests would have caught most of what's bitten you historically:

1. **Golden volumes** — generate `MAX`/cooper, `LUNA`/wave, `WILLIAMS`/hex; assert each mesh volume
   within ±0.5% of the committed reference. Catches silent geometry regressions.
2. **Watertight + manifold** on every exported mesh.
3. **`printability.audit()` passes** on every plate at its export orientation. This module already
   exists and is the best thing in the repo — it just isn't wired into anything automatic.
4. **Packing gate** — all 7 fonts × the 8-letter worst case (`WILLIAMS`) stay inside
   `MAX_RAIL_OUTER_DEG = 45°`.

Wire them into `.github/workflows/ci.yml`. Runtime should be a couple of minutes; the honeycomb body
at 504,048 triangles is the slow one, so mark it `@pytest.mark.slow` if needed.

### 1.6 — Archive the old bowl track (~1 hour)

Per your decision, these are dead:

```
Ogma Print/named-bowl-project-v4.5.zip                 (6.0 MB)
Ogma Print/bowl-generator_22.html                      (1.0 MB)
Ogma Print/The-Named-Bowl-review-2026-07-22.zip        (9.6 MB)
Ogma Print/The-Named-Bowl-REVIEW-2026-07-22.html       (1.7 MB)
Ogma Print/dog-bowls/paw-lattice/                      (SVG generator + parts)
Ogma Print/pv-paw-final.png · pv-arch-low.png
```

(The memory note also lists `pv-hexlat.png`; it isn't on disk. Correct the memory file when you
update it.)

Move them to `Ogma Print/_archive/named-bowl-v4.5/` with a one-page `ARCHIVED.md` recording what
they were, why they're archived, and the one thing worth remembering: the **arched foot ring** and
**multi-rim presets** are the two ideas in v4.5 with no equivalent in the current repo. Note them in
`products/dog-bowl/SPEC.md` as future options rather than losing them silently. Then update the two
memory files (`project_named_bowl_fusion.md`, `project_paw_lattice_bowl.md`) to say ARCHIVED at the
top so a future session doesn't chase the Fusion rebuild.

Also drop `backend/generator/cooper_dog_bowl/` from `.gitignore` and the `Documents/Ogma Print Files`
references in `AGENTS.md` if that sandbox is no longer live.

---

## Part 2 — Production-ready: the gates between here and a sellable SKU

Software is not what's blocking you. These are, in dependency order. **G1, G2 and G6 are the
critical path** — everything else can run alongside.

### ~~G1 — Slice everything and get real numbers~~ ✅ **DONE 2026-08-06**

All 10 plates across the three styles sliced on the P2S profile. Full results in
`G1-slice-results.md`; commit that table into `products/dog-bowl/SPEC.md` during the restructure.

| | cooper | wave | hex |
|---|---:|---:|---:|
| Plates | 4 | 4 | 2 |
| Mass | 249.65 g | 281.11 g | 212.96 g |
| Filament cost | 6.24 | 7.03 | 5.32 |
| **Total time** | **7h30m** | **7h07m** | **7h55m** |
| Longest plate | 4h36m | 3h30m | **7h32m** |

What it changed: pricing must be driven by **machine time** (~7.5 h/stand, ~3 stands/day/printer),
not filament. Letters are under 1.5 g and under 25 min in every case, so name length and font count
are commercially free. hex's single 7h32m plate is a distinct operational risk — fewest plate changes,
but a failure at hour seven loses the whole stand.

**Follow-on now unblocked:** set a price. Take the ~7.5 h, decide what an hour of P2S time is worth
to you, add the bought-in bowl from G6, and you have a floor. That is the one number the business
still lacks.

### G2 — One complete stand of each style, printed and assembled ⏱ ~3 print days

The coupon gates passed; the complete article hasn't been built. Print cooper, wave and hex end to
end, assemble each with letters, and photograph. Expect to find: letter pockets that fit the coupon
but not the curved production wall, the cooper 8-pin top-ring joint binding, hex seat-ramp overhangs
at 39°, and elephant's foot on a 170 mm first layer. Log every finding to `STATUS.md` — this is what
turns "Live" into "print-proven".

### G3 — Load test ⏱ 1 day · **highest untested risk**

**Nothing anywhere in the repo checks that these hold a dog's weight.** The static load is modest —
the Ø133 × 35 mm bowl tapering to Ø100 holds about 0.38 L, so a full bowl plus the steel is well
under 1 kg. The load case is the *dog*: a large breed leaning on the rim applies several kilos,
off-axis, repeatedly. Cooper is an *open lattice*; hex is a 4 mm hollow drum with 1 mm grooves cut
into it. Neither has ever been loaded.

Do the cheap version: assembled stand, full bowl, then load the rim progressively — 5 kg, 10 kg,
20 kg — and record where it yields and how. A dog bowl stand that cracks under a dog is a product
recall, and this is the one failure mode that can't be walked back after you've sold thirty of them.
Publish the resulting number as a stated max load.

### G4 — Specify the adhesive ⏱ 2 hours

Letters glue into pockets; cooper is a 3-part glued assembly; the wave collar is glued. **No adhesive
is named for the dog bowl anywhere in the repo** — the Bouclé lamp docs specify "CA or plastic epoxy"
with a bond-proof checklist, and the golf tee mentions optional CA, so the pattern exists; the bowl
just never got one. Pick one (cyanoacrylate for letters, likely a 2-part epoxy for
structural joints), record cure time and working time, and pull-test one glued letter and one
structural joint. Water and dog slobber are the service environment — check the bond survives a wipe
with a damp cloth.

### G5 — Cleanability decision ⏱ 1 hour

This sits under a dog's dinner. Fuzzy skin and an open paw lattice are the two least cleanable
features in the range, and fuzzy is **default on**. Decide deliberately: keep it and say
"hand-wash, wipe with a damp cloth" on the card, or make fuzzy opt-in. Either is defensible; silence
isn't.

### G6 — Source the bowl ⏱ 1 day · **single point of failure**

Every style is dimensioned to `BOWL_RIM_OD = 140.0`, `BOWL_SEAT_D = 142.0`, `BOWL_DEPTH = 35.0`. The
repo does not record **where that bowl comes from, what it costs, or who sells it in quantity.** The
whole product line is built on one unnamed component.

Needs: named supplier + SKU + landed unit cost, a second compatible source, and — critically —
**measure five bowls from one batch with calipers.** Stamped stainless varies by 0.5–1 mm run to run,
and your letter pockets are toleranced at 0.10 mm. If rim OD drifts by 1 mm across a batch, the
`BOWL_SEAT_D = 142.0` interface needs the tolerance designed in now, not discovered at market.

### G7 — Compliance ⏱ half a day

Good news: **a dog bowl stand is not a toy**, so the EN 71 / CE work in your Oggie Spin research
doesn't apply here, and the printed part never contacts food — the steel bowl is the liner. Record
that reasoning; it's the answer to the obvious question.

What does apply is **GPSR (Regulation (EU) 2023/988)**, in force since 13 December 2024 for consumer
products sold in the EU, including pet accessories. In outline that means: manufacturer name and
postal address on the product or packaging, a model/batch identifier, safety information and
instructions in the language of the market, and traceability. Verify the specifics with the **CCPC**
(`productsafety@ccpc.ie`) — the same contact from the toy-safety research, who were helpful before.
Not legal advice; confirm before printing stock. Background reading:
[UL Solutions on GPSR](https://www.ul.com/resources/europe-general-product-safety-regulation-gpsr-eu2023988-replacing-general-product-safety) ·
[GPSR labelling requirements](https://euverify.com/resource/gpsr-labelling-requirements/).

### G8 — Packaging & instructions ⏱ 1 day

A 170 × 170 × 78 mm stand plus a steel bowl plus a bag of loose letters and a tube of glue. Needs: box
spec, an assembly card (letter orientation is not obvious — which way up is a `W`?), the GPSR label
block from G7, and the stated max load from G3.

### G9 — Repeatability ⏱ 1 print day

Print three of the same SKU on different days. Confirm every letter still seats at 0.10 mm pocket
clearance without individual fettling. If it doesn't, that clearance is a batch-variance problem and
needs opening up — better to learn it now than while assembling an order of ten.

### What's explicitly *not* on the critical path

The GLB preview, the Railway deploy, job storage on a volume, and checkout. The configurator is a
lead-generation and order-taking tool; you can sell at market with a printed style card and a form
long before it's deployed. Park it, and revisit once the SKUs are real.

---

## Part 3 — More bowl styles

Every proposal below reuses the **locked Cooper interface** — Ø140 rim, Ø142 seat, 170 mm OD, 78 mm
height, the glyph-pocket letter system — so none of them re-open a solved problem. Ordered by
reuse-of-proven-machinery, which correlates almost perfectly with how quickly they'll actually print.

Do §1.4 (pluggable styles) first. Adding five styles to the current five-file-edit architecture
means twenty-five coordinated edits and a bad afternoon.

### Tier 1 — days, low risk

**1. Fluted drum.** Vertical flutes on the hex drum body, parameterised by count and depth (`fn`,
`fa` — these are exactly the parameters the archived v4.5 generator used, so the maths is already
worked out and worth mining before you archive it). No overhangs, no supports, no new letter work,
and it reads as considered rather than novelty. The obvious next style.
*Reuses:* hex drum + wrapped-profile pipeline. *New:* a radial offset function.

**2. Bone lattice.** The cooper pipeline already does recessed silhouettes with fuzzy-paint exclusion
and a curved name rail — swap the paw motif for bones, or alternate paw/bone rows. This is a motif
change, not a geometry change, and it's the cheapest genuinely new-looking SKU available.
*Reuses:* the entire cooper panel machinery. *New:* one silhouette path.

**3. Terrazzo / speckle.** No geometry at all — flush multi-colour inlays on the hex drum, using the
same 0.32 mm flush-inlay technique proven on the Oggie Spin Broken Ring. Sells as a distinct product
for the cost of a filament change.
*Reuses:* hex body + Broken Ring inlay method. *New:* an inlay scatter function.

### Tier 2 — a week, medium risk

**4. County / GAA.** Emboss a county outline on the drum and offer the county's GAA colours as the
default palette. You already have the OSM boundary pipeline (`county_clicker.py`, 32 validated
boundaries) and `county_gaa_colours.py` sitting in the same repo. Cross-product reuse, and at an
Irish market it's the strongest hook in this list — "Luna, Co. Tyrone" is a different purchase from
"a dog bowl stand".
*Reuses:* county boundary data + hex drum. *New:* boundary→drum projection. *Risk:* fitting an
irregular outline and a name onto one 4 mm wall without either becoming illegible.

**5. Cable knit / Aran.** Raised cable braid around the drum, matching the knitted-style line in your
market pivot. Handsome and very on-brand, but it's the mesh-density case: the honeycomb already
lands at 504,048 triangles, and a cable pattern is denser. Prototype at reduced resolution first, and
keep the 208-row wrapped-profile approach that fixed the honeycomb's stair-stepping.
*Risk:* generation time and 3MF size; overhang angles on the cable crossovers.

### Tier 3 — worth doing, but later

**6. Open arch plinth.** The arched foot ring from the archived v4.5 track — 4–6 arched legs instead
of a full drum. Less material, faster print, visually lighter. **Do not attempt before G3 passes** —
reducing the load path is exactly the wrong move on an untested structure.

**7. Second size.** Cat / small-breed at Ø110–120 rim. The archived v4.5 generator had multi-rim
presets; this is the other idea worth mining from it. Blocked on G6 — sourcing a *second* bowl before
the first one has a named supplier is premature.

### A note on how many

Three styles that are print-proven, load-tested and photographed will sell better than eight that
generate cleanly. **Recommended: ship Tier 1 (fluted, bone, terrazzo) to six SKUs total, then stop
and get G1–G9 closed** before touching Tier 2.

---

## Sequenced plan

| # | Work | Effort | Blocks |
|---|---|---|---|
| **0** | **Commit + push everything; merge `oggie-spin` → `main`** | **15 min** | **everything** |
| 1 | Delete junk (`_tmp`, `.fuse_hidden*`, `_to_delete/`); fix `.gitignore` | 15 min | — |
| 2 | Untrack `bambu_work/`, Arial/Oswald fonts, STL/GLB; add `LICENSE` | 30 min | — |
| ~~3~~ | ~~**G1 — slice all three styles**~~ ✅ **done 2026-08-06** | — | — |
| 3b | **Set a price** from the ~7.5 h machine time + G6 bowl cost | 1 hr | selling |
| 4 | **G6 — name the bowl supplier; caliper five units** | 1 day | all sizing |
| 5 | Cut the four import seams (A–D) | 1 day | 6 |
| 6 | `git mv` to `products/` + `shared/`; split the two sediment docs | 0.5 day | 7, 8 |
| 7 | Pluggable `BowlStyle` registry | 2 days | all new styles |
| 8 | pytest golden-volume / watertight / printability / packing + CI | 1 day | — |
| 9 | **G2 — print one complete stand per style** | 3 print days | G3 |
| 10 | **G3 — load test to failure; publish a max load** | 1 day | G8, arch style |
| 11 | G4 adhesive · G5 cleanability · G7 GPSR · G8 packaging · G9 repeatability | 3 days | selling |
| 12 | Tier 1 styles: fluted · bone · terrazzo | 3 days | — |
| 13 | Archive Named Bowl v4.5 + paw-lattice; update memory files | 1 hr | — |

**Two weeks of focused work** gets you from here to six print-proven, load-tested, priced SKUs in a
repo that makes the seventh style a one-file change.

Step 0 takes fifteen minutes and protects twelve days of unbacked work. Do that one tonight
regardless of what you think of the rest.
