# Zotero Skills — AI Coding Assistant Skill for Zotero CRUD

> [繁體中文版](README_zh-TW.md)

Comprehensive Zotero library management via dual-API architecture (local read + web write). Works with any AI coding assistant that supports skills or custom instructions.

---

## Overview

A skill that gives AI coding assistants full CRUD access to your Zotero library. Search, add, classify, annotate, and organize references programmatically — all from your terminal.

**Key capabilities:**

- **Dual-API routing** — Reads go through the fast local API (port 23119), writes through Zotero Web API
- **Automatic health check & fallback** — Detects whether Zotero desktop is running; falls back to web-only mode transparently
- **Full CRUD** — Create, read, update, and delete items, notes, tags, and collections
- **JSON templates** for all item types: journal article, book, book section, conference paper, report, thesis, webpage, and more- **Rate limiting** — Built-in `safe_api_call()` wrapper to stay within Zotero's API quotas
- **Collection management** — Create, list, and organize collections; move items between them
- **Batch operations** — Add multiple items in a single API call
- **Child notes** — Attach rich-text notes to any parent item
- **Research Hub integration** — End-to-end pipeline from paper search to NotebookLM

---

## Setup

### Prerequisites

- **Python 3.10+**
- **pyzotero**: `pip install pyzotero`

### API Credentials

1. **API Key** — Generate at [https://www.zotero.org/settings/keys](https://www.zotero.org/settings/keys). Enable "Allow library access" and "Allow write access".
2. **Library ID** — Found on the same page under "Your userID for use in API calls"

### Configuration

Create `config.json` in the skill root:

```json
{
  "zotero_api_key": "YOUR_API_KEY",
  "zotero_library_id": "YOUR_LIBRARY_ID",
  "zotero_library_type": "user",
  "collections": {
    "my_collection": "COLLECTION_KEY"
  }
}
```
> **Tip:** Collection keys are the last URL segment at `https://www.zotero.org/users/<library_id>/collections`

### Installation

**Global (all projects):**
```bash
cp -r zotero-skills/ ~/.claude/skills/zotero-skills/
```

**Project-level:**
```bash
cp -r zotero-skills/ your-project/.claude/skills/zotero-skills/
```

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

`scripts/zotero_client.py` is framework-agnostic — import it from any Python script.
---

## Project Structure

```
~/.claude/skills/zotero-skills/        # Global install path
├── SKILL.md              # Full CRUD reference for AI assistants
├── config.json           # API credentials + collection mappings
├── scripts/
│   ├── zotero_client.py  # ZoteroDualClient + helpers
│   └── add_literature.py # Batch import script
├── references/
│   ├── api-reference.md  # Zotero API endpoint docs
│   └── item-types.md     # JSON templates for all item types
├── docs/                 # Example screenshots
├── README.md             # English
└── README_zh-TW.md       # 繁體中文
```

---

## Dual-API Architecture

Zotero exposes two APIs with different capabilities. This skill routes automatically.

| | Local API (`localhost:23119`) | Web API (`api.zotero.org`) |
|---|---|---|
| **Access** | Requires Zotero desktop running | Works anywhere |
| **Read** | ✅ Fast, full-text search | ✅ Standard queries |
| **Write** | ❌ Not supported (`501`) | ✅ Full CRUD |
| **Rate limit** | None | ~50 req / 10 sec |
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

## Research Hub Pipeline

End-to-end pipeline from literature discovery to AI-assisted synthesis.

```
Paper Search  →  Zotero Write  →  Obsidian Note  →  Hub Index  →  NotebookLM
                 (this skill)     (file write)      (manifest)    (AI Q&A)
```
1. **Paper Search** — Find papers via Google Scholar, Semantic Scholar, Crossref, or direct DOI
2. **Zotero Write** — Add items with metadata, tags, and collection assignment using this skill
3. **Obsidian Note** — Generate structured `.md` notes in your vault with YAML frontmatter
4. **Build Hub Index** — Create a unified manifest linking Zotero keys ↔ Obsidian notes ↔ file paths
5. **NotebookLM** — Upload sources for AI-assisted literature review and Q&A

Hub index building and NotebookLM upload are handled by the `knowledge-base` skill.

---

## Available Functions

From `scripts/zotero_client.py`:

| Function | Description |
|---|---|
| `get_client()` | Configured `pyzotero.Zotero` Web API instance |
| `get_collection(name)` | Find collection key by display name from `config.json` |
| `add_note(zot, item_key, content)` | Attach a child note to a library item |
| `check_duplicate(zot, title, doi)` | Check if item with given title or DOI exists |
| `check_local_api(timeout)` | Test if Zotero desktop local API is reachable |
| `ZoteroDualClient` | Dual-API wrapper — local reads, web writes, auto-fallback |
| `safe_api_call(func)` | API call wrapper with automatic rate-limit backoff |

---

## Usage Examples

### ZoteroDualClient (recommended)

```python
import sys
sys.path.insert(0, r"~/.claude/skills/zotero-skills/scripts")
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

## Requirements

- **Python** 3.10+
- **pyzotero** (`pip install pyzotero`)
- A **Zotero account** with an API key — free at [zotero.org](https://www.zotero.org)
- *(Optional)* **Zotero desktop app** — enables local API reads for faster performance

---

## License

MIT