# AI系統三時間態智能路由實施計劃

## 📋 項目概述

### 目標
將現有的關鍵字匹配系統升級為真正的AI智能路由系統，實現自然語言理解和三時間態自動分類。

### 核心架構
```
用戶自然語言 → Gemini意圖分析 → 三時間態路由 → 現有功能執行 → 智能回應
```

---

## 🔍 現狀分析

### ✅ 現有優勢
1. **完善的Gemini API集成**
   - `modules/services/ai_service.py` - 預約信息提取
   - 已有Google Cloud設定和認證
   - 已有prompt工程經驗

2. **成熟的智能功能**
   - `modules/services/ai_fare_service.py` (1253行) - 完整的自然語言車資查詢
   - `modules/utils/conversation_context.py` - 對話上下文管理
   - 複雜的意圖識別邏輯

3. **清晰的三時間態資料結構**
   - **過去**: `completed_trips` 表 (已完成班次)
   - **現在**: `trips` 表 (當前班次) 
   - **未來**: `fixed_schedules` 表 (固定班次模板)

4. **完整的業務功能**
   - 班次查詢、指派、修改
   - 報表生成、數據分析
   - Flex UI 交互設計

### ⚠️ 現有挑戰
1. **路由邏輯分散**
   - 命令識別在 `message_handler.py`
   - 文本處理在 `text_message_handler.py`
   - AI功能各自獨立

2. **缺乏統一的意圖分析**
   - 現有的if/else規則引擎
   - 無法理解複雜自然語言
   - 新功能需要硬編碼新規則

3. **功能孤島化**
   - AI功能無法組合使用
   - 缺乏跨時間態的智能查詢
   - 沒有統一的知識庫

---

## 🎯 實施目標

### 第一階段目標 (基礎AI路由)
- [ ] 實現統一的意圖分析入口
- [ ] 三時間態自動路由
- [ ] 保持100%向後兼容

### 第二階段目標 (智能增強)  
- [ ] 複雜自然語言理解
- [ ] 動態SQL生成
- [ ] 跨功能組合執行

### 第三階段目標 (AI編排)
- [ ] 多步驟任務分解
- [ ] 智能決策引導
- [ ] 持續學習優化

---

## 📝 詳細實施步驟

### 階段一：基礎架構搭建 (第1-2天)

#### 任務1.1：創建核心AI路由器 🔧
**文件**: `modules/services/ai_router.py`

**功能設計**:
```python
class AIRouter:
    def __init__(self):
        self.gemini_api = GeminiService()
        self.knowledge_base = SystemKnowledgeBase()
    
    def analyze_intent(self, user_message: str) -> IntentResult:
        """使用Gemini分析用戶意圖"""
        pass
    
    def route_to_time_perspective(self, intent: IntentResult) -> TimeRouting:
        """根據意圖路由到對應時間態"""
        pass
    
    def execute_function(self, routing: TimeRouting) -> ExecutionResult:
        """執行對應的業務功能"""
        pass
```

**詳細實現**:
- 整合現有 `ai_service.py` 的Gemini配置
- 創建統一的意圖分析prompt
- 定義標準的返回格式

**估計工時**: 4-6小時

#### 任務1.2：建立系統知識庫 📚
**文件**: `modules/services/system_knowledge.py`

**內容設計**:
```python
SYSTEM_KNOWLEDGE = {
    "database_schema": {
        "trips": "當前進行中的班次...",
        "completed_trips": "已完成的歷史班次...",
        "fixed_schedules": "固定班次模板..."
    },
    "business_rules": {
        "time_perspectives": {
            "past": ["昨天", "上週", "已完成", "歷史"],
            "present": ["今天", "現在", "當前", "待派"],
            "future": ["明天", "下週", "安排", "匯入"]
        }
    },
    "available_functions": {
        "query_trips": "查詢當前班次",
        "query_completed": "查詢已完成班次",
        "import_schedules": "匯入固定班次"
    }
}
```

**估計工時**: 3-4小時

#### 任務1.3：設計意圖分析prompt 📝
**文件**: `modules/prompts/intent_analysis_prompt.txt`

**Prompt設計**:
```
你是一個派班系統的意圖分析專家。請分析用戶的自然語言輸入，識別：

1. 時間態度 (past/present/future)
2. 操作類型 (query/modify/create)  
3. 實體提取 (driver_id, date, location)
4. 目標功能 (trips/completed_trips/fixed_schedules)

系統支援的功能清單：
{function_list}

用戶輸入: "{user_input}"

請以JSON格式返回分析結果：
{
    "time_perspective": "past|present|future",
    "operation_type": "query|modify|create",
    "entities": {...},
    "target_function": "function_name",
    "confidence": 0.85,
    "reasoning": "分析推理過程"
}
```

