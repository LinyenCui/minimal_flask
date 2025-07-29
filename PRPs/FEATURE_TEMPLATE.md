name: "新功能開發PRP模板 - 派班系統專用"
description: |

## Purpose  
專門針對企業級派班系統的新功能開發PRP模板，整合AI智能助手、三時間態架構、Line Bot等核心組件的功能擴展指南。

---

## Feature Specification

### Feature Name
[功能名稱 - 簡潔描述]

### Category
🤖 AI Enhancement | 📱 Line Bot Feature | 📊 Analytics | 🔧 System Tool | 📋 Business Logic

### Priority & Impact
**Business Priority**: 🔴 Critical | 🟡 Important | 🟢 Nice-to-have  
**Technical Complexity**: 🔴 High | 🟡 Medium | 🟢 Low
**User Impact**: [影響的用戶群體和使用場景]

## Feature Requirements

### User Stories
```yaml
作為 [用戶角色]:
  我希望 [具體需求]
  以便 [業務價值]
  
接受條件:
  - [可測試的條件1]
  - [可測試的條件2]
  - [可測試的條件3]
```

### Functional Requirements
- [具體功能要求1]
- [具體功能要求2]
- [與現有功能的整合要求]

### Non-Functional Requirements
- **Performance**: [響應時間、吞吐量要求]
- **Reliability**: [可用性、容錯要求]  
- **Scalability**: [擴展性考慮]
- **Security**: [安全性要求]

## System Integration Analysis

### Three-State Architecture Integration
```yaml
FUTURE_STATE (fixed_schedules):
  - integration: [如何與未來態整合]
  - data_flow: [資料流向]
  
CURRENT_STATE (trips):  
  - integration: [如何與現在態整合]
  - state_transitions: [狀態轉換邏輯]
  
PAST_STATE (completed_trips):
  - integration: [如何與過去態整合]  
  - analytics: [分析需求]
```

### AI System Integration
```yaml
SMART_ASSISTANT:
  - natural_language: [自然語言處理需求]
  - intent_recognition: [意圖識別要求]
  - confidence_handling: [信心度處理]
  
AI_ROUTING:
  - decision_logic: [路由決策邏輯]
  - fallback_strategy: [降級策略]
  
UNIFIED_PARSING:
  - date_parsing: [日期解析需求]
  - entity_extraction: [實體提取需求]
```

### Line Bot Integration
```yaml
MESSAGE_TYPES:
  - text: [文字訊息處理]
  - flex: [Flex Message設計]  
  - quick_reply: [Quick Reply選項]
  
WEBHOOK_HANDLING:
  - event_types: [處理的事件類型]
  - response_format: [回應格式要求]
  
USER_EXPERIENCE:
  - conversation_flow: [對話流程設計]
  - error_handling: [錯誤處理體驗]
```

## Technical Design

### Architecture Components
```python
# 新增或修改的主要組件
components/
├── [component1]/
│   ├── service.py           # 業務邏輯
│   ├── handler.py           # 請求處理  
│   ├── models.py            # 資料模型
│   └── utils.py             # 輔助函數
├── [component2]/
└── integrations/
    ├── ai_integration.py     # AI系統整合
    ├── linebot_integration.py # Line Bot整合
    └── database_integration.py # 資料庫整合
```

### Data Models
```python
# 新增的資料結構
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass  
class [FeatureName]Data:
    """新功能的核心資料模型"""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    # [其他欄位]
    
    def to_dict(self) -> dict:
        """轉換為字典格式，用於API回應"""
        return {
            # 遵循現有API格式標準
        }
    
    @classmethod
    def from_db_row(cls, row) -> '[FeatureName]Data':
        """從資料庫記錄創建實例"""
        return cls(
            # 遵循現有ORM模式
        )
```

### Database Schema Changes
```sql
-- 新增表格（如需要）
CREATE TABLE IF NOT EXISTS [table_name] (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- [其他欄位]
    
    -- 外鍵關聯
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    -- 索引優化
    INDEX idx_[table_name]_lookup ([key_columns])
);

-- 修改現有表格（如需要）  
ALTER TABLE [existing_table] 
ADD COLUMN [new_column] [type] DEFAULT [default_value];

-- 更新序列（重要！）
SELECT setval('[table_name]_id_seq', COALESCE(MAX(id), 1)) FROM [table_name];
```

## Implementation Plan

### Phase 1: Core Implementation
```yaml
Task 1.1: 資料層實現
FILES:
  - CREATE modules/models/[feature]_models.py
  - MODIFY modules/utils/database_helpers.py (if needed)
DEPENDENCIES:
  - 確保PostgreSQL序列正確
  - 遵循現有資料模型模式

Task 1.2: 服務層實現  
FILES:
  - CREATE modules/services/[feature]_service.py
PATTERNS:
  - 參考 modules/services/smart_assistant.py
  - 使用統一錯誤處理模式
  - 整合unified_date_parser

Task 1.3: 處理器實現
FILES:
  - MODIFY modules/handlers/text_message_handler.py
  - OR CREATE modules/handlers/[feature]_handler.py
CAUTION:
  - text_message_handler.py已經很大，謹慎修改
  - 考慮創建獨立handler
```

