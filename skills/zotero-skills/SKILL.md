---
name: zotero-skills
description: "Full CRUD operations on Zotero library — search, add, update, delete items with notes, tags, collections, and PDF attachments. Uses dual-API architecture (local API for fast reads, Web API for writes). Use this skill whenever the user mentions Zotero, references, citations, literature management, reading notes, or wants to organize academic papers — even if they don't explicitly say 'Zotero'."
license: MIT
---

# Zotero Library Management Skill

Dual-API CRUD for a Zotero library: search / read via the local desktop API, write via the Web API. Claude routes the request, picks local-API for reads and Web-API for writes, and verifies the result.

## Hard rules

- **Reads → Local API** (`http://localhost:23119/api`, header `Zotero-Allowed-Request: true`). Fast, no key needed, only available while Zotero desktop is running.
- **Writes → Web API** (`https://api.zotero.org`, header `Zotero-API-Key: <key>`) via `pyzotero`. Always.
- **MCP write tools fail.** `zotero_create_note` / `zotero_batch_update_tags` hit the local API and 400/501 — use `pyzotero` from the shared client instead.
- **API key never appears in commits, notes, or vault files.** Use env vars or `config.json` (gitignored). See `references/api-setup.md`.
- **Always import the shared client** (`from zotero_client import get_client, ZoteroDualClient`) instead of constructing API requests by hand. The shared client handles dual-API routing, rate-limit backoff, and credential loading.

## When to use

Trigger phrases: "add paper to Zotero", "search Zotero", "update this collection", "tag these items", "find duplicates", "create a note on item X", "Zotero / 文獻 / 引用 / 參考文獻管理".

NOT for: auditing the library for cleanup (use `zotero-library-curator` first to plan, then come back here for the apply step).

## Workflow

1. **Probe.** Confirm Zotero desktop is running so reads can use the local API. The shared client's `check_local_api()` returns `True/False`; falls back to Web API automatically if not.
2. **Read state.** `zotero_search_items` / `zotero_get_collections` MCP tools, or direct local-API GET. See `references/read-operations.md`.
3. **Decide & apply.** Pick the right CRUD operation:
   - Create new item / collection / note / attachment → `references/create-operations.md`
   - Update metadata / tags / collection membership / note content → `references/update-operations.md`
   - Move to trash → `references/delete-operations.md`
4. **Verify.** Read the result back via local API or `zot.item(key)` and confirm the change matches intent.

## Output contract

This skill is interactive — there is no machine-readable result file. After every write, surface to the user: the operation performed (CREATE / UPDATE / DELETE), the affected item key(s), and any reversible vs. irreversible aspect (e.g. trash vs. permanent).

## Compatibility

- Tested with `pyzotero >= 1.5`, MCP `zotero` server (any recent version).
- Local API requires Zotero desktop running with **Settings → Advanced → "Allow other applications on this computer to communicate with Zotero"** enabled.
- Web API rate limit is approximately 100 requests / 10 seconds per key. The shared client's `safe_api_call()` handles 429 backoff automatically.

## See also

- `references/api-setup.md` — full API architecture, credentials, shared-client setup
- `references/read-operations.md` — search, get-by-key, list collections, fetch attachments
- `references/create-operations.md` — add items / child notes / attachments / batch
- `references/update-operations.md` — patch metadata, tags, collection membership
- `references/delete-operations.md` — single + batch delete with safety patterns
- `references/error-handling.md` — common 4xx / 5xx + retry strategy
- `references/endpoint-cheatsheet.md` — flat URL / verb table
- `references/api-reference.md` — raw HTTP request bodies, less-common collection-membership operations
- `references/item-types.md` — JSON templates for `journalArticle`, `book`, `conferencePaper`, etc.

## Bundled scripts

- `scripts/zotero_client.py` — the shared client referenced above. Import it for any Zotero operation.
- `scripts/add_literature.py` — batch import script template; use as a starting point when adding many items at once.
