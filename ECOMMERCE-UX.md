# The buying flow — dog bowl designer in Ogma Print Core

**Written:** 2026-08-20 · **Revised:** 2026-08-20 after reading `ogma-print-core` @ `12f61cc` (`dev`)
**Bowl repo:** `flush-letters-and-one-piece` @ `9d7eba0`

The customer's journey from landing on the site to holding the bowl, screen by
screen, and what has to be built behind it.

**This is the second draft.** The first assumed we were building a shop. We are
not — `ogma-print-core` already is one, and most of what the first draft
proposed to build already exists there and works. Three corrections, all of
which make the job smaller:

| First draft said | Actually |
|---|---|
| "Don't build a basket — one stand, one order" | Core has a cart. Multiple bowls per order is a solved problem, not a feature to design |
| A **Fit** step where the customer measures their bowl | **We supply the bowl.** The step is deleted from the customer flow and becomes an admin override on the order |
| Sell the file first, the object second | Superseded. Supplying the bowl answers `G6`, and core is built for physical fulfilment — shipping, addresses, tracking, plate batching |

Numbers below are measured: slice times from `products/dog-bowl/G1-slice-results.md`,
cache and lock behaviour from `studio/api/`, packing limits from `name_fit.py`,
and the core findings from its Prisma schema and `src/lib`. Where something is a
guess it says so. The map designer is out of scope throughout — dog bowls only.

---

## 1. What already exists in core

Verified by reading the schema and the key libraries, not assumed. This is the
list of things **not to build**:

| Concern | Where it lives | State |
|---|---|---|
| Accounts, sessions, password reset | `User`, `Session`, `AnonymousSession` | Done |
| Anonymous → registered conversion | `AnonymousSession.convertedUser` | Done |
| Addresses | `Address` | Done |
| Designs, saved and shareable | `Design` (+ `wizardConfig` JSONB) | Done, map-shaped |
| Cart | `store.ts` `CartItem[]`, `ogma-cart-v1` in localStorage | Done |
| Multi-item checkout | `/api/stripe/cart-checkout`, `Order.cartGroupId` + `cartPosition` | Done |
| Payment + webhook | `/api/stripe/webhook`, `stripePaymentIntentId` | Done |
| Orders, status history, tracking | `Order`, `OrderStatusHistory` | Done |
| Admin: orders, customers, stats | `/admin`, `/api/admin/*` | Done |
| **Per-piece production tracking** | `PrintJob` | Done |
| **Plate batching across orders** | `PlateBatch` + `POST /api/v1/admin/plates/assemble` | Done |
| Filament availability + per-product allow-lists | `FilamentAvailability`, `FilamentAllowlist`, `filament_slots.json` | Done |
| Legal pages | `/terms`, `/privacy`, `/refunds`, `/shipping`, `/faq` | Done |
| Backend build API | `POST /api/v1/designer/generate`, discriminated on `method` | Done |

**The two projects are more compatible than they look.**

- **The filament palettes are identical.** All 25 ids in
  `shared/ogma/palette.json` exist in core's `filament_palette.json` with the
  same hex values, byte for byte. Core has nine more (galaxy and glow
  specials). Nothing to reconcile, and the bowl gains nine colours for free.
- **Both speak the same backend contract.** The bowl studio's web app and core's
  storefront both proxy to a FastAPI service via `PIPELINE_API_URL`.
- **Both already model "a product with configurable parameters".** The bowl has
  `ProductRegistry` / `ProductSpec` / `designer.py`; core has `filament_slots.json`
  keyed by `(productType, slot)` and a `method`-discriminated build endpoint.
  These are the same idea in two dialects.

### The one place the fit is genuinely awkward

`Design` is map-shaped, and four of its columns are **non-nullable floats**:
`bboxMinLon`, `bboxMinLat`, `bboxMaxLon`, `bboxMaxLat`, plus a required
`locationName` and `stylePreset`. A dog bowl has no bounding box. Options, in
preference order:

1. **Make the bbox columns nullable and add `productType`** to `Design`. One
   migration, no data loss, and `wizardConfig` JSONB already exists to hold the
   bowl's 9 parameters. `sourceType` and `pieceCount` show the table has already
   absorbed one non-map product shape (constellations), so this is the second
   time, not the first.
