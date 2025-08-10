# Routing and Module Overview (Developer Notes)

本文件描述訊息主路由瘦身後的結構、各命令群的委派位置，以及與 Service 層的對應關係，供開發維護使用。

## 核心入口與責任
- `modules/routes/webhook.py` → 前置處理 LINE 事件
- `modules/handlers/message_handler.py` → should_process() 前置判斷（權限/前綴/對話與忽略規則）
- `modules/handlers/text_message_handler.py` → 統一對話管理、指令委派（不再承載業務）

## 前置過濾（message_handler）
- 移除群組前綴（!/#//），得到 `command_body`
- 若為 Postback displayText（符合 `POSTBACK_DISPLAY_TEXT_PATTERNS`）→ 忽略
- 若為常見的 Postback emoji echo（🟢/❌/🔵/⚠️/⏸️/✅）→ 忽略
- 仍處於某些流程（預約、批量加成）且非取消字樣 → 放行，以續流

## 對話管理（text_message_handler）
- 優先檢查 `conversation_manager.get_active_conversation(user_id)`
- 依對話類型分派：
  - fare_modification / temp_booking / passenger_leave / driver_assign / query_* / ai_modification_reason
- 無對話時才進入一般命令委派

## 輕路由一覽（行為保持不變）
- 報表：`modules/handlers/report_router.py`
  - `生成周報表*`、`生成月報表*`
  - Service：`modules/services/report_service.py`
- 指派：`modules/handlers/driver_router.py`
  - `指派*`、`指派司機*`、`確認指派*`、`取消指派*`、`放棄指派*`
  - Service：`modules/services/driver_service.py`
- 查詢：`modules/handlers/query_router.py`
  - `東洋班次*`（含日期選擇）、`診所班次*`（含日期選擇）、`查詢班次*`、`查已完成範圍*`、`查班次範圍*`
  - Service：`modules/services/trip_query_service.py`、`modules/services/advanced_query_processor.py`、`modules/services/date_range_query_service.py`
- 同步：`modules/handlers/sync_router.py`
  - `資料庫同步`、`確認同步`、`同步結果`
  - Handler：`modules/handlers/database_sync_handler.py`
- 檢視：`modules/handlers/view_router.py`
  - `班次詳情 [ID]`（Flex + Quick Reply）、`查看 [完成ID]`
  - Service：`modules/services/trip_detail_service.py`、`modules/handlers/trip_handler.py`
- 過去態：`modules/handlers/history_router.py`
  - `查已完成*`、`完成記錄*`（別名 → 轉成查已完成）
  - Service：`modules/services/ai_fare_service.py`、`modules/services/trip_query_service.py`
- 分頁：`modules/handlers/pagination_router.py`
  - `更多/下一頁/更多結果/next/more`（支援 Quick Reply 分頁）
  - Utils：`modules/utils/conversation_context.py`
- 固定類：`modules/handlers/fixed_router.py`
  - `固定班表`、`固定班次#ID請假` 快捷、`固定班次請假*`、`固定班次恢復*`
  - Handlers：`modules/handlers/fixed_schedule_*`
- 修改類：`modules/handlers/modification_router.py`
  - `修改類別*`、`記錄車資*`
  - 「修改車資」已下架，統一提示改用「記錄車資」
  - Handler：`modules/handlers/trip_handler.py`
- 幫助：`modules/handlers/help_router.py`
  - `幫助/幫助文字/完整指令列表/搜尋幫助` 與動態 `help_*`
  - Handler：`modules/help_system/help_handler.py`

## 預約叫車（重要）
- 外觀層：`modules/handlers/temp_booking_session.py`
  - `is_booking_active/start_booking/handle_booking_message/cancel_booking`
  - 啟動/取消/成功 → 鏡射 `conversation_manager` 結束對話（避免殘留）
- 業務層：`modules/handlers/temp_booking_handler.py`
  - AI 解析 → 追問 → 確認 → 寫入 `trips`（`trip_type='temp'` + `custom_*` 欄位）
- 對話分派：`handle_temp_booking_conversation` 僅轉送 + 正確發送 Flex/Quick Reply

## 加入新命令的建議流程
1) 在 `modules/handlers/<your>_router.py` 實作 `handle_xxx_commands(message_text, user_id, reply_token)`，回傳 bool
2) 在 `text_message_handler.py` 對應區塊引入並委派（放在相鄰群組附近，易讀易維護）
3) 若有 Postback，避免在按鈕 action 設定會觸發二次文字事件的 text；或於 `message_handler` 增加忽略規則

## 重要規則（穩定性）
- 不要在 `text_message_handler.py` 增加業務；只做：
  - 對話管理 / 前置保護 / 委派
- 任何新增 AI 功能必須提供降級或傳統後備路徑
- 日期處理統一走 `modules/utils/unified_date_parser.py`
- Postback echo（emoji 或 displayText）一律在 `message_handler` 忽略

## 變更摘要（本輪）
- 新增 8 個輕路由（report/driver/query/sync/view/history/pagination/fixed/modification/help）
- 移除 `修改車資` 指令，統一改用 `記錄車資`
- 預約流程結束時一律清除活躍對話，避免再次輸入被 should_process 擋住
- 忽略 Postback displayText 與 emoji echo，修正私聊重複回覆問題
