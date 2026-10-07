"""Mock integration tests: ZoteroDualClient routing, fallback, batching, write-gate.

Uses fake_pyzotero (no network). Covers Gate 4 routing + Gate 2 M-* scenarios.
"""
import os
import urllib.request
from pathlib import Path

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


def test_delete_items_deletes_per_item(monkeypatch, fake_pyzotero):
    # ZOT-COR-025: delete per-item (each with its OWN fresh version) rather than
    # pyzotero's batch delete, which 412s on a library-version precondition mismatch.
    dual = _dual(monkeypatch, local_available=False)
    keys = [f"K{i}" for i in range(5)]
    dual.delete_items(keys)
    # one fresh web read + one single delete per key; never a list payload
    del_calls = [c for c in dual.web.calls if c[0] == "delete_item"]
    assert len(del_calls) == 5
    assert all(not isinstance(c[1][0], list) for c in del_calls)   # single item, not a batch list
    assert len([c for c in dual.web.calls if c[0] == "item"]) == 5


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


# ---------------- attach_pdf (ZOT-ATTACH-026, ZOT-ATTACH-028) ----------------
def test_attach_pdf_uses_short_safe_name_and_cleans_up(monkeypatch, fake_pyzotero, tmp_path):
    # A long Windows path with spaces must not be sent as the payload's
    # filename; the copy's name must be short and space-free, and the temp
    # dir removed after.
    dual = _dual(monkeypatch, local_available=False)
    src_dir = tmp_path / "a long folder name with spaces (and parens)"
    src_dir.mkdir()
    long_name = "A Really Long Paper Title With Lots Of Spaces In It 2026 Draft Final v3.pdf"
    src = src_dir / long_name
    src.write_bytes(b"%PDF-1.4 fake pdf bytes")

    result = dual.attach_pdf("PARENT01", str(src))

    calls = [c for c in dual.web.calls if c[0] == "upload_attachments"]
    assert len(calls) == 1
    sent_attachments, sent_parentid, sent_basedir = calls[0][1]
    sent_template = sent_attachments[0]
    sent_filename = sent_template["filename"]
    assert sent_parentid == "PARENT01"
    assert sent_template["title"] == long_name     # readable title preserved
    assert sent_filename == Path(sent_filename).name  # BARE name: no directory path at all
    assert " " not in sent_filename                # the uploaded file's name is safe
    assert len(sent_filename) <= 40
    assert sent_filename.startswith("zot_")
    assert sent_filename.endswith(".pdf")
    assert sent_basedir is not None and not Path(sent_basedir).exists()  # temp dir cleaned up
    assert result["key"] and result["md5"]         # read-back succeeded


def test_attach_pdf_filename_never_contains_a_directory_path(monkeypatch, fake_pyzotero, tmp_path):
    # ZOT-ATTACH-028: the real Zotero API rejects any directory separator in
    # the payload's filename field with HTTP 400 ("Stored-file filename
    # '...' cannot contain a directory path"). Assert this invariant directly
    # across a few path shapes, including ones that previously broke 0.3.0.
    dual = _dual(monkeypatch, local_available=False)
    cases = [
        tmp_path / "plain.pdf",
        tmp_path / "a dir with spaces" / "nested.pdf",
        tmp_path / "unicode 論文.pdf",
    ]
    for src in cases:
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"%PDF-1.4")
        dual.attach_pdf("PARENT01", str(src))

    calls = [c for c in dual.web.calls if c[0] == "upload_attachments"]
    assert len(calls) == len(cases)
    for sent_attachments, _parentid, _basedir in (c[1] for c in calls):
        sent_filename = sent_attachments[0]["filename"]
        assert os.sep not in sent_filename
        assert "/" not in sent_filename
        assert sent_filename == Path(sent_filename).name


