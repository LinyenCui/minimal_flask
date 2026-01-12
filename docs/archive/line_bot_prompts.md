# LINE Bot 提示詞記錄

## 群組和私聊的消息處理方案

### 問題背景
1. 原始情況：
   - 群組中需要 @bot 才會回應
   - 但使用 Flex Message 和懸浮選單時，每次都 @bot 很不實際
   - 私聊中可以直接使用所有功能

2. 需求：
   - 群組中改用前綴（!、#、/）觸發，不需要 @bot
   - 私聊中保持直接使用的方式
   - Flex Message 和懸浮選單在兩種場景都要能正常使用
   - 預約功能只在私聊中可用
   - **按鈕點擊時無需使用前綴（即便是在群組中）**

### 優化解決方案
1. 在消息處理的入口處進行場景區分：
   ```python
   @app.route("/callback", methods=['POST'])
   def callback():
       # 獲取 X-Line-Signature 請求頭
       signature = request.headers['X-Line-Signature']
       
       # 獲取請求體
       body = request.get_data(as_text=True)
       app.logger.info("Request body: " + body)
       
       # 處理 webhook 請求
       try:
           events = parser.parse(body, signature)
           for event in events:
               # 處理文本消息
               if event.type == "message" and event.message.type == "text":
                   message_text = event.message.text
                   source_type = event.source.type
                   
                   # 如果是群組消息，檢查前綴，除非是來自按鈕點擊
                   if source_type == 'group' or source_type == 'room':
                       # 檢查是否是從Flex Message按鈕觸發的（使用特殊標記判斷）
                       is_from_button = False
                       
                       # 檢查是否是常見命令格式，這些通常是由按鈕觸發的
                       button_commands = [
                           "查詢班次", "預約", "東洋預約", "查詢固定班次", 
                           "生成週報", "修改狀態", "班次詳情", "幫助", "幫助文字"
                       ]
                       
                       # 檢查是否是按鈕命令
                       for cmd in button_commands:
                           if message_text == cmd or message_text.startswith(f"{cmd} "):
                               is_from_button = True
                               break
                       
                       # 如果不是來自按鈕且沒有前綴，則不處理
                       if not is_from_button and not (message_text.startswith("!") or 
                              message_text.startswith("#") or 
                              message_text.startswith("/")):
                           continue
                       
                       # 如果有前綴，去除前綴
                       if not is_from_button and (message_text.startswith("!") or 
                                             message_text.startswith("#") or 
                                             message_text.startswith("/")):
                           message_text = message_text[1:].strip()
                           
                           # 如果去除前綴後消息為空，則不處理
                           if not message_text:
                               continue
                           
                           # 更新event.message.text為處理後的文本
                           event.message.text = message_text
                   
                   # 處理消息
                   handle_text_message(event)
               
               # 處理 Postback 事件（如果使用了 PostbackAction）
               elif event.type == "postback":
                   handle_postback(event)
                   
       except InvalidSignatureError:
           abort(400)
       except Exception as e:
           print(f"發生錯誤: {e}")
           abort(500)

       return 'OK'
   ```

2. 使用 PostbackAction 代替 MessageAction：
   ```python
   help_bubble = {
       "type": "bubble",
       "body": {
           "type": "box",
           "layout": "vertical",
           "contents": [
               {
                   "type": "button",
                   "action": {
                       "type": "postback",
                       "label": "🔍 查詢班次",
                       "data": "action=query_trips",
                       "displayText": "查詢班次"
                   },
                   "style": "primary",
                   "color": "#1E90FF"
               }
           ]
       }
   }
   ```

