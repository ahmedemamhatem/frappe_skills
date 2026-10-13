# Auth & CSRF

## Same-origin SPA (default)

- Frappe login sets the `sid` cookie. Requests from `/portal` to `/api/...` on the same host carry it automatically.
- **CSRF:** Frappe requires the `X-Frappe-CSRF-Token` header on state-changing requests for cookie sessions. frappe-react-sdk reads `window.csrf_token` and sends it.
- The token must be injected by the server page, so `index.html` (→ `www/portal.html`) contains:

```html
<script>window.csrf_token = '{{ frappe.session.csrf_token }}';</script>
```

and `www/portal.py`:

```python
import frappe
no_cache = 1

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/portal"
        raise frappe.Redirect
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.boot = {"user": frappe.session.user, "lang": frappe.local.lang,
                    "sitename": frappe.local.site}
```

### Dev mode (Vite on :8080)
The Vite dev server serves `index.html` itself, so the Jinja tag is not rendered → CSRF errors on POST. Options:
1. In `site_config.json` for your **dev site only**: `"ignore_csrf": 1`.
2. Or fetch the token on startup from a dev-only endpoint (Doppio generates `get_context_for_dev`, which refuses unless `developer_mode`).

Never set `ignore_csrf` on staging/production.

### Symptoms → cause
| Symptom | Cause |
|---|---|
| `CSRFTokenError` / 400 on POST only | `window.csrf_token` missing or stale (page cached) → `no_cache = 1` on www page |
| Works logged in on Desk, 403 in SPA | Request went to a different host/port (cookie not sent) — check proxy & `siteName` |
| Logged out randomly | `sid` cookie scoped to another domain or `SameSite` issue when embedding in iframe |

## Separate frontend / mobile app (different origin)

Use **token auth**, never cookies across domains:

```tsx
<FrappeProvider
  url="https://erp.example.com"
  tokenParams={{ useToken: true, token: () => getAccessToken(), type: 'Bearer' }}
>
```

- `type: 'Bearer'` → OAuth 2 access token (register an **OAuth Client** in Frappe, use Authorization Code + PKCE for SPAs/mobile).
- `type: 'token'` → `api_key:api_secret` of a dedicated **integration user** — server-to-server only, never ship it in a browser bundle.
- Enable CORS for the frontend origin in site config: `"allow_cors": ["https://app.example.com"]`.

## Guest / public pages

- Guest endpoints need `@frappe.whitelist(allow_guest=True)` — combine with `@rate_limit` and strict input validation (see `frappe-security`).
- Never return internal fields to guests; build the response dict explicitly.

## Role-based UI

Fetch the user's roles once (`frappe.get_roles()` exposed via a small whitelisted `get_boot` method) and hide UI accordingly — **but always enforce on the server**. Hiding a button is UX, not security.