def test_attach_pdf_raises_with_failure_detail_and_cleans_up(monkeypatch, fake_pyzotero, tmp_path):
    # pyzotero can return {"failure": [...]} with no exception (the
    # silent-failure bug); attach_pdf must raise with that detail instead.
    dual = _dual(monkeypatch, local_available=False)
    dual.web._attachment_failure = [{"title": "bad.pdf", "filename": "bad.pdf"}]
    src = tmp_path / "paper with spaces.pdf"
    src.write_bytes(b"%PDF-1.4")

    with pytest.raises(zc.ZoteroWriteError) as ei:
        dual.attach_pdf("PARENT01", str(src))
    assert "bad.pdf" in str(ei.value)

    calls = [c for c in dual.web.calls if c[0] == "upload_attachments"]
    sent_basedir = calls[0][1][2]
    assert not Path(sent_basedir).exists()          # cleaned up even on failure


def test_attach_pdf_succeeds_when_pyzotero_reports_unchanged_dedup(monkeypatch, fake_pyzotero, tmp_path):
    # Reviewer round 1 (ZOT-ATTACH-028): pyzotero's Zupload.upload() routes an
    # item into "unchanged" instead of "success" whenever the Web API's
    # upload-authorization step reports "exists: 1" -- a file with this exact
    # MD5 is already in the library's storage (the same PDF attached to two
    # items, or simply retrying attach_pdf on an already-uploaded file). The
    # attachment ITEM is still created with a real key either way; attach_pdf
    # must not treat this as a failure.
    dual = _dual(monkeypatch, local_available=False)
    dual.web._attachment_unchanged = True
    src = tmp_path / "already_uploaded.pdf"
    src.write_bytes(b"%PDF-1.4")

    result = dual.attach_pdf("PARENT01", str(src))

    assert result["key"]
    assert result["md5"]
    assert result["raw"]["success"] == []
    assert result["raw"]["unchanged"]              # landed in unchanged, not success


def test_attach_pdf_raises_when_readback_has_no_md5(monkeypatch, fake_pyzotero, tmp_path):
    # The success check must read back the created attachment (key, md5)
    # rather than trusting pyzotero's upload-result dict at face value: a
    # key with no corresponding stored file must not look like success.
    dual = _dual(monkeypatch, local_available=False)
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4")

    # Patch item() to simulate a created key whose read-back has no md5.
    real_item = dual.web.item

    def _item_no_md5(key, *a, **k):
        result = real_item(key, *a, **k)
        result["data"]["md5"] = None
        return result

    monkeypatch.setattr(dual.web, "item", _item_no_md5)

    with pytest.raises(zc.ZoteroWriteError) as ei:
        dual.attach_pdf("PARENT01", str(src))
    assert "md5" in str(ei.value)


def test_attach_pdf_wraps_readback_failure_in_zoterowriteerror(monkeypatch, fake_pyzotero, tmp_path):
    # A transient error on the post-upload read-back (e.g. network hiccup)
    # must still surface as ZoteroWriteError, not whatever raw exception
    # item() happened to raise -- the attachment may already exist on the
    # server at that point, so the error message says so.
    dual = _dual(monkeypatch, local_available=False)
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4")

    def _item_raises(key, *a, **k):
        raise RuntimeError("simulated transient read-back failure")

    monkeypatch.setattr(dual.web, "item", _item_raises)

    with pytest.raises(zc.ZoteroWriteError) as ei:
        dual.attach_pdf("PARENT01", str(src))
    assert "read-back failed" in str(ei.value)
    assert "simulated transient read-back failure" in str(ei.value)


def test_attach_pdf_filename_override_is_sanitized(monkeypatch, fake_pyzotero, tmp_path):
    dual = _dual(monkeypatch, local_available=False)
    src = tmp_path / "source.pdf"
    src.write_bytes(b"%PDF-1.4")

    result = dual.attach_pdf("PARENT01", str(src), filename="My Custom Name.pdf")

    calls = [c for c in dual.web.calls if c[0] == "upload_attachments"]
    sent_template = calls[0][1][0][0]
    assert sent_template["title"] == "My Custom Name.pdf"  # override used as the readable title too
    assert sent_template["filename"] == "zot_My_Custom_Name.pdf"
    assert result["title"] == "My Custom Name.pdf"
    assert result["filename"] == "zot_My_Custom_Name.pdf"


