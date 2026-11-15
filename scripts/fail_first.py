#!/usr/bin/env python3
"""Fail-first check: a fix's tests must fail without the fix and pass with it.

The changed test files are copied onto a checkout of the base commit, where the test
command must FAIL, and the same command runs on this working tree, where it must PASS.
A test that passes on both does not check the change.

Usage:
    python scripts/fail_first.py [--base REF] [--tests PATH ...] [--setup CMD] -- CMD ...

CMD is the test command; an argument '{tests}' is replaced by the test files,
otherwise they are appended. Keep the quotes: PowerShell reads a bare {tests} as a script block.
Examples (Bash and PowerShell alike):
    python scripts/fail_first.py -- python -m pytest -q '{tests}'
    python scripts/fail_first.py --setup "npm ci" -- npx vitest run '{tests}'

Each run puts its own tree's src/ and top folder first on PYTHONPATH, so an editable install of
another checkout cannot stand in for the code under test (not with python -E or -I, which ignore
PYTHONPATH: then the installed copy may be the one tested).

Exit: 0 fails on base and passes here; 1 it does not; 2 usage error, nothing to check, or the command
could not run. Read the base output it prints: the base run should fail because the test catches the
missing change, not because a dependency or runner is missing there.
Part of the project kit in ~/.claude/project-kit (stdlib only, any test language).
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_NAMES = ("test_*.py", "*_test.py", "*.test.*", "*.spec.*", "*_test.go", "*Test.java")
TEST_DIRS = {"tests", "test", "__tests__", "spec"}
TAIL = 15
NOT_FOUND = {127, 9009}  # "command not found" from sh and from cmd.exe
PLACEHOLDERS = ("{tests}", "'{tests}'")  # cmd.exe passes the single quotes through


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-c", "core.longpaths=true", "-c", "core.quotepath=false", *args], cwd=repo,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout


def is_test_path(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return any(p in TEST_DIRS for p in parts[:-1]) or any(fnmatch.fnmatch(parts[-1], n) for n in TEST_NAMES)


def default_base(repo: Path) -> str:
    for ref in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        try:
            git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
            return ref
        except RuntimeError:
            continue
    raise RuntimeError("no base branch found; pass --base")


def changed_tests(repo: Path, base: str) -> list[str]:
    tracked = git(repo, "diff", "--name-only", "--diff-filter=AMR", base).splitlines()
    untracked = git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({p for p in tracked + untracked if p and is_test_path(p) and (repo / p).is_file()})


def build_command(cmd: list[str], tests: list[str]) -> list[str]:
    out = [a for c in cmd for a in (tests if c in PLACEHOLDERS else [c])]
    if not any(c in PLACEHOLDERS for c in cmd):
        out += tests
    found = shutil.which(out[0])
    return [found or out[0], *out[1:]]


def own_env(tree: Path) -> dict[str, str]:
    """Environment where Python imports this tree's code before any installed copy."""
    first = [str(tree / "src")] if (tree / "src").is_dir() else []
    rest = os.environ.get("PYTHONPATH")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([*first, str(tree), *([rest] if rest else [])])
    return env


def run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=own_env(cwd))
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout} s"
    except OSError as exc:
        return -2, f"could not start {cmd[0]}: {exc}"


def cleanup(repo: Path, tmp: Path, checkout: Path, added: bool) -> None:
    """Remove only the checkout this run made; never prune other worktrees' records."""
    removed = not added
    if added:
        try:
            git(repo, "worktree", "remove", "--force", str(checkout))
            removed = True
        except RuntimeError:
            pass
    shutil.rmtree(tmp, ignore_errors=True)
    if not removed:
        try:  # git also removes a worktree whose folder is already gone
            git(repo, "worktree", "remove", "--force", str(checkout))
        except RuntimeError as exc:
            print(f"fail-first: could not remove the base checkout record ({exc}); remove it with"
                  f" git worktree remove --force {checkout}", file=sys.stderr)


def tail(text: str) -> str:
    return "\n".join("    " + line for line in text.strip().splitlines()[-TAIL:])


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # a test runner's ✓ must not crash a cp950 console
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print("usage: fail_first.py [--base REF] [--tests PATH ...] [--setup CMD] -- CMD ...", file=sys.stderr)
        return 2
    split = argv.index("--")
    opts, cmd = argv[:split], argv[split + 1:]
    p = argparse.ArgumentParser(prog="fail_first.py")
    p.add_argument("--base")
    p.add_argument("--tests", nargs="+")
    p.add_argument("--setup", help="command run in the base checkout first, e.g. 'npm ci'")
    p.add_argument("--timeout", type=int, default=600)
    a = p.parse_args(opts)
    if not cmd:
        print("fail-first: no test command after --", file=sys.stderr)
        return 2
    try:
        repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
        base_ref = a.base or default_base(repo)
        base = git(repo, "merge-base", "HEAD", base_ref).strip()
        tests = sorted(set(a.tests)) if a.tests else changed_tests(repo, base)
    except RuntimeError as exc:
        print(f"fail-first: {exc}", file=sys.stderr)
        return 2
    missing = [t for t in tests if not (repo / t).is_file()]
    if missing or not tests:
        print(f"fail-first: no test files to check{': missing ' + ', '.join(missing) if missing else ''}",
              file=sys.stderr)
        return 2
    command = build_command(cmd, tests)
    print(f"fail-first: base {base_ref} ({base[:10]}), tests: {', '.join(tests)}")
    tmp = Path(tempfile.mkdtemp(prefix="fail-first-"))
    checkout = tmp / "base"
    added = False
    try:
        git(repo, "worktree", "add", "--detach", str(checkout), base)
        added = True
        for t in tests:
            (checkout / t).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / t, checkout / t)
        if a.setup:
            code, out = run(build_command(shlex.split(a.setup, posix=os.name != "nt"), []), checkout, a.timeout)
            if code:
                print(f"fail-first: setup failed in the base checkout (exit {code})\n{tail(out)}", file=sys.stderr)
                return 2
        # Judge from the text as typed: Path("./run.cmd") drops the "./" and would look like a bare command name.
        raw = cmd[0]
        is_path = "/" in raw or "\\" in raw
        if is_path and not Path(raw).is_absolute() and not (checkout / raw).exists():
            print(f"fail-first: {command[0]} does not exist in the base checkout, so the tests cannot run there;"
                  " give its absolute path, or a command both versions have", file=sys.stderr)
            return 2
        base_code, base_out = run(command, checkout, a.timeout)
        head_code, head_out = run(command, repo, a.timeout)
    except RuntimeError as exc:
        print(f"fail-first: {exc}", file=sys.stderr)
        return 2
    finally:
        cleanup(repo, tmp, checkout, added)
    for where, code, out in (("base checkout", base_code, base_out), ("working tree", head_code, head_out)):
        if code < 0 or code in NOT_FOUND:
            print(f"fail-first: the test command could not run in the {where} (exit {code}), so nothing was"
                  f" checked\n{tail(out)}", file=sys.stderr)
            return 2
    print(f"  without the change (base): exit {base_code}{' (should fail)' if base_code == 0 else ''}")
    print(tail(base_out))
    print(f"  with the change (here):    exit {head_code}{' (should pass)' if head_code != 0 else ''}")
    if head_code:
        print(tail(head_out))
    if base_code != 0 and head_code == 0:
        print("fail-first: OK - the tests fail without the change and pass with it")
        return 0
    if base_code == 0:
        print("fail-first: FAIL - the tests pass without the change, so they do not check it")
    else:
        print("fail-first: FAIL - the tests do not pass with the change")
    return 1


if __name__ == "__main__":
    sys.exit(main())