### Phase 2: AI Integration
```yaml  
Task 2.1: AI助手擴展
FILES:
  - MODIFY modules/services/smart_assistant.py
  - UPDATE modules/ai_agent/tool_registry.py
REQUIREMENTS:
  - 添加新的意圖識別
  - 註冊新工具到AI Agent
  - 更新prompt範本

Task 2.2: 智能路由
FILES:  
  - MODIFY modules/ai_agent/ai_router.py
LOGIC:
  - 定義何時使用新功能
  - 設置信心度閾值
  - 實現fallback機制
```

### Phase 3: Line Bot Integration
```yaml
Task 3.1: Flex Message設計
FILES:
  - CREATE modules/flex_designs/[feature]_flex.py
REQUIREMENTS:
  - 遵循現有Flex Message模式
  - 確保QuickReply格式正確（包含text屬性）
  - 支持多種螢幕尺寸

Task 3.2: Webhook處理
FILES:
  - MODIFY modules/routes/webhook.py
  - UPDATE modules/handlers/message_handler.py
PATTERNS:
  - 使用reply_message而非push_message
  - 遵循現有訊息處理流程
```

### Phase 4: Testing & Validation
```yaml
Task 4.1: 單元測試
FILES:
  - CREATE tests/test_[feature].py
COVERAGE:
  - 核心業務邏輯
  - 錯誤處理分支
  - AI整合功能

Task 4.2: 整合測試
FILES:
  - CREATE tests/integration/test_[feature]_integration.py
SCENARIOS:
  - 端到端功能測試
  - Line Bot互動測試
  - AI路由決策測試

Task 4.3: 環境一致性
VERIFY:
  - 本地環境功能正常
  - Render環境行為一致
  - 資料庫序列同步
```

## Code Implementation Templates

### Service Layer Template
```python
# modules/services/[feature]_service.py
"""
[功能名稱] 服務
負責 [具體職責描述]
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# 統一導入
from modules.utils.unified_date_parser import UnifiedDateParser
from modules.utils.helpers import get_taiwan_time
from modules.utils.database_helpers import get_db_connection

logger = logging.getLogger(__name__)

class [FeatureName]Service:
    """[功能名稱] 核心服務類"""
    
    def __init__(self):
        """初始化服務"""
        self.logger = logger
        
    async def process_request(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """
        處理用戶請求的主要入口
        
        Args:
            user_input: 用戶輸入文字
            user_id: Line用戶ID
            
        Returns:
            處理結果字典
        """
        try:
            # PATTERN: 輸入驗證和標準化
            normalized_input = self._normalize_input(user_input)
            
            # PATTERN: 使用統一日期解析器
            date_info = self._extract_date_info(normalized_input)
            
            # PATTERN: 核心業務邏輯
            result = await self._execute_business_logic(normalized_input, date_info, user_id)
            
            # PATTERN: 標準化回應格式
            return self._format_response(result)
            
        except ValueError as e:
            self.logger.warning(f"輸入驗證失敗: {e}")
            return self._error_response("輸入格式錯誤，請檢查後重試")
            
        except Exception as e:
            self.logger.error(f"服務處理失敗: {e}", exc_info=True)
            return self._error_response("系統暫時無法處理請求，請稍後重試")
    
    def _normalize_input(self, user_input: str) -> str:
        """標準化用戶輸入"""
        # 遵循現有的輸入處理模式
        return user_input.strip().lower()
    
    def _extract_date_info(self, input_text: str) -> Optional[datetime]:
        """提取日期資訊"""
        # CRITICAL: 使用統一日期解析器
        try:
            return UnifiedDateParser.parse(input_text)
        except ValueError:
            return None
    
    async def _execute_business_logic(self, input_text: str, date_info: Optional[datetime], user_id: str) -> Any:
        """執行核心業務邏輯"""
        # 實現具體的功能邏輯
        pass
    
    def _format_response(self, result: Any) -> Dict[str, Any]:
        """格式化回應"""
        return {
            "success": True,
            "data": result,
            "timestamp": get_taiwan_time().isoformat()
        }
    
    def _error_response(self, message: str) -> Dict[str, Any]:
        """錯誤回應格式"""
        return {
            "success": False,
            "error": message,
            "timestamp": get_taiwan_time().isoformat()
        }
```

### AI Integration Template
```python
# modules/ai_agent/tools/[feature]_tools.py
"""
[功能名稱] AI工具註冊
"""

from modules.ai_agent.tool_registry import register_tool
from modules.services.[feature]_service import [FeatureName]Service

@register_tool
def [feature]_tool(user_input: str, user_id: str):
    """
    [功能描述] AI工具
    
    用於處理自然語言請求，例如：
    - "查詢 [具體例子]"
    - "[其他使用場景]"
    """
    service = [FeatureName]Service()
    return service.process_request(user_input, user_id)

# 工具元資料
[feature]_tool.metadata = {
    "name": "[功能名稱]",
    "description": "[功能描述]",
    "parameters": {
        "user_input": "用戶自然語言輸入",
        "user_id": "Line用戶ID"
    },
    "examples": [
        "查詢 [例子1]",
        "[例子2]",
        "[例子3]"
    ]
}
```

