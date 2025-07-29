name: "派班系統PRP模板 v1 - 基於生產線思維的Context-Rich模板"
description: |

## Purpose
專為企業級自動化派班管理系統優化的PRP模板，整合AI智能助手、Line Bot、三時間態架構等核心功能的上下文感知開發模板。

## Core Principles
1. **生產線思維**: 遵循未來態→現在態→過去態的時間流轉
2. **統一解析**: 避免重複實現，使用統一的解析器和服務
3. **AI優先**: 優先考慮自然語言處理和智能路由
4. **環境一致**: 確保本地和Render部署環境行為一致
5. **遵循系統規則**: 嚴格遵循INITIAL.md和現有架構模式

---

## Goal
[描述需要實現的具體功能 - 明確最終狀態和期望結果]

## Why
- [業務價值和用戶影響]
- [與現有三時間態架構的整合方式]
- [解決的問題和受益對象]
- [對派班效率的提升]

## What
[用戶可見行為和技術要求]

### Success Criteria
- [ ] [具體可測量的成果指標]
- [ ] [與Line Bot的集成測試通過]
- [ ] [AI智能助手正確理解並處理請求]
- [ ] [本地和Render環境行為一致]

## All Needed Context

### Documentation & References
```yaml
# 必讀文檔 - 包含在context window中
- file: INITIAL.md
  why: 系統概覽、已知問題、技術債務清單
  
- file: docs/AI_AGENT_ARCHITECTURE.md  
  why: AI Agent架構、工作流程、工具註冊標準
  
- file: docs/guides/PRODUCTION_LINE_DISPATCH_SYSTEM.md
  why: 生產線思維核心概念、三時間態設計
  
- file: modules/utils/unified_date_parser.py
  why: 統一日期解析器，避免重複實現災難
  critical: 所有日期解析必須使用此統一解析器
  
- file: modules/services/smart_assistant.py
  why: AI智能助手服務模式、Gemini集成標準
  
- file: modules/handlers/text_message_handler.py
  why: 訊息處理流程、路由決策模式
  gotcha: 檔案過大，需要謹慎修改，避免破壞現有功能
  
- file: docs/logs/cursor_5.txt
  why: 詳細的問題診斷和修復過程記錄
  critical: 了解6個重複日期解析函數造成的災難

- url: https://developers.line.biz/en/reference/messaging-api/
  section: Flex Message and Quick Reply格式
  critical: action.text屬性必須正確設置
```

### Current Codebase tree
```bash
minimal_flask/
├── app.py                          # 主應用入口
├── modules/
│   ├── handlers/                   # 訊息處理器
│   │   ├── text_message_handler.py # 🔴 過大檔案，需謹慎修改
│   │   └── trip_handler.py
│   ├── services/                   # 核心服務層
│   │   ├── smart_assistant.py      # AI智能助手
│   │   ├── ai_fare_service.py      # AI車資服務
│   │   └── advanced_query_processor.py
│   ├── utils/                      # 工具函數
│   │   ├── unified_date_parser.py  # ✅ 統一日期解析器
│   │   ├── helpers.py              # 🔴 含舊日期解析函數
│   │   └── line_bot.py
│   ├── flex_designs/               # Flex Message設計
│   └── ai_agent/                   # AI Agent架構
├── docs/                           # 完整文檔系統
├── scripts/                        # 維護腳本
└── tests/                          # 🔴 需要擴充的測試框架
```

### Desired Codebase tree (針對此功能添加的檔案)
```bash
# 在此描述需要添加/修改的檔案及其職責
```

### Known Gotchas & Critical Patterns
```python
# 🔴 CRITICAL: 日期解析統一使用
from modules.utils.unified_date_parser import UnifiedDateParser
date = UnifiedDateParser.parse(date_input)  # 絕不使用其他解析函數

# 🔴 CRITICAL: Line Bot免費政策
# ❌ 錯誤：會違反免費政策
line_bot_api.push_message(user_id, message)
# ✅ 正確：使用reply_message
line_bot_api.reply_message(reply_token, message)

# 🔴 CRITICAL: Quick Reply格式
quick_reply = {
    "type": "action", 
    "action": {
        "type": "postback",
        "label": "按鈕文字",
        "data": "action_data",
        "text": "必須有這個text屬性"  # ← 缺少會導致400錯誤
    }
}

# 🔴 CRITICAL: AI智能助手路由
# 遵循: 自然語言 → AI Agent, 精確命令 → 傳統處理
if ai_router.should_use_ai_agent(user_input):
    response = dispatch_agent.process_request(user_input, user_id)
else:
    response = traditional_handler.process(user_input)

# 🔴 CRITICAL: 資料庫查詢模式
# 使用三時間態概念
current_trips = query_current_state()      # trips表
completed_trips = query_past_state()       # completed_trips表
future_schedules = query_future_state()    # fixed_schedules表

# 🔴 CRITICAL: 錯誤處理標準
try:
    result = process_request()
except ValidationError as e:
    logger.error(f"輸入驗證失敗: {e}")
    return error_response("輸入格式錯誤")
except DatabaseError as e:
    logger.error(f"資料庫錯誤: {e}")
    return error_response("系統暫時無法處理請求")
```

## Implementation Blueprint

### Data models and structure
```python
# 遵循現有的資料模型模式
# 參考: modules/models/ (如果存在) 或 helpers.py中的資料結構
```

