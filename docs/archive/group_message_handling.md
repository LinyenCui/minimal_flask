# 群組消息處理功能說明

## 功能概述

1. 在群組中，機器人只回應帶有特定前綴的消息
2. 預約功能僅在私聊中可用
3. 其他功能（如查詢、幫助等）在群組和私聊中都可用

## 實現方式

### 1. 消息前綴處理
- 支持的前綴：`!`、`#`、`/`
- 示例：
  - `!預約` -> 提示使用私聊
  - `!查詢` -> 正常處理查詢命令
  - `!幫助` -> 顯示幫助信息

### 2. 預約功能限制
- 在群組中嘗試使用預約功能時，返回提示消息
- 引導用戶使用私聊進行預約

### 3. 代碼實現
```python
def handle_text_message(event):
    """處理文本消息"""
    message_text = event.message.text
    user_id = event.source.user_id
    reply_token = event.reply_token
    source_type = event.source.type
    
    # 如果是群組消息，檢查是否需要處理
    if source_type == 'group':
        # 如果不是以特定前綴開頭，直接返回
        if not (message_text.startswith("!") or 
                message_text.startswith("#") or 
                message_text.startswith("/")):
            return
            
        # 去除前綴
        message_text = message_text[1:].strip()
        
        # 如果是預約相關命令，返回提示
        if message_text in ["預約", "東洋預約"]:
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="預約功能僅支持在私聊中使用。\n請私聊機器人進行預約。")]
                )
            )
            return
```

## 注意事項

1. 不要修改 `callback` 函數，它是基礎的消息接收入口
2. 保持現有的 SDK 初始化方式不變
3. 確保其他功能（如查詢、幫助等）在去除前綴後能正常工作
4. 在返回提示消息後要及時 return，避免繼續處理

## 測試要點

1. 在群組中測試：
   - 無前綴消息應該被忽略
   - 帶前綴的預約命令應該返回提示
   - 帶前綴的其他命令應該正常工作

2. 在私聊中測試：
   - 所有功能應該正常工作
   - 不需要使用前綴

## 後續優化建議

1. 可以考慮將前綴設置為可配置項
2. 可以添加群組特定的功能
3. 可以為不同群組設置不同的權限 