# AI智能系統維護指南

> 📅 更新日期：2025-07-15  
> 🎯 目的：提供AI系統核心配置文件的維護參考

---

## 📚 核心配置文件清單

### 1. 系統知識庫 ⭐⭐⭐ (最重要)
**文件路徑：** `modules/services/system_knowledge_base.py`

**包含內容：**
- 📊 完整的資料庫Schema定義 (trips、completed_trips、fixed_schedules、drivers)
- 🎯 三時間態映射 (過去/現在/未來)
- 🔍 查詢範例和業務邏輯
- 📋 可用功能列表

**常見修改場景：**
- 新增資料表欄位定義
- 修正狀態值列表
- 增加查詢模式範例
- 更新業務規則

**關鍵區域：**
```python
# 約第18行 - trips表狀態定義
"status": {"description": "班次狀態：待派、準備、已完成、取消"},

# 約第95行 - 三時間態映射
TIME_PERSPECTIVE_MAPPING = {
    PAST: "completed_trips",
    PRESENT: "trips", 
    FUTURE: "fixed_schedules"
}

# 約第300行 - 查詢範例
QUERY_EXAMPLES = [...]
```

---

### 2. AI助手提示詞 ⭐⭐
**文件路徑：** `modules/services/smart_assistant.py`

**包含內容：**
- 🧠 Gemini AI的主要prompt (GEMINI_PROMPT)
- 📝 查詢理解指導
- 🎯 命令生成範例
- 🔄 回應格式定義

**常見修改場景：**
- 改進AI理解邏輯
- 新增查詢範例
- 調整信心度閾值
- 優化錯誤處理

**關鍵區域：**
```python
# 約第50行 - 主要提示詞
GEMINI_PROMPT = """你是台灣計程車調度系統的智能助手..."""

# 約第150行 - 查詢範例區塊
範例查詢1: "今天金額大於200的診所班次"
目標表: completed_trips
標準命令: 查已完成 今天 診所 金額>200
```

---

### 3. 高級查詢處理器 ⭐⭐
**文件路徑：** `modules/services/advanced_query_processor.py`

**包含內容：**
- 🔍 條件解析邏輯 (狀態、日期、司機、金額等)
- 📊 動態SQL生成規則
- 🎯 結果格式化邏輯
- ❌ 錯誤處理機制

**常見修改場景：**
- 新增條件類型 (如優先級、緊急程度)
- 改進解析模式
- 修正SQL生成邏輯
- 優化結果顯示格式

**關鍵區域：**
```python
# 約第230行 - 狀態解析
known_statuses = ['待派', '準備', '已完成', '取消']

# 約第200行 - 條件解析
def _parse_query_conditions(self, command: str) -> Dict:

# 約第280行 - 結果格式化
def _format_completed_trips_result(self, trips: List, command: str, conditions: Dict):
```

---

## 📖 文檔和界面文件

### 4. 幫助文檔系統
**主要文件：**
- `modules/flex_designs/help_flex.py` - LINE Bot幫助界面
- `AI_SIMPLE_USAGE_GUIDE.md` - AI使用指南
- `LONG_TERM_LEAVE_GUIDE.md` - 長期請假指南  
- `DATA_MIGRATION_GUIDE.md` - 資料遷移指南

**修改重點：**
- 更新功能說明
- 新增使用範例
- 修正過時信息
- 改進用戶體驗

---

## 🛠️ 常見維護場景

### 場景1：新增班次狀態類型
```python
# 1. 更新知識庫 (system_knowledge_base.py)
"status": {"description": "班次狀態：待派、準備、已完成、取消、新狀態"},

# 2. 更新查詢處理器 (advanced_query_processor.py)
known_statuses = ['待派', '準備', '已完成', '取消', '新狀態']

# 3. 更新AI提示詞 (smart_assistant.py)
# 在GEMINI_PROMPT中新增範例
```

### 場景2：改進AI查詢理解
```python
# 在smart_assistant.py的GEMINI_PROMPT中新增：
範例查詢X: "您的新查詢模式"
目標表: trips/completed_trips/fixed_schedules  
標準命令: 查詢班次 新條件=值
提取條件: {...}
```

### 場景3：新增查詢條件類型
```python
# 在advanced_query_processor.py的_parse_query_conditions中新增：
# 解析新條件
if '關鍵字' in command:
    conditions['新欄位'] = '提取值'

# 在相應的查詢方法中添加SQL條件：
if conditions.get('新欄位'):
    where_conditions.append("t.新欄位 = :新參數")
    params['新參數'] = conditions['新欄位']
```

### 場景4：優化錯誤處理
```python
# 在advanced_query_processor.py中新增驗證：
if conditions.get('invalid_新條件'):
    return {
        "type": "invalid_新條件",
        "message": "❌ 無效的新條件值\n\n💡 可用值：..."
    }
```

---

## 📝 維護最佳實踐

### 修改前準備
1. **備份重要文件**
   ```bash
   cp modules/services/system_knowledge_base.py modules/services/system_knowledge_base.py.backup
   cp modules/services/smart_assistant.py modules/services/smart_assistant.py.backup
   ```

2. **記錄修改原因**
   - 在文件頂部註釋中記錄修改日期和原因
   - 保留修改歷史記錄

### 測試方法
```bash
# 進入項目目錄
cd /Users/linyancui/minimal_flask

# 運行AI系統測試
python test_enhanced_ai_system.py

# 檢查特定查詢
# 在LINE中測試修改後的查詢模式
```

### 常見檢查點
- [ ] 新增的狀態值在所有相關文件中都已更新
- [ ] AI提示詞中的範例與實際邏輯一致
- [ ] 查詢條件解析正確處理新增的模式
- [ ] 錯誤訊息清楚且有幫助
- [ ] 結果格式化適合手機顯示

---

## 🎯 維護優先級

### 高優先級 (影響用戶體驗)
1. **狀態和類別定義** - 直接影響查詢結果
2. **AI理解邏輯** - 影響查詢解析準確度
3. **錯誤提示** - 影響用戶操作指導

### 中優先級 (改善體驗)
1. **查詢範例** - 幫助AI學習新模式
2. **結果格式化** - 改善閱讀體驗
3. **幫助文檔** - 提供操作指導

### 低優先級 (優化性能)
1. **SQL優化** - 提升查詢效率
2. **緩存機制** - 減少重複計算
3. **日誌記錄** - 方便問題排查

---

## 📞 緊急修復流程

當發現AI理解錯誤或系統行為異常時：

1. **快速定位**
   - 檢查 `system_knowledge_base.py` 中的定義是否正確
   - 驗證 `advanced_query_processor.py` 中的條件解析

2. **臨時修復**
   - 在 `smart_assistant.py` 中添加特殊案例處理
   - 更新錯誤提示幫助用戶理解

3. **完整修復**
   - 更新知識庫定義
   - 優化查詢邏輯
   - 增加測試案例

---

**💡 提示：建議每次修改後都在LINE中測試幾個常用查詢，確保系統正常運作！** 