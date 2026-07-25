# Squspi ball reconstruction

The supplied Squspi files are tessellated STL/3MF exports. They do not contain
editable STEP, Fusion, or SolidWorks bodies, so the design is being rebuilt from
four measured master meshes:

- 1 link, printed 6 times
- 1 mushroom button, printed twice
- 1 six-arm base, printed twice
- 1 curved panel, printed 13 times

Two R188 bearings complete the rotating centre. Nominal R188 dimensions are
6.35 mm bore, 12.70 mm outside diameter, and 4.7625 mm width.

## Reconstruction sequence

1. Clean, centre, and measure the four source masters.
2. Print bearing-fit, running-clearance, and link-root coupons.
3. Freeze the proven R188 and movement interfaces.
4. Replace each reference mesh with a parameter-driven model.
5. Verify each replacement against its reference envelope and interfaces.
6. Branch the verified baseline into a V2 with gap shields, stronger links, and
   support-light parts.
7. Package the accepted model in a genuine Bambu Lab P2S 3MF.

Do not change the spin mechanism while reconstructing the baseline. The current
prototype reportedly spins well, so geometry changes must be isolated and
measured rather than bundled together.

## Generate stage-one outputs

```bash
.venv/bin/python backend/generator/squspi_ball_reconstruction.py \
  --source-dir "/path/to/Squspi+ball_stls" \
  --out /tmp/squspi-reconstruction
```

Outputs:

```text
reference_masters/
  base_reference.stl
  button_reference.stl
  link_reference.stl
  panel_reference.stl
parametric_candidates/
  button_baseline.stl
  base_baseline.stl
  link_baseline.stl
  panel_shell_core.stl
  panel_baseline.stl
coupons/
  r188_fit_matrix.stl
  link_root_matrix.stl
  running_clearance_0_40_{female,male}.stl
  running_clearance_0_50_{female,male}.stl
  running_clearance_0_60_{female,male}.stl
reconstruction_report.json
```

The R188 matrix tests 12.55/12.65/12.75 mm housings and
6.20/6.30/6.40 mm shafts. Select fits by physical print rather than nominal CAD
alone. The clearance pairs test 0.40/0.50/0.60 mm per-side movement.

Printable Bambu Lab P2S Matte PLA projects are written to `p2s_projects/`:

```text
Squspi_R188_Fit_Coupon_P2S.3mf
Squspi_Running_Clearance_Coupons_P2S.3mf
Squspi_Link_Root_Coupon_P2S.3mf
```

Profile: Bambu Lab P2S 0.4 nozzle, Bambu PLA Matte @BBL P2S, 0.20 mm layers,
4 walls, no support.

## Current accuracy (sampled surface comparison)

| Part        | Volume delta | Candidate→source p95 | Candidate→source max | Status                                            |
| ----------- | ------------ | -------------------- | -------------------- | ------------------------------------------------- |
| Button      | −0.34%       | 0.013 mm             | 0.017 mm             | Accepted baseline                                 |
| Link        | −2.7%        | ~1.0 mm              | ~1.4 mm              | Functional candidate; pin blend still approximate |
| Base        | −5.1%        | ~0.5 mm              | ~1.1 mm              | Functional candidate; arm tips simplified         |
| Panel shell | −4.8%        | ~1.2 mm              | ~2.6 mm              | Core accepted; raised outer lip deferred          |
| Panel full  | −5.8%        | ~1.2 mm              | ~2.6 mm              | Rails + Ø2.20 sockets present                     |

## Source findings

- Cleaned master envelopes:
  - link: 9.403 × 7.502 × 7.743 mm
  - button: 25.515 × 25.515 × 7.889 mm
  - base: 33.377 × 35.882 × 7.500 mm
  - panel: 15.989 × 23.343 × 19.350 mm
- Button shaft/seat geometry is consistent with an R188 bore stack.
- Base bore is a stepped R188 pocket with a retaining shoulder.
- Panel body is a concentric spherical shell: outer R25.00, inner R21.00,
  centre near `(18.16, 0, −0.25)` after centering.
- Panel sockets are Ø2.20 on rails at `Y = ±4.00`.
- The panel source contains a tiny zero-volume two-triangle sliver. Stage one
  removes it while preserving the positive-volume body.
- The supplied `(9).3mf` is byte-identical to `(8).3mf` and still embeds a
  Bambu Lab P1P 0.4 mm profile.

## Acceptance gates

The baseline reconstruction is accepted only when:

- R188 bearings seat without deforming or axially clamping either race.
- Spin coast time remains at least 90% of the current prototype.
- Full opening and closing travel is collision-free.
- Reconstructed interfaces agree with the cleaned source within 0.10 mm unless
  a coupon result deliberately changes the fit.
- Every exported mesh is watertight and positive-volume.

## Immediate next work

1. Print coupons and record chosen R188 / clearance fits.
2. Refine base arm-tip loft and link pin blend.
3. Bake the panel outer lip into the shell surface (not as a later boolean).
4. Only then branch into V2 safety/durability changes.
