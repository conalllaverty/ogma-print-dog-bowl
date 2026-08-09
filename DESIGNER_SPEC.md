# The common designer spec

**Status:** implemented 2026-08-09. `shared/ogma/designer.py` is the source of
truth; this document explains the reasoning.

One question drives the whole design: **what does a dog bowl designer have in
common with a lamp designer?** The answer is not "a form". It is a contract:

> A product declares **what** can be configured. The studio decides **how** to
> draw it. Neither knows about the other.

That split is why `studio/web` contains no product-specific logic, and why
adding a product to the designer is backend work.

---

## Layering

```
shared/ogma        the toolkit + the spec types. Imports nothing of ours.
products/<name>    geometry, and a designer.py declaring its spec
studio/            the API + web app. Composes products. Depends on both.
```

`shared` may not import `products` (house rule, enforced by
`tests/smoke_imports.py`). So the catalogue is assembled at the studio layer, in
`studio/api/registry.py` — the one file that knows which products exist.

The API therefore had to move out of `products/dog-bowl/app`. An API serving a
product picker cannot live inside one of the products.

---

## The parameter vocabulary

A spec is a list of parameters. Five kinds cover everything the bowl needs and,
on inspection, everything the lamp and clicker need too:

| Kind | For | Notable config |
|---|---|---|
| `text` | pet name, engraving | `min_length`, `max_length`, `pattern`, `transform`, `strip` |
| `choice` | style, font, county | `options[]`, `display: cards \| dropdown` |
| `filament` | any coloured part | `role` ("stand", "letters") |
| `boolean` | fuzzy skin, feet on/off | — |
| `integer` | flute count, LED count | `minimum`, `maximum`, `step` |

Three decisions inside that table are load-bearing:

**Filament is its own kind, not a colour.** The house rule is Bambu Matte
palette IDs only — never a free hex picker, because the shop can only print what
it stocks. Modelling it as `FilamentParam` makes that structural instead of a
convention someone forgets. The UI renders swatches from `/api/v1/filaments`,
which is shared across products and so is *not* nested under one.

**Options carry flags.** An option can advertise a capability:

```python
Option(id="cooper", name="Paw lattice", flags=("supports_fuzzy",))
```

**Visibility keys off those flags.** The fuzzy toggle only applies to styles
that paint fuzzy skin:

```python
BooleanParam(id="fuzzy_enabled", ..., visible_when=WhenFlag("style", "supports_fuzzy"))
```

Before this, `page.tsx` contained `const showFuzzy = style === "cooper"`. A new
style meant a web edit. Now a style turns its own toggle on by declaring a flag
— the same inversion the `BowlStyle` registry made on the backend. Verified in
the browser: choosing Honeycomb or Fluted removes the control; Paw lattice
restores it.

`WhenEquals(param, values)` exists for the cases a flag doesn't fit.

---

## Values, and the hidden-value trap

`visibleValues()` strips any parameter whose control is hidden before the
payload is sent. Without it, switching from Paw lattice to Honeycomb would post
`fuzzy_enabled: true` for a style that cannot paint — accepted silently, applied
never.

The same filter drives the summary line. It caught a real bug during
implementation: the summary read the raw values and cheerfully announced
"Fuzzy texture: true" on a Honeycomb, while the payload correctly omitted it.
**If a value is hidden, it must be hidden everywhere** — payload, summary, and
anything else derived from state.

The wire format is ids, because that is what the generator consumes — but ids
are not for reading. `displayValue()` resolves them through the option list and
the palette, so the summary says "Stand style: Paw lattice · Stand colour:
Caramel" rather than "cooper · matte-caramel".

`ProductSpec.coerce()` runs server-side before validation: fills defaults, drops
unknown keys, applies `transform` and `strip`, clamps integers. A product's
validator only ever sees a complete, typed dict, never raw browser input.

**Coercion normalises; it must never change what the customer asked for.** Text
is deliberately *not* truncated to `max_length`. It was, briefly, and
`POST name="WILLIAMSON"` came back `ok: true` with `name: "WILLIAMS"` — the
browser's `maxLength` hid it, but on a personalised product that ships the wrong
item. Integers are still clamped, because a slider cannot express intent outside
its own range; a text field can.

---

## Validation is field-addressed, and server-side

It runs in two layers, and the split matters.

