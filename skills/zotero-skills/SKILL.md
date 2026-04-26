---
name: zotero-skills
description: "Full CRUD operations on Zotero library — search, add, update, delete items with notes, tags, collections, and PDF attachments. Uses dual-API architecture (local API for fast reads, Web API for writes). Use this skill whenever the user mentions Zotero, references, citations, literature management, reading notes, or wants to organize academic papers — even if they don't explicitly say 'Zotero'."
---

# Zotero Library Management Skill

Complete CRUD workflow for managing Zotero references: search, add, classify, annotate, update, delete, and organize.

---

## 1. API Architecture & Setup

This skill routes operations through two APIs automatically:

| | Local API | Web API |
|---|---|---|
| **Base URL** | `http://localhost:23119/api` | `https://api.zotero.org` |
| **Auth** | Header: `Zotero-Allowed-Request: true` | Header: `Zotero-API-Key: <key>` |
| **Capabilities** | **Read-only** (GET) | **Full CRUD** (GET/POST/PATCH/DELETE) |
| **Speed** | Very fast (localhost) | Standard (network) |
| **Rate limit** | None | ~100 req / 10 sec |
| **Requires** | Zotero desktop running | API key |

**Routing rules:**
- **Search & Read** → Local API (via MCP tools or direct HTTP) — fast, no key needed
- **Create / Update / Delete** → Web API (via pyzotero) — requires API key
- **Fallback** → If Zotero desktop is closed, all operations go through Web API automatically
> **Warning:** MCP write tools (`zotero_create_note`, `zotero_batch_update_tags`) use the local API and **will fail** with 400/501 errors. Always use pyzotero for writes.

### Getting API Credentials

1. Go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys)
2. Click **"Create new private key"** — enable **Library Read/Write** and **Allow write access**
3. Copy the key and your **Library ID** (shown on the same page)
4. Store in `config.json` (see `config.example.json` for format) or environment variables:

```bash
export ZOTERO_API_KEY="your_key_here"
export ZOTERO_LIBRARY_ID="your_library_id"
export ZOTERO_LIBRARY_TYPE="user"
```

### Using the Shared Client

```python
import sys
sys.path.insert(0, r"~/.claude/skills/zotero-skills/scripts")
from zotero_client import get_client, get_collection, add_note, check_duplicate, ZoteroDualClient

# Option A: Web API client (for writes)
zot = get_client()  # reads credentials from config.json or env vars

# Option B: Dual client (local reads + web writes, auto-fallback)
dual = ZoteroDualClient()
results = dual.search("flood adaptation")            # local API if available
dual.create_note("ITEM_KEY", "Section", "Notes...")  # always web API
```

**Available functions in `zotero_client.py`:**

| Function | Description |
|---|---|
| `get_client()` | Configured `pyzotero.Zotero` Web API instance |
| `get_collection(name)` | Find collection key by display name from `config.json` |
| `add_note(zot, item_key, content)` | Attach a child note to a library item |
| `check_duplicate(zot, title, doi)` | Check if item with given title or DOI exists |
| `check_local_api(timeout)` | Test if Zotero desktop local API is reachable |
| `ZoteroDualClient` | Dual-API wrapper with auto-fallback |
| `safe_api_call(func)` | Wrapper with automatic rate-limit backoff |

---

## 2. READ Operations (Local API — No Key Required)

Use MCP tools for reads when Zotero desktop is running. All GET requests go to `http://localhost:23119/api/users/{LIBRARY_ID}/...`.

### MCP Tools (Recommended for Reads)

| Tool | Description | Key Parameters |
|------|------------|---------------|
| `zotero_search_items` | Search by query | `query`, `qmode`, `item_type`, `tag`, `limit` |
| `zotero_get_item_metadata` | Get item details | `item_key`, `format`, `include_abstract` |
| `zotero_get_collections` | List all collections | `limit` |
| `zotero_get_collection_items` | Items in a collection | (collection key) |
| `zotero_get_tags` | List all tags | — |
| `zotero_search_by_tag` | Find items by tag | (tag name) |
| `zotero_get_item_children` | Notes/attachments | (item key) |
| `zotero_get_notes` | Get notes for item | (item key) |
| `zotero_get_recent` | Recently added items | — |
| `zotero_search_notes` | Search within notes | (query) |
| `zotero_semantic_search` | Semantic similarity | (query) |

