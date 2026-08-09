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
};

export type ProductSpec = ProductSummary & { params: Param[]; groups: string[] };

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
  for (const p of spec.params) if (isVisible(p, spec, values)) out[p.id] = values[p.id];
  return out;
}
