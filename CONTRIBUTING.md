# Contributing to zotero-skills

Thanks for helping improve this skill. It's a small, security-sensitive project
(it holds an API key and can delete library data), so contributions are held to
a clear bar: **tests + no secrets + honest docs**.

## Dev setup

```bash
git clone https://github.com/WenyuChiou/zotero-skills
cd zotero-skills
python -m pip install -r requirements.txt pytest ruff   # Python 3.10+
```

Credentials for local/manual testing go in **environment variables** or
`~/.claude/.env` — **never** in a committed file. See
[`references/api-setup.md`](skills/zotero-skills/references/api-setup.md).

## Before you open a PR

Run the same checks CI runs (they must pass):

```bash
ruff check scripts/ tests/
python -m pytest tests/ -q
```

Optional but recommended — install the local pre-commit hooks so a secret or a
lint error is caught before it's committed:

```bash
pip install pre-commit && pre-commit install
```

## Rules that matter here

- **Never commit `config.json`, `.env`, API keys, or a real Library ID.** They
  are gitignored; CI runs a full-history `gitleaks` scan on every PR.
- **Every new behaviour ships with a test.** The mock suite (`tests/`) uses a
  fake pyzotero client + a mock HTTP server — no real Zotero calls. Real-API
  testing must be isolated (unique test collection, tracked keys, cleanup).
- **Destructive ops are surfaced, not silent.** Prefer `trash_item` (recoverable)
  over `delete_item` (permanent). Writes surface the `failed` bucket, not swallow it.
- **`skills/zotero-skills/SKILL.md`'s "Safety rules" section is load-bearing** —
  it is the agent's operating contract. Changes there need extra care and review.
- **Docs must match the code.** Both READMEs (EN + 繁中) stay mirrored;
  `tests/test_docs_consistency.py` enforces some of this.

## Reporting bugs / security

- Functional bugs → open a GitHub issue.
- Security issues (a leaked key, an injection path) → see
  [`SECURITY.md`](SECURITY.md); **do not** open a public issue.
