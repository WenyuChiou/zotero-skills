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
