---
name: frappe-database
description: Read and write data correctly in Frappe/ERPNext — choosing between frappe.get_list (permission-aware) and frappe.get_all / frappe.db.* (no permission checks), filters syntax, get_value / set_value / exists / count, frappe.qb query builder (joins, aggregates, subqueries, functions), raw SQL safely, transactions and savepoints, bulk inserts/updates, and caching reads. Use whenever code queries or updates the database, writes a report query, or a query is slow or returns wrong/forbidden data.
---

# Database access

> **TL;DR:** User-facing reads → `frappe.get_list` (applies permissions). Internal/system reads → `frappe.get_all` / `frappe.db.get_value`. Complex queries → `frappe.qb`. Raw SQL only with parameters. Never commit in request code.

## Choose the call

| Need | Call | Permissions? |
|---|---|---|
| List for a user (API, report, portal) | `frappe.get_list(dt, filters, fields, order_by, limit_start, limit_page_length)` | ✅ |
| List for system logic / jobs | `frappe.get_all(...)` (same args) | ❌ |
| One/few fields of one record | `frappe.db.get_value(dt, name_or_filters, fields, as_dict=True)` | ❌ |
| Single DocType setting | `frappe.db.get_single_value("ZK Settings", "base_url")` or `frappe.get_cached_doc(...)` | ❌ |
| Exists? | `frappe.db.exists(dt, name_or_filters)` → name or None | ❌ |
| Count | `frappe.db.count(dt, filters)` | ❌ |
| Full document (with children, methods) | `frappe.get_doc(dt, name)`; check `doc.check_permission("read")` for users | via check |
| Update fields without hooks | `frappe.db.set_value(dt, name, {"a": 1})` | ❌ (no validate!) |
| Update with hooks/validation | `doc = frappe.get_doc(...); doc.x = 1; doc.save()` | ✅ on save |
| Delete | `frappe.delete_doc(dt, name)` (runs on_trash) | ✅ |

`frappe.db.set_value` skips validation and hooks — use only for internal flags/status fields where that's intended.

## Filters

```python
filters = {"status": "Active", "end_date": ["<", today()]}                      # dict
filters = [["status", "=", "Active"], ["space", "in", ["SP-1", "SP-2"]]]          # list
or_filters = [["tenant", "=", c], ["guarantor", "=", c]]
# operators: = != > < >= <= like "not like" in "not in" between "is" ("set"/"not set") descendants of / ancestors of (trees)
frappe.get_all("Contract", filters={"end_date": ["between", [start, end]]}, fields=["name"], pluck="name")
frappe.get_all("Contract", filters={"cancel_reason": ["is", "not set"]})
```

Child table fields in `get_list`: `fields=["name", "`tabContract Item`.item_code"]` or `"items.item_code"`.

## Query builder (frappe.qb)

```python
from frappe.query_builder.functions import Count, Sum, Coalesce
Contract = frappe.qb.DocType("Contract")
Item = frappe.qb.DocType("Contract Item")

rows = (
    frappe.qb.from_(Contract)
    .inner_join(Item).on(Item.parent == Contract.name)
    .select(Contract.space, Count(Contract.name).as_("contracts"), Sum(Item.amount).as_("revenue"))
    .where((Contract.docstatus == 1) & (Contract.start_date >= from_date))
    .groupby(Contract.space)
    .orderby(Sum(Item.amount), order=frappe.qb.desc)
    .limit(50)
).run(as_dict=True)

# update / delete
frappe.qb.update(Contract).set(Contract.status, "Expired").where(
    (Contract.status == "Active") & (Contract.end_date < today())).run()
```

Values in qb are parameterised automatically. `.run(debug=True)` prints SQL.

## Raw SQL (when you must)

```python
frappe.db.sql("""
    select name, end_date from `tabContract`
    where space = %(space)s and docstatus = 1
    order by end_date desc
""", {"space": space}, as_dict=True)
```

Never f-string values in. Identifiers (sort field, table) must come from a whitelist.

## Writes in bulk

```python
# many inserts without per-doc hooks (logs, imports)
frappe.db.bulk_insert("Access Event", fields=["name", "device", "event_id", "event_time"],
                      values=[(frappe.generate_hash(length=10), d, e, t) for d, e, t in rows])
```

Needs every mandatory column incl. `name`, `creation`/`modified` if your DocType needs them; skips validation — use for append-only logs. For normal records, loop `insert()` inside a background job in batches.

## Transactions

- A web request is one transaction: commit at the end, rollback on exception. **Don't** `frappe.db.commit()` in controllers or APIs.
- Background jobs and patches may commit per batch: `frappe.db.commit()` every N records.
- Partial failure isolation: `frappe.db.savepoint("sp")` … `frappe.db.rollback(save_point="sp")`.
- Row lock to avoid race conditions (e.g. last available desk): `frappe.get_doc("Space", s, for_update=True)` or `frappe.db.get_value(..., for_update=True)`.

## Caching reads

`frappe.get_cached_doc`, `frappe.get_cached_value(dt, name, field)` — invalidated automatically when the doc is saved. Good for Settings, masters (Item, Space), not for fast-changing transactions. More in `frappe-performance`.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| `frappe.get_all` in user-facing APIs | `frappe.get_list` |
| `get_doc` just to read one field | `db.get_value` |
| `get_doc` / `get_value` inside loops | one query with `in` / join |
| `frappe.db.sql(f"...{x}...")` | qb or `%(x)s` |
| `frappe.db.set_value` on fields with business validation | `doc.save()` |
| `frappe.db.commit()` in request code | let Frappe commit |
| `fields=["*"]` on big tables | explicit fields |
| `limit_page_length=0` in request paths | pagination |
