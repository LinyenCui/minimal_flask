#!/usr/bin/env python3
"""
自動PRP生成器 - 派班系統專用
根據bug報告和功能清單自動生成Context-Rich的PRP文件
"""

import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class PRPType(Enum):
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    ENHANCEMENT = "enhancement"

class Priority(Enum):
    CRITICAL = "🔴 Critical"
    MAJOR = "🟡 Major"  
    MINOR = "🟢 Minor"

class Complexity(Enum):
    HIGH = "🔴 High"
    MEDIUM = "🟡 Medium"
    LOW = "🟢 Low"

@dataclass
class BugReport:
    """Bug報告數據結構"""
    title: str
    description: str
    symptoms: List[str]
    expected_behavior: str
    actual_behavior: str
    environment: str = "Both"  # Local | Render | Both
    priority: Priority = Priority.MAJOR
    related_files: List[str] = None
    error_logs: List[str] = None
    reproduction_steps: List[str] = None
    
    def __post_init__(self):
        if self.related_files is None:
            self.related_files = []
        if self.error_logs is None:
            self.error_logs = []
        if self.reproduction_steps is None:
            self.reproduction_steps = []

@dataclass 
class FeatureRequest:
    """功能請求數據結構"""
    name: str
    description: str
    category: str  # AI Enhancement | Line Bot Feature | Analytics | System Tool | Business Logic
    priority: Priority = Priority.MAJOR
    complexity: Complexity = Complexity.MEDIUM
    user_stories: List[str] = None
    acceptance_criteria: List[str] = None
    integration_points: List[str] = None
    
    def __post_init__(self):
        if self.user_stories is None:
            self.user_stories = []
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []
        if self.integration_points is None:
            self.integration_points = []

