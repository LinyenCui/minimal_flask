# Rewrite v0.1 進度交接 — 2026-05-03（v2）

> **新對話開頭給 Claude 看**：請先讀這檔，確認狀態後再繼續。
> 主 repo 路徑：`/Users/linyancui/minimal_flask`
> 當前分支：`dev_line_channel`
> 規格書：`.claude/worktrees/compassionate-black-dfd7be/docs/logs/rewrite_spec_v0.1.md`
>
> ⚠️ 註：本 handoff 與 spec 原本是 untracked（只活在 compassionate-black-dfd7be
> worktree），這個 v2 版搬到 dev_line_channel 的 docs/logs/ 並（待）commit，
> 之後可考慮把 spec 也一起搬過來避免遺失。

---

## 1. 用戶最近指示（按時間順序）

1. 「在dev_line_channel上舊代碼不要管，直接重做，main上的不要動到就好」
2. 「所有都重做，現在只是從源頭客戶資料表開始」
3. 「客戶資料查找增刪修改的功能完成之後，固定班次的查找增刪請假回復等等功能，先延用！沙盒裡那套，跳過它後直接做「診所班次 xxx」等的trips查找增刪修改請假回復等功能。」
4. 「接續第 2、3 批」(2026-05-03 中) — 已完成
5. **「先更新 rewrite_handoff 然後 R-3 統一介面」**(2026-05-03 晚) ← 當前

意義：
- 客戶部分（query/CRUD/birthday）工具層完成 ✅
- fixed_schedules 跳過，繼續用既有 sandbox `!` 前綴
- trips 三批 mutation（請假/註銷/衝突/恢復/指派/撤銷/創建）全部完成 ✅
- 接下來：**R-3 統一介面 `apply_leave`**（trips 路徑優先，fixed 走半成品 fallback）

---

## 2. 已完成 commits（dev_line_channel）

```
f462821  rewrite: trips mutation 第 3 批 — create_trip（取代沙盒 booking_create）  ← 最新
4b84b17  rewrite: trips mutation 第 2 批 — cancel/conflict/restore/assign/unassign
f970925  rewrite: trips mutation 第 1 批 — passenger_leave + R-5 鎖 + R-6 audit
45215bb  rewrite v0.1: 群組支援 — 早期攔截繞過 should_process 過濾
0ce3d5f  rewrite v0.1: trips 領域上線 — query tools + flex view + router
99337cc  rewrite v0.1: LINE webhook 整合 — 4 個 customer 命令上線
d81de03  rewrite: customer Flex view 渲染器
b5e8629  rewrite: 病歷層查詢
5bf1059  rewrite: customer CRUD tools
de14ca7  sync handler: 自動串接 post_sync_seed
29a310b  rewrite v0.1: customers schema 升級 + query 工具 + seed
```

---

## 3. DB 狀態（本地 dev DB only，Render 沒動）

### 已套用 migrations
- `001_add_customer_fields.sql`：customers + birthday/座標/時間戳 + trigger
- `002_add_medical_fields_and_seed.sql`：customers + 身分證/性別/病歷號/健保 + 5 筆範例
- `003_audit_log.sql`：audit_log 表（R-6）

### Render DB
- 完全未動，sync 來的資料只填舊欄位、新欄位 NULL
- post_sync_seed.py 自動補 5 筆範例患者

### 第 3 批新增的 audit_log action_type
- `create_trip`（before_state=None, after=完整 snapshot, extra 含 fk_resolved 細節）

---

## 4. rewrite/ 目錄結構（dev_line_channel）

```
rewrite/
├── __init__.py
├── tools/
│   ├── __init__.py
│   ├── base.py              # ToolResult, R-5 decorator, audit helpers
│   ├── customer.py          # 8 個 atomic tools
│   ├── trip.py              # 4 query + 7 mutation = 11 個 tools  ← 第 3 批後
│   ├── test_customer.py             # 10 個測試 ✅
│   ├── test_customer_crud.py        # 11 個測試 ✅
│   ├── test_customer_birthday.py    # 5 個測試 ✅
│   ├── test_trip.py                 # 9 個測試 ✅
│   ├── test_trip_mutations.py       # 23 個測試 ✅（第 1+2 批）
│   └── test_trip_create.py          # 12 個測試 ✅（第 3 批，新增）
├── views/
│   ├── customer_flex.py
│   ├── trip_flex.py
│   └── ...
├── tests/
│   └── test_c_scenarios.py
└── router.py
```

---

## 5. 已實作 atomic tools 清單

### customers（8 個 — 完整）
- `query_customer` / `query_customer_by_term` / `get_customer_by_id`
- `create_customer` / `update_customer` / `delete_customer`
- `query_customers_by_birthday_day` / `query_birthday_day_summary`

### trips（query 4 個 + mutation 7 個 = 11 個）
- query: `query_trips` / `query_trip_by_id` / `query_today_trips` / `query_pending_dispatch`
- 第 1 批 mutation: `passenger_leave`
- 第 2 批 mutation: `cancel_trip` / `mark_conflict` / `restore_to_ready` / `assign_driver` / `unassign_driver`
- 第 3 批 mutation: `create_trip`（取代沙盒 booking_create）

### 仍缺的 spec §3.1 工具（2 個小型）
- `update_passenger_name`（改乘客名，鎖內可，不需確認）
- `record_fare_current`（記錄現在態車資，鎖內可，不需確認）

