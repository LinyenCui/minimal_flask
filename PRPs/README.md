# 派班系統PRP (Prompt Response Pattern) 管理系統

## 概述

基於Context Engineering原則的PRP管理系統，專為企業級自動化派班管理系統設計，整合AI智能助手、三時間態架構、Line Bot等核心組件的開發指南。

## 目錄結構

```
PRPs/
├── README.md                    # 本文件
├── AUTO_GENERATOR.py           # 自動PRP生成器
├── BUG_FIX_TEMPLATE.md         # Bug修復PRP模板
├── FEATURE_TEMPLATE.md         # 新功能PRP模板
├── templates/
│   └── prp_dispatch_system_base.md  # 派班系統基礎PRP模板
├── examples/
│   ├── example_bug_report.json      # Bug報告範例
│   └── example_feature_request.json # 功能請求範例
└── generated/                  # 自動生成的PRP檔案
```

## 快速開始

### 1. 使用自動生成器創建Bug修復PRP

```bash
# 使用範例bug報告
python PRPs/AUTO_GENERATOR.py \
  --type bug \
  --input PRPs/example_bug_report.json

# 輸出: PRPs/BUG_FIX_DATE_PARSING_INCONSISTENCY_BETWEEN_LOCAL_AND_RENDER_20250127_143022.md
```

### 2. 使用自動生成器創建新功能PRP

```bash
# 使用範例功能請求
python PRPs/AUTO_GENERATOR.py \
  --type feature \
  --input PRPs/example_feature_request.json

# 輸出: PRPs/FEATURE_INTELLIGENT_CONFLICT_DETECTION_SYSTEM_20250127_143045.md
```

### 3. 手動創建自定義PRP

```bash
# 複製基礎模板
cp PRPs/templates/prp_dispatch_system_base.md PRPs/MY_FEATURE.md

# 編輯模板，填入具體需求
vim PRPs/MY_FEATURE.md
```

## PRP模板說明

### 基礎模板 (prp_dispatch_system_base.md)

專為派班系統優化的Context-Rich模板，包含：

- **生產線思維**: 遵循未來態→現在態→過去態的時間流轉
- **統一解析**: 避免重複實現災難，使用統一的解析器和服務
- **AI優先**: 優先考慮自然語言處理和智能路由
- **環境一致性**: 確保本地和Render部署環境行為一致

### Bug修復模板 (BUG_FIX_TEMPLATE.md)

專門針對已知問題模式的修復指南：

- **已知問題資料庫**: 6個重複日期解析函數、QuickReply格式錯誤等
- **診斷工具集**: 環境驗證、AI系統診斷、Line Bot診斷
- **修復策略**: 熱修復、重構、架構改進
- **預防機制**: 避免類似問題再次發生

### 新功能模板 (FEATURE_TEMPLATE.md)

整合系統核心組件的功能擴展指南：

- **系統整合分析**: 三時間態架構、AI系統、Line Bot整合
- **實施計劃**: 分階段開發策略
- **代碼模板**: Service層、AI整合、Line Bot處理器
- **測試策略**: 單元測試、整合測試、環境一致性

## 自動生成器使用指南

### Bug報告JSON格式

```json
{
  "title": "問題標題",
  "description": "問題描述",
  "symptoms": ["症狀1", "症狀2"],
  "expected_behavior": "預期行為",
  "actual_behavior": "實際行為", 
  "environment": "Local | Render | Both",
  "priority": "🔴 Critical | 🟡 Major | 🟢 Minor",
  "related_files": ["檔案1", "檔案2"],
  "error_logs": ["錯誤日誌1", "錯誤日誌2"],
  "reproduction_steps": ["步驟1", "步驟2"]
}
```

### 功能請求JSON格式

```json
{
  "name": "功能名稱",
  "description": "功能描述",
  "category": "AI Enhancement | Line Bot Feature | Analytics | System Tool | Business Logic",
  "priority": "🔴 Critical | 🟡 Important | 🟢 Nice-to-have",
  "complexity": "🔴 High | 🟡 Medium | 🟢 Low",
  "user_stories": ["用戶故事1", "用戶故事2"],
  "acceptance_criteria": ["接受條件1", "接受條件2"],
  "integration_points": ["整合點1", "整合點2"]
}
```

## 系統特定注意事項

### 🔴 關鍵限制和已知問題

1. **日期解析統一**
   ```python
   # ✅ 正確 - 使用統一解析器
   from modules.utils.unified_date_parser import UnifiedDateParser
   date = UnifiedDateParser.parse(date_input)
   
   # ❌ 錯誤 - 避免重複實現
   # 不要創建新的日期解析函數
   ```

2. **Line Bot免費政策**
   ```python
   # ✅ 正確 - 使用reply_message
   line_bot_api.reply_message(reply_token, message)
   
   # ❌ 錯誤 - 違反免費政策
   line_bot_api.push_message(user_id, message)
   ```

3. **QuickReply格式**
   ```python
   # ✅ 正確 - 包含text屬性
   action = {
       "type": "postback",
       "label": "按鈕文字",
       "data": "action_data",
       "text": "必須有這個text屬性"  # ← 必須包含
   }
   ```

### 🎯 開發最佳實踐

1. **三時間態架構**: 所有功能都應考慮時間流轉邏輯
2. **AI優先路由**: 自然語言 → AI Agent，精確命令 → 傳統處理
3. **環境一致性**: 確保本地和Render環境行為完全一致
4. **統一錯誤處理**: 遵循現有的錯誤處理模式
5. **PostgreSQL序列**: 數據遷移後必須修復序列同步

## 診斷工具

### 環境一致性檢查

```bash
# 檢查統一日期解析器
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

# 檢查重複實現
grep -r "def parse_date" modules/ --exclude="unified_date_parser.py"
```

### AI系統診斷

```bash
# 測試AI路由決策
python -c "
from modules.ai_agent.ai_router import ai_router
test_inputs = ['昨天診所班次', '班次詳情 2207']
for inp in test_inputs:
    print(f'{inp} -> AI路由: {ai_router.should_use_ai_agent(inp)}')
"
```

### Line Bot診斷

```bash
# 檢查QuickReply格式
python -c "
from modules.flex_designs.trip_details_flex import get_trip_details_flex
result = get_trip_details_flex(2320)
print(result.get('quick_reply', {}))
"
```

## 貢獻指南

1. **新增已知問題模式**: 編輯`AUTO_GENERATOR.py`中的`known_issues`資料庫
2. **更新模板**: 根據系統演進更新模板內容
3. **改進生成器**: 增強自動生成邏輯和模式識別
4. **添加診斷工具**: 擴展診斷命令和檢查項目

## 參考文檔

- [INITIAL.md](../INITIAL.md) - 系統概覽和已知問題
- [docs/AI_AGENT_ARCHITECTURE.md](../docs/AI_AGENT_ARCHITECTURE.md) - AI Agent架構
- [docs/guides/PRODUCTION_LINE_DISPATCH_SYSTEM.md](../docs/guides/PRODUCTION_LINE_DISPATCH_SYSTEM.md) - 生產線思維
- [docs/logs/cursor_5.txt](../docs/logs/cursor_5.txt) - 詳細問題分析記錄

## 版本歷史

- **v1.0** (2025-01-27): 初始版本，包含基礎模板和自動生成器
- 基於Context Engineering原則設計
- 整合派班系統特定的已知問題和解決方案
- 支援Bug修復和新功能開發的完整PRP生成