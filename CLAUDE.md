# 智能 LINE Bot 派班管理系統 - Claude 實作指南

> **最後更新**：2026-05-07

這是一個結合真實 AI 技術與三時間態架構的 Taiwan 計程車調度平台，支援自然語言交互、智能路由決策和企業級派班解決方案。

---

## 核心原則

**重要：在所有程式變更和功能開發中必須遵循以下原則：**

### KISS (Keep It Simple, Stupid)
- 設計應以簡潔為目標，避免過度工程化
- 選擇直觀的解決方案而非複雜的實作

### YAGNI (You Aren't Gonna Need It)
- 只實作當前需要的功能
- 不要為未來可能用到的功能提前開發

### 穩定性優先
- **關鍵業務功能必須有傳統處理路徑**，不能完全依賴 AI
- 任何新功能都必須考慮降級機制
- 修改現有功能時必須確保向後兼容

---

## 遷移策略：sandbox 取代 legacy（長期規劃）

> ⚠️ **這個策略 override 過去 v4 / v5 handoff 的「C 路線（不重做）」判斷。**
> 不再有「永遠走 legacy」的功能；雙軌制只是過渡期。

### 終局目標

`rewrite/`（sandbox）補齊 legacy 所有功能 → 砍 legacy → 拆掉 `!` 前綴 → rewrite 變成預設行為 → 推上 Render。

### 推論規則

- `_HARD_FALLTHROUGH_KEYWORDS` 是**待淘汰清單**，不是「rewrite 永遠不做」的功能
- v4 / v5 handoff 寫的「C 路線（不重做）」是過渡期判斷，遷移期所有 fall-through 功能都要做
- 「YAGNI」對「砍 legacy 必要的功能」**不適用** — 不做就遷移卡死

### Phase 路徑

| Phase | 動作 | 狀態（2026-05-07）|
|-------|------|-----|
| 1 | sandbox 接管 query / mutation / 客戶 CRUD / booking | ✅ 已完成 |
| 2 | sandbox 接管 import / 報表 / 新增刪除 fixed_schedule | 🚧 進行中 |
| 3 | 拆 `_HARD_FALLTHROUGH_KEYWORDS`（清空） | 待 |
| 4 | 拆 `!` 前綴判斷邏輯（webhook 一律走 rewrite） | 待 |
| 5 | 刪 legacy（temp_booking_handler / import_handler / fixed_router / customers_ai_service 等） | 待 |
| 6 | 推 Render（env loading 已一勞永逸） | 待 |

每個 Phase → 1-2 天用戶實機驗 → 才推下一 Phase。

### 截至 2026-05-07 砍 legacy 還缺什麼

| 缺口 | 對應 hard fallthrough keyword |
|-----|----|
| 匯入固定班次到 trips | `匯入` / `import` |
| 日 / 週 / 月報表生成 | `報表` / `日報` / `週報` / `周報` |
| 新增 fixed_schedule（legacy 也沒做，業務需要） | — |
| 刪除 fixed_schedule（兩端都沒） | — |

---

## 業務週定義：太陽週（星期日 → 星期六）

> **業務術語**：診所 + 東洋兩大客戶都**週結算**，週的定義必須一致。

- **太陽週起點 = 星期日**（**不是**星期一，跟 ISO 8601 不同）
- 範例：今天 2026-05-07（星期四）→ 本週 = 5/3（日）~ 5/9（六）

### 多功能需要凸顯太陽週

- **匯入固定班次**：「本週」/「下週」/「+3 週」要解析成太陽週的 7 天日期範圍
- **過去態查詢加總**：「本週司機5386東洋班次」「上週司機533收入」「xx 週 X 班次加總」
- **報表生成**：日 / 週 / 月報表的「週」也走太陽週
- **直接問**：「本週是哪一週」「上週是哪一週」 — 系統要能直接答出日期範圍

### 實作要點

