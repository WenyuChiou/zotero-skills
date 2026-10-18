"""Offline checks for plugin/changelog version drift and historical links."""
import json
import re

from conftest import REPO_ROOT


def _metadata():
    manifest = json.loads(
        (REPO_ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return manifest, changelog


def test_manifest_version_matches_latest_changelog_entry():
    manifest, changelog = _metadata()
    version = manifest["version"]
    assert re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version)
    versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M)
    assert versions and versions[0] == version
    assert len(versions) == len(set(versions))
    assert versions == sorted(
        versions, key=lambda value: tuple(map(int, value.split("."))), reverse=True
    )


def test_changelog_links_follow_the_manifest_version():
    manifest, changelog = _metadata()
    version = manifest["version"]
    links = dict(re.findall(r"^\[([^\]]+)\]: (\S+)$", changelog, re.M))
    versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M)
    assert set(versions) <= links.keys()
    prefix = manifest["repository"] + "/compare/"
    assert links["Unreleased"] == prefix + f"v{version}...HEAD"
    assert links[version].startswith(prefix)
    assert links[version].endswith(f"...v{version}")


def test_untagged_history_uses_immutable_commit_boundaries():
    manifest, changelog = _metadata()
    links = dict(re.findall(r"^\[([^\]]+)\]: (\S+)$", changelog, re.M))
    prefix = re.escape(manifest["repository"] + "/compare/")
    # These development versions never received tags; do not restore broken URLs.
    assert re.fullmatch(prefix + r"v0\.2\.0\.\.\.[0-9a-f]{40}", links["0.3.0"])
    assert re.fullmatch(prefix + r"[0-9a-f]{40}\.\.\.[0-9a-f]{40}", links["0.3.1"])
