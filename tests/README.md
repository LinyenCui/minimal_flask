# 派班系統測試套件

這是一個全面的測試套件，涵蓋了派班系統的所有核心功能，包括模型、服務、處理器、AI系統和工具函數。

## 📁 測試結構

```
tests/
├── conftest.py              # pytest配置和夾具
├── run_tests.py            # 測試運行器
├── test_models.py          # 資料模型測試
├── test_services.py        # 服務層測試
├── test_handlers.py        # 處理器層測試
├── test_ai_system.py       # AI系統測試
├── test_utils.py           # 工具函數測試
├── test_integration.py     # 整合測試
└── README.md               # 本文件
```

## 🧪 測試覆蓋範圍

### 1. 資料模型測試 (`test_models.py`)
- **Customer模型**: 客戶創建、唯一性約束
- **Driver模型**: 司機創建、車牌唯一性
- **Trip模型**: 班次創建、狀態轉換、30分鐘修改限制
- **FixedSchedule模型**: 固定班次模板、週次匯入邏輯
- **CompletedTrip模型**: 已完成班次記錄
- **模型關係**: 外鍵關聯、關係查詢

### 2. 服務層測試 (`test_services.py`)
- **TripService**: 班次創建、狀態更新、日期查詢
- **DriverService**: 司機指派、衝突檢測、可用司機查詢
- **SchedulerService**: 固定班次匯入、自動完成過期班次
- **ReportService**: 週報表生成、Google Drive上傳、司機統計
- **AIService**: 預約資訊提取、智能查詢處理
- **MessageService**: LINE消息發送、Flex消息

### 3. 處理器測試 (`test_handlers.py`)
- **MessageHandler**: 消息路由分發、命令解析
- **TextMessageHandler**: 幫助命令、班次查詢、司機指派
- **TripHandler**: 班次創建、狀態更新、詳情查詢
- **TempBookingHandler**: 臨時預約流程、確認處理
- **DriverHandler**: 司機指派、衝突檢查
- **FixedScheduleHandlers**: 固定班次匯入、請假處理
- **SpecialHandlers**: 批量加成、序列修復、資料庫同步

### 4. AI系統測試 (`test_ai_system.py`)
- **GeminiClient**: API初始化、調用測試
- **AIAgent**: 代理初始化、思考流程、工具執行
- **ToolRegistry**: 工具註冊、參數驗證、執行測試
- **KnowledgeBase**: 資料庫schema、業務規則、系統功能
- **AIRouter**: 路由決策、處理器分發
- **SmartAssistant**: 複雜查詢、司機查詢、狀態分析
- **AIFareService**: 車資查詢、趨勢分析
- **錯誤處理**: API失敗、參數錯誤、回退機制

### 5. 工具函數測試 (`test_utils.py`)
- **DateTimeUtils**: 台灣時間轉換、週次計算、日期解析
- **Helpers**: 貨幣格式化、電話驗證、距離計算、數字提取
- **LineBot**: 初始化、消息發送、快速回覆、Flex消息
- **ConversationContext**: 上下文存儲、檢索、過期
- **PassengerNameHandler**: 姓名提取、驗證
- **ModificationUtils**: 修改時間檢查、原因驗證
- **DatabaseUtils**: 連接檢查、安全查詢
- **PerformanceUtils**: 計時裝飾器、緩存工具
- **ErrorHandling**: 安全執行、輸入清理

### 6. 整合測試 (`test_integration.py`)
- **完整預約流程**: 端到端預約、AI處理
- **司機派遣流程**: 指派、衝突檢測
- **固定班次匯入流程**: 週次匯入、命令處理
- **報表生成流程**: 週報表、Google Drive上傳
- **AI系統整合**: 查詢處理、工具執行
- **錯誤處理流程**: 無效命令、資料庫錯誤、AI服務失敗
- **性能測試**: 並發請求、大數據集查詢
- **數據一致性**: 狀態一致性、關聯一致性

## 🚀 快速開始

### 1. 安裝依賴

```bash
# 基本測試依賴
pip install pytest pytest-cov pytest-html

# 額外依賴（如果需要）
pip install pytest-mock pytest-asyncio
```

### 2. 運行測試

```bash
# 使用測試運行器（推薦）
python tests/run_tests.py

# 直接使用pytest
pytest tests/ -v

# 運行特定測試類別
python tests/run_tests.py ai        # AI系統測試
python tests/run_tests.py models    # 模型測試
python tests/run_tests.py quick     # 快速測試
```

