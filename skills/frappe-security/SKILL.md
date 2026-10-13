---
name: frappe-security
description: Security hardening for Frappe/ERPNext apps and their React/portal frontends — permission design (roles, user permissions, permission hooks), safe whitelisted and guest endpoints, SQL injection, XSS, CSRF, file upload safety, secrets handling, API keys and OAuth, rate limiting, audit trails, and a pre-release security checklist. Use when designing roles/permissions, exposing data to portal/guest users or third parties, handling payments/ID documents/personal data, or auditing an app before go-live.
---

# Frappe security

> **TL;DR:** The server is the only security boundary. Every endpoint checks permission on the **actual document**, every query is parameterised, every guest endpoint is rate-limited and returns a hand-built response, secrets live in Password fields, and sensitive files are private.

## Permission model (design it before writing code)

1. **Roles** = what a person does (`Space Manager`, `Accountant`, `Tenant`, `Device Bridge`). Create custom roles; don't hand out `System Manager`.
2. **Role Permissions** (DocType perms, per role: read/write/create/submit/cancel/delete/report/export/share) — configured, shipped as fixtures or in DocType JSON.
3. **User Permissions** = row-level restriction ("this user only sees Location = Mall A"). Applies via Link fields.
4. **`permission_query_conditions` + `has_permission` hooks** for rules user permissions can't express ("tenant sees only contracts where `tenant` = their Customer").

```python
# hooks.py
permission_query_conditions = {"Contract": "my_app.permissions.contract_query"}
has_permission = {"Contract": "my_app.permissions.contract_has_permission"}
```

```python
# my_app/permissions.py
import frappe

def _tenant_customer(user):
    return frappe.db.get_value("Contact", {"user": user}, "customer")   # adjust to your link

def contract_query(user):
    if "Tenant" not in frappe.get_roles(user) or "Space Manager" in frappe.get_roles(user):
        return ""
    customer = _tenant_customer(user)
    return f"`tabContract`.tenant = {frappe.db.escape(customer)}" if customer else "1=0"

def contract_has_permission(doc, ptype, user):
    if "Tenant" in frappe.get_roles(user) and "Space Manager" not in frappe.get_roles(user):
        return doc.tenant == _tenant_customer(user)
    return None   # None = fall back to standard checks
```

Always `frappe.db.escape()` values inside query conditions. Return `"1=0"` (deny) rather than `""` (allow all) when the mapping is missing.

## Endpoint rules

| Rule | How |
|---|---|
| Method restriction | `@frappe.whitelist(methods=["POST"])` for writes |
| Typed input | type hints (validated on v15+), plus range/enum checks |
| Doc-level permission | `doc.check_permission("write")` / `frappe.has_permission(dt, ptype, doc, throw=True)` |
| Role gate | `frappe.only_for(["Accounts Manager"])` |
| User-facing lists | `frappe.get_list` (respects perms), never `get_all`/raw SQL |
| Response | explicit dict; no password/secret/internal fields |
| Guest | `allow_guest=True` + `@rate_limit(limit=..., seconds=...)` + captcha for public forms + no data leakage in errors |

## Injection & XSS

- SQL: `frappe.qb` or `frappe.db.sql("... where name = %(name)s", {"name": x})`. **Never** f-string user input into SQL, `order_by`, or field lists — whitelist sortable fields:

```python
ALLOWED_SORT = {"modified", "end_date", "tenant"}
order_by = f"{sort if sort in ALLOWED_SORT else 'modified'} desc"
```

- HTML/Jinja: autoescape is on in templates — don't use `| safe` on user content. In Python building HTML: `frappe.utils.escape_html`. Text Editor fields are sanitised on save, but be careful rendering them in emails/print formats.
- React: avoid `dangerouslySetInnerHTML`; if you must render server HTML (Text Editor content), sanitise with DOMPurify.
- `frappe.safe_eval` / Server Scripts: never `eval`/`exec` user input.

## CSRF & sessions

- Cookie-session SPAs send `X-Frappe-CSRF-Token` (see `frappe-react-frontend`). Never set `ignore_csrf` outside a local dev site.
- Session expiry: System Settings → `session_expiry`. Force logout on role change for sensitive roles.
- Enable 2FA (System Settings) for staff roles with financial access.

## Secrets & keys

- Credentials → **Password** fieldtype in a Settings DocType, read via `doc.get_password("field")`. Stored encrypted with the site's `encryption_key` — back up `site_config.json` securely (losing it = losing secrets).
- Integration access → dedicated user per integration + narrow role + API key/secret; rotate when staff leave.
- External apps acting for users → **OAuth Client** (Authorization Code + PKCE), not shared API keys.
- Nothing secret in git, fixtures, logs (mask before `frappe.log_error`), or frontend bundles.

## Files

- Sensitive uploads (IDs, contracts, invoices) → `is_private=1`. Private files are served only to users who can read the attached document.
- Restrict types: System Settings → *Allowed File Extensions*; validate size/type again in your upload handler.
- Never build file paths from user input (`../` traversal); use `frappe.get_doc("File", ...)` APIs.

## Audit & personal data

- `track_changes` on important DocTypes (Version log); `track_views` where reading matters (ID documents).
- Access logs: Frappe's Access Log for exports/prints of sensitive docs.
- Personal data: Frappe has **Personal Data Deletion Request** / **Personal Data Download Request** flows — wire your custom DocTypes into `user_data_fields` in `hooks.py` so they're covered.
- Saudi PDPL / GDPR-style obligations: know which DocTypes hold personal data, retention, and who can export.

## Pre-release checklist

- [ ] Role matrix documented (role × DocType × ptype) and matches fixtures.
- [ ] Logged in as each role (incl. Tenant/portal) and tried to read/write others' records via `/api/resource/...` directly.
- [ ] `grep -rn "allow_guest" my_app` — each one rate-limited and reviewed.
- [ ] `grep -rn "ignore_permissions" my_app` — each one justified.
- [ ] `grep -rnE "db\.sql\(f|\.format\(" my_app` — no interpolated SQL.
- [ ] No secrets in repo (`git log -p | grep -i "secret\|api_key\|password"` sanity check, or gitleaks in CI).
- [ ] Sensitive file fields private; export/print permissions restricted.
- [ ] Production: `developer_mode` 0, `ignore_csrf` absent, HTTPS only, admin password strong, 2FA on admins.
- [ ] Dependency audit: `pip-audit` (bench env) and `yarn audit`/`npm audit` for the SPA.
