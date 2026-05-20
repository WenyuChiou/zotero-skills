# Changelog

All notable changes to `zotero-skills` (the Claude Code skill at
`WenyuChiou/zotero-skills`). Format:
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning:
[SemVer](https://semver.org/spec/v2.0.0.html).

This skill ships via the
[`WenyuChiou/ai-research-skills`](https://github.com/WenyuChiou/ai-research-skills)
marketplace; see that repo's CHANGELOG for the catalog-side history.

## [Unreleased]

## [0.1.0] - 2026-05-20

The initial published version. Captures the skill state at commit
[`b543206`](https://github.com/WenyuChiou/zotero-skills/commit/b543206)
("Add MIT LICENSE file"), the HEAD on `master` when this CHANGELOG
was first added.

### Included

- `SKILL.md` (60 lines) — Claude Code skill manifest. Progressive
  disclosure: SKILL.md is intentionally small; the 7 `references/*`
  files are loaded on demand by the host (PR
  [#1](https://github.com/WenyuChiou/zotero-skills/pull/1)).
- `references/` — Zotero CRUD reference: API setup, item operations
  (search/add/update/delete), notes + tags + collections, PDF
  attachments, dual local/Web API routing.
- `config.json.example` — template for the local + Web API credentials
  (the real `config.json` is gitignored).
- Bilingual `README.md` + `README_zh-TW.md`.
- `LICENSE` — MIT (added in PR
  [#3](https://github.com/WenyuChiou/zotero-skills/pull/3)).
- `.claude-plugin/plugin.json` so the root SKILL.md is picked up by
  the `WenyuChiou/ai-research-skills` marketplace.

### Known limitations (as of 0.1.0)

- **No `tests/` directory**, **no GitHub Actions CI**. The skill is
  a documentation + API-routing reference; behaviour is verified by
  the maintainer on real Zotero libraries between releases. A
  programmatic test harness is on the roadmap but not promised.
- Tested by one graduate-student researcher against one Zotero
  library (~1100 items); not corpus-scale validated.
- Local Zotero API (port 23119) requires Zotero desktop running; this
  prerequisite is documented in the README, not enforced by the skill.

[Unreleased]: https://github.com/WenyuChiou/zotero-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/WenyuChiou/zotero-skills/releases/tag/v0.1.0