class PRPGenerator:
    """PRP自動生成器"""
    
    def __init__(self, project_root: str = "/Users/linyancui/ai_experiments/minimal_flask"):
        self.project_root = Path(project_root)
        self.prp_dir = self.project_root / "PRPs"
        self.templates_dir = self.prp_dir / "templates"
        
        # 已知問題模式資料庫
        self.known_issues = {
            "date_parsing": {
                "pattern": "日期解析",
                "files": ["modules/utils/unified_date_parser.py", "modules/utils/helpers.py"],
                "diagnostic_commands": [
                    "python -c \"from modules.utils.unified_date_parser import UnifiedDateParser; print(UnifiedDateParser.parse('昨天'))\"",
                    "grep -r 'parse_date' modules/ --exclude='unified_date_parser.py'"
                ],
                "common_fixes": ["使用統一日期解析器", "檢查時區設定", "驗證環境一致性"]
            },
            "line_bot_api": {
                "pattern": "Line Bot API",
                "files": ["modules/utils/line_bot.py", "modules/handlers/text_message_handler.py"],
                "diagnostic_commands": [
                    "curl -X POST http://localhost:5000/callback -H 'Content-Type: application/json'",
                    "python -c \"from modules.flex_designs.trip_details_flex import get_trip_details_flex; print(get_trip_details_flex(2320))\""
                ],
                "common_fixes": ["檢查QuickReply格式", "使用reply_message而非push_message", "驗證Webhook設定"]
            },
            "ai_routing": {
                "pattern": "AI路由",
                "files": ["modules/ai_agent/ai_router.py", "modules/services/smart_assistant.py"],
                "diagnostic_commands": [
                    "python -c \"from modules.ai_agent.ai_router import ai_router; print(ai_router.should_use_ai_agent('測試'))\"",
                    "python scripts/test_ai_routing.py"
                ],
                "common_fixes": ["檢查信心度閾值", "驗證意圖識別", "確認fallback機制"]
            }
        }
        
        # 系統架構組件
        self.system_components = {
            "ai_system": ["modules/ai_agent/", "modules/services/smart_assistant.py"],
            "line_bot": ["modules/utils/line_bot.py", "modules/flex_designs/"],
            "database": ["modules/utils/database_helpers.py", "scripts/"],
            "handlers": ["modules/handlers/"],
            "services": ["modules/services/"],
            "utils": ["modules/utils/"]
        }

    def generate_bug_fix_prp(self, bug_report: BugReport) -> str:
        """生成Bug修復PRP"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"BUG_FIX_{bug_report.title.replace(' ', '_').upper()}_{timestamp}.md"
        
        # 分析bug模式
        issue_pattern = self._analyze_bug_pattern(bug_report)
        
        # 生成PRP內容
        content = self._generate_bug_fix_content(bug_report, issue_pattern)
        
        # 寫入檔案
        output_path = self.prp_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return str(output_path)

    def generate_feature_prp(self, feature_request: FeatureRequest) -> str:
        """生成新功能PRP"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"FEATURE_{feature_request.name.replace(' ', '_').upper()}_{timestamp}.md"
        
        # 分析功能整合點
        integration_analysis = self._analyze_feature_integration(feature_request)
        
        # 生成PRP內容
        content = self._generate_feature_content(feature_request, integration_analysis)
        
        # 寫入檔案
        output_path = self.prp_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return str(output_path)

    def _analyze_bug_pattern(self, bug_report: BugReport) -> Dict[str, Any]:
        """分析bug模式，匹配已知問題"""
        pattern_matches = {}
        
        description_lower = bug_report.description.lower()
        for pattern_name, pattern_info in self.known_issues.items():
            if pattern_info["pattern"].lower() in description_lower:
                pattern_matches[pattern_name] = pattern_info
        
        return {
            "matches": pattern_matches,
            "affected_components": self._identify_affected_components(bug_report.related_files),
            "suggested_diagnostics": self._get_relevant_diagnostics(pattern_matches)
        }

    def _analyze_feature_integration(self, feature_request: FeatureRequest) -> Dict[str, Any]:
        """分析功能整合點"""
        integration_points = {
            "three_state_architecture": self._analyze_three_state_integration(feature_request),
            "ai_system": self._analyze_ai_integration(feature_request),
            "line_bot": self._analyze_linebot_integration(feature_request),
            "database": self._analyze_database_integration(feature_request)
        }
        
        return integration_points

    def _generate_bug_fix_content(self, bug_report: BugReport, issue_pattern: Dict[str, Any]) -> str:
        """生成Bug修復PRP內容"""
        content = f'''name: "Bug修復PRP - {bug_report.title}"
description: |

## Bug Report
**Bug ID**: {bug_report.title.replace(' ', '_').upper()}
**Severity**: {bug_report.priority.value}
**Environment**: {bug_report.environment}

### Symptoms
{self._format_list(bug_report.symptoms)}

### Expected vs Actual Behavior
**Expected**: {bug_report.expected_behavior}
**Actual**: {bug_report.actual_behavior}
**Impact**: [對用戶/系統的影響]

## Root Cause Analysis

### Hypothesis
基於症狀分析和已知問題模式：
{self._format_pattern_analysis(issue_pattern)}

### Evidence
```bash
# 相關錯誤日誌
{self._format_list(bug_report.error_logs, prefix="# ")}

# 重現步驟
{self._format_list(bug_report.reproduction_steps, prefix="# ")}
```

### Related Known Issues
```yaml
{self._format_known_issues(issue_pattern.get("matches", {}))}
```

## Diagnostic Tools & Commands

### Environment Verification
```bash
{self._format_list(issue_pattern.get("suggested_diagnostics", []))}
```

### Component Analysis
```bash
# 檢查相關檔案
{self._format_list([f"grep -n 'TODO\\|FIXME\\|BUG' {file}" for file in bug_report.related_files])}
```

## Fix Implementation

### Strategy
[選擇修復策略：熱修復 | 重構 | 架構改進]

### Files to Modify
```yaml
PRIMARY:
{self._format_files_to_modify(bug_report.related_files)}

TESTS:
  - file: tests/test_{bug_report.title.replace(' ', '_').lower()}_fix.py
    purpose: 回歸測試，確保bug不再重現
```

### Implementation Steps
```yaml
Step 1: 備份與準備
BACKUP:
  - git stash push -m "backup before {bug_report.title} fix"
  {self._format_list([f"cp {file} {file}.backup" for file in bug_report.related_files[:3]], prefix="  - ")}

Step 2: 核心修復
{self._generate_fix_steps(bug_report, issue_pattern)}

Step 3: 驗證修復
RUN_TESTS:
  - python -m pytest tests/test_{bug_report.title.replace(' ', '_').lower()}_fix.py -v
  - [環境一致性測試]
```

## Testing & Validation

### Regression Tests
```python
# test_{bug_report.title.replace(' ', '_').lower()}_fix.py
def test_original_problem_fixed():
    \"\"\"確保原問題已解決\"\"\"
    # 基於bug描述的測試案例
    {self._generate_test_case(bug_report)}

def test_no_side_effects():
    \"\"\"確保修復沒有破壞其他功能\"\"\"
    # 相關功能的回歸測試
    pass

def test_environment_consistency():
    \"\"\"確保本地和Render環境一致\"\"\"
    # 環境一致性驗證
    pass
```

### Manual Verification
```bash
# 手動測試步驟
{self._format_list(bug_report.reproduction_steps)}

# 預期結果：問題不再重現
```

## Future Prevention

### Added Safeguards
```python
# 防止類似問題的檢查機制
{self._generate_prevention_code(issue_pattern)}
```

### Monitoring Enhancements
```yaml
LOG_PATTERNS:
  - pattern: "{bug_report.title}"
    alert: "可能的{bug_report.title}問題重現"
    
HEALTH_CHECKS:
  - check: "驗證修復的功能正常"
    frequency: "每小時"
```

---

Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
'''
        return content

    def _generate_feature_content(self, feature_request: FeatureRequest, integration_analysis: Dict[str, Any]) -> str:
        """生成新功能PRP內容"""
        content = f'''name: "新功能PRP - {feature_request.name}"
description: |

## Feature Specification

### Feature Name
{feature_request.name}

### Category
{feature_request.category}

### Priority & Impact
**Business Priority**: {feature_request.priority.value}
**Technical Complexity**: {feature_request.complexity.value}
**User Impact**: [影響的用戶群體和使用場景]

## Feature Requirements

### User Stories
```yaml
{self._format_user_stories(feature_request.user_stories)}
```

### Functional Requirements
{self._format_list(feature_request.acceptance_criteria)}

### Non-Functional Requirements
- **Performance**: [響應時間、吞吐量要求]
- **Reliability**: [可用性、容錯要求]
- **Scalability**: [擴展性考慮]
- **Security**: [安全性要求]

## System Integration Analysis

{self._format_integration_analysis(integration_analysis)}

## Technical Design

### Architecture Components
```python
# 新增或修改的主要組件
{self._generate_component_structure(feature_request)}
```

### Data Models
```python
{self._generate_data_models(feature_request)}
```

### Database Schema Changes
```sql
{self._generate_database_changes(feature_request)}
```

## Implementation Plan

{self._generate_implementation_plan(feature_request, integration_analysis)}

## Code Implementation Templates

{self._generate_code_templates(feature_request)}

## Testing Strategy

{self._generate_testing_strategy(feature_request)}

## Deployment Checklist

### Pre-Deployment
- [ ] 所有單元測試通過
- [ ] 整合測試通過
- [ ] 環境一致性驗證完成
- [ ] 資料庫遷移腳本準備就緒
- [ ] 設定檔案更新完成

### Deployment Steps
- [ ] 備份現有系統
- [ ] 執行資料庫遷移
- [ ] 部署應用程式代碼
- [ ] 修復PostgreSQL序列（如適用）
- [ ] 驗證核心功能正常

### Post-Deployment
- [ ] 功能驗證測試
- [ ] 效能監控
- [ ] 用戶反饋收集
- [ ] 文檔更新完成

---

Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
'''
        return content

    def _format_list(self, items: List[str], prefix: str = "- ") -> str:
        """格式化列表"""
        if not items:
            return f"{prefix}[待補充]"
        return "\n".join([f"{prefix}{item}" for item in items])

    def _format_pattern_analysis(self, issue_pattern: Dict[str, Any]) -> str:
        """格式化模式分析"""
        matches = issue_pattern.get("matches", {})
        if not matches:
            return "- 新類型問題，需要詳細分析"
        
        analysis = []
        for pattern_name, pattern_info in matches.items():
            analysis.append(f"- 匹配已知模式: {pattern_name}")
            analysis.append(f"  相關檔案: {', '.join(pattern_info['files'])}")
        
        return "\n".join(analysis)

    def _format_known_issues(self, matches: Dict[str, Any]) -> str:
        """格式化已知問題"""
        if not matches:
            return "# 新問題，無相關已知問題"
        
        formatted = []
        for pattern_name, pattern_info in matches.items():
            formatted.append(f"- issue: \"{pattern_name}\"")
            formatted.append(f"  files: {pattern_info['files']}")
            formatted.append(f"  fixes: {pattern_info['common_fixes']}")
        
        return "\n".join(formatted)

    def _format_files_to_modify(self, files: List[str]) -> str:
        """格式化要修改的檔案"""
        if not files:
            return "  - file: [待確認]\n    changes: [待分析]\n    risk: [待評估]"
        
        formatted = []
        for file in files:
            formatted.append(f"  - file: {file}")
            formatted.append(f"    changes: [具體修改內容]")
            formatted.append(f"    risk: [修改風險評估]")
        
        return "\n".join(formatted)

    def _generate_fix_steps(self, bug_report: BugReport, issue_pattern: Dict[str, Any]) -> str:
        """生成修復步驟"""
        steps = []
        matches = issue_pattern.get("matches", {})
        
        if "date_parsing" in matches:
            steps.append("MODIFY modules/utils/unified_date_parser.py:")
            steps.append("  - ENSURE: 統一日期解析器正常運作")
            steps.append("  - UPDATE: 相關模組使用統一解析器")
        
        if "line_bot_api" in matches:
            steps.append("MODIFY modules/utils/line_bot.py:")
            steps.append("  - CHECK: QuickReply格式包含text屬性")
            steps.append("  - ENSURE: 使用reply_message而非push_message")
        
        if not steps:
            steps.append("MODIFY [主要檔案]:")
            steps.append("  - LOCATE: [具體位置/函數/行數]")
            steps.append("  - REPLACE: [舊代碼片段]")
            steps.append("  - WITH: [新代碼片段]")
        
        return "\n".join(steps)

    def _generate_test_case(self, bug_report: BugReport) -> str:
        """生成測試案例"""
        return f"""
    # 基於bug描述的測試
    # Expected: {bug_report.expected_behavior}
    # Actual (before fix): {bug_report.actual_behavior}
    
    result = function_that_had_bug()
    assert result == expected_result, "Bug應該已修復"
"""

    def _generate_prevention_code(self, issue_pattern: Dict[str, Any]) -> str:
        """生成預防代碼"""
        matches = issue_pattern.get("matches", {})
        
        if "date_parsing" in matches:
            return """
def validate_date_parsing_consistency():
    \"\"\"驗證日期解析一致性\"\"\"
    from modules.utils.unified_date_parser import UnifiedDateParser
    
    test_dates = ["昨天", "今天", "明天", "7/25"]
    for date_str in test_dates:
        try:
            result = UnifiedDateParser.parse(date_str)
            assert result is not None, f"日期解析失敗: {date_str}"
        except Exception as e:
            logger.error(f"日期解析錯誤: {date_str} -> {e}")
            raise
"""
        
        return "# 待實現：根據具體bug類型添加預防機制"

    def _format_user_stories(self, user_stories: List[str]) -> str:
        """格式化用戶故事"""
        if not user_stories:
            return """作為 [用戶角色]:
  我希望 [具體需求]
  以便 [業務價值]
  
接受條件:
  - [可測試的條件1]
  - [可測試的條件2]"""
        
        formatted = []
        for story in user_stories:
            formatted.append(f"- {story}")
        return "\n".join(formatted)

    def _format_integration_analysis(self, integration_analysis: Dict[str, Any]) -> str:
        """格式化整合分析"""
        sections = []
        
        if integration_analysis.get("three_state_architecture"):
            sections.append("""### Three-State Architecture Integration
```yaml
FUTURE_STATE (fixed_schedules):
  - integration: [如何與未來態整合]
  
CURRENT_STATE (trips):
  - integration: [如何與現在態整合]
  
PAST_STATE (completed_trips):
  - integration: [如何與過去態整合]
```""")
        
        if integration_analysis.get("ai_system"):
            sections.append("""### AI System Integration
```yaml
SMART_ASSISTANT:
  - natural_language: [自然語言處理需求]
  - intent_recognition: [意圖識別要求]
  
AI_ROUTING:
  - decision_logic: [路由決策邏輯]
  - fallback_strategy: [降級策略]
```""")
        
        if integration_analysis.get("line_bot"):
            sections.append("""### Line Bot Integration
```yaml
MESSAGE_TYPES:
  - text: [文字訊息處理]
  - flex: [Flex Message設計]
  
WEBHOOK_HANDLING:
  - event_types: [處理的事件類型]
  - response_format: [回應格式要求]
```""")
        
        return "\n\n".join(sections) if sections else "### Integration Analysis\n[待補充整合分析]"

    def _analyze_three_state_integration(self, feature_request: FeatureRequest) -> bool:
        """分析三時間態整合"""
        keywords = ["班次", "schedule", "trip", "時間", "狀態"]
        return any(keyword in feature_request.description.lower() for keyword in keywords)

    def _analyze_ai_integration(self, feature_request: FeatureRequest) -> bool:
        """分析AI整合"""
        keywords = ["ai", "智能", "自然語言", "查詢", "assistant"]
        return any(keyword in feature_request.description.lower() for keyword in keywords)

    def _analyze_linebot_integration(self, feature_request: FeatureRequest) -> bool:
        """分析Line Bot整合"""
        keywords = ["line", "bot", "訊息", "回應", "flex", "互動"]
        return any(keyword in feature_request.description.lower() for keyword in keywords)

    def _analyze_database_integration(self, feature_request: FeatureRequest) -> bool:
        """分析資料庫整合"""
        keywords = ["資料", "database", "查詢", "儲存", "table"]
        return any(keyword in feature_request.description.lower() for keyword in keywords)

    def _generate_component_structure(self, feature_request: FeatureRequest) -> str:
        """生成組件結構"""
        feature_name = feature_request.name.lower().replace(' ', '_')
        return f"""
components/{feature_name}/
├── service.py           # 業務邏輯
├── handler.py           # 請求處理
├── models.py            # 資料模型
└── utils.py             # 輔助函數
"""

    def _generate_data_models(self, feature_request: FeatureRequest) -> str:
        """生成資料模型"""
        feature_name = feature_request.name.replace(' ', '')
        return f"""
@dataclass
class {feature_name}Data:
    \"\"\"新功能的核心資料模型\"\"\"
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    # [其他欄位]
    
    def to_dict(self) -> dict:
        \"\"\"轉換為字典格式\"\"\"
        return {{
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            # [其他欄位]
        }}
"""

    def _generate_database_changes(self, feature_request: FeatureRequest) -> str:
        """生成資料庫變更"""
        table_name = feature_request.name.lower().replace(' ', '_')
        return f"""
-- 新增表格（如需要）
CREATE TABLE IF NOT EXISTS {table_name} (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- [其他欄位]
    
    -- 索引優化
    INDEX idx_{table_name}_lookup ([key_columns])
);

-- 更新序列（重要！）
SELECT setval('{table_name}_id_seq', COALESCE(MAX(id), 1)) FROM {table_name};
"""

    def _generate_implementation_plan(self, feature_request: FeatureRequest, integration_analysis: Dict[str, Any]) -> str:
        """生成實施計劃"""
        phases = []
        
        phases.append("""### Phase 1: Core Implementation
```yaml
Task 1.1: 資料層實現
FILES:
  - CREATE modules/models/[feature]_models.py
  - MODIFY modules/utils/database_helpers.py (if needed)

Task 1.2: 服務層實現
FILES:
  - CREATE modules/services/[feature]_service.py
PATTERNS:
  - 使用統一錯誤處理模式
  - 整合unified_date_parser
```""")
        
        if integration_analysis.get("ai_system"):
            phases.append("""### Phase 2: AI Integration
```yaml
Task 2.1: AI助手擴展
FILES:
  - MODIFY modules/services/smart_assistant.py
  - UPDATE modules/ai_agent/tool_registry.py
```""")
        
        if integration_analysis.get("line_bot"):
            phases.append("""### Phase 3: Line Bot Integration
```yaml
Task 3.1: Flex Message設計
FILES:
  - CREATE modules/flex_designs/[feature]_flex.py
REQUIREMENTS:
  - 確保QuickReply格式正確
```""")
        
        phases.append("""### Phase 4: Testing & Validation
```yaml
Task 4.1: 單元測試
FILES:
  - CREATE tests/test_[feature].py

Task 4.2: 環境一致性
VERIFY:
  - 本地環境功能正常
  - Render環境行為一致
```""")
        
        return "\n\n".join(phases)

    def _generate_code_templates(self, feature_request: FeatureRequest) -> str:
        """生成代碼模板"""
        feature_name = feature_request.name.replace(' ', '')
        
        return f"""### Service Layer Template
```python
# modules/services/{feature_request.name.lower().replace(' ', '_')}_service.py
class {feature_name}Service:
    \"\"\"[功能名稱] 核心服務類\"\"\"
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def process_request(self, user_input: str, user_id: str) -> Dict[str, Any]:
        \"\"\"處理用戶請求的主要入口\"\"\"
        try:
            # PATTERN: 使用統一日期解析器
            date_info = self._extract_date_info(user_input)
            
            # 核心業務邏輯
            result = await self._execute_business_logic(user_input, date_info, user_id)
            
            return self._format_response(result)
            
        except Exception as e:
            self.logger.error(f"服務處理失敗: {{e}}", exc_info=True)
            return self._error_response("系統暫時無法處理請求")
```"""

    def _generate_testing_strategy(self, feature_request: FeatureRequest) -> str:
        """生成測試策略"""
        return f"""### Unit Test Template
```python
# tests/test_{feature_request.name.lower().replace(' ', '_')}.py
class Test{feature_request.name.replace(' ', '')}Service:
    
    @pytest.mark.asyncio
    async def test_process_request_success(self):
        \"\"\"測試正常請求處理\"\"\"
        service = {feature_request.name.replace(' ', '')}Service()
        result = await service.process_request("[測試輸入]", "test_user_123")
        
        assert result["success"] is True
        assert "data" in result
        
    def test_date_parsing_integration(self):
        \"\"\"測試日期解析整合\"\"\"
        # 確保使用統一日期解析器
        pass
```"""

    def _identify_affected_components(self, files: List[str]) -> List[str]:
        """識別受影響的組件"""
        components = []
        for file in files:
            for component, paths in self.system_components.items():
                if any(path in file for path in paths):
                    components.append(component)
        return list(set(components))

    def _get_relevant_diagnostics(self, pattern_matches: Dict[str, Any]) -> List[str]:
        """獲取相關診斷命令"""
        diagnostics = []
        for pattern_name, pattern_info in pattern_matches.items():
            diagnostics.extend(pattern_info.get("diagnostic_commands", []))
        return diagnostics

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="自動PRP生成器")
    parser.add_argument("--type", choices=["bug", "feature"], required=True, help="PRP類型")
    parser.add_argument("--input", required=True, help="輸入JSON檔案路徑")
    parser.add_argument("--output-dir", help="輸出目錄", default="PRPs")
    
    args = parser.parse_args()
    
    generator = PRPGenerator()
    
    # 讀取輸入資料
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if args.type == "bug":
        bug_report = BugReport(**data)
        output_path = generator.generate_bug_fix_prp(bug_report)
        print(f"✅ Bug修復PRP已生成: {output_path}")
        
    elif args.type == "feature":
        feature_request = FeatureRequest(**data)
        output_path = generator.generate_feature_prp(feature_request)
        print(f"✅ 新功能PRP已生成: {output_path}")

if __name__ == "__main__":
    main()