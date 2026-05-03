# Rewrite v0.1 進度交接 — 2026-05-03（v3）

> **新對話開頭給 Claude 看**：請先讀這檔，確認狀態後再繼續。
> 主 repo 路徑：`/Users/linyancui/minimal_flask`
> 當前分支：`dev_line_channel`
> 規格書：`.claude/worktrees/compassionate-black-dfd7be/docs/logs/rewrite_spec_v0.1.md`
>
> ⚠️ rewrite_spec_v0.1.md 仍 untracked 在 compassionate-black-dfd7be worktree，
> 下次方便時可一併搬到 dev_line_channel 的 docs/logs/。

---

## 1. 用戶最近指示（按時間順序）

1. 「在dev_line_channel上舊代碼不要管，直接重做，main上的不要動到就好」
2. 「所有都重做，現在只是從源頭客戶資料表開始」
3. 「客戶資料查找增刪修改的功能完成之後，固定班次的查找增刪請假回復等等功能，先延用！沙盒裡那套，跳過它後直接做「診所班次 xxx」等的trips查找增刪修改請假回復等功能。」
4. 「接續第 2、3 批」(2026-05-03 中) — 已完成
5. 「先更新 rewrite_handoff 然後 R-3 統一介面」(2026-05-03 晚) — 已完成
6. 「資料庫同步暫時封閉 customers」(避免本地 dev 資料被洗) — 已完成
7. 「mutation 按鈕走 Quick Reply」(不放 flex footer) — 已完成
8. **「請假流程要走原系統 input mode 模式（不直發完整命令、由 conversation state 等用戶輸入「[原因] [負加成]」）」** — 已完成
9. **「目前測試沒問題，可以開始下一步」(2026-05-03 晚)** ← 當前

⚠️ **重要設計約束**（多次溝通確認，下個 Claude 必看）：
- mutation 按鈕**用 Quick Reply 呈現**，不要放在 flex bubble footer
- 請假流程**保持「進輸入模式」**，不要憑空編請假慣用語（自己來/出國/生病這種 spec §6.3 的占位字不能直接套）
- 病患接送的真實請假原因是「化療/身體不適/臨時有事/回診」這類醫療情境，每次不同，不能列舉
- 「固定班次請假」往後也走同樣模式（conversation state input mode）

---

## 2. 已完成 commits（dev_line_channel，自 ef2c6e8 後）

```
309ee64  fix: 按鈕回 Quick Reply（不放 flex footer）；只請假流程進輸入模式  ← 最新
817c7c0  fix: 請假改回原系統「輸入模式」流程，砍掉憑空編造的慣用語
4e7aa34  fix(trip_flex): 詳情卡 footer 三按鈕改 vertical 布局
f0fa07b  fix(sync): 暫時跳過 customers 表同步（保護 dev 上本地資料）
b50a689  feat: 第 4 批 — quick reply 接 5 個 trip mutation 命令到 LINE
737e68c  feat(rewrite): 接 postback handler — trip_detail:NNNN 點擊跳詳情
6250311  fix(trip_flex): 同日多筆改拆頁 carousel + 行字體縮為 xxs
ff6237a  rewrite: R-3 統一請假介面 apply_leave（trips 路徑優先 + fixed fallback）
ef2c6e8  docs: 把 REWRITE_HANDOFF 搬到 dev_line_channel + 更新到第 3 批進度
f462821  rewrite: trips mutation 第 3 批 — create_trip
4b84b17  rewrite: trips mutation 第 2 批 — cancel/conflict/restore/assign/unassign
f970925  rewrite: trips mutation 第 1 批 — passenger_leave + R-5 鎖 + R-6 audit
```

⚠️ commit 4e7aa34 / 817c7c0 / b50a689 中的部分視覺/排版設計被後續 commit
推翻 — 讀 git log 時要看最終是 309ee64。詳見 §8 設計演化。

---

## 3. DB 狀態（本地 dev DB only，Render 沒動）

