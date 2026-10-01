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
import shutil
import stat
import sys
import tempfile
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


_SAFE_FILENAME_MAX_LEN = 40  # keeps the copied path short even under a long temp-dir prefix
_SAFE_FILENAME_PREFIX = "zot_"
_SAFE_EXTENSION_RE = re.compile(r"^\.[A-Za-z0-9]{1,8}$")


def _safe_attachment_filename(original_name: str, override: str | None = None) -> str:
    """Derive a short, space-free, collision-safe filename for a temp copy
    used in PDF uploads.

    pyzotero's ``attachment_simple`` can fail SILENTLY against a long Windows
    path that contains spaces (ZOT-ATTACH-026) -- no exception, just an empty
    ``{"failure": [...]}`` entry with no explanation. Copying the file to a
    short, space-free name under a fresh temp directory sidesteps that failure
    mode entirely, regardless of how long or space-filled the original path is.

    Hardening (reviewer round 3):
    - The extension is kept only if it looks like a real one
      (``\\.[A-Za-z0-9]{1,8}``, e.g. ``.pdf``); a dotted but non-extension
      tail such as ``paper.final version for submission to journal`` falls
      back to ``.pdf`` instead of being treated as a 40-character extension.
    - The stem always gets a ``zot_`` prefix, so it can never collide with a
      Windows-reserved device name (``CON``, ``NUL``, ``PRN``, ``AUX``,
      ``COM1``-``COM9``, ``LPT1``-``LPT9``), which is reserved regardless of
      extension.
    - Non-ASCII letters (e.g. CJK titles) are kept; only whitespace and
      characters that are unsafe in a filename are stripped, so a non-Latin
      title does not collapse into a generic "attachment" name.
    """
    base = override if override else original_name
    base = base.strip()
    suffix = Path(base).suffix
    if not _SAFE_EXTENSION_RE.match(suffix):
        suffix = ".pdf"
    stem = Path(base).stem
    stem = re.sub(r"\s+", "_", stem)      # no spaces
    stem = re.sub(r"[^\w.-]", "", stem)   # drop anything unsafe; \w keeps non-ASCII letters
    stem = stem or "attachment"
    max_stem_len = max(1, _SAFE_FILENAME_MAX_LEN - len(suffix) - len(_SAFE_FILENAME_PREFIX))
    return f"{_SAFE_FILENAME_PREFIX}{stem[:max_stem_len]}{suffix}"


_LIBRARY_TYPE_PLURALS = {"user": "users", "group": "groups"}


def _pluralize_library_type(library_type: str) -> str:
    """Map a Zotero ``library_type`` to the real API path segment.

    Real pyzotero's ``Zotero.__init__`` already stores the plural form on the
    instance (``self.library_type = library_type + "s"``), so
    ``self.web.library_type`` is normally already "users" or "groups" by the
    time code here reads it, and a live merge confirmed the real shape is
    ``http://zotero.org/users/<libraryID>/items/<key>`` for a user library
    (``http://zotero.org/groups/...`` for a group one) -- never the singular
    "user"/"group" (ZOT-MERGE-027). This maps a singular value defensively in
    case one ever does reach here (e.g. a non-pyzotero web client or a test
    double); anything already plural, or anything else, passes through
    unchanged.
    """
    return _LIBRARY_TYPE_PLURALS.get(library_type, library_type)


_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def _normalize_doi(doi: str) -> str:
    """Normalize a DOI for equality comparison: strip, drop a leading
    resolver URL (``https://doi.org/``, ``http://doi.org/``,
    ``https://dx.doi.org/``, ``http://dx.doi.org/``, any case) or a
    ``doi:`` prefix (any case, with or without a following space), then
    lowercase what remains.

    DOIs are case-insensitive and are routinely pasted with a resolver
    prefix; comparing them raw (as before) refused merges of the same DOI
    typed two different ways (reviewer rounds 3-4)."""
    doi = (doi or "").strip()
    doi = _DOI_PREFIX_RE.sub("", doi, count=1)
    return doi.strip().lower()


def _normalize_title(title: str) -> str:
    """Normalize a title for a last-resort identity check when neither item
    has a DOI: strip, lowercase, collapse internal whitespace."""
    return re.sub(r"\s+", " ", (title or "").strip().lower())


_YEAR_RE = re.compile(r"(\d{4})")


