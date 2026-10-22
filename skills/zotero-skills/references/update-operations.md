# UPDATE Operations (Web API — Requires API Key)

Item updates use PATCH; collection metadata updates use PUT. Both use
optimistic locking (version-based).

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

# Add item to a collection (preserves all existing memberships)
dual.add_to_collection("ITEM_KEY", "TARGET_COLLECTION_KEY")

# Remove only one membership (preserves all others)
dual.remove_from_collection("ITEM_KEY", "SOURCE_COLLECTION_KEY")

# Move from one named collection to another while preserving unrelated memberships
dual.move_to_collection(
    "ITEM_KEY", "TARGET_COLLECTION_KEY",
    from_collection_key="SOURCE_COLLECTION_KEY",
)

# Rename a collection; update_collection also accepts parentCollection
dual.rename_collection("COLLECTION_KEY", "New name")

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

> Version-conflict (409 / 412) recovery patterns live in `error-handling.md`.
> Full PATCH endpoint reference lives in `api-reference.md`.
