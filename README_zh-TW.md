# Zotero Skills — AI 程式助理的 Zotero CRUD 技能套件

> [English](README.md)

透過雙 API 架構（本地讀取 + Web 寫入）對 Zotero 文獻庫進行完整管理。相容任何支援技能（skills）或自訂指令的 AI 程式助理。

---

## 概覽

本技能套件讓 AI 程式助理能完整存取你的 Zotero 文獻庫，直接從終端機搜尋、新增、分類、標註、整理文獻。

**主要功能：**

- **雙 API 路由** — 讀取走本地 API（port 23119），寫入走 Zotero Web API
- **自動健康檢查與降級** — 自動偵測 Zotero 桌面版是否執行中；未啟動時自動切換至純 Web 模式
- **完整 CRUD** — 建立、讀取、更新、刪除項目、筆記、標籤、集合
- **JSON 模板** — 涵蓋所有項目類型：期刊論文、書籍、書章、研討會論文、報告、論文、網頁等- **速率限制保護** — 內建 `safe_api_call()` 包裝器，自動控制 API 請求頻率
- **集合管理** — 建立、列出、整理集合；在集合間移動項目
- **批次操作** — 單次 API 呼叫新增多筆項目
- **子筆記** — 為任何父項目附加富文字筆記
- **Research Hub 整合** — 從文獻搜尋到 NotebookLM 的端對端工作流程

---

## 安裝設定

### 前置需求

- **Python 3.10+**
- **pyzotero**: `pip install pyzotero`

### API 憑證

