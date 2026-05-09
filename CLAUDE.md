# 智能 LINE Bot 派班管理系統 - Claude 實作指南

> **最後更新**：2026-05-10（Phase A+B+C 搬遷完工）

這是一個結合 Gemini AI 與三時間態架構的 Taiwan 計程車調度平台，用 atomic-tool + skill agent + LIFF 表單三件套取代了原本臃腫的 legacy 業務邏輯。

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
- 修改現有功能時必須確保向後兼容
- 用 `auto_commit=False` + rollback 做測試，不污染生產資料

---

## 工作流規矩（重要）

```
1. 改動先在 dev_line_channel 分支
2. 用戶在 Mac + ngrok 跑「派班 dev」測試 channel 實機驗
3. 用戶確認 OK，才把改動推 main
4. main push → Render 自動部署到 prod「Linyan」channel
```

**Claude 不要直接推 main**。所有 commit 預設提交 `dev_line_channel`，等用戶說 OK 才協助 merge → main → push。

### 砍 / 改 legacy 前

- `git show main:<path>` 看原版功能，避免 reimplementation 漏細節（教訓：帳戶明細第一版漏了 running_balance）
- 不要為了「修 AI 行為差」而退回 legacy fallback 寫 deterministic regex — 改 AI prompt / 加 atomic tool docstring example 才是長期解
- 不重做的判準消失了 — 已沒有「永遠走 legacy」的功能，rewrite 是唯一路徑（Phase D 已完成）

---

## 架構（rewrite v0.1，現在的全部）

### 整體流程

```
LINE Webhook (/callback)
    │
    ├─ 私聊 (user)        → 不需前綴，全收
    ├─ 群組 (group/room)  → 必須 / 開頭，否則跳過
    │                       例外：rewrite-active state（多輪對話 / Quick Reply）
    │
    ↓ 處理順序
    │
    1. rewrite/router.try_route          快速命令（exact match，無 AI 成本）
    2. rewrite/handlers/sandbox_handler  LIFF / 狀態 picker / AI agent / DB 同步橋接
    3. unknown 友善 fallback             「🤔 不太懂這個訊息，輸入「幫助」看可用指令」
       （不再 fall-through legacy — 已砍光）
```

### 5 個 AI Skill（rewrite/ai/skills/）

| Skill | atomic tools | 觸發例 |
|---|---|---|
| `trip_query` | query_trips / query_trip_by_id / query_today_trips / query_pending_dispatch | 今天診所班次、待派 |
| `trip_mutation` | passenger_leave / cancel_trip / mark_conflict / restore_to_ready / assign_driver / unassign_driver / record_fare_current / update_passenger_name / update_trip_category | 1234 化療 -30、註銷 1234、指派司機 1190 28530 |
| `completed_trip` | query / aggregate / update_fare / update_category / update_driver / sun_week_info | 查已完成、本週統計、修車資、改類別、改司機 |
| `customer` | query_customer_by_term / get_by_id / by_birthday_day / create / update / delete | 查太子龍、病歷層 15 |
| `fixed_schedule` | query / create / update / leave / restore | 太子龍的固定班次、固定班次14請假 |

### LIFF 表單（rewrite/handlers/liff/，單一 LIFF App + dispatcher）

```
?form=customer        新增/編輯客戶
?form=booking         預約叫車
?form=import          匯入固定班次
?form=new_schedule    新增固定班次模板
?form=edit_schedule   編輯固定班次
?form=leave_schedule  固定班次請假
?form=report          生成日/週/月報表
?form=deposit         記錄入金
?form=weekly_payment  記錄上週扣款
?form=batch_allowance 批量加成
```

prod LIFF：`2010013922-msGhDtjW`，Endpoint = `https://minimal-flask.onrender.com/liff/customer/form`

---

## 三時間態核心設計（系統精髓）

