# UPDATE Operations (Web API — Requires API Key)

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

> Version-conflict (409 / 412) recovery patterns live in `error-handling.md`.
> Full PATCH endpoint reference lives in `api-reference.md`.
