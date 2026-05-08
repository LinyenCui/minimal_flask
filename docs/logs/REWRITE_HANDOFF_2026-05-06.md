# Rewrite v0.1 進度交接 — 2026-05-06（v5）

> **新對話開頭給 Claude 看**：請先讀這檔 + `docs/logs/REWRITE_HANDOFF_2026-05-04.md` (v4)。
> 主 repo：`/Users/linyancui/minimal_flask`，當前分支：`dev_line_channel`。
> ⚠️ **絕對不要 checkout / push main 分支**。

---

## 0. TL;DR — 給接手的 Claude

自 v4 (commit `8b72f6b`) 起，2 個 commit 進來：

```
07cc0bf feat(rewrite): LIFF 入口接 sandbox + 多輪對話補強 + temp 班次顯示修正
1784b35 feat(rewrite/liff): Phase A 基礎 + Phase B 客戶 CRUD 表單
```

**這兩天做了什麼**：

1. **LIFF 客戶 CRUD（Phase A+B 全部完成）** — `!新增客戶` → Flex 含 LIFF 按鈕 → 表單 → 儲存 → 自動關閉 → 後端 push 客戶詳情 Flex 回 LINE。編輯按鈕（客戶詳情卡）改 URI 直開 LIFF 帶 `?customer_id=N`。手機 LIFF webview + 桌機瀏覽器都跑得動。實機驗：#67 李張月華新增、編輯。
2. **沙盒多輪對話 3 個 bug 修復**（之前用戶很怒）：
   - 短 follow-up（「是」/「確認」/「14」/「-50」）bypass intent classifier，sandbox-active state 內直接帶 `last_skill`
   - state 從只存「上一輪」改存最近 5 輪 history，解決多輪請假流程「-50 時 AI 忘了 schedule_id」的 bug
   - decoration 後 `type=quick_reply` 導致 `last_ai_text=''` 的 capture bug
3. **詳情卡顯示淨化** — 客戶卡醫療欄位（生日 / 病歷層 / 健保 / 病歷號 / 身分證）改成有值才顯示；班次卡 `temp` 類型用 `custom_*` 替代「臨時地點」placeholder。
4. **AI prompt 規則** — 4 個 skill 各加一條「完成單一操作後不主動追問下一步、不說『需要什麼協助』客套句」。
5. **DB schema 對齊 Render** — 本地 `completed_trips` 多了兩個 Render 沒有的 FK（`start_point_fkey` / `end_point_fkey` → `customers.short_name`）導致 temp trip 掉不進 completed_trips。drop 兩 FK + 補進 9 筆歷史 stuck（820, 935-942）。

**下個 Claude 第一件事**：聽用戶今天有什麼新反饋；如果沒有就開 **Tier 1 — 過去態 completed_trip skill**（用戶確認方向，見 §13）。

---

## 1. 自 v4 起累積的關鍵業務邏輯與決策

### 1.1 LIFF 設定

- LINE Login channel（不是 Messaging API）→ Channel ID `2009974915`
- LIFF App ID：`2009974915-h88GuNK8`
- channel 已 `Published`（任何 LINE userId 都能用，無 Roles 邀請步驟）
- env：`.env.dev` 加 `LIFF_ID` + `LIFF_CHANNEL_ID`（gitignore 不入 commit；prod 上 Render 要記得補 dashboard env）
- LIFF Endpoint URL（LINE Console 設）：`https://<ngrok-or-render>/liff/customer/form`
- ngrok 免費版每次重啟換 URL → 要回 Console 改 Endpoint。建議付費版固定 URL 或 reserved domain。

### 1.2 LIFF 入口流程（Tier 0 — 已做）