- 用 `(weekday + 1) % 7` 計算週內第幾天（星期日為 0；Python `datetime.weekday()` 是星期一為 0 要轉換）
- **不要**用 ISO `isocalendar().week`（那是星期一起算 ≠ 業務週）
- legacy `modules/handlers/import_handler.py:parse_week_parameter` 已實作太陽週邏輯，rewrite 可重用 / 重做
- rewrite 應建立 `rewrite/utils/sun_week.py` helper（暴露 `current_week()` / `parse_week_phrase()`），給多 skill / LIFF / atomic tool 共用

### AI 該理解的講法（指 2026-05-07 為今天）

| 用戶說 | 系統解釋 |
|-------|---------|
| 「本週」 | 5/3（日）~ 5/9（六）|
| 「上週」 | 4/26（日）~ 5/2（六）|
| 「下週」 | 5/10（日）~ 5/16（六）|
| 「+3 週」 | 5/24（日）~ 5/30（六）|
| 「本週是哪一週」 | 「本週 5/3-5/9」直接回答 |

### 業務 ops 細節

- fixed_schedule 目前**沒有 UI 入口可建**（admin 網頁 commit `a59114f` 已移除），用戶手動進 PostgreSQL DB INSERT — 這是 Phase 2 要補的 LIFF 表單

---

## 三時間態核心設計（系統精髓）

> ⚠️ **一眼看懂（請所有協作者務必遵守）**
>
> **三時間態對應表**：
> | 時間態 | 資料表 | 概念 |
> |-------|--------|------|
> | 未來態 | `fixed_schedules` | 模板，尚未匯入 |
> | 現在態 | `trips` | 生產線上的班次（含今天與未來已匯入） |
> | 過去態 | `completed_trips` | 已完成的班次 |
>
> **🌊 今天是流動的邊界**：
> - 這一秒是「現在」，下一秒就變成「過去」
> - 班次執行時間到達後，會自動從 `trips` 掉入 `completed_trips`
> - 因此，**今天這個日期同時存在著「現在態」和「過去態」的資料**
>
> **核心路由規則**（以 `{today}` 為動態基準）：
> ```
> 日期 < {today}  → 查 completed_trips（過去態）
> 日期 = {today}  → 含「已完成」→ completed_trips，否則 → trips
> 日期 > {today}  → 查 trips（已匯入的未來班次也在生產線上）
> ```
>
> **用詞統一**：資料庫狀態「取消」已更名為「註銷」

### 🏭 生產線思維

系統將班次管理抽象為現代化工廠的生產線概念：

#### 🔮 未來態（整備區域）
- **核心表**：`fixed_schedules`, `customers`, `drivers`
- **概念**：工廠的原料倉庫和生產模板
- **流程**：`客戶預約 → 固定班次設定 → 週次匯入 → 流入現在態`

#### ⚡ 現在態（生產線）
- **核心表**：`trips`
- **概念**：產品正在生產線上「流動執行」
- **狀態流程**：`待派 → 準備 → (執行時間到達) → 自動掉入過去態`
- **干預機制**：
  - 🏷️ **請假（三層障眼法）**：狀態維持「準備」，用 `passenger_leave_reason` 記錄原因
  - 🚫 **註銷/衝突**：改變狀態，阻止掉入已完成

#### 📦 過去態（成品倉庫）
- **核心表**：`completed_trips`
- **概念**：已完成的「產品」存放區
- **功能**：車資記錄、統計分析、報表生成

### 請假系統的三層障眼法

**設計精髓**：用戶看到的和系統實現的完全不同，但業務邏輯完整

| 層次 | 說明 |
|-----|------|
| 用戶視角 | 顯示「班次已請假（出國度假）」 |
| 系統實現 | `status` = "準備"，`passenger_leave_reason` = "出國度假" |
| 業務邏輯 | 班次正常流轉，自動掉入已完成，保持統計準確性 |

---

## 技術堆疊

