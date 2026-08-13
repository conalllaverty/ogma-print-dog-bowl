# Ogma Print Studio — state of play

**Generated 2026-08-11.** Every fact below was checked against the repo, not
recalled. Where something is unverified it says so.

- Branch `oggie-spin`, HEAD `e39253d`
- **24 commits unpushed.** `origin/main` last moved **2026-07-25** — 17 days ago
- `.git` is 194 MB; 287 tracked `.stl`, 3 `.glb`, 89 `.3mf`
- `_to_delete/` holds 2.2 GB

---

## 0. Do this before anything else

- [ ] **Push.** 24 commits exist on one MacBook and nowhere else.

The original audit called this "the single highest-severity finding" when it was
**4** commits. It is now six times worse and covers the entire studio, the
designer, the 3D viewer, the Squspi and Golf Tee lamp packages, and all nine
plates of Oggie Spin work. It costs ten minutes.

```bash
cd ~/Documents/GitHub/ogma-print-dog-bowl
git push -u origin oggie-spin      # or: git checkout main && git merge oggie-spin && git push
```

- [ ] Decide whether `oggie-spin` should still be the working branch, or whether
      this all belongs on `main`

---

## 1. Cleanup — done

### 1.0 Stop the bleeding
- [x] LICENSE added, proprietary / all rights reserved
- [x] Repo confirmed private
- [x] Unlicensed fonts removed from the tree
- [x] In-flight work landed (`6c32c31`)

### 1.1 Untrack what shouldn't be tracked
- [x] `bambu_work` handling settled — and **reverted** (`bcc4929`). Those 3MFs
      are *inputs*: `build_bambu_project` opens them for plate-preview
      thumbnails, and `cooper_base_plate.3mf` is also read by the bouclé and
      golf-tee assemblies. Untracking them broke fresh clones. The `.gitignore`
      now carries a comment saying why they stay.
- [ ] **287 STL + 3 GLB still tracked.** STL is a derived format — every one
      regenerates from a `.py` in seconds. The `.3mf` files are the real
      deliverables (they carry the slicer settings). Dropping STL/GLB and
      keeping 3MF takes tracked content from ~72 MB to ~30 MB.
      *Needs your call: this is a history-going-forward change.*

### 1.2 Import seams
- [x] **Seam A** — filament palette lifted out of the bowl's `pipeline.py` into
      `shared/ogma/filaments.py`. Nine unrelated modules (five bouclé, two golf
      tee, two coupon generators) were importing the entire bowl geometry just
      to resolve a colour swatch. (`f06832b`)
- [x] **Seam B** — 3MF triangle painting generalised into `shared/ogma/paint.py`
- [x] **Seams C and D reclassified** as structural, not import problems — one is
      `products/clickers/`, one is `products/lamps/`. Cutting them as imports
      would have been the wrong fix.

### 1.3 Monorepo layout
- [x] `products/` + `shared/` (`dc5c7a2`); six products now live there
- [x] API and web app moved out of `products/dog-bowl/app` into `studio/`
      (`290f64b`) — an API that serves a *product picker* cannot live inside one
      of the products

### 1.4 Pluggable styles
- [x] `BowlStyle` registry (`d44fd93`). Adding a style was four coordinated
      edits; it is now one module plus one line.
- [x] Proven by adding **Fluted drum** (`6aad2c0`) — the registry's first real
      test. Flute profile mined from the archived v4.5 track, sign inverted.

### 1.5 Test harness
- [x] `tests/goldens.py` — fingerprints mesh volume/area/triangles/bounds/
      watertightness plus a sha256 of every 3MF member, across 5 cases
- [x] `tests/smoke_imports.py` — 38 modules, fresh interpreters
- [x] `tests/test_name_fit.py` — asserts the fast fit check agrees with the
      real build to 1e-9
- [x] `tests/audit_3mf.py` — 14 P2S checks
- [ ] **Convert to pytest and wire up CI.** Right now these are scripts someone
      has to remember to run.

### 1.6 Archive the old bowl track
- [ ] Move v4.5 zips/HTML/SVG generators to `Ogma Print/_archive/named-bowl-v4.5/`
- [ ] Write `ARCHIVED.md` recording the two ideas with no current equivalent:
      the **arched foot ring** and **multi-rim presets**
- [ ] Note both in `products/dog-bowl/SPEC.md` as future options
- [ ] Mark the two memory files ARCHIVED so a future session doesn't chase the
      Fusion rebuild

---

## 2. The designer — done

### The spec
- [x] `shared/ogma/designer.py` — five parameter kinds; options carry capability
      flags; visibility keys off those flags. `page.tsx` no longer contains
      `style === "cooper"`.
- [x] `studio/api/registry.py` — the one file that knows which products exist
- [x] Jobs are product-agnostic (a product id, a values dict, a status)
- [x] `DESIGNER_SPEC.md` explains the reasoning

### Validation
- [x] Field-addressed, server-side, debounced at 350 ms
- [x] `check_declared()` enforces what the spec declares — one copy of each rule
- [x] **Fit gate answers in 9 ms.** A letter's angular half-extent depends only
      on that letter and the font, so the expensive part memoises per
      `(letter, font)` and packing becomes arithmetic. Cold ~2 s, warm 9 ms.