3. 處理 Postback 事件：
   ```python
   def handle_postback(event):
       """處理 Postback 事件"""
       postback_data = event.postback.data
       reply_token = event.reply_token
       user_id = event.source.user_id
       source_type = event.source.type
       
       try:
           # 解析 postback 數據
           params = {}
           if postback_data:
               param_pairs = postback_data.split('&')
               for pair in param_pairs:
                   if '=' in pair:
                       key, value = pair.split('=')
                       params[key] = value
           
           # 根據 action 參數處理不同的 postback
           action = params.get('action', '')
           
           if action == 'query_trips':
               # 查詢班次
               # ... 實現查詢班次的邏輯 ...
           
           elif action == 'booking':
               # 預約功能
               # 檢查是否在群組中
               if source_type == 'group' or source_type == 'room':
                   messaging_api.reply_message(
                       ReplyMessageRequest(
                           reply_token=reply_token,
                           messages=[TextMessage(text="預約功能僅支持在私聊中使用。\n請私聊機器人進行預約。")]
                       )
                   )
               else:
                   # 在私聊中啟動預約流程
                   # ... 實現預約流程的邏輯 ...
           
           # ... 處理其他 actions ...
       
       except Exception as e:
           print(f"處理 postback 時出錯: {e}")
           messaging_api.reply_message(
               ReplyMessageRequest(
                   reply_token=reply_token,
                   messages=[TextMessage(text=f"處理請求時出錯: {str(e)}")]
               )
           )
   ```

### 關鍵點
1. **前綴檢查改進**：
   - 群組消息需要前綴 (`!`、`#`、`/`)
   - 但是如果消息是由按鈕點擊生成的，則無需前綴

2. **Flex Message 按鈕處理**：
   - 使用 `PostbackAction` 而不是 `MessageAction`
   - 通過 `data` 屬性傳遞參數
   - 通過 `displayText` 屬性控制顯示在聊天窗口的文本

3. **分支處理**：
   - `callback` 函數根據事件類型分發到不同的處理函數
   - `handle_text_message` 處理文本消息
   - `handle_postback` 處理按鈕點擊事件

### 實現步驟
1. 修改 `callback` 函數，添加按鈕點擊檢測邏輯
2. 創建 `handle_postback` 函數處理 postback 事件
3. 修改 Flex Message 設計，使用 `PostbackAction` 代替 `MessageAction`
4. 在 `handle_postback` 函數中實現所有相應的功能處理邏輯

### 注意事項
1. 按鈕點擊的檢測是一種啟發式方法，可能不是 100% 準確
2. 使用 `displayText` 可以控制點擊按鈕後顯示在聊天窗口的文本
3. 所有關鍵功能都需要在 `handle_postback` 中重新實現一遍
4. 預約功能在群組中仍然需要顯示提示信息

### 測試要點
1. 群組中：
   - 直接輸入命令（不帶前綴）時應被忽略
   - 帶前綴的命令可以正常執行
   - 點擊 Flex Message 按鈕可以不帶前綴直接執行命令
   - 預約功能返回提示消息

2. 私聊中：
   - 直接輸入命令可以正常執行
   - 點擊 Flex Message 按鈕可以正常執行命令
   - 預約功能可以正常使用

### 常見問題
1. 如果點擊按鈕後無反應，檢查 `handle_postback` 函數是否正確處理了相應的 action
2. 如果按鈕點擊後需要前綴，檢查 `callback` 函數中的按鈕點擊檢測邏輯
3. 如果群組中按鈕點擊顯示了錯誤消息，檢查 `handle_postback` 函數中的邏輯
4. 如果私聊中按鈕不起作用，檢查 Flex Message 的設計是否正確

### 回滾方案
如果修改後出現問題：
1. 保存當前版本為 .bak
2. 回滾到最後一個已知可用的版本
3. 逐步應用修改，每次修改後進行測試
4. 如果按鈕點擊檢測邏輯不可靠，可以考慮完全使用 `PostbackAction` 方式

## 在群組中實現預約功能（高級方案）

### 挑戰與困難
1. **多輪對話問題**：
   - 預約功能需要多輪對話（選擇日期、時間等）
   - 在群組中，每次回覆都需要前綴會非常不便
   - 用戶可能會忘記添加前綴，導致對話中斷

2. **對話狀態管理**：
   - 需要跟踪用戶在預約流程中的狀態
   - 多個用戶同時在一個群組中進行預約可能會混淆

3. **按鈕識別挑戰**：
   - 目前的方案使用啟發式方法識別按鈕點擊
   - 這種方法在預約過程中可能不夠穩定

### 可能的解決方案

