# Golf Tee Lamp

A sculptural **golf ball on a tee** for the **Bambu Lab LED Lamp Kit-001**.
Ø175 **Jade White** translucent ball (solid 1.6 mm shell, constant-thickness
dimples), **Caramel Matte** tee with **Ø5 filleted bayonet pins** and lock
detents, **Ivory** reflector cup, and a **Grass Green** base with ballast
cover, felt recess, and fuzzy turf (snap-cleared).

Status: **revised five-plate all-PLA package.**

Review spec: [`SPEC.md`](./SPEC.md)

![Concept elevation](./golf-tee-lamp-concept.svg)

## Parts

| Plate | Part                                    | Filament             |
| ----: | --------------------------------------- | -------------------- |
|     1 | Golf ball shade (bayonet + detents)     | PLA Basic Jade White |
|     2 | Golf tee (Ø5 pins + spring snap)        | PLA Matte Caramel    |
|     3 | Grass base (ballast ledge + fuzzy turf) | Grass Green Matte    |
|     4 | Ballast cover                           | Grass Green Matte    |
|     5 | LED reflector cup                       | Ivory White Matte    |

## Key geometry

| Feature                 |                                                           Value |
| ----------------------- | --------------------------------------------------------------: |
| Ball OD / wall / infill |                                    175 / 1.6 mm / **0% sparse** |
| Dimples                 |                         1.4 mm depth, dual-surface displacement |
| Join                    |   3-lug bayonet · Ø5 · R1.2 fillet · **0.4 mm detent** · PCD 70 |
| Shade print             |                     **Flat bed ring + 45° cone** (supports off) |
| Snap                    |                                Ø77 bead with **4 spring slots** |
| Base                    | **120 mm rounded square** × 18 mm · ballast cover · 110 mm felt |
| Cable                   |                           **Ø18** stem · 19 mm underside trench |
| Reflector               |                                    0.8 mm Ivory cup under MH001 |
| Overall height          |                                                         ~302 mm |

## Files

| File                                                                                           | Use                       |
| ---------------------------------------------------------------------------------------------- | ------------------------- |
| [`SPEC.md`](./SPEC.md)                                                                         | Full design specification |
| [`assembly/Golf_Tee_Lamp_Assembly.3mf`](./assembly/Golf_Tee_Lamp_Assembly.3mf)                 | Whole lamp preview        |
| [`production/Golf_Tee_Lamp_All_Plates_P2S.3mf`](./production/Golf_Tee_Lamp_All_Plates_P2S.3mf) | Five-plate P2S print      |

## Regenerate

```bash
.venv/bin/python backend/generator/golf_tee_lamp.py --out design/golf-tee-lamp/production
.venv/bin/python backend/generator/golf_tee_lamp_assembly.py --out design/golf-tee-lamp/assembly
```

## Final slicer check — Plate 1

Before printing the shade:

1. **Supports** = **OFF**
2. **VLH** baked in (0.20 → 0.08 mm on top ~20%) — confirm in Preview
3. **Sparse Infill = 0%**, **Wall Loops = 4**

## Assembly

1. Fill ballast; drop in cover; fit felt pad.
2. Snap tee into base.
3. Drop reflector; feed MH001 USB first, then inline button, through Ø18 stem; seat module.
4. Bayonet-lock the ball (~60°) until the detent clicks. Reverse to service.
