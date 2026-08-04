# Golf Tee Lamp — Design Specification (for review)

**Status:** revised — all-PLA workflow, bayonet detents, ballast cover, reflector.  
**Not production-ready** until MH001 fit, bayonet lock, snap retention, ballast stability, and lit glow pass physical checks.  
**Hardware:** Bambu Lab LED Lamp Kit-001 (MH001) only.  
**Printer target:** Bambu Lab P2S, 0.4 mm nozzle.  
**Workflow:** All-PLA (no PETG support interface).

Canonical numbers: [`backend/generator/golf_tee_lamp_config.py`](../../backend/generator/golf_tee_lamp_config.py).

---

## 1. Product intent

Sculptural **golf ball on a tee** desk lamp:

- Ø175 dimpled **semi-translucent** shade (solid 1.6 mm shell — no infill shadows)
- Matte Caramel tee with **Ø5 filleted bayonet pins** + **0.4 mm lock detents**
- Ivory White **reflector cup** under the MH001
- Grass Green base with **ballast pocket + printed cover**, felt pad, and fuzzy turf
- Cable fully internal; Ø18 stem clears the inline switch and USB

---

## 2. Assembly overview

```text
        ┌─────────────────────┐
        │  Ø175 dimpled ball  │  Jade White PLA Basic · bayonet + detents
        └──────────┬──────────┘  ¼-turn lock onto Ø5 pins
                   │
        ┌──────────┴──────────┐
        │  Tee cup + LED      │  Ivory reflector · MH001 · Ø18 bore
        │  Slotted spring foot│
        └──────────┬──────────┘
                   │ click
        ┌──────────┴──────────┐
        │  Grass base         │  Ballast + cover + felt + fuzzy turf
        └─────────────────────┘
```

| Quantity        |                                Value |
| --------------- | -----------------------------------: |
| Overall height  |                              ~302 mm |
| Widest diameter |                               175 mm |
| Base footprint  |          120 × 120 mm rounded square |
| Printed parts   |                                    5 |
| Non-printed     | MH001 + ballast + 110 mm square felt |

---

## 3. Bill of materials

| Plate | Part            | Filament                                    | Notes                                 |
| ----: | --------------- | ------------------------------------------- | ------------------------------------- |
|     1 | Golf ball shade | **PLA Basic Jade White** (semi-translucent) | Solid shell; supports off (45° skirt) |
|     2 | Golf tee        | **PLA Matte Caramel**                       | Ø5 pins + R1.2 fillets                |
|     3 | Grass base      | Grass Green Matte                           | Fuzzy turf clears snap entry          |
|     4 | Ballast cover   | Grass Green Matte                           | 1.2 mm drop-in plate                  |
|     5 | Reflector cup   | **Ivory White Matte**                       | 0.8 mm liner under MH001              |

Bought-in: MH001; 200–300 g steel washers/shot; **110 × 110 mm** × 1 mm felt or silicone pad.

---

## 4. Ball shade — light quality

### 4.1 Solid shell (no infill shadows)

| Setting           | Value                                                  |
| ----------------- | ------------------------------------------------------ |
| Wall              | **1.6 mm constant** (4 × 0.4 mm passes)                |
| Sparse infill     | **0%**                                                 |
| Top/bottom shells | 5                                                      |
| Filament          | Jade White PLA Basic (not Matte — Matte blocks lumens) |

Dimples use dual-surface displacement so wall thickness never thins into hotspots (`d_max` 1.4 mm, `α_max` 0.058 rad, ~550 Fibonacci centres).

### 4.2 Self-supporting entry (no shade supports)

The opening prints on a **flat bed ring** (~4.8 mm radial width, Ø94.5 OD) that rises into the sphere on a **45° cone** (~14.6 mm tall). This replaces the shallow spherical overhang that forced 300 g+ of support. Dimples start above the blend. Tee seat is a matching **flat-ring rebate**.

| Feature             |                                   Value |
| ------------------- | --------------------------------------: |
| Overhang            | **45°** from vertical (self-supporting) |
| Bed ring OD / width |                   **94.5 mm** / ~4.8 mm |
| Cone height         |                                ~14.6 mm |
| Supports            |                    **Off** on the shade |

### 4.3 Final slicer check — Plate 1 (before print)

Before hitting print on the golf ball shade in Bambu Studio:

1. **Supports** — `Enable Support` = **OFF** (self-supporting 45° skirt).
2. **Variable Layer Height** — already baked into the 3MF (`Metadata/layer_heights_profile.txt`): **0.20 mm** through the lower 80%, ramping to **0.08 mm** on the apex. Confirm in Preview with the **Layer Height** colour scheme.
3. **Infill / walls** — confirm **Sparse Infill = 0%** and **Wall Loops = 4** (exact 1.6 mm solid shell).

---

## 5. Bayonet join

