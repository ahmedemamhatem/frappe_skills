---
name: frappe-integrations
description: Patterns for connecting Frappe/ERPNext to hardware and external systems — access-control devices (ZKTeco and similar), payment gateways, SMS/WhatsApp, accounting/government APIs, and inbound/outbound webhooks. Covers settings DocTypes for credentials, sync jobs with retries and idempotency, integration logs, on-prem bridge agents for LAN devices, and reconciliation. Use when writing any code that talks to a device, a third-party API, or receives callbacks.
---

# Integrations (devices, APIs, webhooks)

> **TL;DR:** Every integration = **Settings DocType** (credentials, encrypted) + **Log DocType** (every request/response) + **a client class** (one place that talks to the outside) + **background jobs** with retries + **idempotent** handlers + a **reconciliation** job. Never call an external system inside a user's save request.

## Decide the direction first

| Pattern | Use when | Frappe pieces |
|---|---|---|
| Outbound on change | ERP change must reach another system (add user to door, send SMS) | `doc_events` → `frappe.enqueue(..., enqueue_after_commit=True)` → client |
| Outbound, no code | simple JSON POST on save/submit | **Webhook** DocType (config only) |
| Inbound callback | system calls you (payment result, device push) | `allow_guest` whitelisted receiver + signature check + log + enqueue |
| Pull / poll | device or API has no push (attendance logs) | scheduler job (`cron`) with cursor stored in Settings |
| Device on a private LAN | ERP is in the cloud, device isn't reachable | small **bridge agent** on-site that calls *your* API (outbound only from the LAN) |

## Standard building blocks

### 1. Settings (Single DocType)
`ZK Settings`: `enabled`, `base_url`, `api_key` (**Password** field), `timeout`, `last_sync_cursor`, `default_access_group`.
Read secrets with `settings.get_password("api_key")`. Never put credentials in `hooks.py`, `site_config.json` committed to git, or code.

### 2. Integration Log
Reuse Frappe's **Integration Request** DocType (fields: `integration_request_service`, `request_data`, `output`, `error`, `status`, `reference_doctype/name`) or create your own `Device Sync Log`. Log **every** call: payload (mask secrets), response, status, duration, reference doc.

### 3. Client class — the only code that touches the wire

```python
# my_app/integrations/zk/client.py
import frappe, requests

class ZKClient:
    def __init__(self):
        s = frappe.get_cached_doc("ZK Settings")
        if not s.enabled:
            frappe.throw("ZK integration is disabled")
        self.base = s.base_url.rstrip("/")
        self.timeout = s.timeout or 10
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {s.get_password('api_key')}"

    def upsert_user(self, pin: str, name: str, card: str | None, valid_from, valid_to, groups: list[str]):
        return self._post("/users", {"pin": pin, "name": name, "card": card,
                                     "valid_from": str(valid_from), "valid_to": str(valid_to),
                                     "groups": groups})

    def delete_user(self, pin: str):
        return self._post(f"/users/{pin}/delete", {})

    def _post(self, path, data):
        r = self.session.post(self.base + path, json=data, timeout=self.timeout)
        r.raise_for_status()
        return r.json()
```

### 4. Enqueue from document events (never inline)

```python
# hooks.py
doc_events = {"Contract": {"on_submit": "my_app.integrations.zk.sync.on_contract_change",
                           "on_cancel": "my_app.integrations.zk.sync.on_contract_change",
                           "on_update_after_submit": "my_app.integrations.zk.sync.on_contract_change"}}
```

```python
# my_app/integrations/zk/sync.py
def on_contract_change(doc, method=None):
    frappe.enqueue(
        "my_app.integrations.zk.sync.sync_contract_access",
        contract=doc.name, queue="short",
        job_id=f"zk_access::{doc.name}", deduplicate=True,
        enqueue_after_commit=True,           # only if the save actually commits
    )
```

### 5. Idempotent job with retry

