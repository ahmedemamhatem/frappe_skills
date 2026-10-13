---
name: frappe-server-scripts
description: Write and decide on Frappe/ERPNext Server Scripts (the Desk "Server Script" DocType) — enabling them, the four types (DocType Event, Scheduler Event, Permission Query, API), the event list, the restricted sandbox (no imports, limited frappe API, safe HTTP helpers), common patterns, and when to move a Server Script into app code instead. Use when a request mentions Server Script, when writing low-code automation on a site without a custom app, or when reviewing or migrating existing Server Scripts.
---

# Server Scripts

> **TL;DR:** Server Scripts are quick, site-level Python in a sandbox. Great for small automations and prototypes on a site you don't deploy code to. Anything important, tested or reused belongs in a custom app (controller / hooks) under git.

## Enable

Disabled by default since v15:

```bash
bench set-config -g server_script_enabled 1     # whole bench (or per site: bench --site x set-config server_script_enabled 1)
```

## When to use / not

| Use a Server Script | Use app code |
|---|---|
| Site has no custom app, small rule needed now | You have a custom app (you do) |
| Admin-owned tweak that may change often | Logic must be reviewed, tested, versioned |
| Prototype before writing it properly | Needs imports, libraries, external SDKs |
| | Performance-sensitive or complex |

Rule of thumb for teams with a custom app: Server Scripts only for prototypes; move to code before go-live.

## Types

| Type | Runs | Key fields |
|---|---|---|
| **DocType Event** | on a document event | Reference DocType, DocType Event |
| **Scheduler Event** | on schedule | Event Frequency (Hourly, Daily, Cron + expression…) |
| **Permission Query** | when listing a DocType | set `conditions` (SQL string) |
| **API** | `GET/POST /api/method/<api_method>` | API Method name, Allow Guest, Rate limit |

DocType Event options: Before Insert, Before Validate, Before Save, After Insert, After Save, Before Rename, After Rename, Before Submit, After Submit, Before Cancel, After Cancel, Before Delete, After Delete, Before Save (Submitted Document), After Save (Submitted Document), Before Print, On Payment Authorization.

## Sandbox rules

- **No `import`** statements. Use what's provided: `frappe`, `frappe.db`, `frappe.qb`, `frappe.utils` (dates/numbers), `json`, `_` (translate), `frappe.make_get_request` / `frappe.make_post_request` for HTTP, `frappe.sendmail`, `frappe.enqueue` (wrapped), `frappe.log_error`, `frappe.throw`, `frappe.msgprint`.
- In DocType Event scripts the document is `doc`.
- In API scripts, inputs are `frappe.form_dict`; return data with `frappe.response["message"] = ...`.
- In Permission Query scripts set `conditions = "..."`, user is `user`.
- No access to files, OS, private attributes (`_x`), or arbitrary modules.
- Read with `frappe.get_list` / `frappe.db.get_value`; for user-facing data assume and design for permission filtering.

## Examples

**DocType Event — Before Save on Contract**
```python
if doc.end_date and doc.start_date and doc.end_date < doc.start_date:
    frappe.throw(_("End Date cannot be before Start Date"))

doc.total = sum((row.amount or 0) for row in doc.items)
```

**DocType Event — After Submit, enqueue work**
```python
frappe.enqueue("my_app.integrations.zk.sync.sync_contract_access", contract=doc.name)
```

**Scheduler Event — daily expiry**
```python
for name in frappe.get_all("Contract", filters={"status": "Active", "end_date": ["<", frappe.utils.today()]}, pluck="name"):
    frappe.db.set_value("Contract", name, "status", "Expired")
```

**API — `/api/method/contract_status`**
```python
name = frappe.form_dict.get("name")
if not name:
    frappe.throw(_("name is required"))
doc = frappe.get_doc("Contract", name)
if not frappe.has_permission("Contract", "read", doc):
    frappe.throw(_("Not permitted"), frappe.PermissionError)
frappe.response["message"] = {"status": doc.status, "end_date": doc.end_date}
```

**Permission Query — tenants see their own contracts**
```python
customer = frappe.db.get_value("Contact", {"user": user}, "customer")
if "Tenant" in frappe.get_roles(user) and "Space Manager" not in frappe.get_roles(user):
    conditions = f"`tabContract`.tenant = {frappe.db.escape(customer)}" if customer else "1=0"
```

## Migrating a Server Script to app code

| Server Script | App code |
|---|---|
| DocType Event: Before Save | controller `validate` (or `doc_events` → `validate`) |
| After Save | `on_update` |
| After Submit | `on_submit` |
| Scheduler Event | `scheduler_events` in hooks.py |
| API | `@frappe.whitelist(methods=[...])` in `api/v1/...` |
| Permission Query | `permission_query_conditions` hook |

Then disable the Server Script (don't delete until the code is live), add tests.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| Business-critical logic only in Server Scripts | app code with tests |
| Same rule in a Server Script *and* the controller | one place |
| API script with Allow Guest and no rate limit | set rate limit, validate input |
| Long loops / heavy work in a DocType Event script | `frappe.enqueue` |
| `import json` (fails) | use the provided `json` |
