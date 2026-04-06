# Zotero Skills — AI Coding Assistant Skill for Zotero CRUD

> Comprehensive Zotero library management via dual-API architecture (local read + web write).  
> Works with any AI coding CLI that supports skills (Claude Code, Codex, Gemini CLI, etc.)

---

## Overview

A skill that gives AI coding assistants full CRUD access to your Zotero library. Search, add, classify, annotate, and organize references programmatically — all from your terminal.

**Key capabilities:**

- **Dual-API routing** — Reads go through the fast local API (port 23119), writes go through the Zotero Web API
- **Full CRUD** — Create, read, update, and delete items, notes, tags, and collections
- **JSON templates** for all item types: journal article, book, book section, conference paper, report, thesis, webpage, and more
- **Rate limiting** — Built-in `safe_api_call()` wrapper to stay within Zotero's API quotas
- **Collection management** — Create, list, and organize collections; move items between them
- **Batch operations** — Add multiple items in a single API call
- **Child notes** — Attach rich-text notes to any parent item

---

## Setup

### Prerequisites

- **Python 3.10+**
- **pyzotero**:
  ```bash
  pip install pyzotero
  ```

### API Credentials

1. **API Key** — Generate at [https://www.zotero.org/settings/keys](https://www.zotero.org/settings/keys)
   - Enable **Allow library access** and **Allow write access**
2. **Library ID** — Found on the same page under **"Your userID for use in API calls"**

### Configuration

Create `config.json` in the skill root:

```json
{
  "api_key": "YOUR_API_KEY",
  "library_id": "YOUR_LIBRARY_ID",
  "library_type": "user",
  "collections": {
    "collection_name": "COLLECTION_KEY"
  }
}
```

> **Tip:** Collection keys can be found at `https://www.zotero.org/users/<library_id>/collections` — the key is the last URL segment.

### Installation

**Global (all projects):**
```bash
cp -r zotero-skills/ ~/.claude/skills/zotero-skills/
```

**Project-level:**
```bash
cp -r zotero-skills/ your-project/.claude/skills/zotero-skills/
```

For non-Claude CLIs, place the skill folder wherever your tool reads skill definitions.

---

## Project Structure

```
zotero-skills/
├── SKILL.md              # Full CRUD reference (1,167 lines)
├── config.json           # API credentials + collection mappings
├── scripts/
│   ├── zotero_client.py  # ZoteroDualClient + helpers
│   └── add_literature.py # Batch import script
├── references/
│   ├── api-reference.md  # Zotero API endpoint docs
│   └── item-types.md     # JSON templates for all item types
├── docs/                 # Example screenshots
├── .gitignore
└── README.md
```

---

## Usage Examples

### Read items

```python
from pyzotero import zotero

zot = zotero.Zotero("YOUR_LIBRARY_ID", "user", "YOUR_API_KEY")
items = zot.top(limit=5)
for item in items:
    print(item["data"]["title"])
```

### Create a journal article

```python
template = zot.item_template("journalArticle")
template["title"] = "Deep Learning for NLP: A Survey"
template["creators"] = [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
template["publicationTitle"] = "Nature Machine Intelligence"
template["date"] = "2025"
template["DOI"] = "10.1038/s42256-025-00001-1"
resp = zot.create_items([template])
```

### Add a child note

```python
parent_key = "ABC12345"
note_template = zot.item_template("note")
note_template["parentItem"] = parent_key
note_template["note"] = "<p>Key findings: Model achieves 95% accuracy on benchmark.</p>"
zot.create_items([note_template])
```

### Search by tag

```python
items = zot.items(tag="machine-learning", limit=25)
for item in items:
    print(f"{item['data']['title']} — {item['data'].get('date', 'n.d.')}")
```

---

## Dual-API Architecture

Zotero exposes two APIs with different capabilities:

| | Local API (`localhost:23119`) | Web API (`api.zotero.org`) |
|---|---|---|
| **Access** | Requires Zotero desktop running | Works anywhere |
| **Read** | ✅ Fast, full-text search | ✅ Standard queries |
| **Write** | ❌ Read-only | ✅ Full CRUD |
| **Rate limit** | None | ~50 req / 10 sec |

The `ZoteroDualClient` in `scripts/zotero_client.py` handles routing automatically — reads go to the local API when available, writes always go through the web API.

---

## Available Functions

From `scripts/zotero_client.py`:

| Function | Description |
|---|---|
| `get_client()` | Returns a configured `pyzotero.Zotero` instance |
| `get_collection(name)` | Find a collection key by display name |
| `add_note(parent_key, content)` | Attach a child note to a library item |
| `check_duplicate(title)` | Check whether an item with the given title exists |
| `ZoteroDualClient` | Dual-API wrapper — local reads, web writes |
| `safe_api_call(func)` | Execute an API call with automatic rate-limit backoff |

---

## Requirements

- **Python** 3.10+
- **pyzotero** (`pip install pyzotero`)
- A **Zotero account** with an API key (free at [zotero.org](https://www.zotero.org))
- *(Optional)* **Zotero desktop app** — enables local API reads for faster performance

---

## License

MIT