> ⚠️ **一眼看懂（請所有協作者務必遵守）**
>
> | 時間態 | 資料表 | 概念 |
> |-------|--------|------|
> | 未來態 | `fixed_schedules` | 模板，尚未匯入 |
> | 現在態 | `trips` | 生產線上的班次（含今天與未來已匯入） |
> | 過去態 | `completed_trips` | 已完成的班次 |
>
> **🌊 今天是流動的邊界**：
> - 班次執行時間到達後，會自動從 `trips` 掉入 `completed_trips`
> - **今天這個日期同時存在著「現在態」和「過去態」的資料**
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

#### 🔮 未來態（整備區域）
- 表：`fixed_schedules`, `customers`, `drivers`
- 流程：`客戶預約 → 固定班次設定 → 週次匯入 → 流入現在態`

#### ⚡ 現在態（生產線）
- 表：`trips`
- 狀態流程：`待派 → 準備 → (執行時間到達) → 自動掉入過去態`
- 干預機制：
  - 🏷️ **請假（三層障眼法）**：`status='準備'`，`passenger_leave_reason` 記原因
  - 🚫 **註銷/衝突**：改變狀態，阻止掉入已完成

#### 📦 過去態（成品倉庫）
- 表：`completed_trips`
- 功能：車資記錄、統計分析、報表生成

### 請假系統的三層障眼法

| 層次 | 說明 |
|-----|------|
| 用戶視角 | 顯示「班次已請假（出國度假）」 |
| 系統實現 | `status` = "準備"，`passenger_leave_reason` = "出國度假"，`extra_fare` = 加成 |
| 業務邏輯 | 班次正常流轉，自動掉入已完成，保持統計準確性 |

---

## 業務週定義：太陽週（星期日 → 星期六）

> **業務術語**：診所 + 東洋兩大客戶都**週結算**，週的定義必須一致。

### 太陽週 vs ISO 8601 對比（**重要差別**）

| 規範 | 一週起算 | 一週結束 | 系統用法 |
|------|---------|---------|---------|
| **太陽週（本系統用）** | **星期日** | **星期六** | 所有業務週次計算、週結算 |
| ISO 8601（`isocalendar().week`） | 星期一 | 星期日 | **不要用** |

- 範例：今天 2026-05-10（星期日）→ 本週 = 5/10（日）~ 5/16（六）
- 太陽週週號用 `date.strftime('%U')`（Python 內建，Sunday-first）

### 實作要點

- AI 必須先 call `sun_week_info` atomic tool 拿 dates，**不可自己算**（LLM 預設 ISO 會錯一天）
- helper 在 `rewrite/utils/sun_week.py`：暴露 `sun_week_start`、`sun_week_number`、`sun_week_by_number`、`parse_week_offset`、`sun_week_info` (atomic tool)
- atomic tool 對 AI 傳的 str 參數會 coerce（`commit f70fb6b`）

### AI 該理解的講法

| 用戶說 | 系統解釋 |
|-------|---------|
| 「本週」 | sun_week_info(week_offset=0) |
| 「上週」 | sun_week_info(week_offset=-1) |
| 「+3 週」 | sun_week_info(week_offset=3) |
| 「第 17 週」 / 「W17」 | sun_week_info(week_number=17) |
| 「5/7 那週」 | sun_week_info(target_date='2026-05-07') |
| 「本週是哪一週」 | 純查詢，回 description |

---

## 技術堆疊

| 類別 | 技術 |
|-----|------|
| Web 框架 | Flask |
| 部署平台 | Render（main 分支自動部署）|
| 資料庫 | PostgreSQL + SQLAlchemy + raw SQL（`sqlalchemy.text`）|
| AI | Google Gemini 2.5 Flash (Vertex AI) |
| LINE Bot | line-bot-sdk v3, Flex Message, Quick Reply, LIFF |
| 報表 | Google Drive API, Excel |

### 環境變數（`.env` / `.env.dev` / Render Dashboard）

