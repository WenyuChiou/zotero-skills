"""Pytest fixtures for zotero-skills audit tests.

SAFETY: an autouse fixture isolates EVERY test from the real developer
credentials and the real network. No test reads the real ``config.json`` /
``~/.claude/.env`` or makes a real Zotero request unless it explicitly opts in.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import zotero_client as zc  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_credentials(monkeypatch, tmp_path):
    """Guarantee no test touches real creds / real ~/.claude/.env / real config.json.

    Redirects ``Path.home()`` to a temp dir (so the REAL ``_read_env_file`` finds
    nothing) rather than stubbing the function — keeps the function under test.
    """
    for var in ("ZOTERO_API_KEY", "ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_TYPE"):
        monkeypatch.delenv(var, raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(zc.Path, "home", staticmethod(lambda: fake_home), raising=True)
    # Point config.json at a non-existent temp path by default.
    monkeypatch.setattr(zc, "_CONFIG_PATH", tmp_path / "no_config.json", raising=True)
    yield


@pytest.fixture
def fake_config(monkeypatch, tmp_path):
    """Write a temp config.json and point the client at it. Returns the dict."""
    def _make(**overrides):
        cfg = {
            "zotero_api_key": "TESTKEY_dummy_0000",
            "zotero_library_id": "9999999",
            "zotero_library_type": "user",
            "collections": {"example": "COLLKEY1"},
        }
        cfg.update(overrides)
        p = tmp_path / "config.json"
        p.write_text(json.dumps(cfg), encoding="utf-8")
        monkeypatch.setattr(zc, "_CONFIG_PATH", p, raising=True)
        return cfg
    return _make


@pytest.fixture
def env_file(monkeypatch):
    """Write a real ~/.claude/.env under the (redirected) HOME so the REAL
    ``_read_env_file`` parses it end-to-end."""
    def _make(**values):
        home = zc.Path.home()
        envdir = home / ".claude"
        envdir.mkdir(parents=True, exist_ok=True)
        lines = [f'{k}="{v}"' for k, v in values.items()]
        (envdir / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return values
    return _make


class FakeZotero:
    """Minimal stand-in for pyzotero.Zotero — records calls, never hits network."""
    def __init__(self, library_id=None, library_type="user", api_key=None, local=False):
        self.library_id = library_id
        self.library_type = library_type
        self.api_key = api_key
        self.local = local
        self.endpoint = "https://api.zotero.org"
        self.calls = []
        self._items = []           # what .items()/.top() return
        self._raise_on = {}        # method_name -> exception to raise

    def _record(self, name, *a, **k):
        self.calls.append((name, a, k))
        if name in self._raise_on:
            raise self._raise_on[name]

    # reads
    def items(self, *a, **k):
        self._record("items", *a, **k)
        return list(self._items)

    def top(self, *a, **k):
        self._record("top", *a, **k)
        return list(self._items)

    def item(self, key, *a, **k):
        self._record("item", key, *a, **k)
        return {"key": key, "version": 1, "data": {"key": key, "version": 1,
                "title": "X", "tags": [], "collections": []}}

    def collection(self, key, *a, **k):
        self._record("collection", key, *a, **k)
        return {"key": key, "version": 1, "data": {"key": key, "name": "C"}}

    def collections(self, *a, **k):
        self._record("collections", *a, **k)
        return []

    # writes
    def create_items(self, items, *a, **k):
        self._record("create_items", items, *a, **k)
        failed = getattr(self, "_create_failed", {})
        return {"successful": {"0": {"key": "NEWKEY01"}}, "failed": dict(failed), "unchanged": {}}

    def create_collections(self, cols, *a, **k):
        self._record("create_collections", cols, *a, **k)
        return {"successful": {"0": {"key": "NEWCOLL1"}}, "failed": {}}

    def update_item(self, data, *a, **k):
        self._record("update_item", data, *a, **k)
        return True

    def delete_item(self, item, *a, **k):
        self._record("delete_item", item, *a, **k)
        return True

    def delete_collection(self, coll, *a, **k):
        self._record("delete_collection", coll, *a, **k)
        return True

    def item_template(self, item_type, *a, **k):
        self._record("item_template", item_type, *a, **k)
        return {"itemType": item_type, "note": "", "tags": [], "parentItem": ""}


@pytest.fixture
def fake_pyzotero(monkeypatch):
    """Patch the lazily-imported ``pyzotero.zotero.Zotero`` with FakeZotero."""
    import types
    created = []

    def factory(*a, **k):
        z = FakeZotero(*a, **k)
        created.append(z)
        return z

    fake_module = types.SimpleNamespace(Zotero=factory)
    fake_pkg = types.SimpleNamespace(zotero=fake_module)
    monkeypatch.setitem(sys.modules, "pyzotero", fake_pkg)
    monkeypatch.setitem(sys.modules, "pyzotero.zotero", fake_module)
    return created
