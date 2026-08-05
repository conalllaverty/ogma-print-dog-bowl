# Golf Tee Lamp — production

Open [`Golf_Tee_Lamp_All_Plates_P2S.3mf`](./Golf_Tee_Lamp_All_Plates_P2S.3mf) in
Bambu Studio (P2S, 0.4 mm nozzle).

Assembled preview: [`../assembly/Golf_Tee_Lamp_Assembly.3mf`](../assembly/Golf_Tee_Lamp_Assembly.3mf).  
Full spec: [`../SPEC.md`](../SPEC.md).

| Plate | Part              | Filament                                  |
| ----: | ----------------- | ----------------------------------------- |
|     1 | Golf ball shade   | Jade White PLA Basic                      |
|     2 | Golf tee          | Caramel Matte                             |
|     3 | Grass base        | Grass Green Matte (fuzzy + tree supports) |
|     4 | Ballast cover     | Grass Green Matte                         |
|     5 | LED reflector cup | Ivory White Matte                         |

## Final slicer check — Plate 1 (before print)

1. **Supports** — `Enable Support` = **OFF**.
2. **Variable Layer Height** — already baked in (0.20 mm → 0.08 mm on top ~20%). Confirm in Preview → Layer Height colouring.
3. **Infill / walls** — **Sparse Infill = 0%**, **Wall Loops = 4** (1.6 mm solid shell).
4. **Seams** — **Back** + scarf **Contour and Hole**; **Arachne**; **Inner/Outer**; wipe **4 mm**.
5. **Fuzzy skin** — **Outer walls only**, **0.04 mm** / **0.08 mm** point distance.

All of the above are set in the generated 3MF; the checklist is a verify-before-print gate.

## Plate 2 notes

Golf tee is exported **snap-foot-down**, with the cup and three bayonet pins
pointing upward. Keep the **8 mm outer brim**, supports off, and 20 mm/s bridge
speed. Its cup and seat undersides are 45° self-supporting flares. Do not flip
it seat-down: the protruding pins become three isolated first-layer islands.
The revised tee has a 21 × 12 mm rounded controller passage through its Ø28
neck and a 7.5 × 5.5 mm radial chase for the MH001 side lead. Its snap is now
Ø73.4 at the shaft and Ø76.4 at the bead; the first Ø74/Ø77 version was too
tight in the printed base.

## Plate 3 notes

Grass base prints **underside on bed**. The cover seat is a **45° loft**, and
Plate 3 has **tree supports** enabled for the ballast pocket roof and cable
trench bridge. Snap opens upward so support scars stay off the snap faces.
Use only the corrected Plate 3: its Ø76.8 mouth narrows to an Ø75.8 insertion
throat and then opens into the Ø77.4 groove. The earlier revised base
incorrectly narrowed to Ø74.2 before the groove and could not accept the tee.
The centre well is 21.8 × 12.8 mm for the rigid controller. Feed it straight
through before snapping in the tee; only the flexible lead belongs in the
7.2 mm underside side trench.
The matching Plate 4 cover is a 111.7→109.3 mm tapered plug: insert its small
face first and press until the large outward face sits behind the felt.

## Plates 4–5 notes

The 1.2 mm cover and 0.8 mm reflector are fully solid from their configured
top/bottom shells and wall loops. Sparse infill stays at **0%**; do not set
gyroid to 100%, which Bambu Studio 2.7 rejects.
Align the reflector's 8.1 mm side notch with the tee chase before seating the
MH001.

```bash
.venv/bin/python backend/generator/golf_tee_lamp.py --out design/golf-tee-lamp/production
```