- [x] Hints are computed, not guessed — the bowl measures the name in all seven
      styles and names one that fits, or says plainly that none does
- [x] Cache warmed in a background thread at startup

### The 3D preview
- [x] Role-tagged GLB: `stand__…`, `letters__…`, `bowl__…`. Colour is applied by
      the viewer, so the whole 25-colour palette shares **one** cached model.
- [x] `preview_keys` declares which parameters change geometry; server cache key
      and client staleness check both derive from it
- [x] Four-view mode — front/top/left orthographic + angled perspective, one
      canvas, four scissored viewports
- [x] Render-on-demand (was drawing every frame forever)

### Controls
- [x] Two-column layout, controls left, model right
- [x] Colour + lettering as swatch/typeface dropdowns with full keyboard support
- [x] Style icons rendered from the real meshes (`tools/render_style_thumbs.py`)
- [x] Lettering options drawn in their own typeface, served from
      `shared/ogma/fonts` — the same files the generator rasterises
- [x] CSS-only motion, honours `prefers-reduced-motion`

### Toolchain
- [x] Next 15.1 → **16.3**, React 19.2.8, TypeScript 6.0.3, ESLint 9.39.5
- [x] Tailwind + PostCSS **removed** — unused scaffolding, no directives or
      utility classes anywhere
- [x] `dev.sh` reinstalls when the manifest changes, and refuses a busy port

---

## 3. Bugs found and fixed

- [x] **`POST name="WILLIAMSON"` returned `ok` with `name="WILLIAMS"`.** `coerce()`
      truncated to `max_length`; the browser's `maxLength` was the only real
      guard. On a personalised product that ships the wrong item.
- [x] **Unknown filament id validated clean**, then raised deep in the build.
      Now checked against the palette.
- [x] **The whole model rendered in one colour.** three.js runs glTF node names
      through `sanitizeNodeName`, which strips `. : / [ ]` — `stand::paw_panel`
      arrived as `standpaw_panel`. Separator is now `__`.
- [x] **Untracked `bambu_work`** broke fresh clones — self-caused, reverted
- [x] **Concurrent jobs would interleave.** The generator configures itself
      through module globals; two jobs at once meant a stand with one name and
      letters for another. Serialised behind a lock.
- [x] **Order summary showed database ids** — "cooper · matte-caramel"
- [x] **Dropdown lists painted underneath later fields.** A forwards-filling
      transform animation keeps a stacking context after it settles.
- [x] **`os.nice()` nearly shipped as a footgun** — per-thread on Linux,
      per-*process* on macOS. Unguarded it would have permanently deprioritised
      the whole API server on your Mac.

---

## 4. Production gates — what actually blocks selling

| Gate | Status | Owner | Notes |
|---|---|---|---|
| G1 slice everything | ✅ done | — | `G1-slice-results.md` |
| **G2** one complete stand of each style | ⬜ | **You** | ~3 print days |
| **G3** load test | ⬜ | **You** | **Highest untested risk.** Nothing has been proven to hold a dog's weight |
| G4 specify the adhesive | ⬜ | You | ~2 h |
| G5 cleanability decision | ⬜ | You | ~1 h |
| **G6** source the bowl | ⬜ | **You** | **Single point of failure.** Blocks all pricing |
| G7 compliance | ⬜ | You | ~half a day |
| G8 packaging & instructions | ⬜ | You | ~1 day |
| G9 repeatability | ⬜ | You | ~1 print day |

Nothing in the software list moves any of these. They are the difference
between a working configurator and a sellable SKU.

---

## 5. Next up — software

Ordered by information gained per hour.

### Wire Oggie Spin into the designer
- [ ] `products/oggie-spin/designer.py` + one line in `studio/api/registry.py`
- [ ] Should require **zero** web changes

This is the honest test of whether the product-spec abstraction earns its keep.
It's registered as "coming soon" already, and you've just built nine plates of
real geometry. If it takes more than a spec file and a registry line, better to
learn that now with two products than later with five.

### Repo hygiene
- [ ] Decide on the 287 tracked STLs (see 1.1)
- [ ] `rm -rf _to_delete` — 2.2 GB (I can't delete on your disk, only move there)
- [ ] README still documents `app/ web/`, a layout that hasn't existed for
      three commits
- [ ] pytest + CI

### More bowl styles
- [ ] **Bone lattice** — proposed, never built. Tier 1 in the plan.
- [ ] Remaining Tier 1 / Tier 2 styles

### Deferred by decision
- No pricing — machine time dominates and the bowl has no supplier, so any
  number would be invented
- No checkout — out of scope until the SKUs are print-proven
- County clicker — dropped from the picker for now

---

## 6. Known risks

- [ ] **trimesh version drift.** The container runs 5.0.0; your venv has 4.12.2.
      Golden *volumes* match to 7 decimal places across versions but triangle
      counts drift ~1%. Run `make test` once on your Mac to get a baseline from
      the version you actually print with.
- [ ] **`_union` / `_difference` are defined five times with four distinct
      implementations.** Deduplicating them would silently change geometry in
      four products. Documented, deliberately not touched.
- [ ] **Bambu Studio has never opened a generated 3MF.** `tests/audit_3mf.py`
      checks the file against a P2S profile and passes 14/14, but that is not
      the same as the slicer accepting it.