1. **API 金鑰** — 至 [https://www.zotero.org/settings/keys](https://www.zotero.org/settings/keys) 產生，勾選 Allow library access 和 Allow write access
2. **Library ID** — 同一頁面下方「Your userID for use in API calls」

### 設定檔

在技能根目錄建立 `config.json`：

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
> **提示：** Collection key 是 `https://www.zotero.org/users/<library_id>/collections` 網址最後一段

### 安裝方式

**全域安裝（所有專案）：**
```bash
cp -r zotero-skills/ ~/.claude/skills/zotero-skills/
```

**專案層級：**
```bash
cp -r zotero-skills/ your-project/.claude/skills/zotero-skills/
```

---

## 非 Claude CLI 使用說明

本技能以 Claude Code 開發，但適用於任何 AI 助理。

| CLI | 如何載入技能 |
|---|---|
| **Claude Code** | 放入 `~/.claude/skills/` 或 `.claude/skills/` — 自動載入 |
| **Codex CLI** | 以 `-C` 傳入 `SKILL.md` 作為上下文檔案，或加入任務提示 |
| **Gemini CLI** | 將 `SKILL.md` 加入系統提示或專案上下文 |
| **Cursor / Windsurf** | 將 `SKILL.md` 加入 `.cursor/rules` 或對應規則檔 |
| **其他工具** | 將 `SKILL.md` 相關段落貼入系統提示 |

`scripts/zotero_client.py` 與框架無關，可從任何 Python 腳本直接匯入。
---

## 目錄結構

```
~/.claude/skills/zotero-skills/        # 全域安裝路徑
├── SKILL.md              # AI 助理的完整 CRUD 指令參考
├── config.json           # API 憑證 + 集合對應
├── scripts/
│   ├── zotero_client.py  # ZoteroDualClient + 輔助函式
│   └── add_literature.py # 批次匯入腳本
├── references/
│   ├── api-reference.md  # Zotero API 端點文檔
│   └── item-types.md     # 所有項目類型的 JSON 模板
├── docs/                 # 範例截圖
├── README.md             # English
└── README_zh-TW.md       # 繁體中文
```

---

## 雙 API 架構

Zotero 提供兩個 API 介面，本技能自動路由。

| | 本地 API (`localhost:23119`) | Web API (`api.zotero.org`) |
|---|---|---|
| **存取條件** | 需 Zotero 桌面版執行 | 任何環境皆可 |
| **讀取** | ✅ 快速、支援全文搜尋 | ✅ 標準查詢 |
| **寫入** | ❌ 不支援（回傳 `501`） | ✅ 完整 CRUD |
| **速率限制** | 無 | 每 10 秒約 50 次請求 |
| **驗證方式** | `Zotero-Allowed-Request: true` header | `Zotero-API-Key: <key>` header |
### 健康檢查與自動降級

初始化時，`ZoteroDualClient` 呼叫 `check_local_api()`，向 `localhost:23119` 發送輕量 GET 請求。

- 若 Zotero 桌面版未執行 → 讀取自動降級為 Web API，無需任何設定變更
- 效能略降（Web 延遲），但所有操作仍正常運作

```python
from zotero_client import ZoteroDualClient

dual = ZoteroDualClient()
# dual.local_available → True 表示桌面版執行中，False 則否

results = dual.search("flood adaptation")            # 優先使用本地 API
dual.create_note("ITEM_KEY", "Section", "Notes...")  # 一律走 Web API
```

### 重要注意事項

- 本地 API **不支援寫入操作** — 所有建立、更新、刪除一律透過 Web API
- 若 Zotero MCP connector 設定 `ZOTERO_LOCAL=true`，其寫入工具將失敗，請改用 `zotero_client.py`

---

## Research Hub 工作流程

從文獻探索到 AI 輔助綜合分析的完整管道。

```
文獻搜尋  →  Zotero 寫入  →  Obsidian 筆記  →  Hub 索引  →  NotebookLM
              (本技能)        (檔案寫入)       (清單產生)    (AI 問答)
```
1. **文獻搜尋** — 透過 Google Scholar、Semantic Scholar、Crossref 或直接 DOI 查詢
2. **Zotero 寫入** — 使用本技能將項目加入 Zotero，附上元數據、標籤、集合分類
3. **Obsidian 筆記** — 在 Obsidian vault 產生結構化 `.md` 筆記，含 YAML frontmatter
4. **建立 Hub 索引** — 產生統一清單，連結 Zotero 金鑰 ↔ Obsidian 筆記 ↔ 檔案路徑
5. **NotebookLM** — 上傳來源進行 AI 輔助文獻回顧與問答

Hub 索引建立和 NotebookLM 上傳由 `knowledge-base` 技能處理。

---

## 可用函式

來自 `scripts/zotero_client.py`：

| 函式 | 說明 |
|---|---|
| `get_client()` | 已設定的 `pyzotero.Zotero` Web API 實例 |
| `get_collection(name)` | 從 `config.json` 以顯示名稱查找集合金鑰 |
| `add_note(zot, item_key, content)` | 為文獻項目附加子筆記 |
| `check_duplicate(zot, title, doi)` | 檢查指定標題或 DOI 的項目是否已存在 |
| `check_local_api(timeout)` | 測試 Zotero 桌面版本地 API 是否可達 |
| `ZoteroDualClient` | 雙 API 包裝器 — 本地讀取、Web 寫入、自動降級 |
| `safe_api_call(func)` | API 呼叫包裝器，自動處理速率限制退避 |

---

## 使用範例

### ZoteroDualClient（建議方式）

```python
import sys
sys.path.insert(0, r"~/.claude/skills/zotero-skills/scripts")
from zotero_client import ZoteroDualClient
dual = ZoteroDualClient()
print(f"本地 API 可用: {dual.local_available}")

results = dual.search("flood risk perception")
dual.create_note("I3P2J58S", "Section 2", "<p>討論 PMT 框架。</p>")
```

### 新增期刊論文

```python
from pyzotero import zotero
zot = zotero.Zotero("YOUR_LIBRARY_ID", "user", "YOUR_API_KEY")

template = zot.item_template("journalArticle")
template["title"] = "Deep Learning for NLP: A Survey"
template["creators"] = [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
template["publicationTitle"] = "Nature Machine Intelligence"
template["date"] = "2025"
template["DOI"] = "10.1038/s42256-025-00001-1"
resp = zot.create_items([template])
```

### 依標籤搜尋

```python
items = zot.items(tag="machine-learning", limit=25)
for item in items:
    print(f"{item['data']['title']} — {item['data'].get('date', 'n.d.')}")
```

---

## 環境需求

- **Python** 3.10+
- **pyzotero**（`pip install pyzotero`）
- **Zotero 帳號** 及 API 金鑰 — 免費註冊於 [zotero.org](https://www.zotero.org)
- *（選用）* **Zotero 桌面版** — 啟用本地 API 讀取，效能更佳

---

## 授權

MIT