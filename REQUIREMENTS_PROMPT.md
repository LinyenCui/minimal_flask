# 智能派班系統優化需求 PRP (Priority Requirement Prompt)

name: "LINE Bot派班系統系統性重構與BUG修復"
description: |

## Purpose
基於context-engineering方法論，系統性修復智能派班系統的關鍵技術債務，提升系統穩定性與可維護性，同時保持現有功能的完整性。

## Core Principles
1. **穩定性優先**: 修復關鍵BUG，確保生產環境正常運作
2. **架構統一**: 消除重複實現，建立一致性架構模式
3. **功能透明**: 明確區分真AI功能與本地算法，避免用戶誤導
4. **測試驅動**: 建立完整測試框架，確保重構安全性
5. **遵循CLAUDE.md**: 嚴格按照專案規範執行開發

---

## Goal
系統性修復智能LINE Bot派班管理系統的重大技術債務，建立穩定可維護的架構基礎，為後續功能擴展做好準備。

## Why
- **業務連續性**: 修復影響生產環境的關鍵BUG，確保24/7穩定運行
- **開發效率**: 統一重複實現，降低維護成本，提升開發速度
- **用戶信任**: 修復功能標示問題，建立透明誠實的用戶體驗
- **技術擴展**: 建立良好架構基礎，支撐未來AI功能擴展

## What
**第一階段：關鍵BUG修復 (P0優先級)**
1. 修復Quick Reply按鈕action.text屬性缺失問題
2. 統一日期解析函數，解決"昨天"查詢差異問題
3. 修復Render端AI信心度異常問題

**第二階段：架構重構 (P1優先級)**  
1. 重構text_message_handler.py，拆分為專責處理器
2. 建立完整測試框架，確保功能穩定性
3. 統一AI調用邏輯，明確功能標示

### Success Criteria
- [ ] Quick Reply按鈕400錯誤完全消除
- [ ] 本地與Render環境查詢結果100%一致
- [ ] AI信心度在兩端環境表現一致
- [ ] text_message_handler.py檔案大小減少60%以上
- [ ] 核心功能測試覆蓋率達到80%以上
- [ ] 所有"AI智能搜索"標示與實際技術實現一致

## All Needed Context

### Documentation & References (list all context needed to implement the feature)
```yaml
# MUST READ - Include these in your context window
- url: https://developers.line.biz/en/docs/messaging-api/
  why: Quick Reply按鈕格式規範，action.text屬性要求
  
- file: docs/AI_TRUTH_REPORT.md
  why: 理解AI功能真實性問題，區分真AI vs包裝算法
  
- file: docs/REFACTOR_DUPLICATE_FUNCTIONS.md 
  why: 日期解析重複實現的系統性解決方案
  critical: 統一使用unified_date_parser.py避免環境差異

- docfile: docs/logs/claude健檢建議.txt
  why: 完整的程式碼品質分析，重構指導原則

- docfile: docs/logs/有一點回魂了.txt
  why: Render端AI配置問題深度分析，環境差異排查方法

- file: docs/logs/日誌0202.txt
  why: 實際運行日誌，了解系統響應模式與性能表現

- file: CLEANUP_REPORT.md
  why: 已清理檔案列表，避免影響不存在的檔案
```

### Current Codebase tree (run `tree` in the root of the project) to get an overview of the codebase
```bash
minimal_flask/
├── modules/
│   ├── handlers/          # 🚨需重構
│   │   ├── text_message_handler.py    # 檔案過大，需拆分
│   │   ├── temp_booking_handler.py    # ✅真AI功能
│   │   └── fixed_schedule_*_handler.py
│   ├── services/          # 核心服務層
│   │   ├── smart_assistant.py         # 🤖 Gemini整合
│   │   ├── ai_fare_service.py         # 🎭 包裝本地算法
│   │   └── advanced_query_processor.py
│   ├── utils/             # 工具函數庫
│   │   ├── unified_date_parser.py     # ✅統一日期解析
│   │   └── conversation_context.py
│   └── flex_designs/      # LINE Bot UI設計
├── docs/logs/             # 📋 運行日誌與問題追蹤  
├── tests/                 # 🚨缺乏完整測試框架
└── CLEANUP_BACKUP/        # 已清理檔案備份
```

### Desired Codebase tree with files to be added and responsibility of file
```bash
modules/
├── handlers/           # 拆分後的專責處理器
│   ├── booking_handler.py      # ✅已存在，真AI功能
│   ├── query_handler.py        # 📋新增：從text_message_handler拆出
│   ├── status_handler.py       # 📋新增：從text_message_handler拆出  
│   ├── conversation_handler.py # 📋新增：對話狀態管理
│   └── text_message_handler.py # 📋重構：大幅縮減，只保留路由功能
├── services/          # 統一業務邏輯
│   ├── ai_service.py          # 📋新增：統一AI調用入口
│   ├── query_service.py       # 📋新增：統一查詢邏輯
│   └── notification_service.py # 📋新增：統一通知服務  
├── utils/             # 統一工具函數
│   ├── unified_date_parser.py # ✅已存在
│   ├── response_formatter.py  # 📋新增：統一回應格式
│   └── validation_utils.py    # 📋新增：統一驗證邏輯
└── tests/             # 完整測試框架
    ├── test_handlers.py       # 📋新增：處理器測試
    ├── test_services.py       # 📋新增：服務層測試
    ├── test_integration.py    # 📋新增：整合測試
    └── test_ai_functionality.py # 📋新增：AI功能測試
```