### TripView 計算欄位
- `display_status`、`status_emoji`、`is_locked`、`minutes_until_trip`

### CustomerView 計算欄位
- `birthday_day`、`age`、`is_masked`

---

## 6. 設計原則 R-1 ~ R-7

| | 原則 | 落實處 |
|--|-----|------|
| R-1 | 跨時間態操作先判斷 ID 所屬表 | ⏳ 將在 apply_leave 實作 |
| R-2 | 三時間態工具對等覆蓋 | ✅ trips 11 個 |
| R-3 | 統一介面工具優先（apply_leave） | ⏳ 接下來做 |
| R-4 | Tool 純函數，session 從參數傳 | ✅ 全 rewrite/ 遵守 |
| R-5 | 30 分鐘鎖 decorator 統一 | ✅ `@require_modifiable_window` |
| R-6 | 所有 mutation 寫 audit log | ✅ 7 種 action_type 都驗過 |
| R-7 | 個資處理（身分證遮罩） | ✅ CustomerView mask_id 預設 True |

---

## 7. LINE 整合狀態

### 已可用命令（rewrite/router.py）
```
查客戶 <關鍵字>           # 群組打 /查客戶 X
客戶詳情 <ID>
病歷層 <日>
病歷層分布

班次詳情 <trip_id>
查班次 [日期] [司機X]
診所班次 [日期]
東洋班次 [日期]
待派班次
```

### 攔截點
- `modules/routes/webhook.py` callback 內，sandbox 之後、should_process 之前
- 私聊 + 群組（`/` 前綴）都能用
- `!` `！` 仍走 sandbox（沒被搶）

### ⚠️ 已有工具但還沒接到 LINE 的（**第 4 批工作**）
- 7 個 mutation（passenger_leave / cancel / conflict / restore / assign / unassign / create_trip）
- 詳情卡 postback 按鈕（[註銷] [衝突] [請假] [恢復準備]）
- → 工具層全測過，但用戶在 LINE 還無法觸發

---

## 8. 當下進度

第 3 批已完成 commit（f462821），沒有中斷的工作。

**下一個方向（用戶指示）：R-3 統一介面 `apply_leave`**

設計初稿：
```python
def apply_leave(
    *,
    session,
    target_id: int,        # 不知道是 trip_id 還是 fixed_schedule_id
    reason: str,
    surcharge: int = 0,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    統一請假介面（R-3）— AI agent 不需要知道時間態差別

    路由：
      - target_id 在 trips 表          → 呼叫 passenger_leave（已實作）
      - target_id 在 fixed_schedules → 暫回 fallback 提示走 sandbox `!`
      - 不在任何表                    → fail

    修 B-1 / C-3：沙盒「請假」永遠路由到 fixed_schedule_leave 的 bug。
    """
```

實作位置選項：
- A) 寫在 `rewrite/tools/trip.py`（passenger_leave 旁邊）
- B) 寫在新檔 `rewrite/tools/leave.py`（跨表 wrapper 獨立）

建議 B，因為這個 wrapper 將來要長 fixed_schedules 路徑，獨立檔案語意更清楚。

測試方向（test_apply_leave.py）：
- T1: target_id 在 trips → 走 passenger_leave 成功
- T2: target_id 在 fixed_schedules → 回 fallback 訊息（不真的請假）
- T3: target_id 不存在 → fail
- T4: trips 路徑的鎖、累加、audit 等行為跟 passenger_leave 一致

---

## 9. 接下來要做的（按優先順序）

### Now：R-3 apply_leave（用戶當前指示）
- 寫 `rewrite/tools/leave.py` 的 `apply_leave` wrapper
- 寫 `rewrite/tools/test_apply_leave.py`
- commit「rewrite: R-3 統一請假介面 apply_leave（trips 路徑優先）」

### 第 4 批 — postback handler + LINE router 命令
- webhook 加 postback 路由
- 詳情卡按鈕真的能執行操作
- router 補命令：`班次請假 X 加成 原因` / `班次註銷 X` / `指派司機 X Y` 等
- 7 個 mutation 工具全部接到 LINE

### 補小工具（spec §3.1 還缺）
- `update_passenger_name`
- `record_fare_current`

### 第 5+ 批 — fixed_schedules（用戶先跳過）
- 等 trips 套件全套穩定再回頭
- 屆時 apply_leave 補完 fixed_schedules 路徑

---

## 10. 新對話開頭建議

```
（用戶說）
請讀 docs/logs/REWRITE_HANDOFF_2026-05-03.md 後接續。
git log -5 看最新 commit 確認進度。
```

或更精準：
```
請讀 docs/logs/REWRITE_HANDOFF_2026-05-03.md 後接續，
方向：R-3 apply_leave 還沒做的部分，
先 git log 看 R-3 是否有 commit 進來；
有 → 接第 4 批 postback handler；沒 → 寫 apply_leave。
```

---

## 11. 用戶相關記憶

- userId（測試用）：`U6b520261e9199a21d25e6d20509eda3f`
- 本地 DB：`postgres@localhost:5432/dispatch_db`
- Render DB：`RENDER_DB_HOST=dpg-cvhb...`（不要動）
- venv：`/Users/linyancui/minimal_flask/venv`
- 工作流：dev_line_channel 上重做、main 不動、最終切 Render

---

*v2 建檔者：Claude（接續第 2、3 批 + R-3 起點）*
*下一個 Claude：請繼續、不必重新介紹 — 進度看完直接做事即可*