def test_attach_pdf_missing_source_raises_before_any_call(monkeypatch, fake_pyzotero, tmp_path):
    dual = _dual(monkeypatch, local_available=False)
    with pytest.raises(FileNotFoundError):
        dual.attach_pdf("PARENT01", str(tmp_path / "does-not-exist.pdf"))
    assert not any(c[0] == "attachment_simple" for c in dual.web.calls)
    assert not any(c[0] == "attachment_both" for c in dual.web.calls)
    assert not any(c[0] == "upload_attachments" for c in dual.web.calls)


# ---------------- merge_duplicates (ZOT-MERGE-027) ----------------
def _merge_fixture(dual, **overrides):
    """Wire up a keep/dup item pair on dual.web for merge_duplicates tests."""
    keep_item = {"key": "KEEPKEY", "version": 5, "data": {
        "key": "KEEPKEY", "version": 5, "title": "Keep Title", "DOI": "10.1/x",
        "collections": ["COLLA"], "tags": [{"tag": "existing-tag"}],
    }}
    dup_item = {"key": "DUPKEY", "version": 3, "data": {
        "key": "DUPKEY", "version": 3, "title": "Dup Title", "DOI": "10.1/x",
        "collections": ["COLLB"], "tags": [{"tag": "existing-tag"}, {"tag": "new-tag"}],
    }}
    keep_item["data"].update(overrides.get("keep", {}))
    dup_item["data"].update(overrides.get("dup", {}))
    dual.web._items_by_key = {"KEEPKEY": keep_item, "DUPKEY": dup_item}
    dual.web._children_by_key = {"DUPKEY": overrides.get("children", [])}
    return keep_item, dup_item