### Known Gotchas of our codebase & Library Quirks
```python
# CRITICAL: LINE Bot API Quick Reply格式要求
# action必須包含text屬性，否則400錯誤
{
    "type": "action", 
    "action": {
        "type": "postback",
        "text": "顯示文字",      # 🚨必須存在
        "data": "action_data",
        "displayText": "用戶看到的文字"
    }
}

# CRITICAL: 日期解析統一模式  
from modules.utils.unified_date_parser import UnifiedDateParser
# ❌不要import其他parse_date_input實現

# CRITICAL: 環境變數依賴
# Render端必須正確設定，否則AI功能降級
os.environ['TZ'] = 'Asia/Taipei'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './path/to/key.json'

# CRITICAL: AI信心度閾值機制
# 信心度<0.8會觸發用戶確認流程
confidence_threshold = 0.8  # 生產環境標準值

# CRITICAL: 回應時間指標
# 真AI功能: >1秒, 本地算法: <0.1秒
# 用於判斷功能分類的重要指標
```

## Implementation Blueprint

### Data models and structure

維持現有三時間態架構，重點修復資料處理邏輯：
```python
# 統一日期解析模型
class UnifiedDateParser:
    @staticmethod
    def parse(date_input: str) -> dict:
        """統一日期解析接口，替代所有重複實現"""
        # 支援: "昨天", "7/25", "2025-07-25"等格式
        
# 統一回應格式模型  
class ResponseFormatter:
    @staticmethod  
    def format_flex_message(data: dict, message_type: str) -> dict:
        """統一Flex訊息格式，確保action.text屬性存在"""
        
# AI功能分類模型
class AIFunctionClassifier:
    @staticmethod
    def is_real_ai_function(function_name: str) -> bool:
        """明確區分真AI功能與本地算法"""
```

### list of tasks to be completed to fullfill the PRP in the order they should be completed

```yaml
Task 1: 修復Quick Reply按鈕格式問題
MODIFY modules/flex_designs/ai_fare_query_flex.py:
  - FIND pattern: "action.*postback"
  - INJECT "text" field for all Quick Reply actions
  - PRESERVE existing data and displayText fields
  - TEST with actual LINE Bot to confirm 400 error resolution

Task 2: 統一日期解析實現
CREATE modules/utils/response_formatter.py:
  - IMPLEMENT unified Quick Reply format validation
  - ENSURE all action objects contain required text attribute
  - PROVIDE backward compatibility for existing code

MODIFY modules/services/ai_fare_service.py:
  - REPLACE local parse_date_input with UnifiedDateParser.parse
  - REMOVE duplicate implementation 
  - VERIFY "昨天" query returns consistent results

MODIFY modules/handlers/trip_query_handler.py:
  - REPLACE local parse_date_input with UnifiedDateParser.parse
  - REMOVE duplicate implementation
  
Task 3: 修復Render端AI信心度問題
CREATE modules/services/ai_service.py:
  - IMPLEMENT unified AI calling interface
  - ADD environment validation for API credentials
  - PROVIDE fallback mechanism when AI unavailable
  - LOG actual confidence scores for debugging

Task 4: 重構text_message_handler.py
CREATE modules/handlers/query_handler.py:
  - EXTRACT query-related functions from text_message_handler.py
  - MIRROR existing logic structure
  - MAINTAIN backward compatibility

CREATE modules/handlers/status_handler.py:
  - EXTRACT status-related functions from text_message_handler.py
  - IMPLEMENT unified status update logic
  - PRESERVE existing Flex message formats

MODIFY modules/handlers/text_message_handler.py:
  - REDUCE to routing logic only
  - DELEGATE specific tasks to specialized handlers
  - MAINTAIN existing API contracts

Task 5: 建立測試框架
CREATE tests/test_date_parsing.py:
  - TEST unified date parser with all supported formats
  - VERIFY environment consistency (local vs Render)
  - INCLUDE edge cases and error handling

CREATE tests/test_quick_reply_format.py:
  - TEST all Flex messages have valid Quick Reply format
  - VERIFY action.text attribute presence
  - SIMULATE LINE Bot API validation

CREATE tests/test_ai_functionality.py:
  - TEST AI confidence score consistency
  - VERIFY fallback mechanism works correctly
  - DISTINGUISH real AI vs local algorithm execution
```

### Per task pseudocode as needed added to each task

