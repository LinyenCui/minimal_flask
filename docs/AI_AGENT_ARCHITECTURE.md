# AI Agent 架構實施方案

## 概述

本文檔描述了根據 Gemini 建議實施的 AI Agent 架構，將傳統的命令式派班系統轉換為自然語言智能派班系統。

## 架構組件

### 1. 核心大腦 (The Core LLM/Agent)
- **位置**: `modules/ai_agent/agent_core.py`
- **功能**: 實現思考→檢索→規劃→執行→回應的完整工作流程
- **核心類**: `DispatchAgent`

### 2. 工具箱 (Toolbox)
- **位置**: `modules/ai_agent/tool_registry.py`
- **功能**: 標準化所有現有功能為AI可用的工具
- **工具分類**:
  - **查詢類**: 東洋班次、診所班次、班次詳情、已完成班次
  - **修改類**: 指派司機、記錄車資、修改類別
  - **創建類**: 匯入固定班次、AI自然語言預約
  - **刪除類**: 清理trips資料
  - **系統類**: 批量操作、報表生成

### 3. 知識庫 (Knowledge Base)
- **位置**: `modules/ai_agent/knowledge_base.py`
- **內容**:
  - 資料庫 Schema (trips, fixed_schedules, completed_trips, drivers, customers)
  - 業務規則 (班次狀態流程、時間態架構、司機指派規則)
  - 使用範例 (自然語言→工具映射)
  - 系統信息 (時區、格式、當前狀態)

### 4. 規劃器與執行器 (Planner & Executor)
- **位置**: `modules/ai_agent/agent_core.py`
- **工作流程**:
  1. **思考階段**: 理解用戶意圖
  2. **檢索階段**: 查找相關背景知識
  3. **規劃階段**: 制定工具使用計劃
  4. **執行階段**: 動態調用工具
  5. **回應階段**: 生成自然語言回答

### 5. AI路由器 (AI Router)
- **位置**: `modules/ai_agent/ai_router.py`
- **功能**: 智能判斷是否使用AI Agent處理
- **路由策略**:
  - 精確命令 → 傳統處理
  - 自然語言 → AI Agent
  - 複雜場景 → AI Agent
  - 多步驟請求 → AI Agent

## 工作流程

### 用戶請求處理流程
```
用戶輸入 → AI路由器 → AI Agent核心 → 工具執行 → 結果回應
    ↓              ↓           ↓           ↓         ↓
消息前處理     路由決策     思考規劃     動態調用   自然語言
```

### 示例：處理「明天有什麼東洋班次？」
1. **思考**: 識別為班次查詢，需要日期轉換
2. **檢索**: 查找東洋班次查詢工具和日期處理規則
3. **規劃**: 使用 `query_dongyang_trips` 工具，參數 `{date: "tomorrow"}`
4. **執行**: 調用 `handle_query_dongyang_trips_flex("東洋班次 明天")`
5. **回應**: 生成友好的班次列表回復

## 實施階段

### 階段一：工具註冊表建立 ✅
- [x] 定義工具標準格式
- [x] 註冊現有功能為工具
- [x] 支援參數驗證和範例

### 階段二：知識庫建設 ✅
- [x] 資料庫結構定義
- [x] 業務規則整理
- [x] 使用範例收集

### 階段三：AI Agent核心 ✅
- [x] 思考-規劃-執行架構
- [x] 動態工具調用
- [x] 錯誤處理和回退

### 階段四：AI路由器集成 ✅
- [x] 智能路由決策
- [x] 傳統系統兼容
- [x] 集成到現有處理流程

### 階段五：測試和優化 🔄
- [x] 基本功能測試
- [ ] 真實場景測試
- [ ] 性能優化
- [ ] 錯誤處理完善

## 使用方式

### 開發者使用
```python
from modules.ai_agent import dispatch_agent

# 處理用戶請求
response = dispatch_agent.process_request("明天有什麼班次？", user_id)

# 檢查結果
if response.success:
    print(response.text)
else:
    print("處理失敗:", response.text)
```

### 系統自動集成
系統會自動判斷是否使用AI Agent：
- 傳統命令格式 → 保持原有處理方式
- 自然語言表達 → 使用AI Agent處理
- 複雜邏輯場景 → 使用AI Agent處理

## 優勢

### 1. 向後兼容
- 所有現有命令格式保持不變
- 用戶可以繼續使用熟悉的命令
- 系統穩定性不受影響

### 2. 自然語言支持
- 「今天有什麼班次？」
- 「幫我查一下明天的東洋班次」
- 「司機5386今天有哪些班次？」

### 3. 複雜邏輯處理
- 「如果明天下雨，班次要怎麼安排？」
- 「查一下昨天完成的班次，然後生成報表」
- 「司機5386請假了，幫我重新安排他的班次」

### 4. 擴展性
- 新增功能只需註冊工具
- 不需要修改 if/else 邏輯
- AI自動學習新功能使用

## 配置選項

### 環境變數
```bash
# Gemini API配置
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash-thinking-exp-1219

# AI Agent配置
AI_AGENT_ENABLED=true
AI_CONFIDENCE_THRESHOLD=0.6
AI_FALLBACK_ENABLED=true
```

### 系統設定
```python
# 在 config.py 中
AI_AGENT_SETTINGS = {
    "enabled": True,
    "confidence_threshold": 0.6,
    "fallback_to_traditional": True,
    "max_execution_time": 30,
    "debug_mode": False
}
```

## 監控和日誌

### 日誌記錄
- 路由決策記錄
- AI處理過程追蹤
- 工具執行結果
- 錯誤和異常處理

### 性能監控
- 響應時間統計
- 成功率統計
- 工具使用頻率
- 用戶滿意度

## 未來擴展

### 短期改進
- [ ] 添加更多工具
- [ ] 優化提示詞
- [ ] 增強錯誤處理
- [ ] 添加用戶偏好學習

### 長期願景
- [ ] 多輪對話支持
- [ ] 語音交互
- [ ] 預測性建議
- [ ] 智能決策支援

## 故障排除

### 常見問題
1. **AI無法理解請求**: 檢查提示詞設定
2. **工具調用失敗**: 檢查工具註冊和參數
3. **回應太慢**: 檢查Gemini API配置
4. **回退到傳統處理**: 檢查路由器設定

### 調試方法
```python
# 啟用調試模式
import logging
logging.getLogger('modules.ai_agent').setLevel(logging.DEBUG)

# 測試特定請求
from modules.ai_agent.ai_router import ai_router
decision = ai_router.should_use_ai_agent("測試請求")
print(f"路由決策: {decision}")
```

## 結論

AI Agent架構成功實現了 Gemini 建議的願景，將系統從硬編碼的命令處理轉換為智能的自然語言處理。系統保持了向後兼容性，同時增加了強大的AI能力，為未來的擴展奠定了堅實基礎。 