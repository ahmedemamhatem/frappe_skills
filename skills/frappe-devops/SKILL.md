---
name: frappe-devops
description: Day-to-day bench operations and production deployment for Frappe/ERPNext v15 and v16 — dev environment setup, git branching for custom apps, safe deploy/migrate procedure, upgrading v15 → v16, production setup (nginx, supervisor/systemd, workers, Redis, socketio), Docker, backups and restore, monitoring, and troubleshooting common bench errors. Use when setting up environments, deploying, upgrading, running bench commands on servers, or debugging migrate/build/worker/socketio failures.
---

# Frappe DevOps

> **TL;DR:** Develop on a dev site with `developer_mode`, ship through git (never edit code on prod), deploy with **backup → pull → migrate → build → restart**, keep staging identical to prod, and test restores — a backup you haven't restored is not a backup.

## Versions

| | v15 | v16 |
|---|---|---|
| Python | 3.10+ (3.11 common) | **3.14** |
| Node | 18 / 20 | **24** |
| Branches | `version-15` | `version-16` |
| Notes | stable, most third-party apps support it | check every third-party app has a `version-16` branch before upgrading |

Pin branches explicitly: `bench init --frappe-branch version-15 ...`, `bench get-app --branch version-15 erpnext`.

## Dev environment

```bash
bench init --frappe-branch version-15 frappe-bench && cd frappe-bench
bench get-app --branch version-15 erpnext
bench get-app git@github.com:yourco/my_app.git
bench new-site dev.localhost --admin-password admin
bench --site dev.localhost install-app erpnext my_app
bench --site dev.localhost set-config developer_mode 1
bench use dev.localhost
bench start
```

Useful: `bench --site dev.localhost console`, `bench --site dev.localhost mariadb`, `bench --site dev.localhost clear-cache`, `bench watch` (rebuild Desk assets on change), `bench --site dev.localhost browse --user Administrator`.

## Git workflow for custom apps

- `main` = production, `develop` = staging, feature branches → PR → review (`frappe-code-review`) → CI green (`frappe-testing`) → merge.
- Branch per Frappe version if you support both: `version-15`, `version-16` (mirrors Frappe's convention).
- Tag releases (`v1.4.0`) and keep a CHANGELOG; prod deploys a tag, not a moving branch.
- Commit DocType JSON, fixtures, patches with the code that needs them — in one PR.

## Deploy procedure (production)

```bash
cd /home/frappe/frappe-bench
bench --site erp.example.com backup --with-files          # 1. backup
bench --site erp.example.com set-maintenance-mode on      # 2. (optional) maintenance
cd apps/my_app && git fetch --tags && git checkout v1.4.0 && cd ../..   # 3. code
bench setup requirements                                  # 4. python/node deps if changed
bench --site erp.example.com migrate                      # 5. patches + schema + fixtures
bench build --app my_app                                  # 6. assets (+ React SPA)
bench restart                                             # 7. web + workers
bench --site erp.example.com set-maintenance-mode off
```

- If `migrate` fails: read the traceback, fix forward in a new release, or restore the backup. Don't hand-edit the DB to "get past" a patch.
- Run the same procedure on **staging first** with a recent prod backup restored.
- `bench update` pulls **all** apps — on prod prefer per-app checkout + migrate so you control what changes.

## Production setup (bare metal / VM)

```bash
sudo bench setup production frappe          # nginx + supervisor configs, as user "frappe"
bench setup nginx && sudo service nginx reload
sudo bench setup lets-encrypt erp.example.com
```

Processes you need running: `web` (gunicorn), `schedule`, `worker` for each queue (short/default/long), `socketio`, Redis (cache + queue). Scale background workers by adding worker processes per queue in the supervisor config (custom queues/timeouts go in `common_site_config.json` → `"workers": {"long": {"timeout": 3600}}`), and gunicorn workers via `bench config set-common-config -c gunicorn_workers 8` (~2×CPU+1), then `bench setup supervisor` + reload. **Start order:** Redis → workers → socketio (v16 upgrades report socketio failing if Redis isn't up).

App server + separate DB server: point `db_host` in `site_config.json` to the DB server, restrict MariaDB to the app server IP, and use `--mariadb-user-host-login-scope` (or `%`) when creating sites.

## Docker

Use the official **frappe_docker** project: build a custom image with your apps (`apps.json`), run with compose (backend, frontend/nginx, websocket, queue-short/long, scheduler, redis, mariadb). Upgrades = new image tag + `bench --site all migrate` in a one-off container.

## Backups & restore

```bash
bench --site erp.example.com backup --with-files --compress
bench --site new.example.com restore /path/db.sql.gz --with-public-files pub.tar --with-private-files priv.tar
```

- Schedule off-site copies: Frappe's built-in **S3 Backup Settings** (any S3-compatible storage), or cron + rclone to your own storage.
- Back up `sites/<site>/site_config.json` (contains `encryption_key` — without it Password fields can't be decrypted).
- **Restore test monthly** onto staging.

## Upgrading v15 → v16

1. Inventory apps; confirm each has a `version-16` branch (some community apps lag).
2. On a **copy** of prod: install Python 3.14 + Node 24, create a fresh bench with v16 or `bench switch-to-branch version-16 frappe erpnext my_app --upgrade`.
3. `bench setup requirements`, `bench --site x migrate`, `bench build`.
4. Fix your app: deprecated APIs (test classes → `IntegrationTestCase`, etc.), run full test suite.
5. Supervisor: make sure Node 24 is on the system PATH (nvm paths aren't loaded by supervisor).
6. Rehearse, time it, then do prod in a maintenance window with a fresh backup.

## Monitoring

- `/app/system-health-report` (v15+), Error Log, Scheduled Job Log, RQ Job list.
- Alerts on: failed jobs rate, queue length, scheduler disabled (`bench --site x doctor`), disk space, backup age.
- Logs: `frappe-bench/logs/` (web.log, worker.log, scheduler.log) — ship to a central log system.

## Troubleshooting

| Symptom | Check |
|---|---|
| Scheduler jobs not running | `bench --site x doctor`; `bench --site x enable-scheduler`; maintenance mode off; `schedule` process up |
| Jobs stuck queued | workers running for that queue? Redis queue reachable? `bench show-pending-jobs` |
| Realtime not working | socketio process, Redis, nginx `/socket.io` block, `socketio_port` |
| Assets 404 after deploy | `bench build`; `bench setup nginx`; symlink `sites/assets` |
| `migrate` fails on a patch | read traceback; patch not idempotent? column missing → `pre/post_model_sync` order |
| "Site is in maintenance mode" stuck | `bench --site x set-maintenance-mode off` |
| Slow everything | see `frappe-performance`; check gunicorn workers vs CPU, MariaDB `innodb_buffer_pool_size` |
