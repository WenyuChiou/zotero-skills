---
name: zotero-skills
description: Full CRUD operations on Zotero library — search, add, update, delete items with notes, tags, collections, and PDF attachments. Uses dual-API architecture (local API for fast reads, Web API for writes). Use when needing to read or write items to Zotero.
---

# Zotero Library Management Skill — Full CRUD Reference

Complete workflow for managing Zotero references: search, add, classify, annotate, update, delete, and organize.

## API Setup Guide

### Getting Your Zotero API Key

1. Go to https://www.zotero.org/settings/keys
2. Click **"New Key"** or **"Create new private key"**
3. Grant these permissions:
   - Library: Read/Write (required for write operations)
   - Notes: Read/Write (required for note creation)
   - Allow write access: **Enabled**
4. Click **Create** and copy the key
5. Store the key securely in:
   - **Option A (Recommended):** `~/.claude/skills/zotero-skills/config.json` under `"zotero_api_key"`
   - **Option B:** Environment variable `ZOTERO_API_KEY`

### Finding Your Library ID

1. Go to https://www.zotero.org/settings/keys (same page as API key)
2. Your **Library ID** is displayed on the page (e.g., `14772686`)
3. Store it in:
   - **Option A (Recommended):** `~/.claude/skills/zotero-skills/config.json` under `"zotero_library_id"`
   - **Option B:** Environment variable `ZOTERO_LIBRARY_ID`

### Setting Up Environment Variables

If not using `config.json`, set these environment variables in your shell or IDE:

**PowerShell:**
```powershell
$env:ZOTERO_API_KEY = "your_key_here"
$env:ZOTERO_LIBRARY_ID = "14772686"
$env:ZOTERO_LIBRARY_TYPE = "user"
```

**Bash:**
```bash
export ZOTERO_API_KEY="your_key_here"
export ZOTERO_LIBRARY_ID="14772686"
export ZOTERO_LIBRARY_TYPE="user"
```

**Python (in scripts):**
```python
import os
os.environ["ZOTERO_API_KEY"] = "your_key_here"
os.environ["ZOTERO_LIBRARY_ID"] = "14772686"
```

---

## API Routing Strategy

This skill uses **two different APIs** for different operations. Understanding which to use prevents errors.

### Search & Read Operations: Use Local API (Zotero MCP)

| Operation | Recommended Tool | API | Speed | Key Required | Example |
|---|---|---|---|---|---|
| Search items | MCP: `zotero_search_items` | Local API | Very Fast | No | Find papers by keyword |
| Get item details | MCP: `zotero_get_item_metadata` | Local API | Fast | No | Retrieve paper metadata |
| List collections | MCP: `zotero_get_collections` | Local API | Fast | No | Show all folders |
| Get notes | MCP: `zotero_get_notes` | Local API | Fast | No | Read reading notes |
| List tags | MCP: `zotero_get_tags` | Local API | Fast | No | Show all tags |

