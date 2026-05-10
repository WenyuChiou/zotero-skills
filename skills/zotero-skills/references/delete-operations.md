# DELETE Operations (Web API — Requires API Key)

The local API does NOT support DELETE (returns 501). All deletion goes through the Web API.

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

## Safety patterns

- **Preview first.** For non-trivial deletes, list the item keys you intend to remove and show them to the user before calling `delete_item`.
- **Tag-based batches.** Apply a `TO-DELETE` tag in a separate pass, let the user audit, then run the tag-based batch above.
- **Collection-only deletes.** `delete_collection` removes the collection, not the items inside it. Items remain in the library (just unfiled). Use this when reorganising rather than removing literature.
