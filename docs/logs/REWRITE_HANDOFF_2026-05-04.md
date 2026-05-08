# Rewrite v0.1 進度交接 — 2026-05-04（v4）

> **新對話開頭給 Claude 看**：請先讀這檔 + `docs/logs/REWRITE_HANDOFF_2026-05-03.md` (v3)。
> 主 repo 路徑：`/Users/linyancui/minimal_flask`
> 當前分支：`dev_line_channel`（main 分支完全沒動）
> ⚠️ **絕對不要 checkout / push main 分支**。所有改動都在 dev_line_channel。

---

## 0. TL;DR — 給接手的 Claude

rewrite v0.1 已完成 **AI agent 框架 + 4 個 Skill（trip_query / trip_mutation / customer / fixed_schedule）**，並接到 LINE webhook 的 `!` 沙盒入口（`rewrite/handlers/sandbox_handler.py`）。用戶實機驗過、踩過 7-8 個坑都已修。

**現在 rewrite 是怎麼跑的**：

```
LINE 用戶打「!XXX」
    ↓
webhook.py 沙盒攔截
    ↓
rewrite/handlers/sandbox_handler.py
    ↓
hard fall-through 關鍵字（「匯入」「預約」「報表」等）→ legacy
    ↓
intent classifier (rewrite/ai/intent.py) — last_skill hint
    ↓
trip_query / trip_mutation / customer / fixed_schedule 之一  or  unknown→legacy
    ↓
Agent (rewrite/ai/agent.py) — multi-turn tool loop（AI 可 chain 多個工具）
    ↓
ToolResult → render LINE message dict (flex / text)
    ↓
若 AI 在等 follow-up → 加進度條 + Quick Reply [❌ 結束對話] + 設 sandbox-active state(90s)
    ↓
reply LINE
```

**下個 Claude 第一件事該做的**：先用 `git log -20` 看最近 commit，看是不是用戶又踩到新 bug 要修，再決定動什麼。**不要憑想像直接做新功能** — 用戶會罵，今天踩過好幾次。

---

## 1. 用戶的核心設計約束（多次強調，下次絕對不要違反）

1. **`!` 前綴 = AI 沙盒模式**，不加前綴 = 既有快速命令／legacy 流程。雙軌並存。
2. **rewrite 終局是替代 legacy（modules/ 下舊代碼）**，不是並存。但 v0.1 dev 階段 fall-through 給 legacy 是合理過渡（C 路線）。
3. **不要重做後比 legacy 更臃腫**。spec §1 量化目標：text_message_handler 1029→<100、AI 三巨頭 4422→~600。當前 rewrite/router.py 690 行偏離（要小心再加東西）。
4. **設計前先驗真實 UX**：不要把 spec 範例字（「自己來/出國/生病」這類）當業務內容。要看用戶實機畫面或自己跑 REPL 驗。
5. **業務邏輯不確定先問用戶**：list 2-3 方案 + tradeoff 給用戶選。不要自己腦補。
6. **行為 vs 呈現要拆清**：用戶反饋「請假流程不要改」是「行為」，「按鈕用 Quick Reply 不放 flex footer」是「呈現」。改流程不要順手把呈現改回去。
7. **絕對不要動 git main 分支**。"main" 在我語境通常指「modules/ 下的 legacy 代碼」，不是 git main 分支。

對應 memory（已存）：
- `~/.claude/projects/-Users-linyancui-minimal-flask/memory/feedback_check_real_ux.md`
- `~/.claude/projects/-Users-linyancui-minimal-flask/memory/feedback_dont_bloat_rewrite.md`
- `~/.claude/projects/-Users-linyancui-minimal-flask/memory/project_deployment_workflow.md`

---

## 2. 今日（自 v3 / commit 417ae16 起）累積的 commits（按時間倒序）

