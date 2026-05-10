# Zotero Web API Reference (deep-dive supplement)

Pair with `create-operations.md` / `update-operations.md` / `delete-operations.md` for the day-to-day pyzotero patterns. This file covers the underlying raw HTTP shapes plus the collection-membership operations that don't fit cleanly into a single CRUD verb.

## Raw create request body

When you need to bypass `pyzotero` and POST directly:

```
POST https://api.zotero.org/users/{userID}/items
Content-Type: application/json
Zotero-API-Key: {apiKey}
```

Body:

```json
{
  "items": [
    {
      "itemType": "journalArticle",
      "title": "Paper Title",
      "creators": [
        {"creatorType": "author", "firstName": "First", "lastName": "Last"}
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
      "tags": [{"tag": "Task-050"}, {"tag": "Memory"}],
      "relations": {},
      "notes": [
        {"itemType": "note", "note": "<p>Note content in HTML</p>"}
      ]
    }
  ]
}
```

Success response (`201 Created`):

```json
{
  "successful": {
    "0": {"key": "XNCU5J2T", "version": 1234, "data": {...}}
  },
  "unchanged": {},
  "failed": {}
}
```

## Add a child note via the template (alternative to `add_note`)

The shared client's `add_note(zot, item_key, content)` helper is the recommended path. If you need to control more fields:

```python
note = zot.item_template("note")
note["note"] = "<p>Content</p>"
note["parentItem"] = "PARENTKEY"
zot.create_items([note])
```

## Collection-membership operations

`create-operations.md` covers assigning a collection at creation time and `update-operations.md` covers the simple `.append()` move. Less common patterns:

```python
# List all collections (with parent info)
cols = zot.collections()
for c in cols:
    parent = c["data"].get("parentCollection", "ROOT")
    print(f"{c['key']}: {c['data']['name']} (parent: {parent})")
```

```python
# Remove an item from a collection (preserves all other collection memberships)
item = zot.item("ITEM_KEY")
cols = item["data"].get("collections", [])
cols.remove("COL_KEY_TO_REMOVE")
item["data"]["collections"] = cols
zot.update_item(item)
```

```python
# Check which collections an item belongs to
item = zot.item("ITEM_KEY")
print(item["data"].get("collections", []))  # list of collection keys
```

```python
# Get items in a collection (alternative to the direct HTTP read in read-operations.md)
items = zot.collection_items("COL_KEY")
for item in items:
    print(f"{item['key']}: {item['data']['title']}")
```

## Creator types

| Type | Description |
|---|---|
| `author` | Paper author |
| `editor` | Book / journal editor |
| `translator` | Translator |
| `contributor` | General contributor |

For full item-type schemas (`journalArticle`, `book`, `conferencePaper`, etc. with their field lists), see `item-types.md`.

## Upstream references

- Zotero Web API v3 write spec: <https://www.zotero.org/support/dev/web_api/v3/write_requests>
- pyzotero: <https://pyzotero.readthedocs.io/>
