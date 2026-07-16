# Zotero Skills — AI Coding Assistant Skill for Zotero CRUD

> [繁體中文版](README_zh-TW.md)

Comprehensive Zotero library management via dual-API architecture (local read + web write). Works with any AI coding assistant that supports skills or custom instructions.

> 📚 Part of the [**agentic AI learning roadmap**](https://github.com/WenyuChiou/awesome-agentic-ai-zh) — a 7-stage curated path for building agentic AI, multilingual (zh-TW · zh-CN · English). This skill is referenced in §13 (research workflow skills).

---

## Overview

A skill that gives AI coding assistants full CRUD access to your Zotero library. Search, add, classify, annotate, and organize references programmatically — all from your terminal.

See [Features](#features) below for the full list.

---

## Features

### Core CRUD Operations
- **Search & Discovery** — Full-text search, tag-based filtering, collection browsing, recent items
- **Create Items** — Add journal articles, books, conference papers, reports, theses, webpages with full metadata
- **Update & Organize** — Edit metadata, manage tags, move items between collections, batch operations
- **Delete & Cleanup** — Remove items, notes, collections; duplicate detection

### Smart API Routing
- **Dual-API architecture** — Reads via fast local API (port 23119), writes via Zotero Web API
- **Auto health check & fallback** — Detects Zotero desktop status; seamless fallback to web-only mode
- **Built-in rate limiting** — `safe_api_call()` wrapper prevents API quota violations

### Notes & Annotations
- **Child notes** — Attach rich HTML notes to any library item
- **Reading notes** — Create structured reading notes with sections
- **Batch note creation** — Add notes to multiple items programmatically

### Collection Management
- **Create & organize** — Build hierarchical collection structures
- **Bulk operations** — Move/copy items between collections in batch
- **Collection browsing** — List and navigate collection trees

### Integration Ready
- **Framework-agnostic** — Works with Claude Code, Codex CLI, Gemini CLI, Cursor, or any AI assistant
- **Python library** — Import `zotero_client.py` directly in any Python project
- **JSON templates** — Pre-built templates for all Zotero item types

---

## Setup

### Prerequisites

- **Python 3.10+**
- **pyzotero**: `pip install pyzotero`

### API Credentials

1. **API Key** — Generate at [https://www.zotero.org/settings/keys](https://www.zotero.org/settings/keys). Grant the **least privilege** you need — enable write access only if you will create / update / delete.
2. **Library ID** — Found on the same page under "Your userID for use in API calls"

### Configuration — recommended: one `.env` file

The shared client resolves credentials in this order: **environment variables → `~/.claude/.env` → `config.json`**. The simplest, safest way is a single file — create **`~/.claude/.env`** and paste three lines:

```bash
ZOTERO_API_KEY=your_key_here
ZOTERO_LIBRARY_ID=your_library_id
ZOTERO_LIBRARY_TYPE=user
```

That's it — no code, works everywhere, and nothing to commit. (Setting the same three as shell environment variables works too.)

> ⚠️ **A stale OS-level `ZOTERO_API_KEY` overrides `~/.claude/.env`** (environment wins). If a new key seems ignored, check for a leftover one — PowerShell: `$Env:ZOTERO_API_KEY` · bash: `echo $ZOTERO_API_KEY` — and remove it.

<details>
<summary><b>Legacy alternative: <code>config.json</code> (deprecated)</b></summary>

`config.json` still works but is **deprecated** — it emits a `DeprecationWarning` at runtime. It is gitignored so it is never committed. Prefer `~/.claude/.env`; use this only if you cannot set env vars:

```bash
cp config.example.json config.json   # then fill in your key + library id
```

```json
{ "zotero_api_key": "YOUR_API_KEY", "zotero_library_id": "YOUR_LIBRARY_ID", "zotero_library_type": "user" }
```

**Never commit credentials.**
</details>

### Installation

Install via the [`ai-research-skills` Claude Code marketplace](https://github.com/WenyuChiou/ai-research-skills):

```bash
claude plugin marketplace add WenyuChiou/ai-research-skills
claude plugin install zotero-skills@ai-research-skills --scope user
```

> **Migrating from a previous `cp -r` / `git clone` install?** SKILL.md
> moved from the repo root to `skills/zotero-skills/SKILL.md` for
> marketplace auto-discovery. The old `cp -r zotero-skills/ ~/.claude/skills/zotero-skills/`
> layout no longer loads (Claude Code scans only one level deep).
> Remove the old copy (`rm -rf ~/.claude/skills/zotero-skills`) and
> run the marketplace install above.

---

## Non-Claude CLI Adaptation

This skill was developed for Claude Code but works with any AI assistant.

| CLI | How to load the skill |
|---|---|
| **Claude Code** | Place in `~/.claude/skills/` or `.claude/skills/` — auto-loaded |
| **Codex CLI** | Pass `SKILL.md` as a context file via `-C` or include in task prompt |
| **Gemini CLI** | Include `SKILL.md` in system prompt or project context |
| **Cursor / Windsurf** | Add `SKILL.md` to `.cursor/rules` or equivalent rules file |
| **Any other tool** | Paste relevant sections of `SKILL.md` into your system prompt |

---

## Project Structure

```
zotero-skills/
├── .claude-plugin/plugin.json   # Marketplace manifest
├── config.example.json          # Template for API credentials
├── config.json                  # Your credentials (gitignored — never committed)
├── requirements.txt             # pyzotero dependency
├── LICENSE                      # MIT
├── scripts/
│   ├── zotero_client.py         # ZoteroDualClient + helpers
│   └── add_literature.py        # Batch import script template
├── skills/zotero-skills/
│   ├── SKILL.md                 # Agent operating rules
│   └── references/              # api-setup, read/create/update/delete-operations,
│       └── ...                  # error-handling, endpoint-cheatsheet, api-reference, item-types
├── README.md                    # English
└── README_zh-TW.md              # 繁體中文
```

---

## Dual-API Architecture

Zotero exposes two APIs with different capabilities. This skill routes automatically.

| | Local API (`localhost:23119`) | Web API (`api.zotero.org`) |
|---|---|---|
| **Access** | Requires Zotero desktop running | Works anywhere |
| **Read** | ✅ Fast, full-text search | ✅ Standard queries |
| **Write** | ❌ Not supported (`501`) | ✅ Full CRUD |
| **Rate limit** | None | ~100 req / 10 sec (dynamic; honor `Backoff`/`Retry-After` headers) |
| **Auth** | `Zotero-Allowed-Request: true` header | `Zotero-API-Key: <key>` header |

### Health Check & Auto-Fallback

On initialization, `ZoteroDualClient` calls `check_local_api()` — a lightweight GET to `localhost:23119`.

- If Zotero desktop is not running → reads fall back to Web API automatically, no config change needed
- Performance degrades slightly (web latency), but all operations still work

```python
from zotero_client import ZoteroDualClient

dual = ZoteroDualClient()
# dual.local_available → True if Zotero desktop running, False otherwise

results = dual.search("flood adaptation")            # local API if available
dual.create_note("ITEM_KEY", "Section", "Notes...")  # always web API
```

### Important Notes

- The local API **does not support write operations** — all creates/updates/deletes go through the Web API
- If you use a Zotero MCP connector with `ZOTERO_LOCAL=true`, its write tools will fail — use `zotero_client.py` for writes

---

## Available Functions

From `scripts/zotero_client.py`:

| Function | Description |
|---|---|
| `get_client()` | Configured `pyzotero.Zotero` Web API instance |
| `get_collection(name)` | Find collection key by display name from `config.json` |
| `add_note(zot, item_key, content)` | Attach a child note to a library item |
| `check_duplicate(zot, title, doi)` | Check if item with given title or DOI exists |
| `check_local_api(timeout, library_id)` | Test if Zotero desktop local API is reachable |
| `ZoteroDualClient` | Dual-API wrapper — local reads, web writes, auto-fallback |
| `safe_api_call(func)` | API call wrapper with automatic rate-limit backoff |

---

## Usage Examples

### ZoteroDualClient (recommended)

```python
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/zotero-skills/scripts"))
from zotero_client import ZoteroDualClient
dual = ZoteroDualClient()
print(f"Local API available: {dual.local_available}")

results = dual.search("flood risk perception")
dual.create_note("I3P2J58S", "Section 2", "<p>Discusses PMT framework.</p>")
```

### Create a journal article

```python
from pyzotero import zotero
zot = zotero.Zotero("YOUR_LIBRARY_ID", "user", "YOUR_API_KEY")

template = zot.item_template("journalArticle")
template["title"] = "Deep Learning for NLP: A Survey"
template["creators"] = [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
template["publicationTitle"] = "Nature Machine Intelligence"
template["date"] = "2025"
template["DOI"] = "10.1038/s42256-025-00001-1"
resp = zot.create_items([template])
```

### Search by tag

```python
items = zot.items(tag="machine-learning", limit=25)
for item in items:
    print(f"{item['data']['title']} — {item['data'].get('date', 'n.d.')}")
```

---

## License

MIT