---
name: frappe-background-jobs
description: Run work outside the web request in Frappe/ERPNext — scheduler_events (hourly/daily/cron, *_long variants), frappe.enqueue options (queue, timeout, job_id, deduplicate, enqueue_after_commit, at_front), enqueue_doc for document methods, batching and committing in long jobs, progress via realtime, retries, monitoring (RQ Job, Scheduled Job Log, Error Log) and worker/queue configuration. Use for anything slow, scheduled, bulk, or integration-related, and when jobs don't run, run twice or time out.
---

# Background jobs & scheduler

> **TL;DR:** Request = fast. Anything slow, external or bulk → `frappe.enqueue(..., enqueue_after_commit=True)`. Scheduled work → `scheduler_events` handlers that stay short and enqueue the heavy part. Make every job safe to run twice.

## enqueue

```python
frappe.enqueue(
    "my_app.billing.statements.generate_for_tenant",   # dotted path (or a function object)
    queue="long",                  # short | default | long
    timeout=1800,                  # seconds; default depends on queue (short 300, default 300, long 1500)
    job_id=f"statement::{tenant}::{month}",
    deduplicate=True,              # with job_id: skip if same job is queued/running
    enqueue_after_commit=True,     # only enqueue if the current transaction commits
    tenant=tenant, month=month,    # kwargs passed to the function
)

# document method
frappe.enqueue_doc("Contract", name, "rebuild_schedule", queue="short", timeout=600)
```

- **`enqueue_after_commit=True`** whenever you enqueue from a save/submit — otherwise the job may run before the data exists, or for data that was rolled back.
- The job runs as the user who enqueued it (session user is set) — permissions apply to `get_list`/`check_permission` inside.
- `now=True` runs the job inline (handy in tests and console debugging).

## Scheduler

```python
# hooks.py
scheduler_events = {
    "daily": ["my_app.contracts.tasks.mark_expired"],
    "daily_long": ["my_app.reports.tasks.rebuild_occupancy_snapshot"],
    "cron": {"0 6 * * *": ["my_app.contracts.tasks.send_expiry_reminders"]},
}
```

- Keys: `all`, `hourly`, `daily`, `weekly`, `monthly`, `hourly_long`, `daily_long`, `weekly_long`, `monthly_long`, `cron`.
- Cron times use the **system time zone** (System Settings).
- After editing, `bench --site x migrate` to sync **Scheduled Job Type** records; check **Scheduled Job Log**.
- Scheduler must be enabled: `bench --site x enable-scheduler`; `bench --site x doctor` shows status. Maintenance mode pauses it.
- Handlers take no arguments.

## Long job template (batch + commit + progress)

```python
import frappe
from frappe.utils import today

BATCH = 500

def mark_expired():
    names = frappe.get_all("Contract", filters={"status": "Active", "end_date": ["<", today()]}, pluck="name")
    total = len(names)
    for i in range(0, total, BATCH):
        for name in names[i:i + BATCH]:
            try:
                doc = frappe.get_doc("Contract", name)
                doc.status = "Expired"
                doc.save(ignore_permissions=True)     # system job: no user context
            except Exception:
                frappe.log_error(title=f"Expire contract failed: {name}")
        frappe.db.commit()                            # allowed in background jobs
        frappe.publish_realtime("expire_progress", {"done": min(i + BATCH, total), "total": total},
                                user="Administrator")
```

Rules: commit per batch (not per row, not once at the end of 100k rows); catch per-record errors so one bad record doesn't stop the run; log with `frappe.log_error`.

## Idempotency & retries

- Design jobs as "make the state correct" (e.g. set status from dates) rather than "add one more" — then rerunning is harmless.
- Use `job_id` + `deduplicate=True` to avoid parallel duplicates.
- Retries: store `attempts` / `next_retry` on a record and let a cron job re-enqueue due items (pattern in `frappe-integrations`). Don't `time.sleep` in workers.

## Queues & workers

| Queue | Use |
|---|---|
| `short` | user-triggered, < 1 min (send one email, sync one contract) |
| `default` | general |
| `long` | reports, imports, monthly runs |

Production runs separate worker processes per queue (supervisor/systemd). Custom queues + timeouts: `common_site_config.json` → `"workers": {"device_sync": {"timeout": 600}}`, then `frappe.enqueue(..., queue="device_sync")` and run a worker for it (`bench worker --queue device_sync`).

## Monitoring & debugging

- **RQ Job** list (`/app/rq-job`): queued/started/failed jobs, exceptions.
- **Scheduled Job Log**: each scheduler run, status, error.
- **Error Log**: everything you `frappe.log_error`.
- `bench --site x show-pending-jobs`, `bench --site x purge-jobs` (careful), `bench doctor`.
- Job not running → workers up? Redis queue reachable? correct queue name? scheduler enabled? site in maintenance mode?

## Anti-patterns

| ❌ | ✅ |
|---|---|
| Heavy loop inside the scheduler handler on `all` | enqueue to `long`, run daily/cron |
| `enqueue` from `validate`/`on_submit` without `enqueue_after_commit` | `enqueue_after_commit=True` |
| One commit after 100k changes (or one per row) | commit per batch |
| Passing whole docs as kwargs | pass names; reload inside the job |
| No `timeout` for long work | set `timeout` and the right queue |
| `time.sleep` retry loops in workers | scheduled retry |
| Job that isn't safe to run twice | idempotent "desired state" design |
