# READ Operations (Local API — No Key Required)

Use MCP tools for reads when Zotero desktop is running. All GET requests go to `http://localhost:23119/api/users/{LIBRARY_ID}/...`.

## MCP Tools (Recommended for Reads)

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

## Direct HTTP (Python)

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