```
64a0d7e fix(fixed_schedule): restore 一律清 surcharge=NULL（用戶確認業務邏輯）
78b1a01 fix(rewrite): 對話模式只在 AI 等 follow-up 時顯示 + Quick Reply 按鈕真的有送
3b07e67 fix(rewrite): sandbox-active 不再卡住快速命令（用戶反饋）
05d00f0 feat(rewrite): 對話模式進度提示 + 主動結束按鈕（用戶建議）
4cb2551 fix(rewrite): 沙盒實機 3 個問題（postback customer_edit + 跨輪對話 context）
84dee95 fix(rewrite): 沙盒攔截 — hard fall-through 關鍵字 + 多輪 active state
b61e9b6 feat(rewrite): Phase 3 — 沙盒入口接 webhook (rewrite agent + legacy fall-through)
54022fd feat(rewrite/ai): Phase 1.7b — fixed_schedule_skill 接 MultiSkillAgent (4 skills 完備)
3ce62b8 feat(rewrite/tools): fixed_schedule atomic tools (4 個 — spec §3.3 部分)
28ee394 feat(rewrite/ai): Phase 2 — Intent classifier + MultiSkillAgent + REPL
68a3b28 feat(rewrite/ai): Phase 1.6 customer_skill + multi-turn tool loop
686e1c7 feat(rewrite/ai): Phase 1.5 — trip_mutation_skill (7 mutation tools 接 AI)
4a287df feat(rewrite): Phase 1 — AI agent 框架 (LLMClient + Skill + trip_query_skill)
b816865 fix(rewrite): 班次列表預設過濾已完成 + 已完成 emoji 改灰勾框
8cec3d1 fix(sync): calibrate_sequence 用 pg_get_serial_sequence 動態查實際序列名稱
4dd6c61 Revert "feat(rewrite): 批量請假..."（用戶說設計理解錯）
b5cbba0 feat(rewrite): 批量請假 — 同日多筆共享 input mode  ← 已 revert
98f5bea rewrite: 補 spec §3.1 兩個小型 mutation — update_passenger_name + record_fare_current
417ae16 docs: handoff v3
```

---

## 3. 當前 rewrite/ 結構（5,420 行 source + 3,016 行 test）

```
rewrite/
├── tools/                       # 27 個 atomic tools
│   ├── base.py                  # ToolResult + R-5 鎖 decorator + audit helpers
│   ├── customer.py              # 8 個（query/CRUD/birthday）
│   ├── trip.py                  # 13 個（4 query + 8 mutation + 1 batch helper）
│   ├── fixed_schedule.py        # 4 個（query / update / leave / restore）
│   │                            #     ⚠️ NO import — spec §3.3 第 5 個沒做（C 路線）
│   ├── leave.py                 # apply_leave 跨表 wrapper（R-3）
│   └── test_*.py                # 6 個測試檔
│
├── ai/                          # AI agent 框架（spec §6）
│   ├── client.py                # LLMClient + GeminiClient
│   ├── skill.py                 # Skill dataclass
│   ├── agent.py                 # Agent (multi-turn tool loop)
│   ├── multi_skill_agent.py     # MultiSkillAgent (intent classify + skill route)
│   ├── intent.py                # classifier (含 last_skill hint)
│   ├── repl.py                  # 終端機互動 REPL（測試用）
│   ├── skills/
│   │   ├── trip_query.py        # 4 工具
│   │   ├── trip_mutation.py     # 10 工具（含 query helper）
│   │   ├── customer.py          # 8 工具
│   │   └── fixed_schedule.py    # 5 工具
│   └── test_*.py                # 4 個整合測試
│
├── handlers/
│   └── sandbox_handler.py       # ! 前綴入口（hard fall-through + classifier + agent）
│
├── views/
│   ├── customer_flex.py
│   └── trip_flex.py
│
├── router.py                    # 快速命令 (查客戶/班次/班次詳情等)
│                                # ⚠️ 690 行偏離 spec < 100 目標
└── conversation_state.py        # in-memory state（請假輸入模式 / sandbox-active）
```

---

## 4. 今日確認的業務邏輯（重要！下次別憑空想）

### 4.1 三時間態 vs surcharge/extra_fare 語意