#### 方案1：臨時免前綴窗口
```python
def handle_text_message(event):
    message_text = event.message.text
    user_id = event.source.user_id
    source_type = event.source.type
    
    # 檢查用戶是否在預約流程中
    if user_id in booking_states:
        # 在預約流程中的用戶可以不使用前綴直接回覆
        # 但只限於預約相關的命令
        booking_step = booking_states[user_id]['step']
        handle_booking_message(user_id, message_text, booking_states)
        return
        
    # 其他消息處理...
```

#### 方案2：使用 Postback 按鈕進行整個預約流程
```python
def handle_postback(event):
    postback_data = event.postback.data
    user_id = event.source.user_id
    
    # 解析 postback 數據
    params = {}
    if postback_data:
        param_pairs = postback_data.split('&')
        for pair in param_pairs:
            if '=' in pair:
                key, value = pair.split('=')
                params[key] = value
    
    action = params.get('action', '')
    
    if action == 'booking_select_date':
        # 顯示日期選擇界面
        date = params.get('date', '')
        # 處理日期選擇...
        
    elif action == 'booking_select_time':
        # 顯示時間選擇界面
        date = params.get('date', '')
        # 處理時間選擇...
        
    # 其他預約相關 actions...
```

#### 方案3：使用特殊的命令格式
```python
def callback():
    # ...
    
    # 如果消息符合預約命令格式（例如：book:date:2023-03-19）
    if re.match(r'book:(date|time|confirm):', message_text):
        # 無需前綴直接處理
        handle_booking_command(event)
        return
        
    # ...
```

#### 方案4：預約專用前綴
```python
def callback():
    # ...
    
    # 如果消息使用預約專用前綴（例如：>）
    if message_text.startswith('>'):
        # 去除前綴並處理為預約命令
        booking_text = message_text[1:].strip()
        handle_booking_message(user_id, booking_text, booking_states)
        return
        
    # ...
```

### 推薦方案

最實用的解決方案是結合 **方案1** 和 **方案2**：

1. 使用 **Postback 按鈕** 進行大部分預約流程
   - 日期選擇：使用日期選擇按鈕
   - 時間選擇：使用時間選擇按鈕
   - 確認：使用確認/取消按鈕

2. 對於需要文本輸入的部分，提供 **臨時免前綴窗口**
   - 設置一個短時間窗口（例如30秒）
   - 在此窗口期間，該用戶的消息無需前綴
   - 窗口期結束後，恢復前綴要求

3. 增加明確的 **用戶提示**
   - 清晰提示用戶當前正在進行預約
   - 指示何時可以直接輸入，何時需要使用前綴

### 實現草案
```python
# 在 booking_states 中添加 no_prefix_window 字段
booking_states[user_id] = {
    'step': 'date',
    'data': {},
    'no_prefix_window': datetime.now() + timedelta(seconds=30)  # 30秒免前綴窗口
}

# 在 callback 函數中
if (source_type == 'group' or source_type == 'room') and user_id in booking_states:
    # 檢查用戶是否在免前綴窗口期
    if booking_states[user_id].get('no_prefix_window', datetime.min) > datetime.now():
        # 在免前綴窗口期內，直接處理消息
        handle_text_message(event)
        return
        
# 在 handle_booking_message 函數中
def handle_booking_message(user_id, message_text, booking_states):
    # 處理預約消息...
    
    # 更新免前綴窗口
    booking_states[user_id]['no_prefix_window'] = datetime.now() + timedelta(seconds=30)
    
    # 返回包含提示的消息
    return TextMessage(text=f"請在30秒內直接回覆（無需添加前綴）\n{prompt_message}")
```

### 注意事項
1. 需要定期清理過期的免前綴窗口記錄
2. 在複雜的群組聊天中，可能需要更明確的用戶識別機制
3. 考慮使用 Quick Reply 功能提供常用選項
4. 在 Flex Message 中提醒用戶當前的前綴要求狀態

### 暫時結論
雖然實現群組預約功能是可能的，但考慮到實現複雜度和可能的用戶混淆，**目前建議保持預約功能僅在私聊中可用**。這樣可以提供最清晰的用戶體驗，避免在群組聊天中的複雜交互問題。

如果未來確實需要群組預約功能，可以採用方案2（完全基於按鈕的預約流程），這是最可靠的實現方式，雖然會犧牲一些靈活性。