### 3. 生成覆蓋率報告

```bash
# 生成覆蓋率報告
python tests/run_tests.py coverage

# 查看HTML報告
open htmlcov/index.html
```

### 4. 生成測試報告

```bash
# 生成HTML測試報告
python tests/run_tests.py report
```

## 📊 測試運行選項

### 基本命令

```bash
python tests/run_tests.py [命令]
```

### 可用命令

| 命令 | 說明 |
|------|------|
| `(無參數)` | 運行完整測試套件 |
| `quick` | 運行快速測試（排除慢速測試） |
| `ai` | 運行AI系統測試 |
| `integration` | 運行整合測試 |
| `models` | 運行模型測試 |
| `services` | 運行服務測試 |
| `handlers` | 運行處理器測試 |
| `utils` | 運行工具測試 |
| `coverage` | 運行覆蓋率分析 |
| `report` | 生成HTML測試報告 |
| `pytest` | 使用pytest運行測試 |
| `help` | 顯示幫助信息 |

### pytest標記

```bash
# 運行特定標記的測試
pytest -m "not slow"           # 排除慢速測試
pytest -m "ai"                 # 只運行AI相關測試
pytest -m "integration"        # 只運行整合測試
pytest -m "database"           # 只運行資料庫相關測試
```

## 🔧 測試配置

### 環境變數

測試會自動設置以下環境變數：

```python
os.environ['TESTING'] = 'True'
os.environ['FLASK_ENV'] = 'testing'
```

### 測試數據庫

測試使用內存SQLite資料庫，每次測試後自動清理。

### Mock服務

測試中自動Mock以下外部服務：
- LINE Bot API
- Gemini AI API  
- Google Drive API

## 📝 編寫新測試

### 1. 使用pytest夾具

```python
def test_my_feature(db_session, sample_drivers, mock_line_bot_api):
    # 使用預設的測試數據和Mock服務
    pass
```

### 2. 使用測試數據工廠

```python
def test_with_custom_data(data_factory, db_session):
    trip = data_factory.create_trip(
        start_point="自訂起點",
        actual_fare=200
    )
    db_session.add(trip)
    db_session.commit()
```

### 3. 使用斷言助手

```python
def test_trip_equality(assertions):
    trip1 = Trip(...)
    trip2 = Trip(...)
    
    assertions.assert_trip_equals(trip1, trip2)
```

### 4. 測試標記

```python
import pytest

@pytest.mark.slow
def test_slow_operation():
    pass

@pytest.mark.ai
def test_ai_feature():
    pass
```

## 🎯 測試最佳實踐

### 1. 測試命名

- 使用描述性的測試名稱
- 遵循 `test_[功能]_[條件]_[期望結果]` 格式

```python
def test_driver_assignment_with_conflict_should_fail():
def test_trip_creation_with_valid_data_should_succeed():
```

### 2. 測試組織

- 每個測試只測試一個功能點
- 使用AAA模式：Arrange, Act, Assert
- 清理測試數據

### 3. Mock使用

- 只Mock外部依賴
- 驗證Mock被正確調用
- 保持Mock簡單

### 4. 斷言

- 使用具體的斷言而非True/False
- 提供有意義的錯誤消息
- 測試邊界條件

## 🐛 故障排除

### 常見問題

1. **ImportError**: 確保項目根目錄在Python路徑中
2. **Database errors**: 檢查測試數據庫設置
3. **Mock failures**: 確認Mock路徑正確
4. **Slow tests**: 使用 `quick` 命令排除慢速測試

### 調試技巧

```python
# 在測試中添加調試信息
import pdb; pdb.set_trace()

# 使用pytest的詳細輸出
pytest -v -s tests/test_specific.py::test_function
```

## 📈 持續集成

### GitHub Actions

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: python tests/run_tests.py coverage
```

### 覆蓋率要求

目標測試覆蓋率：
- 模型: > 90%
- 服務: > 85%
- 處理器: > 80%
- 工具: > 85%
- 整體: > 85%

## 🤝 貢獻指南

1. 為新功能編寫測試
2. 確保所有測試通過
3. 保持測試覆蓋率
4. 更新測試文檔
5. 遵循測試命名規範

---

**注意**: 這個測試套件是根據專案分析生成的完整測試框架。某些測試可能需要根據實際實現進行調整。建議從基本的模型測試開始，逐步添加更複雜的功能測試。