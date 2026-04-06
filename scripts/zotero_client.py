r"""
Shared Zotero client -- single source of truth for credentials and helpers.

Usage from any script::

    import sys
    sys.path.insert(0, r"C:\Users\wenyu\.claude\skills\zotero-skills\scripts")
    from zotero_client import get_client, get_collection, add_note, check_duplicate

    zot = get_client()
    zot.create_items([...])

For dual-mode (local reads + web writes)::

    from zotero_client import ZoteroDualClient
    dual = ZoteroDualClient()
    results = dual.search("flood adaptation")
    dual.create_note("I3P2J58S", "My Notes", "Key findings...")
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# Local API settings
LOCAL_API_BASE = "http://localhost:23119/api"
LOCAL_API_HEADERS = {"Zotero-Allowed-Request": "true"}


def _load_config():
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_local_api(timeout=2) -> bool:
    """Test if Zotero desktop local API is reachable.

    Returns True if localhost:23119 responds, False otherwise.
    """
    try:
        req = urllib.request.Request(
            f"{LOCAL_API_BASE}/users/14772686/items?limit=1",
            headers=LOCAL_API_HEADERS,
        )
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def get_client():
    """Create authenticated Zotero Web API client from config.json."""
    from pyzotero import zotero

    cfg = _load_config()
    api_key = os.environ.get("ZOTERO_API_KEY", cfg["zotero_api_key"])
    lib_id = os.environ.get("ZOTERO_LIBRARY_ID", cfg["zotero_library_id"])
    lib_type = cfg.get("zotero_library_type", "user")
    return zotero.Zotero(lib_id, lib_type, api_key)


def get_collection(name: str) -> str:
    """Get collection key by short name (e.g., 'paper3_wrr')."""
    cfg = _load_config()
    key = cfg.get("collections", {}).get(name)
    if not key:
        raise KeyError(
            f"Collection '{name}' not found in config.json. "
            f"Available: {list(cfg['collections'].keys())}"
        )
    return key


def add_note(zot, item_key: str, content: str) -> bool:
    """Add a note to an existing Zotero item. Auto-wraps plain text in <p> tags."""
    note = zot.item_template("note")
    if not content.strip().startswith("<"):
        content = f"<p>{content}</p>"
    note["note"] = content
    note["parentItem"] = item_key
    try:
        r = zot.create_items([note])
        return bool(r.get("successful"))
    except Exception as e:
        print(f"  Note error for {item_key}: {e}")
        return False


def check_duplicate(zot, title: str, doi: str = "") -> bool:
    """Check if item already exists in Zotero by DOI or title."""
    query = doi or title[:50]
    existing = zot.items(q=query, limit=5)
    return any(
        e["data"]["title"].lower() == title.lower()
        or (doi and e["data"].get("DOI", "") == doi)
        for e in existing
    )


def safe_api_call(func, *args, max_retries=3, **kwargs):
    """Retry an API call with exponential backoff on rate limiting (429)."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e):
                wait = 2 ** attempt
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded")