**`ProductSpec.check_declared()`** enforces what the spec itself declares —
length, pattern, unknown or unavailable options, integer range. The UI checks
the same things as you type, but a browser is not a gate; anything can POST to
the API. Running them server-side is what makes `max_length` a rule rather than
a hint, and it means a product's `validate()` can assume the cheap constraints
already hold. There is exactly one copy of each rule.

**The product's `validate()`** then handles only what the spec cannot express.
For the bowl that is one thing: do the letters physically pack inside ±45°? It
depends on the glyphs, the font and the rail radius, so only the geometry knows.

Validation returns errors addressed to a parameter:

```json
{"ok": false, "errors": [
  {"param": "name", "message": "…", "hint": "Try the Condensed lettering, or a shorter name."}
]}
```

The designer debounces `POST /products/{id}/validate` at 350 ms and renders each
error under its own control, disabling Generate while any remain. Previously the
only way to discover a fit failure was to run a multi-minute generate and read a
stack trace.

`hint` is separate from `message` deliberately: the message says what is wrong,
the hint says what to do about it. And the hint is computed, not guessed — the
bowl measures the name in every lettering style and names one that actually
fits, or says plainly that none does.

### Answering the packing gate in 9 ms

The fit check used to be reachable only by running a full generate. It now runs
during validation, on the same keystroke debounce, because of one observation:

> A letter's angular half-extent depends only on that letter and the font.
> Packing slides letters sideways; it never changes how wide each subtends.

So `products/dog-bowl/generator/name_fit.py` memoises the expensive part
(rasterise → extrude → boolean against the core cylinder, ~0.3 s) per
`(letter, font_style)`, and the packing itself is then arithmetic. 26 letters ×
7 fonts is 182 entries, so the cache converges fast: a novel 8-letter name costs
~2 s cold and **9 ms warm** — which is every keystroke after the first.

It is not an approximation. It calls the same five functions the build calls, so
the two verdicts cannot drift; a test asserts they agree to 1e-9 across ten
cases including every font's worst case. The `NameFitError` catch at generate
time remains as a backstop for anyone posting straight to `/generate`.

A gate that only trips during generation is still caught and stored on the job
as `field_errors`, so a late failure lands under the right control rather than
becoming a 500.

---

## API

```
GET  /api/v1/products                      catalogue for the picker (no params)
GET  /api/v1/products/{id}                 full spec the designer renders from
POST /api/v1/products/{id}/validate        {values} -> {ok, values, errors[]}
POST /api/v1/products/{id}/generate        {values} -> {job_id}   422 on invalid
GET  /api/v1/jobs/{id}                     status, field_errors, output, meta
GET  /api/v1/jobs/{id}/download            the .3mf
GET  /api/v1/filaments                     shared Matte palette
```

Jobs are product-agnostic: a job is a product id, the chosen `values`, and a
status. The old routes hardcoded `name`/`font_style`/`stand`/`letters`/`fuzzy`
in the job record itself. `/api/v1/bowl/*` remains as deprecated aliases.

---

## Custom panels

Declarative rendering covers ordinary controls well and bespoke UX badly. A spec
can therefore name panels the studio may render alongside the generic form:

```python
custom_panels=("bowl-fit",)
```

The web app renders the ones it recognises and **ignores the rest**, so the
backend can declare a panel before the frontend implements it. This is where a
3D preview, a fit diagram or a live packing gauge belongs — not in the parameter
vocabulary, which should stay small.

Keep the bar high. If something can be a parameter, make it a parameter.

---

## Adding a product

1. Write `products/<name>/designer.py` exposing `SPEC = ProductSpec(...)` with a
   generator implementing `validate(values)` and `generate(values, job_dir)`.
2. Add the directory to the live list in `studio/api/registry.py`.

No web changes. A product that isn't ready sets `available=False` and appears in
the picker as "coming soon" — its spec is still declared, so wiring it later is
generator work, not UI work. The lamp and Oggie Spin are registered that way
today.

---

## What this deliberately does not do

- **No pricing.** Machine time dominates cost (see `products/dog-bowl/G1-slice-results.md`)
  and the bought-in bowl still has no supplier, so any number would be invented.
- **No 3D preview.** The old page faked one with CSS. A real GLB export from the
  generator is the honest version; `custom_panels` is where it will attach.
- **No checkout.** Out of scope until the SKUs are print-proven.
- **No client-side geometry.** House rule. The web app is a configurator.
