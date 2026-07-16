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
import re
import stat
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import warnings
from pathlib import Path

# Reconfigure stdout to UTF-8 when possible; some embedding contexts replace
# sys.stdout with an object that has no reconfigure() (ZOT-COMPAT-022).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# Only these keys are read from ~/.claude/.env — never pull unrelated secrets
# from a shared .env into process memory (ZOT-CRED-012).
_ENV_KEYS = ("ZOTERO_API_KEY", "ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_TYPE")

# Local API settings
LOCAL_API_BASE = "http://localhost:23119/api"
LOCAL_API_HEADERS = {"Zotero-Allowed-Request": "true"}


def _warn_if_world_readable(path: Path) -> None:
    """Warn (do not fail) when a plaintext credential file is group/other-readable.

    POSIX only: on Windows the mode bits always report group/other-read regardless
    of the real ACL (and ``chmod 600`` is a no-op), so the check would fire on every
    run with no way to comply — worse than nothing. Skip it there (ZOT-CRED-012).
    """
    if os.name != "posix":
        return
    try:
        mode = path.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            warnings.warn(
                f"Credential file {path} is group/other-readable; restrict it "
                f"(chmod 600) to protect the Zotero API key.",
                stacklevel=2,
            )
    except OSError:
        pass


def _load_config():
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_env_file() -> dict[str, str]:
    """Read only the ZOTERO_* credentials from ~/.claude/.env if present.

    Never loads unrelated secrets from a shared .env into memory (ZOT-CRED-012).
    """

    env_values: dict[str, str] = {}
    env_file = Path.home() / ".claude" / ".env"
    if not env_file.exists():
        return env_values
    _warn_if_world_readable(env_file)
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _ENV_KEYS:
            continue
        value = value.strip()
        # Strip an inline trailing comment for UNQUOTED values (e.g. `KEY=abc  # note`);
        # leave quoted values intact so a legitimate '#' inside quotes is preserved.
        if value[:1] not in ("'", '"'):
            hash_pos = value.find(" #")
            if hash_pos != -1:
                value = value[:hash_pos].rstrip()
        env_values[key] = value.strip('"').strip("'")
    return env_values


def _load_credentials() -> tuple[str | None, str | None, str]:
    """Resolve Zotero credentials: env vars > ~/.claude/.env > config.json (deprecated).

    Consults config.json only when it exists AND creds are still missing, so an
    env-only or explicit-arg caller never hits a raw FileNotFoundError (ZOT-ROB-018).
    """

    api_key = os.environ.get("ZOTERO_API_KEY")
    lib_id = os.environ.get("ZOTERO_LIBRARY_ID")
    lib_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")

    if not api_key or not lib_id:
        env_values = _read_env_file()
        if not api_key:
            api_key = env_values.get("ZOTERO_API_KEY")
        if not lib_id:
            lib_id = env_values.get("ZOTERO_LIBRARY_ID")
        lib_type = env_values.get("ZOTERO_LIBRARY_TYPE", lib_type)

    if (not api_key or not lib_id) and _CONFIG_PATH.exists():
        warnings.warn(
            "Reading Zotero credentials from plaintext config.json is deprecated. "
            "Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID as environment variables or in ~/.claude/.env",
            DeprecationWarning,
            stacklevel=2,
        )
        _warn_if_world_readable(_CONFIG_PATH)
        cfg = _load_config()
        if not api_key:
            api_key = cfg.get("zotero_api_key")
        if not lib_id:
            lib_id = cfg.get("zotero_library_id")
        lib_type = cfg.get("zotero_library_type", lib_type)

    return api_key, lib_id, lib_type


def check_local_api(timeout=2, library_id=None) -> bool:
    """Test if the Zotero desktop local API is reachable on loopback.

    Uses the caller's own library id (arg, else ``ZOTERO_LIBRARY_ID`` env) so the
    probe is not tied to any one account (ZOT-SEC-002). A concrete HTTP response
    — even a 4xx for a mismatched id — means Zotero is listening, so it counts as
    reachable; only connection/timeout errors count as unavailable.
    """
    if library_id is None:
        library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    if library_id:
        url = f"{LOCAL_API_BASE}/users/{library_id}/items?limit=1"
    else:
        url = f"{LOCAL_API_BASE}/"
    try:
        req = urllib.request.Request(url, headers=LOCAL_API_HEADERS)
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        # Server answered (Zotero is up) though with an HTTP error status.
        return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def get_client():
    """Create authenticated Zotero Web API client from env, .env, or config."""
    from pyzotero import zotero

    api_key, lib_id, lib_type = _load_credentials()
    return zotero.Zotero(lib_id, lib_type, api_key)