```
用戶打「!新增客戶」(無參數)
    ↓
sandbox_handler 攔截（_NEW_CUSTOMER_LIFF_TRIGGERS）→ 不過 AI
    ↓
回 Flex 含 [📝 開填寫表單] URI button → https://liff.line.me/<LIFF_ID>
    ↓
LIFF webview / 桌機瀏覽器開 https://<ngrok>/liff/customer/form
    ↓
用戶填表 → JS POST /liff/customer with idToken
    ↓
liff_auth_required decorator 驗 idToken（LINE oauth2/v2.1/verify）
    ↓
呼叫 rewrite.tools.customer.create_customer（不重做業務邏輯）
    ↓
成功 → 後端 push 客戶詳情 Flex + text「已新增 #X」給 user (1-on-1 with bot)
    ↓
前端 liff.closeWindow() (LIFF webview 才有效；桌機顯示「可關閉視窗」)
```

「客戶詳情」Flex 卡的「編輯」按鈕也是 URI → `https://liff.line.me/<LIFF_ID>?customer_id=N`，customer_form.html 的 JS 認 query string 自動進編輯模式。

### 1.3 沙盒多輪對話：當前可靠運作條件

跨多輪 follow-up 要兩個條件同時滿足：
- AI 第一輪 reply 是 text 訊息且結尾「？」/ 含「請問 / 請提供」等 keyword → `_ai_is_waiting_for_followup` 回 True → 設 sandbox-active state
- 後續用戶訊息：90 秒內 + 短 follow-up（在 `_SHORT_FOLLOWUP_TOKENS` set 或 ≤4 字 / 純數字）→ bypass classifier → 帶 last_skill

state 內存 `history`（最近 5 輪 user/ai pair），agent prompt 餵 full history。**flex 訊息回應視為「結果回覆」**，不算 follow-up，不會設 state。

### 1.4 預約 / temp 班次 schema 真相

