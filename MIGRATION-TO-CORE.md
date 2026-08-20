# Moving the bowl into `ogma-print-core`

§9 of [ECOMMERCE-UX.md](ECOMMERCE-UX.md) settled *whether* and *where*. This is
*how*: a file-by-file procedure with a gate on every step.

It is deliberately only the move. Making the bowl a product core can hold
(`Design.productType`, the `method` union, filament slots) is Phase 1 of §7 and
starts after this lands. Rebuilding the designer UI on core's storefront is
Phase 2. A move that also rewrites the 3MF writer is not a move — that is §9's
first named risk and this plan does nothing to earn it.

---

## The finding that shapes the plan: keep the directory names

§9 sketches the target as `backend/ogma/` and `backend/products/dog-bowl/`.
Dropping the `shared/` level costs more than it looks.

Ten modules find the repo root by searching upwards for a sentinel:

```python
_REPO = next(p for p in GENERATOR_DIR.parents if (p / "shared" / "ogma").is_dir())
for _p in (GENERATOR_DIR, _REPO / "shared"):
    sys.path.insert(0, str(_p))
```

Delete `shared/` and that sentinel matches nothing, so every one of them raises
`StopIteration` at import. **28 files reference the `shared` name**; all of them
need an edit under §9's tree.

Keep it, and the number is zero. `backend/` simply becomes what `<repo>` was:

| Expression | Before | After (`backend/shared/`) |
|---|---|---|
| `next(... (p/"shared"/"ogma").is_dir())` | repo root | `backend/` ✓ |
| `Path(__file__).resolve().parents[3]` (tools) | repo root | `backend/` ✓ |
| `Path(__file__).resolve().parent.parent` (tests) | repo root | `backend/` ✓ |
| `assets.SHARED_DIR.parent` | repo root | `backend/` ✓ |

### Verified, not argued

The tree was assembled in a scratch directory and run:

```
backend/
  app/       (stub)
  shared/    ← shared/
  products/  ← products/
  tests/     ← tests/
```

```
pytest         87 passed, 12 failed        ← all 12 in one file, see below
smoke_imports  25 ok, 0 failed, of 25
goldens        6/6 cases built
golden_compare geometry matches the baseline
goldens.json   IDENTICAL to tests/goldens-baseline.json
```

Byte-identical goldens from a relocated tree with **zero source edits**. That is
the whole argument for this shape.

The 12 failures are all `ModuleNotFoundError: No module named 'api'`, all in
`tests/test_retention.py`, because `studio/` was not copied — it is deleted by
the move. Nothing else in the suite touches it.

**Recommendation: deviate from §9's sketch and keep `shared/`.** The cost is a
directory name that reads oddly next to `app/`; the benefit is that the move is
`git mv` and nothing else, which is exactly what risk #1 asks for. Renaming
`shared/` → `ogma/` is a fine follow-up commit once the tree is green, and it
will be a mechanical 28-file change with the goldens already in CI to catch it.

---

## Move map

| From (`ogma-print-dog-bowl`) | To (`ogma-print-core`) | Files |
|---|---|---:|
| `shared/` | `backend/shared/` | 29 |
| `products/` | `backend/products/` | 45 |
| `tests/` | `backend/tests/` (merged) | 15 |
| `fusion/` | `fusion/` (repo root) | 26 |
| `requirements.txt`, `requirements-render.txt` | merged into `backend/requirements.txt` | 2 |
| `AGENTS.md`, `DESIGNER_SPEC.md`, `ECOMMERCE-UX.md`, this file | `docs/dog-bowl/` | 4 |

**Not moved, deleted:**

| Path | Because |
|---|---|
| `studio/api` (11 files) | core's `backend/app` serves the endpoints |
| `studio/web` (27 files) | core's `storefront` is the customer UI |
| `studio/Dockerfile`, `studio/dev.sh` | core has its own |
| `railway.json`, `DEPLOY.md` | core owns deployment |
| `Makefile` | targets fold into core's CI + `backend/` |
| `OGMA-PRINT-STUDIO-PLAN.md`, `OGMA-STUDIO-CHECKLIST.md` | describe a repository that stops existing |

**Left behind:** `_other-products/` — 643 files, 248 MB, archived weeks ago. The
old repository then contains nothing but archived products, which makes
`ogma-print-dog-bowl` a name for everything except the dog bowl. Rename it.

`tests/` filenames were checked against core's `backend/tests/`: **no
collisions**, so the merge is a copy rather than a rename exercise.

---

## Test rehoming

One file needs a decision, and it is not a port.

`tests/test_retention.py` covers job retention, preview-cache LRU eviction and
rate limiting — all of them `studio/api` concerns, and all of them things core
already owns (`backend/app/services/job_store.py`). Its docstring is worth
reading before deleting it:

> Both exist to stop one caller taking the service down — by filling the volume,
> or by monopolising the single build lock. Neither shows up in the goldens, and
> neither is exercised by using the app normally, so they are the parts most
> likely to be quietly wrong.

**Delete the file, and open an issue against core's `job_store` asking whether
its equivalents are covered.** Do not port it — it tests an implementation that
is being thrown away. But do not let the concern evaporate with the code either;
that docstring is describing why nobody would notice.

The other 14 test files move unchanged.

---

## CI: the golden gate

§9's risk #2 is losing the golden harness. It has to run in core's CI **on the
first day of the move, in the same PR**, not soon after.

