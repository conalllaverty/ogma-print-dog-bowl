# The buying flow — designer UX for a shop

**Written:** 2026-08-20 · **Against:** `flush-letters-and-one-piece` @ `3f7d5c6`

What follows is the customer's journey from landing on the site to holding the
bowl, screen by screen, plus what has to change behind each screen to support it.

Every number in here is measured from this repo — slice times from
`products/dog-bowl/G1-slice-results.md`, cache and retention behaviour from
`studio/api/`, fit limits from `products/dog-bowl/generator/name_fit.py`. Where
something is a guess it says so.

---

## 0. Where this starts

The designer today is one screen: a left rail of 11 controls in three groups, a
3D viewer on the right, and a **Generate .3mf** button that hands over a zip.

It works. It is also, precisely, a free print-file generator:

| | Today |
|---|---|
| Who can use it | Anyone, no account |
| What they get | The `.3mf` plus renders, immediately, free |
| What we get | Nothing. No email, no order, no record after 7 days |
| What it costs us | ~40 s of build lock and 14.1 MB of disk per click |
| Deployed | No — images build in CI, Railway config exists, never run |

Three properties of that make it the wrong shape for a shop, and they are the
spine of everything below:

1. **The artefact is the product, and it is given away before any commitment.**
2. **Every visitor is anonymous and transient.** A design exists only in React
   state; reload and it is gone. There is nothing to put in a basket.
3. **The expensive build happens on browse, not on buy.** `/generate` and
   `/preview` share one global build lock on a single replica, so the cost of
   a curious visitor and a paying one is identical.

---

## 1. The decision that shapes every screen

**What are you selling — the file, or the object?** The UX forks hard here and
almost nothing downstream is shared at the copy level.

### Recommendation: sell the file first, the object second

Not because the object is the lesser product — because the file is the one you
can actually sell this quarter, and the software is already 80% shaped for it.

**The file (digital SKU)**

- No supplier. `G6 — source the bowl` is the single point of failure blocking
  all physical pricing, and a digital SKU routes around it entirely: the
  customer already tells us their own bowl's diameter, which is a parameter that
  only makes sense when they own the bowl.
- No shipping, no stock, no returns, no 7.5-hour throughput ceiling.
- Marginal cost ≈ 0, so demand can be tested at any price.
- Still needs `G2` (one stand of each style printed) — you cannot sell a file
  that has never printed — and a plain "this is a file, you print it" framing.

**The object (physical SKU)**

