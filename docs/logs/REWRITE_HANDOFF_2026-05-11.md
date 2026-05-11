# Rewrite Handoff v7 — 2026-05-11

> v6（2026-05-10）後一天內密集修了 11 個 commits，涵蓋 LIFF 全鏈路群組廣播、查詢遺漏、跨對話 state leak、PC LIFF 認證等。本文檔記錄這波修補的全貌與目前系統狀態。

---

## 0. TL;DR

v6 完工後，用戶反映「LIFF 在群組裡按完都推給操作者私聊不推群組」。從這條問題抽絲剝繭，挖出 **6 個獨立 bug**，全部修完：

1. LIFF SDK 的 `getContext().groupId` 是 UUID 不是 LINE 平台 ID → 全鏈路重做 source 傳遞
2. Bubble 上的編輯按鈕沒帶 source → 編輯後 push 退回個人
3. 群組裡 Flex/quickReply 按鈕 callback 沒 `/` 前綴被 webhook 擋
4. via_point '+'-joined 多段途經查不到（4 處查詢 SQL）
5. 私聊 active state 跨到群組，閒聊被當 bot 訊息
6. PC 版 LINE 開 LIFF 全 400（OAuth2 redirect_uri 不符 Callback URL 白名單）

**業務面成果**：群組裡 LIFF 操作（匯入 / 新增客戶 / 預約 / 編輯 / 報表 / 帳務）結果都會推回原群組，全成員可見。

---

## 1. 這波 commits 時間軸（v6 → v7）

```
b3d23e0 [v6 baseline] docs: handoff v6 + CLAUDE.md
        ─── 用戶開始實測 ───

cf6d738 feat(liff/import): 群組廣播第一版（用 liff.getContext()）
f341e65 debug: 加 broadcast log 抓 LINE 400 "to invalid"
d32e7c7 fix(liff/import): 從 webhook 拿真 groupId 塞 URL ★ root cause 定位
07dbea4 fix(liff): customer/booking 套同套修法
e499e67 fix(liff): 系統性修全鏈路（7 entry + 3 detail + 6 template + 6 backend）
a8b548b fix(liff/customer): push bubble 也要把 source 給 render
96fcb28 debug(liff/customer): submit 加 stage debug
e49ec25 fix(webhook/group): 群組按鈕 callback 被擋
5218ec3 fix(query): via_point '+'-joined 查不到
72f04a1 fix(state): cross-channel state leak
a64fa73 fix(liff): PC 開 LIFF 400 — redirectUri 改 LIFF URL
```

每個 commit 都本機 dev_line_channel 驗過才 merge main。

---

## 2. LIFF 群組廣播全鏈路（核心修補）

### 2.1 根因
LIFF SDK 的 `liff.getContext().groupId` 回傳的是 **LIFF-internal UUID**（如 `3677e217-8619-445a-b8b1-604e02c2cfa3`，36 字元），**不是** LINE Messaging API 認的 33 字元平台 ID（`C` + 32 hex）。

用 UUID 當 `to` 去 `pushMessage` 一律回：
```json
{"message": "The property, 'to', in the request body is invalid"}
```

### 2.2 修法（單方向資料流）

```
webhook event.source.group_id (真 groupId)
   ↓
Pattern A: entry render — build_liff_url(event_source) 把 gid 塞進 URL
Pattern B: detail render — 編輯/請假按鈕也走 build_liff_url
   ↓
LIFF URL: https://liff.line.me/{LIFF_ID}?form=xxx&gid=Cxxx
   ↓
LIFF template submit 時讀 URL params 把 source 放進 payload
   ↓
backend handler 用 resolve_push_target(body['source'], fallback_user_id)
   ↓
push 到正確的 group/room/user
```

### 2.3 涵蓋範圍

**Pattern A — 觸發詞 → quick reply 開 LIFF**（7 個）：
- `render_new_customer_entry`
- `render_booking_entry`
- `render_import_entry`
- `render_new_fixed_schedule_entry`
- `render_report_entry`
- `render_batch_allowance_entry`
- `render_accounting_menu`（deposit + weekly_payment 兩個按鈕）

**Pattern B — Flex bubble 上的 LIFF 按鈕**（3 個 renderer）：
- `render_customer_detail` — 編輯按鈕
- `render_fixed_schedule_detail` — 編輯 + 請假按鈕
- `render_fixed_schedule_list_carousel`

