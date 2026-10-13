# CI for Frappe apps

## GitHub Actions (v15 — change versions for v16)

```yaml
# .github/workflows/ci.yml
name: CI
on: [pull_request, push]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mariadb:
        image: mariadb:10.6
        env: { MARIADB_ROOT_PASSWORD: root }
        ports: ["3306:3306"]
        options: --health-cmd="mariadb-admin ping" --health-interval=5s --health-timeout=2s --health-retries=20
      redis-cache: { image: redis:alpine, ports: ["13000:6379"] }
      redis-queue: { image: redis:alpine, ports: ["11000:6379"] }
    steps:
      - uses: actions/checkout@v4
        with: { path: app }
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }     # v16: "3.14"
      - uses: actions/setup-node@v4
        with: { node-version: 20 }           # v16: 24
      - run: pip install frappe-bench
      - run: |
          bench init --skip-redis-config-generation --frappe-branch version-15 ~/bench
          cd ~/bench
          bench get-app --branch version-15 erpnext
          bench get-app my_app $GITHUB_WORKSPACE/app
          bench set-config -g redis_cache redis://127.0.0.1:13000
          bench set-config -g redis_queue redis://127.0.0.1:11000
          bench set-config -g redis_socketio redis://127.0.0.1:11000
          bench new-site test.localhost --db-root-password root --admin-password admin --mariadb-user-host-login-scope='%'
          bench --site test.localhost install-app erpnext my_app
          bench --site test.localhost set-config allow_tests true
      - run: cd ~/bench && bench --site test.localhost run-tests --app my_app --failfast
      - run: cd ~/bench/apps/my_app/portal && yarn install --frozen-lockfile && yarn test --run && yarn build
```

Notes:
- Flag names change between bench versions (`--db-root-password` vs `--mariadb-root-password`, `--mariadb-user-host-login-scope`). Check `bench new-site --help` for the version you install.
- Cache `~/.cache/pip` and `~/.cache/yarn` to cut CI time.
- Also run linters: `ruff check`, `ruff format --check`, `eslint`, `tsc --noEmit`.

## Pre-commit (local)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks: [{ id: ruff, args: [--fix] }, { id: ruff-format }]
```

Frappe's own apps use ruff with tabs — match the style already in your app (`pyproject.toml` `[tool.ruff]`).
