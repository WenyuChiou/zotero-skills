"""Unit tests: credential loading precedence, .env parsing, masking, malformed config."""
import json
import os
import warnings

import pytest

import zotero_client as zc


def test_env_vars_take_precedence(monkeypatch, fake_config, env_file):
    fake_config(zotero_api_key="CFGKEY", zotero_library_id="111")
    env_file(ZOTERO_API_KEY="ENVFILEKEY", ZOTERO_LIBRARY_ID="222")
    monkeypatch.setenv("ZOTERO_API_KEY", "OSENVKEY")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "333")
    key, lib, lib_type = zc._load_credentials()
    assert key == "OSENVKEY"          # U-01: os env beats .env and config
    assert lib == "333"


def test_env_file_used_when_os_env_absent(fake_config, env_file):
    fake_config(zotero_api_key="CFGKEY", zotero_library_id="111")
    env_file(ZOTERO_API_KEY="ENVFILEKEY", ZOTERO_LIBRARY_ID="222", ZOTERO_LIBRARY_TYPE="group")
    key, lib, lib_type = zc._load_credentials()
    assert key == "ENVFILEKEY"        # U-02: .env beats config
    assert lib == "222"
    assert lib_type == "group"


def test_config_json_fallback_emits_deprecation(fake_config):
    fake_config(zotero_api_key="CFGKEY", zotero_library_id="111")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        key, lib, _ = zc._load_credentials()
    assert key == "CFGKEY"            # U-03: config.json still works
    assert lib == "111"
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_read_env_file_parsing():
    # U-04: quotes, comments, blank lines. HOME is redirected by the autouse fixture;
    # write a real .env there and call the REAL _read_env_file end-to-end.
    home = zc.Path.home()
    envdir = home / ".claude"
    envdir.mkdir(parents=True, exist_ok=True)
    (envdir / ".env").write_text(
        '# comment\n\nZOTERO_API_KEY="quoted"\nZOTERO_LIBRARY_ID=333\n  # spaced comment\n',
        encoding="utf-8",
    )
    vals = zc._read_env_file()
    assert vals.get("ZOTERO_API_KEY") == "quoted"
    assert vals.get("ZOTERO_LIBRARY_ID") == "333"
    assert "# comment" not in vals


def test_read_env_file_missing_returns_empty():
    # U-05: HOME (redirected) has no .claude/.env -> {}
    assert zc._read_env_file() == {}


def test_missing_credentials_no_keyerror(fake_config):
    # U-06: config with no key/id present -> returns None/None, not KeyError
    fake_config()
    cfg_path = zc._CONFIG_PATH
    # overwrite with an empty object
    cfg_path.write_text(json.dumps({}), encoding="utf-8")
    key, lib, lib_type = zc._load_credentials()
    assert key is None and lib is None
    assert lib_type == "user"


def test_malformed_config_raises_cleanly(fake_config):
    # U-07: malformed JSON should raise a JSON error, and must not leak values
    fake_config()
    cfg_path = zc._CONFIG_PATH  # capture AFTER fake_config() reassigns _CONFIG_PATH
    cfg_path.write_text("{ this is : not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        zc._load_config()


def test_no_full_key_in_source_prints():
    # U-08 (static): the module must not print os.environ or a full-config dump.
    import inspect
    src = inspect.getsource(zc)
    assert "print(os.environ" not in src
    assert "print(cfg)" not in src


def test_no_perm_warning_for_restricted_file(tmp_path):
    # ZOT-CRED-012 (reviewer): a well-permissioned file must NOT warn. On Windows the
    # check is skipped entirely (mode bits are meaningless there); on POSIX chmod 600
    # makes it non-group/other-readable. Either way: no warning.
    p = tmp_path / "c.json"
    p.write_text("{}", encoding="utf-8")
    if os.name == "posix":
        os.chmod(p, 0o600)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        zc._warn_if_world_readable(p)
    assert not [x for x in w if "group/other-readable" in str(x.message)]


@pytest.mark.skipif(os.name != "posix", reason="mode-bit perms only meaningful on POSIX")
def test_perm_warning_fires_for_world_readable_posix(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{}", encoding="utf-8")
    os.chmod(p, 0o644)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        zc._warn_if_world_readable(p)
    assert [x for x in w if "group/other-readable" in str(x.message)]


# ---------------- credentials_status() (never leaks a secret value) ----------------
_SECRETS = {"OSENVKEY", "ENVFILEKEY", "CFGKEY", "222", "333", "111", "9999999"}


def _assert_no_secret_values(status: dict):
    for v in status.values():
        assert str(v) not in _SECRETS, f"credentials_status() leaked a value: {v!r}"


def test_credentials_status_reports_env_source_no_values(monkeypatch, fake_config, env_file):
    fake_config(zotero_api_key="CFGKEY", zotero_library_id="111")
    env_file(ZOTERO_API_KEY="ENVFILEKEY", ZOTERO_LIBRARY_ID="222")
    monkeypatch.setenv("ZOTERO_API_KEY", "OSENVKEY")
    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "333")

    status = zc.credentials_status()
    assert status["api_key_set"] is True
    assert status["api_key_source"] == "env"
    assert status["library_id_set"] is True
    assert status["library_id_source"] == "env"
    _assert_no_secret_values(status)


def test_credentials_status_reports_dotenv_source(fake_config, env_file):
    fake_config(zotero_api_key="CFGKEY", zotero_library_id="111")
    env_file(ZOTERO_API_KEY="ENVFILEKEY", ZOTERO_LIBRARY_ID="222", ZOTERO_LIBRARY_TYPE="group")

    status = zc.credentials_status()
    assert status["api_key_source"] == "~/.claude/.env"
    assert status["library_id_source"] == "~/.claude/.env"
    assert status["library_type"] == "group"
    assert status["dotenv_file_exists"] is True
    _assert_no_secret_values(status)


def test_credentials_status_reports_config_json_source(fake_config):
    fake_config(zotero_api_key="CFGKEY", zotero_library_id="111")

    status = zc.credentials_status()
    assert status["api_key_source"] == "config.json"
    assert status["library_id_source"] == "config.json"
    assert status["config_json_exists"] is True
    assert status["config_json_readable"] is True
    _assert_no_secret_values(status)


def test_credentials_status_reports_none_when_nothing_configured():
    status = zc.credentials_status()
    assert status["api_key_set"] is False
    assert status["api_key_source"] == "none"
    assert status["library_id_set"] is False
    assert status["library_id_source"] == "none"
    assert status["library_type"] == "user"
    assert status["dotenv_file_exists"] is False
    assert status["config_json_exists"] is False
    _assert_no_secret_values(status)


def test_credentials_status_library_type_matches_load_credentials_exactly(monkeypatch, env_file):
    # _load_credentials() has a quirk: when api_key/lib_id need the
    # ~/.claude/.env fallback, it ALSO re-resolves lib_type from that file,
    # overriding an already-resolved, higher-precedence shell-env lib_type.
    # credentials_status() must report whatever the real client will use,
    # not an independently "clean" precedence that could disagree with it.
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "group")
    env_file(ZOTERO_API_KEY="K", ZOTERO_LIBRARY_ID="1", ZOTERO_LIBRARY_TYPE="user")

    _, _, used_by_client = zc._load_credentials()
    reported = zc.credentials_status()["library_type"]
    assert reported == used_by_client
    assert reported == "user"  # documents the current (quirky) precedence