**call sites — 傳 event.source 給 renderer**：
- `rewrite/handlers/sandbox_handler.py` — 7 處 entry render + agent.process
- `rewrite/router.py` — `_handle_customer_detail` / `_handle_customer_query`
- `rewrite/ai/agent.py` — process / `_chat_with_tool_loop` / `_render_result`

**LIFF templates — 讀 URL params 塞 payload.source**（10 個）：
- customer / booking / import / fixed_schedule / fixed_schedule_leave
- report / deposit / weekly_payment / batch_allowance / whoami_test

**LIFF backends — push 走 `resolve_push_target`**（7 個檔案，8 個 endpoint）：
- customer.py: create / update
- booking.py: create
- import_form.py: execute
- fixed_schedule.py: create / update / leave
- report.py: generate
- accounting.py: deposit / weekly_payment
- batch_allowance.py: execute

### 2.4 共用工具：`rewrite/utils/liff_url.py`

```python
def build_liff_url(liff_id, form, event_source=None, *, extra_params=None) -> str:
    """組 LIFF URL，把 webhook event.source 的 group/room 抓進 query。
    
    支援 event.source 是 webhook obj（snake_case 屬性）或 LIFF payload dict（camelCase keys）。
    extra_params 給 customer_id / id 之類額外參數用。
    """

def resolve_push_target(payload_source, fallback_user_id) -> str | None:
    """從 LIFF payload 的 source dict 決定 push 目標。
    群組/聊天室優先，否則退回 user_id。"""
```

加新 LIFF 流程要遵守的約定（**重要！**）：
1. render entry / detail 簽名加 `event_source=None`
2. 呼叫 render 的地方（sandbox_handler / router / agent）傳 `event.source`
3. LIFF template 在 submit 前讀 `URLSearchParams` 的 `gid`/`rid` 塞 `payload.source`
4. LIFF backend 用 `resolve_push_target(body['source'], request.line_user_id)` 決定 push 目標
5. URL 一律用 `build_liff_url(_liff_id(), 'form_name', event_source)` 組

---

## 3. 群組裡 Flex 按鈕 callback 解禁

### 3.1 症狀
群組裡按 Flex bubble 上的「↩️ 恢復」「❌ 註銷」按鈕，按完沒反應。

### 3.2 根因
這些按鈕送出的文字（`type='message'`）沒 `/` 前綴，被 webhook 的群組過濾擋掉：
```
Skip group non-/ message: '固定班次恢復 29'
```

### 3.3 修法
1. 補齊 `_QUICK_COMMAND_PREFIXES`（在 `rewrite/handlers/sandbox_handler.py`），加入 8 個遺漏的 callback prefix：
   ```python
   '固定班次恢復',         # fixed_schedule_flex「↩️ 恢復」
   '查看 ',                # completed_trip_flex「#N 詳情」
   'acct_ledger_start',    # accounting_flex「📒 查看明細」
   'acct_ledger_range',    # accounting_flex「篩選區間」
   'acct_ledger_next:',    # accounting_flex 翻頁 payload
   '帳務處理',             # accounting_flex「回帳務處理」
   '結束對話',             # 各處對話 cancel
   '放棄操作',             # router.py 取消
   ```

2. webhook 群組過濾改用 `looks_like_quick_command` 判斷（**不只 sandbox-active state 期間用**），讓按鈕 callback 永遠通過。

### 3.4 加新按鈕的約定
之後加新 Flex/quickReply 按鈕 → 把 callback text 的前綴加到 `_QUICK_COMMAND_PREFIXES`。

---

## 4. via_point '+'-joined 多段途經查詢

### 4.1 症狀
「明天新建路的狀態」找不到班次，但 DB 裡明明有：
- `#1442 via='中華南路+新建路'`
- `#1450 via='新建路+中華南路'`

### 4.2 根因
`via_point` 用 `+` 串連多段途經（24 筆現存資料都是這樣），但查詢 SQL 用 `exact match`：
```sql
via_point = :sn
```
只能命中單值 via_point，含 `+` 的全部漏掉。

### 4.3 修法（4 處同步修）
`start/end` 仍 exact（24 筆資料 0 筆有 `+`），`via` 改 `string_to_array` 拆 `+`：
```sql
(start_point = :sn OR end_point = :sn
 OR :sn = ANY(string_to_array(COALESCE(via_point, ''), '+')))
```