def _patch_trash_urlopen(monkeypatch, dual, snapshot_sink=None):
    import urllib.request

    class _Resp:
        status = 204
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        if snapshot_sink is not None:
            snapshot_sink.extend(dual.web.calls)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def test_merge_duplicates_moves_children_unions_tags_and_trashes_last(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    child1 = {"key": "CHILD1", "version": 1, "data": {"key": "CHILD1", "version": 1,
              "itemType": "note", "parentItem": "DUPKEY"}}
    child2 = {"key": "CHILD2", "version": 1, "data": {"key": "CHILD2", "version": 1,
              "itemType": "attachment", "parentItem": "DUPKEY"}}
    keep_item, dup_item = _merge_fixture(dual, children=[child1, child2])
    snapshot_at_trash = []
    _patch_trash_urlopen(monkeypatch, dual, snapshot_at_trash)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY")

    # children moved
    assert child1["data"]["parentItem"] == "KEEPKEY"
    assert child2["data"]["parentItem"] == "KEEPKEY"
    update_calls = [c for c in dual.web.calls if c[0] == "update_item"]
    assert any(c[1][0]["key"] == "CHILD1" for c in update_calls)
    assert any(c[1][0]["key"] == "CHILD2" for c in update_calls)

    # collections + tags unioned onto keep (nothing dropped)
    assert set(keep_item["data"]["collections"]) == {"COLLA", "COLLB"}
    assert {t["tag"] for t in keep_item["data"]["tags"]} == {"existing-tag", "new-tag"}

    # dc:replaces relation added (real Zotero shape: plural "users", ZOT-MERGE-027)
    expected_uri = "http://zotero.org/users/1/items/DUPKEY"
    assert keep_item["data"]["relations"]["dc:replaces"] == [expected_uri]

    # trash happened LAST: the keep update_item call must precede it
    assert any(c[0] == "update_item" and c[1][0].get("key") == "KEEPKEY" for c in snapshot_at_trash)

    assert result == {
        "children_moved": 2,
        "skipped_deleted_children": [],
        "collections_added": ["COLLB"],
        "tags_added": ["new-tag"],
        "relation": expected_uri,
        "trashed_key": "DUPKEY",
    }

    # every child update happened before the trash PATCH, not just keep's
    assert any(c[0] == "update_item" and c[1][0].get("key") == "CHILD1" for c in snapshot_at_trash)
    assert any(c[0] == "update_item" and c[1][0].get("key") == "CHILD2" for c in snapshot_at_trash)


def test_merge_duplicates_preserves_existing_relations_stored_as_list(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    keep_item, _ = _merge_fixture(dual, keep={"relations": {"dc:replaces": ["http://existing/1"]}})
    _patch_trash_urlopen(monkeypatch, dual)

    dual.merge_duplicates("KEEPKEY", "DUPKEY")

    assert keep_item["data"]["relations"]["dc:replaces"] == [
        "http://existing/1", "http://zotero.org/users/1/items/DUPKEY",
    ]


def test_merge_duplicates_preserves_existing_relation_stored_as_string(monkeypatch, fake_pyzotero):
    # dc:replaces can already hold a bare string (not a list) on a real item.
    dual = _dual(monkeypatch, local_available=False)
    keep_item, _ = _merge_fixture(dual, keep={"relations": {"dc:replaces": "http://existing/1"}})
    _patch_trash_urlopen(monkeypatch, dual)

    dual.merge_duplicates("KEEPKEY", "DUPKEY")

    assert keep_item["data"]["relations"]["dc:replaces"] == [
        "http://existing/1", "http://zotero.org/users/1/items/DUPKEY",
    ]


# ---------------- dc:replaces URI shape: users vs groups (ZOT-MERGE-027) ----------------
def test_merge_duplicates_relation_uri_for_user_library(monkeypatch, fake_pyzotero):
    # FakeZotero stores library_type exactly as passed in (singular "user"),
    # unlike real pyzotero, which already pluralizes it internally. The real
    # shape must still come out plural: http://zotero.org/users/<id>/items/<key>.
    dual = _dual(monkeypatch, local_available=False)
    assert dual.web.library_type == "user"
    _merge_fixture(dual)
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert result["relation"] == "http://zotero.org/users/1/items/DUPKEY"


def test_merge_duplicates_relation_uri_for_group_library(monkeypatch, fake_pyzotero):
    # Real pyzotero would already store "groups" here (singular "group" + "s");
    # the already-plural value must pass through unchanged.
    dual = _dual(monkeypatch, local_available=False)
    dual.web.library_type = "groups"
    _merge_fixture(dual)
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert result["relation"] == "http://zotero.org/groups/1/items/DUPKEY"


def test_merge_duplicates_refuses_on_doi_mismatch(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, keep={"DOI": "10.1/aaa"}, dup={"DOI": "10.1/bbb"})

    with pytest.raises(ValueError, match="DOI mismatch"):
        dual.merge_duplicates("KEEPKEY", "DUPKEY")

    assert not any(c[0] == "update_item" for c in dual.web.calls)  # refused before any mutation


def test_merge_duplicates_allows_doi_mismatch_when_flag_false(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, keep={"DOI": "10.1/aaa"}, dup={"DOI": "10.1/bbb"})
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY", require_same_doi=False)
    assert result["trashed_key"] == "DUPKEY"


def test_merge_duplicates_refuses_when_dup_already_deleted(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, dup={"deleted": 1})

    with pytest.raises(ValueError, match="deleted"):
        dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert not any(c[0] == "update_item" for c in dual.web.calls)


def test_merge_duplicates_refuses_when_keep_already_deleted(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, keep={"deleted": 1})

    with pytest.raises(ValueError, match="deleted"):
        dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert not any(c[0] == "update_item" for c in dual.web.calls)


# ---------------- reviewer round 3 (self-merge / child-items / DOI norm / relations union) ----------------
def test_merge_duplicates_refuses_self_merge(monkeypatch, fake_pyzotero):
    # Probe-confirmed bug: merging a key with itself used to trash the keeper.
    dual = _dual(monkeypatch, local_available=False)

    with pytest.raises(ValueError, match="itself"):
        dual.merge_duplicates("SAMEKEY", "SAMEKEY")

    assert dual.web.calls == []  # refused before any read or write


@pytest.mark.parametrize("bad_dup", [
    {"itemType": "note", "parentItem": None},
    {"itemType": "attachment", "parentItem": None},
    {"itemType": "journalArticle", "parentItem": "SOMEPARENT"},
])
def test_merge_duplicates_refuses_child_items(monkeypatch, fake_pyzotero, bad_dup):
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, dup=bad_dup)

    with pytest.raises(ValueError, match="child item"):
        dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert not any(c[0] == "update_item" for c in dual.web.calls)


def test_merge_duplicates_doi_case_and_resolver_prefix_treated_as_equal(monkeypatch, fake_pyzotero):
    # Reviewer probe: "10.1/ABC" vs "10.1/abc" was wrongly refused as a mismatch.
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, keep={"DOI": "https://doi.org/10.1/ABC"}, dup={"DOI": "10.1/abc"})
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert result["trashed_key"] == "DUPKEY"