| 類別 | 技術 |
|-----|------|
| Web 框架 | Flask |
| 部署平台 | Render |
| 資料庫 | PostgreSQL + SQLAlchemy |
| AI | Google Gemini 2.5 Flash (Vertex AI) |
| LINE Bot | line-bot-sdk v3, Flex Message, Quick Reply |
| 報表 | Google Drive API, Excel |

### 環境變數
```bash
LINE_CHANNEL_SECRET=...
LINE_CHANNEL_ACCESS_TOKEN=...
GEMINI_API_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
GCP_PROJECT_ID=chrome-flight-458709-d1
DB_USER=... DB_PASSWORD=... DB_HOST=... DB_NAME=...
TZ=Asia/Taipei  # 時區設定至關重要
```

---

## 專案結構

```
minimal_flask/
├── app.py                      # Flask 應用程式主入口
├── database.py                 # PostgreSQL 連接
├── models.py                   # SQLAlchemy 模型定義
│
├── modules/
│   ├── routes/
│   │   └── webhook.py          # LINE Webhook 入口
│   │
│   ├── handlers/               # 業務邏輯處理器（40 個文件）
│   │   ├── text_message_handler.py   # 主路由器（1,027 行）
│   │   ├── query_router.py           # 查詢路由分發
│   │   ├── customers_ai_handler.py   # 🆕 沙盒客戶系統入口
│   │   ├── trip_handler.py           # 班次管理
│   │   ├── trip_status_handler.py    # 狀態修改
│   │   ├── leave_mode_handler.py     # 請假模式
│   │   ├── temp_booking_handler.py   # AI 預約叫車
│   │   ├── import_handler.py         # 固定班次匯入
│   │   ├── database_sync_handler.py  # 資料庫同步
│   │   └── ...
│   │
│   ├── services/               # 核心服務層（42 個文件）
│   │   ├── smart_assistant.py        # Gemini AI 智能助手（1,502 行）
│   │   ├── customers_ai_service.py   # 🆕 沙盒 AI 服務（Function Calling）
│   │   ├── ai_fare_service.py        # AI 車資服務（1,639 行）
│   │   ├── date_range_query_service.py  # 日期範圍查詢（1,305 行）
│   │   ├── trip_query_service.py     # 班次查詢
│   │   ├── advanced_query_processor.py  # 進階查詢
│   │   ├── report_service.py         # 週/月報表
│   │   ├── scheduler_service.py      # 背景排程
│   │   ├── booking/                  # 🆕 預約子系統
│   │   │   └── booking_service.py    # 預約記錄服務
│   │   └── ...
│   │
│   ├── core/                   # 核心模組（新架構）
│   │   ├── query_classifier.py       # 查詢分類（三時間態判斷）
│   │   ├── query_router.py           # 查詢路由決策
│   │   ├── intent_executor.py        # 意圖執行
│   │   ├── action_dispatcher.py      # 結構化意圖分發
│   │   └── gemini_functions.py       # Gemini Function Calling
│   │
│   ├── utils/                  # 工具函數
│   │   ├── unified_date_parser.py    # ✅ 統一日期解析（必須使用）
│   │   ├── conversation_context.py   # 對話狀態管理
│   │   ├── quick_reply_manager.py    # Quick Reply 管理
│   │   └── line_bot.py               # LINE Bot 工具
│   │
│   └── flex_designs/           # LINE Flex Message 設計
│
└── docs/                       # 文檔（待整理）
```

### 關鍵模組職責

| 模組 | 職責 | 備註 |
|-----|------|------|
| `text_message_handler.py` | 消息路由總入口 | ⚠️ 過大，需拆分 |
| `smart_assistant.py` | Gemini AI 自然語言理解 | ⚠️ 過大，需拆分 |
| `query_classifier.py` | 判斷查詢類型和目標表 | ✅ 新架構核心 |
| `date_range_query_service.py` | 日期範圍查詢（支援分頁） | ✅ 統一查詢入口 |
| `unified_date_parser.py` | 日期解析 | ✅ 必須使用，禁止自建 |

---

## 消息處理流程