### Direct HTTP (Python)

```python
import requests

LIBRARY_ID = "YOUR_LIBRARY_ID"
BASE = f"http://localhost:23119/api/users/{LIBRARY_ID}"
HEADERS = {"Zotero-Allowed-Request": "true", "Zotero-API-Version": "3"}

# Search
items = requests.get(f"{BASE}/items", headers=HEADERS,
    params={"q": "flood adaptation", "qmode": "everything", "limit": 10, "format": "json"}).json()

# Get single item
item = requests.get(f"{BASE}/items/ITEM_KEY", headers=HEADERS).json()

# List collections
colls = requests.get(f"{BASE}/collections", headers=HEADERS, params={"format": "json"}).json()
```

**Common query parameters:** `limit` (max 100), `start` (pagination offset), `sort`, `direction`, `q` (search), `qmode` (`titleCreatorYear` or `everything`), `tag`, `itemType`, `format` (`json`, `keys`, `bibtex`).

---

## 3. CREATE Operations (Web API — Requires API Key)

All writes go to `https://api.zotero.org/users/{LIBRARY_ID}/...` via pyzotero.

### Workflow: Adding Literature

**Always follow this sequence:** check duplicate → create item → add note → (optional) upload PDF.

```python
zot = get_client()

# Step 1: Check for duplicates (DOI preferred, fallback to title)
doi = "10.xxxx/xxxxx"
title = "Paper Title"
if not check_duplicate(zot, title, doi):

    # Step 2: Create item
    template = zot.item_template("journalArticle")
    template["title"] = title
    template["creators"] = [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
    template["publicationTitle"] = "Journal Name"
    template["date"] = "2024"
    template["DOI"] = doi
    template["tags"] = [{"tag": "topic-tag"}, {"tag": "project-name"}]
    template["collections"] = ["COLLECTION_KEY"]  # Always assign a collection
    response = zot.create_items([template])
    item_key = list(response["successful"].values())[0]["key"]

    # Step 3: Add note (recommended for every item)
    add_note(zot, item_key, """
    <h2>Reading Note</h2>
    <p><b>Key findings:</b></p>
    <ul><li>Finding 1</li><li>Finding 2</li></ul>
    """)

    # Step 4 (optional): Upload PDF
    zot.attachment_simple(["path/to/paper.pdf"], item_key)
```

### Create a Collection

```python
result = zot.create_collections([{
    "name": "New Collection",
    "parentCollection": False  # or parent collection key for sub-collections
}])
col_key = list(result["successful"].values())[0]["key"]
```

### Batch Create (up to 50 items per API call)

```python
items = [zot.item_template("journalArticle") for _ in range(len(papers))]
for t, p in zip(items, papers):
    t["title"] = p["title"]
    t["DOI"] = p["doi"]
    t["creators"] = [{"creatorType": "author", "firstName": a[0], "lastName": a[1]} for a in p["authors"]]
result = zot.create_items(items)  # max 50 per call
```

> For all item type templates (journalArticle, conferencePaper, book, bookSection, thesis, report, webpage, etc.), see `references/item-types.md`.

---

## 4. UPDATE Operations (Web API — Requires API Key)

Updates use PATCH with optimistic locking (version-based).