**估計工時**: 2-3小時

#### 任務1.4：修改主路由入口 🚪
**文件**: `modules/handlers/text_message_handler.py`

**修改內容**:
```python
# 在 process_text_message 函數中添加AI路由檢查
def process_text_message(event):
    message_text = event.message.text
    
    # 新增：AI意圖分析檢查
    if should_use_ai_router(message_text):
        from modules.services.ai_router import AIRouter
        router = AIRouter()
        result = router.process_message(message_text, event)
        if result.success:
            return result.send_response(reply_token)
    
    # 保持現有邏輯作為fallback
    # ... 現有代碼 ...
```

**向後兼容策略**:
- 所有現有命令繼續正常工作
- AI路由作為額外功能層
- 失敗時自動回退到現有邏輯

**估計工時**: 2-3小時

### 階段二：三時間態路由實現 (第3-4天)

#### 任務2.1：過去時間態路由 ⏮️
**目標**: 整合現有的車資查詢系統

**實現策略**:
```python
class PastTimeHandler:
    def handle_query(self, intent: IntentResult) -> QueryResult:
        # 利用現有的 CompletedTripMatcher
        matcher = CompletedTripMatcher()
        criteria = self.convert_intent_to_criteria(intent)
        trips = matcher.search_completed_trips(criteria)
        return self.format_results(trips)
```

**集成點**:
- 重用 `ai_fare_service.py` 中的 `CompletedTripMatcher`
- 擴展支援更多查詢類型
- 統一結果格式化

**估計工時**: 3-4小時

#### 任務2.2：現在時間態路由 ⏸️
**目標**: 整合當前班次管理功能

**實現策略**:
```python
class PresentTimeHandler:
    def handle_query(self, intent: IntentResult) -> QueryResult:
        # 調用現有的班次查詢功能
        if intent.entities.get('category') == '診所':
            return handle_clinic_trips_query(intent)
        elif intent.entities.get('category') == '東洋':
            return handle_dongyang_trips_query(intent)
```

**集成點**:
- 重用現有的 `query_trips` 功能
- 整合司機指派邏輯
- 保持Flex UI回應格式

**估計工時**: 3-4小時

#### 任務2.3：未來時間態路由 ⏭️
**目標**: 整合固定班次和預約功能

**實現策略**:
```python
class FutureTimeHandler:
    def handle_import(self, intent: IntentResult) -> ImportResult:
        # 調用現有的匯入功能
        week = intent.entities.get('week', '下週')
        return handle_import_fixed_trips(week)
    
    def handle_booking(self, intent: IntentResult) -> BookingResult:
        # 調用現有的AI預約功能
        booking_info = extract_booking_info_with_gemini(intent.original_text)
        return process_booking_request(booking_info)
```

**集成點**:
- 重用 `handle_import_fixed_trips` 功能
- 整合 `ai_service.py` 的預約提取
- 統一週期規劃邏輯

**估計工時**: 4-5小時

### 階段三：智能路由優化 (第5-6天)

#### 任務3.1：結果智能格式化 📊
**目標**: 統一和美化AI回應格式

**功能設計**:
```python
class ResponseFormatter:
    def format_trip_results(self, trips: List[Trip], query_type: str) -> str:
        """智能格式化班次查詢結果"""
        if len(trips) == 0:
            return self.generate_empty_suggestions(query_type)
        elif len(trips) == 1:
            return self.format_single_trip(trips[0])
        else:
            return self.format_multiple_trips(trips)
    
    def generate_empty_suggestions(self, query_type: str) -> str:
        """當沒有結果時，提供智能建議"""
        pass
```

**估計工時**: 3-4小時

#### 任務3.2：錯誤處理和引導 🚨
**目標**: 當AI無法理解時，提供有用的引導

**實現策略**:
```python
def handle_low_confidence_intent(intent: IntentResult) -> GuidanceResponse:
    if intent.confidence < 0.7:
        return {
            "message": "我不太確定您的意思，您是想要：",
            "suggestions": [
                "查詢今天的班次？",
                "查看已完成的班次？", 
                "匯入固定班次？"
            ],
            "fallback": "使用「幫助」查看完整功能列表"
        }
```

**估計工時**: 2-3小時

#### 任務3.3：性能監控和日誌 📈
**目標**: 監控AI功能的使用和準確性

**功能設計**:
```python
class AIMetrics:
    def log_intent_analysis(self, user_input: str, intent: IntentResult, success: bool):
        """記錄意圖分析的準確性"""
        pass
    
    def track_user_satisfaction(self, user_id: str, interaction_id: str, rating: int):
        """追蹤用戶滿意度"""
        pass
```

**估計工時**: 2小時

### 階段四：測試和優化 (第7天)

