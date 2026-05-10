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

> For all item type templates (journalArticle, conferencePaper, book, bookSection, thesis, report, webpage, etc.), see `item-types.md`.
> For full Web API endpoint reference (parameters, response shapes, write-token semantics), see `api-reference.md`.
