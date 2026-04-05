# Zotero Skills — Claude Code Skill for Zotero CRUD

A [Claude Code](https://claude.com/claude-code) skill that gives Claude full read/write/update/delete access to your Zotero library via the Zotero API and pyzotero.

## What It Does

- **Read** items, collections, tags, and notes (fast local API)
- **Create** journal articles, conference papers, books, preprints, reports, notes
- **Update** metadata, tags, collections, and notes on existing items
- **Delete** items, notes, and collections (with trash safety)
- **Batch import** with duplicate checking and rate limiting
- **Dual-API architecture**: local API (port 23119) for fast reads, Web API for writes

## Quick Start

1. Copy this folder to your Claude skills directory:
   ```
   ~/.claude/skills/zotero-skills/
   ```

2. Install pyzotero:
   ```bash
   pip install pyzotero
   ```
3. Edit `config.json` with your Zotero API key and library ID:
   ```json
   {
     "zotero_api_key": "YOUR_KEY",
     "zotero_library_id": "YOUR_USER_ID",
     "zotero_library_type": "user",
     "collections": {
       "my_collection": "COLLECTION_KEY"
     }
   }
   ```
   Get your API key at https://www.zotero.org/settings/keys (enable read + write access).

4. (Optional) Have a Zotero MCP server running for fast local reads.

## Configuration

All credentials and collection mappings live in `config.json` — the single source of truth. The shared client (`scripts/zotero_client.py`) loads from this file automatically.

Environment variables `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` override config.json if set.

## Project Structure

```
zotero-skills/
├── SKILL.md                 # Full CRUD reference (Claude reads this)
├── config.json              # API key, library ID, collection keys
├── README.md                # This file
├── scripts/
│   ├── zotero_client.py     # Shared client: get_client(), add_note(), check_duplicate()
│   └── add_literature.py    # Reusable script template for batch adds
└── references/
    ├── api-reference.md     # Zotero API documentation
    └── item-types.md        # Item type field specifications
```
## Usage Examples

Ask Claude things like:

- "Add this paper to Zotero: *Attention Is All You Need* by Vaswani et al., 2017. Put it in the Transformers collection."
- "Find the Smith 2020 paper and add a reading note."
- "Batch import these 10 papers into my literature review collection."
- "Delete the duplicate entries tagged TO-DELETE."

## Requirements

- Python 3.8+
- [pyzotero](https://github.com/urschrei/pyzotero)
- Zotero API key with read/write access
- (Optional) Zotero desktop running for local API reads

## License

MIT