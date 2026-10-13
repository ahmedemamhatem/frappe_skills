# Integration go-live checklist

- [ ] Credentials in a Settings DocType Password field; sandbox and production values separated per site.
- [ ] Every outbound HTTP call has `timeout=`.
- [ ] No external call inside a user request/transaction — all via `frappe.enqueue(..., enqueue_after_commit=True)`.
- [ ] Jobs are idempotent (desired-state or dedupe key) and safe to run twice.
- [ ] Retries with backoff and a max attempt count; final failure notifies a human.
- [ ] Every call logged (Integration Request or own log), secrets masked, retention policy (clear old logs via scheduler).
- [ ] Inbound webhooks: signature verified, replay protection (timestamp/event id), rate limited, return 200 fast.
- [ ] Reconciliation job exists and has been run against real data.
- [ ] Time zones: stored UTC, converted once; device clocks synced.
- [ ] Load test: expected peak (e.g. morning entry rush) × 3.
- [ ] Runbook: how to pause the integration (Settings `enabled` = 0), how to replay failed jobs, who gets alerts.
- [ ] Tests: client mocked (`unittest.mock.patch` on the client class) — see `frappe-testing`.