```python
import requests
from frappe.utils import now_datetime, add_to_date

MAX_ATTEMPTS = 6

def sync_contract_access(contract: str):
    doc = frappe.get_doc("Contract", contract)
    desired = desired_access_state(doc)      # your pure function: what *should* the device have?
    log = frappe.get_doc({"doctype": "Integration Request", "integration_request_service": "ZK",
                          "reference_doctype": "Contract", "reference_docname": contract,
                          "request_data": frappe.as_json(desired), "status": "Queued"}
                         ).insert(ignore_permissions=True)
    try:
        client = ZKClient()
        if desired["active"]:
            client.upsert_user(**desired["user"])
        else:
            client.delete_user(desired["user"]["pin"])
        log.db_set("status", "Completed")
        doc.db_set({"access_sync_status": "Synced", "access_sync_attempts": 0,
                    "access_synced_on": now_datetime()})
    except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
        log.db_set({"status": "Failed", "error": str(e)})
        attempts = (doc.access_sync_attempts or 0) + 1
        doc.db_set({"access_sync_status": "Retry" if attempts < MAX_ATTEMPTS else "Failed",
                    "access_sync_attempts": attempts,
                    # exponential backoff: 2, 4, 8, 16, 32 min
                    "access_next_retry": add_to_date(now_datetime(), minutes=2 ** attempts)})
        if attempts >= MAX_ATTEMPTS:
            frappe.log_error(title=f"ZK sync gave up: {contract}")   # + notify ops
```

Retries are picked up by a scheduler job instead of sleeping in a worker:

```python
# hooks.py → scheduler_events = {"cron": {"*/5 * * * *": ["my_app.integrations.zk.sync.retry_due"]}}
def retry_due():
    for name in frappe.get_all("Contract", pluck="name", limit=200, filters={
            "access_sync_status": "Retry", "access_next_retry": ["<=", now_datetime()]}):
        frappe.enqueue("my_app.integrations.zk.sync.sync_contract_access", contract=name,
                       queue="short", job_id=f"zk_access::{name}", deduplicate=True)
```

Key idea: the job pushes the **desired state** (upsert/delete), not "add one more day". Running it twice gives the same result — that's what makes retries safe. (Fields `access_sync_status/attempts/next_retry/synced_on` are Custom Fields on Contract; put them on a separate sync-state DocType if many systems sync the same doc.)

### 6. Reconciliation (the safety net)
Nightly scheduler job compares ERP truth vs device/API state and fixes drift (expired tenants still on the door, paid invoices not marked). Integrations *will* miss events; reconciliation catches it.

```python
scheduler_events = {"cron": {"15 2 * * *": ["my_app.integrations.zk.reconcile.run"]}}
```

### 7. Inbound webhook receiver

```python
@frappe.whitelist(allow_guest=True, methods=["POST"])
def payment_callback():
    raw = frappe.request.get_data()
    verify_signature(raw, frappe.get_request_header("X-Signature"))   # HMAC, constant-time compare
    payload = frappe.parse_json(raw)
    log = frappe.get_doc({"doctype": "Integration Request", "integration_request_service": "Gateway",
                          "request_data": raw.decode(), "status": "Queued"}).insert(ignore_permissions=True)
    frappe.enqueue("my_app.integrations.gateway.process", log=log.name, enqueue_after_commit=True)
    return {"ok": True}                  # answer fast; process async
```

Verify signature → log → enqueue → return 200 quickly. Process idempotently (dedupe on provider's event id).

## Access-control devices specifically (ZKTeco & similar)

- **Prefer the vendor's server API** (e.g. ZKBio/BioTime-style central software) over talking to each door controller; the server handles device fan-out and offline devices.
- If you must talk to devices directly on a LAN, run a **bridge agent** on-site (small Python service) that: pulls pending commands from your Frappe API, applies them with the device SDK/protocol library, posts results + attendance/door logs back. Frappe never needs inbound access to the LAN.
- Model: `Access Credential` (pin, card, face/fingerprint enrolled flag) linked to `Customer/Contact`; `Access Group` ↔ doors/zones; `Contract` → desired groups + validity window + entry quota.
- **Entry quotas** (N days / N entries): count from imported door events (`Access Event` DocType, unique on device_id + event_id) and recompute desired state after each import; when quota is used up, the next sync removes access.
- Always set **validity dates on the device** too (if supported) so access expires even if ERP sync fails.
- Store device time zone; import events in UTC + device TZ and convert once.

See `references/device-bridge.md` for the bridge agent design and `references/checklist.md` before go-live.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| `requests.post(...)` inside `validate`/`on_submit` | enqueue after commit |
| No timeout on HTTP calls | `timeout=` always (worker hangs otherwise) |
| Credentials in code / `hooks.py` | Password field in Settings, `get_password()` |
| "Add one day of access" style incremental commands | push full desired state (idempotent) |
| Swallowing errors | Integration log + `frappe.log_error` + ops notification |
| Trusting inbound webhooks without signature | HMAC/IP allowlist + replay protection |
| No reconciliation | nightly diff & fix job |
| Pulling 100k device events in one request | cursor + batch + commit per batch |
