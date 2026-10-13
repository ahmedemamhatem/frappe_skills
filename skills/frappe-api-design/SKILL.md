---
name: frappe-api-design
description: Design clean, versioned, permission-safe REST APIs on Frappe/ERPNext for React, mobile and third-party clients — module layout for whitelisted methods, typed and validated inputs, consistent response and error shapes, pagination, idempotency, rate limiting, and when to use /api/resource vs /api/method. Use when adding or reviewing any @frappe.whitelist endpoint that a frontend or external system will call, or when designing an API contract between backend and frontend teams. Covers v15 and v16 (/api/v2).
---

# Frappe API design

> **TL;DR:** Put every public endpoint in `my_app/api/v1/<resource>.py`, give it type hints, `methods=[...]`, an explicit permission check and an explicit response dict. Use `/api/resource` only for plain CRUD that the DocType's permissions already cover; anything with business meaning is a whitelisted method.

## When to use what

| Need | Use |
|---|---|
| Plain CRUD on a DocType, permissions = DocType perms | `/api/resource/<DocType>` (or `/api/v2/document/<DocType>` on v15+) — no code |
| Action with business rules (renew, check-in, approve, pay) | whitelisted method `POST /api/method/my_app.api.v1.contracts.renew` |
| Aggregated / dashboard data | whitelisted GET returning a shaped dict |
| External system pushes data to you | webhook receiver (see `frappe-integrations`) |
| You push data to an external system on change | Frappe **Webhook** DocType (config) or `doc_events` + background job |

## Layout

```
my_app/api/
├── __init__.py
├── v1/
│   ├── __init__.py
│   ├── contracts.py     # one module per resource
│   ├── access.py
│   └── _utils.py        # shared: paginate(), ok(), require_role()
```

Versioning = module path (`my_app.api.v1.*`). Breaking change → new `v2` module, keep `v1` until clients migrate. Never rename a released method.

## The endpoint template

```python
# my_app/api/v1/contracts.py
import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

@frappe.whitelist(methods=["POST"])
def renew(name: str, months: int = 12) -> dict:
    """Renew an active contract. Returns the new contract name."""
    if months not in (1, 3, 6, 12):
        frappe.throw(_("Months must be 1, 3, 6 or 12"), frappe.ValidationError)

    contract = frappe.get_doc("Contract", name)
    contract.check_permission("write")                 # 1. permission on the real doc

    if contract.status != "Active":
        frappe.throw(_("Only active contracts can be renewed"))

    new_name = contract.renew(months)                  # 2. logic lives in the controller
    return {"new_contract": new_name}                  # 3. explicit, minimal response
```

Rules:
1. **Type hints on every argument.** From v15, Frappe validates whitelisted-method arguments against their annotations and rejects wrong types. They also document the contract.
2. **`methods=["GET"]` for reads, `["POST"]` for writes** (also `PUT`/`DELETE` if you like REST semantics). Never write on GET.
3. **Permission check on the document**, not just "is logged in": `doc.check_permission("write")`, `frappe.has_permission(doctype, "read", doc, throw=True)`, or `frappe.only_for("Role")`.
4. **Thin endpoint, fat controller.** The endpoint parses, checks, calls a controller/service method, shapes the response. No business logic in `api/`.
5. **Explicit response.** Return a dict you built (`{"items": [...], "total": n}`), never `doc.as_dict()` of a whole document to an external client — it leaks internal fields.
6. **Errors via `frappe.throw` with the right exception class** — the HTTP status follows the class.

## Error → HTTP status

| Raise | Status | Use for |
|---|---|---|
| `frappe.ValidationError` (default `frappe.throw`) | 417 | bad input / business rule |
| `frappe.PermissionError` | 403 | not allowed |
| `frappe.DoesNotExistError` | 404 | missing record |
| `frappe.DuplicateEntryError` | 409 | unique conflict |
| `frappe.AuthenticationError` | 401 | not logged in / bad token |
| `frappe.RateLimitExceededError` | 429 | (raised by `@rate_limit`) |

Front end parses these once (see `frappe-react-frontend` → errors).

## Lists & pagination

```python
@frappe.whitelist(methods=["GET"])
def list_contracts(status: str | None = None, page: int = 0, page_size: int = 20) -> dict:
    page_size = min(page_size, 100)                    # cap
    filters = {"status": status} if status else {}
    items = frappe.get_list(                           # get_list = applies user perms
        "Contract",
        filters=filters,
        fields=["name", "tenant", "space", "status", "end_date"],
        order_by="modified desc",
        limit_start=page * page_size,
        limit_page_length=page_size,
    )
    total = frappe.db.count("Contract", filters)       # see note below
    return {"items": items, "page": page, "page_size": page_size, "total": total}
```

- `frappe.get_list` respects permissions; `frappe.get_all` **ignores them** — never use `get_all` for user-facing data.
- `frappe.db.count` ignores user permissions; when that matters use `len(frappe.get_list(..., pluck="name"))` for small sets or `frappe.get_list(..., fields=["count(name) as total"])`.
- Huge tables: keyset pagination (`modified < last_modified`) instead of offsets — see `frappe-performance`.

## Idempotency (payments, devices, retries)

Any POST a client may retry (mobile networks, device sync, payment callbacks) must be idempotent:

```python
@frappe.whitelist(methods=["POST"])
def record_payment(contract: str, amount: float, client_ref: str) -> dict:
    if existing := frappe.db.get_value("Payment Entry", {"reference_no": client_ref}, "name"):
        return {"payment_entry": existing, "duplicate": True}
    ...
```

Put a **unique** index on the reference field so two parallel requests can't both insert.

## Guest endpoints

```python
@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60)
def request_tour(email: str, phone: str, location: str) -> dict:
    ...
```

Guest = rate limit + strict validation + no internal data in responses + `ignore_permissions=True` only on the exact insert that needs it.

## API contract with the React team

Write it down per endpoint (or generate an OpenAPI/Postman collection from it):

```
POST /api/method/my_app.api.v1.contracts.renew
body: { name: string, months: 1|3|6|12 }
200:  { message: { new_contract: string } }
417:  validation message   403: no permission   404: not found
```

Frappe wraps return values in `{"message": ...}` — document that so the frontend reads `.message`.

## v15 vs v16

- `/api/v2/` exists from v15 (routes like `/api/v2/document/<DocType>/<name>` and `/api/v2/method/<path>`; responses use a `data` key instead of `message`). `/api/` (v1) still works on v16. Pick one per project, stay consistent, and test the exact response shape on your version before the frontend depends on it.
- v16 runs on Python 3.14: `X | None` unions and `type` aliases are fine; on v15 keep to syntax supported by the bench's Python (3.10+ supports `X | None`).

## References

- `references/patterns.md` — bulk endpoints, file responses, CSV export, long-running actions (enqueue + job status), API key users

## Anti-patterns

| ❌ | ✅ |
|---|---|
| `@frappe.whitelist()` with no `methods` doing writes | `methods=["POST"]` |
| `frappe.get_all` in a user-facing endpoint | `frappe.get_list` |
| `ignore_permissions=True` "to make it work" | fix the role permission / check the doc perm explicitly |
| `return doc` / `doc.as_dict()` to external clients | explicit dict of the fields the contract promises |
| Business logic inside `api/` | controller / service method, endpoint calls it |
| `frappe.db.sql(f"... {user_input} ...")` | `frappe.qb` or `%(param)s` placeholders |
| Endpoint names like `get_data2`, `test_api` | `v1.<resource>.<verb>` |
| Silent `try/except: pass` | `frappe.throw` the right class, `frappe.log_error` unexpected ones |
