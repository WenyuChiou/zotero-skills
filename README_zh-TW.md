# Zotero Skills — AI 程式助理的 Zotero CRUD 技能套件

> 透過雙 API 架構（本地讀取 + Web 寫入）對 Zotero 文獻庫進行完整管理。
> 相容任何支援技能（skills）或自訂指令的 AI 程式助理。

---

## 概覽

本技能套件讓 AI 程式助理能完整存取你的 Zotero 文獻庫，直接從終端機搜尋、新增、分類、標註、整理文獻。

**主要功能：**

- **雙 API 路由** — 讀取走本地 API（port 23119），寫入走 Zotero Web API
- **自動健康檢查與降級** — 自動偵測 Zotero 桌面版是否執行中；未啟動時自動切換至純 Web 模式
- **完整 CRUD** — 建立、讀取、更新、刪除項目、筆記、標籤、集合
- **JSON 模板** — 涵蓋所有項目類型：期刊論文、書籍、書章、研討會論文、報告、論文、網頁等
- **速率限制保護** — 內建 `safe_api_call()` 包裝器，自動控制 API 請求頻率
- **集合管理** — 建立、列出、整理集合；在集合間移動項目
- **批次操作** — 單次 API 呼叫新增多筆項目
- **子筆記** — 為任何父項目附加富文字筆記
- **Research Hub 整合** — 從文獻搜尋到 NotebookLM 的端對端工作流程

---

## 安裝設定

### 前置需求

- **Python 3.10+**
- **pyzotero**：
  ```bash
  pip install pyzotero
  ```

### API 憑證