def get_collection(name: str) -> str:
    """Get collection key by short name (e.g., 'paper3_wrr').

    Requires a config.json with a 'collections' map. In the preferred env/.env-only
    setup there may be no config.json — give a clear, actionable error (ZOT-ROB-018).
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"get_collection() needs a 'collections' map in config.json at {_CONFIG_PATH}, "
            "which is absent. Pass the collection key directly, or copy config.example.json "
            "to config.json and add your collection names."
        )
    cfg = _load_config()
    collections = cfg.get("collections", {})
    key = collections.get(name)
    if not key:
        raise KeyError(
            f"Collection '{name}' not found in config.json. "
            f"Available: {list(collections.keys())}"
        )
    return key


def add_note(zot, item_key: str, content: str) -> bool:
    """Add a note to an existing Zotero item. Auto-wraps plain text in <p> tags.

    Surfaces write failures (raises ``ZoteroWriteError`` on a rejected item) rather
    than silently returning False — consistent with the client's create_* methods
    (ZOT-SILENT-007). Let API/network errors propagate to the caller."""
    note = zot.item_template("note")
    if not content.strip().startswith("<"):
        content = f"<p>{content}</p>"
    note["note"] = content
    note["parentItem"] = item_key
    r = zot.create_items([note])
    _raise_on_write_failure(r)
    return bool(r.get("successful"))


def check_duplicate(zot, title: str, doi: str = "") -> bool:
    """Check if item already exists in Zotero by DOI or title."""
    query = doi or title[:50]
    existing = zot.items(q=query, limit=5)
    return any(
        e.get("data", {}).get("title", "").lower() == title.lower()
        or (doi and e.get("data", {}).get("DOI", "") == doi)
        for e in existing
    )


def _is_rate_limited(exc: Exception) -> bool:
    """True if an exception represents an HTTP 429 (typed check preferred)."""
    try:
        from pyzotero import zotero_errors
        if isinstance(exc, zotero_errors.TooManyRequestsError):
            return True
    except Exception:
        pass
    for attr in ("status_code", "code", "status"):
        if getattr(exc, attr, None) == 429:
            return True
    resp = getattr(exc, "response", None)
    if resp is not None and getattr(resp, "status_code", None) == 429:
        return True
    return "429" in str(exc)  # last-resort fallback


def safe_api_call(func, *args, max_retries=3, **kwargs):
    """Retry an API call with exponential backoff on rate limiting (429)."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if _is_rate_limited(e):
                wait = 2 ** attempt
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded")


class ZoteroWriteError(RuntimeError):
    """Raised when a Zotero write reports items in its ``failed`` bucket."""


