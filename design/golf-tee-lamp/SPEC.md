# Golf Tee Lamp — Design Specification (for review)

**Status:** V2 revision after the first full physical assembly test.
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
- Cable fully internal; 21 × 12 mm keyed stem passage clears the supplied controller

---

## 2. Assembly overview

```text
        ┌─────────────────────┐
        │  Ø175 dimpled ball  │  Jade White PLA Basic · bayonet + detents
        └──────────┬──────────┘  ¼-turn lock onto Ø5 pins
                   │
        ┌──────────┴──────────┐
        │  Tee cup + LED      │  Notched reflector · side-lead chase
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
|     4 | Ballast cover   | Grass Green Matte                           | 1.2 mm tapered plug                   |
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

Dimples use dual-surface displacement so wall thickness never thins into
hotspots (`d_max` 1.4 mm, `α_max` 0.058 rad). V2 repulsion-relaxes the
equal-area centres to suppress visible Fibonacci spirals and inserts each
dimple centre plus two profile rings into the triangulation. The exported mesh
therefore reaches the configured 1.4 mm depth at every retained centre instead
of undersampling the depth between coarse sphere vertices.

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
4. **Seams / walls (dimple quality)** — already baked in; verify:
   - Seam Position = **Back** (never Random on a dimpled sphere)
   - Scarf joint seam = **Contour and Hole** (Studio 1.9+)
   - Wall Generator = **Arachne**; Wall sequence = **Inner / Outer**
   - Wipe while retracting = **ON**, wipe distance **4 mm**
5. **Fuzzy skin** — **Outer walls only** (Contour); thickness **0.04 mm**; point distance **0.08 mm**. Keeps the bayonet seat crisp and dimple edges sharp.

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

| Parameter         |                                      Value |
| ----------------- | -----------------------------------------: |
| Shaft / bead      |                          **Ø73.4 / Ø76.4** |
| Mouth / throat    |                          **Ø76.8 / Ø75.8** |
| Groove            |                                  **Ø77.4** |
| Shaft clearance   |                       **0.8 mm diametral** |
| Bead interference |             **0.30 mm/side at the throat** |
| Groove clearance  |            **0.50 mm/side when installed** |
| Spring slots      | **4** × 10° vertical cuts through the bead |

Print: **snap foot on bed**, cup and bayonet pins upward, with an **8 mm outer
brim** for tall-stem stability. The bead has a 45° lower lead-in. Both the
Ø48→Ø90 cup underside and Ø90→Ø110 seat underside flare at **45°**, so supports
stay off. Never print the tee seat-down: the three bayonet pins protrude beyond
the seat and become isolated first-layer islands.

The first Ø74/Ø77 foot would not enter the printed base by hand. The initial V2
male reduced the shaft and bead, but its base still narrowed to the Ø74.2 shaft
socket for 1.2 mm above the groove. That hidden throat demanded 1.1 mm of
radial bead compression and also failed physical insertion. The corrected
Plate 3 keeps the passage at Ø75.8 from its Ø76.8 lead-in mouth to the groove,
limiting insertion compression to the intended 0.30 mm/side. Neither earlier
base is compatible without accurately enlarging that throat.

---

## 7. Grass base — ballast, cover & turf

| Feature         |                                                                  Value |
| --------------- | ---------------------------------------------------------------------: |
| Height          |                                                                  18 mm |
| Footprint       |                          **120 × 120 mm rounded square** (R14 corners) |
| Ballast pocket  | Square outer · Ø80 keepout · 7 mm deep · **45° × 1.2 mm tapered seat** |
| Ballast cover   |     **1.2 mm tapered plug** · 111.7→109.3 mm · optional CA before felt |
| Felt recess     |                   **110 × 110 mm** rounded square × 1.0 mm (underside) |
| Fuzzy turf      |               Top face only — **clears snap entry** (keep R ≈ 40.8 mm) |
| Snap groove     |                                **45°** upper lip chamfer · 2.8 mm tall |
| Controller well |                    **21.8 × 12.8 mm** rounded rectangle through centre |
| Cable           |                         Flexible-lead underside trench **7.2 mm** wide |
| Print           |          Underside on bed · **tree supports** for pocket roof / trench |

---

## 8. Cable path

```text
MH001 side lead → 7.5 × 5.5 mm radial floor chase
                → 21 × 12 mm rounded stem passage (Ø28 neck; ~2.9 mm corner wall)
