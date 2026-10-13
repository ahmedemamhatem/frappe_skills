# Frappe / ERPNext / React — how we build

This project uses Frappe/ERPNext (v15/v16) with React frontends. Before writing, changing or reviewing code, **load the matching skill** and follow it:

| Task | Skill |
|---|---|
| Starting any feature: can config / a built-in do it? | `frappe-config-first` |
| App or module structure, DocType design, customising ERPNext | `frappe-app-architecture` |
| DocType controller (`doctype/x/x.py`) | `frappe-controllers` |
| `hooks.py` | `frappe-hooks` |
| Queries, `frappe.db`, `frappe.qb`, `get_list`/`get_all` | `frappe-database` |
| Desk form/list JS | `frappe-client-scripts` |
| Server Script records | `frappe-server-scripts` |
| Dialogs, Pages, Desk dashboards | `frappe-desk-ui` |
| Scheduler, `frappe.enqueue`, long jobs | `frappe-background-jobs` |
| Reports, Number Cards, charts | `frappe-reports` |
| Any `@frappe.whitelist` endpoint | `frappe-api-design` + `frappe-security` |
| React / portal / SPA | `frappe-react-frontend` |
| Devices (ZK), payments, webhooks, external APIs | `frappe-integrations` |
| Tests, CI | `frappe-testing` |
| Reviewing a PR or diff | `frappe-code-review` |
| Slowness, loops over records | `frappe-performance` |
| Bench, deploy, upgrade, production | `frappe-devops` |

House rules (always apply):
1. Config before code; never edit ERPNext/Frappe core — hooks, Custom Fields (fixtures), overrides.
2. Every whitelisted method: `methods=[...]`, type hints, document-level permission check.
3. `frappe.get_list` for user-facing data; never `get_all` or SQL with interpolated input for users.
4. Validation in `validate`; side effects in `on_update`/`on_submit`; no `frappe.db.commit()` in request code.
5. External calls and heavy work → `frappe.enqueue(..., enqueue_after_commit=True)`.
6. New behaviour ships with tests; run them before saying a task is done.
