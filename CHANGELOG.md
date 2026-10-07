# Changelog

All notable changes to `zotero-skills` (the Claude Code skill at
`WenyuChiou/zotero-skills`). Format:
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning:
[SemVer](https://semver.org/spec/v2.0.0.html).

This skill ships via the
[`WenyuChiou/ai-research-skills`](https://github.com/WenyuChiou/ai-research-skills)
marketplace; see that repo's CHANGELOG for the catalog-side history.

## [Unreleased]

## [0.3.1] - 2026-10-07

### Fixed

- `ZoteroDualClient.attach_pdf()` failed on every call against the
  installed pyzotero (1.7.6): it called `attachment_both([(title,
  str(tmp_path))], parent_key)`, which sets the attachment template's
  `filename` field to the literal string passed in -- including the
  temp directory -- and sends it VERBATIM as item metadata. The real
  Zotero API rejects any directory separator there with HTTP 400,
  "Stored-file filename '...' cannot contain a directory path"
  (ZOT-ATTACH-028). `attach_pdf` now builds the attachment template
  directly and calls pyzotero's `upload_attachments(..., basedir=
  tmp_dir)`, passing only the bare safe filename in the payload and
  letting `basedir` resolve it locally when reading the file -- the
  directory never reaches the server. A pyzotero dedup hit (file
  already present by MD5 somewhere in the library) now also counts as
  success: pyzotero reports that case via `unchanged`, never `success`,
  even though the attachment item is genuinely created either way. It
  also now reads the created attachment back from the Web API and
  confirms an `md5` before returning (wrapping a read-back failure in
  `ZoteroWriteError` too), rather than trusting the upload call's own
  report. **Return shape changed**: `attach_pdf()` now returns
  `{"key", "md5", "title", "filename", "raw"}` instead of pyzotero's
  raw upload-result dict -- every 0.3.0 call failed before reaching a
  caller that could depend on the old shape. Verified against a real
  Zotero library (temporary item + PDF attachment + read-back + trash).
- English and Traditional Chinese credential diagnostics now use the
  value-free `credentials_status()` helper, never key-echo instructions.
- Codex documentation identifies `-C` / `--cd` as a working directory;
  client examples resolve the repository/plugin-root `scripts` module.
- Corrected the 0.3.0 attachment implementation description to name
  `attachment_both`; the historical raw `attachment_simple` caveat remains.

## [0.3.0] - 2026-10-01

Fixes agents wrongly concluding that Zotero writes, duplicate merges,
restoring a trashed item, and PDF attachment are impossible.

### Added

- `credentials_status()`: reports whether an API key / library ID are
  configured and which layer they came from (env var, `~/.claude/.env`,
  or `config.json`), as booleans and a source label only, never the
  value. Lets an agent check credentials without opening either file.
- `ZoteroDualClient.restore_item(key)` / `restore_items(keys)`: reverses
  `trash_item()` by PATCHing `deleted=0`, mirroring the same raw-PATCH
  technique (pyzotero's `update_item` rejects the `deleted` field either
  way).
- `ZoteroDualClient.attach_pdf(parent_key, path, filename=None)`: copies
  the file to a short, space-free, `zot_`-prefixed temp filename (the
  prefix rules out a Windows-reserved device name like `CON`; non-ASCII
  letters, e.g. CJK titles, are preserved) before calling pyzotero's
  `attachment_both`, and raises with the failed-upload detail instead
  of returning a silent `{"failure": [...]}` (fixes a real silent
  failure against a long Windows path with spaces).
- `ZoteroDualClient.merge_duplicates(keep_key, dup_key, require_same_doi=True)`:
  merges two duplicate items over the Web API, which has no native merge
  endpoint. Reproduces the core of a desktop merge: moves every
  (non-trashed) child, paginating with `everything()`; unions
  collections, tags, and the duplicate's own relations (any predicate)
  onto a freshly re-read keeper; adds a `dc:replaces` relation; trashes
  the duplicate last. Refuses `keep_key == dup_key`, a note/attachment/
  child item, an already-deleted item, or an identity mismatch (DOIs
  normalized for case and a doi.org prefix; a title match is required
  when both DOIs are empty) unless explicitly overridden. A failure
  partway through moving children is wrapped in `ZoteroWriteError`
  listing which child keys already moved; nothing is trashed yet at
  that point, so re-running is safe.
- `skills/zotero-skills/references/merge-duplicates.md`: the merge
  recipe, what it does and does not reproduce from the desktop merge,
  and the helper usage.
- `.github/workflows/ci.yml`: pytest matrix (3.10-3.13) + ruff + a
  full-history gitleaks secret scan.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `.pre-commit-config.yaml`.

### Changed

- `SKILL.md`: rewrote the frontmatter `description`, the capability
  table, and the "Common false negatives" list to state that writes
  work via the shared client even though the *separately configured*
  `zotero` MCP server's tools are read-only (this plugin does not
  bundle that server), that credentials should be checked with
  `credentials_status()` rather than by opening a file, that "find a
  missing PDF" is guidance only (no helper function), and that merging
  reproduces the core of a desktop merge, not all of it. Added 8 new
  Chinese trigger phrases and a safety-rule note that merging trashes an
  item.
- `references/create-operations.md` / `references/api-setup.md`:
  documented the `attachment_simple` silent-failure caveat precisely
  (pyzotero raises its own failed-upload entry, not a deeper server
  reason), and added `credentials_status`, `restore_item`, and
  `merge_duplicates` to the helper function table.
- `README.md` / `README_zh-TW.md`: expanded the "What It Can Do" section
  (kept in lockstep) to four points: writes via `credentials_status()`,
  merge (core of desktop merge, restorable), reliable attach, and
  guided PDF search. Credential setup now leads with `~/.claude/.env`,
  demoting `config.json` to a clearly-labeled legacy fallback; added CI
  + License badges.

### Why

An agent checked only the shell environment for `ZOTERO_API_KEY`, found
nothing, and declared writes impossible (the key was in
`~/.claude/.env`); it said a duplicate had to be merged by hand because
the Web API has no merge endpoint; and it said a PDF needed a manual
download when a local copy already existed. Separately,
`attachment_simple` failed silently on a long Windows path with spaces.
A review pass then found the first merge implementation itself had
real gaps: it trashed the keeper on a self-merge, used the wrong
(singular) library-type segment in its own relation URI, dropped the
duplicate's own relations, and let two unrelated items with blank DOIs
merge. This release documents the three original false negatives and
fixes all of the above, plus the credential-check and PDF-restore gaps
a stricter review surfaced. A second review pass then found: a
same-item-related-to-itself relation when the pair was already linked
as "Related"; a case-sensitive self-merge check that missed
differently-cased spellings of one key; two unrelated items with blank
DOIs but a shared generic title (e.g. "Introduction") merging anyway;
`credentials_status()`'s `library_type` disagreeing with what
`_load_credentials()` actually resolves; unwrapped keeper-update/trash
failures; missing `dx.doi.org`/`http://`/`doi:` (with an optional space) DOI
prefix variants;
and an attachment losing its readable title to the short safe filename.
All fixed, with tests pinning each one.

## [0.2.0] - 2026-07-16

Security/correctness audit (PR #5): added the `tests/` suite that did
not exist at 0.1.0, and fixed real bugs found by testing against the
live API. GitHub Actions CI came later, in 0.3.0.

### Added

- `tests/` unit + mock-integration test suite (previously "on the
  roadmap but not promised" per the 0.1.0 Known limitations).

### Fixed

- `delete_items` batch 412: pyzotero's batch `delete_item(list)` sends
  the first item's version as a library-level precondition and 412s as
  soon as items have differing versions; now deletes per item, each
  with its own fresh version.
- `add_note` write failures were silently swallowed; now raises
  `ZoteroWriteError` on a rejected item, consistent with the `create_*`
  methods.

### Changed

- Scoped the PDF-attachment claim in docs to what `zot.attachment_simple`
  actually did at this version (raw pyzotero, not yet a shared-client
  helper).
- `delete_items` doc comment corrected: per-item, not chunked.
- Read-back API guidance clarified.

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

[Unreleased]: https://github.com/WenyuChiou/zotero-skills/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/WenyuChiou/zotero-skills/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/WenyuChiou/zotero-skills/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/WenyuChiou/zotero-skills/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/WenyuChiou/zotero-skills/releases/tag/v0.1.0
