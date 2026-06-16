# Biggy — Web

The frontend for Biggy: an admin dashboard built with **Next.js** (App Router) and **shadcn/ui**.

## Tech stack

| | |
|---|---|
| Framework | [Next.js 16](https://nextjs.org) (App Router, Turbopack) |
| UI library | React 19 |
| Styling | [Tailwind CSS v4](https://tailwindcss.com) |
| Components | [shadcn/ui](https://ui.shadcn.com) — `base-nova` style, built on [Base UI](https://base-ui.com) |
| Icons | [lucide-react](https://lucide.dev) |
| Language | TypeScript |
| Package manager | [pnpm](https://pnpm.io) |

## Getting started

Prerequisites: Node.js 20+ and pnpm 9+.

```bash
# from this directory (src/web)
pnpm install
pnpm dev          # http://localhost:3000
```

Or from the repository root, target this package with `-C`:

```bash
pnpm -C src/web install
pnpm -C src/web dev
```

## Scripts

| Command | Description |
|---|---|
| `pnpm dev` | Start the dev server (Turbopack) |
| `pnpm build` | Production build |
| `pnpm start` | Serve the production build |
| `pnpm lint` | Run ESLint |

## Project structure

```
src/web/
├─ app/                     # App Router
│  ├─ layout.tsx            # Root layout: providers + sidebar/header shell
│  ├─ page.tsx             # Dashboard (stat cards + recent orders)
│  ├─ globals.css          # Tailwind v4 + shadcn theme tokens
│  └─ <section>/page.tsx   # orders, products, customers, analytics, settings
├─ components/
│  ├─ app-sidebar.tsx       # Sidebar navigation + user menu
│  ├─ site-header.tsx       # Top bar + dynamic breadcrumb
│  ├─ page-placeholder.tsx  # Shared empty-state for section pages
│  └─ ui/                   # shadcn/ui primitives
├─ hooks/                   # use-mobile, …
├─ lib/                     # utils (cn), …
└─ public/                  # static assets
```

## Routes

| Route | Page |
|---|---|
| `/` | Dashboard — stat cards + recent orders table |
| `/orders` | Orders (placeholder) |
| `/products` | Products (placeholder) |
| `/customers` | Customers (placeholder) |
| `/analytics` | Analytics (placeholder) |
| `/settings` | Settings (placeholder) |

The sidebar highlights the active route via `usePathname`, and the header breadcrumb is derived from the current path.

## Working with components

Add more shadcn/ui components with:

```bash
pnpm dlx shadcn@latest add <component>   # e.g. dialog, chart, input
```

> **Note — this is the `base-nova` style (Base UI), not Radix.** Polymorphism uses the
> **`render` prop**, not `asChild`. For example, to render a nav button as a link:
>
> ```tsx
> <SidebarMenuButton render={<Link href="/orders" />}>…</SidebarMenuButton>
> ```

The `@/*` import alias maps to this package root (`src/web/*`), e.g. `@/components/ui/button`.

## Deployment

This app lives in a subdirectory. When deploying (e.g. to Vercel), set the project's
**Root Directory** to `src/web`.