### 已套用 migrations
- `001_add_customer_fields.sql`：customers + birthday/座標/時間戳 + trigger
- `002_add_medical_fields_and_seed.sql`：customers + 身分證/性別/病歷號/健保 + 5 筆範例
- `003_audit_log.sql`：audit_log 表（R-6）

### sync_from_render.py 行為（2026-05-03 起）
- `customers` 表暫跳過同步（commit f0fa07b 加 SKIP_TABLES）
- 每次同步開頭印 ⏭️ 提示
- 其他表（drivers / fixed_schedules / trips / account_ledger / payments）正常同步
- post_sync_seed.py 是 UPSERT idempotent，5 筆範例患者每次刷新

### Render DB
- 完全未動

### audit_log action_types（已驗證）
- passenger_leave / cancel_trip / mark_conflict / restore_to_ready /
  assign_driver / unassign_driver / create_trip

---

## 4. rewrite/ 目錄結構（dev_line_channel）

```
rewrite/
├── __init__.py
├── conversation_state.py       # ⭐ 新（in-memory，30min TTL，請假 input mode 用）
├── tools/
│   ├── base.py                 # ToolResult, R-5 decorator, audit helpers
│   ├── customer.py             # 8 個 atomic tools
│   ├── trip.py                 # 4 query + 7 mutation = 11 個 tools
│   ├── leave.py                # ⭐ R-3 apply_leave 跨表 wrapper
│   ├── test_customer.py             # 10 個測試 ✅
│   ├── test_customer_crud.py        # 11 個測試 ✅
│   ├── test_customer_birthday.py    # 5 個測試 ✅
│   ├── test_trip.py                 # 9 個測試 ✅
│   ├── test_trip_mutations.py       # 23 個測試 ✅（第 1+2 批）
│   ├── test_trip_create.py          # 12 個測試 ✅（第 3 批）
│   └── test_apply_leave.py          # 6 個測試 ✅（R-3）
├── views/
│   ├── customer_flex.py
│   ├── trip_flex.py            # ⚠️ 不含 footer button — quickReply 在 router attach
│   ├── test_customer_flex.py
│   └── test_trip_flex_pagination.py # 9 個測試 ✅
├── tests/
│   └── test_c_scenarios.py
└── router.py                   # message + postback dispatch + leave_input state
```

---

## 5. 已實作 atomic tools 清單

### customers（8 個 — 完整）
- `query_customer` / `query_customer_by_term` / `get_customer_by_id`
- `create_customer` / `update_customer` / `delete_customer`
- `query_customers_by_birthday_day` / `query_birthday_day_summary`

### trips（query 4 個 + mutation 7 個 = 11 個）
- query: `query_trips` / `query_trip_by_id` / `query_today_trips` / `query_pending_dispatch`
- mutation 第 1 批: `passenger_leave`
- mutation 第 2 批: `cancel_trip` / `mark_conflict` / `restore_to_ready` / `assign_driver` / `unassign_driver`
- mutation 第 3 批: `create_trip`（取代沙盒 booking_create）

### 跨時間態 wrapper（R-3）
- `leave.apply_leave` — target_id 自動分流 trips / fixed_schedules
  - 在 trips → passenger_leave
  - 在 fixed_schedules → fallback 提示走 sandbox
  - 都不在 → fail

### 仍缺的 spec §3.1 工具（2 個小型）
- `update_passenger_name`（改乘客名，鎖內可，不需確認）  ← **下一步要做**
- `record_fare_current`（記錄現在態車資，鎖內可，不需確認）  ← **下一步要做**

---

## 6. 設計原則 R-1 ~ R-7

| | 原則 | 落實處 |
|--|-----|------|
| R-1 | 跨時間態操作先判斷 ID 所屬表 | ✅ leave.apply_leave |
| R-2 | 三時間態工具對等覆蓋 | ✅ trips 11 個（過去態 v0.2 補） |
| R-3 | 統一介面工具優先（apply_leave） | ✅ |
| R-4 | Tool 純函數 | ✅ |
| R-5 | 30 分鐘鎖 decorator | ✅ |
| R-6 | mutation 寫 audit log | ✅ 7 種 action_type |
| R-7 | 個資處理（身分證遮罩） | ✅ |

