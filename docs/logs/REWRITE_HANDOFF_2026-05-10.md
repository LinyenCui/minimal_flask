# Rewrite v0.1 → 推上 Render Handoff（v6 / 完工版）

> **日期**：2026-05-10
> **里程碑**：Phase A + B + C 全部完成，rewrite 取代 legacy 上 prod
> **main HEAD**：`3f0e6eb`（merge）／ rewrite tip = `722f712`

---

## TL;DR

**搬遷已完成**。從 main `9150147` 起算共 77 個 commit，把 ~25,000 行 legacy 業務代碼換成 ~3,200 行 rewrite 沙盒架構（純函數 atomic tools + AI skill agent + LIFF 表單）。Render 上跑的就是這版。

剩下都是**功能精進跟 bug 修補**，不再有大規模搬遷。

---

## 現在系統長相（Phase D 完工後）

### 架構

```
LINE Webhook (/callback)
    │
    ├─ 私聊 (user)        → 不需前綴，全收
    ├─ 群組 (group/room)  → 必須 / 開頭，否則跳過
    │                       例外：rewrite-active state 不需前綴（多輪對話 / Quick Reply）
    │
    ↓ (處理順序)
    │
    1. rewrite/router.try_route        — 快速命令（exact match，無 AI 成本）
    │   查客戶 / 客戶詳情 / 病歷層 / 診所班次 / 東洋班次 /
    │   班次詳情 / 待派班次 / 班次註銷 / 班次衝突 / 班次請假 / 班次恢復
    │
    2. rewrite/handlers/sandbox_handler.try_handle_sandbox
    │   ├─ exact-match LIFF triggers
    │   │   新增客戶 / 預約叫車 / 匯入固定班次 / 新增固定班次 /
    │   │   生成週/月報表 / 帳務處理 / 批量加成
    │   ├─ exact-match flows
    │   │   幫助、查看明細、acct_ledger_*（cursor pagination）、
    │   │   資料庫同步（橋接 legacy database_sync_handler）、結束對話
    │   ├─ regex flows
    │   │   「[date][location]的狀態」 → status picker + 批次 leave/cancel/conflict/restore
    │   │   多輪對話 follow-up parser
    │   └─ AI agent classifier → 5 個 skill 之一
    │       trip_query / trip_mutation / completed_trip / customer / fixed_schedule
    │
    3. unknown 友善 fallback：「🤔 不太懂這個訊息，輸入「幫助」看可用指令」
       （不再 fall-through legacy — Phase C 砍光了）
```

### 5 個 Skill（rewrite/ai/skills/）

| Skill | 對應 atomic tools | 觸發例 |
|---|---|---|
| `trip_query` | trip 查詢類 4 個 | 今天診所班次、查班次、待派 |
| `trip_mutation` | passenger_leave / cancel_trip / mark_conflict / restore_to_ready / assign_driver / unassign_driver / record_fare_current / update_passenger_name / update_trip_category | 1234 化療 -30、註銷 1234、指派司機 1190 28530 |
| `completed_trip` | query_completed_trips / aggregate / update_fare / update_category / update_driver / sun_week_info | 查已完成、本週統計、修車資、改類別、改司機 |
| `customer` | query_customer_by_term / get_by_id / by_birthday_day / create / update / delete | 查太子龍、病歷層 15、新增客戶 |
| `fixed_schedule` | query / create / update / leave / restore | 太子龍的固定班次、固定班次14請假 |

### LIFF 表單（rewrite/handlers/liff/）

單一 LIFF App + dispatcher pattern（用 `?form=xxx` query 路由）：

| Form | 用途 |
|---|---|
| customer | 新增 / 編輯客戶（仿 booking_form 折疊樣式：4 必填 + 2 顯示 + 3 折疊） |
| booking | 預約叫車 |
| import | 匯入固定班次 |
| fixed_schedule | 新增 / 編輯 / 請假 固定班次 |
| report | 生成日報 / 週報 / 月報 |
| accounting | 帳務處理（記錄入金 + 上週扣款） |
| batch_allowance | 批量加成（颱風假等批量調整） |

prod LIFF：
- LIFF_ID = `2010013922-msGhDtjW`
- LIFF_CHANNEL_ID = `2010013922`
- Endpoint URL = `https://minimal-flask.onrender.com/liff/customer/form`

### 保留的 admin / framework handlers（非業務）

```
modules/handlers/
  database_sync_handler.py   admin: Render → 本地 同步
  sync_handler.py            admin
  sync_router.py             admin（sandbox 橋接這個）
  sequence_fix_handler.py    admin: 修 DB sequence
  cleanup_handler.py         admin: 系統清理
  diagnosis_handler.py       診斷碼系統（未進 rewrite）
  location_message_handler.py 處理 LINE 位置訊息
  image_message_handler.py   處理 LINE 圖片訊息（拍處方箋）
```