| Parameter   |                                       Value |
| ----------- | ------------------------------------------: |
| Lugs / pins |                                    3 @ 120° |
| Twist       |                         ~60° (~¼-turn feel) |
| Pin Ø × H   |                            **5.0 × 4.0 mm** |
| Root fillet |                                 **R1.2 mm** |
| Detent      | **0.4 mm** bump at lock end of each L-track |
| PCD         |                                       70 mm |
| Ball        |             Internal flange + L-track slots |
| Tee         |                               Matching pins |

**Service:** reverse-twist past the detent and lift the shade. Do not glue.

---

## 6. Tee foot — spring snap (anti-creep)

| Parameter      |                                      Value |
| -------------- | -----------------------------------------: |
| Shaft / bead   |                                  Ø74 / Ø77 |
| Entry / groove |                              Ø75.6 / Ø77.4 |
| Spring slots   | **4** × 10° vertical cuts through the bead |

Print: seat on bed, **8 mm outer brim** for tall-stem stability.

---

## 7. Grass base — ballast, cover & turf

| Feature        |                                                           Value |
| -------------- | --------------------------------------------------------------: |
| Height         |                                                           18 mm |
| Footprint      |                   **120 × 120 mm rounded square** (R14 corners) |
| Ballast pocket | Square outer · Ø80 keepout · 7 mm deep · **1.5 mm cover ledge** |
| Ballast cover  |              **1.2 mm** drop-in plate (optional CA) before felt |
| Felt recess    |            **110 × 110 mm** rounded square × 1.0 mm (underside) |
| Fuzzy turf     |        Top face only — **clears snap entry** (keep R ≈ 40.8 mm) |
| Cable          |                                 Underside trench **19 mm** wide |

---

## 8. Cable path

```text
MH001 USB → Ø18 pocket-floor bore → hollow stem (Ø24 neck, 3 mm wall)
         → base well → 19 mm underside trench → inline switch clears same path
```

Feed **USB first**, then the inline button, then seat the module in the reflector.

---

## 9. Reflector cup

| Feature      | Value                                           |
| ------------ | ----------------------------------------------- |
| Material     | Ivory White Matte                               |
| Wall / floor | **0.8 mm**                                      |
| Fit          | Drops into Ø62.1 tee pocket; MH001 seats inside |

---

## 10. Slice profile summary (P2S)

| Part              | Feature        | Spec                                              |
| ----------------- | -------------- | ------------------------------------------------- |
| Ball              | Walls / infill | 4 walls, **0%** sparse                            |
| Ball              | Layer height   | 0.20 mm base + **VLH 0.08–0.10 mm apex** (Studio) |
| Ball              | Supports       | **Off** (45° self-supporting skirt)               |
| Tee               | Orientation    | Seat on bed + wide brim                           |
| Base              | Top finish     | Fuzzy paint (snap-cleared)                        |
| Cover / reflector | Infill         | 100% solid                                        |

---

## 11. Deliverables

| Path                                                                                           | Purpose                                           |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| [`production/Golf_Tee_Lamp_All_Plates_P2S.3mf`](./production/Golf_Tee_Lamp_All_Plates_P2S.3mf) | Five-plate print (Jade / Caramel / Grass / Ivory) |
| [`assembly/Golf_Tee_Lamp_Assembly.3mf`](./assembly/Golf_Tee_Lamp_Assembly.3mf)                 | Assembled preview                                 |
| [`SPEC.md`](./SPEC.md)                                                                         | This document                                     |

```bash
.venv/bin/python backend/generator/golf_tee_lamp.py --out design/golf-tee-lamp/production
.venv/bin/python backend/generator/golf_tee_lamp_assembly.py --out design/golf-tee-lamp/assembly
```

---

## 12. Assembly procedure

1. Fill ballast pocket (200–300 g); drop in ballast cover (optional CA); press in 110 mm square felt pad.
2. Snap tee into base.
3. Drop Ivory reflector into the tee cup.
4. Feed MH001 **USB plug first**, then the inline button, through the Ø18 floor bore → stem → trench; seat the module in the reflector.
5. Align ball entry slots with tee pins; drop; twist ~60° until the **detent clicks**.
6. Reverse past the detent to service the LED.

---

## 13. Physical acceptance gates

| Gate          | Pass criteria                                                              | Status   |
| ------------- | -------------------------------------------------------------------------- | -------- |
| Lit glow      | Even diffusion; no gyroid shadow; dimples soft; reflector helps brightness | Untested |
| Bayonet       | Locks with detent click; holds shade; releases without damage              | Untested |
| MH001 service | Shade off → module swap → shade on                                         | Untested |
| Cable feed    | USB + inline switch pass Ø18 bore and trench by hand                       | Untested |
| Spring snap   | Click in; holds under cable tug; no rapid creep                            | Untested |
| Ballast       | Cover seals pocket; felt flush; lamp stable                                | Untested |
| Support scar  | N/A if supports stay off; bayonet face clean                               | Untested |

---

## 14. Open questions

1. Confirm Jade White Basic vs PETG Translucent for a brighter first lit trial (still all-PLA preferred).
2. Is 0.4 mm detent enough, or deepen to 0.5–0.6 mm after first twist test?
3. Optional CA on the ballast cover vs friction-only on the ledge?