Blocked on real gates, not software ones: `G3` load test (nothing has been
proven to hold a dog's weight), `G6` bowl supply, `G7` compliance, `G8`
packaging. And the economics are unforgiving:

| Per finished stand | cooper | wave | hex |
|---|---:|---:|---:|
| Machine time | 7h30m | 7h07m | 7h55m |
| Filament | €6.24 | €7.03 | €5.32 |
| Mass | 249.65 g | 281.11 g | 212.96 g |

**One P2S produces 2–3 stands a day.** Twenty stands is ten days of continuous
printing. Personalisation is baked into the seven-hour part — the name pockets
are cut into the stand itself — so nothing can be pre-printed to stock except
colourways nobody has ordered yet. A physical SKU is made-to-order with a
two-to-three week lead time, and the price has to carry a working day of machine
time, not €6 of plastic.

**The plan below builds one flow that serves both**, with the SKU choice landing
at Step 5. Steps 1–4 are identical either way, which is what makes this
sequencing safe: nothing built for the digital launch is thrown away.

---

## 2. The journey

Seven steps. One idea per screen, the 3D preview present throughout, and nothing
asked for that we do not need.

```
  Landing → 1 Stand → 2 Name → 3 Colour → 4 Fit → 5 Review → 6 Pay → 7 After
            └────────── design ──────────────────┘   └──── commerce ──────┘
             free · anonymous · shareable             identified · paid
```

The split matters: **everything left of Review is free, anonymous and
shareable; nothing right of it exists today.**

---

### Landing — the product page

**Job:** answer "what is this and why would I want one" in one screen, then get
out of the way.

- Hero: a rendered stand, not a photograph of a printer. Use the real render
  pipeline output (`renders/assembled_hero.png`) so the picture cannot drift
  from the product.
- One line of what it is: a personalised stand that seats a stainless bowl.
- The four stands as a strip, each a link straight into Step 1 with that style
  preselected — a customer who already knows they want the honeycomb should not
  have to walk through a chooser to say so.
- Price, or a price range, above the fold. A personalisation flow with no price
  until checkout is a bounce machine.
- **Start with a name.** A single text field with the CTA — "See it with your
  dog's name on it" — that jumps to Step 2 with the name filled and a default
  stand chosen. This is the highest-converting entry point in a personalisation
  funnel and it costs one input.

**Behind it:** static page, no API calls beyond `/products` for the style strip.

---

### Step 1 — Choose the stand

**Job:** pick `style`. Four options, one decision, no wrong answers.

**On screen**

- Four cards, each with the icon rendered from the real mesh
  (`products/dog-bowl/tools/render_style_thumbs.py`, fingerprinted so a geometry
  change busts the cache), the name, and one line of what it is.
- Selecting a card advances immediately. No **Next** button on this step —
  the choice *is* the action.
- Below the fold: a short "all four seat the same bowl" reassurance, because the
  first question a customer has is whether this choice locks anything else.

**Copy per card** — lead with the look, mention the print consequence only where
it is a real trade:

| Style | Card line |
|---|---|
| Paw lattice | Paw prints pressed into the wall, name on a raised plate |
| Honeycomb | A hexagon field cut into a solid drum |
| Fluted | Vertical flutes, the name in a smooth panel |
| Split wave | A sine seam round the middle — the one you can have in two colours |

**States**

- Nothing to load, nothing to fail. The icons are committed assets served by the
  asset route; a missing one 404s to a neutral placeholder rather than an
  empty card.

**Mobile:** 2×2 grid, cards tappable at full width, no hover states relied on.

---

### Step 2 — The name

**Job:** capture `name` and `font_style`. This is the emotional centre of the
product and the step most likely to fail validation, so it gets the most care.

**On screen**

- The name field, large, autofocused, `Max` as placeholder rather than a
  pre-filled value the customer has to delete.
- **Six lettering styles as live samples of their own name** — not the word
  "Bella" in six faces, *their* name in six faces, re-rendered as they type.
  The browser already has the real font files (`/api/v1/fonts/{file}`, weight
  and italic supplied per style in `_font_meta`), so this is free and exact.
- The 3D preview updates behind, debounced.

**Validation — three layers, in this order**

1. **Client, instant:** 2–8 characters, letters only. `pattern="^[A-Za-z]+$"`.
2. **Server, live:** `POST /products/dog-bowl/validate` on every keystroke,
   debounced ~250 ms. This runs the real packing check, so its verdict cannot
   drift from what the generator would decide. Warm it answers in ~9 ms; cold,
   the first novel 8-letter name costs 2–3 s while glyphs are measured.
   The cache is warmed at boot (~95 s, background thread, both cases).
3. **Geometry, on preview:** the letters have to pack inside ±45° of rail.

**When the name will not fit** — the failure this step exists to handle. Do not
say "invalid". The API already returns a hint naming a style that *does* fit
(`name_fit.widest_fitting_font`):

> **Bartholomew** is too wide for the plate at this size.
> **Try:** Clean Sans fits it · or shorten to 8 letters

Render the suggested font as a one-tap chip that switches `font_style`. If
nothing fits, say so plainly and suggest a shorter name — do not send the
customer round a loop of styles that will all fail.

**Case.** Names are set in the case they are typed — `Chloe` prints as `Chloe`.
Say so under the field, once: *"Typed the way you want it printed."* This is
new behaviour and customers will not assume it.

**The eight-character ceiling.** It is a real geometric limit, not a whim. Show
the counter only from the sixth character, so it reads as help rather than
restriction.

**Mobile:** the font samples become a horizontal scroller of chips; the 3D
preview collapses to a thumbnail that expands on tap.

---

### Step 3 — Colour

**Job:** `stand_filament_id`, `letters_enabled`, `letter_filament_id`, and
`upper_filament_id` on the split wave.

**This step should feel instant, and it can be.** Colour is not in
`preview_keys` — the viewer applies filament colours client-side, so switching
through all 25 filaments is zero API calls and zero rebuilds. Design for that:
big swatches, immediate feedback, encourage play.

**On screen**

- **Stand colour** — 25 swatches from the real palette, grouped by family
  (neutrals, warms, greens, blues, brights) rather than listed in file order.
- **Letters** — a toggle first (`letters_enabled`), then the swatch grid.
  The toggle's two states need honest labels, because it changes what arrives:
  - *On* — "Letters print separately and glue in" (second colour, more work)
  - *Off* — "Name pressed into the stand" (one colour, nothing to glue)
- **Upper colour** — appears only on the split wave. The machinery for this
  exists: `visible_when=WhenFlag("style", "two_tone_body")`. Do not test the
  style id in the UI.

**Contrast is a real failure mode.** Caramel letters on a caramel stand is a
name you cannot read, and we shipped exactly that pairing into a test sheet
before catching it. Compute the contrast ratio between the two filament hexes
and, below about 1.6:1, show an inline note — not an error:

> These two are close in tone. The name will be hard to read.

**Mobile:** swatches at 44 px minimum, three columns, family headers sticky.

---

### Step 4 — The fit

**Job:** `bowl_diameter_mm` and `bowl_body_mm`. **The highest-risk step in the
whole flow**, and the one where the two SKUs genuinely diverge.

A customer measuring their own bowl with a kitchen ruler and getting it wrong by
3 mm produces a stand that does not fit, and they will blame the stand. The seat
enforces a 2 mm minimum engagement and rejects below that, but a bowl that
rattles is still a bad outcome inside the valid range.

**Physical SKU — do not ask this question.**

> **Your bowl is included.** A 140 mm stainless bowl, dishwasher safe, sized to
> this stand.
> *Using your own bowl instead? [Measure it →]*

Default to the supplied bowl. Put customer-supplied behind a link. This removes
the returns risk from the main path entirely and is the single strongest
argument for closing `G6` early.

**Digital SKU — this is the whole product, so teach it properly.**

- A diagram, not prose. Two dimensions on one drawing: **rim** (widest point of
  the lip) and **body** (just below the rim, the part that drops through).
  The generator already emits `cooper_bowl_dimensions.svg` — use it.
- Two number inputs with steppers, defaulting to 140 / 130.
- **Live feedback in words, not just numbers:** as the values change, say what
  will happen — *"Your bowl will sit 3.2 mm into the seat"* — and turn that red
  below the 2 mm minimum with the reason.
- **The fit gauge.** The pipeline already produces
  `OPTIONAL_bowl_fit_gauge_60deg.stl`. Offer it as a free download here: print
  the gauge, check it, then buy. That converts the riskiest step into a
  confidence-building one and costs nothing.
- "Not sure? A nominal 5.5-inch bowl measures 140 mm" as the escape hatch.

**Mobile:** the diagram is the screen; inputs sit under it.

---

### Step 5 — Review

**Job:** show exactly what they are buying, price it, and take the SKU decision.

**On screen**

- **The stand, large.** This is where the four-up view earns its place — front,
  side, top and angled together, the way the viewer already renders in `quad`
  mode. One control: solid or wireframe.
- **A specification list, in plain language.** Name and lettering style, stand,
  colours, size, what is in the box.
- **The two SKUs as a choice, not a hidden default:**

| | **The stand, made and sent** | **The files, to print yourself** |
|---|---|---|
| What arrives | The printed stand, assembled, plus the bowl | A Bambu project file and photos |
| When | 2–3 weeks — each stand is a 7½-hour print | Immediately |
| Price | *(see §3)* | *(see §3)* |
| You need | Nothing | A printer, PLA in two colours, glue |

- **Lead time stated before payment, not after.** Made-to-order at 7½ hours a
  unit cannot pretend to be next-day, and a customer told up front is not a
  customer complaining on day four.
- **Save / share.** "Send this to someone" and "email me this design" — both
  need Step 5's design record and both are cheap conversion insurance.

---

### Step 6 — Checkout

**Job:** take money with the least surface area we can get away with.

**Recommendation: Stripe Checkout, hosted.** Not an embedded card form. It keeps
card data entirely out of this codebase, gets Apple/Google Pay for free, handles
3DS, and handles EU VAT via Stripe Tax. The cost is a redirect and less control
of the visual — worth it at this stage by a wide margin.

- **Guest checkout by default.** No account creation before purchase. An
  account, if it ever exists, is a magic link sent afterwards.
- Digital SKU: email only. No address, no shipping.
- Physical SKU: email, shipping address, delivery country. Nothing else — no
  phone number, no marketing checkbox pre-ticked.
- **The design must survive the round trip.** The customer leaves the site to
  pay; the design record (§4) is what they come back to.

---

### Step 7 — After the purchase

The step most personalisation shops neglect, and the one that produces repeat
custom.

**Digital**

- Download on the confirmation screen *and* by email link. The link must
  outlive the current 7-day job retention — see §4.
- Include the assembly note and the filament recommendations. What they bought
  is a file; what they need is a result.

**Physical**

- Confirmation email with the render of *their* stand, not a stock photo. We
  generate four renders per job already.
- **Three progress emails, no more:** order received · printing started ·
  shipped with tracking. On a two-week lead time, silence reads as a scam.
- A photo of the actual assembled stand before it ships would be exceptional and
  costs one phone snap. Consider it for the first fifty orders.

---

## 3. Pricing — the method, not a number

The floor is knowable from this repo; the price is a business decision.

**Direct cost, physical, per stand**

| | |
|---|---:|
| Filament (measured) | €5.32–7.03 |
| Machine time 7.5 h @ €0.22/h amortised (P2S ~€650 over ~3,000 h) | ~€1.65 |
| Electricity ~0.15 kW × 7.5 h | ~€0.35 |
| The bowl | **unknown — `G6`** |
| Packaging | unknown — `G8` |
| Labour: assembly, gluing letters, packing (~20 min) | unknown |
| **Known subtotal** | **~€8 + bowl + packaging + labour** |

**The number that actually sets the price is throughput.** At 2–3 stands per
printer per day, a printer running flat out for a month makes ~75 stands. Decide
what one printer-month must earn, divide, and that is the floor — not the €8.

**Digital** has no cost floor at all, so it is priced on value and on what it
does to the physical SKU. Price it too low and it cannibalises; too high and it
does not test demand. A common shape is digital at roughly a fifth of physical.

**Do not price on filament.** The measured data shows mass and time are
*anti*-correlated — the honeycomb is the lightest stand and the slowest. Price
on material and you systematically underprice the one that occupies the printer
longest.

---

## 4. What has to change behind the screens

Five structural changes. Everything else is UI.

### 4.1 A design must become a durable object

Today a design is React state. A basket, a shared link, a payment redirect, an
abandoned-design email and an operator reprint all need the same thing: a design
that exists on the server, immutably, with an id.

```
POST /designs           → { id, values, geometry_version, created_at }
GET  /designs/{id}      → the record
GET  /d/{id}            → the designer, rehydrated
```

Immutable: editing a saved design creates a new record. Cheap: a row, not a
build — the meshes are not touched until someone pays. Stamp
`geometry_version` (already computed, `_geometry_fingerprint()`) so a design
bought today can be rebuilt identically in six months, and so we can tell when
it *cannot*.

### 4.2 The artefact must move behind the payment

`GET /jobs/{id}/download` currently serves the `.3mf` to anyone holding a job
id. For a shop:

- Remove anonymous generate and download from the public API.
- Generate **on payment confirmation**, from the design record, in a worker.
- Digital: serve through a signed, expiring URL tied to the order.
- Physical: the customer never sees the file at all. It goes to the operator.

This also fixes the cost asymmetry — the 40-second build now happens once per
*order* rather than once per curious click.

### 4.3 The build lock has to stop being global

`/preview` and `/generate` share one lock on a single replica because the
generator carries state in module globals. Under shop traffic, previews queue
behind order builds and the site feels broken.

**The fix is already proven in this repo:** `tests/goldens.py` runs each case in
a fresh subprocess precisely because module globals do not survive one. Move
generation into a subprocess pool and the constraint disappears — previews get
their own workers, orders get theirs, and the API stops serialising everybody
behind one mutex.

### 4.4 Orders need a database, and designs need to outlive the reaper

Today everything is files on a volume with a 7-day retention sweep
(`job_retention_hours: 168`) and an LRU preview cache. That is correct for a
cache and catastrophic for an order: a design bought on the 1st and printed on
the 12th would have been reaped.

- **Postgres** for designs, orders, and fulfilment state. Small, relational,
  needs backups.
- **Volume or object storage** for artefacts, with retention *per order status*
  rather than a flat age: previews stay a cache; an order's `.3mf` lives until
  it ships plus a warranty window.
- Back up the database. There is nothing to back up today because there is
  nothing worth backing up today; that changes the moment money is involved.

### 4.5 There has to be somewhere for orders to go

An operator console, however plain: order list with status, the design's
renders, a one-click `.3mf` download, and buttons to move an order through
*paid → printing → assembled → shipped*, each emitting the customer email. Put
it behind real authentication — this is the one part of the system that must not
be anonymous.

Manufacturing options belong here too, not in the customer flow.
`one_piece` and `fuzzy_enabled` are process decisions, not preferences: the
three-part build is the proven one, and fuzzy skin is a surface treatment we
should be choosing, not asking about. Hide both from the customer, keep them in
the operator view for reprints and experiments. That takes the customer form
from 11 controls to 9, across seven calm steps instead of one long one.

---

## 5. The build, in order

Ordered by dependency and by risk retired per day. Each phase ends with
something shippable.

### Phase 0 — Retire what is unknown (days, mostly not code)

Nothing below is worth building on an unverified base.

1. **Open a generated `.3mf` in Bambu Studio.** Twenty minutes, and the largest
   unverified risk in the stack. `tests/audit_3mf.py` passes 14/14 against a P2S
   profile, which is not the same as the slicer accepting the file.
2. **Deploy the thing.** The images build in CI and the Railway config exists;
   it has never run. A shop cannot be planned against an unproven deploy.
3. **`G2` — print one stand of each style.** ~3 print days. You cannot sell a
   file that has never printed, in either SKU.
4. **Decide the SKU question** in §1, and whether `G6` starts now.

### Phase 1 — Designs become real (~3 days)

Design records, permalinks, rehydration, `geometry_version` stamping. No UI
change yet. Everything after this depends on it.

### Phase 2 — The stepped designer (~1 week)

The seven steps. Progressive disclosure via the existing `visible_when`.
Manufacturing controls removed from the customer path. Mobile layout — currently
the viewer assumes a desktop stage.

**Ship this before commerce.** It is a better designer whether or not anything
is ever sold, and it is the thing customers judge.

### Phase 3 — Subprocess isolation (~3 days)

Lift the global build lock. Do it before traffic, not after — it is a
refactor under calm conditions now and an incident later.

### Phase 4 — Money (~1 week)

Stripe Checkout, webhooks, order records, the SKU choice at Review, signed
download URLs, order confirmation email. **Digital SKU can launch at the end of
this phase.**

### Phase 5 — Fulfilment (~1 week)

Operator console, order states, the three progress emails, shipping and
tracking. Physical SKU launches here — gated on `G3`, `G6`, `G7`, `G8`, which
are print-and-supply-chain work running in parallel with all of the above.

### Phase 6 — Operations (ongoing)

Backups, error reporting, an uptime check, abandoned-design email, and a real
look at the rate limits (`20 generate/hr`, `120 preview/hr` keyed on
`x-forwarded-for`, which is only trustworthy behind our own proxy).

---

## 6. Decisions needed before Phase 1

1. **Digital, physical, or both?** Everything in §1. My recommendation: build
   the one flow, launch digital at Phase 4, physical at Phase 5.
2. **Does `G6` (bowl supply) start now?** It blocks all physical pricing and it
   is the difference between "measure your bowl" and "your bowl is included" —
   which is the difference between a returns-prone step and a reassuring one.
3. **Price points**, or at least the printer-month target that implies them.
4. **Who fulfils?** One person with one printer at 2–3 stands a day is a hard
   ceiling. It sets the launch volume, and therefore how loudly to launch.
5. **Where does it live?** Railway for both services, custom domain, and whether
   the shop is public or invite-only for the first cohort.

---

## 7. What I would not build

- **Customer accounts.** Guest checkout and a magic link cover everything a
  personalisation shop needs. Accounts are a support surface with no return here.
- **A basket.** One stand is one order. Multi-item baskets can wait for a second
  product.
- **Live pricing per configuration.** Every style costs within €1.71 and 48
  minutes of every other. One price per SKU is honest and far simpler.
- **A style/colour recommender.** Four styles and 25 colours is a browsable
  space, not one that needs an algorithm.
- **Rendering previews server-side per colour.** Colour is client-side already
  and instant. Do not undo that.
