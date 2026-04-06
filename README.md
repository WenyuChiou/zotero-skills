# Zotero Skills — AI Coding Assistant Skill for Zotero CRUD
# Zotero Skills — AI 程式助理的 Zotero CRUD 技能套件

> Comprehensive Zotero library management via dual-API architecture (local read + web write).
> Works with any AI coding assistant that supports skills or custom instructions.
>
> 透過雙 API 架構（本地讀取 + Web 寫入）對 Zotero 文獻庫進行完整管理。
> 相容任何支援技能（skills）或自訂指令的 AI 程式助理。

---

## Overview / 概覽

A skill that gives AI coding assistants full CRUD access to your Zotero library. Search, add, classify, annotate, and organize references programmatically — all from your terminal.

本技能套件讓 AI 程式助理能完整存取你的 Zotero 文獻庫，直接從終端機搜尋、新增、分類、標註、整理文獻。

**Key capabilities / 主要功能：**

- **Dual-API routing** — Reads go through the fast local API (port 23119), writes go through the Zotero Web API
  **雙 API 路由** — 讀取走本地 API（port 23119），寫入走 Zotero Web API
- **Automatic health check & fallback** — Detects whether Zotero desktop is running; falls back to web-only mode transparently
  **自動健康檢查與降級** — 自動偵測 Zotero 桌面版是否執行中；未啟動時自動切換至純 Web 模式
- **Full CRUD** — Create, read, update, and delete items, notes, tags, and collections
  **完整 CRUD** — 建立、讀取、更新、刪除項目、筆記、標籤、集合
- **JSON templates** for all item types: journal article, book, book section, conference paper, report, thesis, webpage, and more
  **JSON 模板** — 涵蓋所有項目類型：期刊論文、書籍、書章、研討會論文、報告、論文、網頁等
- **Rate limiting** — Built-in `safe_api_call()` wrapper to stay within Zotero's API quotas
  **速率限制保護** — 內建 `safe_api_call()` 包裝器，自動控制 API 請求頻率
- **Collection management** — Create, list, and organize collections; move items between them
  **集合管理** — 建立、列出、整理集合；在集合間移動項目
- **Batch operations** — Add multiple items in a single API call
  **批次操作** — 單次 API 呼叫新增多筆項目
- **Child notes** — Attach rich-text notes to any parent item
  **子筆記** — 為任何父項目附加富文字筆記
- **Research Hub integration** — End-to-end pipeline from paper search to NotebookLM
  **Research Hub 整合** — 從文獻搜尋到 NotebookLM 的端對端工作流程

---

## Setup / 安裝設定

### Prerequisites / 前置需求

- **Python 3.10+**
- **pyzotero**:
  ```bash
  pip install pyzotero
  ```

### API Credentials / API 憑證

