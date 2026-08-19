# Ogma bowls in Fusion

The four dog-bowl styles as **editable parametric Fusion models** — a real
timeline, real sketches, real features, and every dimension exposed as a User
Parameter you can type a new number into.

| | |
|---|---|
| **Install** | [docs/INSTALL.md](docs/INSTALL.md) |
| **Every parameter, what it does** | [docs/PARAMETERS.md](docs/PARAMETERS.md) |
| **How to change each design** | [docs/EDITING.md](docs/EDITING.md) |

## Why this is a script and not a .f3d

A `.f3d` is a proprietary Autodesk archive; nothing outside Fusion can author
one with a working timeline. But Fusion runs Python, and a script that builds
native BRep geometry produces exactly what a hand-modelled file would — with
the advantage that the *recipe* is in version control next to the trimesh
generator it was derived from.

So this ships as an add-in you install once. It gives you:

- **a toolbar button** — `Solid > Create > Ogma Bowl`. Type a name, pick a
  style and a letter face, press OK.
- **a batch script** — `OgmaBowlExport` builds all four styles for one name and
  writes `.f3d`, `.3mf` and `.step` to a folder you choose. Those `.f3d` files
  are ordinary Fusion documents; open, edit, save, share.

## Changing the name

Two ways, both supported:

1. **Re-run the command.** `Solid > Create > Ogma Bowl`, type the new name, OK.
   Fastest, and it re-packs the letters and re-sizes Cooper's name plaque to
   match.
2. **Edit the sketch text.** In the timeline, double-click the `ogma_name_text`
   sketch, double-click the text, retype. The pockets rebuild. You will want to
   do the same to `ogma_letter_text` so the printed letters match.

Fusion User Parameters are numeric only, so the name cannot be one. The command
dialog is the closest thing to a "name field", which is why it exists.

## Layout

```
fusion/
  OgmaBowl/                add-in — install this
    OgmaBowl.py            toolbar command + dialog
    OgmaBowl.manifest
    ogma_bowl/
      config.py            geometry constants, transcribed from the generator
      units.py             the only place mm <-> Fusion's internal cm happens
      api.py               thin wrappers, current API signatures only
      params.py            User Parameters — the editable control surface
      letters.py           name pockets + glue-in letter solids
      build.py             orchestration
      styles/              one module per style, same registry shape as Python
  OgmaBowlExport/          batch script — build all four, write files
  docs/                    install, parameters, editing
  tests/                   run these before you trust a change
```

## Before you trust a change

```bash
python3 fusion/tests/check_parity.py       # 106 values vs. the generator
python3 fusion/tests/smoke_imports.py      # module graph + pure-Python logic
python3 fusion/tests/check_api_surface.py  # no retired/nonexistent Fusion API
python3 fusion/tests/gen_parameter_doc.py  # regenerate PARAMETERS.md
```

`check_parity.py` is the important one. The Fusion side cannot import
`geometry_config.py` — Fusion ships its own Python without numpy, trimesh or
shapely — so the constants are transcribed, and a transcription rots silently.
That script compares all 106 of them and fails on any drift.

`check_api_surface.py` exists because Autodesk has retired a fair amount of the
API that sample code still calls. It statically rejects `setDistanceExtent`
(retired 2022-09), `SketchTexts.createInput2` (retired 2025-11),
`create3MFExportOptions` (never existed — it is `createC3MFExportOptions`) and
a handful of others.

## Relationship to the trimesh generator

`products/dog-bowl/generator/` remains the production path: it is what the
configurator calls, what produces painted multi-colour 3MFs, and what the
golden harness regression-tests. This is the **design** path — for changing
shapes by hand, trying a variation, or handing a model to someone who works in
CAD rather than in Python.

Where the two differ, [docs/EDITING.md](docs/EDITING.md) says so explicitly per
style. The differences are all in surface texture construction, never in the
locked interfaces: the Cooper bowl seat, the wave collar clearance, the letter
pocket depth and the print-proven fits are identical in both.
