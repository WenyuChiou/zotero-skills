"""Unit tests: check_local_api, safe_api_call, check_duplicate, note wrapping."""
import urllib.request
import urllib.error
from pathlib import Path

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


# ---------------- _pluralize_library_type (ZOT-MERGE-027) ----------------
def test_pluralize_library_type_maps_singular_user_and_group():
    # pyzotero's real Zotero() already stores the plural form, but this must
    # still produce it if a singular value ever reaches the helper.
    assert zc._pluralize_library_type("user") == "users"
    assert zc._pluralize_library_type("group") == "groups"


def test_pluralize_library_type_passes_through_already_plural():
    assert zc._pluralize_library_type("users") == "users"
    assert zc._pluralize_library_type("groups") == "groups"


# ---------------- _safe_attachment_filename (reviewer round 3 hardening) ----------------
def test_safe_attachment_filename_citation_style_name_has_no_real_extension():
    # "Smith et al. 2020" -> the ". 2020" tail is not a real extension; falls
    # back to .pdf, spaces become underscores, "zot_" prefix always applied.
    assert zc._safe_attachment_filename("Smith et al. 2020") == "zot_Smith_et_al.pdf"


def test_safe_attachment_filename_long_dotted_tail_not_treated_as_extension():
    name = zc._safe_attachment_filename("paper.final version for submission to journal")
    assert name == "zot_paper.pdf"


def test_safe_attachment_filename_reserved_windows_device_name_is_prefixed():
    # "CON" alone is a reserved Windows device name regardless of extension;
    # the "zot_" prefix guarantees the copy is never literally "CON.pdf".
    name = zc._safe_attachment_filename("CON.pdf")
    assert name == "zot_CON.pdf"
    assert Path(name).stem.upper() != "CON"


def test_safe_attachment_filename_keeps_a_real_short_extension():
    assert zc._safe_attachment_filename("notes.docx") == "zot_notes.docx"


def test_safe_attachment_filename_preserves_non_ascii_letters():
    # A CJK title must not collapse into the generic "attachment" fallback;
    # only whitespace and filename-unsafe characters are stripped.
    name = zc._safe_attachment_filename("洪水風險評估.pdf")
    assert name == "zot_洪水風險評估.pdf"


def test_safe_attachment_filename_always_under_max_length():
    long_name = ("A " * 60) + ".pdf"
    name = zc._safe_attachment_filename(long_name)
    assert len(name) <= zc._SAFE_FILENAME_MAX_LEN
    assert " " not in name


# ---------------- _normalize_doi / _normalize_title (ZOT-MERGE-027 guards) ----------------
def test_normalize_doi_strips_case_and_resolver_prefix():
    assert zc._normalize_doi("https://doi.org/10.1/ABC") == "10.1/abc"
    assert zc._normalize_doi("  10.1/AbC  ") == "10.1/abc"
    assert zc._normalize_doi("") == ""
    assert zc._normalize_doi(None) == ""


def test_normalize_doi_strips_dx_doi_org_and_http_and_doi_colon_variants():
    # Reviewer round 4: dx.doi.org, http (not just https), and "doi:" with an
    # optional space must all normalize to the same bare DOI.
    expected = "10.1/x"
    cases = [
        "https://dx.doi.org/10.1/X",
        "http://doi.org/10.1/X",
        "http://dx.doi.org/10.1/X",
        "doi: 10.1/X",
        "DOI:10.1/X",
        "https://doi.org/10.1/X",
    ]
    for c in cases:
        assert zc._normalize_doi(c) == expected, c


def test_normalize_title_collapses_whitespace_and_case():
    assert zc._normalize_title("  Book   A  ") == "book a"
    assert zc._normalize_title("") == ""


# ---------------- _extract_year / _first_creator_lastname (no-DOI fallback) ----------------
def test_extract_year_pulls_four_digits_from_messy_dates():
    assert zc._extract_year("2001") == "2001"
    assert zc._extract_year("May 2001") == "2001"
    assert zc._extract_year("") == ""
    assert zc._extract_year(None) == ""


def test_first_creator_lastname_normalizes_case():
    assert zc._first_creator_lastname({"creators": [{"lastName": "SMITH"}, {"lastName": "Jones"}]}) == "smith"
    assert zc._first_creator_lastname({"creators": []}) == ""
    assert zc._first_creator_lastname({}) == ""
