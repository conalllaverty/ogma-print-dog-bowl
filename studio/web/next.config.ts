import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 infers the workspace root from the nearest lockfile and warns when
  // it finds several. In a monorepo with a stray lockfile anywhere above, it can
  // pick the wrong one and then resolve modules from there. Pin it.
  turbopack: {
    root: path.join(__dirname),
  },

  // ------------------------------------------------------------------------
  // `make dev` prints http://127.0.0.1:3000, and Next 16 does not trust it.
  //
  // The dev server guards `/_next/*` against cross-origin requests and its
  // default allowlist is `localhost`, not the loopback literal. Opening the
  // advertised URL therefore 403s the page's own client chunks and the HMR
  // socket, and a 403 on a chunk is silent in the UI: the server HTML still
  // paints, React never hydrates, so every `useEffect` — including the one that
  // fetches /api/v1/products — never runs. The product picker renders empty and
  // nothing on the page says why.
  //
  // Listed explicitly rather than left to the reader to discover, because
  // studio/dev.sh and the README both hand out the 127.0.0.1 form.
  // ------------------------------------------------------------------------
  allowedDevOrigins: ["127.0.0.1"],

  // The /api/v1/* proxy used to live here as a rewrite. It moved to a route
  // handler at src/app/api/v1/[...path]/route.ts, because `rewrites()` runs at
  // build time: `next build` bakes the resolved destination into
  // routes-manifest.json, so PIPELINE_API_URL in a deployed container was read
  // from the build machine's environment and silently ignored at run time.
};

export default nextConfig;
