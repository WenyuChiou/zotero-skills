#!/usr/bin/env python3
"""
Zotero Literature Addition Script Template.

Copy and modify this script for adding literature to specific tasks.

Usage:
    python add_literature.py

Configuration:
    Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID environment variables,
    or modify the constants below.
"""

import os
from typing import Dict, List, Optional

try:
    from pyzotero import zotero
except ImportError:
    print("Error: pyzotero not installed. Run: pip install pyzotero")
    exit(1)


# =============================================================================
# Configuration
# =============================================================================

# From .mcp.json or environment variables
ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "YOUR_API_KEY_HERE")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "YOUR_LIBRARY_ID")
ZOTERO_LIBRARY_TYPE = "user"  # or "group"


# =============================================================================
# Helper Functions
# =============================================================================

def create_client():
    """Create Zotero API client."""
    return zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)


def add_journal_article(
    zot,
    title: str,
    authors: List[Dict[str, str]],
    journal: str,
    year: str,
    volume: str = "",
    issue: str = "",
    pages: str = "",
    doi: str = "",
    abstract: str = "",
    tags: List[str] = None,
    note: str = "",
    collections: List[str] = None,
) -> Optional[str]:
    """
    Add a journal article to Zotero.

    Args:
        zot: Zotero client
        title: Article title
        authors: List of {"firstName": "...", "lastName": "..."} dicts
        journal: Journal name
        year: Publication year
        volume: Journal volume
        issue: Journal issue
        pages: Page range
        doi: DOI (without https://doi.org/)
        abstract: Article abstract
        tags: List of tag strings
        note: Note content (HTML supported)
        collections: List of collection keys to assign item to.
            IMPORTANT: Always provide at least one collection key
            to avoid orphaned items in the library root.

    Returns:
        Item key if successful, None otherwise
    """
    template = zot.item_template("journalArticle")

    template["title"] = title
    template["publicationTitle"] = journal
    template["date"] = year
    template["volume"] = volume
    template["issue"] = issue
    template["pages"] = pages
    template["DOI"] = doi
    template["abstractNote"] = abstract

    template["creators"] = [
        {"creatorType": "author", "firstName": a.get("firstName", ""), "lastName": a.get("lastName", "")}
        for a in authors
    ]

    if tags:
        template["tags"] = [{"tag": t} for t in tags]

    if collections:
        template["collections"] = collections

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            item_key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created: {title[:50]}... (key: {item_key})")

            if note:
                add_note(zot, item_key, note)

            return item_key
        else:
            print(f"[ERROR] Failed: {title}")
            print(f"        {response.get('failed', {})}")
            return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def add_preprint(
    zot,
    title: str,
    authors: List[Dict[str, str]],
    repository: str,
    archive_id: str,
    year: str,
    abstract: str = "",
    tags: List[str] = None,
    note: str = "",
    collections: List[str] = None,
) -> Optional[str]:
    """Add a preprint (arXiv, etc.) to Zotero.

    Args:
        collections: List of collection keys to assign item to.
            IMPORTANT: Always provide at least one collection key
            to avoid orphaned items in the library root.
    """
    template = zot.item_template("preprint")

    template["title"] = title
    template["repository"] = repository
    template["archiveID"] = archive_id
    template["date"] = year
    template["abstractNote"] = abstract
    template["url"] = f"https://arxiv.org/abs/{archive_id}" if repository == "arXiv" else ""

    template["creators"] = [
        {"creatorType": "author", "firstName": a.get("firstName", ""), "lastName": a.get("lastName", "")}
        for a in authors
    ]

    if tags:
        template["tags"] = [{"tag": t} for t in tags]

    if collections:
        template["collections"] = collections

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            item_key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created: {title[:50]}... (key: {item_key})")

            if note:
                add_note(zot, item_key, note)

            return item_key
        else:
            print(f"[ERROR] Failed: {title}")
            return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def add_note(zot, item_key: str, content: str) -> bool:
    """Add a note to an existing item."""
    note_template = zot.item_template("note")
    note_template["note"] = f"<p>{content}</p>" if not content.startswith("<") else content
    note_template["parentItem"] = item_key

    try:
        response = zot.create_items([note_template])
        if response.get("successful"):
            print(f"       Note added to {item_key}")
            return True
        return False
    except Exception as e:
        print(f"       Note error: {e}")
        return False


# =============================================================================
# Main - Customize this section for your task
# =============================================================================

def main():
    """Add literature for your task."""
    zot = create_client()

    print("=" * 60)
    print("Adding Literature to Zotero")
    print("=" * 60)

    # Example: Add a journal article (always assign to at least one collection)
    add_journal_article(
        zot,
        title="Example Paper Title",
        authors=[
            {"firstName": "First", "lastName": "Author"},
            {"firstName": "Second", "lastName": "Author"},
        ],
        journal="Example Journal",
        year="2024",
        volume="1",
        issue="1",
        pages="1-10",
        doi="10.xxxx/xxxxx",
        abstract="Paper abstract here.",
        tags=["Task-XXX", "Example-Tag"],
        note="<strong>Key finding:</strong> Description of why this paper matters.",
        collections=["YOUR_COLLECTION_KEY"],  # Replace with your collection key (see SKILL.md)
    )

    # Example: Add an arXiv preprint (multiple collections OK)
    add_preprint(
        zot,
        title="Example Preprint Title",
        authors=[{"firstName": "First", "lastName": "Author"}],
        repository="arXiv",
        archive_id="2502.12110",
        year="2025",
        abstract="Preprint abstract.",
        tags=["Task-XXX", "LLM-Agent"],
        note="Applied in: Module name. Key contribution: Description.",
        collections=["YOUR_COLLECTION_KEY"],  # Replace with your collection key(s)
    )

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
