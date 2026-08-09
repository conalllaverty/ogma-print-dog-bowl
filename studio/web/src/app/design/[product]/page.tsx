"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import Controls from "@/components/Controls";
import {
  defaults,
  displayValue,
  visibleValues,
  type FieldError,
  type Filament,
  type ProductSpec,
  type Values,
} from "@/lib/spec";

export default function DesignerPage({ params }: { params: Promise<{ product: string }> }) {
  const { product } = use(params);

  const [spec, setSpec] = useState<ProductSpec | null>(null);
  const [filaments, setFilaments] = useState<Filament[]>([]);
  const [values, setValues] = useState<Values>({});
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/products/${product}`).then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      }),
      fetch("/api/v1/filaments").then((r) => r.json()),
    ])
      .then(([s, f]) => {
        setSpec(s);
        setValues(defaults(s));
        setFilaments(f.filaments ?? []);
      })
      .catch(() => setFatal("Could not load this designer."));
  }, [product]);

  // Debounced server-side validation, so a fit problem shows under the field
  // while you type rather than after a multi-minute generate.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!spec) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      fetch(`/api/v1/products/${product}/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: visibleValues(spec, values) }),
      })
        .then((r) => r.json())
        .then((d) => setErrors(d.errors ?? []))
        .catch(() => {});
    }, 350);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [spec, values, product]);

  const onChange = useCallback((id: string, v: string | number | boolean) => {
    setValues((prev) => ({ ...prev, [id]: v }));
    setDownloadUrl(null);
  }, []);

  const blocked = errors.length > 0;

  async function onGenerate() {
    if (!spec) return;
    setBusy(true);
    setStatus("queued");
    setDownloadUrl(null);
    try {
      const res = await fetch(`/api/v1/products/${product}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: visibleValues(spec, values) }),
      });
      if (res.status === 422) {
        const d = await res.json();
        setErrors(d.detail?.errors ?? []);
        setStatus(null);
        return;
      }
      const { job_id } = await res.json();
      // Poll. Generation is minutes, not seconds — see the print notes.
      for (;;) {
        await new Promise((r) => setTimeout(r, 1500));
        const j = await (await fetch(`/api/v1/jobs/${job_id}`)).json();
        setStatus(j.status);
        if (j.status === "succeeded") {
          setDownloadUrl(`/api/v1/jobs/${job_id}/download`);
          break;
        }
        if (j.status === "failed") {
          if (j.field_errors?.length) setErrors(j.field_errors);
          setStatus("failed");
          break;
        }
      }
    } catch {
      setStatus("failed");
    } finally {
      setBusy(false);
    }
  }

  const summary = useMemo(() => {
    if (!spec) return "";
    // Only summarise what is actually visible. A hidden control's value is
    // stripped from the payload by visibleValues(), so listing it here would
    // claim a setting that will not be applied.
    const shown = visibleValues(spec, values);
    return spec.params
      .filter((p) => p.id in shown)
      .map((p) => `${p.label}: ${displayValue(p, shown[p.id], filaments)}`)
      .join(" · ");
  }, [spec, values, filaments]);

  if (fatal) return <main className="wrap"><p className="err">{fatal}</p><Link href="/">← Back</Link></main>;
  if (!spec) return <main className="wrap"><p>Loading…</p></main>;

  return (
    <main className="wrap">
      <nav className="crumbs">
        <Link href="/">← All products</Link>
      </nav>
      <header className="hero">
        <h1>{spec.name}</h1>
        <p>{spec.description}</p>
        <p className="pnote">{spec.print_note}</p>
      </header>

      <Controls
        spec={spec}
        values={values}
        filaments={filaments}
        errors={errors}
        onChange={onChange}
      />

      {/* Custom panels are advertised by the spec. Unknown ids are ignored, so
          the backend can declare one before the frontend implements it. */}
      {spec.custom_panels.includes("bowl-fit") ? (
        <section className="group">
          <h2>Fit</h2>
          <p className="fhelp">
            Every style seats the same stainless bowl, so you can change style
            without re-measuring anything.
          </p>
        </section>
      ) : null}

      <section className="group">
        <h2>Make it</h2>
        <p className="fhelp">{summary}</p>
        <button className="cta" disabled={busy || blocked} onClick={onGenerate}>
          {busy ? "Generating…" : blocked ? "Fix the errors above" : "Generate .3mf"}
        </button>
        {status ? <p className="fhelp">Status: {status}</p> : null}
        {downloadUrl ? (
          <p><a className="cta" href={downloadUrl}>Download .3mf</a></p>
        ) : null}
      </section>
    </main>
  );
}
