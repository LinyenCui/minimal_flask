## FEATURE:

**智能LINE Bot派班管理系統** - 結合AI技術與傳統數據處理的Taiwan計程車調度平台，支援多司機、多路線、複雜查詢的企業級派班解決方案

### 🎯 核心系統架構
- **三時間態設計**：未來態(fixed_schedules) → 現在態(trips) → 過去態(completed_trips)
- **混合智能處理**：真AI功能(預約叫車) + 高效本地算法(查詢系統) + 智能路由決策
- **生產線思維派班**：自動化狀態轉換、衝突檢測、批量處理能力
- **LINE Bot完整整合**：Webhook處理、Flex Message設計、Quick Reply互動、群組管理

#### 🕐 AI日期判斷邏輯（重要規則）
**基本原則**：
- **過去日期（< 今天）**：強制使用過去態工具，查詢completed_trips表
- **今天及未來（>= 今天）**：預設使用現在態工具，查詢trips表中已匯入班次
- **明確指定已完成**：不分日期，使用過去態工具

**具體規則**：
1. 查詢7/29、7/28等過去日期 → 必須使用過去態工具（查已完成）
2. 查詢今天但未指定「已完成」→ 現在態工具（查trips中今天班次）
3. 查詢今天且明確要「已完成」→ 過去態工具（查completed_trips）
4. 查詢未來日期 → 現在態工具（trips表涵蓋已匯入的未來班次）
5. **只有今天（8/1）才可能同時存在於trips和completed_trips中**

### 🤖 AI功能分層
**真正使用AI (Gemini Pro)**：
- 智能預約叫車：自然語言→結構化數據(1.9秒響應)
- 意圖路由分析：複雜命令解析與派發
- 圖片OCR處理：車資憑證、地點識別

**本地算法包裝**：
- 車資查詢系統：高效SQL查詢(0.01秒響應)
- 司機班次查詢：關鍵詞匹配演算法
- 統計報表生成：數據聚合與格式化

### 📊 企業級功能
- **智能請假系統**：三層障眼法機制、狀態自動同步
- **報表分析引擎**：週報表、月報表、A4列印優化、數據匯出
- **批量處理工具**：假期加成批量更新、序列修復、資料庫清理
- **多租戶架構**：群組權限管理、用戶角色分離

## EXAMPLES:

### 💡 實際使用場景展示

#### 1. 智能預約叫車 (真AI功能)
```
用戶輸入: "明天早上8點診所，怡平路到湖美街，28530司機"
系統流程: 
📱 LINE接收 → 🤖 Gemini解析 → 📊 結構化數據 → 💾 數據庫創建
結果: 自動創建trip記錄，包含正確的時間、地點、司機、類別信息
響應時間: 1.9秒 (含AI處理)
```

#### 2. 複雜車資查詢 (包裝本地算法)
```
用戶輸入: "/昨天司機5386診所班次"
系統流程:
📱 指令解析 → 🔍 本地算法匹配 → 📊 SQL查詢 → 🎨 Flex訊息
結果: 精美格式的班次列表，包含車資統計、狀態標示
響應時間: 0.01秒 (純本地處理)
```

#### 3. 生產線派班管理
```
管理者操作: 批量更新司機狀態、處理衝突班次、生成週報表
系統展示: 三時間態數據流轉、自動狀態同步、衝突檢測與提醒
```

### 📁 完整系統文檔架構

**核心架構文檔：**
- `docs/AI_TRUTH_REPORT.md` - AI功能真實性分析與成本評估  
- `docs/REFACTOR_DUPLICATE_FUNCTIONS.md` - 重複程式碼統一重構計劃
- `CLEANUP_REPORT.md` - 專案清理與架構整理報告

**實施指南：**
- `docs/guides/PRODUCTION_LINE_DISPATCH_SYSTEM.md` - 生產線思維派班核心設計
- `docs/guides/ADVANCED_LEAVE_SYSTEM.md` - 三層次請假障眼法機制
- `docs/AI_SIMPLE_USAGE_GUIDE.md` - AI車資查詢系統詳細指南

**開發工具：**
- `docs/BATCH_ALLOWANCE_GUIDE.md` - 批量加成處理與假期管理
- `docs/DATA_MIGRATION_GUIDE.md` - 資料搬移標準程序與注意事項
- `docs/CLEANUP_GUIDE.md` - 資料庫清理工具完整說明

