/**
 * Runtime proxy to the studio API.
 *
 * The browser only ever talks to this server, which forwards `/api/v1/*` on to
 * the API. One origin means no CORS in the browser and no API URL in the client
 * bundle — that part was always the intent.
 *
 * This used to be a `rewrites()` entry in next.config.ts, and that is why it
 * moved: **`rewrites()` is evaluated at build time, not per request.** The
 * destination is baked into `.next/routes-manifest.json` by `next build`, so a
 * production container reading `PIPELINE_API_URL` from its environment had no
 * effect at all — it proxied to whatever URL was present on the build machine.
 * In a container that default resolves to the container itself, and every API
 * call 500s with ECONNREFUSED 127.0.0.1:8000.
 *
 * A route handler reads the variable on each request, so one image runs in any
 * environment and changing the API URL is a restart rather than a rebuild.
 */

import { NextRequest } from "next/server";

// Never prerender or cache: this is a proxy, and the API's own cache headers
// are forwarded through untouched.
export const dynamic = "force-dynamic";

/** Same default next.config.ts used, kept for `make dev`. */
const API = process.env.PIPELINE_API_URL || "http://127.0.0.1:8000";

/**
 * Headers that describe *this* hop and must not be replayed on the next one.
 * `host` in particular: sending the browser's Host to the API breaks routing on
 * any platform that vhosts, and `content-length` goes stale once the body has
 * been buffered.
 */
const STRIP_REQUEST = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "accept-encoding",
]);

const STRIP_RESPONSE = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
]);

async function proxy(request: NextRequest, path: string[]) {
  const search = request.nextUrl.search;
  const url = `${API}/api/v1/${path.map(encodeURIComponent).join("/")}${search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!STRIP_REQUEST.has(key.toLowerCase())) headers.set(key, value);
  });

  // Buffer rather than stream the request: every body this API takes is a small
  // JSON `values` object, and streaming one would need `duplex: "half"` plus the
  // matching support at both ends for no benefit.
  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    // The API being down is a 502, not a 500: this server is fine, the one
    // behind it is not, and saying so makes the difference obvious in logs.
    return Response.json(
      { detail: `Cannot reach the studio API at ${API}` },
      { status: 502 },
    );
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!STRIP_RESPONSE.has(key.toLowerCase())) out.set(key, value);
  });

  // The body streams straight through, untouched — preview GLBs run to a couple
  // of megabytes and a generated .3mf to more, and `content-disposition` on the
  // download route is what names the file the customer saves.
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: out,
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function POST(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function HEAD(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
