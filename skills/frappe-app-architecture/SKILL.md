---
name: frappe-app-architecture
description: Structure and evolve custom Frappe/ERPNext apps — app and module layout, where code lives (controllers, services, api, integrations, React SPA), DocType and data-model design, extending ERPNext without touching core (fixtures, Custom Fields, overrides, doc_events), patches and migrations, multi-app dependencies, and settings/feature flags. Use when starting a new app, adding a module or major feature, designing DocTypes, deciding how to customise ERPNext, or refactoring a messy app.
---

# Frappe app architecture

> **TL;DR:** One custom app per product/domain, modules by business area, **controllers own behaviour, services own cross-DocType workflows, `api/` is thin, integrations isolated**. Extend ERPNext through hooks, Custom Fields (as fixtures) and overrides — never by editing core.

## New app

```bash
bench new-app my_app          # title, description, publisher, email, license
bench --site dev.localhost install-app my_app
bench --site dev.localhost set-config developer_mode 1   # required to create/export DocTypes
```

Declare dependencies in `hooks.py`:

```python
required_apps = ["erpnext"]   # bench refuses to install my_app without it
```

## Recommended layout

```
my_app/
├── my_app/
│   ├── hooks.py
│   ├── patches.txt
│   ├── modules.txt                 # Spaces, Contracts, Access, Billing
│   ├── spaces/                     # one folder per module
│   │   ├── doctype/space/{space.json, space.py, space.js, test_space.py}
│   │   ├── report/occupancy/...
│   │   └── workspace/spaces/...
│   ├── contracts/doctype/contract/...
│   ├── services/                   # cross-DocType workflows (pure-ish Python)
│   │   └── contract_lifecycle.py   # activate(), renew(), terminate()
│   ├── api/v1/                     # thin whitelisted endpoints (see frappe-api-design)
│   ├── integrations/zk/            # client.py, sync.py, reconcile.py (see frappe-integrations)
│   ├── overrides/                  # override_doctype_class targets
│   │   └── sales_invoice.py
│   ├── patches/v1_0/               # data migrations
│   ├── fixtures/                   # exported custom fields, property setters, roles…
│   ├── public/{js,css}             # Desk assets (bundled via *.bundle.js)
│   ├── www/portal.{html,py}        # SPA entry (generated)
│   └── tests/factories.py
├── portal/                         # React SPA source (see frappe-react-frontend)
└── pyproject.toml
```

### Where does this code go?

| Code | Place |
|---|---|
| Validation / defaults / state of **one** DocType | its controller `doctype/x/x.py` (`validate`, `before_submit`, …) |
| Workflow across several DocTypes (contract → invoice → access) | `services/` function, called from controller events or APIs |
| Reacting to **ERPNext** DocType events (Sales Invoice paid) | `doc_events` in `hooks.py` → handler in `services/` or `overrides/` |
| Changing ERPNext DocType behaviour | `override_doctype_class` (extend the class, call `super()`) — sparingly |
| HTTP endpoint | `api/v1/<resource>.py` |
| Talking to an external system | `integrations/<system>/` |
| Desk UI tweaks for an ERPNext form | `doctype_js` in hooks → `public/js/<doctype>.js` |
| Rich UI for portal users | React SPA |

## Designing DocTypes

- **Name things in the business language** (`Space`, `Contract`, `Access Credential`), singular, Title Case.
- **Naming:** `naming_series` for transactional docs (`CON-.YYYY.-.#####`), `field:` / `format:` for masters with natural keys. Avoid hash names for anything users talk about.
- **Submittable** (`is_submittable`) for anything with legal/financial meaning (contracts, payments) → immutable after submit, cancel + amend for changes.
- **Child tables** for lines owned by the parent (contract items, schedule); **Link** to separate DocType when the thing has its own life (Space, Customer).
- **Reuse ERPNext masters**: Customer, Contact, Address, Item, Price List, Company, Cost Center, Project. Don't create a parallel "Tenant" DocType if Customer + a few Custom Fields does it.
- **Tree DocTypes** (`is_tree`) for hierarchies (Location → Building → Floor → Space).
- Add `status` as a Select with a clear state list; drive it from code or a **Workflow** (config) — not both.
- Put **Search Index** on fields you filter big lists by; **unique** where the business says unique.
- **Settings** → Single DocType (`issingle`).

## Extending ERPNext (no core edits)

| Need | Tool | Notes |
|---|---|---|
| Extra field on Sales Invoice | Custom Field | ship as **fixture** (filtered by module or name) |
| Change label/hidden/mandatory of a standard field | Property Setter | fixture |
| Run code when Sales Invoice is submitted | `doc_events` | keep handler small, enqueue heavy work |
| Change a method of a standard DocType | `override_doctype_class` | subclass the original, call `super()`; only one app can win — document it |
| Replace a whitelisted API | `override_whitelisted_methods` | last resort |
| Extend list/form JS | `doctype_js`, `doctype_list_js` | |
| Add permission logic | `permission_query_conditions`, `has_permission` hooks | see `frappe-security` and its `references/permissions-api.md` |

Fixtures in `hooks.py`:

```python
fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Contracts"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Contracts"]]},
    {"dt": "Role", "filters": [["name", "in", ["Space Manager", "Tenant", "Device Bridge"]]]},
    "Workflow", "Workflow State", "Workflow Action Master",   # careful: unfiltered exports everything
]
```

`bench --site dev.localhost export-fixtures --app my_app` → commit `fixtures/*.json`. **Set `module` on every Custom Field / Property Setter** you create so the filter catches it.

## Patches (migrations)

```
# patches.txt
[pre_model_sync]
my_app.patches.v1_0.rename_tenant_field        # runs before DocType JSON sync

[post_model_sync]
my_app.patches.v1_0.backfill_contract_status   # runs after new fields exist
```

```python
# my_app/patches/v1_0/backfill_contract_status.py
import frappe

def execute():
    if not frappe.db.has_column("Contract", "status"):
        return
    frappe.db.sql("""update `tabContract` set status='Active'
                     where docstatus=1 and (status is null or status='')""")
```

Rules: idempotent (safe to re-run), no `frappe.get_doc(...).save()` loops over big tables (use SQL/qb + batches), never edit a patch after release — add a new one. Field renames: `rename_field` from `frappe.model.utils.rename_field` in `pre_model_sync`.

## Configuration & feature flags

- Business config → Settings DocType (editable by admins, versioned in DB).
- Infra config → `site_config.json` (`frappe.conf.get("zk_bridge_url")`), never committed with secrets.
- Feature flags → Check fields in Settings, read via `frappe.get_cached_doc` (cache invalidates on save).

## Multi-app bench

- Before building, check installed apps (`bench --site x list-apps`) — HRMS, Payments, Insights, Helpdesk, CRM may already have it.
- Shared logic between your apps → a small common app (`my_core`), listed in `required_apps`.
- Avoid circular imports between apps; communicate via hooks/doc_events.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| Editing files in `apps/erpnext` | hooks, Custom Fields, overrides |
| Custom Fields created on prod by hand | fixtures / patch, from dev |
| One giant `utils.py` | `services/`, `integrations/`, controllers |
| Business logic in Client Scripts | server controller (client only for UX) |
| Parallel copies of ERPNext masters | reuse Customer/Item/Contact + Custom Fields |
| Editing a released patch | new patch |
| `override_doctype_class` for something `doc_events` can do | `doc_events` |