```
LINE Webhook (/callback)
    │
    ├─→ 🆕 沙盒路由檢查（優先）
    │   ├─ 前綴 cu/客 → customers_ai_handler
    │   ├─ 活躍沙盒對話 → customers_ai_handler
    │   └─ 待確認狀態 → customers_ai_handler
    │
    ├─→ should_process() 檢查（群組需 / 前綴）
    │
    ├─→ text_message_handler.process_text_message()
    │   │
    │   ├─ 特殊命令檢查（幫助、重置、查等）
    │   │
    │   ├─ 對話狀態檢查（請假模式、車資修改確認等）
    │   │
    │   └─ AI 智能路由
    │       ├─ query_classifier 判斷查詢類型
    │       ├─ query_router 決定目標表和處理器
    │       └─ 執行查詢並返回結果
    │
    └─→ Flex Message / Quick Reply 回應
```

### 查詢系統架構

```
用戶輸入: "/1/15 司機5386班次"
    │
    ├─→ query_classifier.parse_direct_query()
    │   └─ 解析日期、司機、類別、地點
    │
    ├─→ query_classifier.determine_query_table()
    │   └─ 根據日期判斷: trips 或 completed_trips
    │
    ├─→ date_range_query_service.handle_query_trips_range()
    │   ├─ 純過去 → query_completed_trips_range()
    │   ├─ 純現在/未來 → query_current_trips_range()
    │   └─ 混合範圍 → 分別查詢後合併（支援分頁）
    │
    └─→ 格式化結果 + Quick Reply 分頁按鈕
```

---

## AI 智能路由系統

### 雙軌制設計（已實施）

系統採用 AI + 傳統解析器的雙軌制，確保穩定性：

```python
# 雙軌制流程
if is_standard_command(message):
    return handle_direct_command(message)  # 直接處理，不經 AI
else:
    try:
        return smart_assistant.process(message)  # AI 處理
    except:
        return traditional_fallback(message)  # AI 失敗時降級
```

### Gemini Function Calling（核心 AI 功能）

**設計理念**：只用於「需要智能理解」的操作，查詢仍走傳統路徑

**定義位置**：`modules/core/gemini_functions.py`

| Function | 用途 | 觸發條件 |
|----------|------|----------|
| `query_trips_by_context` | 查詢班次 | 包含「班次」關鍵字 |
| `clarify_user_intent` | 意圖澄清 | 包含「狀態」或意圖不明確 |
| `passenger_leave` | 乘客請假 | 包含「請假」+ 日期/地點 |
| `update_fare` | 修改車資 | 班次號碼 + 金額 + 「修改」 |
| `confirm_operation` | 確認操作 | 「確認」「是」「執行」 |
| `cancel_operation` | 取消操作 | 「取消」「不要」 |

---

## 沙盒客戶系統（Customers AI Sandbox）

**獨立的 AI 對話系統**，專門給特定客戶使用，支援自然語言預約和客戶管理。

### 觸發方式
```bash
# 前綴觸發（群組和私聊都適用）
cu ...        # 英文前綴
客 ...        # 中文前綴
/cu ...       # 帶斜線前綴
/客 ...       # 帶斜線前綴

# 多輪對話中自動保持
# （用戶在沙盒對話中時，後續消息自動路由到沙盒）
```

### 相關模組
| 模組 | 職責 |
|-----|------|
| `handlers/customers_ai_handler.py` | 沙盒消息入口 |
| `services/customers_ai_service.py` | 沙盒 AI 服務（使用 Function Calling） |
| `services/booking/booking_service.py` | 預約記錄服務 |

### 流程特點
- **多輪對話**：支援缺失信息補充
- **確認機制**：操作前需用戶確認（「確認」/「取消」）
- **實體連結**：自動關聯最近班次（支援「改那一班」）

---

## 指令系統

### 未來態指令（規劃）
```bash
匯入固定班次 [週次]              # 從模板匯入到生產線
匯入固定班次 本週 覆蓋           # 覆蓋模式匯入
查詢固定班次 [客戶]              # 查看模板
固定班次請假 [ID] [加成] [原因]  # 長期請假
```

