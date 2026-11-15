# Working rules

<!-- project-kit v1 (solo). Installed from ~/.claude/project-kit. Keep this page under 4 KB:
merge or delete a rule before adding one. Rules every repo shares live in ~/.claude, not here. -->

Workflow mode: solo

## Every change

1. **One change at a time.** A commit or PR holds one feature, or two or three related bug fixes. Never mix a refactor or a cleanup into a fix.
2. **Show it works.** Before saying a change is done, run the tests it touches and quote the command and its result. If you could not run them, say "not verified". CI, where the repo has it, runs the full suite.
3. **Commit checks stay on.** The kit installs three git hooks: a review gate (a change of 50 or more lines, three or more files, or a governance file needs a reviewer's ack first), a secret scan, and a check that scope-sensitive files are named in the commit message. Do not skip them with `--no-verify` unless the owner says so.

## Bug fixes

4. **Fail first.** Every bug fix comes with a test that fails without the fix and passes with it. Prove it before the commit:

   ```bash
   python scripts/fail_first.py -- python -m pytest -q '{tests}'
   ```

   It runs the changed tests on the base commit (they must fail) and on your branch (they must pass). Put its last line in the PR.

## Pull requests

5. **Fill in the PR template:** what changed, how it was checked, and the fail-first result for a fix.

## Rules about rules

6. **A rule gets a check when it can.** When a mistake repeats, add a test, lint rule or hook that catches it, and shrink the rule here to one line that points at that check.
7. **Project rules stay here.** Add what only this project needs below this line; keep the page under 4 KB.

## Project rules

<!-- Add this project's own rules here. -->