2. A separate `BowlDesign` table. Cleaner conceptually, but `Order.designId` is
   a hard FK to `Design`, so this means either a polymorphic order or a second
   order path. Not worth it for one product.

**Recommendation: option 1.** One migration, and the bowl becomes
`productType: "dog-bowl"` alongside the existing map types.

---

## 2. The customer journey

**Five steps, not seven.** Fit is gone (we supply the bowl); checkout and
account come from core and are not redesigned here.

```
  Shop → 1 Stand → 2 Name → 3 Colour → 4 Review → [cart] → core checkout → core account
         └──────────── the designer ───────────┘           └──── already exists ────┘
```

Everything left of the cart is new work. Everything right of it exists.

---

### Entry — the shop page

**Job:** answer "what is this" and get out of the way.

- Hero: a render of an actual stand from the pipeline
  (`renders/assembled_hero.png`), not a photo of a printer.
- The four stands as a strip, each linking straight into Step 1 with that style
  preselected. Someone who already wants the honeycomb should not walk through a
  chooser to say so.
- **Price above the fold.** A personalisation flow that hides the price until
  checkout is a bounce machine.
- **Start with a name.** One text field — *"See it with your dog's name on it"* —
  jumping to Step 2 with the name filled and a default stand chosen. Highest-
  converting entry into a personalisation funnel, and it costs one input.

---

### Step 1 — Choose the stand

**Job:** pick `style`. Four options, one decision, no wrong answers.

- Four cards, icons rendered from the real meshes by
  `products/dog-bowl/tools/render_style_thumbs.py` and fingerprinted, so a
  geometry change busts the cache and a stale icon is visibly stale.
- Selecting a card advances. No **Next** on this step — the choice is the action.
- One reassurance line: every style takes the same bowl, so this choice locks
  nothing else.

| Style | Card line |
|---|---|
| Paw lattice | Paw prints pressed into the wall, name on a raised plate |
| Honeycomb | A hexagon field cut into a solid drum |
| Fluted | Vertical flutes, the name in a smooth panel |
| Split wave | A sine seam round the middle — the one you can have in two colours |

**Mobile:** 2×2 grid, full-width tap targets, nothing depending on hover.

---

### Step 2 — The name

**Job:** `name` and `font_style`. The emotional centre of the product, and the
step most likely to fail validation, so it gets the most care.

- Name field, large, autofocused, `Max` as *placeholder* rather than a value the
  customer must delete first.
- **Six lettering styles, each rendering their own name** — not a specimen word
  in six faces, *their* name in six faces, updating as they type. The browser
  already gets the real font files from the API with the correct weight and
  italic per style, so this is exact and free.
- The 3D preview updates behind, debounced.

**Validation, three layers:**

1. **Client, instant** — 2–8 characters, letters only, `^[A-Za-z]+$`.
2. **Server, live** — the real packing check, debounced ~250 ms. ~9 ms warm;
   a novel 8-letter name costs 2–3 s cold while glyphs are measured. Its verdict
   cannot drift from the generator's, because it calls the same functions.
3. **Geometry** — letters must pack inside ±45° of rail.

**When a name will not fit**, do not say "invalid". The API already returns a
font that *does* fit:

> **Bartholomew** is too wide for the plate at this size.
> **Try:** Clean Sans fits it · or shorten to 8 letters

Render the suggestion as a one-tap chip that switches `font_style`. If nothing
fits, say so and ask for a shorter name — never send someone round a loop of
styles that will all fail.

**Case.** Names print in the case they are typed — `Chloe` prints as `Chloe`.
Say so once, under the field: *"Typed the way you want it printed."* This is new
behaviour and nobody will assume it.

**The 8-character ceiling** is geometric, not arbitrary. Show the counter from
the sixth character so it reads as help, not restriction.

**Mobile:** font samples become a horizontal chip scroller; the 3D preview
collapses to a thumbnail that expands on tap.

---

### Step 3 — Colour

**Job:** `stand_filament_id`, `letters_enabled`, `letter_filament_id`, and
`upper_filament_id` on the split wave.

**This step should feel instant, and it genuinely can be.** Colour is not in
`preview_keys` — the viewer applies filament colours client-side, so walking the
whole palette is zero API calls and zero rebuilds. Design for play: big swatches,
immediate feedback.

