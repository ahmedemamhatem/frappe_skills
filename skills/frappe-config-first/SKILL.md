---
name: frappe-config-first
description: Before writing any new Frappe/ERPNext code (DocType, controller method, hook, Client or Server Script, report, override), check whether configuration, a built-in feature, an installed app or a few lines in existing code already does it. Also used to audit a diff or a whole app for avoidable custom code. Includes an optional PostToolUse guard script that flags risky patterns (raw SQL, DB calls in loops, unchecked whitelisted writes, guest endpoints without rate limits, commits in request code) on every edit. Use at the start of any feature, and when asked to slim down, audit or simplify an app.
---

# Config first, code last

> **TL;DR:** Frappe ships most business behaviour as **configuration**. Every line of custom code is something to test, review and re-check on every upgrade. Walk the questions below top to bottom and stop at the first "yes".

## The questions

1. **Is it needed at all?** Maybe a standard report, list view filter, saved report or workspace shortcut already answers it.
2. **Is it configuration?**

| Requirement sounds like… | Use (no code) |
|---|---|
| "notify X when Y happens / N days before Z" | **Notification** (event, days before/after a date field, condition, Jinja message, email/system/SMS) |
| "approval / states / only managers can move to Approved" | **Workflow** |
| "assign to someone automatically / round robin" | **Assignment Rule** |
| "add a field / change label / make mandatory / hide" | **Custom Field**, **Property Setter** (Customize Form) |
| "fetch tenant name from contract" | `fetch_from` on the field |
| "show field only when…" / "mandatory when…" | `depends_on`, `mandatory_depends_on`, `read_only_depends_on` |
| "auto-number like CON-2026-0001" | Naming Series / autoname format |
| "who can see what" | Role Permission Manager, User Permissions, Permission Levels |
| "public form for leads/bookings" | **Web Form** |
| "printed contract / invoice layout" | **Print Format** (Jinja or Print Format Builder) |
| "send data to another system on save" | **Webhook** DocType |
| "auto-repeat invoice monthly" | **Auto Repeat** |
| "KPI on a dashboard" | **Number Card**, **Dashboard Chart**, Workspace |
| "simple report, few joins" | **Report Builder** saved report, or **Query Report** |
| "email to doc" / inbox | Email Account + "Append To" |

3. **Does an installed app already have it?** `bench --site <site> list-apps`, then search `*/doctype/`, `*/report/`, `hooks.py` across `apps/`. ERPNext, HRMS, Payments, CRM, Helpdesk, Insights cover a lot (Subscription, Payment Request, Pricing Rule, Asset, Project, Timesheet…).
4. **Is there a framework helper?** `frappe.utils` (dates, money, `flt`, `cint`, `getdate`, `add_months`, `date_diff`), `frappe.model.mapper.get_mapped_doc` (make X from Y), `frappe.share`, `frappe.desk.form.assign_to`, `frappe.sendmail`, `frappe.qb`.
5. **Can an existing file take it?** One more `doc_events` entry, one more method in the existing controller, one more handler in the existing form script — instead of a new module/file.
6. **Only then** write the smallest code: a method in the DocType's controller, or a function in `services/` if it spans DocTypes.

When you skip a rung on purpose (e.g. Notification can't express the condition), say why in the PR or a one-line comment — so the next reviewer doesn't re-ask.

## Audit mode

When asked to audit a diff or an app, report each finding as:

```
[file:line] what was written → what could replace it (rung #) → effort/risk of switching
```

Typical finds:
- `on_submit` hook that only sends an email → Notification.
- `validate()` that only sets a field from a linked doc → `fetch_from`.
- Client Script that only toggles visibility → `depends_on`.
- Custom status juggling across buttons → Workflow.
- Custom DocType duplicating Customer/Contact/Item → reuse + Custom Fields.
- Scheduled job that creates monthly invoices → Auto Repeat / ERPNext Subscription.
- Python report looping over docs → Query Report or one aggregated query.

Then also run the anti-pattern tables of the matching skills (`frappe-controllers`, `frappe-database`, `frappe-api-design`, `frappe-security`, `frappe-performance`) for a combined report.

## Optional automatic guard (hook)

`scripts/frappe_guard.py` is a fast regex check you can wire as a Claude Code `PostToolUse` hook. After every Write/Edit of a `.py` file under `apps/`, it warns about:

- `frappe.db.sql(` with an f-string or `.format(` (injection risk) and plain `frappe.db.sql(` (prefer qb/ORM)
- `get_doc` / `get_value` / `db.sql` / `db.exists` inside a `for`/`while` body (N+1)
- `@frappe.whitelist` functions that `.save()/.submit()/.cancel()/.delete()/.insert()` with no permission check in the function
- `allow_guest=True` without `@rate_limit`
- `frappe.db.commit()` outside a background-job style module
- `ignore_permissions=True`

It only sees text in one file, so it misses N+1 through helper functions and can't judge business logic. Treat it as a cheap floor, not a review.

Wiring (in the project's `.claude/settings.json`; adjust the path to where the repo is cloned):

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Write|Edit",
        "hooks": [{ "type": "command",
                    "command": "python3 ~/frappe_skils/skills/frappe-config-first/scripts/frappe_guard.py" }] }
    ]
  }
}
```

The script reads the hook JSON from stdin, prints findings to stderr and exits `2` when there are warnings (so Claude sees them and can fix), `0` otherwise. Run its tests with `python3 -m unittest discover -s skills/frappe-config-first/scripts -p "test_*.py"`.