def test_merge_duplicates_requires_title_match_when_both_dois_empty(monkeypatch, fake_pyzotero):
    # Reviewer probe: empty DOIs on both sides used to pass the guard for ANY pair.
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, keep={"DOI": "", "title": "Book A"}, dup={"DOI": "", "title": "Unrelated Book B"})

    with pytest.raises(ValueError, match="title"):
        dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert not any(c[0] == "update_item" for c in dual.web.calls)


def test_merge_duplicates_allows_empty_dois_with_matching_title_type_and_year(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual,
                   keep={"DOI": "", "title": "  Book A  ", "itemType": "book", "date": "2020"},
                   dup={"DOI": "", "title": "book a", "itemType": "book", "date": "2020-03"})
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert result["trashed_key"] == "DUPKEY"


def test_merge_duplicates_allows_empty_dois_with_matching_title_type_and_creator(monkeypatch, fake_pyzotero):
    # Same title/itemType, DIFFERENT year, but the same first creator's last
    # name: the "year OR creator" half of the guard is satisfied by creator.
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(
        dual,
        keep={"DOI": "", "title": "Book A", "itemType": "book", "date": "2001",
              "creators": [{"creatorType": "author", "firstName": "Jane", "lastName": "Smith"}]},
        dup={"DOI": "", "title": "book a", "itemType": "book", "date": "2019",
             "creators": [{"creatorType": "author", "firstName": "J.", "lastName": "SMITH"}]},
    )
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert result["trashed_key"] == "DUPKEY"


def test_merge_duplicates_empty_dois_title_mismatch_overridable_with_flag(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual, keep={"DOI": "", "title": "Book A"}, dup={"DOI": "", "title": "Unrelated Book B"})
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY", require_same_doi=False)
    assert result["trashed_key"] == "DUPKEY"


def test_merge_duplicates_refuses_generic_title_with_different_year_and_no_creator(monkeypatch, fake_pyzotero):
    # Reviewer's case: two "Introduction" bookSections, same generic title and
    # itemType, but different years and no creators to fall back on.
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual,
                   keep={"DOI": "", "title": "Introduction", "itemType": "bookSection", "date": "2001"},
                   dup={"DOI": "", "title": "Introduction", "itemType": "bookSection", "date": "2019"})

    with pytest.raises(ValueError, match="year"):
        dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert not any(c[0] == "update_item" for c in dual.web.calls)