def _raise_on_write_failure(resp):
    """Surface pyzotero's ``failed`` bucket instead of silently passing (ZOT-SILENT-007).

    The failed map is ``{index: {"code", "message"}}`` and contains no credentials.
    """
    failed = (resp or {}).get("failed") or {}
    if failed:
        raise ZoteroWriteError(f"Zotero write reported {len(failed)} failed item(s): {failed}")
    return resp


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

        resolved_api_key, resolved_lib_id, lib_type = _load_credentials()
        self.user_id = user_id or resolved_lib_id
        self.api_key = api_key or resolved_api_key

        # Web client for writes (needs API key) — also used as fallback for reads
        self.web = zotero.Zotero(self.user_id, lib_type, self.api_key)

        # Test local API connectivity before creating local client
        self.local_available = check_local_api(library_id=self.user_id)

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
                error_str = str(e).lower()
                # A lost connection permanently disables local for this session.
                if any(k in error_str for k in ["connection", "timeout", "refused", "urlopen"]):
                    print(f"[ZoteroDualClient] Local API lost connection: {e}")
                    print("[ZoteroDualClient] Switching to Web API for remaining operations")
                    self.local_available = False
                    self.local = self.web
                    return getattr(self.web, method_name)(*args, **kwargs)
                # A local cache miss (item not yet synced to desktop) — retry this
                # one read on the Web API without disabling local (ZOT-REL-008).
                if "404" in error_str or "not found" in error_str:
                    return getattr(self.web, method_name)(*args, **kwargs)
                raise  # Genuine caller error — surface it
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

    def _web_item(self, key):
        """Read an item from the AUTHORITATIVE Web API so its version matches the
        write target (never source a write version from the local channel, ZOT-COR-004)."""
        return self.web.item(key)

    # --- WRITE (web API only — local API does not support writes) ---
    def create_item(self, item_data):
        self._require_web()
        return _raise_on_write_failure(self.web.create_items([item_data]))

    def create_items(self, items_list):
        self._require_web()
        results = []
        for i in range(0, len(items_list), 50):
            batch = items_list[i:i + 50]
            results.append(_raise_on_write_failure(self.web.create_items(batch)))
        return results

    def create_note(self, parent_key, title, content, tags=None):
        self._require_web()
        # Emit the title heading; wrap only genuinely inline content. Suppress the
        # injected heading ONLY when the content already opens with a heading whose
        # text equals `title` — never silently drop a distinct title (ZOT-COR-016).
        body = content if content.lstrip().startswith("<") else f"<p>{content}</p>"
        lead = re.match(r"\s*<h[1-6][^>]*>(.*?)</h[1-6]>", content, re.I | re.S)
        lead_text = lead.group(1).strip().lower() if lead else None
        if not title or (lead_text is not None and lead_text == title.strip().lower()):
            note_html = body
        else:
            note_html = f"<h1>{title}</h1>{body}"
        note = {
            "itemType": "note",
            "parentItem": parent_key,
            "note": note_html,
            "tags": [{"tag": t} for t in (tags or [])],
        }
        return _raise_on_write_failure(self.web.create_items([note]))

    def create_collection(self, name, parent_key=False):
        self._require_web()
        return _raise_on_write_failure(self.web.create_collections(
            [{"name": name, "parentCollection": parent_key}]
        ))

    # --- UPDATE (web API; version read from the authoritative Web API) ---
    def update_item(self, key, updates: dict):
        self._require_web()
        item = self._web_item(key)  # version must come from the Web API (ZOT-COR-004)
        for field, value in updates.items():
            item["data"][field] = value
        return self.web.update_item(item["data"])

    def add_tags(self, key, new_tags: list):
        self._require_web()
        item = self._web_item(key)
        existing = [t["tag"] for t in item["data"].get("tags", [])]
        for tag in new_tags:
            if tag not in existing:
                item["data"].setdefault("tags", []).append({"tag": tag})
        return self.web.update_item(item["data"])

    def remove_tags(self, key, tags_to_remove: list):
        self._require_web()
        item = self._web_item(key)
        item["data"]["tags"] = [
            t for t in item["data"].get("tags", []) if t["tag"] not in tags_to_remove
        ]
        return self.web.update_item(item["data"])

    def add_to_collection(self, item_key, collection_key):
        """Add the item to a collection. This ADDS a membership; it does NOT
        remove the item from any collection it is already in (ZOT-COR-014)."""
        self._require_web()
        item = self._web_item(item_key)
        item["data"].setdefault("collections", [])
        if collection_key not in item["data"]["collections"]:
            item["data"]["collections"].append(collection_key)
        return self.web.update_item(item["data"])

    # Back-compat alias; note the true semantics are "add" not "move".
    move_to_collection = add_to_collection

    # --- TRASH (recoverable — preferred default, ZOT-DEL-003) ---
    def trash_item(self, key):
        """Move an item to the trash (RECOVERABLE, auto-purged after ~30 days) by
        setting ``deleted=1``. Prefer this over ``delete_item``, which is PERMANENT.

        Empirically verified: the Web API ``DELETE`` does NOT trash (it removes the
        item outright), and pyzotero's ``update_item`` rejects the ``deleted`` field,
        so trashing is issued as a direct PATCH against the authoritative Web API
        (API key stays in a header over TLS; version comes from the Web read)."""
        self._require_web()
        item = self._web_item(key)
        version = item["data"]["version"]
        safe_key = urllib.parse.quote(str(key), safe="")  # defense-in-depth on path interpolation
        url = f"{self.web.endpoint}/{self.web.library_type}/{self.web.library_id}/items/{safe_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps({"deleted": 1}).encode("utf-8"),
            method="PATCH",
            headers={
                "Zotero-API-Key": self.api_key,
                "Zotero-API-Version": "3",
                "If-Unmodified-Since-Version": str(version),
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 204)

    def trash_items(self, keys: list):
        return [self.trash_item(k) for k in keys]

    # --- DELETE (web API — PERMANENT, not recoverable) ---
    def delete_item(self, key):
        """PERMANENTLY delete an item (NOT recoverable — it does not go to the
        trash). Use ``trash_item`` for a recoverable removal (ZOT-DEL-003)."""
        self._require_web()
        item = self._web_item(key)  # authoritative version for the delete
        return self.web.delete_item(item)

    def delete_items(self, keys: list):
        """PERMANENTLY delete items (NOT recoverable). Deletes PER ITEM so each uses
        its own fresh version. pyzotero's batch ``delete_item(list)`` sends the first
        item's version as a *library*-level ``If-Unmodified-Since-Version`` and 412s
        as soon as items have differing versions (ZOT-COR-025, seen in real-API
        testing). Prefer ``trash_items`` for a recoverable removal."""
        self._require_web()
        return [self.delete_item(k) for k in keys]

    def delete_collection(self, collection_key):
        self._require_web()
        coll = self.web.collection(collection_key)
        return self.web.delete_collection(coll)

    # --- TEMPLATES ---
    def get_template(self, item_type="journalArticle"):
        return self.web.item_template(item_type)