```
modules/services/
  ai_service.py              Vertex AI 初始化
  ai_service_enhanced.py     image_message_handler 用
  scheduler_service.py       背景排程（班次掉到 completed）
  incremental_sync_service.py
  report_service.py          rewrite/tools/report.py 用這個
  driver_service.py          rewrite/tools/trip 用這個
  diagnosis_query_service.py
  + location 相關 (geo / distance / clinic / arrival_template / chat_settings / group_location_meta / provider_factory)
  + drive_service.py (report_service 用)
```

---

## 三時間態仍是核心（沒變）

| 時間態 | 表 | rewrite 對應 |
|---|---|---|
| 未來態（模板）| fixed_schedules | tools/fixed_schedule.py + skills/fixed_schedule.py |
| 現在態（生產線）| trips | tools/trip.py + skills/trip_query/trip_mutation |
| 過去態（成品）| completed_trips | tools/completed_trip.py + skills/completed_trip |

「請假三層障眼法」維持原設計：status='準備'，passenger_leave_reason 記原因。

---

## 太陽週（業務週定義）

⚠️ **嚴禁用 ISO 8601（週一起算）**：

- 太陽週 = 星期日 ~ 星期六
- 週號用 `strftime('%U')`
- AI 必須先 call `sun_week_info` atomic tool 拿 dates，**不可自己算**（LLM 預設 ISO 會錯一天）

詳見 `rewrite/utils/sun_week.py`。

---

## 工作流規矩（這次違反了，下次嚴格遵守）

1. **改動先 dev_line_channel** → 用戶 Mac + ngrok 跑順了沒問題 → **用戶**才推 main → Render auto-deploy。Claude 不要直接推 main。
2. **不退回 legacy fallback**：rewrite 取代 legacy 是大方向，AI 行為差就改 AI prompt / 加更多 atomic tool 的 examples，不是再加一條繞過 AI 的 deterministic regex。
3. **砍 legacy 前先 git show main 確認原版功能**：避免 reimplementation 漏功能（這次帳戶明細第一版漏了 running_balance 跟 cursor pagination）。
4. **驗證原則**：每個 commit 都跑 6/6 regression（test_completed_trip / test_completed_trip_mutations / test_trip / test_customer / test_trip_flex_pagination / test_multi_skill），實機驗 OK 才 commit。

---

## 部署環境

```
prod  Render「minimal_flask」 service
       https://minimal-flask.onrender.com
       branch: main
       env: LIFF_ID + LIFF_CHANNEL_ID + LINE_CHANNEL_* + DATABASE_URL +
            GCP_* + GOOGLE_APPLICATION_CREDENTIALS + TZ
       Provider「小黃Bot」prod / Channel「Linyan」(messaging) + 派班liff (login)

dev   Mac local + ngrok
       branch: dev_line_channel
       .env (base) + .env.dev (override LIFF / dev channel / localhost DB)
       Provider「小黃Bot」dev / 派班liff（login + LIFF）
```

---

## 已知未做（功能精進方向）

從 prod 用戶實機驗的 feedback：

1. **AI 對 mutation 命令偶爾只 query 不執行** — 已在 trip_mutation skill prompt 加「執行優先」原則（`722f712`），實機驗證中
2. **帳戶明細 carousel 上限 84 筆**（12 bubbles × 7 列）— 超過要靠「篩選區間」縮範圍。LIFF 版本待考慮
3. **指派司機需要記司機 ID** — 用戶想要 picker UX 但要符合「不退回 legacy」原則，可能改成 AI 自然語言「派車況最閒的」這類智能化
4. **diagnosis 模組未進 rewrite** — 評估後保留 legacy 不動（獨立模組）
5. **image_message_handler 未進 rewrite** — 拍處方箋自動建預約功能保留

---

## 已知 bug（小）

1. （commit `f70fb6b` 已修）`sun_week_info` 對 AI 傳 str 參數會炸 weekday — 已 coerce
2. （pending）「指派司機 N M」AI 偶爾只查不做 — prompt 已強化（`722f712`），需再驗

---

## 統計

```
從 main 9150147 起算：
  77 個 commit
  ~25,000 行 legacy 業務代碼砍掉
  ~3,200 行 rewrite 結構（atomic tools + skills + views + LIFF）
  6/6 regression 全綠
  prod 實機驗（陸續發現的 bug 都已 hotfix）
```

---

## 下一個對話該知道的

1. **本檔（v6）+ 之前的 v3 ~ v5（docs/logs/REWRITE_HANDOFF_*.md）**：完整脈絡
2. **CLAUDE.md**：核心設計原則 + 三時間態 + 太陽週
3. **MEMORY.md**（user-level）的工作流 + bloat / legacy 警示
4. **現在主要工作**：功能精進 + bug 修補。**不再有大規模搬遷**。動手原則：
   - 改 prompt 比加 deterministic regex 優先
   - 改動先 dev_line_channel，本地 ngrok 驗 OK 再請用戶推 main
   - 加新 atomic tool 是 OK 的（如 update_completed_trip_driver），但 LINE 整合層保持輕薄
5. **遇到 prod bug**：通常是 AI 行為問題 → 改 skill system_prompt / atomic tool docstring 加 examples / 加更明確的觸發詞解釋
