"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { ProductSummary } from "@/lib/spec";

export default function PickerPage() {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/products")
      .then((r) => r.json())
      .then((d) => setProducts(d.products ?? []))
      .catch(() => setError("Could not reach the designer API. Is it running?"));
  }, []);

  return (
    <main className="wrap">
      <header className="hero">
        <h1>What are we making?</h1>
        <p>Pick a product to design. Everything prints on a Bambu P2S in Matte PLA.</p>
      </header>

      {error ? <p className="err">{error}</p> : null}

      <div className="picker">
        {products.map((p) =>
          p.available ? (
            <Link key={p.id} href={`/design/${p.id}`} className="ptile">
              <span className="ptitle">{p.name}</span>
              <span className="ptag">{p.tagline}</span>
              <span className="pdesc">{p.description}</span>
              <span className="pnote">{p.print_note}</span>
              <span className="pcta">Design one →</span>
            </Link>
          ) : (
            <div key={p.id} className="ptile soon" aria-disabled>
              <span className="ptitle">{p.name}</span>
              <span className="ptag">{p.tagline}</span>
              <span className="pdesc">{p.description}</span>
              <span className="pnote">{p.print_note}</span>
              <span className="pcta muted">Coming soon</span>
            </div>
          )
        )}
      </div>
    </main>
  );
}
