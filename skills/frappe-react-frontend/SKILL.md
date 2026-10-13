---
name: frappe-react-frontend
description: Build React (Vite + TypeScript) frontends that live inside a Frappe/ERPNext custom app — scaffolding with Doppio, auth and CSRF, data fetching with frappe-react-sdk, realtime updates, file uploads, routing, build and deploy. Use whenever creating or changing a React SPA, portal or dashboard served by Frappe, wiring React to whitelisted methods or DocTypes, or debugging CSRF/403/session/socket issues between React and Frappe. Covers Frappe v15 and v16.
---

# React on Frappe

> **TL;DR:** Ship the React app *inside* your Frappe app (served at `/<spa>` from the same origin), use **frappe-react-sdk** for data, let Frappe's session cookie + `window.csrf_token` handle auth, and keep business logic on the server in whitelisted methods — React only renders and calls.

## Decision: which setup?

| Situation | Choose |
|---|---|
| Portal/dashboard for logged-in Frappe users (staff, tenants, customers) | **Same-origin SPA** inside the app (this skill's default) |
| Public marketing site, SEO matters | Frappe Website / Web Pages / Builder, not a SPA |
| Separate mobile app or third-party frontend on another domain | Token auth (API key/secret or OAuth bearer) + CORS — see `references/auth-and-csrf.md` |
| Small UI tweak on a Desk form | Client Script, not React |
| Rich custom screen *inside Desk* | Desk Page (`frappe.ui.form`, or a React bundle mounted in a Page) |

Default data layer: **frappe-react-sdk** (SWR-based, made for Frappe). Use TanStack Query only if the team already standardises on it — the pattern is in `references/data-fetching.md`.

## Scaffold (recommended: Doppio)

```bash
cd ~/frappe-bench
bench get-app https://github.com/NagariaHussain/doppio
bench add-spa --app my_app --typescript --tailwindcss   # answer prompts: name=portal, framework=React
cd apps/my_app/portal && yarn dev                       # http://<site>:8080
```

What Doppio sets up (know this so you can fix it by hand):
- `apps/my_app/portal/` — Vite project, `proxyOptions.ts` proxies `/app|api|assets|files|private` to the bench webserver port (with websockets).
- `vite.config` → `build.outDir = ../my_app/public/portal`, build script `vite build --base=/assets/my_app/portal/ && yarn copy-html-entry` (copies `index.html` to `my_app/www/portal.html`).
- `my_app/www/portal.py` — page context that injects the CSRF token (`frappe.sessions.get_csrf_token()`) and boot data, `no_cache = 1`.
- `hooks.py` → `website_route_rules = [{"from_route": "/portal/<path:app_path>", "to_route": "portal"}]` so deep links like `/portal/contracts/123` serve the SPA.

## Project layout

```
my_app/portal/src/
├── main.tsx            # FrappeProvider + Router
├── api/                # one file per backend module: typed wrappers around hooks
│   └── contracts.ts
├── types/              # generated/handwritten DocType interfaces
├── features/<feature>/ # pages + components for one feature
├── components/ui/      # shared UI primitives
└── lib/                # utils, formatters (dates, currency)
```

Rules:
- **Never call `fetch('/api/...')` from components.** Go through `src/api/*` so URLs, params and types live in one place.
- **Type every DocType you touch** (`types/Contract.ts`). Generate them rather than hand-write when possible (Frappe Types / `frappe-types` app writes TS interfaces on DocType save).
- Keep **filters, permissions and totals on the server**. React must not compute anything the backend must also trust.

## Provider

```tsx
// main.tsx
import { FrappeProvider } from 'frappe-react-sdk'

const socketPort = import.meta.env.VITE_SOCKET_PORT   // dev only, e.g. "9000"
const siteName = window.frappe?.boot?.sitename ?? import.meta.env.VITE_SITE_NAME

<FrappeProvider socketPort={socketPort} siteName={siteName} enableSocket>
  <RouterProvider router={router} />
</FrappeProvider>
```

`FrappeProvider` props (frappe-react-sdk 1.x): `url`, `tokenParams`, `socketPort`, `siteName`, `enableSocket`, `swrConfig`, `customHeaders`. On the same origin you normally pass **no `url` and no `tokenParams`** — the session cookie does the work.

## Core hooks (frappe-react-sdk 1.x)

| Need | Hook |
|---|---|
| Current user, login, logout | `useFrappeAuth()` → `currentUser, login, logout, isLoading` |
| One doc | `useFrappeGetDoc<T>(doctype, name)` |
| List of docs | `useFrappeGetDocList<T>(doctype, { fields, filters, orderBy, limit, limit_start })` |
| Count | `useFrappeGetDocCount(doctype, filters)` |
| Call whitelisted GET | `useFrappeGetCall<T>(method, params, swrKey?, options?)` → `data.message` |
| Call whitelisted POST (mutation) | `const { call, loading, error, result } = useFrappePostCall<T>(method)` |
| Create / update / delete doc | `useFrappeCreateDoc`, `useFrappeUpdateDoc`, `useFrappeDeleteDoc` |
| Upload file | `useFrappeFileUpload()` |
| Link-field search | `useSearch(doctype, text, filters?, limit?, debounce?)` |
| Realtime | `useFrappeEventListener(event, cb)`, `useFrappeDocTypeEventListener(doctype, cb)`, `useFrappeDocumentEventListener(doctype, name, cb)` |

Full patterns, typed wrappers and pagination: `references/data-fetching.md`.

## Non-negotiables

1. **Mutations go through POST whitelisted methods** (`@frappe.whitelist(methods=["POST"])`) — never GET for writes.
2. **Always show server errors.** Frappe returns `exc_type` + `_server_messages`; parse them once in a helper (`references/data-fetching.md#errors`) and show a toast — never swallow.
3. **Don't fetch whole docs for lists.** Pass `fields: [...]` explicitly; default list fetch returns only `name`.
4. **Paginate** every list (`limit` + `limit_start`, or `useSWRInfinite`-style) — no `limit: 0` on growing tables.
5. **Realtime = invalidate, don't patch.** On a socket event call `mutate()`; let the server be the source of truth.
6. **Dates/currency:** format with the user's settings from boot (`frappe.boot.sysdefaults` / `user` time zone) — never assume browser locale = system settings. RTL (Arabic) via `dir="rtl"` on `<html>` from `frappe.boot.lang`.
7. **Build output is generated.** Add `my_app/public/portal/` and `my_app/www/portal.html` to `.gitignore` *or* commit them deliberately — pick one per team, and make CI match (see `frappe-devops`).

## v15 vs v16

| | v15 | v16 |
|---|---|---|
| Node for bench / build | 18 or 20 | 24 |
| Python | 3.10+ | 3.14 |
| Socket.IO | node `socketio.js` on `socketio_port` (default 9000) | same model; make sure Redis + workers start before socketio in supervisor |

React code itself is the same on both; the differences are toolchain versions in CI and production.

## References

- `references/data-fetching.md` — typed API layer, mutations, errors, pagination, optimistic UI, TanStack alternative
- `references/auth-and-csrf.md` — session vs token auth, CSRF, guest pages, CORS for separate domains
- `references/realtime-and-files.md` — `frappe.publish_realtime` → React, file uploads, private files
- `references/build-and-deploy.md` — build, cache-busting, nginx, common production bugs

## Anti-patterns

| ❌ | ✅ |
|---|---|
| `fetch('/api/resource/...')` sprinkled in components | typed wrappers in `src/api/` |
| Storing API key/secret in the React bundle | session cookie (same origin) or OAuth for external apps |
| Computing invoice totals / access rights in React | compute in a whitelisted method, React displays |
| `frappe.client.get_list` with `limit_page_length: 0` | server-side pagination |
| Polling every 5s for changes | `publish_realtime` + `useFrappeEventListener` → `mutate()` |
| Calling `frappe.get_all` in a whitelisted method for user-facing data | `frappe.get_list` (applies permissions) |
| Separate Node/Express backend "because React" | whitelisted methods are your backend |
