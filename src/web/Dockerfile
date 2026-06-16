# Biggy web — Next.js (standalone output). Build from the REPO ROOT (it needs workspaces/ for
# the /api/source + /api/topology routes):
#   docker build -f src/web/Dockerfile -t biggy-web .
FROM node:24-slim AS base
ENV PNPM_HOME=/pnpm
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

FROM base AS deps
WORKDIR /app
COPY src/web/package.json src/web/pnpm-lock.yaml src/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY src/web/ ./
# Next.js standalone output ships public/ separately (copied in the run stage). This app
# carries no static assets, so guarantee the dir exists to keep that COPY valid and future-proof.
RUN mkdir -p public
# Dummy values so env validation passes at build time (no connection is made); the real
# DATABASE_URL / REDIS_URL are injected at runtime.
ENV DATABASE_URL="postgres://build:build@localhost:5432/build"
ENV REDIS_URL="redis://localhost:6379"
RUN pnpm build

FROM base AS run
WORKDIR /app
ENV NODE_ENV=production
ENV WORKSPACES_ROOT=/app/workspaces
# Bind to all interfaces, not the Docker-assigned container-id hostname — otherwise Next's
# standalone server (hostname = process.env.HOSTNAME || '0.0.0.0') listens on an interface the
# Railway proxy can't reach. PORT is injected by Railway at runtime.
ENV HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
COPY workspaces/ ./workspaces/
EXPOSE 3000
CMD ["node", "server.js"]