| 表 | 欄位 | restore 時怎麼處理 | 為什麼 |
|----|-----|------------------|-------|
| `fixed_schedules` | `surcharge` | **一律清 NULL**（commit 64a0d7e）| 模板層，surcharge 99% 是請假設的負加成。下次匯入時會 copy 到 trips → 殘留會錯帳 |
| `trips` | `extra_fare` | **負數歸零、正數保留**（commit 4b84b17）| 實際班次，可能是請假負加成（負數），也可能是等候費等正常加成（正數） |

兩邊不同是 by design。docstring 已寫清楚原因。

### 4.2 fixed_schedule 是什麼

「**每週匯入到 trips 的模板**」— legacy 命令「匯入固定班次 本週」會把 fixed_schedules 的 row 複製到 trips（每週一次）。所以：

- **長期請假**（客戶出國/住院）= 改 fixed_schedule 的 status=請假，避免每週匯入後一筆筆 trips 請假
- **單次請假** = 改特定 trip 的 passenger_leave_reason（trips 表，三層障眼法）

### 4.3 sandbox 多輪對話設計（commit 78b1a01 確定）

判斷 AI 是否在等 follow-up（`_ai_is_waiting_for_followup`）：
- text 結尾 `?`/`？` → True
- 含「請問/請提供/請輸入/請確認/是否要/需要」等字眼 → True
- flex 訊息 → False（視為結果回覆）

**只有 follow-up 時才**：加進度條「💬 對話模式進行中」+ Quick Reply [❌ 結束對話] + 設 sandbox-active state(90 秒)。

90 秒內：
- 看起來像 follow-up 的訊息（如「出國 -50」「14」）→ 攔到 rewrite
- 看起來像快速命令的訊息（如「診所班次 今天」「資料庫同步」）→ **不攔**，走快速命令
- 用戶打「結束」/「結束對話」/「退出」/「exit」/「quit」/「bye」→ 立即清 state

判斷快速命令：`looks_like_quick_command` 比對已知前綴清單（rewrite + legacy 共 30+ 個）。

### 4.4 hard fall-through 關鍵字（rewrite 不做、直接給 legacy）

`_HARD_FALLTHROUGH_KEYWORDS = ('匯入', '預約', 'booking', '報表', '日報', '週報', '周報', 'import')`

意思：訊息含這些字眼 → sandbox_handler 直接 return False → webhook 走 legacy `customers_ai_service`。比 LLM-based intent 判斷可靠（用戶看到「匯入固定班次」會直覺加 ! 前綴，但 rewrite 沒做 import）。

### 4.5 sequence drift bug（commit 8cec3d1 修，紀錄）

本地 dev DB 的 `trips_trip_id_seq1` / `completed_trips_id_seq1` / `customers_id_seq1` 名字有 `1` 後綴（schema 升級殘留），sync_from_render.py 寫死 `f"{table}_{col}_seq"` 找不到 → 靜默跳過 calibrate → sequence 永遠落後 → INSERT 撞 PK。

修法：用 PostgreSQL 內建 `pg_get_serial_sequence(table, col)` 動態查。

---

## 5. 已知不會做（C 路線 — 不重做、走 legacy）

| 功能 | 路徑 | 為什麼不做 |
|------|-----|---------|
| 匯入固定班次（每週）| 用戶打「匯入固定班次 本週」**不加 ! 前綴**走 legacy import_handler | spec §3.3 第 5 個工具，複雜（週次計算 / 批量 INSERT / unique_code）；用戶決定走 C |
| 預約叫車（booking_create）| 用戶打「!預約...」走 legacy customers_ai_service `_tool_booking_create` | rewrite 已實作 `create_trip` atomic tool，但跟 booking 流程不太一樣；改天再看 |
| 「明天龍埔街的狀態」+ 三層 quick reply 批量請假 | legacy 的 `intent_executor._handle_clarify_intent` + `leave_mode_handler` 已能處理 | 用戶實機驗證過 fall-through 正常；rewrite 不重做 |
| 過去態 completed_trips 全套 | spec §11 標 v0.2 | v0.2 工作 |

