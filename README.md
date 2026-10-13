# Frappe Skills

Claude Code skills for teams building on **Frappe / ERPNext (v15 & v16)** with **React** frontends.
They teach Claude (and new developers) how we build: config-first thinking, controllers, hooks, database, APIs, React, integrations, testing, review, performance, security and deployment.

## Skills (18)

**Foundations**

| Skill | What it covers |
|---|---|
| `frappe-config-first` | check config/built-ins before coding, audit mode, optional auto-guard hook script |
| `frappe-app-architecture` | app/module layout, where code goes, DocType design, extending ERPNext, patches, fixtures |
| `frappe-controllers` | exact document event order, what goes in each event, doc helpers, overrides (v16 `extend_doctype_class`) |
| `frappe-hooks` | full `hooks.py` reference and "my hook doesn't run" checklist |
| `frappe-database` | `get_list` vs `get_all`, filters, `frappe.qb`, safe SQL, bulk writes, transactions |

**Desk & low-code**

| Skill | What it covers |
|---|---|
| `frappe-client-scripts` | form/list JS events, `set_query`, buttons, server calls |
| `frappe-server-scripts` | Server Script types, sandbox rules, when to move to app code |
| `frappe-desk-ui` | dialogs, custom Pages, form dashboards, tree view, realtime in Desk |
| `frappe-reports` | Report Builder vs Query vs Script Report, charts, summaries, prepared reports |
| `frappe-background-jobs` | scheduler, `frappe.enqueue`, batching, retries, monitoring |

**APIs, React & integrations**

| Skill | What it covers |
|---|---|
| `frappe-api-design` | versioned, typed, permission-safe whitelisted APIs |
| `frappe-react-frontend` | React SPA inside a Frappe app: Doppio, frappe-react-sdk, CSRF, realtime, files, deploy |
| `frappe-integrations` | ZK/access devices, payments, webhooks, sync jobs, reconciliation, LAN bridge agent |

**Quality & operations**

| Skill | What it covers |
|---|---|
| `frappe-testing` | v15/v16 test classes, factories, mocking, React tests (Vitest + MSW), CI |
| `frappe-code-review` | severity-ranked PR checklist + report format |
| `frappe-performance` | profiling, N+1, indexes, caching, jobs, React perf |
| `frappe-security` | permission design, endpoint rules, injection/XSS, secrets, files, audit (+ permissions API reference) |
| `frappe-devops` | bench, deploy steps, production, Docker, backups, v15→v16 upgrade, troubleshooting |

---

## Use it in Claude Code

### 1. Get the repo (once per machine)

```bash
git clone https://github.com/ahmedemamhatem/frappe_skils.git ~/frappe_skils
```

### 2. Install the skills

Pick one:

```bash
# A) For every project on this machine (recommended for a developer laptop)
~/frappe_skils/install.sh

# B) For one project only — run from anywhere, pass the app or bench folder
~/frappe_skils/install.sh ~/frappe-bench/apps/my_app

# C) Copy into a project so the team gets them via the project's own git
~/frappe_skils/install.sh --copy ~/frappe-bench/apps/my_app
```

A and B create **symlinks**, so `cd ~/frappe_skils && git pull` updates every project at once.

### 3. Make Claude use them as the reference for dev work

Claude Code picks up skills automatically when a request matches a skill's description. To make it treat them as the **standard for all dev work**, put the guide in `CLAUDE.md` (Claude reads it at the start of every session):

- Option B/C above does this for you (appends `index.md` to the project's `CLAUDE.md`).
- For all projects: paste the contents of `index.md` into `~/.claude/CLAUDE.md`.

`index.md` maps each kind of task to a skill and lists the house rules (config first, permission checks, `get_list` for user data, enqueue after commit, tests).

### 4. Check it works

Start Claude Code inside your project and type `/skills` (or ask *"which skills do you have?"*). You should see the `frappe-*` skills. Then try:

- "Add an API to renew a contract" → it should follow `frappe-api-design` (POST, type hints, permission check).
- "Review my last commit" → report in the `frappe-code-review` format.
- "The Contract list is slow" → `frappe-performance` steps.

You can always name a skill explicitly: *"Use frappe-integrations to design the ZK door sync."*

### 5. Optional: automatic guard on every edit

`skills/frappe-config-first/scripts/frappe_guard.py` warns Claude about raw/interpolated SQL, DB calls in loops, unchecked whitelisted writes, guest endpoints without rate limits and commits in request code — right after it edits a file. Add to your project's `.claude/settings.json`:

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

---

## Customise for your team

1. Replace example names (`my_app`, `Contract`, `Space`, `ZK Settings`) with your real app and DocTypes.
2. Add your conventions (naming series, branches, code style) to `frappe-app-architecture`.
3. Add a project skill (e.g. `skills/coworking-domain/SKILL.md`) describing your DocTypes, contract rules, packages and access logic — this is where Claude gains the most.
4. When Claude gets something wrong twice, add the fix to the relevant skill's anti-patterns table.

Each skill is a folder with a `SKILL.md` (front-matter `name` + `description`, then instructions) and optional `references/` or `scripts/`.

## Tests

```bash
python3 -m unittest discover -s skills/frappe-config-first/scripts -p "test_*.py"
```

## Versions

Checked against Frappe/ERPNext `version-15` and `version-16` source (v16: Python 3.14, Node 24), frappe-react-sdk 1.17 and Doppio. Confirm version-specific details on your own bench.
