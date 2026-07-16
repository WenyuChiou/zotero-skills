"""Unit tests: check_local_api, safe_api_call, check_duplicate, note wrapping."""
import urllib.request
import urllib.error

import pytest

import zotero_client as zc
from conftest import FakeZotero


# ---------------- check_local_api ----------------
class _Recorder:
    def __init__(self):
        self.req = None
        self.timeout = None

    def __call__(self, req, timeout=None):
        self.req = req
        self.timeout = timeout
        class _Resp:
            def read(self_inner):
                return b"{}"
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, *a):
                return False
        return _Resp()


def test_check_local_api_uses_loopback_and_timeout(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", rec)
    assert zc.check_local_api(timeout=1) is True          # U-09
    assert rec.req.full_url.startswith("http://localhost:23119/api")
    assert rec.req.headers.get("Zotero-allowed-request") == "true"  # urllib title-cases header keys
    assert rec.timeout == 1


def test_check_local_api_returns_false_on_error(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("refused")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert zc.check_local_api(timeout=1) is False          # M-02 unit-level


def test_check_local_api_does_not_hardcode_real_library_id(monkeypatch):
    # ZOT-SEC-002 fixed: no hardcoded id; uses the passed/env library id.
    rec = _Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", rec)
    zc.check_local_api(timeout=1)
    assert "14772686" not in rec.req.full_url               # U-10


def test_check_local_api_uses_passed_library_id(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", rec)
    zc.check_local_api(timeout=1, library_id="9999999")
    assert "/users/9999999/" in rec.req.full_url


def test_check_local_api_reachable_on_http_error(monkeypatch):
    # A responding-but-error server still means Zotero is up.
    def http_err(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", http_err)
    assert zc.check_local_api(timeout=1, library_id="1") is True


# ---------------- safe_api_call ----------------
def test_safe_api_call_retries_on_429(monkeypatch):
    monkeypatch.setattr(zc.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Exception("429 Too Many Requests")
        return "ok"

    assert zc.safe_api_call(flaky, max_retries=5) == "ok"   # U-11
    assert calls["n"] == 3


def test_safe_api_call_reraises_non_429(monkeypatch):
    monkeypatch.setattr(zc.time, "sleep", lambda *_: None)

    def boom():
        raise Exception("500 Server Error")

    with pytest.raises(Exception) as ei:
        zc.safe_api_call(boom, max_retries=5)               # U-12
    assert "500" in str(ei.value)


def test_safe_api_call_exhausts_retries(monkeypatch):
    monkeypatch.setattr(zc.time, "sleep", lambda *_: None)

    def always_429():
        raise Exception("429")

    with pytest.raises(Exception) as ei:
        zc.safe_api_call(always_429, max_retries=2)          # U-13
    assert "Max retries" in str(ei.value)


# ---------------- check_duplicate ----------------
def test_check_duplicate_matches_title():
    z = FakeZotero()
    z._items = [{"data": {"title": "My Paper", "DOI": ""}}]
    assert zc.check_duplicate(z, "my paper") is True         # case-insensitive


def test_check_duplicate_matches_doi():
    z = FakeZotero()
    z._items = [{"data": {"title": "Other", "DOI": "10.1/x"}}]
    assert zc.check_duplicate(z, "Nonmatch", doi="10.1/x") is True


def test_check_duplicate_survives_titleless_item():
    # ZOT-COR-005 fixed: title-less items no longer crash the dedup guard.
    z = FakeZotero()
    z._items = [{"data": {"DOI": "10.9/z"}}]  # no 'title' key (valid for some item types)
    assert zc.check_duplicate(z, "Whatever") is False        # U-14


# ---------------- note wrapping ----------------
def test_add_note_wraps_plain_text():
    z = FakeZotero()
    ok = zc.add_note(z, "PARENT01", "plain finding")          # U-15
    assert ok is True
    created = [c for c in z.calls if c[0] == "create_items"][0]
    note = created[1][0][0]
    assert note["note"] == "<p>plain finding</p>"
    assert note["parentItem"] == "PARENT01"


def test_add_note_preserves_existing_html():
    z = FakeZotero()
    zc.add_note(z, "PARENT01", "<p>already</p>")
    created = [c for c in z.calls if c[0] == "create_items"][0]
    note = created[1][0][0]
    assert note["note"] == "<p>already</p>"


def test_add_note_surfaces_write_failure():
    # Must not silently swallow a rejected item (parity with create_* / ZOT-SILENT-007).
    z = FakeZotero()
    z._create_failed = {"0": {"code": 400, "message": "bad"}}
    with pytest.raises(zc.ZoteroWriteError):
        zc.add_note(z, "PARENT01", "x")
