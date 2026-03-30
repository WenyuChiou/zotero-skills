---
name: zotero-write
description: Add literature to Zotero library with notes, tags, and PDF attachments. Use when needing to write items to Zotero (MCP only supports read).
---

# Zotero Library Management Skill

Complete workflow for managing Zotero references: search, add, classify, annotate, and organize.

## Setup

### 1. Zotero MCP Server (Read Operations)

Install and configure a Zotero MCP server for read operations (`zotero_search_items`, `zotero_get_collections`, etc.). Add it to your `.mcp.json` or MCP settings.

### 2. pyzotero (Write Operations)

```bash
pip install pyzotero
```

### 3. API Credentials

1. Go to **https://www.zotero.org/settings/keys** and create a new API key
2. Grant the key **read/write** access to your personal library (and any groups you need)
3. Note your **User ID** from the same settings page
4. Set environment variables (or configure them in `.mcp.json`):

```bash
export ZOTERO_API_KEY="your-api-key-here"
export ZOTERO_LIBRARY_ID="your-user-id"
```

## Prerequisites

```python
import os, sys

# Windows encoding fix
sys.stdout.reconfigure(encoding='utf-8')

from pyzotero import zotero

ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID")

if not ZOTERO_API_KEY or not ZOTERO_LIBRARY_ID:
    raise ValueError(
        "Missing Zotero credentials. Set environment variables:\n"
        "  ZOTERO_API_KEY=<your key from https://www.zotero.org/settings/keys>\n"
        "  ZOTERO_LIBRARY_ID=<your user ID>"
    )

zot = zotero.Zotero(ZOTERO_LIBRARY_ID, "user", ZOTERO_API_KEY)
```

## Architecture

- **Read** (MCP tools): `zotero_search_items`, `zotero_get_item_metadata`, `zotero_get_collections`, etc.
- **Write** (`pyzotero`): Create items, add notes, assign collections, upload PDFs

## Workflow: Adding Literature

Always follow this sequence:

### Step 1: Check for Duplicates (MCP or pyzotero)

Before adding ANY item, search Zotero to avoid duplicates:

```
Use MCP tool: zotero_search_items with the paper title or DOI
```

Or via pyzotero (more reliable for DOI matching):

```python
# Prefer DOI search (most reliable)
if doi:
    existing = zot.items(q=doi, limit=5)
else:
    existing = zot.items(q=title[:50], limit=5)

# Check for match
is_duplicate = any(
    e["data"]["title"].lower() == title.lower()
    or e["data"].get("DOI", "") == doi
    for e in existing
)
```

If found, skip creation. If the existing item needs updates (notes, collections, tags), go to Step 5.

### Step 2: Create Item

```python
template = zot.item_template("journalArticle")  # See Item Types below
template["title"] = "Paper Title"
template["creators"] = [{"creatorType": "author", "firstName": "First", "lastName": "Last"}]
template["publicationTitle"] = "Journal Name"
template["date"] = "2024"
template["DOI"] = "10.xxxx/xxxxx"
template["abstractNote"] = "Abstract text"
template["tags"] = [{"tag": "Project-Name"}, {"tag": "Topic-Tag"}]  # See Tag Convention
template["collections"] = ["YOUR_COLLECTION_KEY"]  # MANDATORY - See Classification Guide

response = zot.create_items([template])
item_key = list(response["successful"].values())[0]["key"]
```

### Step 3: Add Note (MANDATORY)

Every item MUST have a structured note. Use the appropriate template:

```python
note_html = """
<h2>Reading Note</h2>
<p><b>Cited in:</b> Your paper/project, Section X.Y</p>
<p><b>Role:</b> Brief description of how this reference is used.</p>
<p><b>Key findings:</b></p>
<ul>
  <li>Finding 1</li>
  <li>Finding 2</li>
</ul>
"""
add_note(zot, item_key, note_html)
```

### Step 4: Upload PDF (Optional)

```python
from pathlib import Path
pdf_path = Path("path/to/paper.pdf")
zot.attachment_simple([str(pdf_path)], item_key)
```

### Step 5: Update Existing Item

```python
# Add to new collection
item = zot.item("EXISTING_KEY")
cols = item["data"].get("collections", [])
if "NEW_COLLECTION_KEY" not in cols:
    cols.append("NEW_COLLECTION_KEY")
    item["data"]["collections"] = cols
    zot.update_item(item)

# Add additional note
add_note(zot, "EXISTING_KEY", "<p><b>Update:</b> Also cited in Section X.Y.</p>")
```

## Item Types

