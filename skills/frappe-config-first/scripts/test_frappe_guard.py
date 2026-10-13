import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frappe_guard import check_source  # noqa: E402

GUARD = Path(__file__).parent / "frappe_guard.py"


class TestGuard(unittest.TestCase):
    def test_clean_code_has_no_findings(self):
        src = '''
import frappe

@frappe.whitelist(methods=["POST"])
def renew(name: str):
    doc = frappe.get_doc("Contract", name)
    doc.check_permission("write")
    doc.save()
'''
        self.assertEqual(check_source(src), [])

    def test_interpolated_sql(self):
        f = check_source('frappe.db.sql(f"select * from tabX where a={x}")')
        self.assertTrue(any("injection" in x for x in f))

    def test_plain_sql_is_soft_warning(self):
        f = check_source('frappe.db.sql("select 1")')
        self.assertTrue(any("prefer frappe.qb" in x for x in f))

    def test_db_call_in_loop(self):
        src = "for n in names:\n    d = frappe.get_doc('X', n)\n"
        self.assertTrue(any("N+1" in x for x in check_source(src)))

    def test_whitelist_write_without_permission(self):
        src = '''
@frappe.whitelist()
def close(name):
    d = frappe.get_doc("X", name)
    d.status = "Closed"
    d.save()
'''
        f = check_source(src)
        self.assertTrue(any("permission check" in x for x in f))
        self.assertTrue(any("methods" in x for x in f))

    def test_guest_without_rate_limit(self):
        src = '''
@frappe.whitelist(allow_guest=True)
def ping():
    return 1
'''
        self.assertTrue(any("rate_limit" in x for x in check_source(src)))

    def test_guest_with_rate_limit_ok(self):
        src = '''
@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60)
def ping():
    return 1
'''
        self.assertFalse(any("rate_limit" in x for x in check_source(src)))

    def test_commit_allowed_in_patches(self):
        self.assertTrue(check_source("frappe.db.commit()", "apps/a/a/api.py"))
        self.assertFalse(check_source("frappe.db.commit()", "apps/a/a/patches/v1/p.py"))

    def test_hook_entrypoint_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "apps" / "a" / "a" / "x.py"
            p.parent.mkdir(parents=True)
            p.write_text("for n in names:\n    frappe.db.get_value('X', n, 'y')\n")
            r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps({"tool_input": {"file_path": str(p)}}),
                               text=True, capture_output=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("N+1", r.stderr)
            r = subprocess.run([sys.executable, str(GUARD)], input="not json", text=True, capture_output=True)
            self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
