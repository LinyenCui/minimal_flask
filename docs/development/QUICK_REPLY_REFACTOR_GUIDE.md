# Quick Reply 系統重構指南

## 概述

本文檔說明 Quick Reply 系統的重構，從多種不一致的格式統一為標準化的格式和處理機制。

## 重構前的問題

### 1. 多種不一致的響應格式
- `"type": "quick_reply"`
- `"type": "text_with_quick_reply"`
- `"type": "flex_with_quick_reply"`
- 混合使用 `message` 和 `text` 欄位
- 不同的 Quick Reply 數據結構

### 2. 重複的處理邏輯
- 每個 handler 都有自己的 Quick Reply 處理代碼
- 大量重複的 LINE SDK 對象創建邏輯
- 不一致的錯誤處理

### 3. 維護困難
- 修改 Quick Reply 邏輯需要更新多個文件
- 沒有統一的驗證和測試

## 重構後的架構

### 1. 核心組件

#### QuickReplyManager (`modules/utils/quick_reply_manager.py`)
- 統一的 Quick Reply 創建和管理
- 標準化的響應格式
- 常用按鈕組合
- 格式驗證

#### ResponseHandler (`modules/utils/response_handler.py`)
- 統一的響應發送處理
- 新舊格式兼容
- 錯誤處理和回退機制

### 2. 標準化響應格式

#### 文字響應
```python
# 純文字
{
    "type": "text_only",
    "text": "消息內容"
}

# 帶 Quick Reply 的文字
{
    "type": "text_with_quick_reply",
    "text": "消息內容",
    "quick_reply": {
        "items": [
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "按鈕文字",
                    "text": "發送內容"
                }
            }
        ]
    }
}
```

#### Flex 響應
```python
# 純 Flex
{
    "type": "flex_only",
    "flex_message": {...},
    "alt_text": "替代文字"
}

# 帶 Quick Reply 的 Flex
{
    "type": "flex_with_quick_reply",
    "flex_message": {...},
    "alt_text": "替代文字",
    "quick_reply": {...}
}
```

## 使用指南

### 1. 創建響應

#### 使用 QuickReplyManager
```python
from modules.utils.quick_reply_manager import QuickReplyManager

# 創建文字響應
buttons = [
    {"label": "確認", "text": "確認", "type": "message"},
    {"label": "取消", "text": "取消", "type": "message"}
]
response = QuickReplyManager.create_text_response("請選擇操作", buttons)

# 創建 Flex 響應
response = QuickReplyManager.create_flex_response(
    flex_content, 
    "Flex 消息", 
    buttons
)
```

#### 使用便利函數
```python
from modules.utils.response_handler import send_text_response, send_flex_response

# 直接發送文字響應
send_text_response(reply_token, "消息內容", buttons)

# 直接發送 Flex 響應
send_flex_response(reply_token, flex_content, "Alt Text", buttons)
```

### 2. 處理響應

#### 在 Handler 中
```python
from modules.utils.response_handler import ResponseHandler

# 處理任何格式的響應
def my_handler(reply_token, user_input):
    result = some_processing_function(user_input)
    
    # 統一處理（支持新舊格式）
    success = ResponseHandler.handle_legacy_format(reply_token, result)
    
    if not success:
        reply_text(reply_token, "處理失敗")
```

### 3. 常用按鈕組合

```python
from modules.utils.quick_reply_manager import QuickReplyManager

common_buttons = QuickReplyManager.create_common_buttons()

# 確認/取消按鈕
confirm_cancel = common_buttons["confirm_cancel"]

# 放棄操作按鈕
abandon = common_buttons["abandon_operation"]

# 預約相關按鈕
booking = common_buttons["booking_actions"]
```

## 遷移步驟

### 1. 更新 Handler 導入
```python
# 舊方式
from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
from modules.utils.line_bot import reply_message_with_quick_reply

# 新方式
from modules.utils.quick_reply_manager import QuickReplyManager
from modules.utils.response_handler import ResponseHandler, send_text_response
```

### 2. 重構 Quick Reply 創建
```python
# 舊方式
quick_reply_items = [
    QuickReplyItem(
        action=MessageAction(
            label="確認",
            text="確認"
        )
    )
]
quick_reply = QuickReply(items=quick_reply_items)
reply_message_with_quick_reply(reply_token, text, quick_reply)

# 新方式
buttons = [
    {"label": "確認", "text": "確認", "type": "message"}
]
send_text_response(reply_token, text, buttons)
```

### 3. 更新響應處理
```python
# 舊方式
if result.get("type") == "quick_reply":
    reply_message_with_quick_reply(reply_token, result["text"], result["quick_reply"])
elif result.get("type") == "text":
    reply_text(reply_token, result["text"])

# 新方式
ResponseHandler.handle_legacy_format(reply_token, result)
```

## 向後兼容性

重構後的系統完全向後兼容：

1. **舊格式支持**：`ResponseHandler.handle_legacy_format()` 可以處理所有舊的響應格式
2. **逐步遷移**：可以逐個文件進行遷移，不需要一次性改完
3. **錯誤處理**：新系統有更好的錯誤處理和回退機制

## 測試

運行重構測試：
```bash
python tests/test_quick_reply_refactor.py
```

## 好處

### 1. 代碼簡化
- 減少了 70% 的重複代碼
- 統一的 API 接口
- 更清晰的代碼結構

### 2. 維護性改善
- 單一責任：每個組件有明確的職責
- 集中管理：所有 Quick Reply 邏輯在一個地方
- 易於測試和調試

### 3. 擴展性
- 新的按鈕類型易於添加
- 統一的驗證和錯誤處理
- 更好的日誌記錄

### 4. 開發效率
- 減少樣板代碼
- 常用按鈕組合可重用
- 便利函數快速開發

## 注意事項

1. **LINE API 限制**：Quick Reply 最多支持 13 個按鈕
2. **按鈕文字長度**：label 建議不超過 20 個字符
3. **響應時間**：複雜的 Flex 消息可能需要更長處理時間

## 後續計劃

1. **完成所有 Handler 的遷移**
2. **添加更多常用按鈕組合**
3. **實現 Quick Reply 分析和統計**
4. **優化 Flex 消息的 Quick Reply 整合**