---

## 6. spec §1 量化目標 vs 現況（2026-05-04）

| 項目 | spec 目標 | 現況 | 評估 |
|-----|---------|-----|------|
| 日期解析器 | 1 個 | 1 個 ✅ | 對齊 |
| AI 三巨頭（main 4,422 行）| ~600 行 | rewrite/ai/ 1,475 行 | ✅ 在預算內（多但 4 skill + multi-turn loop 比 main 完整） |
| atomic tools | 17 個 | 27 個 + 4 skill | ✅ 超 spec |
| test 覆蓋 | — | 3,016 行 | 健康 |
| 入口 router | < 100 行 | rewrite/router.py **690 行** | ⚠️ **偏離**（再加新 mutation 命令前要拆檔） |
| Handler 檔案 | 5-8 個 | rewrite/ 沒 handler 概念，跳過 | — |

---

## 7. 下一步（按優先順序）

### Now（接手後立即可做）
- **無。** 等用戶實機反饋。今天大量改動還沒完整實機驗證，下個對話應先聽用戶的 bug 報告，不要主動加新功能。

### 短期（用戶有需求才做）
- **觀察 hard fallthrough / sandbox-active 邊界**：用戶可能踩到我列的關鍵字以外的 case
- **trip 領域沒接 LINE 的 atomic tools**：`update_passenger_name` / `record_fare_current` 工具有了但沒接 message regex（router.py 沒命令觸發），可透過 sandbox AI 用（但快速命令還沒做）
- **router.py 拆檔**：超過 700 行就拆 `rewrite/handlers/trip_command.py` / `customer_command.py`
- **handoff 自我更新**：每次 session 收尾前 +5 行 commit log 跟業務邏輯

### 中期
- **LIFF 表單建置**（用戶確認方向）：客戶/班次/門診記錄表等多場景受惠 — 詳見 §12
- **Phase 6 e2e 測試**：spec §7，跑端到端模擬 LINE webhook
- **過去態 completed_trips（v0.2）**：spec §11
- **Phase 7 Render 切換**：spec §7，dev_line_channel 切到 Render，main 退役

### 不做（避免）
- ❌ 重做「批量請假」「明天X的狀態」 — 走 C 路線（用戶確認）
- ❌ 重做「匯入固定班次」 — 用戶決定不重做
- ❌ 過早優化（未實際發生問題前不要改架構）
- ❌ 加新 regex command 到 router.py（會擠爆，spec 量化目標已偏離）

---

## 8. 給接手 Claude 的「Don't」清單（踩過的坑）

按時間順序：

1. **不要把 spec 範例字當業務內容** — 「自己來/出國/生病」是 spec §6.3 的 placeholder，被我當預設清單用，用戶罵了一次（commit b5cbba0 → 4dd6c61 revert）
2. **不要把 quick reply 改回 flex footer** — 用戶選了 quick reply，我順手改回 footer，又被罵（commit 817c7c0）
3. **不要憑空編 LINE 流程** — 看不到原系統真實畫面就不要設計（現在有 rewrite/ai/repl.py 可以驗）
4. **不要為了「對等覆蓋」而臃腫** — main 能跑就先走 C，重點是 atomic tools 不是 LINE 1:1 重現
5. **不要動 git main 分支** — main 是 Render 跑的版本，dev_line_channel 才是工作分支
6. **不要每次 reply 機械式加進度條** — 只有 AI 真的在等 follow-up 才加（commit 78b1a01 修）
7. **不要 sandbox-active 攔所有訊息** — 90 秒內快速命令仍要能用（commit 3b07e67 修）
8. **業務邏輯不確定先問** — restore 時欄位該如何處理、合併還是覆蓋這類細節 spec 通常沒寫，腦補會錯（commit 64a0d7e 教訓）

---

## 9. 實機測試怎麼跑

