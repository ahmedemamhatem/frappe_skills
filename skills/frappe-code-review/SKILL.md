---
name: frappe-code-review
description: Structured code review for Frappe/ERPNext + React pull requests — a severity-ranked checklist covering correctness, permissions/security, performance, data integrity, upgrade safety, API contracts, frontend quality and tests, with a fixed report format. Use when asked to review a PR, diff, branch or file in a Frappe app or its React frontend, before merging, or when self-reviewing generated code.
---

# Frappe + React code review

> **TL;DR:** Read the diff with the checklist below, report findings as **Blocker / Major / Minor / Nit** with file:line and a concrete fix. Blockers = security, data loss, broken upgrades, permission bypass. Don't pad the report with style nits that a linter would catch.

## Process

1. **Understand the change.** Read the PR description / ticket. What should happen? Which DocTypes, hooks, APIs, screens?
2. **Map the blast radius.** `git diff --stat`; note touched `hooks.py`, DocType JSON, patches, `api/`, `public/`, React `src/`.
3. **Walk the checklist** (below) for each touched area.
4. **Check tests exist** for new behaviour and for the bug being fixed.
5. **Write the report** in the format at the end.

If the `frappe-decision-ladder` skill is installed, also run its "is this code necessary / is there a config option" pass.

## Checklist

### 🔴 Security & permissions (Blocker if violated)
- [ ] Every `@frappe.whitelist` has `methods=[...]`, type-hinted args, and a **document-level** permission check (`check_permission`, `has_permission(..., throw=True)`, `only_for`).
- [ ] No `allow_guest=True` without rate limit + validation + minimal response.
- [ ] No `ignore_permissions=True` / `frappe.flags.ignore_permissions` unless justified in a comment and scoped to one call.
- [ ] `frappe.get_all` / `frappe.db.*` not used to return user-facing data (they skip permissions) → `frappe.get_list`.
- [ ] No SQL built with f-strings/`format` from input → `frappe.qb` or `%(x)s` params.
- [ ] No secrets in code, JSON fixtures, or the React bundle.
- [ ] Jinja/HTML output escaped (`frappe.utils.escape_html`, no `| safe` on user data); React: no `dangerouslySetInnerHTML` with server strings unless sanitized.
- [ ] File uploads of sensitive docs are private.

### 🔴 Data integrity & upgrade safety
- [ ] Schema changes are in DocType JSON (exported via Desk in developer mode), not hand-edited inconsistently; Custom Fields shipped as **fixtures** or created in `after_install`/patches.
- [ ] Renamed/removed fields have a **patch** that migrates data; patch registered in `patches.txt` under the right section (`[pre_model_sync]` / `[post_model_sync]`) and is idempotent.
- [ ] No core/ERPNext file modified — overrides via `override_doctype_class`, `doc_events`, `override_whitelisted_methods`, hooks.
- [ ] No `frappe.db.commit()` inside controllers/request code (breaks atomicity). Allowed only in long background jobs that commit per batch.
- [ ] Submitted documents aren't mutated except via `on_update_after_submit` / "Allow on Submit" fields.
- [ ] Naming series / autoname changes won't collide with existing records.

### 🟠 Performance
- [ ] No DB calls inside loops (`get_doc`/`get_value` per row) → fetch once with `get_all(..., filters={"name": ["in", names]})` or a join.
- [ ] Lists paginated; no `limit_page_length=0` on growing tables in request paths.
- [ ] New filter/sort columns on big tables have an index (`search_index` / `add_index` in patch).
- [ ] Slow work (external calls, PDF, emails to many, > ~2s) is `frappe.enqueue`d, `enqueue_after_commit=True` when triggered from a save.
- [ ] Cached reads use `frappe.get_cached_doc` / `frappe.cache` with proper invalidation.
- [ ] React: no request waterfalls on page load; lists use explicit `fields`; heavy routes lazy-loaded.

### 🟡 Correctness & design
- [ ] Logic is in the controller (or a service module), not in `api/` or Client Scripts duplicating server rules.
- [ ] Validation in `validate` (runs on every save), side effects in `on_submit`/`on_update` — not the other way round.
- [ ] Hooks event order respected (`before_validate` → `validate` → `before_save` → `on_update`, etc.).
- [ ] Translations: user-facing strings wrapped in `_()` (Python) / `__()` (JS) / i18n in React.
- [ ] Dates/times via `frappe.utils` (`getdate`, `now_datetime`, `add_days`), time zone aware; currency via `flt(..., precision)`.
- [ ] Errors: `frappe.throw(_("..."), ExcClass)` for users; `frappe.log_error` for unexpected failures; no bare `except: pass`.

### 🟡 API contract (if API changed)
- [ ] Backward compatible, or new version module (`api/v2`).
- [ ] Response shape documented and matches frontend types.
- [ ] Idempotent where clients may retry.

### 🟢 Frontend (React)
- [ ] API calls go through `src/api/*` typed wrappers.
- [ ] Loading, empty and error states handled; server error messages shown.
- [ ] No business rules/permissions decided only on the client.
- [ ] Accessibility basics: labels on inputs, buttons are `<button>`, keyboard reachable; RTL ok if Arabic is supported.
- [ ] `tsc --noEmit` and ESLint clean; no `any` in new API types.

### 🟢 Tests
- [ ] New behaviour and the fixed bug have tests (`frappe-testing`).
- [ ] Integrations mocked; tests don't depend on order or existing site data.

## Report format

```markdown
## Review: <PR title>

**Verdict:** Approve | Approve with changes | Request changes

### Blockers
1. `my_app/api/v1/contracts.py:42` — `renew()` has no permission check; any logged-in user can renew any contract.
   **Fix:** `contract.check_permission("write")` before `contract.renew()`.

### Major
1. ...

### Minor
1. ...

### Nits (optional, max 5)

### What's good
- One or two specific things worth keeping.

### Tests
- Missing: permission test for `renew` as a tenant user.
```

Rules for the report: every finding has a location, *why* it matters, and a concrete fix. Group repeats ("same issue in 4 places: a, b, c, d"). Don't report what linters (ruff/eslint/prettier) already enforce.
