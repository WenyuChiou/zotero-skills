"""Mock integration tests: ZoteroDualClient routing, fallback, batching, write-gate.

Uses fake_pyzotero (no network). Covers Gate 4 routing + Gate 2 M-* scenarios.
"""
import pytest

import zotero_client as zc


def _dual(monkeypatch, local_available, api_key="KEY", user_id="1"):
    monkeypatch.setattr(zc, "check_local_api", lambda *a, **k: local_available)
    # Supply creds via env so __init__'s unconditional _load_credentials() resolves
    # from env (not the absent config.json).
    monkeypatch.setenv("ZOTERO_API_KEY", api_key or "ENVKEY")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", user_id or "1")
    return zc.ZoteroDualClient(user_id=user_id, api_key=api_key)


def test_construction_with_explicit_args_no_config(monkeypatch, fake_pyzotero):
    # ZOT-ROB-018 fixed: with no env/.env/config.json, explicit args must NOT
    # raise FileNotFoundError — config.json is consulted only when it exists.
    monkeypatch.setattr(zc, "check_local_api", lambda *a, **k: False)
    dual = zc.ZoteroDualClient(user_id="1", api_key="K")  # no config present
    assert dual.api_key == "K" and dual.user_id == "1"


def test_missing_credentials_no_config_returns_none(monkeypatch):
    # _load_credentials returns Nones (not a crash) when nothing is configured.
    monkeypatch.setattr(zc, "check_local_api", lambda *a, **k: False)
    key, lib, lib_type = zc._load_credentials()
    assert key is None and lib is None and lib_type == "user"


def test_read_uses_local_when_available(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=True)
    dual.search("flood")                               # routing: read -> local
    assert any(c[0] == "items" for c in dual.local.calls)
    assert not any(c[0] == "items" for c in dual.web.calls)
    assert dual.local is not dual.web


def test_read_uses_web_when_local_unavailable(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    assert dual.local is dual.web                      # fallback wired
    dual.search("flood")
    assert any(c[0] == "items" for c in dual.web.calls)


def test_read_falls_back_on_connection_error(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=True)
    dual.local._raise_on["items"] = Exception("Connection refused (urlopen error)")
    dual.search("flood")                               # M-12
    assert dual.local_available is False               # flipped
    assert any(c[0] == "items" for c in dual.web.calls)  # served by web


def test_read_reraises_non_connection_error(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=True)
    dual.local._raise_on["items"] = Exception("400 Bad Request")
    with pytest.raises(Exception) as ei:
        dual.search("flood")                           # non-connection error must NOT be swallowed
    assert "400" in str(ei.value)


def test_read_falls_back_on_local_404_without_disabling_local(monkeypatch, fake_pyzotero):
    # ZOT-REL-008: a local cache miss (404) retries on web WITHOUT permanently
    # disabling local for the rest of the session.
    dual = _dual(monkeypatch, local_available=True)
    dual.local._raise_on["item"] = Exception("404 Not Found")
    dual.get_item("ITEM01")
    assert any(c[0] == "item" for c in dual.web.calls)   # served by web
    assert dual.local_available is True                  # local NOT disabled by a cache miss


def test_write_requires_web_key(monkeypatch, fake_pyzotero, fake_config):
    # Build a client with a library id but NO api key -> writes must be refused.
    monkeypatch.setattr(zc, "check_local_api", lambda *a, **k: False)
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "1")
    fake_config(zotero_api_key="", zotero_library_id="1")  # empty key, no crash on fallback
    dual = zc.ZoteroDualClient(user_id="1", api_key=None)
    assert dual.api_key in (None, "")
    with pytest.raises(ValueError):
        dual.create_item({"itemType": "journalArticle"})   # write-gate


def test_all_write_methods_go_through_web(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=True)
    dual.create_item({"itemType": "note"})
    dual.create_note("P1", "T", "body")
    dual.create_collection("New")
    # every write recorded on web, never on local
    web_writes = [c[0] for c in dual.web.calls]
    assert "create_items" in web_writes
    assert "create_collections" in web_writes
    assert not any(c[0] in ("create_items", "create_collections") for c in dual.local.calls)