```bash
LINE_CHANNEL_SECRET=...
LINE_CHANNEL_TOKEN=...        # 注意：用 LINE_CHANNEL_TOKEN，不是 ACCESS_TOKEN
LIFF_ID=...                    # prod = 2010013922-msGhDtjW
LIFF_CHANNEL_ID=...            # prod = 2010013922
GCP_PROJECT_ID=chrome-flight-458709-d1
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
DATABASE_URL=postgresql+psycopg2://...
RENDER_DB_HOST / RENDER_DB_USER / RENDER_DB_NAME / RENDER_DB_PASSWORD  # 同步用
TZ=Asia/Taipei                 # 時區至關重要
```

env 載入邏輯（app.py 已寫好不動）：
```
RENDER 環境變數存在 → 用 dashboard 設的（prod）
本地有 .env.dev    → .env (base) + .env.dev (override)
```

---

## 專案結構

```
minimal_flask/
├── app.py                      Flask 入口
├── database.py                 PostgreSQL 連接
│
├── rewrite/                    rewrite v0.1 主架構
│   ├── handlers/
│   │   ├── sandbox_handler.py  訊息主路由（exact-match → state machine → AI agent）
│   │   └── liff/               10 個 LIFF endpoints
│   ├── ai/
│   │   ├── agent.py            Gemini Function Calling agent
│   │   ├── client.py           Gemini client
│   │   ├── intent.py           意圖分類器（routes 訊息到 5 skills 之一）
│   │   ├── skill.py            Skill 定義
│   │   └── skills/             5 個 skill：trip_query / trip_mutation / completed_trip / customer / fixed_schedule
│   ├── tools/                  atomic tools（純函數，session 從參數傳入）
│   │   ├── base.py             ToolResult / 共用 decorator（R-5 鎖、audit log）
│   │   ├── trip.py             現在態 tools
│   │   ├── completed_trip.py   過去態 tools
│   │   ├── customer.py         客戶 CRUD
│   │   ├── fixed_schedule.py   未來態 tools
│   │   ├── leave.py            apply_leave shared
│   │   ├── import_fixed.py     匯入 fixed → trips
│   │   ├── report.py           報表（包 legacy report_service）
│   │   ├── accounting.py       帳務（query_balance / record_deposit / record_weekly_charge / query_ledger_page）
│   │   └── batch_allowance.py  批量加成
│   ├── views/                  Flex Message 渲染（純函數，輸入 view 物件，輸出 dict）
│   ├── router.py               快速命令路由（查客戶 / 班次詳情 / etc）
│   ├── conversation_state.py   多輪對話 state（in-memory dict + TTL）
│   └── utils/
│       └── sun_week.py         太陽週 helpers + sun_week_info atomic tool
│
├── modules/                    保留的 admin / framework
│   ├── routes/webhook.py       LINE webhook entry
│   ├── handlers/
│   │   ├── database_sync_handler.py  admin: Render → 本地同步
│   │   ├── sync_router.py / sync_handler.py / sequence_fix_handler.py / cleanup_handler.py
│   │   ├── diagnosis_handler.py      診斷碼系統（獨立模組）
│   │   ├── location_message_handler.py  LINE 位置訊息
│   │   └── image_message_handler.py     拍處方箋（用 ai_service_enhanced）
│   ├── services/
│   │   ├── ai_service.py             Vertex AI 初始化（rewrite agent 共用）
│   │   ├── ai_service_enhanced.py    image_message_handler 用
│   │   ├── scheduler_service.py      背景排程（班次自動掉到 completed）
│   │   ├── incremental_sync_service.py  同步 infrastructure
│   │   ├── report_service.py         rewrite/tools/report.py 包這個
│   │   ├── driver_service.py         rewrite/tools/trip 用
│   │   ├── diagnosis_query_service.py
│   │   └── 其他 location 相關 (geo / distance / clinic / arrival_template / chat_settings ...)
│   └── utils/                  共用工具（line_bot / unified_date_parser / taiwan_time / modification_utils / week_utils 等）
│
├── templates/liff/             LIFF 表單 HTML
├── migrations/                 SQL migration files (001-005)
├── scripts/                    sync_from_render / reverse_sync_customers / post_sync_seed / 各種 admin
└── docs/logs/                  Handoff 記錄
```