```python
# Task 1: Quick Reply修復範例
def fix_quick_reply_format(quick_reply_data):
    """
    修復Quick Reply格式，確保包含必要的text屬性
    """
    for item in quick_reply_data.get('items', []):
        if item['type'] == 'action':
            action = item['action']
            if action['type'] == 'postback':
                # CRITICAL: 確保text屬性存在
                if 'text' not in action:
                    action['text'] = action.get('displayText', 'Action')
    return quick_reply_data

# Task 2: 日期解析統一範例  
def unified_date_handling(date_input):
    """
    統一日期解析，替代所有重複實現
    """
    # PATTERN: 統一使用UnifiedDateParser
    from modules.utils.unified_date_parser import UnifiedDateParser
    
    try:
        parsed_result = UnifiedDateParser.parse(date_input)
        return parsed_result
    except Exception as e:
        # PATTERN: 統一錯誤處理
        logger.error(f"Date parsing failed: {e}")
        return None

# Task 3: AI信心度修復範例
def check_ai_confidence_consistency():
    """
    檢查AI信心度在不同環境的一致性
    """
    # PATTERN: 環境配置檢查
    required_env_vars = [
        'GOOGLE_APPLICATION_CREDENTIALS',
        'GEMINI_API_KEY', 
        'TZ'
    ]
    
    for var in required_env_vars:
        if not os.getenv(var):
            logger.warning(f"Missing environment variable: {var}")
            return False
    
    # PATTERN: AI調用標準化
    try:
        response = ai_client.analyze("測試查詢", timeout=30)
        confidence = response.get('confidence', 0.0)
        
        # CRITICAL: 記錄信心度以供調試
        logger.info(f"AI confidence: {confidence}")
        return confidence >= 0.8
        
    except Exception as e:
        # PATTERN: 必須有fallback機制
        logger.error(f"AI call failed, using fallback: {e}")
        return False
```

### Integration Points
```yaml
DATABASE:
  - No schema changes required
  - Existing three-time-state architecture maintained
  - Performance optimization through unified query patterns
  
CONFIG:
  - Validate Render environment variables
  - Ensure GOOGLE_APPLICATION_CREDENTIALS path is correct
  - Verify TZ=Asia/Taipei setting for date parsing consistency
  
ROUTES:
  - Maintain existing webhook endpoints
  - Preserve LINE Bot API contracts
  - Add health check endpoint for environment validation
  
AI_SERVICES:
  - Unify Gemini API calling patterns
  - Standardize confidence score handling
  - Implement consistent fallback mechanisms
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Run these FIRST - fix any errors before proceeding
python -m py_compile modules/utils/response_formatter.py
python -m py_compile modules/services/ai_service.py
python -m py_compile modules/handlers/query_handler.py

# Expected: No syntax errors. If errors, READ the error and fix.
```

### Level 2: Unit Tests each new feature/file/function use existing test patterns
```python
# CREATE test_quick_reply_format.py with these test cases:
def test_quick_reply_has_text_attribute():
    """Quick Reply按鈕必須包含text屬性"""
    quick_reply = generate_quick_reply_buttons()
    for item in quick_reply['items']:
        assert 'text' in item['action']

def test_date_parsing_consistency():
    """日期解析在不同環境下結果一致"""
    test_dates = ["昨天", "今天", "7/25", "2025-07-25"]
    for date_str in test_dates:
        result = UnifiedDateParser.parse(date_str)
        assert result is not None
        assert 'date' in result

def test_ai_confidence_fallback():
    """AI調用失敗時fallback機制工作正常"""
    with mock.patch('ai_client.analyze', side_effect=Exception("API Error")):
        result = smart_assistant.process("查詢命令")
        assert result is not None  # 不應該因為AI失敗而中斷
        assert result.get('source') == 'fallback'
```

```bash
# Run and iterate until passing:
python -m pytest tests/test_quick_reply_format.py -v
python -m pytest tests/test_date_parsing.py -v
python -m pytest tests/test_ai_functionality.py -v
# If failing: Read error, understand root cause, fix code, re-run
```

### Level 3: Integration Test
```bash
# Test actual LINE Bot functionality
python test_line_bot_integration.py

# Test environment consistency
python test_render_local_consistency.py

# Expected: All Quick Reply buttons work, date queries consistent
# If error: Check logs for specific failure points
```

## Final validation Checklist
- [ ] Quick Reply按鈕在LINE Bot中正常工作，無400錯誤
- [ ] "昨天"查詢在本地和Render返回相同結果數量
- [ ] AI信心度在兩端環境表現一致
- [ ] text_message_handler.py檔案大小明顯減少
- [ ] 所有新建測試通過: `python -m pytest tests/ -v`
- [ ] 手動測試成功: 發送測試訊息到LINE Bot群組
- [ ] 日誌顯示統一的日期解析和AI調用模式
- [ ] 功能標示與實際技術實現一致

---

## Anti-Patterns to Avoid
- ❌ 不要創建新的日期解析函數，統一使用UnifiedDateParser
- ❌ 不要跳過Quick Reply的text屬性驗證
- ❌ 不要忽略環境變數差異，必須驗證Render配置  
- ❌ 不要讓AI調用失敗影響核心功能，必須有fallback
- ❌ 不要在沒有測試的情況下重構大型檔案
- ❌ 不要修改現有API契約，保持向後兼容性