- **Stand colour** — swatches grouped by family (neutrals, warms, greens, blues,
  brights) rather than file order.
- **Letters** — a toggle first, then swatches. Label the two states by what
  arrives, not by the flag name:
  - *On* — "Letters print separately and glue in" (second colour)
  - *Off* — "Name pressed into the stand" (one colour, nothing to glue)
- **Upper colour** — split wave only. The machinery exists:
  `visible_when=WhenFlag("style", "two_tone_body")`. The UI must never test a
  style id.

**Which colours appear is core's decision, not the bowl's.** Core has
`FilamentAvailability` and per-`(productType, slot)` `FilamentAllowlist`, curated
in the admin UI. The bowl should read the allow-list for `dog-bowl/stand`,
`dog-bowl/letters` and `dog-bowl/upper` rather than shipping its own list — that
is how a filament that has run out disappears from the storefront without a
deploy.

**Contrast is a real failure mode.** Caramel letters on a caramel stand is a name
you cannot read — we shipped exactly that pairing into a test sheet last week
before catching it. Compute the contrast ratio between the two hexes and below
about 1.6:1 show an inline note, not an error:

> These two are close in tone. The name will be hard to read.

**Mobile:** 44 px minimum swatches, three columns, sticky family headers.

---

### Step 4 — Review

**Job:** show exactly what they are buying, then cart or checkout.

- **The stand, large.** This is where the four-up view earns its keep — front,
  side, top and angled, as the viewer already renders in `quad` mode.
- **A plain-language spec list:** name and lettering, stand style, colours,
  and what is in the box — *including the bowl*, which is the thing that
  justifies the price and must not be buried.
- **Lead time, before payment not after.** Each stand is a ~7½-hour print made
  to order. A customer told up front is not a customer complaining on day four.
- **Two buttons, not one:** *Add another bowl* and *Checkout*. See §3.
- **Save / share** — "send this to someone", "email me this design". Both are
  free given core's `Design` records, and both are cheap conversion insurance.

---

### Steps 5–7 — Cart, checkout, account

**Not redesigned. These are core's, and they work.** Two things worth flagging
because they affect the bowl's copy:

1. **Core requires an account to order.** `Order.userId` is non-nullable, while
   `Design.userId` is nullable with an `AnonymousSession` fallback. So the real
   flow is *design anonymously → register or log in at checkout → design
   converts to the account*. That is a legitimate model and the conversion path
   already exists — but it is **not** guest checkout, and the first draft of this
   document wrongly assumed it would be. If guest checkout is wanted, that is a
   change to core, not to the bowl.
2. **The designer is currently admin-gated.** Three recent commits on `dev` lock
   it behind login and admin (`b81871a`, `48f5480`, `8387905`). Whatever gating
   the bowl designer launches under should be a deliberate decision, not
   inherited by accident.

---

## 3. Ordering more than one bowl

**Already solved, and worth understanding before designing anything.** Core's
pattern is:

- A `CartItem` is a frozen snapshot of the wizard config, held in the client
  store and persisted to `localStorage` under `ogma-cart-v1`.
- At checkout, `/api/stripe/cart-checkout` creates **one `Order` per item**, all
  sharing a `cartGroupId`, with `cartPosition` preserving order.
- The Stripe webhook fans payment-complete out across every `Order` in the group.
- Admin groups by `cartGroupId` and fulfils the group as a bundle.

**What this means for the bowl UX**

- Two dogs, two names, two colourways is the *normal* case for this product, not
  an edge case. A household with two dogs is the most likely multi-buy in the
  catalogue.
- Step 4's **Add another bowl** should return to Step 1 with *colours and style
  carried over and the name cleared* — the second bowl is usually the matching
  one with a different name. That single default is the difference between a
  pleasant second purchase and re-doing the whole wizard.
- The cart line for each bowl must show the **name and a colour swatch pair**,
  not "Dog bowl ×2". Two personalised items that look identical in a cart is a
  support ticket.
- Bundle pricing already has a home: `FormatSize.additionalPriceCents` is the
  existing "each additional" mechanism, and the cart maths is
  `priceCents + additionalPriceCents × (qty − 1)`. A second bowl shipping in the
  same parcel genuinely costs less to fulfil, so the discount is honest.

---

## 4. The bowl fit — an admin concern now