### 關鍵模組職責

| 模組 | 職責 | 備註 |
|-----|------|------|
| `sandbox_handler.py` | 訊息主路由 | 所有用戶訊息都走這（除 LIFF GET）|
| `rewrite/router.py` | 快速命令 cheap dispatch | 純 regex + 直接 SQL，無 AI |
| `rewrite/ai/agent.py` | Function Calling loop | 處理 multi-turn tool 呼叫 |
| `rewrite/tools/*.py` | atomic 業務邏輯 | 純函數 + ToolResult，純 DB session 介面 |
| `unified_date_parser.py` | 日期解析 | ✅ 必須使用，禁止自建 |

---

## 指令系統

### 純訊息（AI / 快速命令）

```bash
# 查詢
查太子龍                       # 客戶搜尋（cascade）
客戶詳情 5                     # 客戶 #5 詳情
病歷層 15                      # 生日 15 日的客戶
今天診所班次 / 東洋班次          # 當天班次
班次詳情 1234 / 待派班次         # 班次 / 全部待派
查已完成 昨天 司機5386          # 過去態查詢

# 狀態管理（高頻）
今天X的狀態 / 5/9 X的狀態        # 列班次 + 批次按鈕（請假/註銷/衝突/改回準備）

# 修改（自然語言，AI 處理）
1234 化療 -30                 # 請假
1234 註銷 / 衝突              # 改狀態
派司機 5386 給 #1234           # 指派
記錄車資 1234 380              # 車資
修改類別 1234 診所             # 改類別

# LIFF 表單入口
新增客戶 / 預約叫車 / 匯入固定班次
新增固定班次 / 編輯固定班次
生成週報表 / 月報表
帳務處理 / 批量加成

# 系統
資料庫同步 / 同步結果
幫助
```

### LIFF 表單入口（單一 LIFF App + dispatcher）

用戶打觸發詞 → bot 回 Quick Reply [LIFF 按鈕] → 點開表單 → 提交 → atomic tool 處理。

---

## 開發規範

### 日期處理

```python
# ✅ 正確：使用統一解析器
from modules.utils.unified_date_parser import UnifiedDateParser
date = UnifiedDateParser.parse("昨天")

# ❌ 錯誤：自建解析函數
def my_date_parser(date_str): ...  # 禁止！

# 對於太陽週相關問題：AI 必須先 call sun_week_info atomic tool
```

### atomic tool 規範

```python
# 純函數，session 從參數傳入（R-4）
def my_tool(*, session, trip_id: int, ...) -> ToolResult:
    # validate args
    if not trip_id:
        return ToolResult.fail("trip_id 必填")
    # query / mutate
    ...
    # mutation 一定要寫 audit log（R-6）
    write_audit(session=session, action_type='...', target_id=trip_id, ...)
    if auto_commit:
        session.commit()
    return ToolResult.success(data=...)

# 對 AI 傳 str 的 int / date 參數要 coerce（避免 type error）
```

### Flex 訊息格式

```python
# ✅ Quick Reply MessageAction 需要 text
{"type": "action", "action": {"type": "message", "label": "...", "text": "..."}}

# Flex 50KB 上限：carousel JSON 太大會被 LINE 退（帳戶明細測試案例）
# → 控制每 bubble 列數 + 簡化每 row 結構
```

### AI prompt 寫作