### 🏗️ 專案模組架構 
```
minimal_flask/
├── modules/
│   ├── handlers/          # 業務邏輯處理器
│   │   ├── text_message_handler.py    # 🚨需重構：檔案過大
│   │   ├── temp_booking_handler.py    # ✅真AI功能
│   │   └── fixed_schedule_*_handler.py # 生產線邏輯
│   ├── services/          # 核心服務層
│   │   ├── smart_assistant.py         # 🤖 Gemini整合
│   │   ├── ai_fare_service.py         # 🎭 包裝本地算法
│   │   └── advanced_query_processor.py # 📊 SQL查詢引擎
│   ├── utils/             # 工具函數庫  
│   │   ├── unified_date_parser.py     # ✅統一日期解析
│   │   └── conversation_context.py   # 對話狀態管理
│   └── flex_designs/      # LINE Bot UI設計
├── docs/logs/             # 📋 完整運行日誌與問題追蹤
└── tests/                 # 🚨缺乏：需要完整測試框架
```

## DOCUMENTATION:

### 📚 必讀技術文檔 (MUST READ - Include these in your context window)

**LINE Messaging API & Bot Development:**
- url: https://developers.line.biz/en/docs/messaging-api/
  why: Webhook事件處理、Flex Message設計規範、用戶驗證機制、Quick Reply按鈕格式
  critical: Quick Reply的action.text屬性是必須的，缺少會導致400錯誤

**Google Gemini AI Integration:**  
- url: https://ai.google.dev/docs
  section: Prompting Guide, Image Processing, Text Generation
  why: 自然語言處理API、圖片識別與OCR、意圖分析與實體抽取
  critical: API金鑰配置錯誤會導致本地/雲端環境行為差異

**Flask & SQLAlchemy 架構:**
- url: https://flask-sqlalchemy.palletsprojects.com/
  why: 數據庫ORM操作、會話管理、查詢優化、多數據庫支援
  
**Python APScheduler:**
- url: https://apscheduler.readthedocs.io/
  why: 定時任務調度、cron表達式、任務持久化

### 📖 內部專案文檔 (Critical Context)

**問題分析與修復記錄:**
- docfile: docs/logs/claude健檢建議.txt
  why: 完整的程式碼品質分析報告，識別冗餘與失效程式碼
  
- docfile: docs/logs/有一點回魂了.txt  
  why: Render端AI服務配置問題的深度分析，本地vs雲端環境差異排查

- docfile: docs/AI_TRUTH_REPORT.md
  why: AI功能真實性分析，區分真AI vs包裝本地算法，成本評估

**架構設計精髓:**
- docfile: docs/REFACTOR_DUPLICATE_FUNCTIONS.md
  why: 日期解析函數重複實現問題的系統性解決方案

- docfile: CLEANUP_REPORT.md  
  why: 專案清理報告，已刪除檔案清單，架構整理結果

### 🔧 實施日誌與踩坑記錄

**運行時日誌分析:**
- file: docs/logs/日誌0202.txt
  why: 實際用戶交互日誌，展示系統運行模式與性能數據
  pattern: 觀察响應時間差異：AI功能>1秒，本地算法<0.1秒

- file: docs/logs/日誌1004.txt  
  why: 錯誤處理案例，展示Quick Reply按鈕格式問題與修復方法

## OTHER CONSIDERATIONS:

### 🚨 已知重大BUG (Critical Issues) 

**🔴 立即修復 (P0優先級):**

1. **Quick Reply按鈕格式錯誤** 
   ```python
   # ❌ 錯誤：缺少action.text屬性導致400錯誤
   {"type": "action", "action": {"type": "postback", "data": "...", "displayText": "..."}}
   
   # ✅ 正確：必須包含text屬性
   {"type": "action", "action": {"type": "postback", "text": "顯示文字", "data": "...", "displayText": "..."}}
   ```

2. **日期解析函數重複實現** ✅已解決 (2024年)
   - ✅ 已統一使用`modules/utils/unified_date_parser.py` 
   - ✅ 18個文件正確使用統一解析器
   - ✅ 查詢結果一致性問題已修復
   - ✅ 舊函數已設置轉發和棄用警告
   -  解決時間: 2024年下半年

