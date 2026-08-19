# Install

Five minutes, once. Fusion needs to be told where the add-in lives; after that
it loads on every launch.

## 1. Add the add-in

1. Open Fusion.
2. **Utilities** tab → **ADD-INS** → **Scripts and Add-Ins** (or press
   <kbd>Shift</kbd>+<kbd>S</kbd>).
3. Click the **Add-Ins** tab in the dialog.
4. Click the green **+** next to "My Add-Ins" → **Add existing**.
5. Navigate to and select this folder:

   ```
   ~/Documents/GitHub/ogma-print-dog-bowl/fusion/OgmaBowl
   ```

   Select the **OgmaBowl** folder itself, not a file inside it.
6. `OgmaBowl` now appears in the list. Select it, tick **Run on Startup**, then
   click **Run**.

You should get a new **Ogma Bowl** button under **Solid → Create**.

## 2. Add the batch export script

Same dialog, **Scripts** tab this time:

1. Green **+** → **Add existing**.
2. Select:

   ```
   ~/Documents/GitHub/ogma-print-dog-bowl/fusion/OgmaBowlExport
   ```

3. `OgmaBowlExport` appears in the Scripts list. Select it → **Run** whenever
   you want files on disk.

The script asks for a name and an output folder, then builds all four styles
and writes `.f3d`, `.3mf` and `.step` for each.

> The script has to be separate from the add-in. Fusion forbids saving or
> exporting from inside a command event — a command runs in a transaction and a
> save cannot join one — so the toolbar button builds, and the script writes
> files.

## 3. Fonts

The letter styles map to the same faces the Python generator ships:

| Letter style | Font family | Where to get it |
|---|---|---|
| `bold` (default) | Overpass | [Google Fonts](https://fonts.google.com/specimen/Overpass) |
| `clean` | Source Sans 3 | Google Fonts |
| `serif` | Lora | Google Fonts |
| `slab` | Roboto Slab | Google Fonts |
| `rounded` | Fredoka | Google Fonts |
| `playful` | Baloo 2 | Google Fonts |
| `condensed` | Barlow Condensed | Google Fonts |

The `.ttf` files are already in the repo at
`shared/ogma/assets/fonts/` — double-click each one and hit **Install Font** in
Font Book. Restart Fusion afterwards; it reads the font list at launch.

**This matters more than it looks.** Fusion substitutes a default face for an
unknown font name *without telling you*, so an uninstalled font gives you a
model that builds cleanly and prints wrong. If the letters look nothing like
the reference renders, this is why.

## 4. Check it works

**Solid → Create → Ogma Bowl**, leave everything at its defaults, press OK.
You should get the Cooper paw-lattice stand: a base, a paw panel, a top seat
ring, and six letter solids spelling COOPER.

Then open **Modify → Change Parameters** and confirm the `ogma…` rows are
there. Change `ogmaPawRecessDepth` from `0.7 mm` to `1.5 mm` and watch the pads
deepen. That is the whole point — if that works, everything works.

## Troubleshooting

**The button does not appear.**
Re-open Scripts and Add-Ins and check `OgmaBowl` shows as *Running*. If it is
stopped, select it and press Run. If it errors on load, the message box will
have the traceback.

**"Ogma Bowl could not finish" with a traceback about `embossFeatures`.**
`EmbossFeature` was added to the Fusion API in September 2025. Update Fusion.

**The name is silently missing from the wall.**
Sketch text is passed to Emboss as an expression, and expressions need quoting.
If you edited `ogma_name_text` by hand, make sure the text is still wrapped in
single quotes: `'COOPER'`, not `COOPER`.

**Letters come out mirrored, or on the wrong side.**
The name sits on the −Y face by convention (the front, facing you in the
default home view). If your document has a different orientation convention,
rotate the finished bodies rather than fighting the sketch.

**It builds but the model is 10× too big or too small.**
Somebody bypassed `units.py`. Fusion's API is centimetres internally, always,
regardless of document units — a raw `78.0` means 78 cm. Every length in the
codebase goes through `units.mm()` or `units.cm()` for exactly this reason.
