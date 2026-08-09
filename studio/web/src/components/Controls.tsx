"use client";

import { useMemo } from "react";
import Dropdown, { type DropdownItem } from "@/components/Dropdown";
import type { FieldError, Filament, Option, Param, ProductSpec, Values } from "@/lib/spec";
import { fontFaces, isVisible } from "@/lib/spec";

type Props = {
  spec: ProductSpec;
  values: Values;
  filaments: Filament[];
  errors: FieldError[];
  onChange: (id: string, value: string | number | boolean) => void;
};

/** Word drawn in each lettering option's own face. Short, and a plausible name. */
const FONT_SAMPLE = "Bella";

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

type ControlProps = Omit<Props, "errors"> & {
  param: Param;
  families: Record<string, string>;
};

/** One control per param kind. Adding a kind means adding a case here and in
 *  designer.py — nothing per product. */
function Control({ param, spec, values, filaments, families, onChange }: ControlProps) {
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

    case "choice": {
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
                {thumbUrl(spec, o) ? (
                  // Rendered from the real mesh, so the icon is the stand.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img className="card-thumb" src={thumbUrl(spec, o)!} alt="" loading="lazy" />
                ) : null}
                <span className="card-name">{o.name}</span>
                <span className="card-desc">{o.description}</span>
              </button>
            ))}
          </div>
        );
      }
      const items: DropdownItem[] = param.options.map((o) => ({
        id: o.id,
        label: o.name,
        description: o.description,
        disabled: !o.available,
        fontFamily: families[o.id],
        fontWeight: (o.meta?.font_weight as number) ?? undefined,
        fontItalic: Boolean(o.meta?.font_italic),
      }));
      const showsFont = items.some((i) => i.fontFamily);
      return (
        <Dropdown
          items={items}
          value={String(v ?? "")}
          ariaLabel={param.label}
          sample={showsFont ? FONT_SAMPLE : undefined}
          onChange={(id) => onChange(param.id, id)}
        />
      );
    }

    case "filament":
      return (
        <Dropdown
          items={filaments.map((f) => ({
            id: f.id,
            label: f.name,
            description: f.material ?? undefined,
            swatch: f.hex,
          }))}
          value={String(v ?? "")}
          ariaLabel={param.label}
          onChange={(id) => onChange(param.id, id)}
        />
      );

    case "boolean":
      return (
        <button
          type="button"
          role="switch"
          aria-checked={!!v}
          className={`switch${v ? " on" : ""}`}
          onClick={() => onChange(param.id, !v)}
        >
          <span className="switch-track" aria-hidden>
            <span className="switch-thumb" />
          </span>
          <span className="switch-label">{v ? "On" : "Off"}</span>
        </button>
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

function thumbUrl(spec: ProductSpec, o: Option): string | null {
  const thumb = o.meta?.thumb as string | undefined;
  return thumb ? `/api/v1/products/${spec.id}/assets/${thumb}` : null;
}

export default function Controls({ spec, values, filaments, errors, onChange }: Props) {
  // One stylesheet for the whole spec rather than a rule per render.
  const { css, families } = useMemo(() => fontFaces(spec), [spec]);

  return (
    <>
      {css ? <style dangerouslySetInnerHTML={{ __html: css }} /> : null}
      {spec.groups.map((group, gi) => {
        const params = spec.params.filter((p) => p.group === group && isVisible(p, spec, values));
        if (!params.length) return null;
        return (
          <section key={group} className="group reveal" style={{ animationDelay: `${gi * 70}ms` }}>
            <h2>{group}</h2>
            {params.map((p) => (
              <div key={p.id} className="field">
                <label className="flabel">{p.label}</label>
                {p.help ? <p className="fhelp">{p.help}</p> : null}
                <Control
                  param={p}
                  spec={spec}
                  values={values}
                  filaments={filaments}
                  families={families}
                  onChange={onChange}
                />
                <ErrorText errors={errors} id={p.id} />
              </div>
            ))}
          </section>
        );
      })}
    </>
  );
}