USB + 55.7 × 19.65 × 10.65 mm controller
                → straight through tee and 21.8 × 12.8 mm base well
Flexible lead   → 7.2 mm underside trench → controller remains outside base
```

The V1 Ø18 circular bore was invalid: the controller's 19.65 × 10.65 mm cross
section has a ~22.35 mm diagonal. Feed the USB and controller straight through
the tee and base before engaging the snap. Do not attempt to turn the rigid
55.7 mm controller through the side trench; that trench carries only cable.
Align the reflector notch and LED side lead with the chase before seating.

---

## 9. Reflector cup

| Feature        | Value                                           |
| -------------- | ----------------------------------------------- |
| Material       | Ivory White Matte                               |
| Wall / floor   | **0.8 mm**                                      |
| Fit            | Drops into Ø62.1 tee pocket; MH001 seats inside |
| Controller cut | **21.6 × 12.6 mm** through floor                |
| Side notch     | **8.1 mm** wide; align with tee chase           |

---

## 10. Slice profile summary (P2S)

| Part              | Feature        | Spec                                               |
| ----------------- | -------------- | -------------------------------------------------- |
| Ball              | Walls / infill | 4 walls, **0%** sparse · **Arachne** · Inner/Outer |
| Ball              | Layer height   | 0.20 mm base + **VLH 0.08–0.10 mm apex** (Studio)  |
| Ball              | Seams          | **Back** + scarf **Contour and Hole** · wipe 4 mm  |
| Ball              | Fuzzy skin     | **Outer walls only** · 0.04 mm / 0.08 mm           |
| Ball              | Supports       | **Off** (45° self-supporting skirt)                |
| Tee               | Orientation    | **Snap foot on bed** + 8 mm brim; supports off     |
| Tee               | Cup underside  | Dual **45°** self-supporting flares                |
| Base              | Orientation    | Underside on bed + **tree supports** (pocket roof) |
| Base              | Cover seat     | **45° lofted ramp** (no flat ledge cantilever)     |
| Base              | Top finish     | Fuzzy paint (snap-cleared)                         |
| Cover / reflector | Fill           | Fully solid by shells · **0% sparse infill**       |

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

1. Fill ballast pocket (200–300 g); insert the cover small-face-first until its
   large outward face settles behind the felt recess (optional CA); press in the
   110 mm square felt pad.
2. Feed the MH001 USB and controller straight through the keyed tee passage and
   base centre well. Route only the flexible lead into the underside side trench.
3. Snap the revised tee into the base.
4. Align the Ivory reflector notch with the tee chase. Seat the MH001 with its
   side lead settled into the radial chase.
5. Align ball entry slots with tee pins; drop; twist ~60° until the **detent clicks**.
6. Reverse past the detent to service the LED.

---

## 13. Physical acceptance gates

| Gate          | Pass criteria                                                              | Status                                  |
| ------------- | -------------------------------------------------------------------------- | --------------------------------------- |
| Lit glow      | Even diffusion; no gyroid shadow; dimples soft; reflector helps brightness | Untested                                |
| Bayonet       | Locks with detent click; holds shade; releases without damage              | Untested                                |
| MH001 service | Shade off → module swap → shade on                                         | Untested                                |
| Cable feed    | USB + 19.65 × 10.65 mm controller pass keyed tee/base wells by hand        | V1 failed; V2 untested                  |
| Side lead     | MH001 side lead seats without pinching in aligned tee/reflector chase      | V1 failed; V2 untested                  |
| Spring snap   | Ø73.4/Ø76.4 foot passes Ø75.8 throat, clicks and releases by hand          | Two sockets failed; correction untested |
| Ballast       | Cover seals pocket; felt flush; lamp stable                                | Untested                                |
| Support scar  | N/A if supports stay off; bayonet face clean                               | Untested                                |

---

## 14. Open questions

1. Confirm Jade White Basic vs PETG Translucent after evaluating the completed
   V1 shade. The V2 wall remains 1.6 mm because no glow failure was reported.
2. Is 0.4 mm detent enough, or deepen to 0.5–0.6 mm after the twist test?
3. Optional CA on the tapered ballast cover vs friction-only after its fit test?
