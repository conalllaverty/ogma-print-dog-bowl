import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 infers the workspace root from the nearest lockfile and warns when
  // it finds several. In a monorepo with a stray lockfile anywhere above, it can
  // pick the wrong one and then resolve modules from there. Pin it.
  turbopack: {
    root: path.join(__dirname),
  },

  // The /api/v1/* proxy used to live here as a rewrite. It moved to a route
  // handler at src/app/api/v1/[...path]/route.ts, because `rewrites()` runs at
  // build time: `next build` bakes the resolved destination into
  // routes-manifest.json, so PIPELINE_API_URL in a deployed container was read
  // from the build machine's environment and silently ignored at run time.
};

export default nextConfig;