---

## 7. LINE 整合狀態（已實機驗證）

### 命令攔截點（modules/routes/webhook.py）
- Postback：sandbox 之前 → `rewrite.router.try_route_postback`（trip_detail:NNNN）
- Message：sandbox 之後 → `rewrite.router.try_route`（先檢 leave_input state，再 prefix）

### 已上線命令（rewrite/router.py）

**客戶領域**
```
查客戶 <關鍵字>     |  客戶詳情 <ID>
病歷層 <日>         |  病歷層分布
```

**班次查詢**
```
查班次 [日期] [司機X]   |  診所班次 [日期]
東洋班次 [日期]         |  班次詳情 <trip_id>
待派班次
```

**班次 mutation（quick reply 觸發 + input mode）**
```
班次註銷 <id>            → cancel_trip（直發）
班次衝突 <id>            → mark_conflict（直發）
班次請假 <id>            → 進 leave_input state（兩步驟）
班次恢復 <id>            → restore_to_ready（直發）
班次撤銷指派 <id>        → unassign_driver（直發，鎖內也可）
```

### Quick Reply 設計（trip_flex.py:build_trip_quick_reply）

詳情卡 reply 時 attach quickReply（顯示在 LINE 輸入框上方，不是 bubble footer）：

| trip 狀態 | Quick Reply items |
|----------|------------------|
| 已完成 | 無 |
| 鎖內 | 無 |
| 鎖外 + 準備 | [❌ 註銷] [⚠️ 衝突] [🏷️ 請假] |
| 鎖外 + 請假 | [↩️ 改回準備] |
| 鎖外 + 衝突 | [↩️ 改回準備] |
| 鎖外 + 註銷 | [↩️ 改回準備] |

### 請假 input mode 流程（重要！）

**保留原系統行為**，不要改：

```
1. 用戶按 [🏷️ 請假] → 自動發送「班次請假 1097」（只 trip_id）
2. router._handle_trip_leave 預檢：
   - trip 不存在 → 回 error 訊息
   - is_locked → 回「30 分鐘鎖內無法請假」
   - status != '準備' → 回「狀態 X 無法請假」
   - 通過 → set_state(user_id, 'leave_input', {trip_id: 1097})
3. bot reply 提示：
   ┌────────────────────────────────┐
   │ 🏷️ 班次 #1097 乘客請假          │
   │                                │
   │ 請輸入：[原因] [負加成]         │
   │                                │
   │ ❌ 退出：點下方「放棄操作」     │
   └────────────────────────────────┘
   + Quick Reply [❌ 放棄操作]

4. 用戶下一則 message 進來，try_route 開頭先 _state_get：
   - 「化療 -30」 → rsplit + int → passenger_leave + 清 state → 回更新後詳情卡
   - 「化療」（沒整數） → 「❌ 操作失敗」+ 清 state（用戶從按鈕重來）
   - 「放棄操作」/「放棄」/「取消」 → 清 state + 「已放棄請假操作」
```

**禁忌（已踩過坑）**：
- ❌ 不要把「自己來/出國/生病」這種 spec §6.3 範例字當預設清單
- ❌ 不要把按鈕加進 flex bubble footer（用戶選的是 Quick Reply）
- ❌ 不要把 [請假] 按鈕設成「直發完整命令」（要進 input mode）

### Conversation state 機制

`rewrite/conversation_state.py`：
- `set_state(user_id, type, payload)` / `get_state(user_id)` / `clear_state(user_id)`
- in-memory dict + threading.Lock，30 分鐘 TTL
- spec N-3 標 v0.2 改 DB 持久化（多 worker 才需要）

