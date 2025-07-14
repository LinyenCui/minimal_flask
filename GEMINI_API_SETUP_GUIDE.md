# Gemini API 配置指南

## 🎯 問題分析

您的 **Usage-Based Spending: $0 / $50** 沒有使用到的原因是：

### ❌ 當前狀態
- ✅ AI系統代碼完整 (ai_router.py, ai_service.py)
- ❌ Gemini API憑證未配置
- ❌ 環境變數缺失
- ❌ 所有AI功能回退到基本匹配，不產生API調用

## 🔧 解決方案

### 步驟1：取得Google Cloud憑證

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 選擇項目：`chrome-flight-458709-d1`
3. 啟用 **Vertex AI API**
4. 創建服務帳戶並下載JSON憑證文件

### 步驟2：配置環境變數

在您的 `.env` 文件中添加：

```env
# Google Cloud / Gemini API 配置
GCP_PROJECT_ID=chrome-flight-458709-d1
GCP_LOCATION=us-central1
GEMINI_MODEL=gemini-2.0-flash-001
GOOGLE_APPLICATION_CREDENTIALS=chrome-flight-458709-d1-cc3bdb1f0846.json
```

### 步驟3：放置憑證文件

將下載的JSON憑證文件重命名為 `chrome-flight-458709-d1-cc3bdb1f0846.json` 並放在項目根目錄。

### 步驟4：測試配置

```bash
# 測試AI路由器
python test_ai_router.py

# 測試AI服務
python -c "from modules.services.ai_service import test_gemini_extraction; test_gemini_extraction()"
```

## 🚀 配置完成後的效果

✅ **自然語言理解**：
- "我要查詢今天的東洋班次" → 正確路由到當前班次查詢
- "昨天司機123的車資是多少？" → 正確路由到已完成班次查詢

✅ **API使用量**：
- 每次AI分析會消耗 Gemini API 調用
- Usage-Based Spending 開始計算實際使用量

✅ **三時間態智能路由**：
- 過去：已完成班次查詢
- 現在：當前班次管理  
- 未來：固定班次規劃

## 📊 預期API使用量

- **意圖分析**：每次自然語言請求 1 次調用
- **複雜查詢**：可能需要 2-3 次調用
- **每月預估**：100-500 次調用（視使用頻率）

## 🔍 驗證方法

配置完成後，測試以下自然語言命令：

```
測試1: "我要查詢今天的診所班次"
期望: 正確識別為present + query + trips

測試2: "昨天司機123的車資統計"  
期望: 正確識別為past + query + completed_trips

測試3: "明天要匯入固定班次"
期望: 正確識別為future + create + fixed_schedules
```

## 🎉 配置成功指標

- ✅ test_ai_router.py 通過所有測試
- ✅ 日誌顯示 "AI路由器已成功初始化"
- ✅ 自然語言請求獲得智能回應
- ✅ Usage-Based Spending 開始計算使用量

---

**注意**: 配置完成後，您的AI系統才會真正開始工作，並開始使用您的50調用額度。 