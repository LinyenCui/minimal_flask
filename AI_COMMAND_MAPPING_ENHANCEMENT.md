# AI 命令映射增強功能 - 修改步驟文檔

## 📋 功能概述

將 AI 智能查詢與現有的標準命令進行智能映射，當 AI 偵測到用戶輸入與現成命令含義相同時，提供確認對話框並調用具有完整 Flex Message 和 Quick Reply 的標準命令。

## 🎯 實現目標

### 1. 智能映射確認機制
- AI 偵測到與現成命令相同含義時，顯示確認對話框
- 用戶確認後調用標準命令，享受完整的 Flex Message 體驗

### 2. 複雜查詢 Flex Message 增強
- 支援「所有類別」查詢的 Flex Message 顯示
- 支援「司機篩選」的 Flex Message 分組
- 支援「狀態篩選」的 Flex Message 分組

---

## 🔧 第一階段：智能映射確認機制

### 步驟 1.1：修改智能助手映射邏輯

**文件：** `modules/services/smart_assistant.py`

**修改內容：**
```python
def _analyze_potential_mapping(self, user_input: str) -> Dict:
    """分析用戶輸入是否可映射到標準命令"""
    
    # 定義標準命令映射規則
    mapping_rules = {
        "東洋班次": {
            "patterns": ["今天東洋", "東洋今天", "今天東洋班次", "東洋班次今天"],
            "command_template": "東洋班次 {date}",
            "description": "東洋班次查詢 (含完整 Flex Message 和分頁功能)"
        },
        "診所班次": {
            "patterns": ["今天診所", "診所今天", "今天診所班次", "診所班次今天"],
            "command_template": "診所班次 {date}",
            "description": "診所班次查詢 (含完整 Flex Message 和分頁功能)"
        },
        "班次詳情": {
            "patterns": ["查看班次", "班次詳情", "看班次"],
            "command_template": "班次詳情 {trip_id}",
            "description": "班次詳情查詢 (含完整 Flex Message 和操作按鈕)"
        }
    }
    
    # 檢測映射可能性
    for command_name, rule in mapping_rules.items():
        for pattern in rule["patterns"]:
            if self._pattern_matches(user_input, pattern):
                return {
                    "mappable": True,
                    "command_name": command_name,
                    "standard_command": self._build_standard_command(user_input, rule),
                    "description": rule["description"]
                }
    
    return {"mappable": False}

def _build_confirmation_message(self, mapping_info: Dict) -> str:
    """構建映射確認訊息"""
    return f"""🤖 偵測到目前系統中有相同涵義的現成指令

💬 您的查詢：「{mapping_info['user_input']}」
🎯 現成指令：「{mapping_info['standard_command']}」
✨ 功能特色：{mapping_info['description']}

是否調用現成指令？"""
```

### 步驟 1.2：建立映射確認對話流程

**文件：** `modules/handlers/text_message_handler.py`

**新增處理邏輯：**
```python
def handle_command_mapping_confirmation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理命令映射確認對話"""
    context_data = conversation.get('context_data', {})
    
    if message_text in ["確認調用", "確認", "是", "好"]:
        # 用戶確認，執行標準命令
        standard_command = context_data.get('standard_command')
        logger.info(f"🎯 用戶確認調用標準命令: {standard_command}")
        
        # 清除對話狀態
        conversation_manager.end_conversation(user_id)
        
        # 執行標準命令
        if standard_command.startswith("東洋班次"):
            from modules.services.trip_query_service import handle_query_trips_flex
            flex_message, text_fallback = handle_query_trips_flex(standard_command)
            if flex_message:
                reply_flex_message(reply_token, flex_message)
            else:
                reply_text(reply_token, text_fallback)
                
        elif standard_command.startswith("診所班次"):
            from modules.services.trip_query_service import handle_query_clinic_trips_flex
            flex_message, text_fallback = handle_query_clinic_trips_flex(standard_command)
            if flex_message:
                reply_flex_message(reply_token, flex_message)
            else:
                reply_text(reply_token, text_fallback)
                
        # ... 其他命令類型
        
    elif message_text in ["放棄", "取消", "不要", "否"]:
        # 用戶取消，回到原 AI 處理
        conversation_manager.end_conversation(user_id)
        reply_text(reply_token, "已取消調用，將使用 AI 智能搜索處理您的查詢...")
        
        # 重新用 AI 處理
        original_query = context_data.get('original_query')
        # 執行原始 AI 查詢邏輯...
        
    else:
        reply_text(reply_token, "請選擇「確認調用」或「放棄」")
```

### 步驟 1.3：整合映射邏輯到主流程

**文件：** `modules/handlers/text_message_handler.py` 的 `process_text_message`

**修改智能助手處理部分：**
```python
# 在智能助手處理前，先檢查映射可能性
mapping_result = smart_assistant._analyze_potential_mapping(message_text)

if mapping_result.get("mappable"):
    # 啟動映射確認對話
    confirmation_message = smart_assistant._build_confirmation_message({
        "user_input": message_text,
        "standard_command": mapping_result["standard_command"],
        "description": mapping_result["description"]
    })
    
    conversation_manager.start_conversation(
        user_id=user_id,
        conversation_type='command_mapping_confirmation',
        current_step='waiting_confirmation',
        context_data={
            'original_query': message_text,
            'standard_command': mapping_result["standard_command"],
            'command_name': mapping_result["command_name"]
        },
        prompt_message=confirmation_message,
        duration_minutes=3
    )
    
    # 添加 Quick Reply
    quick_reply = QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label="確認調用", text="確認調用")),
            QuickReplyItem(action=MessageAction(label="放棄", text="放棄"))
        ]
    )
    
    reply_message_with_quick_reply(reply_token, confirmation_message, quick_reply.to_dict())
    return

# 如果沒有映射可能性，繼續原有的智能助手邏輯
```

