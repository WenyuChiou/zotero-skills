# Zotero Skills — Claude Code Skill for Zotero CRUD

> Comprehensive Zotero library management via dual-API architecture (local read + web write)

![Claude Code Compatible](https://img.shields.io/badge/Claude_Code-Compatible-blueviolet?style=flat-square)

---

## What's New (zotero-write → zotero-skills)

This project was formerly `zotero-write`. The rename to `zotero-skills` reflects a major expansion in scope:

- **Merged comprehensive CRUD documentation** — `SKILL.md` now covers all read, create, update, and delete operations in a single reference (1,167 lines)
- **`ZoteroDualClient` class** — Automatic routing between local API (reads) and web API (writes)
- **Full JSON templates** for all item types: journal article, book, book section, conference paper, report, thesis, webpage, and more
- **`safe_api_call()`** — Wrapper with built-in rate limiting to stay within Zotero's API quotas
- **Collection management** — Create, list, and organize collections; move items between them
- **Child note creation** — Attach rich-text notes to any parent item
- **Batch import support** — Add multiple items in a single API call
- **Error handling guide** — Common failure modes and fixes
- **Quick reference card** — Copy-paste code snippets for everyday tasks
---

## Setup / Environment Configuration

### Prerequisites

- **Python 3.10+**
- **pyzotero** — Install via pip:
  ```bash
  pip install pyzotero
  ```

### Getting Your API Credentials

1. **API Key** — Generate one at [https://www.zotero.org/settings/keys](https://www.zotero.org/settings/keys)
   - Enable **Allow library access** and **Allow write access**
2. **Library ID** — Found on the same page under **"Your userID for use in API calls"**

### Configuration

Create (or edit) `config.json` in the skill root:

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

> **Tip:** You can find collection keys by browsing your library at `https://www.zotero.org/users/<library_id>/collections` — the key is the last segment of the URL.
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
├── .gitignore
└── README.md
```
---

## Usage Examples

### Read items from your library

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
print(resp)
```
### Add a child note

```python
parent_key = "ABC12345"
note_content = "<p>Key findings: Model achieves 95% accuracy on benchmark.</p>"
note_template = zot.item_template("note")
note_template["parentItem"] = parent_key
note_template["note"] = note_content
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

Zotero exposes two separate APIs with different capabilities:

| | Local API (`localhost:23119`) | Web API (`api.zotero.org`) |
|---|---|---|
| **Access** | Requires Zotero desktop running | Works anywhere |
| **Read** | ✅ Fast, full-text search | ✅ Standard queries |
| **Write** | ❌ Read-only | ✅ Full CRUD |
| **Rate limit** | None | ~50 req / 10 sec |
The **`ZoteroDualClient`** in `scripts/zotero_client.py` handles this automatically — reads are routed to the local API when Zotero desktop is running (for speed), and all writes go through the web API.

---

## Available Functions

Quick reference for `scripts/zotero_client.py`:

| Function | Description |
|---|---|
| `get_client()` | Returns a configured `pyzotero.Zotero` instance |
| `get_collection(name)` | Find a collection key by its display name |
| `add_note(parent_key, content)` | Attach a child note to a library item |
| `check_duplicate(title)` | Check whether an item with the given title already exists |
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