class ZoteroDualClient:
    """Dual-mode Zotero client: local API for fast reads, Web API for writes.

    Automatically detects whether Zotero desktop is running.
    If local API is unreachable, all operations fall back to Web API.

    Usage::

        dual = ZoteroDualClient()          # reads config.json automatically
        results = dual.search("flood")     # fast local read (or web fallback)
        dual.create_note("KEY", "Title", "Content")  # web write
    """

    def __init__(self, user_id=None, api_key=None):
        from pyzotero import zotero

        cfg = _load_config()
        self.user_id = user_id or cfg["zotero_library_id"]
        self.api_key = api_key or os.environ.get("ZOTERO_API_KEY", cfg["zotero_api_key"])
        lib_type = cfg.get("zotero_library_type", "user")

        # Web client for writes (needs API key) — also used as fallback for reads
        self.web = zotero.Zotero(self.user_id, lib_type, self.api_key)

        # Test local API connectivity before creating local client
        self.local_available = check_local_api()

        if self.local_available:
            try:
                self.local = zotero.Zotero(self.user_id, lib_type, local=True)
                # Verify with a real request
                self.local.top(limit=1)
                print("[ZoteroDualClient] Local API connected (fast reads enabled)")
            except Exception as e:
                print(f"[ZoteroDualClient] Local API init failed: {e}")
                print("[ZoteroDualClient] Falling back to Web API for all operations")
                self.local = self.web
                self.local_available = False
        else:
            print("[ZoteroDualClient] Zotero desktop not running (localhost:23119 unreachable)")
            print("[ZoteroDualClient] Using Web API for all operations")
            self.local = self.web
            self.local_available = False

    def _read(self, method_name, *args, **kwargs):
        """Execute a read operation with automatic local-to-web fallback.

        Tries local API first (fast). If it fails, falls back to Web API.
        Updates self.local_available so subsequent calls skip local directly.
        """
        if self.local_available:
            try:
                return getattr(self.local, method_name)(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                # Connection refused, timeout, or other network error
                if any(k in error_str.lower() for k in ["connection", "timeout", "refused", "urlopen"]):
                    print(f"[ZoteroDualClient] Local API lost connection: {e}")
                    print("[ZoteroDualClient] Switching to Web API for remaining operations")
                    self.local_available = False
                    self.local = self.web
                else:
                    raise  # Re-raise non-connection errors
        # Web API fallback
        return getattr(self.web, method_name)(*args, **kwargs)

    def _require_web(self):
        if not self.api_key:
            raise ValueError(
                "Web API key required for write operations. "
                "Get one at https://www.zotero.org/settings/keys"
            )

    def status(self) -> dict:
        """Return current connection status."""
        return {
            "local_api": "connected" if self.local_available else "unavailable",
            "web_api": "connected" if self.api_key else "no API key",
            "read_source": "local (fast)" if self.local_available else "web",
            "write_source": "web",
        }

    # --- READ (local with web fallback) ---
    def search(self, query, limit=25, qmode="titleCreatorYear"):
        return self._read("items", q=query, qmode=qmode, limit=limit)

    def get_item(self, key):
        return self._read("item", key)

    def get_collections(self):
        return self._read("collections")

    def get_collection_items(self, collection_key, limit=100):
        return self._read("collection_items", collection_key, limit=limit)

    def get_tags(self):
        return self._read("tags")

    def get_children(self, key):
        return self._read("children", key)

    def search_by_tag(self, tag, limit=50):
        return self._read("items", tag=tag, limit=limit)

    # --- WRITE (web API only — local API does not support writes) ---
    def create_item(self, item_data):
        self._require_web()
        return self.web.create_items([item_data])

    def create_items(self, items_list):
        self._require_web()
        results = []
        for i in range(0, len(items_list), 50):
            batch = items_list[i:i + 50]
            results.append(self.web.create_items(batch))
        return results

    def create_note(self, parent_key, title, content, tags=None):
        self._require_web()
        if "<p>" not in content and "<h" not in content:
            content = f"<h1>{title}</h1><p>{content}</p>"
        note = {
            "itemType": "note",
            "parentItem": parent_key,
            "note": content,
            "tags": [{"tag": t} for t in (tags or [])],
        }
        return self.web.create_items([note])

    def create_collection(self, name, parent_key=False):
        self._require_web()
        return self.web.create_collections(
            [{"name": name, "parentCollection": parent_key}]
        )

    # --- UPDATE (web API, reads version from local/web) ---
    def update_item(self, key, updates: dict):
        self._require_web()
        item = self._read("item", key)  # Read version (local or web fallback)
        for field, value in updates.items():
            item["data"][field] = value
        return self.web.update_item(item["data"])

    def add_tags(self, key, new_tags: list):
        self._require_web()
        item = self._read("item", key)
        existing = [t["tag"] for t in item["data"]["tags"]]
        for tag in new_tags:
            if tag not in existing:
                item["data"]["tags"].append({"tag": tag})
        return self.web.update_item(item["data"])

    def remove_tags(self, key, tags_to_remove: list):
        self._require_web()
        item = self._read("item", key)
        item["data"]["tags"] = [
            t for t in item["data"]["tags"] if t["tag"] not in tags_to_remove
        ]
        return self.web.update_item(item["data"])

    def move_to_collection(self, item_key, collection_key):
        self._require_web()
        item = self._read("item", item_key)
        if collection_key not in item["data"]["collections"]:
            item["data"]["collections"].append(collection_key)
        return self.web.update_item(item["data"])

    # --- DELETE (web API) ---
    def delete_item(self, key):
        self._require_web()
        item = self._read("item", key)
        return self.web.delete_item(item)

    def delete_items(self, keys: list):
        self._require_web()
        items = [self._read("item", k) for k in keys]
        return self.web.delete_item(items)

    def delete_collection(self, collection_key):
        self._require_web()
        coll = self._read("collection", collection_key)
        return self.web.delete_collection(coll)

    # --- TEMPLATES ---
    def get_template(self, item_type="journalArticle"):
        return self.web.item_template(item_type)
