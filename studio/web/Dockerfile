# The configurator. Build context is studio/web.
#
#     docker build -t ogma-studio-web studio/web
#
# The browser only ever talks to this server; next.config.ts rewrites
# /api/v1/* through to the API. That keeps one origin, so there is no CORS in
# the browser and no API URL baked into the client bundle.

FROM node:24-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:24-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

# PIPELINE_API_URL is read per request by the proxy route handler at
# src/app/api/v1/[...path]/route.ts, so setting it here is enough and the same
# image runs in any environment.
#
# It was a build-stage ARG before, which was the only thing that *could* work
# while the proxy was a next.config.ts rewrite — rewrites are baked into
# routes-manifest.json by `next build`. That made the image environment-specific
# and meant changing the API URL required a rebuild, with no error if you
# forgot. See the route handler for the full story.
#
# This default matches the dev fallback; the platform overrides it with the API
# service's internal URL.
ENV PIPELINE_API_URL=http://127.0.0.1:8000

# --chown on every COPY: the node:24 images ship a `node` user, but COPY lands
# files as root, so switching to USER node without this gives EACCES on
# /app/package.json before `next start` is even reached.
COPY --from=build --chown=node:node /app/.next          ./.next
COPY --from=build --chown=node:node /app/node_modules   ./node_modules
COPY --from=build --chown=node:node /app/package.json   ./package.json
COPY --from=build --chown=node:node /app/public         ./public
COPY --from=build --chown=node:node /app/next.config.ts ./next.config.ts

USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