We supply the bowl, so **the customer is never asked to measure anything.** The
two parameters do not disappear; they move.

- `bowl_diameter_mm` (140) and `bowl_body_mm` (130) become **defaults on the
  product**, not questions in the wizard.
- The admin order view gets a **Bowl fit** panel — the two numbers, editable,
  with the seat-engagement readout the generator already computes. Changing them
  regenerates that order's `.3mf`.
- **Why keep them editable at all:** a supplier substitution mid-run is exactly
  the scenario that breaks a made-to-order product silently. If batch two of the
  stainless bowls measures 138 mm, an operator needs to change one number and
  reprint — not wait for a deploy. The generator already validates a 2 mm
  minimum seat engagement and refuses below it, so the guard rail is in place.
- A customer-supplied-bowl SKU can come back later as an explicit variant. It is
  a different product with different support characteristics, and mixing it into
  the main path is what the first draft got wrong.

The wizard drops from 11 controls to **7**, across four calm steps:
`name`, `style`, `font_style`, `stand_filament_id`, `letters_enabled`,
`letter_filament_id`, `upper_filament_id`.

`one_piece` and `fuzzy_enabled` are **process decisions, not preferences** —
the three-part build is the proven one, and fuzzy skin is a finish we should be
choosing. Both belong in the admin order view beside the bowl fit, for reprints
and experiments.

---

## 5. Production — the part core already does better than we planned

The first draft proposed building a fulfilment queue. Core has one, and it is
more capable than what was proposed. It also **changes the economics**.

`PrintJob` tracks a **piece**, not an order: `pieceIndex`, `pieceLabel`,
`pieceKind`, `assetPath`, `requiredFilaments`, `bedFootprintMm`, and a status of
`pending | batched | printing | printed | failed`. `PlateBatch` then combines
pieces **from different orders** onto one Bambu plate via lib3mf assembly, with
bin-packing and AMS palette-overflow detection.

**The dog bowl is a natural fit, because it is already a multi-piece product.**
Cooper is four plates: base, paw panel, top seat ring, letters. Each becomes a
`PrintJob` piece, and the plate builder can then do the thing that fixes
throughput:

| Piece | Time | Batching opportunity |
|---|---|---|
| Paw panel | 4h36m | Same colour across orders |
| Base | 1h28m | Same colour across orders |
| Top seat ring | 1h09m | Same colour across orders |
| **Letters** | **10m24s, 0.91 g** | **Many customers' names on one plate** |

The first draft said "one P2S makes 2–3 stands a day and nothing can be
pre-printed". The first half is still true. The second half is **wrong** — the
pieces are separable and colour-shareable, and core can already pack them. Three
customers who all chose a charcoal honeycomb share base and ring plates; their
letters share a single 10-minute plate. That is a real throughput multiplier on
the exact product being sold, and it is already built.

**What this needs from the bowl side:** the pipeline must emit per-piece
metadata — bed footprint and required filaments per mesh — so the packer can do
its job. Today it emits the meshes and a dimensions JSON. Adding a sidecar is
small work with a large payoff.

---

## 6. Pricing

The floor is knowable; the price is a business decision.

| Per stand | |
|---|---:|
| Filament (measured) | €5.32–7.03 |
| Machine time 7.5 h @ ~€0.22/h amortised | ~€1.65 |
| Electricity ~0.15 kW × 7.5 h | ~€0.35 |
| The bowl | supplier-dependent |
| Packaging, labour (~20 min assembly and gluing) | not yet measured |

**Throughput sets the price, not materials.** At 2–3 stands per printer per day
a printer-month is ~75 stands; decide what a printer-month must earn and divide.
Plate batching (§5) is the lever that moves this number, and it is the strongest
argument for wiring the bowl into `PrintJob` properly rather than treating each
order as an opaque `.3mf`.

**Do not price on filament.** The measured data has mass and time
*anti*-correlated — the honeycomb is the lightest stand and the slowest. Price on
material and you systematically underprice the one that occupies the printer
longest.

Core's `constants-v2.ts` already models sizes, modes, price deltas and bundle
discounts. A dog bowl is one entry with one price and an `additionalPriceCents`
for the second bowl.

---

## 7. The work, in order

Each phase ends with something shippable. Phase 0 is not optional.

### Phase 0 — Retire what is unknown (days, mostly not code)

