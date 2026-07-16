# Error Handling

| Code | Meaning | Fix |
|------|---------|-----|
| 400 | Bad Request | Check JSON format; local API returns this for unsupported POST |
| 403 | Forbidden | Missing `Zotero-Allowed-Request` header (local) or invalid API key (web) |
| 404 | Not Found | Item / collection key doesn't exist |
| 409 / 412 | Version conflict | Re-fetch item to get latest version, then retry |
| 429 | Rate limited | Back off and retry; use `safe_api_call()` |
| 501 | Not Implemented | Local API doesn't support this method — use Web API |

## Version-conflict recovery

pyzotero raises `PreConditionFailedError` (412) / `ConflictError` (409) on a stale version. Re-fetch and retry:

```python
from pyzotero import zotero_errors
try:
    zot.update_item(item["data"])
except zotero_errors.PreConditionFailedError:
    fresh = zot.item(item["data"]["key"])
    fresh["data"]["title"] = "Updated title"
    zot.update_item(fresh["data"])
```

## Partial batch failure (`ZoteroWriteError`)

`ZoteroDualClient.create_item` / `create_items` / `create_note` / `create_collection` inspect
pyzotero's `failed` bucket and **raise `zotero_client.ZoteroWriteError`** if any item failed —
they do not silently return a partial-success payload. Catch it to inspect which items failed:

```python
from zotero_client import ZoteroDualClient, ZoteroWriteError

dual = ZoteroDualClient()
try:
    dual.create_items(items)
except ZoteroWriteError as e:
    print("some items were rejected:", e)  # message includes the failed index -> code/message map
```

## Rate-limit handling

The Web API rate limit is approximately 100 requests / 10 seconds (the server also
signals backoff via `Backoff` / `Retry-After` response headers). The shared client's
`safe_api_call()` retries on `429` with a fixed **exponential backoff** (`2**attempt`
seconds); it does not currently read the `Retry-After` header. Prefer it over hand-rolling retries.

```python
from zotero_client import safe_api_call

result = safe_api_call(lambda: zot.create_items(items))
```
