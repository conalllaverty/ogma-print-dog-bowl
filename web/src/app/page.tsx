"use client";

import { useEffect, useMemo, useState } from "react";

type Filament = { id: string; name: string; hex: string; material?: string };
type FontStyle = { id: string; name: string; description: string };

const MAX = 8;

export default function HomePage() {
  const [filaments, setFilaments] = useState<Filament[]>([]);
  const [fontStyles, setFontStyles] = useState<FontStyle[]>([]);
  const [name, setName] = useState("MAX");
  const [fontStyle, setFontStyle] = useState("bold");
  const [standId, setStandId] = useState("matte-caramel");
  const [letterId, setLetterId] = useState("matte-ivory-white");
  const [fuzzy, setFuzzy] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/v1/filaments")
      .then((r) => r.json())
      .then((data) => {
        setFilaments(data.filaments || []);
        setFontStyles(data.font_styles || []);
      })
      .catch(() => setError("Could not load filament palette. Is the API running?"));
  }, []);

  const stand = useMemo(() => filaments.find((f) => f.id === standId), [filaments, standId]);
  const letter = useMemo(() => filaments.find((f) => f.id === letterId), [filaments, letterId]);
  const cleanName = name.toUpperCase().replace(/[^A-Z]/g, "").slice(0, MAX);

  async function onGenerate() {
    setBusy(true);
    setError(null);
    setDownloadUrl(null);
    setStatus("queued");
    try {
      const res = await fetch("/api/v1/bowl/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cleanName,
          font_style: fontStyle,
          stand_filament_id: standId,
          letter_filament_id: letterId,
          fuzzy_enabled: fuzzy,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Generate failed");
      const jobId = data.job_id as string;
      for (;;) {
        await new Promise((r) => setTimeout(r, 1200));
        const jr = await fetch(`/api/v1/bowl/jobs/${jobId}`);
        const job = await jr.json();
        setStatus(job.status);
        if (job.status === "succeeded") {
          setDownloadUrl(job.download_url);
          break;
        }
        if (job.status === "failed") {
          throw new Error(job.error || "Generation failed");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Ogma Print</p>
        <h1>Paw-lattice bowl</h1>
        <p className="lede">
          Enter a name, pick Bambu Lab Matte PLA colours, and download a print-ready P2S project.
        </p>

        <div className="preview" aria-hidden>
          <div className="cylinder" style={{ background: stand?.hex || "#AE835B" }}>
            <div className="rail">
              <span style={{ color: letter?.hex || "#fff", fontFamily: "var(--font-display)" }}>
                {cleanName || "NAME"}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <label>
          Name
          <input
            value={name}
            maxLength={MAX}
            onChange={(e) => setName(e.target.value)}
            placeholder="MAX"
            autoComplete="off"
          />
          <small>
            {cleanName.length}/{MAX} · A–Z only
          </small>
        </label>

        <fieldset>
          <legend>Letter style</legend>
          <div className="styles">
            {fontStyles.map((fs) => (
              <button
                key={fs.id}
                type="button"
                className={fontStyle === fs.id ? "chip on" : "chip"}
                onClick={() => setFontStyle(fs.id)}
              >
                <strong>{fs.name}</strong>
                <span>{fs.description}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <SwatchRow label="Stand colour" value={standId} options={filaments} onChange={setStandId} />
        <SwatchRow label="Letter colour" value={letterId} options={filaments} onChange={setLetterId} />

        <label className="check">
          <input type="checkbox" checked={fuzzy} onChange={(e) => setFuzzy(e.target.checked)} />
          Fuzzy outer wall (paws + name rail stay smooth)
        </label>

        <button type="button" className="cta" disabled={busy || cleanName.length < 2} onClick={onGenerate}>
          {busy ? "Generating…" : "Generate 3MF"}
        </button>

        {status && <p className="status">Status: {status}</p>}
        {error && <p className="error">{error}</p>}
        {downloadUrl && (
          <a className="download" href={downloadUrl}>
            Download {cleanName}_Paw_Lattice_P2S.3mf
          </a>
        )}
      </section>

      <style jsx>{`
        .page {
          min-height: 100vh;
          display: grid;
          grid-template-columns: 1.1fr 0.9fr;
          gap: 2rem;
          padding: 2.5rem clamp(1.25rem, 4vw, 4rem) 3rem;
          max-width: 1200px;
          margin: 0 auto;
        }
        @media (max-width: 900px) {
          .page {
            grid-template-columns: 1fr;
          }
        }
        .eyebrow {
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: var(--muted);
          font-size: 0.75rem;
          margin: 0 0 0.75rem;
        }
        h1 {
          font-family: var(--font-display), Georgia, serif;
          font-weight: 560;
          font-size: clamp(2.8rem, 7vw, 4.6rem);
          line-height: 0.95;
          margin: 0 0 1rem;
        }
        .lede {
          color: var(--muted);
          max-width: 34rem;
          font-size: 1.05rem;
          line-height: 1.5;
        }
        .preview {
          margin-top: 2.5rem;
          height: min(52vh, 420px);
          display: grid;
          place-items: center;
        }
        .cylinder {
          width: min(280px, 70vw);
          height: min(340px, 48vh);
          border-radius: 999px;
          position: relative;
          box-shadow:
            inset 0 0 0 1px rgba(255, 255, 255, 0.08),
            0 30px 60px rgba(0, 0, 0, 0.35);
          background-image: linear-gradient(
            90deg,
            rgba(0, 0, 0, 0.22),
            transparent 35%,
            transparent 65%,
            rgba(255, 255, 255, 0.12)
          );
        }
        .rail {
          position: absolute;
          left: 50%;
          top: 42%;
          transform: translate(-50%, -50%);
          width: 78%;
          height: 18%;
          border-radius: 10px;
          background: rgba(0, 0, 0, 0.18);
          display: grid;
          place-items: center;
          letter-spacing: 0.12em;
          font-size: clamp(1.4rem, 3vw, 2rem);
          font-weight: 700;
        }
        .panel {
          border: 1px solid var(--line);
          border-radius: 22px;
          padding: 1.5rem;
          background: rgba(255, 255, 255, 0.03);
          backdrop-filter: blur(10px);
          display: grid;
          gap: 1.1rem;
          align-content: start;
        }
        label,
        fieldset {
          display: grid;
          gap: 0.45rem;
          border: 0;
          padding: 0;
          margin: 0;
        }
        legend {
          margin-bottom: 0.35rem;
        }
        input[type="text"],
        input:not([type]) {
          width: 100%;
          border-radius: 12px;
          border: 1px solid var(--line);
          background: rgba(0, 0, 0, 0.25);
          color: var(--ink);
          padding: 0.85rem 1rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }
        small {
          color: var(--muted);
        }
        .styles {
          display: grid;
          gap: 0.5rem;
        }
        .chip {
          text-align: left;
          border-radius: 14px;
          border: 1px solid var(--line);
          background: transparent;
          color: var(--ink);
          padding: 0.75rem 0.9rem;
          display: grid;
          gap: 0.15rem;
          cursor: pointer;
        }
        .chip span {
          color: var(--muted);
          font-size: 0.85rem;
        }
        .chip.on {
          border-color: var(--accent);
          background: rgba(174, 131, 91, 0.15);
        }
        .check {
          display: flex;
          gap: 0.65rem;
          align-items: center;
        }
        .cta {
          border: 0;
          border-radius: 999px;
          padding: 0.95rem 1.2rem;
          background: var(--accent);
          color: #1a140f;
          font-weight: 700;
          cursor: pointer;
        }
        .cta:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .status {
          color: var(--muted);
          margin: 0;
        }
        .error {
          color: #ff8f8f;
          margin: 0;
          white-space: pre-wrap;
        }
        .download {
          color: var(--ink);
          font-weight: 700;
        }
      `}</style>
    </main>
  );
}

function SwatchRow({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Filament[];
  onChange: (id: string) => void;
}) {
  return (
    <fieldset>
      <legend>{label}</legend>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(42px, 1fr))",
          gap: "0.45rem",
        }}
      >
        {options.map((f) => {
          const on = f.id === value;
          return (
            <button
              key={f.id}
              type="button"
              title={f.name}
              aria-label={f.name}
              onClick={() => onChange(f.id)}
              style={{
                width: "100%",
                aspectRatio: "1",
                borderRadius: 999,
                border: on ? "2px solid #f4ece3" : "1px solid rgba(255,255,255,0.15)",
                background: f.hex,
                cursor: "pointer",
                boxShadow: on ? "0 0 0 2px #ae835b" : "none",
              }}
            />
          );
        })}
      </div>
      <small style={{ color: "var(--muted)" }}>{options.find((f) => f.id === value)?.name}</small>
    </fieldset>
  );
}
