# Biggy

A monorepo-style workspace for the Biggy project.

## Layout

```
biggy/
├─ docs/          # Project documentation
└─ src/
   ├─ web/        # Next.js admin dashboard (frontend) — see src/web/README.md
   └─ lib/        # AI services (planned — not yet added)
```

| Package | Status | Description |
|---|---|---|
| [`src/web`](src/web) | ✅ active | Admin dashboard — Next.js 16, React 19, Tailwind v4, shadcn/ui |
| `src/lib` | 🚧 planned | The AI side of the project |

## Quick start

The frontend is the only package today. From the repository root:

```bash
pnpm -C src/web install
pnpm -C src/web dev        # http://localhost:3000
```

…or work inside the package directly:

```bash
cd src/web
pnpm install
pnpm dev
```

See [`src/web/README.md`](src/web/README.md) for the full frontend guide.

## Conventions

- **Package manager:** [pnpm](https://pnpm.io).
- **Each package under `src/` is self-contained** (its own `package.json`, dependencies, and config). When `src/lib` is added, a root pnpm workspace can be introduced to share tooling across packages.