def test_merge_duplicates_refuses_mismatched_item_types_even_with_same_title(monkeypatch, fake_pyzotero):
    # Reviewer's case: journalArticle vs book, no DOI -- itemType must also match.
    dual = _dual(monkeypatch, local_available=False)
    _merge_fixture(dual,
                   keep={"DOI": "", "title": "Shared Title", "itemType": "journalArticle", "date": "2020"},
                   dup={"DOI": "", "title": "Shared Title", "itemType": "book", "date": "2020"})

    with pytest.raises(ValueError, match="itemType"):
        dual.merge_duplicates("KEEPKEY", "DUPKEY")
    assert not any(c[0] == "update_item" for c in dual.web.calls)


def test_merge_duplicates_unions_dup_own_relations_onto_keep(monkeypatch, fake_pyzotero):
    # Reviewer probe: dup's OWN relations (any predicate, including its own
    # dc:replaces from an earlier merge) used to be dropped entirely.
    dual = _dual(monkeypatch, local_available=False)
    keep_item, _ = _merge_fixture(dual, dup={"relations": {
        "dc:relation": ["http://zotero.org/users/1/items/RELATED1"],
        "dc:replaces": ["http://zotero.org/users/1/items/OLDERDUP"],
    }})
    _patch_trash_urlopen(monkeypatch, dual)

    dual.merge_duplicates("KEEPKEY", "DUPKEY")

    rel = keep_item["data"]["relations"]
    assert rel["dc:relation"] == ["http://zotero.org/users/1/items/RELATED1"]
    assert rel["dc:replaces"] == [
        "http://zotero.org/users/1/items/OLDERDUP",
        "http://zotero.org/users/1/items/DUPKEY",
    ]