涵蓋：
- `rewrite/tools/trip.py:query_trips` — 用戶踩到的
- `rewrite/tools/completed_trip.py:query_completed_trips`
- `rewrite/tools/fixed_schedule.py:query_fixed_schedule`
- `rewrite/tools/customer.py:delete_customer` 的 FK ref 檢查（隱性 bug：原本誤判沒人引用 → 允許刪客戶 → 班次孤兒）

---

## 5. Cross-channel state leak

### 5.1 症狀
用戶在私聊跟 bot 對話完，切到群組正常聊天，群組裡所有不帶 `/` 的訊息（如「這樣是我的問題囉～」「從這裡往下數看看」）都被當 bot 訊息處理，bot 跑 AI classifier 回 unknown fallback。

### 5.2 根因
`conversation_state` 用 `user_id` 為 key（per-user 不分對話），webhook 用「state in active_types」條件 bypass `/` 前綴規則時沒檢查 state 是不是在同個對話設的 → 跨頻道洩漏。

### 5.3 修法
- `set_state(user_id, type, payload, ttl_minutes=None, chat_id=None)` 加 `chat_id` 參數
- 新增 `get_chat_id_from_event(event)` helper：抽 `group_id` / `room_id` / `user_id`（看 source 類型）
- 所有 5 處 `set_state` 呼叫都帶 `chat_id`
- webhook 群組過濾條件多比對：`state.chat_id == current_event.chat_id` 才 bypass

副作用：v0.1 啟動前殘留的舊 state 沒 `chat_id` → 全部不 bypass。沒關係，重啟就清光（in-memory）。

---

## 6. PC 版 LINE 開 LIFF 400

### 6.1 症狀
PC 用戶按 quick reply 開任何 LIFF 表單 → LINE OAuth2 直接 400：
```
https://access.line.me/oauth2/v2.1/error400?error=Bad%20Request&
error_description=invalid url. channelId=2009974915,
redirectUriString=https://我們網域/liff/report/form?form=report&gid=...
```

手機完全不受影響（手機 LIFF 走 LINE app 內 SSO 不過 OAuth2）。

### 6.2 根因
所有 LIFF template 都這樣寫：
```js
liff.login({ redirectUri: window.location.href });
```

`window.location.href` 是 form 完整 URL（含我們 backend 域名 + query）。LIFF SDK 在 PC 端把這字串**原樣**當 OAuth2 redirect_uri。LINE OAuth2 比對 channel 的 Callback URL 白名單：白名單裡只有 `https://liff.line.me/{LIFF_ID}` → base 不符 → 400。

### 6.3 修法
10 個 template 的 `liff.login` 全改：
```js
liff.login({ redirectUri: 'https://liff.line.me/' + LIFF_ID + window.location.search });
```

- base 換成 `liff.line.me`（白名單 base 相符 → OAuth2 過）
- `window.location.search` 把 query 帶過去（回來時 dispatcher 才能路由到正確的 form）

---

## 7. 部署架構（dev / prod 分離）

兩組獨立的 LINE channel pair：

| Pair | LINE Login channel | Messaging API channel | LIFF Endpoint | Bot 跑在 |
|---|---|---|---|---|
| **dev** | 派班liff | 小黃機器人 | ngrok 網域 `/liff/customer/form` | Mac + ngrok（dev_line_channel 分支）|
| **prod** | 派班記帳liff | Linyan | Render 網域 `/liff/customer/form` | Render（main 分支）|

兩組環境變數獨立：`LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` / `LIFF_ID` / `LIFF_CHANNEL_ID` 在本地 `.env` 跟 Render env vars 各填各的。

**工作流程約定（嚴格遵守）**：
1. 所有改動先在 `dev_line_channel` 分支
2. 本地 Mac + ngrok 連 dev pair 驗證
3. 驗 OK 才 `git checkout main && git merge dev_line_channel --no-ff && git push origin main`
4. 推完切回 `dev_line_channel`

---

## 8. LIFF 表單清單

10 個 LIFF templates，dispatcher 是 `/liff/customer/form?form=xxx`：