def test_create_items_batches_by_50(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    items = [{"itemType": "note", "note": str(i)} for i in range(120)]
    dual.create_items(items)                           # 50 + 50 + 20 -> 3 calls
    create_calls = [c for c in dual.web.calls if c[0] == "create_items"]
    assert len(create_calls) == 3
    assert [len(c[1][0]) for c in create_calls] == [50, 50, 20]


def test_status_reports_sources(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=True)
    st = dual.status()
    assert st["read_source"].startswith("local")
    assert st["write_source"] == "web"


def test_update_item_reads_version_from_web(monkeypatch, fake_pyzotero):
    # ZOT-COR-004: the write version must come from the authoritative Web API,
    # NOT the local channel, even when local is available.
    dual = _dual(monkeypatch, local_available=True)
    dual.update_item("ITEM01", {"title": "New"})
    assert any(c[0] == "item" for c in dual.web.calls)       # version read on web
    assert not any(c[0] == "item" for c in dual.local.calls)  # not from local
    assert any(c[0] == "update_item" for c in dual.web.calls)


def test_delete_item_reads_version_from_web(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=True)
    dual.delete_item("ITEM01")
    assert any(c[0] == "item" for c in dual.web.calls)
    assert any(c[0] == "delete_item" for c in dual.web.calls)


def test_trash_item_patches_deleted_flag(monkeypatch, fake_pyzotero):
    # ZOT-DEL-003: trash_item issues a PATCH {"deleted":1} (recoverable), NOT a DELETE.
    import json as _json
    import urllib.request
    dual = _dual(monkeypatch, local_available=False)
    captured = {}

    class _Resp:
        status = 204
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["method"] = req.get_method()
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["hdr"] = {k.lower(): v for k, v in req.headers.items()}
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert dual.trash_item("ITEM01") is True
    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/items/ITEM01")
    assert _json.loads(captured["body"]) == {"deleted": 1}
    assert captured["hdr"].get("zotero-api-key") == "KEY"        # key in header, not URL
    assert "zotero-api-key" not in captured["url"].lower()
    assert "if-unmodified-since-version" in captured["hdr"]


def test_delete_item_uses_web_delete_not_patch(monkeypatch, fake_pyzotero):
    # delete_item is PERMANENT: goes through web.delete_item (a DELETE), never a trash PATCH.
    dual = _dual(monkeypatch, local_available=False)
    dual.delete_item("ITEM01")
    assert any(c[0] == "delete_item" for c in dual.web.calls)


def test_delete_items_chunks_by_50(monkeypatch, fake_pyzotero):
    # ZOT-COR-013
    dual = _dual(monkeypatch, local_available=False)
    keys = [f"K{i}" for i in range(120)]
    dual.delete_items(keys)
    del_calls = [c for c in dual.web.calls if c[0] == "delete_item"]
    assert len(del_calls) == 3
    assert [len(c[1][0]) for c in del_calls] == [50, 50, 20]


def test_create_items_surfaces_failed_bucket(monkeypatch, fake_pyzotero):
    # ZOT-SILENT-007
    dual = _dual(monkeypatch, local_available=False)
    dual.web._create_failed = {"0": {"code": 400, "message": "bad"}}
    with pytest.raises(zc.ZoteroWriteError):
        dual.create_items([{"itemType": "note", "note": "x"}])


def test_create_note_keeps_title_when_content_prewrapped(monkeypatch, fake_pyzotero):
    # ZOT-COR-016
    dual = _dual(monkeypatch, local_available=False)
    dual.create_note("P1", "My Title", "<p>already wrapped</p>")
    note = [c for c in dual.web.calls if c[0] == "create_items"][0][1][0][0]
    assert "<h1>My Title</h1>" in note["note"]
    assert "already wrapped" in note["note"]


def test_create_note_no_dup_when_title_matches_heading(monkeypatch, fake_pyzotero):
    # Content already opens with a heading whose text == title -> no duplicate.
    dual = _dual(monkeypatch, local_available=False)
    dual.create_note("P1", "My Title", "<h1>My Title</h1><p>body</p>")
    note = [c for c in dual.web.calls if c[0] == "create_items"][0][1][0][0]
    assert note["note"].lower().count("<h1") == 1
    assert "My Title" in note["note"]


def test_create_note_preserves_distinct_title_over_content_heading(monkeypatch, fake_pyzotero):
    # Reviewer edge case: a DISTINCT title must NOT be silently dropped when the
    # content opens with an unrelated heading.
    dual = _dual(monkeypatch, local_available=False)
    dual.create_note("P1", "My Real Title", "<h2>Unrelated Heading</h2><p>body</p>")
    note = [c for c in dual.web.calls if c[0] == "create_items"][0][1][0][0]
    assert "My Real Title" in note["note"]        # title preserved
    assert "Unrelated Heading" in note["note"]     # content preserved too


def test_add_to_collection_only_adds(monkeypatch, fake_pyzotero):
    # ZOT-COR-014: adds membership, does not remove existing ones.
    dual = _dual(monkeypatch, local_available=False)
    dual.add_to_collection("ITEM01", "COLL_NEW")
    payload = [c for c in dual.web.calls if c[0] == "update_item"][0][1][0]
    assert "COLL_NEW" in payload["collections"]
    # move_to_collection is a back-compat alias of add_to_collection
    assert dual.move_to_collection == dual.add_to_collection