**方法 A：終端機 REPL**（最快、不用 LINE）
```bash
cd /Users/linyancui/minimal_flask
source venv/bin/activate
python rewrite/ai/repl.py
```
直接打字試，flex 訊息會用 ASCII art 簡化顯示。

**方法 B：跑 unit / integration tests**
```bash
for f in rewrite/tools/test_*.py rewrite/views/test_*.py rewrite/ai/test_*.py; do
  echo "=== $f ==="
  python "$f" 2>&1 | tail -3
done
```

**方法 C：LINE 實機**（用 dev_line_channel ngrok）
- 重啟 Flask（kill + `python app.py`）
- 在 LINE 打 `!XXX` 試
- 看 Flask console log（`[intent]` / `[Agent loop]` / `[rewrite sandbox]` 等）

---

## 10. 用戶相關備忘

- userId（測試用）：`U6b520261e9199a21d25e6d20509eda3f`
- email：`gshanyue222@gmail.com`
- 業務：醫療接送派班（診所/東洋兩大客戶類別）
- 用戶角色：派班員、看得到 LINE 訊息、會抱怨設計問題
- 工作流：dev_line_channel 上做、main 不動、最終切 Render（Phase 7）

---

## 11. 接手 Claude 的開頭建議

```
（用戶說）
請讀 docs/logs/REWRITE_HANDOFF_2026-05-04.md 後接續。
git log -20 看最新狀態。
我接下來想做 X / 我踩到 Y 問題 / 我要驗 Z 功能。
```

接手第一輪建議只做：
1. 讀 handoff v4 + v3
2. `git log -20` 看最新 commits
3. 跟用戶確認當前要做什麼（不要主動加功能）

---

*v4 建檔者：Claude，2026-05-04 對話接近 context 上限時整理*
*下個 Claude：你看到的應該已經是被拷進新對話的純文字。先讀 §0 §1 §8 三節，再 git log，再開工。*

---

## 12. LIFF 表單建置規劃（用戶確認方向）

### 12.1 為什麼要做

對話式 AI（沙盒）+ Flex Message 對「欄位多」的場景吃緊：
- 客戶資料 11 欄（name/short_name/address/category/phone/remarks/birthday/gender/national_id/medical_record_no/insurance_type）
- 用戶用自然語言「!新增客戶...」很容易漏欄位、要 AI 回問多輪
- LIFF 提供原生 form：dropdown / 日期選擇器 / 即時驗證 / 一次提交

### 12.2 適用場景（用戶提的 + 將來會遇到的）

| 場景 | 為什麼 LIFF 較合適 |
|-----|-----------------|
| 客戶 CRUD（新增 / 編輯）| 11 欄太多、AI 漏欄常見 |
| 臨時班次新增（booking_create）| 日期 + 時間 + 起終點 + 司機 + 車資 ≥ 7 欄 + 可選欄位 |
| 固定班次修改 | 同上，且有 dropdown（類別 / 方向 / 司機） |
| **門診記錄表**（用戶將來要做）| 多欄醫療記錄資料、需結構化欄位 |
| 報表參數選擇 | 日期區間選擇器 / 司機 multi-select / 類別 / 格式 |
| 將來：車資修改、請假理由收集等 | 比 conversation state 多輪輸入 UX 好 |

### 12.3 技術選型

```
LINE App
  ├─ 用戶打「!新增客戶」
  ├─ bot 回 Flex bubble 含 [📝 開填寫表單] 按鈕（URI action 指向 LIFF URL）
  ├─ LIFF webview 開啟（LINE 內嵌瀏覽器）
  │   ├─ HTML form：欄位 + dropdown + datepicker + validation
  │   ├─ LIFF SDK 自動拿 LINE userId（liff.getProfile()）
  │   └─ 用戶按 [送出] → JS POST 到後端
  ├─ Flask /liff/customer/create
  │   ├─ 驗證 LIFF idToken（liff.getIDToken）
  │   ├─ 呼叫 rewrite/tools/customer.py:create_customer
  │   └─ 回 JSON 結果
  └─ liff.closeWindow() 或顯示成功 + push 訊息給 user
```