3. **Render端AI信心度異常**
   - 本地端信心度=0.95，Render端=low
   - 根因: GOOGLE_APPLICATION_CREDENTIALS或API金鑰配置問題
   - 表現: 相同查詢觸發不同處理邏輯

**🟡 架構技術債 (P1優先級):**

4. **text_message_handler.py檔案過大重構**
   - 單一檔案承擔過多職責，違反單一責任原則
   - 需要拆分為專責處理器: booking_handler, query_handler, status_handler

5. **AI功能真實性問題 (AI Washing)**
   - 部分標示為"AI智能搜索"的功能實際使用本地算法
   - 需要明確區分真AI功能 vs 高效本地算法
   - 用戶界面標示需要誠實反映技術實現

### 🏗️ 已知架構模式與程式庫怪癖

```python
# CRITICAL: 日期解析統一模式
from modules.utils.unified_date_parser import UnifiedDateParser
# ❌ 不要直接import parse_date_input，會造成重複實現問題

# CRITICAL: LINE Bot API限制
# 使用reply_message而非push_message (免費政策限制)
line_bot_api.reply_message(reply_token, messages)  # ✅
# line_bot_api.push_message(user_id, messages)     # ❌ 會產生費用

# CRITICAL: Gemini API呼叫模式
# 必須處理網路超時和配額限制
try:
    response = gemini_client.generate_content(prompt, timeout=30)
except Exception as e:
    # 必須有fallback機制，不能讓AI失敗影響核心功能
    return local_algorithm_fallback(input_data)

# CRITICAL: 時區處理 
# 相對日期解析依賴正確的時區設定
os.environ['TZ'] = 'Asia/Taipei'  # Render端必須設定
```

### 🗂️ 當前程式庫結構與依賴

**Database Schema (三時間態設計):**
```sql
-- 未來態: 固定班表
fixed_schedules: id, schedule_data, status, created_at

-- 現在態: 活躍班次  
trips: trip_id, date, time, status, driver_id, start_point, end_point

-- 過去態: 已完成班次
completed_trips: id, date, meter_fare, extra_fare, driver_id, category
```

**期望程式庫結構 (重構目標):**
```bash
modules/
├── handlers/           # 拆分後的專責處理器
│   ├── booking_handler.py      # ✅ 真AI功能，已優化
│   ├── query_handler.py        # 📋 從text_message_handler拆出
│   ├── status_handler.py       # 📋 從text_message_handler拆出
│   └── conversation_handler.py # 📋 新增對話狀態管理
├── services/          # 核心業務邏輯
│   ├── ai_service.py          # 🤖 統一AI調用入口
│   ├── query_service.py       # 📊 統一查詢邏輯
│   └── notification_service.py # 📱 統一通知服務
└── utils/             # 統一工具函數
    ├── unified_date_parser.py # ✅ 已實現
    ├── response_formatter.py  # 📋 統一回應格式
    └── validation_utils.py    # 📋 統一驗證邏輯
```

### 🔒 安全考量與生產環境注意事項

**環境變數管理:**
```bash
# Render端必須設定的環境變數
GOOGLE_APPLICATION_CREDENTIALS=./path/to/service-account.json
GEMINI_API_KEY=your_gemini_api_key
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_access_token
TZ=Asia/Taipei  # 時區設定對日期解析至關重要
```

**安全限制:**
- LINE Webhook簽名驗證必須正確實現
- 用戶身份認證與群組權限控制
- API密鑰安全存儲，避免硬編碼
- SQL注入防護，使用參數化查詢
- 敏感數據日誌過濾

**性能考量:**
- 為常用查詢添加數據庫索引
- AI處理流程添加快取機制，避免重複調用
- 大量數據查詢需要分頁處理
- 定時任務避免重疊執行

### 🎯 反模式避免清單

- ❌ 不要創建新的日期解析函數，使用統一解析器
- ❌ 不要在handler層直接調用AI API，通過service層
- ❌ 不要忽略環境差異，本地測試不等於生產環境  
- ❌ 不要使用push_message，遵循LINE Bot免費政策
- ❌ 不要硬編碼時區和配置，使用環境變數
- ❌ 不要讓AI失敗影響核心功能，必須有fallback

這個系統展現了Taiwan計程車行業數位化的創新實踐，混合智能架構在成本控制與功能實現間取得了良好平衡，但需要系統性重構來解決技術債務。