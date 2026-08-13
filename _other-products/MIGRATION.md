# These products are on their way out of the dog bowl repo

Everything here was split out of `ogma-print-dog-bowl` on 2026-08-13, so that
repo could narrow to one product: the dog bowl stand and its designer.

Nothing in here is broken. It was moved, not retired.

## What's here

| Path | What it is |
|---|---|
| `products/clickers/` | 32 Irish county MX-switch clickers + salmon nigiri clicker |
| `products/lamps/` | Bouclé Stack and Golf Tee, both on the Bambu LED Kit 001 |
| `products/oggie-spin/` | Modular fidget spinner, Broken Ring Illusion |
| `products/squspi-ball/` | Squspi ball reconstruction + twin-rail review |
| `shared/` | A **copy** of the `ogma` toolkit, taken at the time of the split |
| `requirements.txt` | A copy of the dog bowl repo's, unedited |
| `_rescued-from-to-delete/` | See below — needs a decision before you trust it |

## Why `shared/` is a copy

These products import the toolkit — `ogma.filaments` for the Matte palette,
`ogma.bambu_project` to build 3MFs, `ogma.paint` for fuzzy skin. Two lamp
modules also read a shared asset by path:

```
products/lamps/generator/golf_tee_lamp_assembly.py:276   cooper_base_plate
products/lamps/generator/boucle_lamp_assembly.py:518     cooper_base_plate
```

which resolves to `shared/ogma/bambu/plate_previews/cooper_base_plate.3mf`. That
file is included in the copy.

So this directory runs standalone. The cost is that there are now two copies of
`ogma`, free to drift. That is a real problem and it has exactly one good fix:
publish `ogma` as a package both repos depend on. Until then, treat the dog bowl
repo's copy as canonical and port changes deliberately.

**Nothing here imports the dog bowl.** That was checked, not assumed — the seam
work in `f06832b` and the `paint.py` split are what made this a clean cut rather
than an untangling.

## Running it after extraction

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

PYTHONPATH=shared .venv/bin/python products/oggie-spin/generator/oggie_spin_complete.py
```

Each generator expects its own directory on `sys.path` (intra-product imports
are flat, `import oggie_spin_bayonet`) plus `shared/`. The dog bowl repo's
`tests/smoke_imports.py` is a working example of setting that up, and is worth
copying across — it globs `products/*/generator`, so it needs no edit to work
here.

## `_rescued-from-to-delete/`

These were sitting in a `_to_delete/` scratch directory that was cleared during
the split. They were pulled out rather than deleted because **two of them differ
from the tracked versions** and nobody has established which is newer:

| File | Status |
|---|---|
| `oggie_spin_onepiece.py` | differs from `products/oggie-spin/generator/` copy by ~448 diff lines |
| `oggie_spin_batch.py` | differs by ~18 diff lines |
| `modular-spinner/active/README.md` | 551 lines, no equivalent in the tree |
| `snap-tab-sections.png`, `02_ivory_white_core_*.stl` | design reference / derived output |

Diff the two `.py` files against `products/oggie-spin/generator/` before doing
anything else. If the tracked versions win, delete this directory. The rescued
copies came from a directory named `misplaced-by-claude`, which suggests they
are the *older* half of a mistake — but that is a guess, and 448 lines is too
many to discard on a guess.

## History

The split was a plain move, by decision: no `git filter-repo`, no subtree
extraction. When this becomes its own repo it starts with a fresh `git init` and
no prior commits. The dog bowl repo's history still contains every file that was
here, so nothing is lost — it is just not carried forward.
