# Zotero Write API Reference

Detailed reference for the Zotero Web API write operations.

## API Endpoint

```
POST https://api.zotero.org/users/{userID}/items
Content-Type: application/json
Zotero-API-Key: {apiKey}
```

## Creating Items

### Request Body Format

```json
{
  "items": [
    {
      "itemType": "journalArticle",
      "title": "Paper Title",
      "creators": [
        {
          "creatorType": "author",
          "firstName": "First",
          "lastName": "Last"
        }
      ],
      "abstractNote": "Abstract text",
      "publicationTitle": "Journal Name",
      "volume": "63",
      "issue": "2",
      "pages": "81-97",
      "date": "1956",
      "DOI": "10.1037/h0043158",
      "ISSN": "",
      "url": "",
      "tags": [
        {"tag": "Task-050"},
        {"tag": "Memory"}
      ],
      "relations": {},
      "notes": [
        {
          "itemType": "note",
          "note": "<p>Note content in HTML</p>"
        }
      ]
    }
  ]
}
```

### Response

Success (201 Created):
```json
{
  "successful": {
    "0": {
      "key": "XNCU5J2T",
      "version": 1234,
      "data": { ... }
    }
  },
  "unchanged": {},
  "failed": {}
}
```

## pyzotero Methods

### Get Item Template

```python
template = zot.item_template("journalArticle")
# Returns dict with all available fields for item type
```

### Create Items

```python
response = zot.create_items([item1, item2, ...])
# Maximum 50 items per request
```

### Update Item

```python
item = zot.item("ITEMKEY")
item["data"]["title"] = "New Title"
zot.update_item(item)
```

### Delete Item

```python
zot.delete_item(item)  # Moves to trash
```

### Add Child Note

```python
note = zot.item_template("note")
note["note"] = "<p>Content</p>"
note["parentItem"] = "PARENTKEY"
zot.create_items([note])
```

## Collections

### Create Collection

```python
new_col = {
    "name": "Reinforcement-Learning",
    "parentCollection": "4EM52NPV",  # Parent key, or False for root-level
}
result = zot.create_collections([new_col])
col_key = list(result["successful"].values())[0]["key"]
```

### List Collections

```python
cols = zot.collections()
for c in cols:
    parent = c["data"].get("parentCollection", "ROOT")
    print(f"{c['key']}: {c['data']['name']} (parent: {parent})")
```

### Assign Item to Collection at Creation

```python
template = zot.item_template("journalArticle")
template["title"] = "Paper Title"
# ... other fields ...
template["collections"] = ["COL_KEY_1", "COL_KEY_2"]  # Assign before creating
response = zot.create_items([template])
```

### Assign Existing Item to Collection

```python
item = zot.item("ITEM_KEY")
current = item["data"].get("collections", [])
if "NEW_COL_KEY" not in current:
    current.append("NEW_COL_KEY")
    item["data"]["collections"] = current
    zot.update_item(item)
```

### Remove Item from Collection

```python
item = zot.item("ITEM_KEY")
cols = item["data"].get("collections", [])
cols.remove("COL_KEY_TO_REMOVE")
item["data"]["collections"] = cols
zot.update_item(item)
```

### Check Item's Collections

```python
item = zot.item("ITEM_KEY")
print(item["data"].get("collections", []))  # Returns list of collection keys
```

### Get Items in a Collection

```python
items = zot.collection_items("COL_KEY")
for item in items:
    print(f"{item['key']}: {item['data']['title']}")
```

## Item Types

| Type | Description |
|------|-------------|
| `journalArticle` | Journal paper |
| `book` | Book |
| `bookSection` | Chapter in book |
| `conferencePaper` | Conference paper |
| `thesis` | PhD/Master thesis |
| `preprint` | Preprint (arXiv, etc.) |
| `webpage` | Web page |
| `report` | Technical report |
| `note` | Standalone or child note |

## Creator Types

| Type | Description |
|------|-------------|
| `author` | Paper author |
| `editor` | Book/journal editor |
| `translator` | Translator |
| `contributor` | General contributor |

## Rate Limits

- 100 requests per 10 seconds per API key
- Batch operations recommended (up to 50 items per request)

## References

- Official Docs: https://www.zotero.org/support/dev/web_api/v3/write_requests
- pyzotero: https://pyzotero.readthedocs.io/
