# API Setup

This skill routes operations through two APIs automatically:

| | Local API | Web API |
|---|---|---|
| **Base URL** | `http://localhost:23119/api` | `https://api.zotero.org` |
| **Auth** | Header: `Zotero-Allowed-Request: true` | Header: `Zotero-API-Key: <key>` |
| **Capabilities** | **Read-only** (GET) | **Full CRUD** (GET/POST/PATCH/DELETE) |
| **Speed** | Very fast (localhost) | Standard (network) |
| **Rate limit** | None | ~100 req / 10 sec |
| **Requires** | Zotero desktop running | API key |

**Routing rules:**
- **Search & Read** → Local API (via MCP tools or direct HTTP) — fast, no key needed
- **Create / Update / Delete** → Web API (via pyzotero) — requires API key
- **Fallback** → If Zotero desktop is closed, all operations go through Web API automatically

> **Warning:** MCP write tools (`zotero_create_note`, `zotero_batch_update_tags`) use the local API and **will fail** with 400/501 errors. Always use pyzotero for writes.

## Getting API Credentials

1. Go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys)
2. Click **"Create new private key"** — enable **Library Read/Write** and **Allow write access**
3. Copy the key and your **Library ID** (shown on the same page)
4. Store in `config.json` (see `config.example.json` for format) or environment variables:

```bash
export ZOTERO_API_KEY="your_key_here"
export ZOTERO_LIBRARY_ID="your_library_id"
export ZOTERO_LIBRARY_TYPE="user"
```

## Using the Shared Client

```python
import sys
sys.path.insert(0, r"~/.claude/skills/zotero-skills/scripts")
from zotero_client import get_client, get_collection, add_note, check_duplicate, ZoteroDualClient

# Option A: Web API client (for writes)
zot = get_client()  # reads credentials from config.json or env vars

# Option B: Dual client (local reads + web writes, auto-fallback)
dual = ZoteroDualClient()
results = dual.search("flood adaptation")            # local API if available
dual.create_note("ITEM_KEY", "Section", "Notes...")  # always web API
```

**Available functions in `zotero_client.py`:**

| Function | Description |
|---|---|
| `get_client()` | Configured `pyzotero.Zotero` Web API instance |
| `get_collection(name)` | Find collection key by display name from `config.json` |
| `add_note(zot, item_key, content)` | Attach a child note to a library item |
| `check_duplicate(zot, title, doi)` | Check if item with given title or DOI exists |
| `check_local_api(timeout)` | Test if Zotero desktop local API is reachable |
| `ZoteroDualClient` | Dual-API wrapper with auto-fallback |
| `safe_api_call(func)` | Wrapper with automatic rate-limit backoff |
