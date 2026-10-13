---
name: frappe-performance
description: Diagnose and fix performance problems in Frappe/ERPNext apps — slow forms, list views, reports, APIs and background jobs. Covers profiling (recorder, slow query log, EXPLAIN), N+1 elimination, query builder and indexes, caching with frappe.cache and get_cached_doc, keyset pagination, batching large jobs, worker/queue tuning, and React-side performance. Use when something is slow, before shipping features on large tables, or when reviewing code that loops over records.
---

# Frappe performance

> **TL;DR:** Measure first (Recorder / slow query log), then fix in this order: **N+1 queries → missing indexes → over-fetching → work that belongs in a background job → caching.** Most Frappe slowness is one of the first three.

## 1. Measure

| Tool | Use |
|---|---|
| **Recorder** (Desk → `/app/recorder`, start, reproduce, stop) | every SQL query of a request with duration + stack — finds N+1 instantly |
| `frappe.db.sql(..., debug=True)` / `explain=True` | print query / EXPLAIN in dev |
| MariaDB slow query log (`long_query_time = 1`) | production hotspots |
| `bench --site x console` + `%timeit` | micro-benchmarks |
| RQ dashboard / `/app/rq-job` | queue backlog, failed jobs, job durations |
| Browser DevTools network + React Profiler | frontend waterfalls / re-renders |

Write down the baseline (ms, query count) before changing anything.

## 2. Kill N+1

```python
# ❌ 1 + N queries
for c in frappe.get_all("Contract", filters={"status": "Active"}, pluck="name"):
    doc = frappe.get_doc("Contract", c)
    tenant_name = frappe.db.get_value("Customer", doc.tenant, "customer_name")

# ✅ 1 query with a join
Contract, Customer = frappe.qb.DocType("Contract"), frappe.qb.DocType("Customer")
rows = (frappe.qb.from_(Contract)
        .join(Customer).on(Customer.name == Contract.tenant)
        .select(Contract.name, Contract.end_date, Customer.customer_name)
        .where(Contract.status == "Active")
        .run(as_dict=True))

# ✅ or 2 queries + dict lookup
contracts = frappe.get_all("Contract", filters={"status": "Active"}, fields=["name", "tenant", "end_date"])
names = {c.tenant for c in contracts}
tenant_map = dict(frappe.get_all("Customer", filters={"name": ["in", list(names)]},
                                 fields=["name", "customer_name"], as_list=True))
```

Also N+1 in disguise: `doc.save()` in a loop (each save = validate + hooks + many queries). For bulk changes where hooks aren't needed: `frappe.db.set_value` or a single `frappe.qb.update(...)`; where hooks *are* needed: enqueue in batches.

## 3. Indexes

- Fields used in filters / `order by` on big tables (> ~50k rows): tick **Search Index** in the DocType field, or add composite indexes in a patch:

```python
def execute():
    frappe.db.add_index("Access Event", ["device", "event_time"], index_name="device_time_idx")
```

- `frappe.db.add_unique("Access Event", ["device", "event_id"])` for dedupe keys (also protects integrity).
- Check with `EXPLAIN` — look for `type: ALL` (full scan) on large tables.
- Don't index everything: every index slows inserts.

## 4. Fetch less

- `fields=[...]` explicit; never `fields=["*"]` in hot paths.
- `pluck="name"` when you need one column.
- `frappe.db.get_value(dt, name, [f1, f2], as_dict=True)` instead of `get_doc` when you only read 2 fields.
- `frappe.db.exists` / `frappe.db.count` instead of loading lists to check presence/size.
- **Keyset pagination** for deep pages / infinite scroll:

```python
rows = frappe.get_all("Access Event", fields=["name", "event_time", "pin"],
    filters={"event_time": ["<", last_seen_time]} if last_seen_time else {},
    order_by="event_time desc", limit=100)
```

## 5. Background jobs

- Anything > ~1–2s or external: `frappe.enqueue(method, queue="short|default|long", timeout=..., job_id=..., deduplicate=True)`.
- Large data jobs: process in **batches of 500–1000**, `frappe.db.commit()` after each batch (allowed in jobs), publish progress.
- Queue choice: `short` for user-triggered quick tasks, `default`, `long` for reports/imports. Configure workers per queue in `common_site_config.json` → `workers` (and run enough `bench worker` processes).
- Scheduler jobs must be short; they should *enqueue* heavy work, not do it.

## 6. Caching

```python
settings = frappe.get_cached_doc("ZK Settings")            # auto-invalidated on save

def get_space_price(space: str) -> float:
    key = f"space_price::{space}"
    if (v := frappe.cache.get_value(key)) is not None:      # v15+: frappe.cache is the client
        return v
    v = compute_price(space)
    frappe.cache.set_value(key, v, expires_in_sec=600)
    return v

# invalidate on change (hooks.py doc_events → on_update)
def clear_space_price(doc, method=None):
    frappe.cache.delete_value(f"space_price::{doc.name}")
```

- `@redis_cache(ttl=600)` (`from frappe.utils.caching import redis_cache`) for pure, cacheable reads; pass `user=True` when the result depends on the current user.
- `@site_cache` / `@request_cache` (same module) for per-process / per-request memoization.
- Never cache permission-dependent results under a key without the user in it.

## 7. Reports & dashboards

- Script Reports: one aggregated SQL/qb query, not Python loops over docs. Add `prepared_report` for very heavy ones (runs in background, cached).
- Number Cards / Dashboard Charts: use their built-in caching / time intervals instead of custom APIs on every page load.

## 8. React side

- Parallel, not waterfall: fire independent `useFrappeGetCall`s together; or one "page data" endpoint returning everything a screen needs.
- `swrConfig` `dedupingInterval` + `revalidateOnFocus: false` on heavy screens.
- Virtualize long tables (TanStack Virtual); paginate on the server.
- Code-split routes with `lazy()`; check bundle with `vite build --mode production` + `rollup-plugin-visualizer`.

## v15 vs v16

Same tools and APIs. v16 on Python 3.14 is generally faster per request; don't rely on it to fix N+1. `frappe.cache` (object) is the API on both; old `frappe.cache()` call style is legacy.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| `get_doc` in a loop | join / `in` filter + dict |
| `doc.save()` × 10,000 in a request | batch job, or `set_value`/`qb.update` when hooks not needed |
| `limit_page_length=0` on growing tables | paginate / aggregate in SQL |
| Heavy work in scheduler handler | scheduler enqueues |
| Caching permission-filtered data globally | include user/role in key, or don't cache |
| Guessing | Recorder + EXPLAIN |
