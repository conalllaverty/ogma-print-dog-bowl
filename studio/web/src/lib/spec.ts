// Types mirroring shared/ogma/designer.py. Kept deliberately thin: the web app
// renders whatever the server declares and must not grow product knowledge.

export type Visibility =
  | { type: "flag"; param: string; flag: string }
  | { type: "equals"; param: string; values: string[] };

export type Option = {
  id: string;
  name: string;
  description: string;
  available: boolean;
  flags: string[];
  /** Free-form passthrough from the spec. Known keys the UI understands:
   *  `thumb` (asset path), `font_url`, `font_weight`, `font_italic`. */
  meta?: Record<string, unknown>;
};

type Base = {
  id: string;
  label: string;
  help: string;
  group: string;
  visible_when?: Visibility;
};

export type Param =
  | (Base & { kind: "text"; default: string; min_length: number; max_length: number;
              pattern: string; transform: "none" | "upper" | "lower"; placeholder: string; strip: boolean })
  | (Base & { kind: "choice"; options: Option[]; default: string; display: "cards" | "dropdown" })
  | (Base & { kind: "filament"; default: string; role: string })
  | (Base & { kind: "boolean"; default: boolean })
  | (Base & { kind: "integer"; default: number; minimum: number; maximum: number; step: number });

export type ProductSummary = {
  id: string; name: string; tagline: string; description: string;
  available: boolean; custom_panels: string[]; print_note: string;
  has_preview: boolean;
};

export type ProductSpec = ProductSummary & {
  params: Param[];
  groups: string[];
  /** Parameters that change the preview geometry. Colour is never among them. */
  preview_keys: string[];
};

export type Filament = { id: string; name: string; hex: string; material?: string };
export type FieldError = { param: string; message: string; hint: string };

export type Values = Record<string, string | number | boolean>;

export function defaults(spec: ProductSpec): Values {
  const v: Values = {};
  for (const p of spec.params) v[p.id] = p.default;
  return v;
}

/** Whether a param should be shown, given the current values.
 *  This is the only place conditional logic lives — no product ids anywhere. */
export function isVisible(param: Param, spec: ProductSpec, values: Values): boolean {
  const w = param.visible_when;
  if (!w) return true;
  const current = values[w.param];
  if (w.type === "equals") return w.values.includes(String(current));
  // flag: look up the chosen option of the referenced param and read its flags
  const ref = spec.params.find((p) => p.id === w.param);
  if (!ref || ref.kind !== "choice") return false;
  const opt = ref.options.find((o) => o.id === String(current));
  return !!opt?.flags.includes(w.flag);
}

/** Strip values whose control is hidden, so a hidden toggle can't leak into a job. */
export function visibleValues(spec: ProductSpec, values: Values): Values {
  const out: Values = {};
  // Tolerate a not-yet-loaded spec: this runs inside render, and a `?? {}`
  // upstream once made it throw before the fetch resolved.
  for (const p of spec?.params ?? []) if (isVisible(p, spec, values)) out[p.id] = values[p.id];
  return out;
}

/**
 * How a value should read to a customer.
 *
 * The wire format is ids — "cooper", "matte-caramel", true — because that is
 * what the generator consumes. Showing those back in the order summary reads
 * like a database row: "Stand style: cooper · Stand colour: matte-caramel".
 * Choices carry their own display name, and filaments get theirs from the
 * palette, so the summary can say "Paw lattice · Caramel" instead.
 */
export function displayValue(
  param: Param,
  value: Values[string],
  filaments: Filament[] = [],
): string {
  switch (param.kind) {
    case "choice":
      return param.options.find((o) => o.id === String(value))?.name ?? String(value);
    case "filament":
      return filaments.find((f) => f.id === String(value))?.name ?? String(value);
    case "boolean":
      return value ? "Yes" : "No";
    default:
      return String(value);
  }
}

/**
 * A stable string for "what geometry would these values produce".
 *
 * Built from `preview_keys` alone, which is what lets the viewer keep showing a
 * model while the customer walks the palette: colour is not in the signature,
 * so the model never goes stale for a colour change. The server derives its
 * cache key from exactly the same fields.
 */
export function previewSignature(spec: ProductSpec, values: Values): string {
  return (spec.preview_keys ?? []).map((k) => `${k}=${String(values[k])}`).join("|");
}

/**
 * Map filament slots to the viewer's roles: `{ stand: "#AE835B", letters: "#FFF" }`.
 *
 * The link between a FilamentParam's `role` and a GLB node's `role::` prefix is
 * the contract that makes instant recolouring work. It is declared once on the
 * backend (see the FilamentParam definitions) and consumed here.
 */
export function filamentRoles(
  spec: ProductSpec | null,
  values: Values,
  filaments: Filament[],
): Record<string, string> {
  const out: Record<string, string> = {};
  if (!spec?.params) return out;
  for (const p of spec.params) {
    if (p.kind !== "filament") continue;
    const hex = filaments.find((f) => f.id === String(values[p.id]))?.hex;
    if (hex) out[p.role] = hex;
  }
  return out;
}

/**
 * Filament roles the current design leaves out — `["letters"]` with the glue-in
 * letters switched off.
 *
 * Derived from visibility rather than declared separately: a filament slot whose
 * control the spec has hidden is, by definition, a part this configuration does
 * not include. Nothing here knows *why* it is hidden, so a product that adds an
 * optional part gets the viewer behaviour for free.
 */
export function hiddenFilamentRoles(
  spec: ProductSpec | null,
  values: Values,
): string[] {
  if (!spec?.params) return [];
  const out: string[] = [];
  for (const p of spec.params) {
    if (p.kind === "filament" && !isVisible(p, spec, values)) out.push(p.role);
  }
  return out;
}

/**
 * `@font-face` rules for every option that declares a typeface.
 *
 * The alternative is bundling the fonts into the web app, which would mean two
 * copies of each face — one the browser shows, one the generator rasterises —
 * free to drift apart. Instead an option carries `meta.font_url` pointing at the
 * API, and this turns the set of them into a stylesheet.
 *
 * Returns CSS text plus a map from option id to the family name to request.
 */
export function fontFaces(spec: ProductSpec): { css: string; families: Record<string, string> } {
  const families: Record<string, string> = {};
  const rules: string[] = [];
  for (const p of spec?.params ?? []) {
    if (p.kind !== "choice") continue;
    for (const o of p.options) {
      const url = o.meta?.font_url as string | undefined;
      if (!url) continue;
      const family = `ogma-${p.id}-${o.id}`;
      families[o.id] = family;
      // No weight/style descriptors: each file is one face, and declaring a
      // weight it doesn't have invites the browser to synthesise one.
      rules.push(`@font-face{font-family:"${family}";src:url("${url}") format("truetype");font-display:swap;}`);
    }
  }
  return { css: rules.join("\n"), families };
}
