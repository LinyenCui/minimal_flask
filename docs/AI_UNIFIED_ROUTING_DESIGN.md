# 🤖 AI統一三時間態路由設計

## 🎯 核心概念

**讓AI成為所有班次相關查詢的統一入口，智能判斷時間態並路由到正確的處理器。**

## 🏗️ 架構設計

```
用戶輸入 → AI智能路由器 → 時間態判斷 → 自動重試機制 → 統一回應
```

### 統一命令處理流程

#### 階段1：AI智能解析
```python
用戶：「班次詳情 1585」
AI解析：
- 意圖：查看班次詳情  
- 班次ID：1585
- 時間態：未知（需要智能判斷）
- 信心度：高
```

#### 階段2：智能時間態判斷
```python
判斷邏輯：
1. 檢查數字特徵：1585（較大數字，可能是trip_id）
2. 先嘗試trips表（現在態）
3. 如果失敗，嘗試completed_trips表（過去態）
4. 返回找到的結果 + 智能提示
```

#### 階段3：自動容錯與引導
```python
情況A：在trips表找到
→ 返回詳情 + 提示：「✅ 這是生產線上的班次」

情況B：在completed_trips表找到  
→ 返回詳情 + 提示：「✅ 這是已完成的班次」

情況C：都找不到
→ 智能建議：「可能的原因和建議操作」
```

## 📝 具體實現策略

### 方案1：增強現有智能助手
在`smart_assistant.py`中添加統一班次查詢功能：

```python
# 新增統一班次詳情查詢
"班次查詢 [ID]": {
    "handler": "unified_trip_details",
    "auto_route": True,
    "fallback_tables": ["trips", "completed_trips"],
    "smart_hints": True
}
```

### 方案2：創建智能班次查詢器
```python
class UnifiedTripQueryService:
    """統一班次查詢服務 - 跨時間態智能搜索"""
    
    def query_trip_details(self, trip_id: int, user_context: dict):
        # 1. 嘗試trips表（現在態）
        current_result = self._query_trips_table(trip_id)
        if current_result:
            return self._format_current_trip_result(current_result)
        
        # 2. 嘗試completed_trips表（過去態）  
        completed_result = self._query_completed_trips_table(trip_id)
        if completed_result:
            return self._format_completed_trip_result(completed_result)
        
        # 3. 智能建議
        return self._generate_smart_suggestions(trip_id)
```

### 方案3：AI自然語言處理升級
讓AI處理更自然的查詢：

```python
# 用戶輸入範例
"我想看班次1585的詳情"           → 統一班次查詢 1585
"查看#2014的信息"              → 統一班次查詢 2014  
"班次1996怎麼樣了"             → 統一班次查詢 1996
"司機533昨天所有班次的詳情"     → 複雜查詢 + 批量詳情
```

## 🔄 智能路由規則

### 時間態自動判斷
```python
def smart_time_perspective_detection(query: str, trip_id: int):
    # 規則1：關鍵字判斷
    if any(keyword in query for keyword in ['昨天', '已完成', '車資', '收入']):
        return 'past_first'  # 優先查過去態
    
    # 規則2：ID範圍啟發式  
    if trip_id > 1500:  # 較大ID可能是近期的trip_id
        return 'present_first'  # 優先查現在態
    
    # 規則3：上下文記憶
    recent_context = get_user_recent_context(user_id)
    if recent_context.last_query_type == 'completed_trips':
        return 'past_first'
    
    # 默認：先查現在態，再查過去態
    return 'present_first'
```

### 自動重試邏輯
```python
def unified_trip_query(trip_id: int, query_context: dict):
    strategy = smart_time_perspective_detection(query_context['original_query'], trip_id)
    
    if strategy == 'present_first':
        # 1. 嘗試trips表
        result = query_trips_table(trip_id)
        if result:
            return format_result(result, table='trips', hint='生產線上的班次')
        
        # 2. 失敗時嘗試completed_trips表
        result = query_completed_trips_table(trip_id) 
        if result:
            return format_result(result, table='completed_trips', hint='已完成的班次')
    
    # 相反順序邏輯...
    
    # 都失敗時的智能建議
    return generate_smart_not_found_message(trip_id, query_context)
```