def test_merge_duplicates_relation_union_has_no_duplicates(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    keep_item, _ = _merge_fixture(
        dual,
        keep={"relations": {"dc:relation": "http://zotero.org/users/1/items/RELATED1"}},
        dup={"relations": {"dc:relation": ["http://zotero.org/users/1/items/RELATED1"]}},
    )
    _patch_trash_urlopen(monkeypatch, dual)

    dual.merge_duplicates("KEEPKEY", "DUPKEY")

    rel = keep_item["data"]["relations"]
    assert rel["dc:relation"] == ["http://zotero.org/users/1/items/RELATED1"]  # string->list, not duplicated


def test_merge_duplicates_paginates_children_with_everything(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    child1 = {"key": "CHILD1", "version": 1, "data": {"key": "CHILD1", "version": 1,
              "itemType": "note", "parentItem": "DUPKEY"}}
    _merge_fixture(dual, children=[child1])
    _patch_trash_urlopen(monkeypatch, dual)

    dual.merge_duplicates("KEEPKEY", "DUPKEY")

    assert len([c for c in dual.web.calls if c[0] == "children"]) == 1
    assert len([c for c in dual.web.calls if c[0] == "everything"]) == 1


def test_merge_duplicates_skips_already_deleted_children_and_reports_them(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    live_child = {"key": "CHILDLIVE", "version": 1, "data": {"key": "CHILDLIVE", "version": 1,
                  "itemType": "note", "parentItem": "DUPKEY"}}
    trashed_child = {"key": "CHILDTRASHED", "version": 1, "data": {"key": "CHILDTRASHED", "version": 1,
                     "itemType": "note", "parentItem": "DUPKEY", "deleted": 1}}
    _merge_fixture(dual, children=[live_child, trashed_child])
    _patch_trash_urlopen(monkeypatch, dual)

    result = dual.merge_duplicates("KEEPKEY", "DUPKEY")

    assert live_child["data"]["parentItem"] == "KEEPKEY"
    assert trashed_child["data"]["parentItem"] == "DUPKEY"  # left alone, never touched
    update_calls = [c for c in dual.web.calls if c[0] == "update_item"]
    assert not any(c[1][0].get("key") == "CHILDTRASHED" for c in update_calls)
    assert result["children_moved"] == 1
    assert result["skipped_deleted_children"] == ["CHILDTRASHED"]


def test_merge_duplicates_child_failure_wraps_error_blocks_trash_and_keep_update(monkeypatch, fake_pyzotero):
    # Mutation-testing probe M1/M2 target: a failure moving a child must NOT
    # be swallowed, and must NOT be followed by a keep update or a trash.
    dual = _dual(monkeypatch, local_available=False)
    child1 = {"key": "CHILD1", "version": 1, "data": {"key": "CHILD1", "version": 1,
              "itemType": "note", "parentItem": "DUPKEY"}}
    child2 = {"key": "CHILD2", "version": 1, "data": {"key": "CHILD2", "version": 1,
              "itemType": "note", "parentItem": "DUPKEY"}}
    _merge_fixture(dual, children=[child1, child2])
    dual.web._fail_on_call["update_item"] = {"count": 2, "exc": RuntimeError("boom"), "seen": 0}

    def must_not_be_called(req, timeout=None):
        raise AssertionError("trash must not be attempted if a child move failed")
    monkeypatch.setattr(urllib.request, "urlopen", must_not_be_called)

    with pytest.raises(zc.ZoteroWriteError) as ei:
        dual.merge_duplicates("KEEPKEY", "DUPKEY")

    msg = str(ei.value)
    assert "CHILD1" in msg                      # already-moved child key reported
    assert "safe to re-run" in msg.lower()
    assert "boom" in msg
    update_calls = [c for c in dual.web.calls if c[0] == "update_item"]
    assert not any(c[1][0].get("key") == "KEEPKEY" for c in update_calls)  # keep never updated


def test_merge_duplicates_rereads_keep_right_before_updating(monkeypatch, fake_pyzotero):
    # If keep changed (e.g. a concurrent edit) while children were being
    # moved, the final write must use the LATEST version and data, not a
    # copy read at the very start of the call.
    dual = _dual(monkeypatch, local_available=False)
    keep_v1 = {"key": "KEEPKEY", "version": 5, "data": {
        "key": "KEEPKEY", "version": 5, "title": "Keep", "DOI": "10.1/x",
        "collections": ["COLLA"], "tags": [],
    }}
    keep_v2 = {"key": "KEEPKEY", "version": 9, "data": {
        "key": "KEEPKEY", "version": 9, "title": "Keep", "DOI": "10.1/x",
        "collections": ["COLLA", "COLLC"], "tags": [{"tag": "added-concurrently"}],
    }}
    dup_item = {"key": "DUPKEY", "version": 3, "data": {
        "key": "DUPKEY", "version": 3, "title": "Dup", "DOI": "10.1/x",
        "collections": ["COLLB"], "tags": [{"tag": "new-tag"}],
    }}
    keep_reads = iter([keep_v1, keep_v2])

    def fake_item(key, *a, **k):
        dual.web._record("item", key, *a, **k)
        return next(keep_reads) if key == "KEEPKEY" else dup_item

    monkeypatch.setattr(dual.web, "item", fake_item)
    dual.web._children_by_key = {"DUPKEY": []}
    _patch_trash_urlopen(monkeypatch, dual)

    dual.merge_duplicates("KEEPKEY", "DUPKEY")

    update_calls = [c for c in dual.web.calls if c[0] == "update_item"]
    keep_update = [c for c in update_calls if c[1][0]["key"] == "KEEPKEY"][0]
    payload = keep_update[1][0]
    assert payload["version"] == 9                               # from the SECOND (fresh) read
    assert set(payload["collections"]) == {"COLLA", "COLLB", "COLLC"}
    assert {t["tag"] for t in payload["tags"]} == {"added-concurrently", "new-tag"}


# ---------------- reviewer round 4 ----------------
def test_merge_duplicates_skips_self_referencing_relation_from_related_pair(monkeypatch, fake_pyzotero):
    # Zotero's "Related" links are two-way: keep->dup and dup->keep both exist
    # before the merge. Unioning dup's own relation back onto keep must not
    # leave keep pointing at itself.
    dual = _dual(monkeypatch, local_available=False)
    keep_uri = "http://zotero.org/users/1/items/KEEPKEY"
    dup_uri_existing = "http://zotero.org/users/1/items/DUPKEY"
    keep_item, _ = _merge_fixture(
        dual,
        keep={"relations": {"dc:relation": [dup_uri_existing]}},
        dup={"relations": {"dc:relation": [keep_uri]}},
    )
    _patch_trash_urlopen(monkeypatch, dual)

    dual.merge_duplicates("KEEPKEY", "DUPKEY")

    rel = keep_item["data"]["relations"]
    assert keep_uri not in rel["dc:relation"]
    assert rel["dc:relation"] == [dup_uri_existing]


def test_merge_duplicates_refuses_self_merge_with_differently_cased_keys(monkeypatch, fake_pyzotero):
    # pyzotero / the Web API upper-case keys; "abcd2345" vs "ABCD2345" must
    # still be caught even though the raw string comparison would differ.
    dual = _dual(monkeypatch, local_available=False)
    dual.web._items_by_key = {
        "abcd2345": {"key": "ABCD2345", "version": 1, "data": {"key": "ABCD2345", "version": 1, "title": "X"}},
        "ABCD2345": {"key": "ABCD2345", "version": 1, "data": {"key": "ABCD2345", "version": 1, "title": "X"}},
    }
    reqs_captured = []

    def fake_urlopen(req, timeout=None):
        reqs_captured.append(req.full_url)
        class _R:
            status = 204
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        return _R()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="itself"):
        dual.merge_duplicates("abcd2345", "ABCD2345")
    assert reqs_captured == []
    assert not any(c[0] == "update_item" for c in dual.web.calls)


def test_merge_duplicates_keep_update_failure_wrapped_nothing_trashed(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    child1 = {"key": "CHILD1", "version": 1, "data": {"key": "CHILD1", "version": 1,
              "itemType": "note", "parentItem": "DUPKEY"}}
    _merge_fixture(dual, children=[child1])
    dual.web._fail_on_call["update_item"] = {"count": 2, "exc": RuntimeError("412 Precondition Failed"), "seen": 0}

    def must_not_be_called(req, timeout=None):
        raise AssertionError("trash must not be attempted if keep's update failed")
    monkeypatch.setattr(urllib.request, "urlopen", must_not_be_called)

    with pytest.raises(zc.ZoteroWriteError) as ei:
        dual.merge_duplicates("KEEPKEY", "DUPKEY")

    msg = str(ei.value).lower()
    assert "child1" in msg            # already-moved children named
    assert "not saved" in msg         # keep's changes were not saved
    assert "nothing was trashed" in msg


def test_merge_duplicates_trash_failure_wrapped_keep_already_updated(monkeypatch, fake_pyzotero):
    dual = _dual(monkeypatch, local_available=False)
    keep_item, _ = _merge_fixture(dual)

    def fail_on_patch(req, timeout=None):
        raise RuntimeError("network blip")
    monkeypatch.setattr(urllib.request, "urlopen", fail_on_patch)

    with pytest.raises(zc.ZoteroWriteError) as ei:
        dual.merge_duplicates("KEEPKEY", "DUPKEY")

    msg = str(ei.value)
    assert "DUPKEY" in msg
    assert "trash_item" in msg.lower() or "by hand" in msg.lower()
    # keep's update DID happen before the trash attempt
    assert set(keep_item["data"]["collections"]) == {"COLLA", "COLLB"}


# ---------------- restore_item (ZOT-MERGE-027 "trash/restore" follow-up) ----------------
def test_restore_item_patches_deleted_flag_to_zero(monkeypatch, fake_pyzotero):
    import json as _json
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
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert dual.restore_item("ITEM01") is True
    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/items/ITEM01")
    assert _json.loads(captured["body"]) == {"deleted": 0}
