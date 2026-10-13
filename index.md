# Frappe dev skills (include in CLAUDE.md)

This project uses Frappe/ERPNext (v15/v16) with React frontends. Before writing or reviewing code, load the matching skill from `.claude/skills/`:

- Designing an app, module, DocType, or ERPNext customisation → `frappe-app-architecture`
- Adding/changing any `@frappe.whitelist` endpoint → `frappe-api-design` + `frappe-security`
- Any React/portal/SPA work → `frappe-react-frontend`
- Talking to devices (ZK), payment gateways, webhooks, external APIs → `frappe-integrations`
- Writing tests or CI → `frappe-testing`
- Reviewing a PR or diff → `frappe-code-review`
- Something is slow, or code loops over records → `frappe-performance`
- Bench, deploy, upgrade, production issues → `frappe-devops`

House rules (always):
1. Never edit ERPNext/Frappe core — use hooks, Custom Fields (fixtures), overrides.
2. Every whitelisted method: `methods=[...]`, type hints, document-level permission check.
3. `frappe.get_list` for user-facing data, never `get_all` or raw SQL with interpolated input.
4. External calls and heavy work go to `frappe.enqueue(..., enqueue_after_commit=True)`.
5. New behaviour ships with tests.
