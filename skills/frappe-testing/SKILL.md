---
name: frappe-testing
description: Write and run automated tests for Frappe/ERPNext custom apps and their React frontends — backend integration/unit tests with FrappeTestCase (v15) and IntegrationTestCase/UnitTestCase (v16), test records and factories, mocking integrations, testing permissions and whitelisted APIs, React tests with Vitest + Testing Library + MSW, and CI. Use when adding tests, fixing flaky tests, setting up a test site, or when a feature/bugfix needs coverage before merge.
---

# Testing Frappe apps

> **TL;DR:** Each DocType gets `test_<doctype>.py` next to it. Test **behaviour** (validation, permissions, API responses, side effects), not getters. Mock everything that leaves the server. Run on a dedicated test site in CI on every PR.

## Setup

```bash
bench new-site test.localhost --admin-password admin --mariadb-root-password ***   # once
bench --site test.localhost install-app erpnext my_app
bench --site test.localhost set-config allow_tests true
bench --site test.localhost run-tests --app my_app                     # whole app
bench --site test.localhost run-tests --module my_app.contracts.doctype.contract.test_contract
bench --site test.localhost run-tests --doctype "Contract" --failfast
```

Never run tests on a real company site — tests insert and roll back data and can leave records behind.

## Base classes (v15 vs v16)

| | v15 | v16 |
|---|---|---|
| DB-backed test | `from frappe.tests.utils import FrappeTestCase` | `from frappe.tests import IntegrationTestCase` |
| Pure logic, no DB | `unittest.TestCase` | `from frappe.tests import UnitTestCase` |
| Change user | `frappe.set_user("x@y.com")` (reset in `tearDown`) | same, or `from frappe.tests import set_user` → `with set_user("x@y.com"):` |

On v16 `FrappeTestCase` still imports (compat shim) but is deprecated — new tests should use the v16 classes.

Supporting both versions in one app: import with a fallback.

```python
try:
    from frappe.tests import IntegrationTestCase as BaseTestCase   # v16
except ImportError:
    from frappe.tests.utils import FrappeTestCase as BaseTestCase  # v15
```

Each test method runs inside a transaction that's rolled back afterwards, so tests don't see each other's data. Data created in `setUpClass` persists across the class — keep it minimal.

## What to test (priority order)

1. **Validation & business rules** — every `frappe.throw` path in `validate`/`before_submit`.
2. **Permissions** — a user *without* the role can't read/write; user permissions restrict lists.
3. **Whitelisted APIs** — input validation, response shape, permission errors.
4. **Side effects** — on submit: GL entries, child docs created, jobs enqueued, realtime published.
5. **Scheduler jobs & integrations** — with the external client mocked.
6. **Patches** — run the patch function on fixture data, assert result.

## Template

```python
# my_app/contracts/doctype/contract/test_contract.py
import frappe
from unittest.mock import patch
from frappe.utils import add_days, today
from my_app.tests.factories import make_customer, make_space, make_contract

class TestContract(BaseTestCase):
    def setUp(self):
        self.customer = make_customer()
        self.space = make_space()

    def test_end_before_start_rejected(self):
        c = make_contract(self.customer, self.space, start=today(), end=add_days(today(), -1), do_not_save=True)
        self.assertRaises(frappe.ValidationError, c.insert)

    def test_overlapping_contract_for_same_space_rejected(self):
        make_contract(self.customer, self.space, submit=True)
        with self.assertRaises(frappe.ValidationError):
            make_contract(make_customer(), self.space, submit=True)

    def test_submit_enqueues_access_sync(self):
        with patch("frappe.enqueue") as enqueue:
            make_contract(self.customer, self.space, submit=True)
        self.assertTrue(any("sync_contract_access" in str(c.args) for c in enqueue.call_args_list))

    def test_tenant_user_cannot_read_other_tenants_contract(self):
        other = make_contract(make_customer(), self.space, submit=True)
        frappe.set_user(make_portal_user(self.customer))
        try:
            self.assertFalse(frappe.has_permission("Contract", "read", other.name))
        finally:
            frappe.set_user("Administrator")
```

## Factories, not giant JSON fixtures

```python
# my_app/tests/factories.py
import frappe
from frappe.utils import add_months, today

def make_customer(**kw):
    return frappe.get_doc({"doctype": "Customer", "customer_name": kw.get("name") or frappe.generate_hash(length=8),
                           "customer_group": "All Customer Groups", "territory": "All Territories"}).insert()

def make_contract(customer, space, start=None, end=None, submit=False, do_not_save=False, **kw):
    doc = frappe.get_doc({"doctype": "Contract", "tenant": customer.name, "space": space.name,
                          "start_date": start or today(), "end_date": end or add_months(today(), 1), **kw})
    if do_not_save:
        return doc
    doc.insert()
    if submit:
        doc.submit()
    return doc
```

Random names (`frappe.generate_hash`) avoid collisions between tests.

## Mocking integrations

Patch the **client class**, not `requests`:

```python
@patch("my_app.integrations.zk.sync.ZKClient")
def test_sync_deletes_user_when_contract_cancelled(self, Client):
    c = make_contract(self.customer, self.space, submit=True)
    c.cancel()
    sync_contract_access(c.name)
    Client.return_value.delete_user.assert_called_once()
```

## Testing whitelisted APIs

Call the Python function directly (fast) for logic; use `frappe.call`-style HTTP tests only for routing/auth concerns.

```python
def test_renew_requires_write_permission(self):
    c = make_contract(self.customer, self.space, submit=True)
    frappe.set_user(make_user_without_roles())
    try:
        with self.assertRaises(frappe.PermissionError):
            renew(c.name, 12)
    finally:
        frappe.set_user("Administrator")
```

## React tests

See `references/react-testing.md` (Vitest + Testing Library + MSW mocking Frappe responses).

## CI

See `references/ci.md` — GitHub Actions / Bitbucket pipeline that spins up MariaDB + Redis, installs bench, runs backend tests and frontend tests on every PR.

## Anti-patterns

| ❌ | ✅ |
|---|---|
| Tests that hit real ZK/payment APIs | mock the client class |
| `frappe.db.commit()` inside tests | let the framework roll back |
| Hard-coded names `"CUST-0001"` | factories with random names |
| Asserting on full `as_dict()` | assert the fields that matter |
| One huge test per DocType | one behaviour per test, descriptive name |
| Forgetting `frappe.set_user("Administrator")` after switching | `try/finally` or v16 context manager |
| Running tests on production site | dedicated test site with `allow_tests` |
