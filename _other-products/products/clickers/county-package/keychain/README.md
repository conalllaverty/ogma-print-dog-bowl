# County clicker keychain concept

Current artifact:

- [`tyrone-keychain-concept.svg`](./tyrone-keychain-concept.svg)

This phase is intentionally 2D only. Do not build production CAD until the
switch and click feel are physically selected.

## Proposed series format

- Every county body uses a **46 mm longest dimension**.
- The reinforced lug sits outside that envelope, making total length roughly
  55–58 mm depending on placement.
- Mainland county polygons only; offshore islands are omitted.
- Keychain-specific simplification removes necks below approximately 1.8 mm.
- Lug belongs to the fixed shell and never moves.
- Two internal guides prevent top rotation and edge binding.
- Two GAA colours: fixed shell plus contrasting moving top.

## Recommended switch

**Kailh GM 8.0 mouse microswitch**

- Published envelope: 12.8 × 5.8 × 6.5 mm
- Typical operating force: approximately 60–65 gf
- Published pre-travel: approximately 0.3 mm
- High mechanical cycle rating

Why it is the preferred starting point:

- Its narrow 5.8 mm axis fits small and elongated counties much more easily
  than a 13.8 mm square keyboard switch.
- It provides a crisp mechanical click.
- It allows all county bodies to remain near one common keychain size.

Tradeoffs:

- Movement is much shorter than an MX or Choc keyboard switch.
- The moving top needs a centre actuator plus separate guide/retention features.
- A printed clip or captive pocket must hold the switch body; electrical
  soldering is unnecessary for a mechanical-only fidget.

## Alternatives

### Kailh Choc V1

- 13.8 × 13.8 mm plate cutout
- Approximately 3.0 mm full travel
- Better keyboard-like motion
- Only slightly smaller in footprint than the existing MX mechanism
- Likely requires a 52–55 mm county body

### 6 × 6 mm tactile switch

- Smallest and easiest to fit
- Low cost
- Very short travel and weaker fidget feel

## Concept dimensions

- County body longest dimension: 46 mm
- Approximate total length including lug: 57 mm
- Target total thickness: 10.5 mm
- Keyring lug outer diameter: 9 mm
- Keyring hole: 4.2 mm
- Minimum lug bridge: 3 mm
- Fixed shell rim: 1.2 mm
- Moving-top side clearance: 0.7 mm
- Moving top above rim: approximately 1.2 mm
- Target press movement: 0.3–0.6 mm

All dimensions remain provisional until an actual switch is measured.

## Next gate

1. Buy one or more GM 8.0 switches.
2. Confirm the click force and short travel are satisfying for a keychain.
3. Measure the exact body, actuator, pins and operating position.
4. Build a mechanism-only 3D fit coupon.
5. Only then create the Tyrone shell/top CAD.

If the GM 8.0 movement feels too shallow, switch to Choc V1 before investing
in the all-county geometry.

## Switch references

- Kailh GM 8.0 product information:
  https://www.kailhswitch.com/info/the-feature-of-kailh-gm-8-0-micro-switch-47272142.html
- Kailh Choc drawing:
  https://www.kailhswitch.com/Content/upload/pdf/201915927/CPG135001D01_-_Red_Linear_Choc.pdf