當 AI 行為不如預期：
- ❌ **不要**寫 deterministic regex bypass AI
- ✅ 改 skill `_system_prompt()` 加更多 examples
- ✅ atomic tool docstring 寫清楚觸發詞 / 期待行為
- ✅ schema description 用「Triggers: ...」具體列舉用戶會說什麼話

---

## 絕對不要做的事情

- **絕不**直接推 main（永遠先 dev_line_channel → 用戶驗 → 再推 main）
- **絕不**為了修 AI 行為退回 legacy fallback 寫 deterministic regex
- **絕不**跳過 `unified_date_parser` 自建日期解析
- **絕不**修改三時間態的核心流轉邏輯而不充分測試
- **絕不**砍 legacy 前不跑 `git show main:<path>` 確認原版功能
- **絕不**用 ISO 週（`isocalendar()`）— 必須走太陽週

## 必須要做的事情

- **總是**用 `unified_date_parser`
- **總是**遵循三時間態設計原則
- **總是**修改 atomic tool 後跑 6/6 regression
  ```
  test_completed_trip / test_completed_trip_mutations / test_trip /
  test_customer / test_trip_flex_pagination / test_multi_skill
  ```
- **總是**mutation 寫 audit log（R-6）
- **總是**對 AI 傳的參數做 type coerce（str → int / date）

---

## 常用開發指令

```bash
# 本地開發（dev_line_channel + ngrok）
python app.py

# 跑回歸（必跑 6 個）
source venv/bin/activate
for t in rewrite/tools/test_completed_trip.py \
         rewrite/tools/test_completed_trip_mutations.py \
         rewrite/tools/test_trip.py \
         rewrite/tools/test_customer.py \
         rewrite/views/test_trip_flex_pagination.py \
         rewrite/ai/test_multi_skill.py; do
  python "$t" 2>&1 | tail -2
done

# 資料庫同步（Render → 本地）
python scripts/sync_from_render.py

# 反向同步 customers（一次性，已執行過）
python scripts/reverse_sync_customers.py --live

# 推 prod（用戶在本地驗 OK 後執行）
git checkout main
git merge dev_line_channel --no-ff
git push origin main
```

---

## 已知架構問題 / 改進方向

### 🟢 大規模搬遷已完成

從 main `9150147` 起算 77 個 commit，~25,000 行 legacy → ~3,200 行 rewrite。

詳細：`docs/logs/REWRITE_HANDOFF_2026-05-10.md`（最新）

### 🟡 待精進（功能 / UX 層）

- **AI 對 mutation 命令偶爾只 query 不執行** — trip_mutation skill prompt 已加「執行優先」原則，需持續監控
- **帳戶明細 carousel 上限 84 筆** — 超過要靠「篩選區間」縮範圍。LIFF 版本可考慮
- **指派司機需要記司機 ID** — 已禁退回 picker UX，方向是 AI 智能化（如「派最閒的司機」）

### 🔴 不在 rewrite 範圍

- **diagnosis 模組**（診斷碼）— 獨立保留 legacy
- **image_message_handler**（拍處方箋自動建預約）— 保留 legacy

---

## 下一個對話該知道的

1. **詳細歷程**：`docs/logs/REWRITE_HANDOFF_2026-05-10.md`（v6 完工版）
2. **過去 handoff**：`docs/logs/REWRITE_HANDOFF_2026-05-{03,04,06}.md`
3. **MEMORY.md**（user-level）的工作流規矩 + bloat / legacy 警示
4. **現在主要工作**：功能精進 + bug 修補。**不再有大規模搬遷**。

### 動手順序（每個任務）

1. 改動先在 `dev_line_channel`
2. 跑 6/6 regression
3. 用戶在 Mac + ngrok 實機驗
4. 用戶 OK → 才 merge 到 main → push → Render auto-deploy
5. **Claude 不直接 push main**

### 砍 / 改 legacy 前

1. `git show main:<path>` 看原版功能
2. **不退回 legacy fallback** — 改 AI prompt 比加 deterministic regex 優先
