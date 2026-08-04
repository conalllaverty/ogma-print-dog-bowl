# Golf Tee Lamp — production

Open [`Golf_Tee_Lamp_All_Plates_P2S.3mf`](./Golf_Tee_Lamp_All_Plates_P2S.3mf) in
Bambu Studio (P2S, 0.4 mm nozzle).

Assembled preview: [`../assembly/Golf_Tee_Lamp_Assembly.3mf`](../assembly/Golf_Tee_Lamp_Assembly.3mf).  
Full spec: [`../SPEC.md`](../SPEC.md).

| Plate | Part              | Filament                           |
| ----: | ----------------- | ---------------------------------- |
|     1 | Golf ball shade   | Jade White PLA Basic               |
|     2 | Golf tee          | Caramel Matte                      |
|     3 | Grass base        | Grass Green Matte (top fuzzy turf) |
|     4 | Ballast cover     | Grass Green Matte                  |
|     5 | LED reflector cup | Ivory White Matte                  |

## Final slicer check — Plate 1 (before print)

1. **Supports** — `Enable Support` = **OFF**.
2. **Variable Layer Height** — already baked in (0.20 mm → 0.08 mm on top ~20%). Confirm in Preview → Layer Height colouring.
3. **Infill / walls** — **Sparse Infill = 0%**, **Wall Loops = 4** (1.6 mm solid shell).

All three are set in the generated 3MF; the checklist is a verify-before-print gate.

```bash
.venv/bin/python backend/generator/golf_tee_lamp.py --out design/golf-tee-lamp/production
```