**Advantages:**
- No rate limiting
- Works offline (when Zotero desktop is open)
- Localhost (http://localhost:23119/api)
- No credentials required (only header: `Zotero-Allowed-Request: true`)

**Important:** These tools work ONLY when Zotero desktop application is running.

### Write Operations: Use Web API (pyzotero or direct HTTP)

| Operation | Recommended Tool | API | Key Required | Example |
|---|---|---|---|---|
| Create item | pyzotero: `zot.create_items()` | Web API | **YES** | Add new paper to library |
| Add note | pyzotero: `add_note()` function | Web API | **YES** | Add reading notes |
| Update tags | pyzotero: `zot.update_item()` | Web API | **YES** | Add/remove tags |
| Update metadata | pyzotero: `zot.update_item()` | Web API | **YES** | Change title or date |
| Create collection | pyzotero: `zot.create_collections()` | Web API | **YES** | New folder |
| Delete item | pyzotero: `zot.delete_item()` | Web API | **YES** | Move to trash |

**Advantages:**
- Full CRUD support (Create, Read, Update, Delete)
- Works even if Zotero desktop is closed
- Rate limit: 100 requests per 10 seconds per IP

**Disadvantages:**
- Slower than local API
- Requires API key
- Subject to rate limiting

**Web API base URL:** `https://api.zotero.org`

### Fallback: When Local API Unavailable

If Zotero desktop is not running or local API is not accessible on `localhost:23119`, pyzotero automatically handles BOTH read and write via the Web API (slower but complete).

### Why MCP Write Tools Will Fail

The Zotero MCP connector (`zotero_create_note`, `zotero_batch_update_tags`, etc.) is configured with `ZOTERO_LOCAL=true`, which means:

- It uses `http://localhost:23119/api` (local API only)
- Local API does NOT support write operations
- Attempted writes return:
  - `400 Endpoint does not support method` (for POST)
  - `501 Method not implemented` (for PATCH/DELETE)

**Do not use MCP write tools.** Instead:

1. **Use pyzotero for Python code:**
   ```python
   from zotero_client import get_client, add_note
   zot = get_client()
   zot.create_items([template])
   add_note(zot, item_key, html)
   ```

2. **Use Web API directly for PowerShell:**
   ```powershell
   $h = @{
     "Zotero-API-Key" = "your_key"
     "Zotero-API-Version" = "3"
     "Content-Type" = "application/json"
   }
   Invoke-WebRequest -Uri "https://api.zotero.org/users/14772686/items" -Method POST -Headers $h -Body $json
   ```

3. **Updating MCP Config (Optional, not recommended):**
   If you want to enable MCP write tools, set `ZOTERO_LOCAL=false` in claude_desktop_config.json. Trade-off: all reads become slower (network instead of localhost).

---

## Dual-API Architecture

This skill uses two API surfaces depending on the operation:

| API | Base URL | Auth | Capabilities |
|-----|----------|------|-------------|
| **Local API** | `http://localhost:23119/api` | Header: `Zotero-Allowed-Request: true` | **Read-only** (GET) |
| **Web API** | `https://api.zotero.org` | Header: `Zotero-API-Key: <key>` | **Full CRUD** (GET/POST/PATCH/DELETE) |

**User ID:** `14772686`
**Library Type:** `user`

### Critical Architecture Decision
- The Zotero local API (port 23119) **does NOT support write operations**.
  - POST → returns `400 Endpoint does not support method`
  - PATCH → returns `501 Method not implemented`
  - DELETE → returns `501 Method not implemented`
- All write/update/delete operations MUST go through the **Web API** with an API key.
- The existing Zotero MCP connector (`zotero_*` tools) is configured with `ZOTERO_LOCAL=true`,
  so its write tools (`zotero_create_note`, `zotero_batch_update_tags`) **will fail**.
- **Hybrid approach:** Keep `ZOTERO_LOCAL=true` for fast reads via MCP, and use pyzotero / direct Web API calls for write operations.

---

## 1. Setup

### 1.1 Zotero MCP Server (Read Operations)

Install and configure a Zotero MCP server for read operations (`zotero_search_items`, `zotero_get_collections`, etc.). Add it to your `.mcp.json` or MCP settings.

### 1.2 pyzotero (Write Operations)

```bash
pip install pyzotero
```

### 1.3 API Credentials (Centralized)

Credentials and collection keys are stored in `~/.claude/skills/zotero-skills/config.json`. This is the **single source of truth** — no more hardcoding in scripts.

```json
// ~/.claude/skills/zotero-skills/config.json
{
  "zotero_api_key": "hLGhkxO20sXiKpMF62mGDeG2",
  "zotero_library_id": "14772686",
  "zotero_library_type": "user",
  "collections": {
    "parent": "MDMG47ZS",
    "paper1b_nature_water": "UM8N5CRU",
    "paper3_wrr": "XZ22GHJA",
    "wrr_intro": "4KDW9UZ9",
    "wrr_comparable": "4BJS58TX",
    "pmt_behavior": "6AFGP7RT",
    "bounded_rationality": "QD723EMF",
    "flood_adaptation": "AQP8NC4V",
    "flood_insurance": "YSSPJU2R"
  }
}
```

### 1.4 Required Headers

**Local API (reads only):**
```
Zotero-Allowed-Request: true
Zotero-API-Version: 3
```

**Web API (full CRUD):**
```
Zotero-API-Key: <your_key>
Zotero-API-Version: 3
Content-Type: application/json
```

---

## 2. Prerequisites — Use the Shared Client

```python
import sys
sys.path.insert(0, r"C:\Users\wenyu\.claude\skills\zotero-skills\scripts")
from zotero_client import get_client, get_collection, add_note, check_duplicate

zot = get_client()  # Reads from config.json automatically
collection_key = get_collection("paper3_wrr")  # Lookup by short name
```

The shared client (`scripts/zotero_client.py`) handles:
- Credential loading from `config.json` (falls back to env vars)
- `get_client()` — authenticated Zotero Web API instance
- `get_collection(name)` — lookup collection key by short name
- `add_note(zot, item_key, html)` — add structured note
- `check_duplicate(zot, title, doi)` — prevent duplicate entries
- `ZoteroDualClient` — advanced class using local API for reads + Web API for writes

---

## 3. READ Operations (Local API — Fast, No Key Required)

All GET requests go to `http://localhost:23119/api/users/14772686/...`
with header `Zotero-Allowed-Request: true`.

### 3.1 List Items

```powershell
# Get top-level items (default: JSON format)
$h = @{ "Zotero-Allowed-Request" = "true"; "Zotero-API-Version" = "3" }
$r = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items/top?limit=25&format=json" -Headers $h

# Get item keys only (lightweight)
$r = Invoke-WebRequest -Uri "http://localhost:23119/api/users/14772686/items?limit=50&format=keys" -Headers $h
```

```bash
# curl equivalent
curl -s -H "Zotero-Allowed-Request: true" \
  "http://localhost:23119/api/users/14772686/items/top?limit=25&format=json"
```

**Query Parameters:**
| Param | Description | Example |
|-------|------------|---------|
| `limit` | Max items (default 25, max 100) | `limit=50` |
| `start` | Offset for pagination | `start=25` |
| `sort` | Sort field | `sort=dateModified` |
| `direction` | Sort direction | `direction=desc` |
| `format` | Response format | `format=json`, `format=keys`, `format=bibtex` |
| `q` | Quick search query | `q=flood adaptation` |
| `qmode` | Search mode | `qmode=titleCreatorYear` or `qmode=everything` |
| `tag` | Filter by tag | `tag=ABM` |
| `itemType` | Filter by type | `itemType=journalArticle` |
| `since` | Items modified since version | `since=1000` |

### 3.2 Get Single Item

```powershell
$h = @{ "Zotero-Allowed-Request" = "true" }
$item = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items/I3P2J58S" -Headers $h
$item.data.title  # "Long-term household flood adaptation..."
$item.data.DOI    # "10.5194/egusphere-egu26-12778"
$item.data.tags   # Array of {tag, type} objects
```

### 3.3 Get Item Children (notes, attachments)

```powershell
$children = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items/I3P2J58S/children" -Headers $h
```

### 3.4 List Collections

```powershell
$collections = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/collections?format=json" -Headers $h
# Each collection has: key, data.name, data.parentCollection, meta.numItems
```

### 3.5 Get Collection Items

```powershell
$items = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/collections/GH5CN2ZZ/items?format=json" -Headers $h
```

### 3.6 List Tags

```powershell
$tags = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/tags" -Headers $h
```

### 3.7 Search Items

```powershell
# Search by title/creator/year
$results = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items?q=agent-based+model&qmode=titleCreatorYear&limit=10&format=json" -Headers $h

# Search everything (including full-text)
$results = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items?q=flood+insurance&qmode=everything&limit=10&format=json" -Headers $h

# Filter by tag
$results = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items?tag=ABM&format=json" -Headers $h

# Filter by item type
$results = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items?itemType=journalArticle&format=json" -Headers $h

# Multiple tags (AND logic - use multiple tag params)
$results = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items?tag=ABM&tag=flood-adaptation&format=json" -Headers $h

# Exclude tag (prefix with -)
$results = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items?tag=-TO-DELETE&format=json" -Headers $h
```

### 3.8 Get Trash Items

```powershell
$trash = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items/trash?format=json" -Headers $h
```

### 3.9 Get Saved Searches

```powershell
$searches = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/searches" -Headers $h
```

---

## 4. CREATE Operations (Web API — Requires API Key)

All POST requests go to `https://api.zotero.org/users/14772686/...`

### Workflow: Adding Literature

Always follow this sequence:

#### Step 1: Check for Duplicates (MCP or pyzotero)

Before adding ANY item, search Zotero to avoid duplicates:

```
Use MCP tool: zotero_search_items with the paper title or DOI
```

Or via pyzotero (more reliable for DOI matching):

```python
# Prefer DOI search (most reliable)
if doi:
    existing = zot.items(q=doi, limit=5)
else:
    existing = zot.items(q=title[:50], limit=5)

# Check for match
is_duplicate = any(
    e["data"]["title"].lower() == title.lower()
    or e["data"].get("DOI", "") == doi
    for e in existing
)
```

If found, skip creation. If the existing item needs updates (notes, collections, tags), go to Step 5.

#### Step 2: Create Item

```python
template = zot.item_template("journalArticle")  # See Item Types below
template["title"] = "Paper Title"
template["creators"] = [{"creatorType": "author", "firstName": "First", "lastName": "Last"}]
template["publicationTitle"] = "Journal Name"
template["date"] = "2024"
template["DOI"] = "10.xxxx/xxxxx"
template["abstractNote"] = "Abstract text"
template["tags"] = [{"tag": "Project-Name"}, {"tag": "Topic-Tag"}]  # See Tag Convention
template["collections"] = ["YOUR_COLLECTION_KEY"]  # MANDATORY - See Classification Guide

response = zot.create_items([template])
item_key = list(response["successful"].values())[0]["key"]
```

**PowerShell equivalent (direct Web API):**

```powershell
$key = "hLGhkxO20sXiKpMF62mGDeG2"
$h = @{
    "Zotero-API-Key" = $key
    "Zotero-API-Version" = "3"
    "Content-Type" = "application/json"
}
$body = @'
[{
  "itemType": "journalArticle",
  "title": "Paper Title",
  "creators": [
    {"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}
  ],
  "publicationTitle": "Journal Name",
  "date": "2024",
  "DOI": "10.xxxx/xxxxx",
  "tags": [{"tag": "ABM"}],
  "collections": ["YOUR_COLLECTION_KEY"],
  "relations": {}
}]
'@
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$r = Invoke-WebRequest -Uri "https://api.zotero.org/users/14772686/items" -Method POST -Headers $h -Body $bytes
$result = $r.Content | ConvertFrom-Json
$newKey = $result.success.'0'
```

#### Step 3: Add Note (MANDATORY)

Every item MUST have a structured note. Use the appropriate template:

```python
note_html = """
<h2>Reading Note</h2>
<p><b>Cited in:</b> Your paper/project, Section X.Y</p>
<p><b>Role:</b> Brief description of how this reference is used.</p>
<p><b>Key findings:</b></p>
<ul>
  <li>Finding 1</li>
  <li>Finding 2</li>
</ul>
"""
add_note(zot, item_key, note_html)
```

**PowerShell equivalent (child note via Web API):**

```powershell
$body = @'
[{
  "itemType": "note",
  "parentItem": "ITEM_KEY_HERE",
  "note": "<h1>Reading Notes</h1><p>Key findings...</p>",
  "tags": [{"tag": "reading-notes"}]
}]
'@
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$r = Invoke-WebRequest -Uri "https://api.zotero.org/users/14772686/items" -Method POST -Headers $h -Body $bytes
```

#### Step 4: Upload PDF (Optional)

```python
from pathlib import Path
pdf_path = Path("path/to/paper.pdf")
zot.attachment_simple([str(pdf_path)], item_key)
```

### 4.1 Create a Standalone Note

```json
[{
  "itemType": "note",
  "note": "<h1>Research Planning</h1><p>Next steps for the ABM flood project...</p>",
  "tags": [{"tag": "planning"}],
  "collections": ["GH5CN2ZZ"]
}]
```

### 4.2 Create a Collection

```powershell
$body = '[{"name": "Flood Insurance Literature", "parentCollection": false}]'
$r = Invoke-WebRequest -Uri "https://api.zotero.org/users/14772686/collections" `
  -Method POST -Headers $h -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result = ($r.Content | ConvertFrom-Json)
$newCollKey = $result.success.'0'
```

```python
# Python — create sub-collection
result = zot.create_collections([{
    "name": "Flood Insurance Literature",
    "parentCollection": "MDMG47ZS"
}])
col_key = list(result["successful"].values())[0]["key"]
```

### 4.3 Batch Create (Multiple Items at Once)

The API accepts up to **50 items per POST request**.

```python
items = []
for paper in papers_to_add:
    t = zot.item_template("journalArticle")
    t["title"] = paper["title"]
    t["DOI"] = paper["doi"]
    t["creators"] = [{"creatorType": "author", "firstName": a.split()[0], "lastName": a.split()[-1]} for a in paper["authors"]]
    t["tags"] = [{"tag": tag} for tag in paper["tags"]]
    t["collections"] = [paper.get("collection_key", "")]
    items.append(t)

# Split into batches of 50
for i in range(0, len(items), 50):
    batch = items[i:i+50]
    result = zot.create_items(batch)
    print(f"Batch {i//50 + 1}: {len(result.get('success', {}))} created, {len(result.get('failed', {}))} failed")
```

---

## 5. UPDATE Operations (Web API — Requires API Key)

### 5.1 Update Item Metadata

Updates use PATCH with the `If-Unmodified-Since-Version` header for optimistic locking.

```python
# Python — update item
item = zot.item("I3P2J58S")
item["data"]["title"] = "Updated Title Here"
item["data"]["date"] = "2026-04"
zot.update_item(item["data"])
```

```powershell
# PowerShell — Step 1: Get current version
$h_read = @{ "Zotero-Allowed-Request" = "true" }
$item = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items/I3P2J58S" -Headers $h_read
$version = $item.version

# Step 2: PATCH via Web API
$h_write = @{
    "Zotero-API-Key" = $key
    "Zotero-API-Version" = "3"
    "Content-Type" = "application/json"
    "If-Unmodified-Since-Version" = "$version"
}
$patch = @{ title = "Updated Title Here"; date = "2026-04" } | ConvertTo-Json
$r = Invoke-WebRequest -Uri "https://api.zotero.org/users/14772686/items/I3P2J58S" `
  -Method PATCH -Headers $h_write -Body ([System.Text.Encoding]::UTF8.GetBytes($patch))
```

### 5.2 Update Tags on an Item

```python
item = zot.item("I3P2J58S")
# Add new tags while preserving existing ones
existing_tags = item["data"]["tags"]
new_tags = existing_tags + [{"tag": "new-category"}, {"tag": "reviewed"}]
item["data"]["tags"] = new_tags
zot.update_item(item["data"])

# Remove a specific tag
item["data"]["tags"] = [t for t in item["data"]["tags"] if t["tag"] != "TO-DELETE"]
zot.update_item(item["data"])
```

### 5.3 Move Item to / Remove from Collection

```python
# Add to collection
item = zot.item("I3P2J58S")
if "YSSPJU2R" not in item["data"]["collections"]:
    item["data"]["collections"].append("YSSPJU2R")
    zot.update_item(item["data"])

# Remove from collection
item["data"]["collections"] = [c for c in item["data"]["collections"] if c != "YSSPJU2R"]
zot.update_item(item["data"])
```

### 5.4 Update Note Content

```python
note = zot.item("NOTE_KEY")
note["data"]["note"] = "<h1>Updated Notes</h1><p>Revised analysis after re-reading...</p>"
zot.update_item(note["data"])
```

### 5.5 Update Collection Name

```python
collection = zot.collection("GH5CN2ZZ")
collection["data"]["name"] = "ABM — Agent-Based Models"
zot.update_collection(collection["data"])
```

### 5.6 Batch Update Items

```python
# Update multiple items at once (max 50 per call)
items_to_update = []
for key in ["KEY1", "KEY2", "KEY3"]:
    item = zot.item(key)
    item["data"]["tags"].append({"tag": "batch-processed"})
    items_to_update.append(item["data"])

zot.update_items(items_to_update)
```

---

## 6. DELETE Operations (Web API — Requires API Key)

### CRITICAL: Deletion Strategy

The Zotero local API does NOT support DELETE (returns 501).
All deletion must go through the Web API.

**Two-stage deletion:**
1. **Move to Trash** — item remains recoverable for 30 days
2. **Permanent Delete** — item is gone forever (use with extreme caution)

### 6.1 Move Single Item to Trash

```python
# Python — move to trash
item = zot.item("ITEM_KEY")
zot.delete_item(item)  # Moves to trash by default
```

```powershell
# PowerShell — get version first, then DELETE via Web API
$h_read = @{ "Zotero-Allowed-Request" = "true" }
$item = Invoke-RestMethod -Uri "http://localhost:23119/api/users/14772686/items/ITEM_KEY" -Headers $h_read
$version = $item.version

$h_del = @{
    "Zotero-API-Key" = $key
    "Zotero-API-Version" = "3"
    "If-Unmodified-Since-Version" = "$version"
}
$r = Invoke-WebRequest -Uri "https://api.zotero.org/users/14772686/items/ITEM_KEY" `
  -Method DELETE -Headers $h_del
# Returns 204 No Content on success
```

### 6.2 Batch Delete Multiple Items

```powershell
# Delete up to 50 items at once using itemKey parameter
$keys = "KEY1,KEY2,KEY3"
$r = Invoke-WebRequest -Uri "https://api.zotero.org/users/14772686/items?itemKey=$keys" `
  -Method DELETE -Headers $h_del
```

```python
# Python — batch delete
items = zot.items(tag="TO-DELETE", limit=50)
if items:
    zot.delete_item(items)  # Accepts list of item dicts
```

### 6.3 Delete a Collection

```python
collection = zot.collection("COLLECTION_KEY")
zot.delete_collection(collection)
# Note: This deletes the collection only, NOT the items in it
```

### 6.4 Delete a Note

```python
note = zot.item("NOTE_KEY")
zot.delete_item(note)
```

### 6.5 Permanently Delete from Trash

There is no direct API endpoint for permanent deletion from trash.
Items in trash are automatically purged after 30 days.
To permanently delete immediately, use Zotero's desktop UI:
1. Go to Trash in Zotero
2. Right-click → "Delete Item(s) Permanently..."

---

## 7. Item Types & JSON Templates

### Item Type Reference

| Type | Template Name | When to Use |
|------|--------------|-------------|
| Journal article | `journalArticle` | Peer-reviewed papers |
| Conference paper | `conferencePaper` | Conference proceedings |
| Book | `book` | Monographs |
| Book section | `bookSection` | Chapter in edited volume |
| Preprint | `preprint` | arXiv, SSRN, working papers |
| Thesis | `thesis` | PhD/Master dissertations |
| Report | `report` | Technical reports, government docs |
| Webpage | `webpage` | Online resources |

### 7.1 Journal Article (Full Template)

```json
{
  "itemType": "journalArticle",
  "title": "",
  "creators": [
    {"creatorType": "author", "firstName": "", "lastName": ""}
  ],
  "abstractNote": "",
  "publicationTitle": "",
  "volume": "",
  "issue": "",
  "pages": "",
  "date": "",
  "series": "",
  "seriesTitle": "",
  "journalAbbreviation": "",
  "language": "en",
  "DOI": "",
  "ISSN": "",
  "shortTitle": "",
  "url": "",
  "accessDate": "",
  "extra": "",
  "tags": [],
  "collections": [],
  "relations": {}
}
```

### 7.2 Conference Paper

```json
{
  "itemType": "conferencePaper",
  "title": "",
  "creators": [
    {"creatorType": "author", "firstName": "", "lastName": ""}
  ],
  "abstractNote": "",
  "date": "",
  "proceedingsTitle": "",
  "conferenceName": "",
  "place": "",
  "publisher": "",
  "volume": "",
  "pages": "",
  "series": "",
  "language": "en",
  "DOI": "",
  "ISBN": "",
  "url": "",
  "tags": [],
  "collections": [],
  "relations": {}
}
```

### 7.3 Book

```json
{
  "itemType": "book",
  "title": "",
  "creators": [
    {"creatorType": "author", "firstName": "", "lastName": ""}
  ],
  "abstractNote": "",
  "series": "",
  "volume": "",
  "edition": "",
  "place": "",
  "publisher": "",
  "date": "",
  "numPages": "",
  "language": "en",
  "ISBN": "",
  "url": "",
  "tags": [],
  "collections": [],
  "relations": {}
}
```

### 7.4 Book Section

```json
{
  "itemType": "bookSection",
  "title": "",
  "creators": [
    {"creatorType": "author", "firstName": "", "lastName": ""},
    {"creatorType": "editor", "firstName": "", "lastName": ""}
  ],
  "abstractNote": "",
  "bookTitle": "",
  "series": "",
  "volume": "",
  "edition": "",
  "place": "",
  "publisher": "",
  "date": "",
  "pages": "",
  "language": "en",
  "ISBN": "",
  "url": "",
  "tags": [],
  "collections": [],
  "relations": {}
}
```

### 7.5 Report

```python
template = zot.item_template("report")
template["title"] = "Report Title"
template["creators"] = [{"creatorType": "author", "lastName": "Organization", "firstName": ""}]
template["institution"] = "Issuing Institution"
template["date"] = "2024"
template["reportNumber"] = "Report-001"
template["url"] = "https://example.org/report"
template["collections"] = ["YOUR_COLLECTION_KEY"]
```

### 7.6 Note (Standalone or Child)

```json
{
  "itemType": "note",
  "parentItem": "",
  "note": "<p>Note content with <strong>HTML formatting</strong></p>",
  "tags": [{"tag": "note-tag"}],
  "collections": [],
  "relations": {}
}
```

*Omit `parentItem` or set to `""` for standalone notes.*
*Set `parentItem` to a valid item key (e.g., `"I3P2J58S"`) for child notes.*

### 7.7 Collection

```json
{
  "name": "Collection Name",
  "parentCollection": false
}
```

*Set `parentCollection` to a collection key for sub-collections, or `false` for top-level.*

### Creator Types by Item Type
- **journalArticle**: `author`, `contributor`, `editor`, `translator`, `reviewedAuthor`
- **conferencePaper**: `author`, `contributor`, `editor`, `translator`, `seriesEditor`
- **book**: `author`, `contributor`, `editor`, `translator`, `seriesEditor`
- **bookSection**: `author`, `contributor`, `editor`, `translator`, `bookAuthor`, `seriesEditor`
- **thesis**: `author`, `contributor`
- **report**: `author`, `contributor`, `translator`, `seriesEditor`

---

## 8. Classification Guide

### Collection Hierarchy

Organize your Zotero collections to mirror your project structure:

```
MDMG47ZS  Parent/
  XZ22GHJA    paper3_wrr/
    4KDW9UZ9      wrr_intro
    4BJS58TX      wrr_comparable
  UM8N5CRU    paper1b_nature_water/
  6AFGP7RT    pmt_behavior
  QD723EMF    bounded_rationality
  AQP8NC4V    flood_adaptation
  YSSPJU2R    flood_insurance
```

> **Tip:** Find your collection keys via MCP (`zotero_get_collections`) or in the Zotero web UI URL. Update `config.json` when adding new collections.

### Auto-Classification Rules

Assign to a **primary** collection always; add **secondary** if a paper spans topics.

| Keywords in title/abstract | Primary Collection | Key |
|---|---|---|
| flood adaptation, household adaptation | flood_adaptation | `AQP8NC4V` |
| flood insurance, NFIP, premium | flood_insurance | `YSSPJU2R` |
| PMT, protection motivation | pmt_behavior | `6AFGP7RT` |
| bounded rationality, heuristic | bounded_rationality | `QD723EMF` |

### Classification Priority

When multiple categories match, assign primary by priority (highest first):

1. **Empirical data source** (primary evidence)
2. **Domain application** (applied context)
3. **Theory/Method** (foundational frameworks)
4. **Infrastructure** (tooling, architecture)

All others become secondary collections.

---

## 9. Tag Convention

| Tag Pattern | Purpose | Example |
|---|---|---|
| `Project-Name` | Which project cites this | `My-Thesis` |
| `Section-X.Y` | Specific section reference | `Section-3.2` |
| Topic tags | Thematic classification | `Machine-Learning`, `Survey`, `Benchmark` |
| Status tags | Reading status | `To-Read`, `In-Progress`, `Done` |

---

## 10. Note Templates

### General Reading Note

```html
<h2>Reading Note</h2>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Role:</b> What this reference contributes to your work.</p>
<p><b>Key findings:</b></p>
<ul>
  <li>Finding 1</li>
  <li>Finding 2</li>
</ul>
<p><b>Relevance:</b> How this connects to your research question.</p>
```

### Theoretical Foundation

```html
<h2>Theory Reference</h2>
<p><b>Theory:</b> Name of theoretical framework</p>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Key contribution:</b> Core idea or model this paper introduces.</p>
<p><b>How we use it:</b> How the theory applies in your work.</p>
```

### Methodological Reference

```html
<h2>Methods Reference</h2>
<p><b>Method:</b> Name of method or technique</p>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Key idea:</b> What the method does and why it matters.</p>
<p><b>How we use/extend it:</b> Adaptations for your context.</p>
```

### Empirical Data Source

```html
<h2>Data Source</h2>
<p><b>Dataset/Metric:</b> Name and value range</p>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Key data:</b> What the paper reports (sample size, key statistics).</p>
<p><b>Methodology:</b> How the data was collected.</p>
<p><b>Limitations:</b> Scope constraints or caveats.</p>
```

---

## 11. Batch Import

For adding multiple references at once with duplicate checking and rate limiting:

```python
import time

items_to_add = [
    {
        "type": "journalArticle",
        "title": "Example Paper Title",
        "authors": [{"firstName": "A", "lastName": "B"}],
        "journal": "Journal Name",
        "year": "2024",
        "doi": "10.xxx",
        "collections": ["YOUR_COLLECTION_KEY"],
        "tags": ["Project-Name", "Topic-Tag"],
        "note": "<p><b>Cited in:</b> Section X.Y</p>",
    },
    # ... more items
]

created = 0
skipped = 0
failed = 0

for i, item_info in enumerate(items_to_add):
    # Step 1: Duplicate check (DOI preferred, fallback to title)
    query = item_info.get("doi") or item_info["title"][:50]
    existing = zot.items(q=query, limit=5)
    if any(
        e["data"]["title"].lower() == item_info["title"].lower()
        or (item_info.get("doi") and e["data"].get("DOI", "") == item_info["doi"])
        for e in existing
    ):
        print(f"[SKIP] Already exists: {item_info['title'][:50]}")
        skipped += 1
        continue

    # Step 2: Create item
    template = zot.item_template(item_info["type"])
    template["title"] = item_info["title"]
    template["creators"] = [
        {"creatorType": "author", "firstName": a["firstName"], "lastName": a["lastName"]}
        for a in item_info["authors"]
    ]
    if item_info["type"] == "journalArticle":
        template["publicationTitle"] = item_info.get("journal", "")
    elif item_info["type"] == "conferencePaper":
        template["conferenceName"] = item_info.get("conference", "")
    template["date"] = item_info.get("year", "")
    template["DOI"] = item_info.get("doi", "")
    template["tags"] = [{"tag": t} for t in item_info.get("tags", [])]
    template["collections"] = item_info.get("collections", [])

    response = zot.create_items([template])
    if response.get("successful"):
        key = list(response["successful"].values())[0]["key"]
        # Step 3: Add note (mandatory)
        if item_info.get("note"):
            add_note(zot, key, item_info["note"])
        print(f"[OK] {item_info['title'][:50]}... ({key})")
        created += 1
    else:
        reason = response.get("failed", {}).get("0", {}).get("message", "Unknown")
        print(f"[FAIL] {item_info['title'][:50]} — {reason}")
        failed += 1

    # Rate limit: Zotero allows 100 requests per 10 seconds
    if (i + 1) % 40 == 0:
        print(f"  [pause] {i+1} items processed, waiting 5s for rate limit...")
        time.sleep(5)

print(f"\nDone: {created} created, {skipped} skipped, {failed} failed")
```

---

## 12. Existing MCP Tools Reference

The Zotero MCP connector provides these tools. All use the local API for reads.

### Read/Search Tools (WORKING)

| Tool | Description | Key Parameters |
|------|------------|---------------|
| `zotero_search_items` | Search by query string | `query`, `qmode`, `item_type`, `tag`, `limit` |
| `zotero_get_item_metadata` | Get item details by key | `item_key`, `format`, `include_abstract` |
| `zotero_get_collections` | List all collections | `limit` |
| `zotero_get_collection_items` | Items in a collection | (collection key) |
| `zotero_get_tags` | List all tags | — |
| `zotero_search_by_tag` | Find items by tag | (tag name) |
| `zotero_get_item_children` | Notes/attachments for item | (item key) |
| `zotero_get_notes` | Get notes for item | (item key) |
| `zotero_get_annotations` | PDF annotations | (item key) |
| `zotero_get_item_fulltext` | Full text of attachment | (item key) |
| `zotero_get_recent` | Recently added items | — |
| `zotero_search_notes` | Search within notes | (query) |
| `zotero_semantic_search` | Semantic similarity search | (query) |
| `zotero_advanced_search` | Complex queries | — |
| `fetch` | Get fulltext/metadata by ID | `id` |

### Write Tools (BROKEN in local mode — use pyzotero / Web API instead)

| Tool | Status | Reason |
|------|--------|--------|
| `zotero_create_note` | **FAILS** (400) | Local API doesn't support POST |
| `zotero_batch_update_tags` | **FAILS** (400/501) | Local API doesn't support POST/PATCH |
| `zotero_update_search_database` | Works | Updates local semantic search DB only |

### Fixing MCP Write Tools (Optional)

To enable the MCP connector's write tools, update the Zotero MCP config to use the Web API:

1. Edit `%APPDATA%\Claude\claude_desktop_config.json`
2. Update the `zotero` entry:

```json
"zotero": {
  "command": "C:\\Users\\wenyu\\anaconda3\\envs\\zotero-mcp-env\\Scripts\\zotero-mcp.exe",
  "args": ["serve", "--transport", "stdio"],
  "env": {
    "ZOTERO_LOCAL": "false",
    "ZOTERO_API_KEY": "hLGhkxO20sXiKpMF62mGDeG2",
    "ZOTERO_LIBRARY_ID": "14772686",
    "ZOTERO_LIBRARY_TYPE": "user"
  }
}
```

3. Restart Claude Desktop

**Trade-off:** Switching to Web API makes writes work but reads become slower (network vs local).

---

## 13. Error Handling

### Common Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 200 | OK (GET) | Success |
| 204 | No Content | Success (DELETE/PATCH) |
| 400 | Bad Request | Check JSON format; local API returns this for unsupported methods (POST) |
| 403 | Forbidden | Missing `Zotero-Allowed-Request: true` header (local) or invalid API key (web) |
| 404 | Not Found | Item/collection key doesn't exist |
| 409 | Conflict | Version mismatch — re-fetch item, get new version, retry |
| 412 | Precondition Failed | `If-Unmodified-Since-Version` doesn't match; item was modified by another client |
| 413 | Request Entity Too Large | Payload exceeds max (try fewer items per batch) |
| 429 | Too Many Requests | Rate limited — wait and retry (check `Retry-After` header) |
| 501 | Not Implemented | Local API doesn't support this method (PATCH/DELETE) |

### Version Conflict Recovery

```python
from pyzotero import zotero_errors

try:
    zot.update_item(item["data"])
except zotero_errors.PreConditionError:
    # Re-fetch to get the latest version
    fresh_item = zot.item(item["data"]["key"])
    fresh_item["data"]["title"] = "Your updated title"
    zot.update_item(fresh_item["data"])
```

### Rate Limiting

```python
import time

def safe_api_call(func, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e):
                wait = 2 ** attempt  # Exponential backoff
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### Unicode / Encoding

Always use UTF-8 encoding when sending data:
```powershell
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$r = Invoke-WebRequest ... -Body $bytes
```

For Python on Windows console:
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

---

## 14. Integration with Knowledge-Base Skill

### Obsidian Sub-Category → Zotero Collection Mapping

When the knowledge-base skill creates Obsidian notes, use this mapping to also
add the paper to the corresponding Zotero collection:

```python
OBSIDIAN_TO_ZOTERO = {
    "ABM": "GH5CN2ZZ",
    "ABM/introduction": "95LER8AR",
    "ABM/Implication": "BLWKV8H9",
    "ABM/Flood damage": "RGWPTYWR",
    "ABM/Flood insurance": "YSSPJU2R",
    # Add more mappings as collections grow
}
```

### One-Command Pipeline — Zotero Steps

When processing a new paper through the research pipeline:

1. **Search Zotero** (MCP tool, local API): Check if the paper already exists
   ```
   zotero_search_items(query="paper title or DOI")
   ```

2. **Create Item** (Web API via pyzotero): If not found, create it
   ```python
   zot = get_client()  # from zotero_client.py
   template = zot.item_template("journalArticle")
   # ... fill template ...
   result = zot.create_items([template])
   ```

3. **Add to Collection** (Web API): Assign to appropriate collection
   ```python
   col_key = get_collection("flood_adaptation")  # from config.json
   # collection key is set in template["collections"] before creation
   ```

4. **Attach Note** (Web API): Add reading notes or AI summary
   ```python
   add_note(zot, new_key, note_html)
   ```

5. **Tag for Tracking** (Web API): Add status tags
   ```python
   item = zot.item(new_key)
   item["data"]["tags"].extend([{"tag": "to-read"}, {"tag": "pipeline-added"}])
   zot.update_item(item["data"])
   ```

---

## 15. Quick Reference Card

### Reads (Local API — always available)
```
GET http://localhost:23119/api/users/14772686/items?q=QUERY&limit=N
GET http://localhost:23119/api/users/14772686/items/ITEMKEY
GET http://localhost:23119/api/users/14772686/items/ITEMKEY/children
GET http://localhost:23119/api/users/14772686/collections
GET http://localhost:23119/api/users/14772686/collections/COLLKEY/items
GET http://localhost:23119/api/users/14772686/tags
GET http://localhost:23119/api/users/14772686/items/trash
GET http://localhost:23119/api/users/14772686/searches
Header: Zotero-Allowed-Request: true
```

### Writes (Web API — requires API key)
```
POST   https://api.zotero.org/users/14772686/items          (create items)
POST   https://api.zotero.org/users/14772686/collections    (create collections)
PATCH  https://api.zotero.org/users/14772686/items/ITEMKEY  (update item)
DELETE https://api.zotero.org/users/14772686/items/ITEMKEY  (delete item)
DELETE https://api.zotero.org/users/14772686/items?itemKey=K1,K2  (batch delete)
DELETE https://api.zotero.org/users/14772686/collections/COLLKEY  (delete collection)
Headers: Zotero-API-Key: KEY, Zotero-API-Version: 3, Content-Type: application/json
```

### All Item Types Available
`journalArticle`, `conferencePaper`, `book`, `bookSection`, `thesis`,
`report`, `webpage`, `preprint`, `manuscript`, `note`, `attachment`,
`document`, `presentation`, `computerProgram`, `patent`, `statute`,
`case`, `hearing`, `bill`, `map`, `artwork`, `film`, `podcast`,
`videoRecording`, `audioRecording`, `interview`, `letter`, `email`,
`instantMessage`, `forumPost`, `blogPost`, `encyclopediaArticle`,
`dictionaryEntry`, `magazineArticle`, `newspaperArticle`, `radioBroadcast`,
`tvBroadcast`

---

## 16. Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| 403 Forbidden | API key lacks write permission | Check https://www.zotero.org/settings/keys |
| Missing credentials | Env vars not set | Set `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` or use config.json |
| Item not appearing | Sync delay (1-10s) | Wait, then refresh Zotero desktop |
| PDF upload fails | File not found or invalid | Verify path exists, file > 1KB |
| Duplicate created | Skipped search step | Always search before creating |
| Orphaned item | No collection assigned | Always set `template["collections"]` |
| UnicodeEncodeError | Windows cp950 console | Add `sys.stdout.reconfigure(encoding='utf-8')` |
| Rate limit (429) | Too many requests | Add `time.sleep(5)` every 40 items |

## Bundled Resources

- `config.json` — API credentials and collection key mappings (single source of truth)
- `references/api-reference.md` — Full Zotero API documentation
- `references/item-types.md` — Item type field specifications
- `scripts/zotero_client.py` — Shared Python client with `get_client()`, `add_note()`, `check_duplicate()`, `ZoteroDualClient`
- `scripts/add_literature.py` — Reusable Python script template

---

*Last updated: 2026-04-05*
*Tested against: Zotero 7 desktop, local API port 23119, pyzotero in zotero-mcp-env*