| Type | Template Name | When to Use |
|------|--------------|-------------|
| Journal article | `journalArticle` | Peer-reviewed papers |
| Conference paper | `conferencePaper` | Conference proceedings |
| Book | `book` | Monographs |
| Book section | `bookSection` | Chapter in edited volume |
| Preprint | `preprint` | arXiv, SSRN, working papers |
| Thesis | `thesis` | PhD/Master dissertations |
| Report | `report` | Technical reports, government docs |
| Webpage | `webpage` | Online resources |

### Conference Paper Template

```python
template = zot.item_template("conferencePaper")
template["title"] = "Paper Title"
template["creators"] = [{"creatorType": "author", "firstName": "F", "lastName": "L"}]
template["conferenceName"] = "Conference Name 2024"
template["proceedingsTitle"] = "Proceedings of Conference"
template["date"] = "2024"
template["DOI"] = "10.xxxx/xxxxx"
template["pages"] = "1-10"
template["collections"] = ["YOUR_COLLECTION_KEY"]
```

### Book Template

```python
template = zot.item_template("book")
template["title"] = "Book Title"
template["creators"] = [{"creatorType": "author", "firstName": "F", "lastName": "L"}]
template["publisher"] = "Publisher Name"
template["place"] = "City"
template["date"] = "2024"
template["ISBN"] = "978-xxx"
template["numPages"] = "350"
template["collections"] = ["YOUR_COLLECTION_KEY"]
```

### Report Template

```python
template = zot.item_template("report")
template["title"] = "Report Title"
template["creators"] = [{"creatorType": "author", "lastName": "Organization", "firstName": ""}]
template["institution"] = "Issuing Institution"
template["date"] = "2024"
template["reportNumber"] = "Report-001"
template["url"] = "https://example.org/report"
template["collections"] = ["YOUR_COLLECTION_KEY"]
```

## Classification Guide

### Collection Hierarchy

Organize your Zotero collections to mirror your project structure. Example:

```
XXXXXXXX  My-Research-Project/
  XXXXXXXX    01-Theory/
    XXXXXXXX      Sub-Topic-A
    XXXXXXXX      Sub-Topic-B
  XXXXXXXX    02-Methods/
    XXXXXXXX      Quantitative
    XXXXXXXX      Qualitative
  XXXXXXXX    03-Applications/
    XXXXXXXX      Domain-A
    XXXXXXXX      Domain-B
  XXXXXXXX    04-Background/
    XXXXXXXX      Related-Work
```

> **Tip:** Find your collection keys via MCP (`zotero_get_collections`) or in the Zotero web UI URL.

### Auto-Classification Rules

Assign to a **primary** collection always; add **secondary** if a paper spans topics.

Customize this table for your project:

| Keywords in title/abstract | Primary Collection | Key |
|---|---|---|
| keyword-a, keyword-b | Sub-Topic-A | `YOUR_KEY` |
| keyword-c, keyword-d | Sub-Topic-B | `YOUR_KEY` |
| keyword-e, keyword-f | Quantitative | `YOUR_KEY` |
| keyword-g, keyword-h | Domain-A | `YOUR_KEY` |

### Classification Priority

When multiple categories match, assign primary by priority (highest first):

1. **Empirical data source** (primary evidence)
2. **Domain application** (applied context)
3. **Theory/Method** (foundational frameworks)
4. **Infrastructure** (tooling, architecture)

All others become secondary collections.

### Creating New Collections

If no existing collection fits:

```python
new_col = {
    "name": "New-Sub-Collection",
    "parentCollection": "PARENT_KEY",
}
result = zot.create_collections([new_col])
col_key = list(result["successful"].values())[0]["key"]
print(f"Created collection: {col_key}")
```

Then update this SKILL.md to include the new collection key.

## Tag Convention

| Tag Pattern | Purpose | Example |
|---|---|---|
| `Project-Name` | Which project cites this | `My-Thesis` |
| `Section-X.Y` | Specific section reference | `Section-3.2` |
| Topic tags | Thematic classification | `Machine-Learning`, `Survey`, `Benchmark` |
| Status tags | Reading status | `To-Read`, `In-Progress`, `Done` |

## Note Templates

### General Reading Note

```html
<h2>Reading Note</h2>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Role:</b> What this reference contributes to your work.</p>
<p><b>Key findings:</b></p>
<ul>
  <li>Finding 1</li>
  <li>Finding 2</li>
</ul>
<p><b>Relevance:</b> How this connects to your research question.</p>
```

### Theoretical Foundation

```html
<h2>Theory Reference</h2>
<p><b>Theory:</b> Name of theoretical framework</p>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Key contribution:</b> Core idea or model this paper introduces.</p>
<p><b>How we use it:</b> How the theory applies in your work.</p>
```

### Methodological Reference

