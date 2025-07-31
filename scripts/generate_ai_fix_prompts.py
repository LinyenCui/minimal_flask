#!/usr/bin/env python3
"""
根據文檔同步檢查報告自動生成AI修改提示詞
將每個問題轉換為具體的AI修改指令
"""
import json
import re
from datetime import datetime
from pathlib import Path

class AIPromptGenerator:
    def __init__(self):
        self.project_root = Path("/Users/linyancui/ai_experiments/minimal_flask")
        self.prompts_dir = self.project_root / "ai_prompts"
        self.prompts_dir.mkdir(exist_ok=True)
        
    def read_sync_report(self):
        """讀取文檔同步檢查報告"""
        report_file = self.project_root / "DOC_SYNC_REPORT.md"
        if not report_file.exists():
            print("❌ 找不到 DOC_SYNC_REPORT.md，請先運行文檔同步檢查")
            return None
            
        return report_file.read_text(encoding='utf-8')
    
    def generate_initial_md_update_prompt(self, issue_data):
        """生成更新INITIAL.md的AI提示詞"""
        prompt = f"""# AI修改任務：更新INITIAL.md文檔

## 任務描述
根據文檔同步檢查結果，更新INITIAL.md中已過時的問題描述。

## 具體修改要求

### 目標文件
`/Users/linyancui/ai_experiments/minimal_flask/INITIAL.md`

### 需要修改的內容
找到以下內容並進行更新：

```markdown
**原文 (約第161行):**
2. **日期解析函數重複實現災難**
   - 6個不同模組各自實現parse_date_input函數
   - 導致"昨天"查詢本地54筆 vs Render 21筆差異
   - 影響文件: `ai_fare_service.py`, `trip_query_handler.py`, `booking_service.py`等
   - 解決方案: 統一使用`modules/utils/unified_date_parser.py`
```

**修改為：**
```markdown
2. **日期解析函數重複實現** ✅已解決 (2024年)
   - ✅ 已統一使用`modules/utils/unified_date_parser.py` 
   - ✅ 18個文件正確使用統一解析器
   - ✅ 查詢結果一致性問題已修復
   - ✅ 舊函數已設置轉發和棄用警告
   - 📅 解決時間: 2024年下半年
```

### 當前狀態數據
- 統一使用unified_date_parser.py的文件：18個
- 重複實現：已減少至1個（unified_date_parser.py本身）
- 問題狀態：已大幅改善

### 修改原則
1. 保持原有的編號和結構
2. 添加✅標記表示已解決
3. 更新具體數據
4. 保持markdown格式正確
5. 不要修改其他未涉及的內容

### 驗證要求
修改完成後請確認：
- markdown格式正確
- 所有✅符號正常顯示
- 編號序列保持正確
- 內容與實際代碼狀況一致

**生成時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**問題來源:** 文檔同步檢查報告
"""
        
        return prompt
    
    def generate_quick_reply_documentation_prompt(self, issue_data):
        """生成記錄Quick Reply功能完成狀態的提示詞"""
        prompt = f"""# AI修改任務：記錄Quick Reply功能實現狀態

## 任務描述
為已實現的Quick Reply退出機制功能添加文檔記錄。

## 具體修改要求

### 選項1：更新INITIAL.md
在`INITIAL.md`的適當位置添加已完成功能記錄：

```markdown
### ✅ 最近完成的功能改進

**Quick Reply退出機制** (2024年)
- ✅ 班次詳情請假對話框退出機制
- ✅ 固定班次請假退出機制  
- ✅ 統一Quick Reply處理邏輯
- 📁 涉及文件：
  - `modules/handlers/trip_status_handler.py`
  - `modules/services/postback_service.py`
  - `modules/flex_designs/trip_details_flex.py`
  - `modules/handlers/text_message_handler.py`
- 🧪 測試文件：3個驗證文件
```

### 選項2：創建新的功能完成記錄文件
創建`COMPLETED_FEATURES.md`文件記錄已完成功能：

```markdown
# 已完成功能記錄

## Quick Reply退出機制 ✅

**完成時間：** 2024年下半年  
**問題描述：** 用戶在班次詳情請假對話框中無法退出  
**解決方案：** 添加Quick Reply退出按鈕  

### 實現詳情
- 實現文件：4個核心文件
- 測試驗證：3個測試文件
- 功能狀態：完全可用

### 相關文件
- `modules/handlers/trip_status_handler.py` - 主要實現
- `modules/services/postback_service.py` - 調用處理
- `modules/flex_designs/trip_details_flex.py` - UI展示
- `modules/handlers/text_message_handler.py` - 消息路由
```

### 當前狀態數據
- 實現文件數：4個關鍵文件  
- 測試文件數：3個
- 功能狀態：已完全實現

### 推薦行動
建議選擇**選項2**，創建專門的已完成功能記錄文件，這樣便於：
1. 追蹤功能完成歷史
2. 避免INITIAL.md過於冗長
3. 方便查找特定功能的實現狀態

**生成時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**問題來源:** 文檔同步檢查報告
"""
        
        return prompt
    
    def generate_handler_split_planning_prompt(self, issue_data):
        """生成text_message_handler.py拆分規劃的提示詞"""  
        prompt = f"""# AI修改任務：text_message_handler.py拆分規劃

## 任務描述
為text_message_handler.py (目前2087行) 制定詳細的拆分計劃。

## 當前狀況分析
- **文件大小：** 2087行 (嚴重超標，建議<500行)
- **問題：** 單一文件承擔過多職責
- **風險：** 修改一個功能容易影響其他功能

## 拆分策略規劃

### Phase 1: 分析現有功能模塊
請分析`modules/handlers/text_message_handler.py`並識別：

1. **核心功能模塊** (按功能分組)
   - 預約/叫車處理
   - 查詢處理 (班次查詢、車資查詢)
   - 狀態更新處理
   - 對話管理
   - 其他工具性功能

2. **依賴關係分析**
   - 各模塊間的調用關係
   - 共享的工具函數
   - 外部依賴

### Phase 2: 設計拆分架構
基於INITIAL.md的建議，設計新架構：

```
modules/handlers/
├── booking_handler.py           # 預約叫車相關
├── query_handler.py            # 各種查詢功能  
├── status_handler.py           # 狀態更新相關
├── conversation_handler.py     # 對話狀態管理
└── message_router.py           # 消息路由分發
```

### Phase 3: 遷移計劃
制定安全的遷移步驟：

1. **準備階段**
   - 創建新的handler文件框架
   - 設計統一的接口規範
   - 準備測試框架

2. **漸進遷移**
   - 從獨立性最高的模塊開始
   - 每次遷移一個模塊並測試
   - 保持原文件作為fallback

3. **驗證階段**
   - 功能完整性測試
   - 性能對比測試  
   - 錯誤處理測試

### 具體輸出要求
請生成：
1. **功能模塊清單** - 詳細的功能分組
2. **拆分架構圖** - 新的文件結構和調用關係
3. **遷移時間表** - 分階段實施計劃
4. **風險評估** - 潛在問題和緩解措施

### 成功標準
- 每個新文件<500行
- 模塊職責清晰單一
- 接口設計合理
- 測試覆蓋完整
- 不影響現有功能

**當前文件位置:** `modules/handlers/text_message_handler.py`
**當前行數:** 2087行
**拆分目標:** 5-6個專責文件

**生成時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**任務性質:** 架構重構規劃
"""
        
        return prompt
    
    def parse_issues_from_report(self, report_content):
        """從報告中解析問題"""
        issues = []
        
        # 使用正則表達式提取問題
        issue_pattern = r'### \d+\. (.+?)\n\n\*\*問題描述:\*\* (.+?)\n\n\*\*相關文件:\*\* (.+?)\n\n\*\*建議行動:\*\* (.+?)\n'
        matches = re.findall(issue_pattern, report_content, re.DOTALL)
        
        for match in matches:
            issue_type, description, files, suggestion = match
            issues.append({
                'type': issue_type.strip(),
                'description': description.strip(), 
                'files': files.strip(),
                'suggestion': suggestion.strip()
            })
        
        return issues
    
    def generate_all_prompts(self):
        """生成所有AI修改提示詞"""
        report_content = self.read_sync_report()
        if not report_content:
            return False
        
        print("🤖 開始生成AI修改提示詞...")
        
        # 生成各種提示詞
        prompts = {
            'update_initial_md': self.generate_initial_md_update_prompt({}),
            'document_quick_reply': self.generate_quick_reply_documentation_prompt({}),
            'plan_handler_split': self.generate_handler_split_planning_prompt({})
        }
        
        # 保存提示詞文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for prompt_name, prompt_content in prompts.items():
            filename = f"{prompt_name}_{timestamp}.md"
            filepath = self.prompts_dir / filename
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(prompt_content)
                print(f"✅ 已生成: {filename}")
            except Exception as e:
                print(f"❌ 生成失敗 {filename}: {e}")
        
        # 生成提示詞索引文件
        self.generate_prompts_index(prompts.keys(), timestamp)
        
        return True
    
    def generate_prompts_index(self, prompt_names, timestamp):
        """生成提示詞索引文件"""
        index_content = f"""# AI修改提示詞索引

**生成時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**批次編號:** {timestamp}

## 可用的提示詞

### 1. 更新INITIAL.md文檔
**文件:** `update_initial_md_{timestamp}.md`  
**用途:** 修正INITIAL.md中已過時的日期解析問題描述  
**AI工具:** 推薦使用 Gemini, Claude, GPT-4  

### 2. 記錄Quick Reply功能
**文件:** `document_quick_reply_{timestamp}.md`  
**用途:** 為已完成的Quick Reply功能添加文檔記錄  
**AI工具:** 推薦使用 Gemini, Claude  

### 3. text_message_handler.py拆分規劃
**文件:** `plan_handler_split_{timestamp}.md`  
**用途:** 制定2087行大文件的拆分計劃  
**AI工具:** 推薦使用 Claude, GPT-4 (需要代碼分析能力)

## 使用說明

1. **選擇適合的AI工具** - 根據任務複雜度選擇
2. **複製提示詞內容** - 完整複製到AI工具中
3. **提供文件訪問** - 確保AI工具能訪問相關文件
4. **驗證結果** - AI生成結果後需要人工檢查
5. **應用修改** - 確認無誤後應用到項目中

## 注意事項

- 這些提示詞基於當前的文檔同步檢查報告生成
- 如果代碼發生變化，可能需要重新生成提示詞
- 建議在AI執行前先運行最新的文檔同步檢查

---

**自動生成工具:** `scripts/generate_ai_fix_prompts.py`  
**使用方法:** `python3 scripts/generate_ai_fix_prompts.py`
"""
        
        index_file = self.prompts_dir / f"README_{timestamp}.md"
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(index_content)
        
        print(f"📋 已生成索引文件: README_{timestamp}.md")
        
        # 同時更新主索引文件
        main_index = self.prompts_dir / "README.md"
        with open(main_index, 'w', encoding='utf-8') as f:
            f.write(index_content)
        print(f"📋 已更新主索引: README.md")

def main():
    print("🚀 開始生成AI修改提示詞...")
    print("="*50)
    
    generator = AIPromptGenerator()
    
    if generator.generate_all_prompts():
        print("="*50)
        print("🎉 AI修改提示詞生成完成！")
        print()
        print("📁 提示詞保存位置: ai_prompts/")
        print("📋 查看索引文件: ai_prompts/README.md")
        print()
        print("💡 使用建議:")
        print("1. 查看 ai_prompts/README.md 選擇適合的提示詞")
        print("2. 複製完整提示詞內容到 Gemini/Claude/GPT-4")
        print("3. 讓AI執行修改任務")
        print("4. 檢查AI的修改結果")
        print("5. 應用到項目中")
    else:
        print("❌ 生成失敗，請檢查文檔同步檢查報告是否存在")

if __name__ == "__main__":
    main()