⚠️ try_route 開頭一定要先 `_state_get(user_id)`，有 state 就 dispatch 到對應
handler，所有訊息都先給 state handler 接（包括 rewrite prefix 命令也會被攔截）。

### 還沒接 LINE 的（將來工作）
- update_passenger_name / record_fare_current（spec §3.1 還缺，**下一步補**）
- fixed_schedules 全套（先用 sandbox `!` 走）
- 批量請假（截圖原系統有「全部請假」批量入口）

---

## 8. 設計演化歷程（避免下個 Claude 重蹈覆轍）

第 4 批 LINE 整合走過幾次反覆，最終定案：

| 嘗試 | commit | 結果 |
|-----|--------|-----|
| Quick Reply + 請假慣用語直發（自己來/出國/生病） | b50a689 | ❌ 用戶罵：spec 占位字當業務 |
| 改 footer button vertical | 4e7aa34 → 817c7c0 | ❌ 用戶選的是 Quick Reply 不是 footer |
| 把 [請假] 改進 input mode | 817c7c0 | ✅ 流程對 |
| 把按鈕加回 flex footer | 817c7c0 | ❌ 用戶選的是 Quick Reply |
| 拿掉 footer + Quick Reply + input mode | 309ee64 | ✅ 最終 |

**教訓**（已寫進 `~/.claude/projects/-Users-linyancui-minimal-flask/memory/feedback_check_real_ux.md`）：
- 修問題要拆「行為」與「呈現」兩層分開確認
- spec 範例字（「常用」「示範」「例如」開頭）視為 placeholder，不能直接 production
- 改設計前先回看用戶在前一輪選了什麼方向

---

## 9. 接下來要做的（按優先順序）

### Now：補 spec §3.1 還缺的兩個小工具（用戶確認方向）
- `update_passenger_name(trip_id, new_name, ...)` — 改乘客名
  - allow_in_lock=True，不需確認
  - audit log action='update_passenger_name'
  - 寫單元測試
- `record_fare_current(trip_id, meter_fare, extra_fare, ...)` — 記錄現在態車資
  - allow_in_lock=True，不需確認
  - 跟「記錄已完成車資」不同（那是 v0.2 過去態工作）
  - 寫單元測試

兩個都做完後 trips 領域工具集就齊（11 → 13 個）。

接 LINE 命令的部分等之後決定（可能是 quickReply 或文字命令）。

### 後續批次
- **批量請假**（截圖原系統有「全部請假」入口）：選某日所有班次，一次套上同個原因+加成
- **fixed_schedules 全套**：用戶先跳過用 sandbox，等 trips 套件穩定再回頭
  - 屆時 `apply_leave` 補完 fixed_schedules 路徑（目前是 fallback）
  - 「固定班次請假」必須走同樣 input mode（用戶明示）

---

## 10. 新對話開頭建議

```
（用戶說）
請讀 docs/logs/REWRITE_HANDOFF_2026-05-03.md 後接續。
重點看 §1 的「重要設計約束」+ §7 的「請假 input mode 流程」+ §8 的「禁忌」。
git log 看最新 commit 確認進度，再決定要不要動。
```

---

## 11. 用戶相關記憶

- userId（測試用）：`U6b520261e9199a21d25e6d20509eda3f`
- 本地 DB：`postgres@localhost:5432/dispatch_db`
- Render DB：`RENDER_DB_HOST=dpg-cvhb...`（不要動）
- venv：`/Users/linyancui/minimal_flask/venv`
- 工作流：dev_line_channel 上重做、main 不動、最終切 Render
- 用戶會以使用者身份在 LINE 上實機跑流程，截圖回饋。設計前若沒看過原系統的真實畫面，不要憑 spec 想像

---

*v3 建檔者：Claude（接續第 4 批 LINE 整合 + 請假 input mode + 實測通過）*
*下一個 Claude：請先讀 §1 §7 §8 三節，再動手 — 這幾節寫的是踩過坑後的硬約束*
