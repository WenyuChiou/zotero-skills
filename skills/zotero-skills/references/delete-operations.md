# DELETE Operations (Web API — Requires API Key)

The local API does NOT support DELETE (returns 501). All deletion goes through the Web API.

> ⚠️ **`delete_item` is PERMANENT, not trash.** Empirically verified against the live
> Zotero Web API: `DELETE /items/KEY` removes the item outright (a subsequent GET
> returns 404 and the item is **not** in the trash). This contradicts the older belief
> that the API "moves to trash" — it does not. For a **recoverable** removal use the
> shared client's `trash_item()` (which sets `deleted=1` via PATCH); items in the trash
> are auto-purged after ~30 days and can be restored until then.

```python
from zotero_client import ZoteroDualClient
dual = ZoteroDualClient()

# RECOVERABLE — move to trash (preferred default)
dual.trash_item("ITEM_KEY")          # sets deleted=1; restorable for ~30 days
dual.trash_items(["K1", "K2"])

# PERMANENT — irreversible, does NOT go to trash. Confirm the exact keys first.
dual.delete_item("ITEM_KEY")
dual.delete_items(["K1", "K2"])      # chunked by 50

# Delete a collection (items inside are NOT deleted, just unfiled)
dual.delete_collection("COLLECTION_KEY")
```

Raw pyzotero (note the same permanence):

```python
item = zot.item("ITEM_KEY")
zot.delete_item(item)  # PERMANENT — not recoverable via the API
```

## Safety patterns

- **Preview first.** For non-trivial deletes, list the item keys you intend to remove and show them to the user before calling `delete_item`.
- **Tag-based batches.** Apply a `TO-DELETE` tag in a separate pass, let the user audit, then run the tag-based batch above.
- **Collection-only deletes.** `delete_collection` removes the collection, not the items inside it. Items remain in the library (just unfiled). Use this when reorganising rather than removing literature.
