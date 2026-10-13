---
name: frappe-desk-ui
description: Build custom UI inside Frappe Desk (not the React portal) — frappe.ui.Dialog and frappe.prompt, custom Pages, workspace shortcuts, list view and tree view customisation, form dashboards/connections, HTML fields, realtime updates in Desk, frappe.ui.form controls, and bundling JS/CSS with *.bundle.js. Use when staff-facing screens in Desk need dialogs, wizards, custom pages, dashboards or live updates, or when deciding between a Desk Page and the React SPA.
---

# Desk UI

> **TL;DR:** Staff work in Desk — extend it with dialogs, form buttons, list settings and Pages before building a separate React app. Use the React SPA (`frappe-react-frontend`) for portal users (tenants/customers) or truly custom experiences.

## Desk or React?

| Users | Screen | Choose |
|---|---|---|
| Staff | forms, lists, approvals | Desk forms + client scripts |
| Staff | one special screen (front desk check-in, floor map) | **Desk Page** (or a React bundle mounted inside a Page) |
| Tenants / customers | portal | React SPA or Web Forms |

## Dialog

```js
const d = new frappe.ui.Dialog({
    title: __("Renew Contract"),
    fields: [
        { fieldname: "months", label: __("Months"), fieldtype: "Select", options: "1\n3\n6\n12", default: "12", reqd: 1 },
        { fieldname: "space", label: __("Space"), fieldtype: "Link", options: "Space",
          get_query: () => ({ filters: { is_active: 1 } }) },
        { fieldtype: "Section Break" },
        { fieldname: "notes", label: __("Notes"), fieldtype: "Small Text" },
    ],
    primary_action_label: __("Renew"),
    async primary_action(values) {
        await frm.call("renew", values);
        d.hide();
        frm.reload_doc();
    },
});
d.show();
```

Quick one-field input: `frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", reqd: 1 }, v => ..., __("Reason"))`.
Confirm: `frappe.confirm(__("Cancel access?"), () => ...)`.

## Custom Page

Create a **Page** (developer mode, module set) → `my_app/spaces/page/front_desk/front_desk.js`:

```js
frappe.pages["front-desk"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Front Desk"), single_column: true });
    page.set_primary_action(__("Check In"), () => check_in(page));
    const location = page.add_field({ fieldname: "location", label: __("Location"), fieldtype: "Link",
                                      options: "Location", change: () => load(page) });
    page.main.html(`<div class="front-desk-list"></div>`);
    page.location = location;
    load(page);
    frappe.realtime.on("access_event", () => load(page));     // live updates
};

async function load(page) {
    const rows = await frappe.xcall("my_app.api.v1.access.today_entries", { location: page.location.get_value() });
    page.main.find(".front-desk-list").html(frappe.render_template("front_desk_rows", { rows }));
}
```

Templates: `front_desk_rows.html` next to the JS (Frappe micro-template, `{{ }}` / `{% %}`), or build DOM in JS. Restrict the Page with its **Roles** table.

## Form dashboard & connections

```python
# contract_dashboard.py (next to the controller)
def get_data():
    return {
        "fieldname": "contract",
        "transactions": [
            {"label": "Billing", "items": ["Sales Invoice", "Payment Entry"]},
            {"label": "Access", "items": ["Access Credential", "Access Event"]},
        ],
    }
```

Add indicators/headlines from JS: `frm.dashboard.add_indicator(__("Entries left: {0}", [n]), "blue")`, `frm.dashboard.set_headline(...)`.

## HTML field rendering

```js
refresh(frm) {
    frm.get_field("usage_html").$wrapper.html(frappe.render_template("contract_usage", { usage: frm.doc.__onload?.usage }));
}
```

Feed data via the controller's `onload` → `self.set_onload("usage", ...)`.

## Tree view

For `is_tree` DocTypes (Location → Building → Floor → Space): `doctype_tree_js` / `<doctype>_tree.js` with `frappe.treeview_settings["Location"] = { get_tree_nodes: "...", add_tree_node: "...", fields: [...] }`.

## Realtime in Desk

Server: `frappe.publish_realtime("access_event", {...}, after_commit=True)`.
Client: `frappe.realtime.on("access_event", cb)`; remove with `frappe.realtime.off("access_event", cb)` when leaving the page.
Forms already auto-refresh notices when someone else saves the doc.

## Assets

`public/js/front_desk.bundle.js` + `app_include_js = "front_desk.bundle.js"` (or include per page/doctype). `bench build --app my_app`. Use CSS variables (`var(--text-color)`, `var(--bg-color)`) so dark mode works.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| Building a React app for a single staff dialog | `frappe.ui.Dialog` |
| jQuery string HTML with unescaped user data | `frappe.utils.escape_html` / templates |
| Polling with `setInterval` | `frappe.realtime.on` |
| Hard-coded colors | Frappe CSS variables |
| Page without Roles | set Roles on the Page |