Core's `backend-unit` job already runs `python -m pytest tests/` from
`backend/`, so the 14 moved test files are picked up with no CI change at all.
`goldens.py` is a script, not a pytest module, so it needs its own job —
transplanted from this repo's `geometry` job:

```yaml
  bowl-geometry:
    name: Dog bowl — generators still build
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install backend deps
        working-directory: backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Build all six golden cases
        working-directory: backend
        run: python tests/goldens.py /tmp/goldens.json /tmp/goldenjobs
      - name: Compare against the baseline
        working-directory: backend
        run: python tests/golden_compare.py tests/goldens-baseline.json /tmp/goldens.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bowl-goldens
          path: /tmp/goldens.json
```

Two things not to lose in translation:

- **`golden_compare.py`, not `diff`.** It compares with measured tolerances
  because the geometry kernels are not bit-reproducible across versions, and it
  deliberately ignores the 3MF member `sha256`s. An exact comparison in CI fails
  on an unrelated dependency bump and everyone learns to ignore the harness.
- **The paint lives in bytes `golden_compare` skips.** A mask that paints the
  wrong triangles leaves the goldens green. `tests/test_fuzzy_paint.py` is the
  cover for that and runs under `backend-unit`; it is not optional.

Core CI triggers on `main` and `feat/hex-pivot` only. Add whatever branch the
move lands on, or the first run happens after merge.

---

## Dependencies and the image

Measured, both `requirements.txt` files parsed:

**The bowl needs, core lacks (8):**
`pydantic-settings`, `rtree`, and the pyrender stack — `pyglet`, `pyopengl`,
`imageio`, `freetype-py`, `networkx`, `six`.

**Core has, the bowl never imports (17):**
`osmnx`, `rasterio`, `opencv-python-headless`, `scikit-image`, `scikit-learn`,
`openai`, `google-genai`, `elevation`, `gpxpy`, `mapbox-vector-tile`,
`reportlab`, `lib3mf`, `matplotlib`, `fonttools`, `defusedxml`, `httpx`,
`python-multipart`.

Nothing conflicts. 11 packages are already shared.

§9's risk #3 — one fat image — is real but smaller than it reads. The heavy half
is already isolated: `requirements-render.txt` is one pinned line
(`pyrender==0.1.45`) installed `--no-deps` on purpose, because pyrender pins
`PyOpenGL==3.1.0` which cannot run its shadow pass under NumPy 2. That comment
must travel with the line; installing it normally breaks the resolve.

Rendering is only used by `render_style_thumbs.py` (a committed build-time
asset) and job stills. **Make the pyrender stack an optional extra rather than a
base dependency**, and the API image gains `pydantic-settings` and `rtree` and
nothing else. Decide this during the move, not after — it is the moment the
question is cheap.

---

## Sequence

Every step ends green. Nothing depends on a later step being right.

**0. Land this branch first.** `flush-letters-and-one-piece` is 16 commits ahead
of its own `main` and unmerged. Moving from a branch carries the divergence into
core; moving from `main` moves a tree without the flush letters, the one-piece
stand, or the print-quality work. Merge to `main`, then move from `main`.
*Gate: `main` has the 16 commits and CI is green.*

**1. Move the files, on a branch in core.** `git mv`-equivalent copy of the four
directories into the shape above, plus the doc moves. No content edits at all.
*Gate: `pytest backend/tests` is 93 passed / 12 failed, and the 12 are
`test_retention.py`.*

**2. Delete `test_retention.py` and open the `job_store` issue.**
*Gate: `pytest backend/tests` is 93 passed, 0 failed.*

**3. Merge requirements.** Union of the two files, pyrender kept as its own
`--no-deps` extra with its comment intact.
*Gate: a clean `pip install` in a fresh venv, then `smoke_imports.py` 25/25.*

**4. Add the `bowl-geometry` CI job.** Add the branch to the trigger list.
*Gate: the job runs and `golden_compare` prints "geometry matches the baseline".
Byte-identical is what it produced locally; tolerances are the fallback.*

**5. Delete `studio/`.**
*Gate: nothing imports it — `grep -rn "studio" backend/` is clean, and the suite
is still 93 passed.*

**6. Merge. Then rename the old repository** to something true, and strip it to
`_other-products/`.

Steps 1–5 are one PR. It is a large diff and a trivial review: every file moves,
none changes.

---

## What this plan does not cover

Deliberately out of scope, in the order they come next:

- **`Design.productType`, the `method: "dog-bowl"` union, filament slots** —
  §7 Phase 1. Starts once the tree is green.
- **The designer UI on core's storefront** — §7 Phase 2, ~1–1.5 weeks. `create/`
  and `cart/` already exist there.
- **Unifying the two 3MF writers.** The bowl has `bambu_project.py`, core has a
  `lib3mf` assembler. §9 risk #1 says explicitly: a separate decision, taken
  later, on its own evidence.
- **The duplicated filament palette.** Core has `filament_palette.py` and
  `filament_slots.json`; the bowl has `shared/ogma/palette.json`. One survives.
  Not during the move.
- **Renaming `shared/` → `ogma/`.** A mechanical 28-file follow-up, with the
  goldens already in CI to catch it.

## Rollback

Steps 1–5 add files to core and change nothing that exists there, so rollback is
reverting one PR. The old repository is untouched until step 6, and step 6 is the
only irreversible one — do it after core has served a real order.
