"use client";

import type { FieldError, Filament, Param, ProductSpec, Values } from "@/lib/spec";
import { isVisible } from "@/lib/spec";

type Props = {
  spec: ProductSpec;
  values: Values;
  filaments: Filament[];
  errors: FieldError[];
  onChange: (id: string, value: string | number | boolean) => void;
};

function ErrorText({ errors, id }: { errors: FieldError[]; id: string }) {
  const e = errors.find((x) => x.param === id);
  if (!e) return null;
  return (
    <p className="err">
      {e.message}
      {e.hint ? <span className="hint"> {e.hint}</span> : null}
    </p>
  );
}

/** One control per param kind. Adding a kind means adding a case here and in
 *  designer.py — nothing per product. */
function Control({ param, values, filaments, onChange }: Omit<Props, "spec" | "errors"> & { param: Param }) {
  const v = values[param.id];

  switch (param.kind) {
    case "text":
      return (
        <input
          className="text-input"
          value={String(v ?? "")}
          maxLength={param.max_length}
          placeholder={param.placeholder}
          onChange={(e) => {
            let s = e.target.value;
            if (param.transform === "upper") s = s.toUpperCase();
            if (param.transform === "lower") s = s.toLowerCase();
            onChange(param.id, s);
          }}
        />
      );

    case "choice":
      if (param.display === "cards") {
        return (
          <div className="cards">
            {param.options.map((o) => (
              <button
                key={o.id}
                type="button"
                disabled={!o.available}
                className={`card ${String(v) === o.id ? "sel" : ""}`}
                onClick={() => onChange(param.id, o.id)}
              >
                <span className="card-name">{o.name}</span>
                <span className="card-desc">{o.description}</span>
              </button>
            ))}
          </div>
        );
      }
      return (
        <select className="select" value={String(v ?? "")} onChange={(e) => onChange(param.id, e.target.value)}>
          {param.options.map((o) => (
            <option key={o.id} value={o.id} disabled={!o.available}>
              {o.name} — {o.description}
            </option>
          ))}
        </select>
      );

    case "filament":
      return (
        <div className="swatches">
          {filaments.map((f) => (
            <button
              key={f.id}
              type="button"
              title={`${f.name}${f.material ? ` · ${f.material}` : ""}`}
              aria-label={f.name}
              className={`swatch ${String(v) === f.id ? "sel" : ""}`}
              style={{ background: f.hex }}
              onClick={() => onChange(param.id, f.id)}
            />
          ))}
        </div>
      );

    case "boolean":
      return (
        <label className="toggle">
          <input type="checkbox" checked={!!v} onChange={(e) => onChange(param.id, e.target.checked)} />
          <span>{v ? "On" : "Off"}</span>
        </label>
      );

    case "integer":
      return (
        <div className="rangewrap">
          <input
            type="range"
            min={param.minimum}
            max={param.maximum}
            step={param.step}
            value={Number(v ?? param.default)}
            onChange={(e) => onChange(param.id, Number(e.target.value))}
          />
          <span className="rangeval">{String(v)}</span>
        </div>
      );
  }
}

export default function Controls({ spec, values, filaments, errors, onChange }: Props) {
  return (
    <>
      {spec.groups.map((group) => {
        const params = spec.params.filter((p) => p.group === group && isVisible(p, spec, values));
        if (!params.length) return null;
        return (
          <section key={group} className="group">
            <h2>{group}</h2>
            {params.map((p) => (
              <div key={p.id} className="field">
                <label className="flabel">{p.label}</label>
                {p.help ? <p className="fhelp">{p.help}</p> : null}
                <Control param={p} values={values} filaments={filaments} onChange={onChange} />
                <ErrorText errors={errors} id={p.id} />
              </div>
            ))}
          </section>
        );
      })}
    </>
  );
}
