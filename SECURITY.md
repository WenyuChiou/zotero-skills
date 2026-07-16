# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | ✅ |
| < 0.2 | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately via GitHub's **[Security Advisories](https://github.com/WenyuChiou/zotero-skills/security/advisories/new)**
("Report a vulnerability"). Include: what you found, how to reproduce it, and the
impact. You'll get an acknowledgement and a fix timeline; please allow a
reasonable window before any public disclosure.

## Credential handling (what this project protects)

This skill authenticates to the Zotero Web API with a private API key and can
create/update/**permanently delete** library data. Handling rules:

- **Credentials are never committed.** `config.json` and `.env` are gitignored;
  the resolution order is env vars → `~/.claude/.env` → `config.json` (deprecated).
- **Least privilege.** Generate an API key with only the access you need; enable
  write only if you create/update/delete.
- **A full-history `gitleaks` scan runs in CI** on every push and PR, and a local
  `gitleaks` pre-commit hook is available (`.pre-commit-config.yaml`), so a
  committed key is caught early.
- If you believe an API key was ever exposed, **revoke it immediately** at
  <https://www.zotero.org/settings/keys> — revocation is the only complete
  remedy; scrubbing git history alone does not un-expose an already-public key.

## Agent-safety note

`skills/zotero-skills/SKILL.md` treats all Zotero content (titles, notes,
annotations, PDF text, filenames) as **untrusted data, not instructions**, to
resist prompt injection. Report any path that lets library content drive a tool
action (especially a write/delete) as a security issue.
