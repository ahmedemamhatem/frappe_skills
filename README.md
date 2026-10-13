# Frappe Dev Skills

Claude Code skills for teams building on **Frappe / ERPNext (v15 & v16)** with **React** frontends.
They teach the AI (and new team members) how *we* build: architecture, APIs, React integration, device/API integrations, testing, review, performance, security and deployment.

Designed to sit **next to [FrappeForge](https://github.com/anoopverma-collab/FrappeForge)** — FrappeForge covers Frappe syntax (controllers, hooks, client/server scripts, DB, permissions API); these skills cover how to design, connect, test and ship whole features. No name collisions, same `skills/<name>/SKILL.md` layout.

## Skills

| Skill | Use it for |
|---|---|
| `frappe-app-architecture` | app/module layout, where code goes, DocType design, extending ERPNext safely, patches, fixtures |
| `frappe-api-design` | versioned, typed, permission-safe whitelisted APIs for React/mobile/3rd parties |
| `frappe-react-frontend` | React SPA inside a Frappe app: Doppio, frappe-react-sdk, auth/CSRF, realtime, files, build/deploy |
| `frappe-integrations` | ZK/access devices, payment gateways, webhooks, sync jobs, retries, reconciliation, LAN bridge agent |
| `frappe-testing` | v15/v16 test classes, factories, mocking, permission tests, React tests (Vitest + MSW), CI |
| `frappe-code-review` | severity-ranked PR checklist + report format |
| `frappe-performance` | profiling, N+1, indexes, caching, background jobs, React perf |
| `frappe-security` | permission design, endpoint rules, injection/XSS, secrets, files, audit, release checklist |
| `frappe-devops` | bench setup, deploy procedure, production, Docker, backups, v15→v16 upgrade, troubleshooting |

## Install

**Option A — per project (simplest)**

```bash
cp -r skills/* /path/to/frappe-bench/apps/my_app/.claude/skills/
# or for all your projects:
cp -r skills/* ~/.claude/skills/
```

**Option B — merge into your FrappeForge fork** (keeps auto-sync via its `install-skills.sh`)

```bash
cp -r skills/* ~/.claude-skills/skills/
cd ~/.claude-skills && git add skills && git commit -m "Add team dev skills" && git push
~/.claude-skills/install-skills.sh   # run inside each project
```

Then add `index.md` (or its contents) to the project's `CLAUDE.md` so the AI knows the skills exist.

## Using them

Claude Code loads a skill automatically when the request matches its description. You can also ask directly:

- "Using frappe-api-design, add an endpoint to renew a contract"
- "Review this PR with frappe-code-review"
- "frappe-performance: the Contract list is slow, find why"
- "Set up a React portal for tenants (frappe-react-frontend)"

## Customise for your team

These are a strong default — make them yours:

1. Replace example names (`my_app`, `Contract`, `Space`, `ZK Settings`) with your real app/DocTypes.
2. Add your conventions (naming series, branch names, code style) to `frappe-app-architecture`.
3. Add project-specific skills (e.g. `coworking-domain` describing your DocTypes, contract rules and access logic).
4. When the AI gets something wrong twice, add the fix to the relevant skill's anti-patterns table.

## Versions verified against

- Frappe/ERPNext `version-15` and `version-16` (v16: Python 3.14, Node 24)
- frappe-react-sdk 1.17, Doppio (main)

Always confirm version-specific details on your own bench before relying on them.