### 現在態指令（執行）
```bash
診所班次 [日期]                 # 查看診所班次
東洋班次 [日期]                 # 查看東洋班次
班次詳情 [trip_id]              # 查看詳情
指派司機 [trip_id] [司機ID]     # 指派司機
修改狀態 [trip_id] [狀態]       # 修改狀態
乘客請假 [trip_id] [加成] [原因] # 臨時請假
```

### 過去態指令（記錄）
```bash
查已完成 [條件]                 # 查詢已完成班次
記錄車資 [ID] [錶價] [加成]     # 記錄車資
統計金額 [條件]                 # 金額統計
生成周報表 [類別]               # 生成週報
```

### AI 自然語言（群組需 / 前綴）
```bash
/昨天5386已完成班次             → 查已完成 昨天 司機5386
/1/15所有班次                   → 查班次 1/15
/7/15司機533診所班次            → 查班次 7/15 司機533 診所
```

---

## 開發規範

### 日期處理
```python
# ✅ 正確：使用統一解析器
from modules.utils.unified_date_parser import UnifiedDateParser
parser = UnifiedDateParser()
date = parser.parse_date_input("昨天")

# ❌ 錯誤：自建解析函數
def my_date_parser(date_str): ...  # 禁止！
```

### Quick Reply 格式
```python
# ✅ 正確格式（MessageAction 需要 text）
QuickReplyItem(action=MessageAction(label="下一頁", text="下一頁"))

# ❌ 錯誤格式（PostbackAction 需要 text 和 data）
QuickReplyItem(action=PostbackAction(data="xxx"))  # 缺少 text
```

### 「放棄」vs「取消」按鈕
```python
# ✅ 使用「放棄AI修改」避免與「註銷」狀態混淆
{"label": "❌ 放棄修改", "text": "放棄AI修改"}

# ❌ 「取消修改」可能被 AI 誤解為查詢「註銷」狀態
```

---

## 已知架構問題

### 🔴 P0：需要重構

| 問題 | 現狀 | 建議 |
|-----|------|------|
| `text_message_handler.py` 過大 | 1,027 行 | 拆分為路由 + 分類 + 執行 |
| `smart_assistant.py` 過大 | 1,502 行 | 拆分為 AI 客戶端 + 提示詞 + 解析器 |
| `ai_fare_service.py` 過大 | 1,639 行 | 拆分為查詢 + 修改 + 對話 |

### 🟡 P1：待優化

- 查詢系統有多個入口（handlers/query_router vs core/query_router）
- 模型定義分散（根目錄 models.py vs modules/models/）
- 部分備份文件未清理

### 🟢 P2：長期改善

- 建立監控和可觀測性
- 完善測試覆蓋率
- 整理 docs/ 目錄文檔

---

## 絕對不要做的事情

- **絕不**在沒有降級機制的情況下依賴 AI
- **絕不**跳過 `unified_date_parser` 自建日期解析
- **絕不**修改三時間態的核心流轉邏輯而不充分測試
- **絕不**在 `text_message_handler.py` 中添加更多業務邏輯

## 必須要做的事情

- **總是**為 AI 功能實現 fallback 機制
- **總是**使用統一日期解析器
- **總是**遵循三時間態設計原則
- **總是**在修改核心功能前進行測試

---

## 常用開發指令

```bash
# 本地開發
python app.py

# 資料庫同步
python scripts/sync_from_render.py

# 檢查模組導入
python -c "import modules; print('OK')"
```

---

## 總結

### 系統優勢
1. **創新的三時間態設計** - 生產線思維的業務抽象
2. **真正的 AI 整合** - Gemini 驅動的自然語言理解
3. **精妙的請假機制** - 三層障眼法設計
4. **雙軌制穩定性** - AI + 傳統解析器降級

### 發展方向
1. 重構超大模組文件
2. 統一查詢系統入口
3. 建立監控機制
4. 整理文檔體系
