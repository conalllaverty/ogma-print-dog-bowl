# Oggie Spin — archive

**Nothing in this tree is a live design.** Do not build, print, or copy
tolerances from these packages. The only active design is
[`../active/`](../active/) — the Broken Ring Illusion.

Kept for provenance: these record what was tried, what was measured, and why
each direction was dropped. Several carry physical test results that still
constrain the active design.

| Folder | What it was | Why it is archived |
| ------ | ----------- | ------------------ |
| [`clip-lock-complete/`](./clip-lock-complete/) | The plain five-colour nine-plate package — same mechanism, no optical inlays. Includes `Oggie_Spin_Complete_P2S.3mf`, the one-plate `Oggie_Spin_5x_Clip_Lock_P2S.3mf` batch, meshes, assembly GLB and `dimensions_and_validation.json`. | Superseded by the Broken Ring Illusion, which is the same spinner with the winning optical treatment. **Its `dimensions_and_validation.json` is still the dimensional reference** for the shared mechanism. |
| [`broken-ring-batch/`](./broken-ring-batch/) | `Oggie_Spin_5x_Broken_Ring_P2S.3mf`, the one-plate five-arm batch print of the active design, plus a stale duplicate core inlay mesh (`02_ivory_white_core_broken-ring_inlay.stl`, superseded by the `_+_br` version). | Only the nine-plate project is in the current workflow. Note the generator re-emits this batch file on every run — delete it from `active/` after rebuilds. |
| [`bayonet-fit-test/`](./bayonet-fit-test/) | The original R188 + M3 screw/nyloc cap mechanism and its bayonet fit-test coupons. | Replaced by the fully printed Tough+ split-collet cartridge. No metal fastener remains in the design; the R188 is the only non-printed part. |
| [`optical-variants/`](./optical-variants/) | Seven core-and-arm optical experiments — full-body vortex (`VX`), spiral/wave (`SP`), chevron (`CH`), strobe (`ST`), opposing drift (`OD`), colour pulse (`CP`), dashed ladder (`LD`) — plus the separate shutter/exposed-infill prototype (`SH`). | The broken-ring treatment won. These are the losing candidates. |
| [`visuals/`](./visuals/) | Early renders: `hero-assembled`, `exploded`, `cap-stack`, `joint-detail`. | All show the earlier **three-arm** direction with the single-barb joint and M3 cap stack. Superseded by the current concept sheet in `active/`. |
| `lok-core-concept.svg` | The earliest Lok Core joint concept sheet. | Superseded by `active/oggie-spin-concept.svg`. |

## Findings that still bind the active design

Retired mechanisms — **do not restore any of these:**

- **Friction ribs** — interference ribs on the dovetail flanks. Shaved material
  on repeated swaps. Replaced by a loose slide plus a dedicated latch.
- **Rigid side detents** — non-compliant bumps. A rigid detent in a swap joint
  either shaves or will not seat.
- **Pinch-Lok flex rails/barbs** — latch integrated into the rails themselves.
  The surviving design deliberately separates the jobs: rails carry radial and
  torsional load, the latch carries axial only.
- **Legacy barb recesses** — the mating recesses for the old barbs. Removing
  them is what makes the current core/arm a matched pair.
- **Solid-slide arms** — no active latch, retention by fit alone. Released with
  a straight pull.
- **Long petal arms** — the only retirement backed by physical testing: easy
  lift, rattle, and uneven one-side lock. This is why the current wrap is short
  (R20.12–R24.5, ±20°). **Do not reintroduce a long lever arm.**

Bearing pocket fits measured physically: Ø12.86 released under gravity, Ø12.78
was too tight, Ø12.68 would not hand-install. Ø12.82 is the hand-fit target.

Wrap clearance: 0.25 mm rattled, which is why 0.12 mm was chosen — but see
[`../ARM-RETENTION-REVIEW.md`](../ARM-RETENTION-REVIEW.md), which argues that
rattle came from the wrap being asked to do location work.

## Regenerating archived packages

Only if you need to reproduce a retired build:

```bash
.venv/bin/python backend/generator/oggie_spin_complete.py \
  --out design/modular-spinner/archive/clip-lock-complete
.venv/bin/python backend/generator/oggie_spin_bayonet.py \
  --out design/modular-spinner/archive/bayonet-fit-test
.venv/bin/python backend/generator/oggie_spin_optical_variants.py \
  --out design/modular-spinner/archive
.venv/bin/python backend/generator/oggie_spin_shutter_infill.py \
  --out design/modular-spinner/archive
```

**The generator modules are not archived.** `oggie_spin_complete.py`,
`oggie_spin_bayonet.py` and `oggie_spin_optical_variants.py` are all live
dependencies of the active Broken Ring build — see the dependency map in
[`../README.md`](../README.md). Only `oggie_spin_shutter_infill.py` is
standalone.