**選型**：
- 前端：vanilla HTML/JS（簡單場景）or Vue（多場景時組件化）— 先 vanilla 看
- 後端：Flask 加 `/liff/...` blueprint，**重用既有 atomic tools**（不重做業務邏輯）
- 認證：LIFF idToken 驗證（保證請求來自 LINE 用戶）
- 部署：HTTPS（Render 已有；dev 用 ngrok）

### 12.4 實作 roadmap（建議分 3 個 Phase）

**Phase A — 基礎建設**（半天）：
1. LINE Developer Console 建立 LIFF App，拿 `LIFF_ID`（5 分鐘點擊）
2. Flask 加 `modules/routes/liff.py` 或 `rewrite/handlers/liff/` blueprint
3. 寫 LIFF auth 中間件：
   - 驗 idToken
   - 從 LINE 拿 userId
   - 確保 user 有權限（同 LINE channel 的成員）
4. 靜態檔目錄 `static/liff/` 放 HTML/JS/CSS

**Phase B — 第一個表單：客戶新增/編輯**（半天-1 天）：
1. `static/liff/customer_form.html` — name/short_name/address/category 下拉/phone/birthday/gender/national_id/medical_record_no/insurance_type
2. 提交 POST `/liff/customer/create` 或 `/liff/customer/<id>/update`
3. 後端 wrapper 呼叫 `rewrite.tools.customer.create_customer` / `update_customer`
4. 回應後 `liff.closeWindow()` + LINE push 訊息「✅ 已新增客戶 #X」

**Phase C — 其他場景按需擴**（每個場景半天-1 天）：
- 臨時班次新增（重用 `rewrite.tools.trip.create_trip`）
- 固定班次修改（重用 `rewrite.tools.fixed_schedule.update_fixed_schedule`）
- 門診記錄表（**新領域，要先設計 DB schema**）
- 報表參數選擇

### 12.5 跟現有 rewrite 的整合

LIFF **不取代** AI 沙盒，而是並存：
- 簡單操作（查詢、單欄位 mutation、follow-up）→ AI 沙盒（`!XXX`）
- 複雜表單（欄位多、需要結構化選項）→ LIFF

入口：用戶在 LINE 打「!新增客戶」 → AI 看到「想新增客戶」 → reply 含 LIFF 按鈕的 Flex（取代當前的「請給簡稱地址類別」回問）

### 12.6 不做的

- ❌ Flex Message 假裝 form（LINE Flex 不支援真 input，硬做用按鈕 mock 體驗很差）
- ❌ 完全用 LIFF 取代 AI 沙盒（簡單對話用 LIFF 太重）
- ❌ 不要在 LIFF 裡重做業務邏輯 — 一律呼叫 atomic tools

### 12.7 接手 Claude 啟動 LIFF 工作的步驟

1. **跟用戶確認場景優先順序**：客戶？門診？班次？哪個先做？
2. **跟用戶要 LINE Developer Console 帳號權限**或請用戶代建 LIFF App，拿 `LIFF_ID` + `LINE_LOGIN_CHANNEL_ID`（不是 messaging API channel ID）
3. **環境變數加**：`LIFF_ID=...`、`LINE_LOGIN_CHANNEL_ID=...`（給 idToken 驗證用）
4. **Phase A 先做**（建設） → Phase B（第一表單） → 用戶實機驗一輪
5. **Phase C 按用戶優先級擴**

### 12.8 給用戶的問題（接手後問）

接手 Claude 第一輪該問用戶：
- 「LIFF 第一個要做哪個 form？客戶 CRUD / 門診記錄表 / 班次新增 / ...」
- 「LINE Developer Console 是你的還是另一個帳號？要不要我列建 LIFF App 的步驟給你？」
- 「門診記錄表的欄位有哪些？這是新 DB schema，要先設計」
- 「客戶 form 是新增 + 編輯都要、還是先做新增？」