#### 任務4.1：單元測試 🧪
**文件**: `tests/test_ai_router.py`

**測試範圍**:
- 意圖分析準確性測試
- 三時間態路由測試  
- 向後兼容性測試
- 錯誤處理測試

**估計工時**: 4-5小時

#### 任務4.2：整合測試 🔗
**測試場景**:
- 端到端功能測試
- LINE Bot集成測試
- 性能壓力測試

**估計工時**: 3-4小時

#### 任務4.3：用戶接受測試 👥
**測試策略**:
- 內部測試版本部署
- 收集實際使用反饋
- 根據反饋調整prompt和邏輯

**估計工時**: 持續進行

---

## 🗂️ 文件結構規劃

### 新增文件
```
modules/services/
├── ai_router.py              # 核心AI路由器
├── system_knowledge.py       # 系統知識庫
├── time_handlers/
│   ├── __init__.py
│   ├── past_handler.py       # 過去時間態處理
│   ├── present_handler.py    # 現在時間態處理
│   └── future_handler.py     # 未來時間態處理
└── response_formatter.py     # 回應格式化器

modules/prompts/
├── intent_analysis_prompt.txt    # 意圖分析prompt
├── time_routing_prompt.txt       # 時間態路由prompt
└── function_selection_prompt.txt # 功能選擇prompt

tests/
├── test_ai_router.py         # AI路由器測試
├── test_time_handlers.py     # 時間態處理器測試
└── test_integration.py       # 整合測試
```

### 修改文件
```
modules/handlers/text_message_handler.py  # 添加AI路由入口
modules/handlers/message_handler.py       # 更新命令識別邏輯
modules/services/ai_service.py            # 擴展Gemini API功能
```

---

## 📊 風險評估與緩解

### 🔴 高風險項目
1. **Gemini API調用失敗**
   - 緩解：完整的fallback機制
   - 回退到現有關鍵字匹配

2. **意圖識別準確率不足**
   - 緩解：設定信心閾值
   - 低信心時提供選項引導

3. **性能影響**
   - 緩解：添加緩存機制
   - 異步處理非關鍵路徑

### 🟡 中風險項目
1. **向後兼容性問題**
   - 緩解：完整的測試覆蓋
   - 分階段部署驗證

2. **用戶習慣改變**
   - 緩解：保持現有命令可用
   - 逐步引導用戶體驗新功能

---

## 📈 成功指標

### 技術指標
- [ ] 意圖識別準確率 > 85%
- [ ] API回應時間 < 3秒
- [ ] 向後兼容性 100%
- [ ] 測試覆蓋率 > 90%

### 業務指標  
- [ ] 用戶查詢成功率提升 20%
- [ ] 自然語言查詢佔比 > 30%
- [ ] 用戶滿意度評分 > 4.0/5.0
- [ ] 客服工作量減少 15%

### 系統指標
- [ ] API費用控制在 $20/月內
- [ ] 系統可用性 > 99.5%
- [ ] 錯誤率 < 1%

---

## 🔄 部署策略

### 階段部署計劃
1. **內部測試** (第8天)
   - 部署到開發環境
   - 團隊內部測試驗證

2. **灰度發布** (第9-10天) 
   - 10%用戶體驗新功能
   - 監控關鍵指標

3. **全量部署** (第11天)
   - 100%用戶開放功能
   - 持續監控和優化

### 回滾計劃
- 緊急關閉AI路由功能
- 回退到純關鍵字匹配
- 保持所有現有功能可用

---

## 📅 時間線總覽

| 天數 | 階段 | 主要任務 | 交付物 |
|------|------|---------|--------|
| 1-2  | 基礎架構 | AI路由器、知識庫 | 核心框架 |
| 3-4  | 時間態路由 | 三時間態處理器 | 路由功能 |
| 5-6  | 智能優化 | 格式化、錯誤處理 | 完整功能 |
| 7    | 測試 | 單元、整合測試 | 測試報告 |
| 8-11 | 部署 | 階段部署驗證 | 生產就緒 |

**總計**: 約11天完成完整的AI系統改造

---

## 📋 檢查清單

### 開始前確認
- [ ] 確認Gemini API配額和限制
- [ ] 備份當前穩定版本
- [ ] 準備測試環境
- [ ] 確認團隊技術準備

### 每日檢查
- [ ] 代碼提交和備份
- [ ] 功能測試驗證
- [ ] 性能指標監控
- [ ] 進度狀態更新

### 完成前確認
- [ ] 所有測試通過
- [ ] 文檔更新完成
- [ ] 部署流程驗證
- [ ] 團隊培訓完成

---

**文檔版本**: 1.0  
**創建日期**: 2025-07-14  
**預計完成**: 2025-07-25  
**負責人**: AI Assistant  
**審核狀態**: 待確認 