1. **API 金鑰** — 至 [https://www.zotero.org/settings/keys](https://www.zotero.org/settings/keys) 產生
   - 勾選 **Allow library access** 和 **Allow write access**
2. **Library ID** — 同一頁面下方 **"Your userID for use in API calls"**

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

> **提示：** 集合金鑰可在 `https://www.zotero.org/users/<library_id>/collections` 找到 — URL 最後一段即為金鑰。

### 安裝方式

**全域安裝（所有專案）：**
```bash
cp -r zotero-skills/ ~/.claude/skills/zotero-skills/
```

**專案層級安裝：**
```bash
cp -r zotero-skills/ your-project/.claude/skills/zotero-skills/
```

---

## 非 Claude CLI 使用說明

本技能套件以 Claude Code 開發，但核心 Python 腳本和 API 模式適用於任何 AI 助理：

| CLI | 如何載入技能 |
|---|---|
| **Claude Code** | 放入 `~/.claude/skills/` 或 `.claude/skills/` — 自動載入 |
| **Codex CLI** | 透過 `-C` 傳入 `SKILL.md` 作為上下文文件，或加入任務提示詞 |
| **Gemini CLI** | 將 `SKILL.md` 加入系統提示詞或專案上下文 |
| **Cursor / Windsurf** | 將 `SKILL.md` 加入 `.cursor/rules` 或對應規則文件 |
| **其他工具** | 將 `SKILL.md` 相關段落貼入你的系統提示詞 |

`scripts/zotero_client.py` 模組與框架無關 — 可從任何 Python 腳本直接匯入，不論使用哪個 AI 助理。

---

## 目錄結構

```
zotero-skills/
├── SKILL.md              # 完整 CRUD 參考文件與 AI 助理指令
├── config.json           # API 憑證 + 集合對應
├── scripts/
│   ├── zotero_client.py  # ZoteroDualClient + 輔助函式
│   └── add_literature.py # 批次匯入腳本
├── references/
│   ├── api-reference.md  # Zotero API 端點文件
│   └── item-types.md     # 所有項目類型的 JSON 模板
├── docs/                 # 範例截圖
└── README.md
```

---

## 雙 API 架構

Zotero 提供兩個 API 介面，功能各異。本技能自動路由：

| | 本地 API (`localhost:23119`) | Web API (`api.zotero.org`) |
|---|---|---|
| **存取條件** | 需要 Zotero 桌面版執行中 | 任何環境皆可 |
| **讀取** | ✅ 快速、支援全文搜尋 | ✅ 標準查詢 |
| **寫入** | ❌ 不支援（`501 Method not implemented`）| ✅ 完整 CRUD |
| **速率限制** | 無 | ~50 次 / 10 秒 |
| **驗證方式** | `Zotero-Allowed-Request: true` 標頭 | `Zotero-API-Key: <key>` 標頭 |

### 健康檢查與自動降級

`ZoteroDualClient` 初始化時會呼叫 `check_local_api()`，向 `localhost:23119` 發送輕量 GET 請求：

- 若 Zotero 桌面版**未執行**：讀取自動降級為 Web API，無需任何設定變更
- 效能略降（Web 延遲 vs. 本地），但所有操作仍正常運作

```python
from zotero_client import ZoteroDualClient

dual = ZoteroDualClient()
# dual.local_available → True 表示 Zotero 桌面版執行中，False 反之

results = dual.search("flood adaptation")          # 可用時走本地 API
dual.create_note("ITEM_KEY", "Section", "Notes...")  # 永遠走 Web API
```

### 重要注意事項

- 本地 API **不支援寫入操作** — 所有建立、更新、刪除一律透過 Web API
- 若你的 Zotero MCP connector 設定 `ZOTERO_LOCAL=true`，其寫入工具將失敗 — 請改用 `zotero_client.py`
- 建議混合模式：MCP 或本地 API 讀取，`ZoteroDualClient` 寫入

---

## Research Hub 工作流程

本技能套件是 Research Hub 工作流程的核心元件 — 從文獻探索到 AI 輔助綜合分析的完整管道：

```
文獻搜尋（Paper Search）
    ↓
Zotero 寫入（Zotero Write）   ← 本技能負責此步驟
    ↓
Obsidian 筆記（Obsidian Note） （透過 Obsidian MCP 或直接寫檔）
    ↓
建立 Hub 索引（Build Hub Index）（彙整 Zotero + Obsidian 元數據）
    ↓
NotebookLM                     （上傳來源進行 AI 輔助問答）
```

**逐步說明：**

1. **文獻搜尋** — 透過 Google Scholar、Semantic Scholar、Crossref 或直接 DOI 查詢找到論文
2. **Zotero 寫入** — 使用本技能將項目加入 Zotero，附上元數據、標籤、集合分類
3. **Obsidian 筆記** — 在 Obsidian vault 中產生結構化 `.md` 筆記，記錄關鍵發現
4. **建立 Hub 索引** — 執行索引建立器，產生統一的 JSON/CSV 清單，連結 Zotero 金鑰 ↔ Obsidian 筆記 ↔ 檔案路徑
5. **NotebookLM** — 將 Hub 索引（及相關 PDF）上傳至 NotebookLM 進行 AI 輔助文獻回顧

`SKILL.md` 包含每個步驟的詳細指令。Hub 索引建立器和 NotebookLM 上傳步驟由 `knowledge-base` 技能處理。

---

## 可用函式

來自 `scripts/zotero_client.py`：

| 函式 | 說明 |
|---|---|
| `get_client()` | 回傳已設定的 `pyzotero.Zotero` Web API 實例 |
| `get_collection(name)` | 從 `config.json` 依顯示名稱查詢集合金鑰 |
| `add_note(zot, item_key, content)` | 為文獻項目附加子筆記 |
| `check_duplicate(zot, title, doi)` | 檢查指定標題或 DOI 的項目是否已存在 |
| `check_local_api(timeout)` | 測試 Zotero 桌面版本地 API 是否可存取 |
| `ZoteroDualClient` | 雙 API 包裝器 — 本地讀取、Web 寫入、自動降級 |
| `safe_api_call(func)` | 帶自動速率限制退避的 API 呼叫包裝器 |

---

## 使用範例

### 讀取項目

```python
from pyzotero import zotero

zot = zotero.Zotero("YOUR_LIBRARY_ID", "user", "YOUR_API_KEY")
items = zot.top(limit=5)
for item in items:
    print(item["data"]["title"])
```

### 新增期刊論文

```python
template = zot.item_template("journalArticle")
template["title"] = "Deep Learning for NLP: A Survey"
template["creators"] = [{"creatorType": "author", "firstName": "Jane", "lastName": "Doe"}]
template["publicationTitle"] = "Nature Machine Intelligence"
template["date"] = "2025"
template["DOI"] = "10.1038/s42256-025-00001-1"
resp = zot.create_items([template])
```

### 新增子筆記

```python
parent_key = "ABC12345"
note_template = zot.item_template("note")
note_template["parentItem"] = parent_key
note_template["note"] = "<p>關鍵發現：模型在基準測試達到 95% 準確率。</p>"
zot.create_items([note_template])
```

### 依標籤搜尋

```python
items = zot.items(tag="machine-learning", limit=25)
for item in items:
    print(f"{item['data']['title']} — {item['data'].get('date', 'n.d.')}")
```

### 使用 ZoteroDualClient（建議方式）

```python
import sys
sys.path.insert(0, r"~/.claude/skills/zotero-skills/scripts")
from zotero_client import ZoteroDualClient

dual = ZoteroDualClient()
print(f"本地 API 可用: {dual.local_available}")

results = dual.search("flood risk perception")
dual.create_note("I3P2J58S", "Section 2", "<p>討論 PMT 框架。</p>")
```

---

## 環境需求

- **Python** 3.10+
- **pyzotero**（`pip install pyzotero`）
- **Zotero 帳號** 及 API 金鑰（免費，[zotero.org](https://www.zotero.org)）
- *（選用）* **Zotero 桌面版** — 啟用本地 API 讀取，效能更佳

---

## 授權

MIT
