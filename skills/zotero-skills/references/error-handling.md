# Error Handling

| Code | Meaning | Fix |
|------|---------|-----|
| 400 | Bad Request | Check JSON format; local API returns this for unsupported POST |
| 403 | Forbidden | Missing `Zotero-Allowed-Request` header (local) or invalid API key (web) |
| 404 | Not Found | Item / collection key doesn't exist |
| 409 / 412 | Version conflict | Re-fetch item to get latest version, then retry |
| 429 | Rate limited | Wait and retry (check `Retry-After` header); use `safe_api_call()` |
| 501 | Not Implemented | Local API doesn't support this method — use Web API |

## Version-conflict recovery

```python
from pyzotero import zotero_errors
try:
    zot.update_item(item["data"])
except zotero_errors.PreConditionError:
    fresh = zot.item(item["data"]["key"])
    fresh["data"]["title"] = "Updated title"
    zot.update_item(fresh["data"])
```

## Rate-limit handling

The Web API rate limit is roughly 100 requests / 10 seconds. The shared client wraps calls with `safe_api_call()` which automatically backs off on `429` responses; prefer it over hand-rolling retries.

```python
from zotero_client import safe_api_call

result = safe_api_call(lambda: zot.create_items(items))
```
