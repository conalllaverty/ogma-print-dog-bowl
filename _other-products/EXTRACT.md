# Moving this out into its own repo

Everything here is ready to leave. It runs standalone — that was checked, not
assumed — and nothing in the dog bowl repo imports any of it.

Read `MIGRATION.md` first for what is in here and why `shared/` is a copy.
This file is just the mechanics.

**Do the dog bowl repo's push first.** These commits exist on one machine, and
step 3 deletes files from it.

---

## 1. Copy it out

```bash
cd ~/Documents/GitHub
cp -R ogma-print-dog-bowl/_other-products ogma-print-workshop
cd ogma-print-workshop
```

`cp -R`, not `mv` — the original stays put until step 3, so a mistake here costs
nothing. Rename `ogma-print-workshop` to whatever you like; nothing refers to it
by name.

## 2. Make it a repo and check it runs

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Prove it works before committing anything
PYTHONPATH=shared .venv/bin/python products/oggie-spin/generator/oggie_spin_complete.py --help
```

Bring across the import smoke test, which globs `products/*/generator` and so
needs no edit:

```bash
cp ../ogma-print-dog-bowl/tests/smoke_imports.py tests/smoke_imports.py
.venv/bin/python tests/smoke_imports.py     # 34 ok, 0 failed, 1 skipped, of 35
```

Those numbers are measured: this tree was copied out and the smoke test run
against it before these instructions were written.

`boucle_lamp_fusion` is the expected skip — it imports `adsk.*`, which only
exists inside Autodesk Fusion.

A `.gitignore` worth starting from — the dog bowl repo's, which already knows
about this tree:

```bash
cp ../ogma-print-dog-bowl/.gitignore .gitignore
```

Two rules in it were written for these products specifically and should stay:
`design/**/fusion/` with `*.obj` / `*.mtl` (256 MB of regenerable Fusion mesh
exports), and the note about `bambu_work` 3MFs being tracked *inputs*.

Then:

```bash
git init
git add -A
git commit -m "Split out of ogma-print-dog-bowl: clickers, lamps, Oggie Spin, Squspi ball"
gh repo create ogma-print-workshop --private --source=. --push
```

`--private`. The dog bowl repo is proprietary/all-rights-reserved and its
LICENSE applies to this work too — copy it across if you want that explicit.

## 3. Settle the rescued files, then delete the folder

Before removing anything, resolve the one open question. Two files in
`_rescued-from-to-delete/` **differ from the tracked versions** and nobody has
established which is newer:

```bash
diff _rescued-from-to-delete/oggie_spin_onepiece.py \
     products/oggie-spin/generator/oggie_spin_onepiece.py

diff _rescued-from-to-delete/oggie_spin_batch.py \
     products/oggie-spin/generator/oggie_spin_batch.py
```

~448 and ~18 diff lines. They came from a directory named `misplaced-by-claude`,
which suggests they are the *older* half of a past mistake — but that is a
guess. If the tracked versions win, `rm -rf _rescued-from-to-delete`. Also worth
a look: `modular-spinner/active/README.md`, 551 lines with no equivalent in the
tree.

Once the new repo is pushed and you are happy:

```bash
cd ../ogma-print-dog-bowl
git rm -r --cached _other-products
rm -rf _other-products
git commit -m "Drop the split-out products; they live in ogma-print-workshop now"
git push
```

That reclaims 457 MB from the working tree.

## 4. What it does not do

**`.git` stays ~220 MB.** History still holds every file that was ever here —
290 STLs and 90 3MFs among them. Deleting them going forward does not shrink the
past. If the size actually bothers you:

```bash
pip install git-filter-repo
git filter-repo --path _other-products --invert-paths
```

This **rewrites history**. Everyone with a clone has to re-clone, and any
existing GitHub PRs and branches break. It is worth doing on a repo with one
user and no open PRs, and worth avoiding otherwise. Take a backup clone first.

**The two copies of `ogma` will drift.** Both repos now carry `shared/ogma`, and
nothing keeps them in step. Treat the dog bowl's copy as canonical and port
changes deliberately, or publish `ogma` as a package both depend on — which is
the only real fix and is worth doing if these products stay active.

## 5. If you want the designer here too

Oggie Spin was registered in the studio picker as "coming soon" and that entry
has been removed, because this repo cannot serve it. Wiring it up properly is
the same two steps the dog bowl took, and it is still the honest test of whether
the product-spec abstraction earns its keep:

1. `products/oggie-spin/designer.py` exposing `SPEC = ProductSpec(...)`, with a
   generator implementing `validate(values)` and `generate(values, job_dir)`
2. one line in the studio's `registry.py`

You would need `studio/` here as well — copy it from the dog bowl repo. See
`DESIGNER_SPEC.md` there for the contract.
