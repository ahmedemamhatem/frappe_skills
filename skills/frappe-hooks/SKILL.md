---
name: frappe-hooks
description: Reference for a custom app's hooks.py in Frappe/ERPNext v15/v16 — doc_events (including wildcard "*"), scheduler_events, fixtures, overrides (override_doctype_class, v16 extend_doctype_class, override_whitelisted_methods), permission hooks, Desk asset includes (app_include_js, doctype_js, doctype_list_js), website routes, boot info, install/migrate hooks, request hooks, jinja methods and user_data_fields. Use whenever adding or changing hooks.py, or when something "configured in hooks" doesn't fire.
---

# hooks.py

> **TL;DR:** hooks.py is your app's wiring diagram. Keep handlers as dotted paths to small functions, run `bench --site x migrate` (or at least `clear-cache`) after changing it, and remember hooks from **all** installed apps are merged.

## Document events

```python
doc_events = {
    "Contract": {
        "validate": "my_app.contracts.events.validate_contract",
        "on_submit": "my_app.contracts.events.on_contract_submit",
        "on_cancel": "my_app.contracts.events.on_contract_cancel",
    },
    "Sales Invoice": {
        "on_submit": "my_app.billing.events.link_invoice_to_contract",
    },
    "*": {
        "on_update": "my_app.audit.events.track_sensitive_changes",   # every DocType: keep it tiny
    },
}
```

```python
def on_contract_submit(doc, method=None):   # signature: (doc, method)
    ...
```

- Same event names as controller methods (`before_insert`, `validate`, `on_update`, `on_submit`, `on_cancel`, `on_trash`, `after_insert`, `before_rename`, `on_update_after_submit`, `on_change`…). See `frappe-controllers` for order.
- Hook handlers run **after** the controller's own method for that event.
- A list of paths is allowed per event: `"validate": ["a.b.c", "a.b.d"]`.
- `"*"` runs for every document save in the system — heavy code here slows the whole site.

## Scheduler

```python
scheduler_events = {
    "all": ["my_app.tasks.every_tick"],                # every scheduler tick (~4 min) — rarely needed
    "hourly": ["my_app.tasks.hourly"],
    "daily": ["my_app.tasks.expire_contracts"],
    "weekly": [...], "monthly": [...],
    "hourly_long": [...], "daily_long": ["my_app.tasks.rebuild_occupancy"],  # *_long → long queue
    "cron": {
        "*/5 * * * *": ["my_app.integrations.zk.sync.retry_due"],
        "15 2 * * *": ["my_app.integrations.zk.reconcile.run"],
    },
}
```

After changing: `bench --site x migrate` (syncs Scheduled Job Type records). Check runs in **Scheduled Job Log**. Details: `frappe-background-jobs`.

## Fixtures

```python
fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Contracts"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Contracts"]]},
    {"dt": "Role", "filters": [["name", "in", ["Space Manager", "Tenant"]]]},
    {"dt": "Workflow", "filters": [["document_type", "in", ["Contract"]]]},
]
```

`bench --site x export-fixtures --app my_app` → JSON in `my_app/fixtures/`, imported on `migrate`/install. Always filter — an unfiltered `"Custom Field"` exports every customisation on the site.

## Overrides & extension

```python
override_doctype_class = {"Sales Invoice": "my_app.overrides.sales_invoice.CustomSalesInvoice"}
extend_doctype_class = {"Sales Invoice": ["my_app.overrides.sales_invoice.InvoiceMixin"]}  # v16 only
override_whitelisted_methods = {
    "erpnext.selling.doctype.quotation.quotation.make_sales_order": "my_app.overrides.quotation.make_sales_order",
}
```

## Permissions

```python
permission_query_conditions = {"Contract": "my_app.permissions.contract_query"}   # list filtering (SQL condition)
has_permission = {"Contract": "my_app.permissions.contract_has_permission"}       # single doc check
```

See `frappe-security` and `frappe-security/references/permissions-api.md`.

## Desk assets

```python
app_include_js = "my_app.bundle.js"          # every Desk page (public/js/my_app.bundle.js)
app_include_css = "my_app.bundle.css"
doctype_js = {"Sales Invoice": "public/js/sales_invoice.js"}            # add form script to a standard DocType
doctype_list_js = {"Contract": "public/js/contract_list.js"}
doctype_tree_js = {"Location": "public/js/location_tree.js"}
web_include_js = "my_app_web.bundle.js"      # website/portal pages
```

`*.bundle.js` / `*.bundle.css` in `public/` are built by `bench build` (esbuild). After changes: `bench build --app my_app`, hard refresh.

## Website & portal

```python
website_route_rules = [{"from_route": "/portal/<path:app_path>", "to_route": "portal"}]   # SPA deep links
portal_menu_items = [{"title": "My Contracts", "route": "/contracts", "reference_doctype": "Contract", "role": "Tenant"}]
has_website_permission = {"Contract": "my_app.permissions.contract_website_permission"}
```

## Boot, session, requests

```python
extend_bootinfo = "my_app.boot.extend_bootinfo"   # def extend_bootinfo(bootinfo): bootinfo.my_app = {...}
on_session_creation = "my_app.auth.on_login"
on_logout = "my_app.auth.on_logout"
before_request = ["my_app.request.before"]        # every request — keep it extremely light
after_request = ["my_app.request.after"]
```

Boot data is available in Desk JS as `frappe.boot.my_app`. Don't put large or per-record data in boot.

## Install / migrate

```python
required_apps = ["erpnext"]
before_install = "my_app.install.before_install"
after_install = "my_app.install.after_install"       # create default records, roles
after_migrate = ["my_app.install.after_migrate"]      # idempotent sync tasks
before_uninstall = "my_app.install.before_uninstall"
```

## Jinja & misc

```python
jinja = {"methods": ["my_app.utils.jinja.format_space"], "filters": ["my_app.utils.jinja.arabic_number"]}
standard_queries = {"Customer": "my_app.queries.customer_query"}        # Link field search
user_data_fields = [{"doctype": "Access Credential", "filter_by": "user", "redact_fields": ["card_no"], "partial": 1}]
ignore_links_on_delete = ["Access Event"]
auto_cancel_exempted_doctypes = ["Payment Entry"]
```

## Debugging "my hook doesn't run"

1. Dotted path correct and importable? `bench --site x console` → `frappe.get_attr("my_app.x.y")`.
2. `bench --site x clear-cache` (hooks are cached), then `migrate` for scheduler/fixtures.
3. App installed on *this* site? `bench --site x list-apps`.
4. Look at merged hooks: `frappe.get_hooks("doc_events")` in console.
5. Event name typo (`on_submitt`) fails silently.
