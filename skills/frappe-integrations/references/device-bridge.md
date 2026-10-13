# On-site bridge agent (devices on a private LAN)

Use when Frappe runs in the cloud/datacenter and devices (door controllers, biometric terminals, printers, scales) sit on a site LAN without inbound access.

```
[Frappe]  <── HTTPS (outbound from site) ──  [Bridge agent @ site]  ── LAN/SDK ──>  [Devices]
```

## Frappe side

DocTypes:
- `Device` — site, IP, serial, model, time zone, `last_seen`, `status`.
- `Device Command` — device, command (`upsert_user`, `delete_user`, `open_door`, `sync_time`), payload JSON, status (`Queued/Sent/Done/Failed`), attempts, error, `idempotency_key` (unique).
- `Access Event` — device, event_id, pin, time (UTC), direction, result. **Unique (device, event_id).**

API (`my_app/api/v1/bridge.py`, called by the agent with an API-key user that has only the `Device Bridge` role):

```python
@frappe.whitelist(methods=["GET"])
def pull_commands(site: str, limit: int = 50) -> list[dict]:
    frappe.only_for("Device Bridge")
    return frappe.get_all("Device Command",
        filters={"site": site, "status": "Queued"},
        fields=["name", "device", "command", "payload", "idempotency_key"],
        order_by="creation asc", limit=min(limit, 200))

@frappe.whitelist(methods=["POST"])
def report_results(results: list[dict]) -> dict:
    frappe.only_for("Device Bridge")
    for r in results:
        frappe.db.set_value("Device Command", r["name"],
            {"status": "Done" if r["ok"] else "Failed", "error": r.get("error")})
    return {"ok": True}

@frappe.whitelist(methods=["POST"])
def push_events(device: str, events: list[dict]) -> dict:
    frappe.only_for("Device Bridge")
    inserted = 0
    for e in events:
        if frappe.db.exists("Access Event", {"device": device, "event_id": e["event_id"]}):
            continue                                  # idempotent
        frappe.get_doc({"doctype": "Access Event", "device": device, **e}).insert(ignore_permissions=True)
        inserted += 1
    frappe.db.set_value("Device", device, "last_seen", frappe.utils.now())
    frappe.enqueue("my_app.access.quota.recompute_for_events", device=device, enqueue_after_commit=True)
    return {"inserted": inserted}
```

(`get_all` is fine here: role-gated system endpoint, not user-facing data.)

## Agent side (Python service on a small PC / VM at site)

- Loop every 5–10s: `pull_commands` → apply to device → `report_results`.
- Loop every 30–60s: read new device events since last stored cursor → `push_events` in batches of ≤500.
- Store cursor + pending results locally (SQLite) so a network outage loses nothing; resend on reconnect.
- Run as a systemd/Windows service, auto-restart, log rotation; heartbeat updates `Device.last_seen`.
- Device protocol: use the vendor SDK or a maintained library for that device family; isolate it behind one `DeviceDriver` interface so other brands can be added.

## Monitoring

- Scheduler job: alert if any `Device.last_seen` older than 10 min or `Device Command` stuck `Queued` > 15 min.
- Dashboard: commands per status, failures per device, events imported per hour.
