import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 infers the workspace root from the nearest lockfile and warns when
  // it finds several. In a monorepo with a stray lockfile anywhere above, it can
  // pick the wrong one and then resolve modules from there. Pin it.
  turbopack: {
    root: path.join(__dirname),
  },

  async rewrites() {
    // The browser only ever talks to the Next server; it proxies to the API.
    // That keeps one origin, so no CORS in development and no API URL baked
    // into the client bundle.
    const api = process.env.PIPELINE_API_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${api}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