## 📋 用戶體驗改善

### 統一命令格式
用戶只需要記住一種格式：

```bash
# 統一格式
班次詳情 [ID]     # AI自動判斷是trips還是completed_trips
查看 [ID]        # 同上，別名命令  
班次 [ID]        # 同上，簡化命令

# 自然語言（推薦）
"看看班次1585"
"班次2014的情況"  
"我想查1996"
```

### 智能回應示例
```bash
用戶：班次詳情 1585
AI：✅ 找到生產線上的班次 #1585
    📅 2025-07-16 (星期二) 14:30
    🚗 司機533 (AB-1234)
    📍 台中火車站 → 彰化基督教醫院
    📊 狀態：準備中
    💡 這是當前正在執行的班次

用戶：班次詳情 123  
AI：✅ 找到已完成班次 #123
    📅 2025-07-15 (星期一) 09:15  
    🚗 司機5386 (CD-5678)
    📍 豐原診所 → 台中火車站
    💰 車資：錶價280 + 加成50 = 330元
    💡 這是已完成的班次記錄
```

## 🚀 實施計劃

### ✅ 階段1：核心功能開發（已完成）
1. ✅ 創建 `UnifiedTripQueryService` - 跨時間態智能搜索
2. ✅ 實現智能時間態判斷 - 基於關鍵字、ID範圍、用戶歷史
3. ✅ 添加自動重試機制 - 先查一個表，失敗時自動查另一個表
4. ✅ 整合到現有處理器 - 修改`text_message_handler.py`支持統一查詢

### 🔄 階段2：AI集成（進行中）
1. ✅ 更新 `smart_assistant.py` 的prompt - 添加統一班次查詢命令支持
2. 🔄 添加統一班次查詢命令支持 - 實現「統一班次查詢 [ID]」命令
3. ⏳ 實現自然語言解析 - 讓AI自動將各種表達轉換為統一命令

### ⏳ 階段3：用戶體驗優化（計劃中）
1. ⏳ 優化錯誤提示和建議
2. ⏳ 添加上下文記憶功能  
3. ⏳ 實現批量查詢支持

## 📋 已實現功能

### 核心統一查詢服務
- **智能時間態判斷**：根據關鍵字、ID範圍、用戶歷史自動決定搜索策略
- **跨表自動重試**：優先查一個表，失敗時自動查另一個表
- **統一結果格式**：所有查詢結果都包含來源表、時間態、智能提示
- **相似ID建議**：找不到時自動推薦相近的班次ID

### 命令統一化
- **班次詳情 [ID]** → 使用統一查詢服務
- **查看 [ID]** → 使用統一查詢服務  
- **統一班次查詢 [ID]** → 直接調用統一查詢服務

### 智能提示系統
- 自動提示班次來源（生產線 vs 成品倉庫）
- 提供相似ID建議
- 智能錯誤診斷和解決建議

## 🧪 測試驗證

創建了完整的測試套件 `test_unified_trip_query.py`：
- 測試不同ID範圍的查詢策略
- 驗證關鍵字影響的時間態判斷  
- 測試不存在ID的智能建議
- 驗證跨表自動重試機制

## 🎯 用戶體驗改善效果

### 問題解決
✅ **命令混亂** - 用戶不再需要記憶trips vs completed_trips的區別
✅ **ID困惑** - 系統自動判斷ID應該在哪個表中查找
✅ **錯誤處理** - 提供智能建議而不是簡單的"找不到"

### 使用體驗
✅ **統一入口** - 所有班次詳情查詢使用相同命令格式
✅ **智能容錯** - 自動嘗試不同時間態，提高成功率
✅ **清晰回饋** - 明確告知用戶數據來源和含義 