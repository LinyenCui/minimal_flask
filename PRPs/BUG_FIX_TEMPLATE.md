name: "Bug修復PRP模板 - 派班系統專用"
description: |

## Purpose
專門針對企業級派班系統的Bug修復PRP模板，整合已知問題模式、診斷工具和修復策略。

---

## Bug Report
**Bug ID**: [識別碼，如: DATE_PARSING_INCONSISTENCY]
**Severity**: 🔴 Critical | 🟡 Major | 🟢 Minor
**Environment**: Local | Render | Both

### Symptoms
- [用戶看到的錯誤現象]
- [具體的錯誤訊息]
- [重現步驟]

### Expected vs Actual Behavior
**Expected**: [應該發生什麼]
**Actual**: [實際發生什麼]
**Impact**: [對用戶/系統的影響]

## Root Cause Analysis

### Hypothesis
[基於日誌分析和已知問題模式的假設]

### Evidence
```bash
# 相關日誌片段
[timestamp] - [module] - [level] - [message]

# 診斷命令結果
python debug_script.py
```

### Related Known Issues
```yaml
# 參考已知問題清單
- issue: "6個重複日期解析函數"
  impact: "本地/Render環境不一致"
  docs: "docs/logs/cursor_5.txt"
  
- issue: "QuickReply格式錯誤"  
  symptom: "HTTP 400 - text屬性缺失"
  location: "modules/utils/line_bot.py"
  
- issue: "正則表達式衝突"
  symptom: "修復查看指令破壞AI日期解析"
  pattern: "r'(\d+)' 太寬泛"
```

## Diagnostic Tools & Commands

### Environment Verification
```bash
# 檢查統一日期解析器狀態
python -c "
from modules.utils.unified_date_parser import UnifiedDateParser
print('昨天:', UnifiedDateParser.parse('昨天'))
print('7/25:', UnifiedDateParser.parse('7/25'))
"

# 檢查時區設定
python -c "
from modules.utils.helpers import get_taiwan_time
print('台灣時間:', get_taiwan_time())
print('時區:', get_taiwan_time().tzinfo)
"

# 檢查重複實現
grep -r "def parse_date" modules/ --exclude="unified_date_parser.py"
grep -r "parse_date_input" modules/ 
```

### AI System Diagnostics  
```bash
# 測試AI路由決策
python -c "
from modules.services.smart_assistant import SmartAssistant
from modules.ai_agent.ai_router import ai_router

test_inputs = ['昨天診所班次', '班次詳情 2207', '查已完成 2025-07-24 診所']
for inp in test_inputs:
    decision = ai_router.should_use_ai_agent(inp)
    print(f'{inp} -> AI路由: {decision}')
"

# 測試統一解析器一致性
python scripts/test_date_parsing_consistency.py
```

### Line Bot Diagnostics
```bash
# 檢查QuickReply格式
python -c "
from modules.flex_designs.trip_details_flex import get_trip_details_flex
result = get_trip_details_flex(2320)
import json
print(json.dumps(result.get('quick_reply', {}), indent=2, ensure_ascii=False))
"

# 檢查Webhook處理
curl -X POST http://localhost:5000/callback \
  -H "Content-Type: application/json" \
  -H "X-Line-Signature: test" \
  -d '{"events":[{"type":"message","message":{"type":"text","text":"測試"}}]}'
```

## Fix Implementation

### Strategy
[選擇修復策略：熱修復 | 重構 | 架構改進]

### Files to Modify
```yaml
PRIMARY:
  - file: [主要修改檔案]
    changes: [具體修改內容]
    risk: [修改風險評估]
    
SECONDARY:
  - file: [次要修改檔案]  
    changes: [配合性修改]
    
TESTS:
  - file: [測試檔案]
    purpose: [測試目的]
```

