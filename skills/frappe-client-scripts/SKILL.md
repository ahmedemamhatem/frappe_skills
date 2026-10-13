---
name: frappe-client-scripts
description: Write Desk form and list JavaScript for Frappe/ERPNext — frappe.ui.form.on events (setup, onload, refresh, validate, before_save, after_save, submit/cancel, field change, child table add/remove), set_query for Link filters, custom buttons, frm.set_value / set_df_property / toggle_display, calling server methods (frm.call, frappe.call, frappe.xcall), child table helpers, list view settings, and the difference between app form scripts and Client Script records. Use for any change to how a Desk form or list behaves in the browser.
---

# Desk client scripts

> **TL;DR:** Client scripts are for **UX** — filters, buttons, showing/hiding, quick fetches. Anything that must be enforced goes in the server controller. Prefer `depends_on` / `fetch_from` / Property Setters before writing JS.

## Where the code lives

| Case | Place |
|---|---|
| Your own DocType | `doctype/contract/contract.js` (auto-loaded) |
| Standard/ERPNext DocType from your app | `public/js/sales_invoice.js` + `doctype_js` in hooks.py |
| Quick site-specific tweak by an admin | **Client Script** record (Desk) — not version-controlled; export as fixture if it must ship |
| List view | `contract_list.js` (`frappe.listview_settings["Contract"]`) |

## Form events

```js
frappe.ui.form.on("Contract", {
    setup(frm) {                         // once per form instance: set_query here
        frm.set_query("space", () => ({ filters: { location: frm.doc.location, is_active: 1 } }));
        frm.set_query("item_code", "items", (doc, cdt, cdn) => ({ filters: { item_group: "Spaces" } }));
    },
    onload(frm) {},                      // doc loaded (first time)
    refresh(frm) {                       // every render: buttons, indicators, read-only toggles
        if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
            frm.add_custom_button(__("Renew"), () => renew(frm), __("Actions"));
        }
        frm.toggle_display("allowed_entries", frm.doc.plan_type === "Entries");
    },
    validate(frm) {                      // before save — can block with frappe.throw / frappe.validated = false
        if (frm.doc.end_date < frm.doc.start_date) frappe.throw(__("End before start"));
    },
    before_save(frm) {}, after_save(frm) {},
    before_submit(frm) {}, on_submit(frm) {},
    before_cancel(frm) {}, after_cancel(frm) {},

    // field change: event name = fieldname
    space(frm) {
        if (!frm.doc.space) return;
        frappe.db.get_value("Space", frm.doc.space, ["monthly_rate", "capacity"]).then(({ message }) => {
            frm.set_value("monthly_rent", message.monthly_rate);
        });
    },
});

// child table events: on the child DocType
frappe.ui.form.on("Contract Item", {
    qty(frm, cdt, cdn) { calc_row(frm, cdt, cdn); },
    rate(frm, cdt, cdn) { calc_row(frm, cdt, cdn); },
    items_add(frm, cdt, cdn) {},          // <tablefield>_add
    items_remove(frm) { calc_total(frm); },// <tablefield>_remove
});

function calc_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
    calc_total(frm);
}
```

## Calling the server

```js
// doc method (@frappe.whitelist on the controller method) — permission checked on the doc
frm.call("renew", { months: 12 }).then(r => { frm.reload_doc(); frappe.show_alert(__("Renewed")); });

// module function
frappe.call({ method: "my_app.api.v1.contracts.get_summary", args: { name: frm.doc.name },
              freeze: true, freeze_message: __("Loading...") })
    .then(r => render_summary(frm, r.message));

// promise style
const summary = await frappe.xcall("my_app.api.v1.contracts.get_summary", { name: frm.doc.name });
```

## Common helpers

| Need | Code |
|---|---|
| Set value (triggers change events) | `frm.set_value("field", v)` / `frm.set_value({a: 1, b: 2})` |
| Child row value | `frappe.model.set_value(cdt, cdn, "field", v)` |
| Add child row | `const r = frm.add_child("items", {item_code}); frm.refresh_field("items")` |
| Field property | `frm.set_df_property("field", "read_only", 1)`; also `reqd`, `hidden`, `options`, `label` |
| Toggle | `frm.toggle_reqd("f", cond)`, `frm.toggle_enable("f", cond)`, `frm.toggle_display("f", cond)` |
| Intro / indicator | `frm.set_intro(__("Pending approval"), "orange")`, `frm.page.set_indicator(__("Active"), "green")` |
| Dialog | see `frappe-desk-ui` |
| Translate | `__("Text {0}", [value])` |
| Route | `frappe.set_route("Form", "Space", frm.doc.space)` |

## List view

```js
frappe.listview_settings["Contract"] = {
    add_fields: ["status", "end_date"],
    get_indicator(doc) {
        return { Active: [__("Active"), "green", "status,=,Active"],
                 Expired: [__("Expired"), "red", "status,=,Expired"] }[doc.status] || [__(doc.status), "gray"];
    },
    onload(listview) {
        listview.page.add_inner_button(__("Expiring this month"), () =>
            listview.filter_area.add([["Contract", "end_date", "Timespan", "this month"]]));
    },
};
```

## Anti-patterns

| ❌ | ✅ |
|---|---|
| Validation only in JS | server `validate`; JS is a nicer early message |
| `set_query` inside `refresh` (re-registered every render) | `setup` |
| JS just to show/hide or make mandatory | `depends_on` / `mandatory_depends_on` in DocType |
| JS fetching a value from a Link | `fetch_from` |
| `frappe.call` with `async: false` | promises / `frappe.xcall` |
| `frm.save()` inside `after_save` / `refresh` | loops; don't |
| `frappe.db.get_list` in a loop per row | one server method returning everything |
| Hard-coded English strings | `__()` |