- `trips` 表：`trip_type` 區分 `'fixed'` / `'temp'`；`fixed_trip_id` 有值代表是 fixed 模板匯入的
- temp 班次因起終點五花八門（不在 `customers.short_name` 約束內）→ DB 寫「臨時地點」(customer #52) placeholder + `custom_*` 寫真實值
- 顯示時 swap：`if trip_type=='temp': use custom_*`（rewrite TripView.display_route 已實作；legacy trip_query_flex 早就有）
- scheduler 把 temp trip → completed_trips 時也 swap（用 `custom_*` 寫進 completed_trips.start_point）
- ⚠️ **本地 dev DB 先前多了兩個 Render 沒有的 FK**（`completed_trips_start_point_fkey` / `_end_point_fkey` → `customers.short_name`），擋了 temp 班次寫入。已 DROP，跟 Render 對齊。code 沒動。

### 1.5 「對話模式進行中」的範圍

- 出現條件：AI 在等 follow-up（_ai_is_waiting_for_followup True，純 flex 不算）
- 顯示：text 訊息結尾加「💬 對話模式進行中（90秒內可不加 ! 前綴回覆）」+ Quick Reply [❌ 結束對話]
- decoration 後 type=text → quick_reply（不是 LINE 原生格式但 line_bot.py 認）

---

## 2. 當前 rewrite/ 結構（v5）

```
rewrite/
├── tools/                       27+ atomic tools
│   ├── customer.py              query/CRUD/birthday + medical
│   ├── trip.py                  query / mutation / create_trip / TripView.display_route()
│   ├── fixed_schedule.py        query / update / leave / restore
│   └── leave.py                 跨表 wrapper
│
├── ai/                          (1,475 行 src)
│   ├── client.py / skill.py / agent.py / multi_skill_agent.py / intent.py / repl.py
│   └── skills/
│       ├── trip_query.py        + 「不追問」prompt 規則
│       ├── trip_mutation.py     + 「不追問」prompt 規則
│       ├── customer.py          + 「不追問」prompt 規則
│       └── fixed_schedule.py    + 「不追問」prompt 規則
│
├── handlers/
│   ├── sandbox_handler.py       v5 加：!新增客戶 LIFF Flex / short followup bypass / history(5)
│   └── liff/                    🆕 v5
│       ├── __init__.py          liff_bp blueprint, url_prefix=/liff
│       ├── auth.py              liff_auth_required decorator + verify_line_id_token
│       ├── health.py            /liff/health, /liff/whoami(_test)
│       └── customer.py          客戶 CRUD endpoints + push_customer_to_user
│
├── views/
│   ├── customer_flex.py         + render_new_customer_entry, _liff_url; 醫療欄位條件顯示
│   └── trip_flex.py             用 TripView.display_route() (temp swap)
│
├── router.py                    690 行（仍偏離 spec <100 — 沒新增 regex；待之後拆檔）
├── conversation_state.py        + history 欄位（最近 5 輪）
└── (templates/liff/)            🆕 customer_form.html / whoami_test.html

```

⚠️ 用戶 5/4 已警告：router.py 不要再加新 regex 命令（spec 量化目標已偏離），有東西先拆 `handlers/trip_command.py` 之類。

---

## 3. spec §1 量化目標 vs 現況（2026-05-06）

| 項目 | spec 目標 | 現況 | 評估 |
|-----|---------|-----|------|
| AI 三巨頭 | ~600 行 | rewrite/ai/ ~1,500 行 | ✅ 在預算內 |
| atomic tools | 17 個 | 27+ 個 | ✅ 超 spec |
| 入口 router | < 100 行 | rewrite/router.py **690 行** | ⚠️ 偏離（這次沒加東西，但下次再加 mutation 命令前要拆檔） |
| sandbox_handler | — | 414 行（v4 是 ~280；history + bypass 加進來變大）| 不算大 |

---

## 4. 下一步（按優先順序）

### Now（接手後立即可做）
- **無**。聽用戶實機反饋；今天大量改動可能還有邊界 case。

### Tier 1（用戶確認方向，下個工作 session 主軸）—— 過去態 query skill
**目標**：把 legacy 的「查已完成 / 統計金額」搬到 sandbox。

新檔：
- `rewrite/tools/completed_trip.py`
  - `query_completed_trips(date_from, date_to, customer_short_name, driver_id, category, status, limit)`
  - `query_completed_trip_by_id(id)`
  - `aggregate_fares(date_from, date_to, group_by='driver'|'customer'|'category', ...)` — sum/count
- `rewrite/ai/skills/completed_trip.py` — system_prompt + tool schemas
- `rewrite/views/completed_trip_flex.py` — 詳情卡 / 列表 / 統計卡（金額醒目顯示）
- `rewrite/handlers/sandbox_handler.py` + `intent.py` — 加 `'completed_trip'` intent

⚠️ 三時間態 corner case：「今天」可能橫跨 trips（未過時間） / completed_trips（已過時間）— CLAUDE.md 已寫 router 規則，照做。重用 `modules/services/date_range_query_service.py` 的混合查詢邏輯。

### Tier 2 —— 過去態 mutation
- `update_completed_trip_fare(id, meter_fare, extra_fare, modification_reason)` — 對應 legacy「記錄車資」
- 接到 trip_mutation skill 或 completed_trip skill。

### Tier 3 —— 報表生成（配 LIFF，**不純 sandbox**）
- 「生成週/日報表」要選日期 / 司機 / 類別 / 格式 → 走 LIFF 表單選參數 + 後端產 Excel + Drive 上傳。
- 跟 LIFF booking（用戶提過）性質相同，可一起規劃。

### 拆 legacy 的時機
Tier 1 + 2 跑穩 1-2 週後：
- 逐項移除 `_HARD_FALLTHROUGH_KEYWORDS`（`'匯入', '預約', 'booking', '報表'...`）
- 「匯入固定班次」legacy 還沒重做（spec C 路線）→ 最後再砍
- 「預約叫車」改走 LIFF 表單後 legacy 也可以砍
- 最終目標：webhook 不再 fall-through，`customers_ai_service` 退役

---

## 5. v4 §8 Don't 清單延伸（v5 新增 4 條）

按時間順序，5/5–5/6 踩過：

9. **不要憑想像就改 prompt 解決對話問題** — 我先改 4 個 skill prompt 想壓「請問需要什麼協助」尾追，結果實際 log 顯示「是」根本沒到 rewrite，是 fall-through legacy 在說客套話。要先看 log 找根因，才不浪費修錯地方。
10. **不要相信「sandbox-active state 90 秒會攔下一句」**而不驗 — classifier 對短訊息（「是 / 確認 / 14」）會回 unknown 直接 fall-through 到 legacy。需要 bypass classifier 走 last_skill 才真正生效。
11. **不要忘記 state 是「替換」不是「累積」** — 每輪 `_state_set` 蓋掉前面，多輪請假流程到第 3 輪 AI 已忘 schedule_id。要顯式保留 history。
12. **不要在 `db.create_all()` 假設 schema 一致** — 本地 dev DB 多了 Render 沒有的 FK，是 model 宣告 + 早期 create_all 殘留。Schema 差異要看 Render backup 確認，**不要光看 model**。

---

## 6. 已知不會做（C 路線 — 不重做、走 legacy）

延續 v4 §5：

| 功能 | 路徑 | 為什麼不做 |
|------|-----|---------|
| 匯入固定班次（每週）| legacy import_handler | spec §3.3 第 5 個工具，週次計算 + 批量 INSERT 複雜；走 C |
| 預約叫車（!預約 ...） | legacy customers_ai_service `_tool_booking_create` | rewrite 已有 `create_trip` atomic tool 但 booking 流程不一樣；改天用 LIFF 表單做 |
| 「明天 X 的狀態」三層 quick reply 批量請假 | legacy intent_executor + leave_mode_handler | 用戶實機驗 fall-through OK；不重做 |

---

## 7. 實機測試怎麼跑（同 v4 §9）

**A. 終端 REPL**：`python rewrite/ai/repl.py`
**B. unit / integration tests**：`for f in rewrite/tools/test_*.py rewrite/ai/test_*.py; do echo $f; python $f | tail -3; done`
**C. LINE 實機**：dev_line_channel ngrok。看 Flask console log（`[intent]` / `[Agent loop]` / `[rewrite sandbox]`）
**D. LIFF 實機**：手機 LINE 點 `https://liff.line.me/2009974915-h88GuNK8` 或桌機開 `https://<ngrok>/liff/customer/form`

---

## 8. 用戶相關備忘（同 v4 §10）

- userId（測試）：`U6b520261e9199a21d25e6d20509eda3f`
- email：`gshanyue222@gmail.com`
- 業務：醫療接送派班（診所 / 東洋 / 門診）
- 工作流：dev_line_channel 上做、main 不動、最終切 Render（Phase 7）
- 部署提醒：Render 上 prod env 還沒設 `LIFF_ID` / `LIFF_CHANNEL_ID`（dev/prod 之後可建兩個獨立 LIFF App，dev 指 ngrok / prod 指 render URL）

---

## 9. 接手 Claude 的開頭建議

```
（用戶說）
請讀 docs/logs/REWRITE_HANDOFF_2026-05-06.md (v5) + ...05-04.md (v4) 後接續。
git log -10 看最新狀態。
我接下來想做 X / 我踩到 Y 問題 / 我要驗 Z 功能。
```

接手第一輪建議只做：
1. 讀 v5 + v4
2. `git log -10` 看最新 commits
3. 跟用戶確認當前要做什麼（不要主動加功能）
4. 如要開 Tier 1，先列 atomic tool 規格給用戶看再動

---

*v5 建檔者：Claude，2026-05-06*
*下個 Claude：先讀 §0 §1 §5（Don't 延伸）→ git log → 開工*