1. **API Key** — Generate at [https://www.zotero.org/settings/keys](https://www.zotero.org/settings/keys)
   **API 金鑰** — 至上方連結產生，勾選 Allow library access 和 Allow write access
2. **Library ID** — Found on the same page under "Your userID for use in API calls"
   **Library ID** — 同一頁面下方 "Your userID for use in API calls"

### Configuration / 設定檔

Create `config.json` in the skill root / 在技能根目錄建立 `config.json`：

```json
{
  "zotero_api_key": "YOUR_API_KEY",
  "zotero_library_id": "YOUR_LIBRARY_ID",
  "zotero_library_type": "user",
  "collections": {
    "my_collection": "COLLECTION_KEY"
  }
}
```

> **Tip / 提示:** Collection keys are the last URL segment at `https://www.zotero.org/users/<library_id>/collections`

### Installation / 安裝方式

**Global / 全域安裝（所有專案）：**
```bash
cp -r zotero-skills/ ~/.claude/skills/zotero-skills/
```

**Project-level / 專案層級：**
```bash
cp -r zotero-skills/ your-project/.claude/skills/zotero-skills/
```

---

## Non-Claude CLI Adaptation / 非 Claude CLI 使用說明

This skill was developed for Claude Code but works with any AI assistant.
本技能以 Claude Code 開發，但適用於任何 AI 助理。

| CLI | How to load the skill / 如何載入技能 |
|---|---|
| **Claude Code** | Place in `~/.claude/skills/` or `.claude/skills/` — auto-loaded / 自動載入 |
| **Codex CLI** | Pass `SKILL.md` as a context file via `-C` or include in task prompt |
| **Gemini CLI** | Include `SKILL.md` in system prompt or project context |
| **Cursor / Windsurf** | Add `SKILL.md` to `.cursor/rules` or equivalent rules file |
| **Any other tool** | Paste relevant sections of `SKILL.md` into your system prompt |

`scripts/zotero_client.py` is framework-agnostic — import it from any Python script.
`scripts/zotero_client.py` 與框架無關，可從任何 Python 腳本直接匯入。

---

## Project Structure / 目錄結構

```
zotero-skills/
├── SKILL.md              # Full CRUD reference and instructions for AI assistants
├── config.json           # API credentials + collection mappings
├── scripts/
│   ├── zotero_client.py  # ZoteroDualClient + helpers
│   └── add_literature.py # Batch import script
├── references/
│   ├── api-reference.md  # Zotero API endpoint docs
│   └── item-types.md     # JSON templates for all item types
├── docs/                 # Example screenshots
└── README.md
```

---

## Dual-API Architecture / 雙 API 架構

Zotero exposes two APIs with different capabilities. This skill routes automatically.
Zotero 提供兩個 API 介面，本技能自動路由。

| | Local API (`localhost:23119`) | Web API (`api.zotero.org`) |
|---|---|---|
| **Access / 存取條件** | Requires Zotero desktop running / 需桌面版執行 | Works anywhere / 任何環境 |
| **Read / 讀取** | ✅ Fast, full-text search | ✅ Standard queries |
| **Write / 寫入** | ❌ Not supported (`501 Method not implemented`) | ✅ Full CRUD |
| **Rate limit / 速率限制** | None / 無 | ~50 req / 10 sec |
| **Auth / 驗證** | `Zotero-Allowed-Request: true` header | `Zotero-API-Key: <key>` header |

### Health Check & Auto-Fallback / 健康檢查與自動降級

On initialization, `ZoteroDualClient` calls `check_local_api()` — a lightweight GET to `localhost:23119`.
初始化時，`ZoteroDualClient` 呼叫 `check_local_api()`，向 `localhost:23119` 發送輕量 GET 請求。

- If Zotero desktop is not running → reads fall back to Web API automatically, no config change needed
  若桌面版未執行 → 讀取自動降級為 Web API，無需任何設定變更
- Performance degrades slightly (web latency), but all operations still work
  效能略降，但所有操作仍正常運作

```python
from zotero_client import ZoteroDualClient

dual = ZoteroDualClient()
# dual.local_available → True if Zotero desktop running, False otherwise

results = dual.search("flood adaptation")            # local API if available
dual.create_note("ITEM_KEY", "Section", "Notes...")  # always web API
```

### Critical Notes / 重要注意事項

- The local API **does not support write operations** — all creates/updates/deletes go through the Web API
  本地 API **不支援寫入** — 所有建立、更新、刪除一律透過 Web API
- If you use a Zotero MCP connector with `ZOTERO_LOCAL=true`, its write tools will fail — use `zotero_client.py` for writes
  若 Zotero MCP connector 設定 `ZOTERO_LOCAL=true`，其寫入工具將失敗，請改用 `zotero_client.py`

---

## Research Hub Pipeline / Research Hub 工作流程

End-to-end pipeline from literature discovery to AI-assisted synthesis.
從文獻探索到 AI 輔助綜合分析的完整管道。

```
Paper Search / 文獻搜尋
    ↓
Zotero Write / Zotero 寫入          ← this skill / 本技能
    ↓
Obsidian Note / Obsidian 筆記       (via Obsidian MCP or file write)
    ↓
Build Hub Index / 建立 Hub 索引     (aggregates Zotero + Obsidian metadata)
    ↓
NotebookLM                          (upload sources for AI-assisted Q&A)
```

**Steps / 步驟：**

1. **Paper Search** — Find papers via Google Scholar, Semantic Scholar, Crossref, or direct DOI lookup
   **文獻搜尋** — 透過 Google Scholar、Semantic Scholar、Crossref 或直接 DOI 查詢
2. **Zotero Write** — Use this skill to add items with metadata, tags, and collection assignment
   **Zotero 寫入** — 使用本技能將項目加入 Zotero，附上元數據、標籤、集合分類
3. **Obsidian Note** — Generate a structured `.md` note in your Obsidian vault with key findings
   **Obsidian 筆記** — 在 Obsidian vault 產生結構化筆記，記錄關鍵發現
4. **Build Hub Index** — Create a unified JSON/CSV manifest linking Zotero keys ↔ Obsidian notes ↔ file paths
   **建立 Hub 索引** — 產生統一清單，連結 Zotero 金鑰 ↔ Obsidian 筆記 ↔ 檔案路徑
5. **NotebookLM** — Upload the hub index (and linked PDFs) for AI-assisted literature review
   **NotebookLM** — 上傳 Hub 索引（及相關 PDF）進行 AI 輔助文獻回顧

Hub index building and NotebookLM upload are handled by the `knowledge-base` skill.
Hub 索引建立器和 NotebookLM 上傳由 `knowledge-base` 技能處理。

---

## Available Functions / 可用函式

From `scripts/zotero_client.py` / 來自 `scripts/zotero_client.py`：

| Function | Description / 說明 |
|---|---|
| `get_client()` | Configured `pyzotero.Zotero` Web API instance |
| `get_collection(name)` | Find collection key by display name from `config.json` |
| `add_note(zot, item_key, content)` | Attach a child note to a library item |
| `check_duplicate(zot, title, doi)` | Check if item with given title or DOI exists |
| `check_local_api(timeout)` | Test if Zotero desktop local API is reachable |
| `ZoteroDualClient` | Dual-API wrapper — local reads, web writes, auto-fallback |
| `safe_api_call(func)` | API call wrapper with automatic rate-limit backoff |

---

## Usage Examples / 使用範例

### Read items / 讀取項目

```python
from pyzotero import zotero

zot = zotero.Zotero("YOUR_LIBRARY_ID", "user", "YOUR_API_KEY")
items = zot.top(limit=5)
for item in items:
    print(item["data"]["title"])
```

### Create a journal article / 新增期刊論文

```python
template = zot.item_template("journalArticle")
template["title"] = "Deep Learning for NLP: A Survey"
template["creators"] = [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
template["publicationTitle"] = "Nature Machine Intelligence"
template["date"] = "2025"
template["DOI"] = "10.1038/s42256-025-00001-1"
resp = zot.create_items([template])
```

### Add a child note / 新增子筆記

```python
parent_key = "ABC12345"
note_template = zot.item_template("note")
note_template["parentItem"] = parent_key
note_template["note"] = "<p>Key findings: Model achieves 95% accuracy on benchmark.</p>"
zot.create_items([note_template])
```

### Search by tag / 依標籤搜尋

```python
items = zot.items(tag="machine-learning", limit=25)
for item in items:
    print(f"{item['data']['title']} — {item['data'].get('date', 'n.d.')}")
```

### Use ZoteroDualClient (recommended / 建議方式)

```python
import sys
sys.path.insert(0, r"~/.claude/skills/zotero-skills/scripts")
from zotero_client import ZoteroDualClient

dual = ZoteroDualClient()
print(f"Local API available: {dual.local_available}")

results = dual.search("flood risk perception")
dual.create_note("I3P2J58S", "Section 2", "<p>Discusses PMT framework.</p>")
```

---

## Requirements / 環境需求

- **Python** 3.10+
- **pyzotero** (`pip install pyzotero`)
- A **Zotero account** with an API key — free at [zotero.org](https://www.zotero.org)
  **Zotero 帳號** 及 API 金鑰（免費）
- *(Optional)* **Zotero desktop app** — enables local API reads for faster performance
  *（選用）* **Zotero 桌面版** — 啟用本地 API 讀取，效能更佳

---

## License / 授權

MIT
