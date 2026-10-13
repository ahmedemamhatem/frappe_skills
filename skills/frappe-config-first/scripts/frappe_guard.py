#!/usr/bin/env python3
"""Lightweight Frappe code guard for Claude Code PostToolUse hooks.

Reads the hook payload (JSON) from stdin, checks the edited file if it is a
Python file under an `apps/` directory, prints warnings to stderr and exits 2
when something is found (exit 0 otherwise). Text/regex based on purpose: fast,
no imports of Frappe, never blocks on its own errors.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LOOP_DB_CALL = re.compile(
    r"frappe\.(get_doc|get_cached_doc|db\.get_value|db\.sql|db\.exists|db\.count|get_value)\("
)
SQL_INTERPOLATED = re.compile(r"frappe\.db\.sql\(\s*(f[\"']|[\"'].*[\"']\s*\.format\()")
SQL_ANY = re.compile(r"frappe\.db\.sql\(")
WHITELIST = re.compile(r"^\s*@frappe\.whitelist\((?P<args>.*)\)")
DOC_WRITE = re.compile(r"\.(save|submit|cancel|delete|insert)\(")
PERM_CHECK = re.compile(
    r"check_permission\(|has_permission\(|only_for\(|frappe\.throw\(.*PermissionError|validate_permission"
)
COMMIT = re.compile(r"frappe\.db\.commit\(\)")
IGNORE_PERMS = re.compile(r"ignore_permissions\s*=\s*True|flags\.ignore_permissions\s*=\s*True")
DEF = re.compile(r"^(?P<indent>\s*)def\s+\w+")
LOOP = re.compile(r"^(?P<indent>\s*)(for|while)\b.*:\s*(#.*)?$")


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def function_blocks(lines: list[str]):
    """Yield (start_index, end_index_exclusive, decorators) for each top-level-ish def."""
    i = 0
    n = len(lines)
    while i < n:
        m = DEF.match(lines[i])
        if not m:
            i += 1
            continue
        start = i
        base = indent_of(lines[i])
        decorators = []
        j = start - 1
        while j >= 0 and lines[j].strip().startswith("@"):
            decorators.append(lines[j])
            j -= 1
        k = i + 1
        while k < n and (not lines[k].strip() or indent_of(lines[k]) > base):
            k += 1
        yield start, k, decorators
        i = k


def check_source(source: str, path: str = "") -> list[str]:
    findings: list[str] = []
    lines = source.splitlines()
    is_job_module = any(p in path for p in ("/patches/", "/tasks", "jobs", "/background", "scheduler"))

    # 1. SQL
    for no, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        if SQL_INTERPOLATED.search(line):
            findings.append(f"{no}: frappe.db.sql with f-string/.format — SQL injection risk; use frappe.qb or %(param)s values")
        elif SQL_ANY.search(line):
            findings.append(f"{no}: frappe.db.sql — prefer frappe.qb / frappe.get_list unless raw SQL is really needed")

    # 2. DB calls inside loops (same file, inline only)
    for no, line in enumerate(lines):
        m = LOOP.match(line)
        if not m:
            continue
        base = indent_of(line)
        k = no + 1
        while k < len(lines) and (not lines[k].strip() or indent_of(lines[k]) > base):
            if LOOP_DB_CALL.search(lines[k]) and not lines[k].lstrip().startswith("#"):
                findings.append(f"{k + 1}: DB call inside a loop (N+1) — fetch once with filters={{'name': ['in', ...]}} or a join")
            k += 1

    # 3. Whitelisted functions
    for start, end, decorators in function_blocks(lines):
        wl = next((WHITELIST.match(d) for d in decorators if WHITELIST.match(d)), None)
        if not wl:
            continue
        body = "\n".join(lines[start:end])
        args = wl.group("args")
        if DOC_WRITE.search(body) and not PERM_CHECK.search(body) and "allow_guest" not in args:
            findings.append(f"{start + 1}: whitelisted function writes documents without an explicit permission check")
        if "allow_guest=True" in args.replace(" ", "") and not any("rate_limit" in d for d in decorators):
            findings.append(f"{start + 1}: allow_guest endpoint without @rate_limit")
        if DOC_WRITE.search(body) and "methods" not in args:
            findings.append(f"{start + 1}: whitelisted function writes data but doesn't restrict methods=['POST']")

    # 4. Commits / ignore_permissions
    for no, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        if COMMIT.search(line) and not is_job_module:
            findings.append(f"{no}: frappe.db.commit() in request code breaks atomicity — only commit in background jobs/patches")
        if IGNORE_PERMS.search(line):
            findings.append(f"{no}: ignore_permissions=True — make sure this is intentional and scoped (add a comment why)")

    # de-duplicate, keep order
    seen, out = set(), []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path.endswith(".py") or "/apps/" not in path.replace("\\", "/"):
        return 0
    if "/test_" in path or path.endswith("_test.py"):
        return 0
    try:
        source = Path(path).read_text(encoding="utf-8")
    except Exception:
        return 0
    findings = check_source(source, path.replace("\\", "/"))
    if not findings:
        return 0
    print(f"frappe_guard: {path}", file=sys.stderr)
    for f in findings:
        print(f"  line {f}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