### Task List (按執行順序)
```yaml
Task 1: 準備工作
VERIFY modules/utils/unified_date_parser.py:
  - CHECK: UnifiedDateParser.parse()方法存在且正常
  - TEST: 相對日期("昨天", "明天")解析正確
  - ENSURE: 所有新代碼使用此統一解析器

Task 2: [具體任務]
MODIFY/CREATE [檔案路徑]:
  - FIND pattern: [現有模式]
  - FOLLOW pattern from: [參考檔案]
  - INTEGRATE with: [相關服務]
  - PRESERVE: [必須保持的功能]

...

Task N: 驗證與測試
VALIDATE environment consistency:
  - TEST: 本地環境功能正常
  - TEST: Render環境行為一致
  - CHECK: 無重複實現引入
  - VERIFY: AI智能助手正確路由
```

### Per Task Pseudocode
```python
# Task [N] 偽代碼
async def new_feature_handler(event, context):
    """
    遵循現有的handler模式
    參考: modules/handlers/text_message_handler.py
    """
    # PATTERN: 統一的用戶輸入處理
    user_input = normalize_input(event.message.text)
    user_id = event.source.user_id
    
    # PATTERN: AI路由決策
    if ai_router.should_use_ai_agent(user_input):
        # 使用AI Agent處理自然語言
        response = await smart_assistant.process(user_input, user_id)
    else:
        # 使用傳統處理流程
        response = await traditional_processor.handle(user_input)
    
    # PATTERN: 統一回應格式
    return format_line_response(response, reply_token=event.reply_token)

# CRITICAL: 日期相關處理
def process_date_query(date_input: str):
    """任何日期處理都必須使用統一解析器"""
    try:
        parsed_date = UnifiedDateParser.parse(date_input)
        return query_by_date(parsed_date)
    except ValueError as e:
        logger.warning(f"日期解析失敗: {date_input} -> {e}")
        return fallback_date_handling()
```

### Integration Points
```yaml
DATABASE:
  - tables: trips, completed_trips, fixed_schedules, drivers
  - indexes: "確保常用查詢有適當索引"
  - sequences: "注意PostgreSQL序列同步問題"
  
AI_SYSTEM:
  - smart_assistant: "自然語言理解和意圖識別"
  - ai_fare_service: "車資相關查詢處理"  
  - unified_date_parser: "所有日期解析統一入口"
  
LINE_BOT:
  - webhook: "訊息接收和驗證"
  - flex_message: "豐富的互動介面"
  - quick_reply: "快速回應選項"
  
CONFIG:
  - environment: "區分本地/Render環境設定"
  - gemini_api: "AI服務配置"
  - line_channel: "Line Bot憑證配置"
```

## Validation Loop

### Level 1: Syntax & Style  
```bash
# 執行順序很重要 - 先修復這些再繼續
python -m py_compile [new_file.py]     # 語法檢查
# 如果有linter: ruff check [new_file.py] --fix
```

### Level 2: Unit Tests
```python
# 創建 test_[feature].py，遵循現有測試模式
def test_date_parsing_consistency():
    """確保使用統一日期解析器"""
    from modules.utils.unified_date_parser import UnifiedDateParser
    
    # 測試相對日期
    yesterday = UnifiedDateParser.parse("昨天")
    assert yesterday is not None
    
    # 測試絕對日期
    absolute_date = UnifiedDateParser.parse("7/25")
    assert absolute_date is not None

def test_ai_routing_decision():
    """測試AI路由決策正確性"""
    # 自然語言應該路由到AI
    assert ai_router.should_use_ai_agent("昨天診所班次") == True
    
    # 精確命令應該使用傳統處理
    assert ai_router.should_use_ai_agent("班次詳情 2207") == False

def test_line_bot_response_format():
    """測試Line Bot回應格式正確"""
    response = create_flex_message(test_data)
    # 確保Quick Reply包含text屬性
    assert "text" in response.quick_reply.items[0].action
```

### Level 3: Integration Test
```bash
# 啟動本地服務測試
python app.py

# 測試Line Bot webhook（如果可行）
curl -X POST http://localhost:5000/callback \
  -H "Content-Type: application/json" \
  -d '{"events":[{"type":"message","message":{"type":"text","text":"測試訊息"}}]}'

# 測試AI功能
# [具體的測試命令]
```

### Level 4: Environment Consistency
```bash
# 關鍵：確保本地和Render環境一致
# 測試統一日期解析器
python -c "
from modules.utils.unified_date_parser import UnifiedDateParser
print('昨天:', UnifiedDateParser.parse('昨天'))
print('7/25:', UnifiedDateParser.parse('7/25'))
"

# 檢查時區設定
python -c "
from modules.utils.helpers import get_taiwan_time
print('台灣時間:', get_taiwan_time())
"
```

## Final Validation Checklist
- [ ] 統一日期解析器使用正確，無重複實現
- [ ] AI智能助手路由決策正確
- [ ] Line Bot回應格式符合API要求  
- [ ] 本地和Render環境行為一致
- [ ] 無語法錯誤和類型錯誤
- [ ] 單元測試全部通過
- [ ] 整合測試成功
- [ ] 日誌輸出有用且不過度冗長
- [ ] 遵循三時間態架構原則
- [ ] 符合現有程式碼風格和模式

---

## Anti-Patterns to Avoid (派班系統特定)
- ❌ 不要創建新的日期解析函數，統一使用UnifiedDateParser
- ❌ 不要使用push_message，會違反Line免費政策
- ❌ 不要忽略QuickReply的text屬性
- ❌ 不要破壞三時間態的資料流轉邏輯
- ❌ 不要繞過AI路由器直接處理自然語言
- ❌ 不要在沒有測試環境一致性的情況下部署
- ❌ 不要修改text_message_handler.py而不充分測試
- ❌ 不要硬編碼配置值，使用環境變數
- ❌ 不要忽略PostgreSQL序列同步問題
- ❌ 不要複製重複的錯誤處理邏輯