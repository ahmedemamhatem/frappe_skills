---
name: frappe-controllers
description: Write Python Document controllers for Frappe/ERPNext DocTypes — the exact lifecycle event order for insert, save, submit, cancel, update-after-submit, delete and rename; what belongs in each event; doc helpers (db_set, get_doc_before_save, has_value_changed, flags, child tables, run_method); naming/autoname; virtual and computed fields; and extending standard DocTypes (override_doctype_class, v16 extend_doctype_class). Use when creating or changing any `doctype/<name>/<name>.py`, or debugging "why did my code run twice / not run / see old values".
---

# Document controllers

> **TL;DR:** **Validate in `validate`, change other records in `on_update`/`on_submit`, never commit, never call external systems inline.** Know the event order — most controller bugs are code in the wrong event.

## Event order (verified against Frappe v15/v16 `document.py`)

**New document — `doc.insert()`**
```
before_insert → autoname / naming → before_validate → validate → before_save
→ [row inserted in DB] → after_insert → on_update → on_change
```
Note: `after_insert` runs **before** `on_update`.

**Save existing — `doc.save()`**
```
before_validate → validate → before_save → [DB update] → on_update → on_change
```

**Submit — `doc.submit()`** (docstatus 0 → 1)
```
before_validate → validate → before_submit → [DB update] → on_update → on_submit → on_change
```

**Cancel — `doc.cancel()`** (1 → 2)
```
before_cancel → [DB update] → on_cancel → (back-link check) → on_change
```
`validate` does **not** run on cancel.

**Update after submit** (Allow-on-Submit fields)
```
before_update_after_submit → [DB update] → on_update_after_submit → on_change
```

**Delete — `frappe.delete_doc()`**: `on_trash` → [delete] → `after_delete`
**Rename — `frappe.rename_doc()`**: `before_rename(old, new, merge)` → `after_rename(old, new, merge)`
**Form load (Desk)**: `onload` (server, `doc.set_onload(key, value)` to pass extra data to the form)

`flags.ignore_validate = True` skips everything from `validate` onwards in the "before" phase (but `before_validate` still runs on save/submit).

## What goes where

| Event | Put here | Don't put here |
|---|---|---|
| `before_insert` | defaults that must exist before naming | validation of user input (use validate) |
| `autoname` | custom name logic (`self.name = ...`) | DB writes |
| `before_validate` | normalise input (trim, upper, set derived defaults) | |
| `validate` | **all** checks + `frappe.throw`, computed fields on this doc (totals, status) | changing *other* documents, emails, external calls |
| `before_save` | last-moment field sets that depend on validated data | throws that should have been in validate |
| `before_submit` | submit-only checks (approvals done, mandatory attachments) | |
| `on_update` | side effects on other docs, realtime, enqueue jobs | changing *self* fields with `self.x = ...` (not saved) → use `self.db_set` |
| `after_insert` | create linked docs that need `self.name` | |
| `on_submit` | ledger/stock postings, create follow-up docs, enqueue integrations | |
| `on_cancel` | reverse what `on_submit` did | |
| `on_trash` | block deletes (`frappe.throw`) or clean up dependents | |
| `on_change` | runs after any change incl. `db_set` with notify — keep it light | heavy work |

## Template

```python
# my_app/contracts/doctype/contract/contract.py
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate, flt


class Contract(Document):
    def validate(self):
        self.validate_dates()
        self.validate_no_overlap()
        self.calculate_totals()
        self.set_status()

    def validate_dates(self):
        if getdate(self.end_date) < getdate(self.start_date):
            frappe.throw(_("End Date cannot be before Start Date"))

    def validate_no_overlap(self):
        overlap = frappe.db.exists("Contract", {
            "space": self.space, "docstatus": 1, "name": ["!=", self.name],
            "start_date": ["<=", self.end_date], "end_date": [">=", self.start_date]})
        if overlap:
            frappe.throw(_("Space {0} is already booked by {1}").format(self.space, overlap))

    def calculate_totals(self):
        self.total = sum(flt(i.amount) for i in self.items)

    def set_status(self):
        if self.docstatus == 2:
            self.status = "Cancelled"
        elif self.docstatus == 1:
            self.status = "Expired" if getdate(self.end_date) < getdate() else "Active"
        else:
            self.status = "Draft"

    def on_submit(self):
        frappe.enqueue("my_app.integrations.zk.sync.sync_contract_access",
                       contract=self.name, enqueue_after_commit=True)

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        frappe.enqueue("my_app.integrations.zk.sync.sync_contract_access",
                       contract=self.name, enqueue_after_commit=True)

    def on_update(self):
        if self.has_value_changed("space"):
            self.notify_space_change()
```

## Helpers you'll use

| Need | Use |
|---|---|
| Previous values | `self.get_doc_before_save()` (None on insert), `self.has_value_changed("field")` |
| Set a field after save without re-running hooks | `self.db_set("field", value)` / `self.db_set({...})` (`update_modified=False` to keep timestamp) |
| Is new? | `self.is_new()` |
| Child rows | `self.append("items", {...})`, `self.get("items")`, `self.set("items", [])` |
| Pass flags between events/callers | `self.flags.skip_access_sync = True` (not saved) |
| Call another event-style method | `self.run_method("custom_method")` (also triggers `doc_events` hooks for it) |
| Show non-blocking message | `frappe.msgprint(_("..."), indicator="orange", alert=True)` |
| Type hints for fields | auto-generated `TYPE_CHECKING` block in v15+ controllers — keep it |
| Data to Desk form on load | `def onload(self): self.set_onload("entries_left", ...)` |
| Whitelisted doc method (call from form: `frm.call("renew")`) | `@frappe.whitelist()` on the method; permission is checked on the doc |

## Naming

- DocType settings first: Naming Series (`CON-.YYYY.-.#####`), `field:space_code`, `format:SP-{location}-{###}`.
- Custom: `def autoname(self): self.name = make_autoname(f"{self.location_code}-.####")` (`from frappe.model.naming import make_autoname`).

## Extending standard DocTypes

| Approach | Version | Notes |
|---|---|---|
| `doc_events` in hooks.py | v15, v16 | preferred: add behaviour without replacing the class |
| `override_doctype_class = {"Sales Invoice": "my_app.overrides.sales_invoice.CustomSalesInvoice"}` | v15, v16 | subclass the ERPNext class, call `super()`; **only one app wins** if several override |
| `extend_doctype_class = {"Sales Invoice": ["my_app.overrides.sales_invoice.SalesInvoiceMixin"]}` | **v16 only** | mixins combined across apps — preferred on v16 when you need methods on the class |

```python
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

class CustomSalesInvoice(SalesInvoice):
    def validate(self):
        super().validate()
        self.validate_contract_reference()
```

## Anti-patterns

| ❌ | ✅ |
|---|---|
| `self.field = x` in `on_update` (never saved) | `self.db_set("field", x)` |
| `self.save()` inside `on_update`/`validate` (recursion) | set fields in `validate`, or `db_set` |
| `frappe.db.commit()` in a controller | let the request commit |
| HTTP calls / emails in `validate` | `frappe.enqueue(..., enqueue_after_commit=True)` in `on_update`/`on_submit` |
| Validation in `on_update` (row already written) | `validate` |
| Duplicating checks in Client Script only | server `validate` (client is UX only) |
| `frappe.get_doc` of the same doc inside its own events | use `self` |
| Overriding a whole ERPNext class for one check | `doc_events` → `validate` handler |