```html
<h2>Methods Reference</h2>
<p><b>Method:</b> Name of method or technique</p>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Key idea:</b> What the method does and why it matters.</p>
<p><b>How we use/extend it:</b> Adaptations for your context.</p>
```

### Empirical Data Source

```html
<h2>Data Source</h2>
<p><b>Dataset/Metric:</b> Name and value range</p>
<p><b>Cited in:</b> Project name, Section X.Y</p>
<p><b>Key data:</b> What the paper reports (sample size, key statistics).</p>
<p><b>Methodology:</b> How the data was collected.</p>
<p><b>Limitations:</b> Scope constraints or caveats.</p>
```

## Helper Function

Standardized note creation — handles both raw text and HTML input:

```python
def add_note(zot, item_key: str, content: str) -> bool:
    """Add a note to an existing item. Auto-wraps plain text in <p> tags."""
    note_template = zot.item_template("note")
    if not content.strip().startswith("<"):
        content = f"<p>{content}</p>"
    note_template["note"] = content
    note_template["parentItem"] = item_key
    try:
        response = zot.create_items([note_template])
        if response.get("successful"):
            return True
        print(f"  Note failed for {item_key}: {response.get('failed', {})}")
        return False
    except Exception as e:
        print(f"  Note error for {item_key}: {e}")
        return False
```

## Batch Import

For adding multiple references at once with duplicate checking and rate limiting:

```python
import time

items_to_add = [
    {
        "type": "journalArticle",
        "title": "Example Paper Title",
        "authors": [{"firstName": "A", "lastName": "B"}],
        "journal": "Journal Name",
        "year": "2024",
        "doi": "10.xxx",
        "collections": ["YOUR_COLLECTION_KEY"],
        "tags": ["Project-Name", "Topic-Tag"],
        "note": "<p><b>Cited in:</b> Section X.Y</p>",
    },
    # ... more items
]

created = 0
skipped = 0
failed = 0

for i, item_info in enumerate(items_to_add):
    # Step 1: Duplicate check (DOI preferred, fallback to title)
    query = item_info.get("doi") or item_info["title"][:50]
    existing = zot.items(q=query, limit=5)
    if any(
        e["data"]["title"].lower() == item_info["title"].lower()
        or (item_info.get("doi") and e["data"].get("DOI", "") == item_info["doi"])
        for e in existing
    ):
        print(f"[SKIP] Already exists: {item_info['title'][:50]}")
        skipped += 1
        continue

    # Step 2: Create item
    template = zot.item_template(item_info["type"])
    template["title"] = item_info["title"]
    template["creators"] = [
        {"creatorType": "author", "firstName": a["firstName"], "lastName": a["lastName"]}
        for a in item_info["authors"]
    ]
    if item_info["type"] == "journalArticle":
        template["publicationTitle"] = item_info.get("journal", "")
    elif item_info["type"] == "conferencePaper":
        template["conferenceName"] = item_info.get("conference", "")
    template["date"] = item_info.get("year", "")
    template["DOI"] = item_info.get("doi", "")
    template["tags"] = [{"tag": t} for t in item_info.get("tags", [])]
    template["collections"] = item_info.get("collections", [])

    response = zot.create_items([template])
    if response.get("successful"):
        key = list(response["successful"].values())[0]["key"]
        # Step 3: Add note (mandatory)
        if item_info.get("note"):
            add_note(zot, key, item_info["note"])
        print(f"[OK] {item_info['title'][:50]}... ({key})")
        created += 1
    else:
        reason = response.get("failed", {}).get("0", {}).get("message", "Unknown")
        print(f"[FAIL] {item_info['title'][:50]} — {reason}")
        failed += 1

    # Rate limit: Zotero allows 100 requests per 10 seconds
    if (i + 1) % 40 == 0:
        print(f"  [pause] {i+1} items processed, waiting 5s for rate limit...")
        time.sleep(5)

print(f"\nDone: {created} created, {skipped} skipped, {failed} failed")
```

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| 403 Forbidden | API key lacks write permission | Check https://www.zotero.org/settings/keys |
| Missing credentials | Env vars not set | Set `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` |
| Item not appearing | Sync delay (1-10s) | Wait, then refresh Zotero desktop |
| PDF upload fails | File not found or invalid | Verify path exists, file > 1KB |
| Duplicate created | Skipped search step | Always search before creating |
| Orphaned item | No collection assigned | Always set `template["collections"]` |
| UnicodeEncodeError | Windows cp950 console | Add `sys.stdout.reconfigure(encoding='utf-8')` |
| Rate limit (429) | Too many requests | Add `time.sleep(5)` every 40 items |

## Bundled Resources

- `references/api-reference.md` - Full Zotero API documentation
- `references/item-types.md` - Item type field specifications
- `scripts/add_literature.py` - Reusable Python script template