### Line Bot Handler Template
```python
# modules/handlers/[feature]_handler.py
"""
[功能名稱] Line Bot 處理器
"""

import logging
from linebot.v3.messaging import (
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    QuickReply,
    QuickReplyItem,
    PostbackAction
)

from modules.services.[feature]_service import [FeatureName]Service
from modules.flex_designs.[feature]_flex import create_[feature]_flex
from modules.utils.line_bot import get_line_bot_api

logger = logging.getLogger(__name__)

class [FeatureName]Handler:
    """[功能名稱] Line Bot處理器"""
    
    def __init__(self):
        self.service = [FeatureName]Service()
        self.line_bot_api = get_line_bot_api()
    
    async def handle_[feature]_request(self, event):
        """處理[功能名稱]請求"""
        try:
            user_input = event.message.text
            user_id = event.source.user_id
            reply_token = event.reply_token
            
            # 呼叫服務層處理
            result = await self.service.process_request(user_input, user_id)
            
            if result["success"]:
                # 創建Flex Message回應
                flex_message = create_[feature]_flex(result["data"])
                
                # CRITICAL: 確保QuickReply格式正確
                quick_reply = QuickReply(items=[
                    QuickReplyItem(
                        action=PostbackAction(
                            label="[選項1]",
                            data="action=[action1]",
                            text="[選項1]"  # ← 必須包含text屬性
                        )
                    ),
                    # 更多選項...
                ])
                
                # 使用reply_message（遵循免費政策）
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[FlexMessage(
                            alt_text="[功能名稱]查詢結果",
                            contents=flex_message,
                            quick_reply=quick_reply
                        )]
                    )
                )
            else:
                # 錯誤處理
                error_message = TextMessage(text=result["error"])
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[error_message]
                    )
                )
                
        except Exception as e:
            logger.error(f"[功能名稱]處理失敗: {e}", exc_info=True)
            # 發送通用錯誤訊息
            error_message = TextMessage(text="系統暫時無法處理請求，請稍後重試")
            self.line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[error_message]
                )
            )
```

## Testing Strategy

### Unit Test Template
```python
# tests/test_[feature].py
"""[功能名稱] 單元測試"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from modules.services.[feature]_service import [FeatureName]Service

class Test[FeatureName]Service:
    """[功能名稱]服務測試"""
    
    def setUp(self):
        self.service = [FeatureName]Service()
    
    @pytest.mark.asyncio
    async def test_process_request_success(self):
        """測試正常請求處理"""
        # Arrange
        user_input = "[測試輸入]"
        user_id = "test_user_123"
        
        # Act  
        result = await self.service.process_request(user_input, user_id)
        
        # Assert
        assert result["success"] is True
        assert "data" in result
        assert "timestamp" in result
    
    @pytest.mark.asyncio  
    async def test_process_request_invalid_input(self):
        """測試無效輸入處理"""
        # Arrange
        user_input = ""
        user_id = "test_user_123"
        
        # Act
        result = await self.service.process_request(user_input, user_id)
        
        # Assert
        assert result["success"] is False
        assert "error" in result
    
    def test_date_parsing_integration(self):
        """測試日期解析整合"""
        # 確保使用統一日期解析器
        with patch('modules.utils.unified_date_parser.UnifiedDateParser.parse') as mock_parse:
            mock_parse.return_value = datetime.now().date()
            
            date_info = self.service._extract_date_info("昨天")
            
            mock_parse.assert_called_once_with("昨天")
            assert date_info is not None
```

## Deployment Checklist

### Pre-Deployment
- [ ] 所有單元測試通過
- [ ] 整合測試通過  
- [ ] 環境一致性驗證完成
- [ ] 資料庫遷移腳本準備就緒
- [ ] 設定檔案更新完成
- [ ] 日誌輸出適當且有用

### Deployment Steps
- [ ] 備份現有系統
- [ ] 執行資料庫遷移
- [ ] 部署應用程式代碼
- [ ] 修復PostgreSQL序列（如適用）
- [ ] 驗證核心功能正常
- [ ] 監控錯誤日誌

### Post-Deployment
- [ ] 功能驗證測試
- [ ] 效能監控
- [ ] 用戶反饋收集
- [ ] 文檔更新完成

---

## Feature-Specific Considerations

### For AI Enhancement Features
- 確保與現有AI路由器整合
- 考慮信心度和fallback機制
- 更新工具註冊表和prompt範本

### For Line Bot Features  
- 遵循免費政策限制
- 確保Flex Message格式正確
- 考慮不同裝置的顯示效果

### For Analytics Features
- 遵循三時間態資料流轉
- 考慮大資料量的效能影響
- 設計適當的資料索引

### For System Tools
- 考慮對現有功能的影響
- 實現適當的權限控制
- 提供詳細的操作日誌