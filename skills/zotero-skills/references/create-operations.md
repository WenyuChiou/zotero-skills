# CREATE Operations (Web API — Requires API Key)

All writes go to `https://api.zotero.org/users/{LIBRARY_ID}/...` via pyzotero.

## Workflow: Adding Literature

**Always follow this sequence:** check duplicate → create item → add note → (optional) upload PDF.

```python
zot = get_client()

# Step 1: Check for duplicates (DOI preferred, fallback to title)
doi = "10.xxxx/xxxxx"
title = "Paper Title"
if not check_duplicate(zot, title, doi):

    # Step 2: Create item
    template = zot.item_template("journalArticle")
    template["title"] = title
    template["creators"] = [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
    template["publicationTitle"] = "Journal Name"
    template["date"] = "2024"
    template["DOI"] = doi
    template["tags"] = [{"tag": "topic-tag"}, {"tag": "project-name"}]
    template["collections"] = ["COLLECTION_KEY"]  # Always assign a collection
    response = zot.create_items([template])
    item_key = list(response["successful"].values())[0]["key"]

    # Step 3: Add note (recommended for every item)
    add_note(zot, item_key, """
    <h2>Reading Note</h2>
    <p><b>Key findings:</b></p>
    <ul><li>Finding 1</li><li>Finding 2</li></ul>
    """)

    # Step 4 (optional): Upload PDF
    zot.attachment_simple(["path/to/paper.pdf"], item_key)
```

## Create a Collection

```python
result = zot.create_collections([{
    "name": "New Collection",
    "parentCollection": False  # or parent collection key for sub-collections
}])
col_key = list(result["successful"].values())[0]["key"]
```

## Batch Create (up to 50 items per API call)

```python
items = [zot.item_template("journalArticle") for _ in range(len(papers))]
for t, p in zip(items, papers):
    t["title"] = p["title"]
    t["DOI"] = p["doi"]
    t["creators"] = [{"creatorType": "author", "firstName": a[0], "lastName": a[1]} for a in p["authors"]]
result = zot.create_items(items)  # max 50 per call
```

## Attach a PDF (silent-failure caveat)

Raw `zot.attachment_simple([...], item_key)` (Step 4 above) can fail
**silently** against a long Windows path that contains spaces: no
exception, just a `{"success": [], "failure": [...], "unchanged": []}`
result with no reason surfaced, unless the caller inspects it. A long path
with spaces is a completely normal thing to have on Windows (a file under
`Downloads` or a synced folder, say), so do not conclude "the PDF can't be
attached" from a bare `attachment_simple` call that looks like it did
nothing.

Prefer the shared client's `attach_pdf()`, which copies the file to a
short, space-free, `zot_`-prefixed filename in a temp directory first
(the prefix means the copy can never collide with a Windows-reserved
device name like `CON` or `NUL`), and **raises** on failure instead of
returning it silently. What it raises is the failed-upload entry
pyzotero's own `failure` list contains (title/filename); pyzotero does
not expose a deeper server-side reason for the failure, so that is the
most detail there is to surface:

```python
from zotero_client import ZoteroDualClient
dual = ZoteroDualClient()
dual.attach_pdf("ITEM_KEY", r"C:\Users\me\Downloads\A Really Long Paper Title (Draft Final v3).pdf")
```

If you must call `zot.attachment_simple()` directly, always check the
`failure` list in its return value before reporting success, and copy to
a short filename yourself first if it reports one.

> If the PDF itself is missing rather than failing to attach, see the
> "Find a missing PDF" row in `SKILL.md`'s capability table before telling
> the user it must be downloaded by hand.

> For all item type templates (journalArticle, conferencePaper, book, bookSection, thesis, report, webpage, etc.), see `item-types.md`.
> For full Web API endpoint reference (parameters, response shapes, write-token semantics), see `api-reference.md`.
