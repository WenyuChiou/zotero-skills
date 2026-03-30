# zotero-write

A Claude skill for managing Zotero references programmatically — search, add, classify, annotate, and organize literature from within Claude conversations.

## What It Does

The Zotero MCP server only supports **read** operations. This skill fills the gap by providing a complete **write** workflow via [pyzotero](https://github.com/urschrei/pyzotero):

- **Create items** — journal articles, conference papers, books, preprints, reports, and more
- **Add structured notes** — templates for reading notes, theory refs, methods refs, and data sources
- **Classify into collections** — auto-assign items based on keyword rules you define
- **Tag consistently** — project, section, and topic tags following a convention
- **Batch import** — add many references at once with duplicate checking and rate limiting
- **Upload PDFs** — attach full-text files to items

## Prerequisites

- **Python 3.8+**
- **pyzotero**: `pip install pyzotero`
- **Zotero MCP server** configured for read operations (search, browse collections, etc.)
- **Zotero API key** with read/write access to your personal library

## Quick Setup

1. **Get your API key** — go to https://www.zotero.org/settings/keys, create a key with read/write access, and note your User ID.

2. **Set environment variables:**
   ```bash
   export ZOTERO_API_KEY="your-api-key-here"
   export ZOTERO_LIBRARY_ID="your-user-id"
   ```
   Or configure them in your `.mcp.json` / MCP settings so they're available to Claude automatically.

3. **Install pyzotero:**
   ```bash
   pip install pyzotero
   ```

4. **Customize SKILL.md** — replace the placeholder collection hierarchy and auto-classification rules with your own Zotero collection keys and keyword mappings.

## Usage Examples

**Add a single paper via Claude:**
> "Add this paper to my Zotero: *Attention Is All You Need* by Vaswani et al., 2017, NeurIPS. Put it in the Transformers collection and tag it as Section-2.1."

**Batch import from a list:**
> "Here are 10 papers I need in Zotero for my literature review: [list]. Classify each into the right collection and add reading notes."

**Update an existing item:**
> "Find the Smith 2020 paper in Zotero and add it to the Methods collection too. Add a note that it's also cited in Section 4.3."

## Project Structure

```
zotero-write/
├── SKILL.md                    # Main skill instructions (Claude reads this)
├── README.md                   # This file
├── scripts/
│   └── add_literature.py       # Reusable Python script template
└── references/
    ├── api-reference.md        # Zotero API documentation
    └── item-types.md           # Item type field specifications
```

## License

MIT
