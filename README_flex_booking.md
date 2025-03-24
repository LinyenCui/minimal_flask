# 預約功能 Flex Message 實現說明

## 概述

本文檔說明了使用LINE Flex Message實現預約功能的設計和實現方法。Flex Message提供了更豐富的視覺呈現和交互方式，使預約流程更加直觀和用戶友好。

## 文件結構

- `booking_flex_design.py`: 包含所有Flex Message模板的設計
- `handle_booking_flex.py`: 包含處理預約流程的邏輯

## 預約流程

預約功能分為以下幾個步驟：

1. **開始預約**: 用戶輸入「預約」命令，系統顯示日期選擇界面
2. **選擇日期**: 用戶可以選擇今天、明天、後天或輸入其他日期
3. **選擇時間**: 用戶可以從常用時間中選擇，或輸入自定義時間
4. **輸入起點**: 用戶可以從常用地點中選擇，或輸入自定義地點
5. **輸入途經點**: 用戶輸入途經點（可選）
6. **輸入終點**: 用戶輸入終點（可選）
7. **確認預約**: 系統顯示預約信息，用戶確認或取消
8. **預約成功**: 系統顯示預約成功信息，包括班次ID和詳細信息

## Flex Message 設計

### 1. 日期選擇界面

- 顯示今天、明天、後天的日期按鈕
- 提供「選擇其他日期」選項
- 顯示當前預約類別

### 2. 時間選擇界面

- 顯示常用時間段的按鈕網格
- 提供輸入自定義時間的提示
- 顯示已選擇的日期

### 3. 地點選擇界面

- 顯示常用地點的列表
- 提供輸入自定義地點的提示
- 顯示已選擇的日期和時間

### 4. 預約確認界面

- 顯示所有預約信息（日期、時間、起點、途經點、終點、類別）
- 提供確認和取消按鈕

### 5. 預約成功界面

- 顯示班次ID和所有預約信息
- 顯示班次狀態（待派）
- 提供查詢班次按鈕

## 狀態管理

預約流程使用`booking_states`字典來管理用戶的預約狀態，包括：

- `state`: 用戶當前的狀態（例如：'booking'）
- `step`: 預約流程的當前步驟（例如：'date', 'time', 'start_point'等）
- `data`: 已收集的預約數據

## 錯誤處理

- 每個步驟都有輸入驗證，確保數據格式正確
- 提供友好的錯誤提示，指導用戶輸入正確的格式
- 在發生異常時清除用戶狀態，避免卡在錯誤的狀態中

## 使用方法

1. 將`booking_flex_design.py`和`handle_booking_flex.py`添加到項目中
2. 在`app.py`的`handle_text_message`函數中添加對「預約」命令的處理
3. 使用`handle_booking_start`函數開始預約流程
4. 使用`handle_booking_message`函數處理預約過程中的消息

## 示例代碼

```python
# 在handle_text_message函數中添加
elif message_text.strip() == "預約":
    try:
        from handle_booking_flex import handle_booking_start
        bubble, error_message = handle_booking_start(user_id, category="診所")
        if bubble:
            flex_message = FlexMessage(alt_text="預約班次", contents=FlexContainer.from_dict(bubble))
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[flex_message]
                )
            )
            return
        elif error_message:
            reply_text = error_message
    except Exception as e:
        reply_text = f"處理預約命令時出錯: {str(e)}"

# 在handle_text_message函數開頭添加
# 檢查用戶是否在預約流程中
if user_id in booking_states and booking_states[user_id]["state"] == "booking":
    try:
        from handle_booking_flex import handle_booking_message
        bubble, text_message = handle_booking_message(user_id, message_text)
        if bubble:
            flex_message = FlexMessage(alt_text="預約班次", contents=FlexContainer.from_dict(bubble))
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[flex_message]
                )
            )
            return
        elif text_message:
            reply_text = text_message
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
            return
    except Exception as e:
        reply_text = f"處理預約消息時出錯: {str(e)}"
        # 清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
```

## 注意事項

1. 確保Flask應用上下文在數據庫操作時可用
2. 測試所有可能的用戶輸入路徑，確保錯誤處理正確
3. 考慮添加超時機制，避免用戶長時間不回應導致的資源佔用
4. 未來可以考慮添加更多視覺元素，如顏色編碼和圖標，提升用戶體驗

## 未來擴展

1. 添加更多預約類別的選擇
2. 實現預約修改和取消功能
3. 添加司機指派通知
4. 與AI自然語言處理集成，支持更自然的對話式預約 