---

## 🎨 第二階段：複雜查詢 Flex Message 增強

### 步驟 2.1：所有類別查詢的 Flex Message

**文件：** `modules/flex_designs/all_categories_flex.py` (新建)

**實現難度：🟡 中等**

**設計思路：**
```python
def generate_all_categories_flex(date_str: str) -> Dict:
    """生成所有類別班次的 Flex Message"""
    
    # 1. 分別查詢東洋和診所班次
    dongyang_trips = query_dongyang_trips(date_str)
    clinic_trips = query_clinic_trips(date_str)
    
    # 2. 合併並按時間排序
    all_trips = sorted(dongyang_trips + clinic_trips, key=lambda x: x.time)
    
    # 3. 按類別分組顯示
    flex_content = {
        "type": "carousel",
        "contents": [
            create_category_bubble("東洋", dongyang_trips),
            create_category_bubble("診所", clinic_trips)
        ]
    }
    
    # 4. 如果某類別無班次，自動調整顯示
    return flex_content
```

### 步驟 2.2：司機篩選的 Flex Message

**文件：** `modules/flex_designs/driver_filtered_flex.py` (新建)

**實現難度：🟢 容易**

**設計思路：**
```python
def generate_driver_filtered_flex(driver_id: str, date_str: str) -> Dict:
    """生成特定司機的班次 Flex Message"""
    
    # 1. 查詢該司機的所有班次
    driver_trips = query_trips_by_driver(driver_id, date_str)
    
    # 2. 按類別分組
    trips_by_category = group_by_category(driver_trips)
    
    # 3. 使用現有的 trip_query_flex 邏輯，但加上司機信息標題
    flex_content = generate_trips_flex_with_driver_header(
        trips=driver_trips,
        driver_id=driver_id,
        date_str=date_str
    )
    
    return flex_content
```

### 步驟 2.3：狀態篩選的 Flex Message

**文件：** `modules/flex_designs/status_filtered_flex.py` (新建)

**實現難度：🟢 容易**

**設計思路：**
```python
def generate_status_filtered_flex(status: str, date_str: str) -> Dict:
    """生成特定狀態的班次 Flex Message"""
    
    # 1. 查詢特定狀態的班次
    status_trips = query_trips_by_status(status, date_str)
    
    # 2. 使用狀態主題色彩
    status_colors = {
        "準備": "#4CAF50",      # 綠色
        "待派": "#FF9800",      # 橙色  
        "已完成": "#2196F3",    # 藍色
        "取消": "#F44336",      # 紅色
        "衝突": "#9C27B0"       # 紫色
    }
    
    # 3. 生成帶狀態主題的 Flex Message
    flex_content = generate_trips_flex_with_status_theme(
        trips=status_trips,
        status=status,
        color=status_colors.get(status, "#666666"),
        date_str=date_str
    )
    
    return flex_content
```

---

## 🔄 第三階段：智能路由邏輯

### 步驟 3.1：修改 smart_assistant 路由

**文件：** `modules/services/smart_assistant.py`

**路由邏輯：**
```python
def route_complex_query(self, user_input: str, ai_analysis: Dict) -> str:
    """根據查詢複雜度選擇處理方式"""
    
    # 1. 簡單映射 -> 確認對話 -> 標準命令
    if self._is_simple_mapping(ai_analysis):
        return "show_mapping_confirmation"
    
    # 2. 所有類別 -> 複合 Flex Message
    elif self._is_all_categories_query(ai_analysis):
        return "generate_all_categories_flex"
    
    # 3. 司機篩選 -> 司機 Flex Message  
    elif self._is_driver_filtered_query(ai_analysis):
        return "generate_driver_filtered_flex"
    
    # 4. 狀態篩選 -> 狀態 Flex Message
    elif self._is_status_filtered_query(ai_analysis):
        return "generate_status_filtered_flex"
    
    # 5. 複雜條件 -> advanced_query_processor
    else:
        return "use_advanced_query_processor"
```

---

## 📊 實現難度評估

| 功能 | 難度 | 工作量 | 備註 |
|------|------|--------|------|
| 映射確認對話 | 🟡 中等 | 2-3小時 | 需要整合對話管理 |
| 所有類別 Flex | 🟡 中等 | 3-4小時 | 需要合併查詢邏輯 |
| 司機篩選 Flex | 🟢 容易 | 1-2小時 | 複用現有 Flex 模板 |
| 狀態篩選 Flex | 🟢 容易 | 1-2小時 | 複用現有 Flex 模板 |
| 智能路由邏輯 | 🟡 中等 | 2-3小時 | 需要整合所有功能 |

**總工作量估計：9-14 小時**

---

## 🎯 實現優先級建議

### Phase 1 (立即實現)
1. 映射確認對話機制
2. 簡單的東洋/診所班次映射

### Phase 2 (短期目標)  
3. 司機篩選 Flex Message
4. 狀態篩選 Flex Message

### Phase 3 (長期優化)
5. 所有類別複合查詢
6. 更複雜的條件組合

---

## 💡 額外考慮

**用戶體驗優化：**
- 映射確認對話設置 3 分鐘過期
- 提供「記住我的選擇」選項 (未來功能)
- 保持與現有 Flex Message 設計一致

**性能考慮：**
- 複合查詢時考慮分頁處理
- 大量結果時的載入體驗優化

**錯誤處理：**
- 標準命令執行失敗時的降級處理
- 映射邏輯的容錯機制 