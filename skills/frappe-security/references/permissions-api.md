# Permissions API reference

## Checks in Python

```python
frappe.has_permission("Contract", "write", doc=name_or_doc, user=None, throw=False)   # → bool
frappe.has_permission("Contract", "read", doc, throw=True)                            # raises PermissionError
doc.check_permission("write")             # raises if the session user can't
doc.has_permission("submit")              # → bool
frappe.only_for(["Space Manager", "System Manager"])   # raises unless user has one of the roles
frappe.get_roles(user=None)               # list of roles
frappe.session.user                       # current user ("Guest" for anonymous)
```

Permission types (`ptype`): `read`, `write`, `create`, `delete`, `submit`, `cancel`, `amend`, `report`, `export`, `import`, `print`, `email`, `share`, `select` (only in Link dropdowns).

## What enforces automatically

| Operation | Checks perms? |
|---|---|
| `frappe.get_list`, `/api/resource` | ✅ role + user permissions + `permission_query_conditions` |
| `frappe.get_all`, `frappe.db.*`, `frappe.qb`, raw SQL | ❌ |
| `doc.insert()` | ✅ `create` (unless `ignore_permissions=True`) |
| `doc.save()` / `submit()` / `cancel()` | ✅ |
| `frappe.get_doc()` | ❌ loading isn't checked → call `doc.check_permission("read")` when returning to users |
| `frappe.db.set_value` | ❌ |
| `frappe.delete_doc` | ✅ (unless `ignore_permissions=True`) |
| Whitelisted **doc** method (`frm.call`) | ✅ doc read/write as configured |
| Whitelisted module function | ❌ only "logged in" — you check |

## User Permissions

```python
from frappe.permissions import add_user_permission, remove_user_permission
add_user_permission("Location", "Mall A", "manager@example.com", ignore_permissions=True)
frappe.get_list("Contract")   # now limited to Contracts whose Link field to Location = Mall A
```

Options on a User Permission: `applicable_for` (only certain DocTypes), `is_default`, `hide_descendants` (trees). DocType fields can opt out with "Ignore User Permissions".

## Permission levels

Field-level: set `permlevel` (1, 2…) on sensitive fields (e.g. rent amount, card number); grant read/write for that level only to certain roles in Role Permission Manager.

## Sharing

```python
frappe.share.add("Contract", name, user="tenant@example.com", read=1, write=0, notify=1)
```

Shared docs are visible even without role permission — useful for one-off access, not as a permission model.

## Hooks

```python
# hooks.py
permission_query_conditions = {"Contract": "my_app.permissions.contract_query"}   # returns SQL condition string
has_permission = {"Contract": "my_app.permissions.contract_has_permission"}       # returns True/False/None
```

- `query(user)` → string appended to WHERE (`""` = no restriction). Escape with `frappe.db.escape`.
- `has_permission(doc, ptype, user)` → `False` denies, `True`/`None` continues standard checks (it can't grant beyond role permissions).
- Both run for every list/doc access of that DocType — keep them cheap (cache lookups per user).

## Portal / website

- Portal users = Website Users with roles like `Customer`/your `Tenant` role.
- `has_website_permission` hook for portal list/detail pages; `portal_menu_items` to show menu entries per role.