```python
# Update metadata
item = zot.item("ITEM_KEY")
item["data"]["title"] = "Updated Title"
item["data"]["date"] = "2026-04"
zot.update_item(item["data"])

# Add tags (preserve existing)
item = zot.item("ITEM_KEY")
item["data"]["tags"].append({"tag": "new-tag"})
zot.update_item(item["data"])

# Remove a tag
item["data"]["tags"] = [t for t in item["data"]["tags"] if t["tag"] != "old-tag"]
zot.update_item(item["data"])

# Move item to collection
item = zot.item("ITEM_KEY")
item["data"]["collections"].append("TARGET_COLLECTION_KEY")
zot.update_item(item["data"])

# Update note content
note = zot.item("NOTE_KEY")
note["data"]["note"] = "<h1>Updated Notes</h1><p>Revised analysis.</p>"
zot.update_item(note["data"])

# Batch update (max 50 per call)
items_to_update = [zot.item(k) for k in keys]
for item in items_to_update:
    item["data"]["tags"].append({"tag": "batch-processed"})
zot.update_items([i["data"] for i in items_to_update])
```

---

## 5. DELETE Operations (Web API — Requires API Key)

The local API does NOT support DELETE (returns 501). All deletion goes through Web API.

```python
# Move single item to trash
item = zot.item("ITEM_KEY")
zot.delete_item(item)  # moves to trash, recoverable for 30 days

# Delete a note
note = zot.item("NOTE_KEY")
zot.delete_item(note)

# Delete a collection (items inside are NOT deleted)
collection = zot.collection("COLLECTION_KEY")
zot.delete_collection(collection)

# Batch delete items by tag
items = zot.items(tag="TO-DELETE", limit=50)
if items:
    zot.delete_item(items)  # accepts list of item dicts
```

> Permanent deletion from trash is only available via Zotero desktop UI (right-click → "Delete Permanently"). Items in trash are auto-purged after 30 days.

---

## 6. Error Handling

| Code | Meaning | Fix |
|------|---------|-----|
| 400 | Bad Request | Check JSON format; local API returns this for unsupported POST |
| 403 | Forbidden | Missing `Zotero-Allowed-Request` header (local) or invalid API key (web) |
| 404 | Not Found | Item/collection key doesn't exist |
| 409/412 | Version conflict | Re-fetch item to get latest version, then retry |
| 429 | Rate limited | Wait and retry (check `Retry-After` header); use `safe_api_call()` |
| 501 | Not Implemented | Local API doesn't support this method — use Web API |

**Version conflict recovery:**

```python
from pyzotero import zotero_errors
try:
    zot.update_item(item["data"])
except zotero_errors.PreConditionError:
    fresh = zot.item(item["data"]["key"])
    fresh["data"]["title"] = "Updated title"
    zot.update_item(fresh["data"])
```

---

## 7. Quick Reference

### Read Endpoints (Local API)
```
GET localhost:23119/api/users/{ID}/items?q=QUERY&limit=N
GET localhost:23119/api/users/{ID}/items/ITEMKEY
GET localhost:23119/api/users/{ID}/items/ITEMKEY/children
GET localhost:23119/api/users/{ID}/collections
GET localhost:23119/api/users/{ID}/collections/COLLKEY/items
GET localhost:23119/api/users/{ID}/tags
GET localhost:23119/api/users/{ID}/items/trash
```

### Write Endpoints (Web API)
```
POST   api.zotero.org/users/{ID}/items          (create)
POST   api.zotero.org/users/{ID}/collections    (create collection)
PATCH  api.zotero.org/users/{ID}/items/ITEMKEY  (update)
DELETE api.zotero.org/users/{ID}/items/ITEMKEY  (delete)
DELETE api.zotero.org/users/{ID}/items?itemKey=K1,K2  (batch delete)
```

---

## Bundled Resources

| Resource | Description | When to read |
|----------|-------------|-------------|
| `config.json` | API credentials + collection mappings | Auto-loaded by `get_client()` |
| `references/item-types.md` | JSON templates for all item types | When creating items — find the right template |
| `references/api-reference.md` | Full Zotero API endpoint docs | When you need detailed parameter info |
| `scripts/zotero_client.py` | Shared Python client | Import for any Zotero operation |
| `scripts/add_literature.py` | Batch import script template | When adding many items at once |

---

*Last updated: 2026-04-05*