| form 參數 | template | backend endpoint | 用途 |
|---|---|---|---|
| `customer`（預設）/ 帶 `customer_id` | customer_form.html | `/liff/customer` | 新增 / 編輯客戶 |
| `booking` | booking_form.html | `/liff/booking` | 預約叫車 |
| `import` | import_form.html | `/liff/import` | 匯入固定班次 |
| `new_schedule` | fixed_schedule_form.html | `/liff/fixed_schedule` | 新增固定班次 |
| `edit_schedule&id=N` | fixed_schedule_form.html | `/liff/fixed_schedule/{id}` | 編輯固定班次 |
| `leave_schedule&id=N` | fixed_schedule_leave_form.html | `/liff/fixed_schedule/{id}/leave` | 長期請假 |
| `report` | report_form.html | `/liff/report` | 生成日 / 週 / 月報表 |
| `deposit` | deposit_form.html | `/liff/accounting/deposit` | 記錄入金 |
| `weekly_payment` | weekly_payment_form.html | `/liff/accounting/weekly_payment` | 記錄週扣款 |
| `batch_allowance` | batch_allowance_form.html | `/liff/batch_allowance` | 批量加成 |
| — | whoami_test.html | — | 診斷用（測 idToken）|

每個 template 共通結構：
- `_safeIdToken()` 清 idToken 髒字元（防 iOS LIFF SDK bug）
- `liff.login({redirectUri: 'https://liff.line.me/' + LIFF_ID + window.location.search})` — PC OAuth2 過白名單
- submit 時讀 URL params 的 `gid`/`rid` 塞 `payload.source`

---

## 9. AI Skill 架構（無變動）

5 個 skills（`rewrite/ai/skills/`）：
1. `trip_query` — 現在態查詢
2. `trip_mutation` — 現在態狀態變更
3. `completed_trip` — 過去態
4. `fixed_schedule` — 未來態
5. `customer` — 客戶管理

Agent loop：intent classifier → skill → multi-turn tool loop → render result

---

## 10. 已知問題 & 後續工作

### 🟢 已解決（v7）
- ✅ LIFF 群組廣播全鏈路
- ✅ 群組按鈕 callback 被擋
- ✅ via_point '+'-joined 查詢
- ✅ Cross-channel state leak
- ✅ PC LIFF 400

### 🟡 待觀察 / 未來工作
- **Vertex AI deprecation warning**：使用的 SDK 在 2026-06-24 後棄用，要評估遷移到新 SDK
- **ngrok URL 不穩定**：每次重開 ngrok URL 改變，dev pair 的 LIFF Endpoint URL 要手動更新（free tier 限制）
- **狀態 5min TTL 偶爾太短**：複雜對話可能逾時，視情況調整
- **LIFF Endpoint URL 與 Callback URL 的設定**：目前 Callback URL 是 LINE 自動填的 `liff.line.me/{LIFF_ID}`，沒設過其他 URL；若未來想做標準 OAuth2 web login（非 LIFF），會需要另外設

### 🔴 P0 重構（從 CLAUDE.md 移過來，仍未做）
- `modules/handlers/text_message_handler.py`（1027 行）— Phase C 後可考慮刪 legacy（rewrite 已不 fall-through）
- `modules/services/smart_assistant.py`（1502 行）— 同上
- `modules/services/ai_fare_service.py`（1639 行）— 同上

---

## 11. 給下一個對話 Claude 的提醒

1. **改動先 dev_line_channel，本地驗 OK 才推 main**（用戶嚴格要求）
2. **不退回 legacy fallback**（要改 AI prompt，不要加 deterministic regex bypass）
3. 加新 LIFF 流程一定要照 §2.4 的 5 條約定
4. 加新 Flex/quickReply 按鈕記得在 §3.3 的 `_QUICK_COMMAND_PREFIXES` 補上 callback prefix
5. 任何查詢涉及 `start_point/via_point/end_point` 時，注意 `via_point` 可能是 `+`-joined（§4.3 模板）
6. 設 active state 一律帶 `chat_id`（§5.3）

---

## 附錄：commit 對照表

```
v6 baseline: b3d23e0 docs: handoff v6
v7 baseline: 2e05a26 merge: 修 PC 版 LIFF 400

v6 → v7 共 11 個功能 commit + 4 個 merge commit
```

**LIFF 群組廣播相關**：
- cf6d738 / f341e65 / d32e7c7 / 07dbea4 / e499e67 / a8b548b / 96fcb28

**其他 fix**：
- e49ec25（群組按鈕 callback）
- 5218ec3（via_point '+'-joined）
- 72f04a1（cross-channel state leak）
- a64fa73（PC LIFF 400）
