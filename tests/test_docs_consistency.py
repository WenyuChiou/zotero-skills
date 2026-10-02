"""Documentation Declared-vs-Actual tests. These lock in the Gate 9 doc fixes
(rate-limit consistency, expanded sys.path, real reference-file layout, deps/LICENSE)."""
import re


from conftest import REPO_ROOT

README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
README_ZH = (REPO_ROOT / "README_zh-TW.md").read_text(encoding="utf-8")
SKILL = (REPO_ROOT / "skills/zotero-skills/SKILL.md").read_text(encoding="utf-8")
API_SETUP = (REPO_ROOT / "skills/zotero-skills/references/api-setup.md").read_text(encoding="utf-8")
ERR = (REPO_ROOT / "skills/zotero-skills/references/error-handling.md").read_text(encoding="utf-8")
ALL_DOCS = {"README.md": README, "README_zh-TW.md": README_ZH, "SKILL.md": SKILL,
            "api-setup.md": API_SETUP, "error-handling.md": ERR}


def test_skill_see_also_reference_files_exist():
    # D-01: every references/*.md named in SKILL.md must exist.
    refs = re.findall(r"references/([a-z-]+\.md)", SKILL)
    assert refs
    for r in set(refs):
        assert (REPO_ROOT / "skills/zotero-skills/references" / r).exists(), r


def test_marketplace_layout_matches_docs():
    # D-05: files the install docs rely on must exist.
    assert (REPO_ROOT / ".claude-plugin/plugin.json").exists()
    assert (REPO_ROOT / "skills/zotero-skills/SKILL.md").exists()


def test_en_zh_readme_structural_alignment():
    # D-06: same number of H2 sections in both languages.
    en_h2 = len(re.findall(r"^## ", README, re.M))
    zh_h2 = len(re.findall(r"^## ", README_ZH, re.M))
    assert en_h2 == zh_h2, f"EN {en_h2} vs ZH {zh_h2} H2 sections"


def test_rate_limit_figure_is_consistent():
    # D-02: collect every 'N req / 10 sec' figure across docs; must be one value.
    nums = set()
    for txt in ALL_DOCS.values():
        for m in re.findall(r"~?(\d+)\s*(?:req(?:uests)?)\s*/\s*10\s*sec", txt):
            nums.add(int(m))
    assert len(nums) <= 1, f"inconsistent rate-limit figures: {sorted(nums)}"


def test_no_unexpanded_tilde_in_syspath_examples():
    # D-03
    for name, txt in ALL_DOCS.items():
        assert 'sys.path.insert(0, r"~' not in txt, name
        assert "sys.path.insert(0, r'~" not in txt, name


def test_docs_dir_claim_matches_reality():
    # D-04
    docs_dir = REPO_ROOT / "docs"
    advertises = "screenshot" in README.lower()
    non_empty = docs_dir.exists() and any(docs_dir.iterdir())
    assert (not advertises) or non_empty


def test_dependency_declaration_exists():
    # D-07
    assert (REPO_ROOT / "requirements.txt").exists() or (REPO_ROOT / "pyproject.toml").exists()


def test_config_json_is_gitignored():
    gi = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "config.json" in gi


def test_credential_diagnostics_do_not_echo_api_key_values():
    for name, text in ALL_DOCS.items():
        assert not re.search(r"echo\s+\$\{?ZOTERO_API_KEY", text), name
        assert not re.search(r"`\$Env:ZOTERO_API_KEY`", text, re.I), name
    for text in (README, README_ZH):
        assert "credentials_status()" in text


def test_codex_c_is_working_directory_not_context_file():
    for text in (README, README_ZH):
        row = next(line for line in text.splitlines() if "**Codex CLI**" in line)
        assert "--cd" in row
        assert "directory" in row or "工作目錄" in row


def test_readme_examples_use_repository_root_module_path():
    for text in (README, README_ZH):
        assert "from scripts.zotero_client import ZoteroDualClient" in text
        assert "~/.claude/skills/zotero-skills/scripts" not in text
        assert "credentials_status()" in text


def test_current_attachment_changelog_names_actual_api():
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    current = changelog.split("## [0.3.0]", 1)[1].split("## [0.2.0]", 1)[0]
    assert "before calling pyzotero's\n  `attachment_both`" in current


def test_documented_safe_diagnostic_runs_without_echoing_values(tmp_path):
    import os
    import subprocess
    import sys
    secret = "synthetic-do-not-echo-key"
    library = "synthetic-do-not-echo-library"
    env = dict(os.environ, HOME=str(tmp_path), ZOTERO_API_KEY=secret, ZOTERO_LIBRARY_ID=library)
    code = 'from scripts.zotero_client import credentials_status; print(credentials_status())'
    assert code in README and code in README_ZH
    run = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert "'api_key_set': True" in run.stdout
    assert "'api_key_source': 'env'" in run.stdout
    assert secret not in run.stdout + run.stderr
    assert library not in run.stdout + run.stderr