1. **Open a generated `.3mf` in Bambu Studio.** Twenty minutes, and the largest
   unverified risk in the bowl stack. `tests/audit_3mf.py` passes 14/14 against a
   P2S profile, which is not the same as the slicer accepting the file.
2. **`G2` — print one stand of each style.** ~3 print days.
3. **`G3` — load test.** Nothing has been proven to hold a dog's weight. This is
   a liability gate on a product a dog eats from, and no amount of storefront
   work substitutes for it.
4. **Audit core properly.** This document is written from its schema and key
   libraries. Before committing to the integration, read its designer wizard and
   checkout end to end — the estimates below assume the patterns hold.

### Phase 1 — Make the bowl a product core can hold (~1 week)

- `Design.productType`, bbox columns nullable, one migration.
- `dog-bowl` entries in `filament_slots.json` for `stand`, `letters`, `upper` —
  both copies, since CI checks them in lockstep.
- `method: "dog-bowl"` added to the backend's discriminated union, so the bowl
  builds through the same `generate` / `result` / `preview.glb` / `download.3mf`
  endpoints as everything else.
- **Decision point:** does the bowl generator move into core's `backend/`, or
  stay a separate FastAPI service that core proxies to? See §8.

### Phase 2 — The designer, four steps (~1–1.5 weeks)

The wizard above. Progressive disclosure via the existing `visible_when`.
Manufacturing controls removed from the customer path. The viewer ported —
currently it assumes a desktop stage and will need a mobile layout.

**Ship this before commerce.** It is a better designer whether or not anything
is ever sold, and it is what customers judge.

### Phase 3 — Cart and checkout (~3 days)

Mostly wiring, because the cart exists: a bowl `CartItem` shape, the cart line
rendering name and swatches, *Add another bowl* carrying style and colours
forward, and a bowl price entry with `additionalPriceCents`.

### Phase 4 — Admin and production (~1 week)

- Bowl fit panel on the order (§4), plus `one_piece` / `fuzzy_enabled`.
- Per-piece sidecar from the pipeline: bed footprint and required filaments.
- `PrintJob` rows per bowl piece; verify the plate builder packs them.
- Reprint-one-piece, which is the common real failure — a letter comes out badly
  far more often than a whole stand does.

### Phase 5 — Launch (gated on Phase 0)

Lead-time copy, the three fulfilment emails core already sends, and a decision on
whether the first cohort is invite-only.

### Not on the critical path, but do it before real traffic

**Lift the global build lock.** `/preview` and `/generate` share one mutex on a
single replica because the generator keeps state in module globals, so previews
queue behind order builds. The fix is already proven in-repo: `tests/goldens.py`
runs each case in a subprocess precisely because module globals do not survive
one. A calm refactor now; an incident later.

---

## 8. Decisions needed

1. **Where does the bowl generator live?** In core's `backend/` as another
   `method`, or as a separate service core proxies to. Separate keeps this
   repo's test harness, goldens and CI intact and is far less disruptive;
   merging gives one deployable and one place for shared concerns like the
   filament palette. **Recommendation: separate service first**, merge later if
   the seam turns out to be noisy — the palettes already agree byte for byte,
   which is the thing that would have forced a merge.
2. **Guest checkout, or accounts?** Core requires a user on `Order` today (§2).
   Requiring registration to buy a €X personalised gift costs conversions;
   changing it is core-side work.
3. **Bowl supplier and unit cost** — the last unknown in the price floor.
4. **Who fulfils, and at what volume?** One printer at 2–3 stands a day is the
   ceiling, before batching. It sets how loudly to launch.
5. **Does the bowl designer launch public, or admin-gated** like the map designer
   currently is?

---

## 9. What I would not build

- **Guest checkout, unless it is cheap.** Core has a real anonymous-session →
  account conversion path. Use it before rebuilding checkout.
- **A second admin.** Core's admin is better than what the first draft proposed.
  Add panels to it; do not start another.
- **A bowl-specific filament list.** Read core's allow-lists. The palettes are
  already identical, so the only thing a separate list can do is drift.
- **Live pricing per configuration.** Every style costs within €1.71 and 48
  minutes of every other. One price is honest and much simpler.
- **A customer-supplied-bowl path in the main flow.** A later variant, if ever.
  Mixing it in is what made the first draft's Fit step a returns risk.