def _extract_year(date_str: str) -> str:
    """Pull a 4-digit year out of a Zotero ``date`` field (which can be as
    messy as ``"May 2001"`` or as clean as ``"2001"``), or ``""`` if none
    is found."""
    m = _YEAR_RE.search(date_str or "")
    return m.group(1) if m else ""


def _first_creator_lastname(data: dict) -> str:
    """Normalized last name of an item's first creator, or ``""`` if it has
    none."""
    creators = data.get("creators") or []
    if not creators:
        return ""
    return (creators[0].get("lastName") or "").strip().lower()


def credentials_status() -> dict:
    """Report whether Zotero credentials are configured, and which layer
    they came from, WITHOUT ever returning the API key, the library ID, or
    any file contents. Safe to print or log.

    Call this instead of opening ``~/.claude/.env`` or ``config.json``: an
    agent that only checks the shell environment and finds nothing has not
    checked ``~/.claude/.env`` or ``config.json``, and will wrongly conclude
    writes are impossible (SKILL.md "Common false negatives" #1). This does
    the same env > ``~/.claude/.env`` > ``config.json`` resolution as
    ``_load_credentials()`` internally, and reports only booleans and a
    source label per field.
    """
    env_api_key = os.environ.get("ZOTERO_API_KEY")
    env_lib_id = os.environ.get("ZOTERO_LIBRARY_ID")

    dotenv_values = _read_env_file()
    dotenv_path = Path.home() / ".claude" / ".env"

    cfg: dict = {}
    config_readable = False
    if _CONFIG_PATH.exists():
        try:
            cfg = _load_config()
            config_readable = True
        except (OSError, ValueError):
            config_readable = False

    def _resolve(env_val, dotenv_key, cfg_key):
        if env_val:
            return True, "env"
        if dotenv_values.get(dotenv_key):
            return True, "~/.claude/.env"
        if cfg.get(cfg_key):
            return True, "config.json"
        return False, "none"

    api_key_set, api_key_source = _resolve(env_api_key, "ZOTERO_API_KEY", "zotero_api_key")
    library_id_set, library_id_source = _resolve(env_lib_id, "ZOTERO_LIBRARY_ID", "zotero_library_id")

    # Delegate library_type to _load_credentials() itself rather than a
    # hand-rolled precedence, so this always matches what ZoteroDualClient
    # will actually use, byte for byte. _load_credentials() has a quirk:
    # when api_key/lib_id need the ~/.claude/.env fallback, it ALSO
    # re-resolves lib_type from that file, even if the shell environment
    # already had a different (higher-precedence) lib_type -- reporting an
    # independently "clean" precedence here would silently disagree with
    # the real client (reviewer round 4).
    _, _, library_type = _load_credentials()

    return {
        "api_key_set": api_key_set,
        "api_key_source": api_key_source,
        "library_id_set": library_id_set,
        "library_id_source": library_id_source,
        "library_type": library_type,
        "dotenv_file_exists": dotenv_path.exists(),
        "config_json_exists": _CONFIG_PATH.exists(),
        "config_json_readable": config_readable,
    }


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

    def attach_pdf(self, parent_key: str, path, filename: str | None = None) -> dict:
        """Attach a PDF (or other file) to an existing item, via a short safe copy.

        Copies ``path`` into a fresh temp directory under a short, space-free
        filename (derived from the original basename unless ``filename`` is
        given), then calls pyzotero's ``attachment_both`` with that copy's
        path but the ORIGINAL (or ``filename``-overridden) basename as the
        displayed title -- so the Zotero item shows a readable name even
        though the uploaded file itself has the short, safe one. This avoids
        the SILENT failure ``attachment_simple``/``attachment_both`` can hit
        against a long Windows path containing spaces (ZOT-ATTACH-026): no
        exception is raised, it just returns ``{"failure": [...]}`` with no
        detail unless a caller checks for it. This method checks, and RAISES
        with whatever detail pyzotero's own ``failure`` list contains --
        never returns a result the caller might not look at.

        The temp copy is always removed afterward, success or failure.
        """
        self._require_web()
        src = Path(path)
        if not src.is_file():
            raise FileNotFoundError(f"No such file: {src}")

        safe_name = _safe_attachment_filename(src.name, filename)
        display_title = filename if filename else src.name
        tmp_dir = tempfile.mkdtemp(prefix="zotattach_")
        try:
            tmp_path = Path(tmp_dir) / safe_name
            shutil.copyfile(src, tmp_path)
            result = self.web.attachment_both([(display_title, str(tmp_path))], parent_key)
            failures = (result or {}).get("failure") or []
            if failures:
                raise ZoteroWriteError(
                    f"Zotero attachment upload failed for {len(failures)} file(s) "
                    f"attaching {src.name!r} to {parent_key}: {failures}"
                )
            return result
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

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
    def _patch_deleted_flag(self, key, flag: int) -> bool:
        """PATCH an item's ``deleted`` flag directly against the authoritative
        Web API. ``flag=1`` trashes, ``flag=0`` restores.

        Empirically verified: the Web API ``DELETE`` does NOT trash (it removes
        the item outright), and pyzotero's ``update_item`` rejects the
        ``deleted`` field (``check_items`` has no such field in its allowed-keys
        template), so this is issued as a direct PATCH (API key stays in a
        header over TLS; version comes from the Web read)."""
        self._require_web()
        item = self._web_item(key)
        version = item["data"]["version"]
        safe_key = urllib.parse.quote(str(key), safe="")  # defense-in-depth on path interpolation
        url = f"{self.web.endpoint}/{self.web.library_type}/{self.web.library_id}/items/{safe_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps({"deleted": flag}).encode("utf-8"),
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

    def trash_item(self, key):
        """Move an item to the trash (RECOVERABLE, auto-purged after ~30 days) by
        setting ``deleted=1``. Prefer this over ``delete_item``, which is
        PERMANENT. See ``restore_item`` to reverse this."""
        return self._patch_deleted_flag(key, 1)

    def trash_items(self, keys: list):
        return [self.trash_item(k) for k in keys]

    def restore_item(self, key):
        """Restore a trashed item (the reverse of ``trash_item``) by setting
        ``deleted=0``, via the same raw-PATCH technique (pyzotero's
        ``update_item`` rejects the ``deleted`` field either way)."""
        return self._patch_deleted_flag(key, 0)

    def restore_items(self, keys: list):
        return [self.restore_item(k) for k in keys]

    def merge_duplicates(self, keep_key: str, dup_key: str, require_same_doi: bool = True) -> dict:
        """Merge ``dup_key`` into ``keep_key`` (ZOT-MERGE-027).

        The Zotero Web API has no native merge endpoint -- only the desktop
        app's merge pane does this in one click. This reproduces the CORE of
        the desktop merge, over the Web API, as a sequence of ordinary writes:

          0. Refuse ``keep_key == dup_key`` (merging an item with itself would
             just trash it).
          1. Read both items from the Web API (authoritative version source,
             matching ``update_item`` / ``trash_item``, ZOT-COR-004).
          2. Refuse if either is a note, an attachment, or has a ``parentItem``
             (only top-level library items can be merged).
          3. Refuse if either item is already deleted/trashed (call
             ``restore_item()`` on it first), or if they fail the identity
             check: DOIs normalized (strip/drop a doi.org or dx.doi.org
             resolver prefix or a ``doi:`` prefix, any case/scheme, then
             lowercase) must match when at least one side has one; when
             BOTH are empty, the normalized title AND itemType must match,
             and EITHER the year or the first creator's last name must
             also match -- unless ``require_same_doi=False``.
          4. Move every child (notes AND attachments) of ``dup_key`` onto
             ``keep_key`` by setting each child's ``parentItem``, paginating
             with ``everything()`` so this is not silently capped at ~100
             children. A child that is itself already in the trash is
             SKIPPED (pyzotero's ``update_item`` rejects a payload carrying
             a ``deleted`` key) and reported, not silently dropped. If any
             (non-skipped) child move raises, the error is wrapped in
             ``ZoteroWriteError`` listing which child keys were already
             moved -- nothing has been trashed yet, so re-running this call
             is safe once the underlying error is fixed.
          5. Re-read ``keep`` fresh, right before writing it, so the union
             below is based on its latest version (not a copy that may have
             gone stale while children were being moved).
          6. Union ``dup``'s collections, tags, and own relations (any
             predicate, a bare string normalized to a one-item list, no
             duplicates) onto the freshly-read ``keep`` -- never drops
             anything ``keep`` already had. A relation value pointing back
             at ``keep`` itself is SKIPPED (Zotero's "Related" links are
             two-way, so ``dup`` commonly already has one pointing at
             ``keep``; copying it over would leave ``keep`` related to
             itself, which the desktop merge also avoids).
          7. Add the real Zotero item URI, e.g.
             ``http://zotero.org/users/<libraryID>/items/<dup_key>`` for a
             user library or ``http://zotero.org/groups/<libraryID>/items/<dup_key>``
             for a group library, to ``keep``'s ``relations['dc:replaces']``.
          8. ``trash_item(dup_key)`` LAST, once nothing useful is left on it.

        A failure updating ``keep`` (step 6/7) or trashing ``dup`` (step 8)
        is also wrapped in ``ZoteroWriteError``, stating plainly what has
        and has not happened yet (children ARE already moved either way;
        a step-6/7 failure means nothing was trashed; a step-8 failure
        means ``keep`` WAS updated but ``dup`` still needs trashing by
        hand).

        This does NOT do everything the desktop merge pane does: it does not
        repoint OTHER items' existing relations that reference ``dup_key``
        (those still point at a now-trashed item), does not reconcile
        ``dateAdded`` (desktop keeps the earliest), and does not deduplicate
        identical PDF attachments that end up as siblings on ``keep`` after
        the merge. Do those by hand if they matter for a given pair.

        CALLER MUST GET USER CONFIRMATION FIRST: step 8 trashes an item, which
        this skill's safety rules treat like any other delete -- confirm the
        keep/duplicate keys and titles with the user before calling this.

        Returns a summary dict: ``children_moved`` (count),
        ``skipped_deleted_children`` (keys left alone because they were
        already trashed), ``collections_added`` and ``tags_added`` (lists of
        what was newly added to ``keep``), ``relation`` (the dc:replaces URI
        added), ``trashed_key`` (``dup_key``).
        """
        self._require_web()
        if keep_key == dup_key:
            raise ValueError(f"Cannot merge an item with itself ({keep_key!r}).")

        keep_item = self._web_item(keep_key)
        dup_item = self._web_item(dup_key)
        keep_data = keep_item["data"]
        dup_data = dup_item["data"]

        # pyzotero / the Web API upper-case item keys, so two differently-cased
        # spellings of the same key (e.g. "abcd2345" vs "ABCD2345") would slip
        # past the raw `keep_key == dup_key` check above; compare the keys the
        # server actually returned too (reviewer round 4).
        if str(keep_data.get("key", "")).upper() == str(dup_data.get("key", "")).upper():
            raise ValueError(
                f"Cannot merge an item with itself ({keep_key!r} and {dup_key!r} "
                "resolve to the same item)."
            )

        for label, data in (("keep", keep_data), ("dup", dup_data)):
            if data.get("parentItem") or data.get("itemType") in ("note", "attachment"):
                raise ValueError(
                    f"Cannot merge: {label}={data.get('key')} is a child item "
                    f"(itemType={data.get('itemType')!r}, parentItem={data.get('parentItem')!r}); "
                    "only top-level library items can be merged."
                )

        if keep_data.get("deleted") or dup_data.get("deleted"):
            raise ValueError(
                f"Cannot merge: keep={keep_key} deleted={bool(keep_data.get('deleted'))}, "
                f"dup={dup_key} deleted={bool(dup_data.get('deleted'))}. Call restore_item() "
                "on the trashed one first, or pick a different pair."
            )

        if require_same_doi:
            keep_doi = _normalize_doi(keep_data.get("DOI", ""))
            dup_doi = _normalize_doi(dup_data.get("DOI", ""))
            if keep_doi or dup_doi:
                if keep_doi != dup_doi:
                    raise ValueError(
                        f"Refusing to merge {keep_key} and {dup_key}: DOI mismatch "
                        f"(keep={keep_doi!r} vs dup={dup_doi!r}). Pass "
                        "require_same_doi=False to override after manual confirmation."
                    )
            else:
                keep_title = _normalize_title(keep_data.get("title", ""))
                dup_title = _normalize_title(dup_data.get("title", ""))
                same_title = bool(keep_title) and keep_title == dup_title
                same_item_type = keep_data.get("itemType") == dup_data.get("itemType")
                keep_year = _extract_year(keep_data.get("date", ""))
                dup_year = _extract_year(dup_data.get("date", ""))
                same_year = bool(keep_year) and keep_year == dup_year
                keep_creator = _first_creator_lastname(keep_data)
                dup_creator = _first_creator_lastname(dup_data)
                same_creator = bool(keep_creator) and keep_creator == dup_creator
                if not (same_title and same_item_type and (same_year or same_creator)):
                    raise ValueError(
                        f"Refusing to merge {keep_key} and {dup_key}: neither item has a "
                        "DOI, and they do not match closely enough without one (title "
                        f"match={same_title}, itemType match={same_item_type} "
                        f"({keep_data.get('itemType')!r} vs {dup_data.get('itemType')!r}), "
                        f"year match={same_year}, first-creator match={same_creator}). "
                        "Pass require_same_doi=False to override after manual confirmation."
                    )

        # Step 4: move every (non-trashed) child of dup onto keep, paginated.
        children = self.web.everything(self.web.children(dup_key)) or []
        moved_child_keys = []
        skipped_deleted_children = []
        try:
            for child in children:
                child_data = child["data"]
                child_key = child_data.get("key")
                if child_data.get("deleted"):
                    skipped_deleted_children.append(child_key)
                    continue
                child_data["parentItem"] = keep_key
                self.web.update_item(child_data)
                moved_child_keys.append(child_key)
        except Exception as exc:
            raise ZoteroWriteError(
                f"merge_duplicates aborted while moving children of {dup_key} onto "
                f"{keep_key}: {exc}. Already moved: {moved_child_keys}. Nothing was "
                "trashed; safe to re-run once the underlying error is fixed."
            ) from exc
        children_moved = len(moved_child_keys)

        # Step 5: re-read keep fresh, right before writing it (not the copy
        # read at the top, which may be stale after moving children).
        fresh_keep_data = self._web_item(keep_key)["data"]

        # Step 6: union collections, tags, and dup's own relations onto keep.
        keep_collections = set(fresh_keep_data.get("collections", []))
        dup_collections = set(dup_data.get("collections", []))
        collections_added = sorted(dup_collections - keep_collections)
        fresh_keep_data["collections"] = list(keep_collections | dup_collections)

        keep_tag_names = {t["tag"] for t in fresh_keep_data.get("tags", [])}
        new_tags = [t for t in dup_data.get("tags", []) if t["tag"] not in keep_tag_names]
        fresh_keep_data.setdefault("tags", []).extend(new_tags)

        lib_segment = _pluralize_library_type(self.web.library_type)
        dup_uri = f"http://zotero.org/{lib_segment}/{self.web.library_id}/items/{dup_key}"
        keep_uri = f"http://zotero.org/{lib_segment}/{self.web.library_id}/items/{keep_key}"

        keep_relations = fresh_keep_data.setdefault("relations", {})
        for predicate, values in (dup_data.get("relations") or {}).items():
            values_list = [values] if isinstance(values, str) else list(values)
            existing = keep_relations.get(predicate, [])
            if isinstance(existing, str):
                existing = [existing]
            merged = list(existing)
            for v in values_list:
                if v == keep_uri:
                    continue  # would make keep related to itself; skip (ZOT-MERGE round 4)
                if v not in merged:
                    merged.append(v)
            keep_relations[predicate] = merged

        # Step 7: record the merge itself via dc:replaces.
        existing_replaces = keep_relations.get("dc:replaces", [])
        if isinstance(existing_replaces, str):
            existing_replaces = [existing_replaces]
        if dup_uri not in existing_replaces:
            existing_replaces = [*existing_replaces, dup_uri]
        keep_relations["dc:replaces"] = existing_replaces

        try:
            self.web.update_item(fresh_keep_data)
        except Exception as exc:
            raise ZoteroWriteError(
                f"merge_duplicates aborted while updating keep={keep_key} after moving "
                f"{children_moved} child(ren) from {dup_key}: {exc}. Children ARE already "
                f"moved (keys: {moved_child_keys}); keep's collections/tags/relations were "
                "NOT saved; nothing was trashed. Safe to re-run once the underlying error "
                "is fixed (the already-moved children will simply be re-moved)."
            ) from exc

        # Step 8: trash the duplicate LAST, after everything useful moved off it.
        try:
            self.trash_item(dup_key)
        except Exception as exc:
            raise ZoteroWriteError(
                f"merge_duplicates updated keep={keep_key} (children moved, collections/"
                f"tags/relations unioned) but failed to trash the duplicate {dup_key}: "
                f"{exc}. Nothing left to redo except trashing {dup_key} by hand (e.g. "
                "trash_item(dup_key)) once the underlying error is fixed."
            ) from exc

        return {
            "children_moved": children_moved,
            "skipped_deleted_children": skipped_deleted_children,
            "collections_added": collections_added,
            "tags_added": [t["tag"] for t in new_tags],
            "relation": dup_uri,
            "trashed_key": dup_key,
        }

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