### Implementation Steps
```yaml
Step 1: 備份與準備
BACKUP:
  - cp [critical_file] [critical_file].backup
  - git stash push -m "backup before fix"
  
VERIFY_BASELINE:
  - python -m pytest tests/ -v
  - [運行診斷工具確認問題重現]

Step 2: 核心修復
MODIFY [primary_file]:
  - LOCATE: [具體位置/函數/行數]
  - REPLACE: [舊代碼片段]
  - WITH: [新代碼片段]
  - REASON: [修復邏輯說明]

Step 3: 整合修復
UPDATE [secondary_files]:
  - ENSURE: [相關模組一致性]
  - TEST: [局部功能測試]

Step 4: 驗證修復
RUN_TESTS:
  - [具體測試命令]
  - [預期結果]
```

### Critical Code Changes
```python
# BEFORE (問題代碼)
def problematic_function():
    # 說明問題所在
    pass

# AFTER (修復代碼)  
def fixed_function():
    # 說明修復邏輯
    # PATTERN: 遵循現有模式
    # REFERENCE: 參考檔案或文檔
    pass

# REASONING
"""
修復原理說明：
1. [問題成因]
2. [解決方案]  
3. [預防措施]
"""
```

## Testing & Validation

### Regression Tests
```python
# test_[bug_id]_fix.py
def test_original_problem_fixed():
    """確保原問題已解決"""
    # 重現原問題的測試案例
    # 確認修復後不再出現
    
def test_no_side_effects():
    """確保修復沒有破壞其他功能"""
    # 相關功能的測試案例
    
def test_environment_consistency():
    """確保本地和Render環境一致"""
    # 環境一致性測試
```

### Manual Verification
```bash
# 本地測試
[具體測試命令和預期結果]

# Render環境測試  
[如何在Render環境驗證修復]

# 端到端測試
[完整流程測試步驟]
```

### Performance Impact
```bash
# 修復前後性能對比
time [test_command_before]
time [test_command_after]

# 記憶體使用檢查
python -m memory_profiler [script_to_test]
```

## Deployment & Monitoring

### Deployment Checklist
- [ ] 本地測試全部通過
- [ ] 重要功能regression測試通過  
- [ ] 環境一致性驗證完成
- [ ] 備份關鍵檔案已創建
- [ ] 修復邏輯文檔已更新

### Post-Deployment Monitoring
```bash
# 監控關鍵指標
tail -f logs/app.log | grep -E "(ERROR|WARNING|修復相關關鍵字)"

# 功能驗證
[部署後驗證命令]

# 回滾計劃
git checkout [backup_commit]
# 或
cp [backup_file] [original_file]
```

### Documentation Updates
- [ ] 更新INITIAL.md中的已知問題清單
- [ ] 記錄修復過程到docs/logs/
- [ ] 更新相關技術文檔
- [ ] 添加預防性檢查到診斷工具

## Future Prevention

### Added Safeguards
```python
# 添加的檢查機制
def validate_[function_behavior]():
    """防止類似問題再次發生的檢查函數"""
    pass

# 改進的錯誤處理
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"已知問題模式: {e}")
    return fallback_solution()
```

### Monitoring Enhancements
```yaml
# 新增監控點
LOG_PATTERNS:
  - pattern: "[錯誤特徵]"
    alert: "可能的相同問題重現"
    
HEALTH_CHECKS:
  - check: "[功能驗證]"
    frequency: "每小時"
    
AUTOMATED_TESTS:
  - test: "test_[bug_id]_regression"
    run: "每次部署"
```

---

## Bug Fix Templates

### Template 1: Date Parsing Issue
適用於：日期解析相關問題

### Template 2: AI Routing Problem  
適用於：智能助手路由決策問題

### Template 3: Line Bot API Error
適用於：Line Bot API格式或政策問題

### Template 4: Database Inconsistency
適用於：本地/Render資料庫不一致問題

### Template 5: Configuration Mismatch
適用於：環境配置差異問題