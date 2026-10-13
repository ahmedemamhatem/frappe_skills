# Build & deploy

## Build

```bash
cd apps/my_app/portal
yarn install --frozen-lockfile
yarn build      # vite build --base=/assets/my_app/portal/ && copy index.html → my_app/www/portal.html
```

Hook it into `bench build` so production builds include it — in `apps/my_app/package.json`:

```json
{ "scripts": { "build": "cd portal && yarn install --frozen-lockfile && yarn build" } }
```

`bench build --app my_app` runs the app's `build` script.

## Production checklist

- [ ] `--base=/assets/my_app/portal/` matches the folder under `public/` (blank page + 404 JS = wrong base).
- [ ] `www/portal.html` regenerated after every build (it holds the hashed asset names).
- [ ] `website_route_rules` entry exists so deep links don't 404 on refresh.
- [ ] `www/portal.py` has `no_cache = 1` (otherwise users get someone else's stale CSRF token from cache).
- [ ] Assets are hashed by Vite → safe to cache long; the HTML must not be cached.
- [ ] After deploy: `bench build --app my_app && bench --site all clear-cache && bench restart`.
- [ ] Node version in CI = server (18/20 for v15, 24 for v16).

## Common production bugs

| Bug | Fix |
|---|---|
| Blank page, console 404 for `/assets/index-xxx.js` | wrong `base`, or `bench build` didn't run the SPA build |
| Refresh on `/portal/contracts/1` → 404 | missing `website_route_rules` |
| Works in dev, CSRF error in prod | HTML cached / served without Jinja (check it's in `www/`, not `public/`) |
| Socket works in dev, not prod | nginx missing `/socket.io` block or socketio not in supervisor |
| Arabic text renders LTR | set `dir` from `boot.lang` on `<html>` |
| Big bundle (>1MB) | route-level `lazy()` imports; don't import whole icon/chart libs |
