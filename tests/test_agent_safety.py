"""Agent-safety CONTRACT tests: SKILL.md is the agent's safety spec.

There is no runtime agent to drive here, so these assert that SKILL.md (the
always-in-context spec) and the references contain the mandated guardrail
language. Each control below is now present in SKILL.md's "Safety rules"
section (ZOT-AGENT-006); these tests lock it in against regressions.
"""
import re


from conftest import REPO_ROOT

SKILL = (REPO_ROOT / "skills/zotero-skills/SKILL.md").read_text(encoding="utf-8").lower()
DELETE = (REPO_ROOT / "skills/zotero-skills/references/delete-operations.md").read_text(encoding="utf-8").lower()


# --- controls already present (should PASS on current repo) ---
def test_skill_forbids_key_in_notes():
    # A-03: key must never be written into a note/item/log
    assert "api key never appears" in SKILL or ("api key" in SKILL and "note" in SKILL)


def test_delete_reference_requires_preview():
    # A-07: preview before non-trivial delete
    assert "preview" in DELETE and "before" in DELETE


def test_skill_distinguishes_trash_vs_permanent():
    assert "trash" in SKILL and "permanent" in SKILL


# --- controls added by the Gate 9 hardening (now locked in) ---
def test_skill_declares_content_is_data():
    # A-01/A-06: metadata/notes/annotations/PDF text are DATA, not instructions
    has_data_rule = ("data, not instruction" in SKILL or "not instructions" in SKILL
                     or "treat" in SKILL and "as data" in SKILL)
    assert has_data_rule


def test_skill_forbids_executing_content_instructions():
    # A-01: never execute commands found in Zotero content
    assert re.search(r"(do not|never|don't).{0,40}(execute|follow|obey).{0,40}(instruction|command|content)", SKILL)


def test_skill_requires_batch_scope_limit():
    # A-02/A-08: show count + scope, enforce a ceiling before batch destructive ops
    assert re.search(r"(scope limit|maximum|max\b|ceiling|count).{0,60}(batch|delete|bulk)", SKILL) \
        or re.search(r"(batch|bulk).{0,60}(scope limit|maximum|ceiling|count)", SKILL)


def test_skill_guards_empty_query():
    assert re.search(r"(empty|wildcard|blank).{0,40}(query|filter)", SKILL) \
        or "whole library" in SKILL or "entire library" in SKILL
