# AI車資修改確認機制

## 🚨 重要：這是核心用戶保護機制，任何修改都要保留！

### 完整流程
1. **用戶發起**：`我要修改2014的車資`（信息不完整）
2. **AI理解**：智能助手生成 `記錄車資 2014` 
3. **對話收集**：AI車資服務啟動對話模式
4. **用戶輸入**：提供車資數額 `280 -280`
5. **詢問原因**：AI要求說明修改原因
6. **用戶提供**：原因 `前一班延誤，導致無法搭載`
7. **⭐ 確認框**：顯示詳細修改信息 + Quick Reply
8. **用戶選擇**：「確認修改」或「取消修改」
9. **執行結果**：修改或取消

### 關鍵技術實現

#### 1. 對話狀態管理
```python
# 步驟1: waiting_reason (等待修改原因)
# 步驟2: waiting_confirmation (等待用戶確認)
```

#### 2. 確認框Quick Reply
```python
quick_reply_items = [
    QuickReplyItem(action=MessageAction(label="✅ 確認修改", text="確認修改")),
    QuickReplyItem(action=MessageAction(label="❌ 取消修改", text="取消修改"))
]
```

#### 3. 確認框信息內容
- 📋 班次ID和類別
- 📍 起終點路線  
- 🚗 司機信息
- 💰 費用變更對比
- 📊 總計變化金額
- 📝 修改原因

### 🔒 用戶權利保障
- **永遠有取消權利**：任何時候都可以取消修改
- **完整信息透明**：所有變更細節都清楚顯示
- **明確確認機制**：必須主動選擇才執行修改
- **降級處理**：Quick Reply失效時仍可用文字回覆

### 📂 涉及文件
- `modules/handlers/text_message_handler.py` - 主要對話邏輯
- `modules/utils/line_bot.py` - Quick Reply消息發送
- `modules/services/ai_fare_service.py` - AI車資服務
- `modules/utils/conversation_context.py` - 對話狀態管理

### ⚠️ 修改注意事項
1. **絕對不能跳過確認框** - 這是用戶保護機制
2. **保留Quick Reply** - 提供最佳用戶體驗
3. **維持對話狀態** - waiting_confirmation 步驟是必需的
4. **錯誤降級** - Quick Reply失效時要有備案

### 🧪 測試場景
1. 完整確認流程測試
2. 取消修改測試  
3. Quick Reply點擊測試
4. 文字回覆確認測試
5. 錯誤情況降級測試

---
**創建日期**: 2025-01-17  
**最後更新**: 2025-01-17  
**重要程度**: 🚨 最高 - 用戶數據保護核心機制

---

## 🚨 AI路由邏輯統一警告

### ⚠️ 重要提醒：避免多重AI處理邏輯衝突

在修復車資修改功能時，**絕對不能重新引入多重AI處理邏輯**！

**歷史教訓**：我們在 cursor_2.md 第24655行記錄了完整的AI路由邏輯衝突解決過程：

#### 🚫 禁止的多重AI邏輯：
```python
# ❌ 錯誤：三層AI處理衝突
1. 智能助手系統（Line 1043+）→ handle_smart_fare_query
2. AI車資查詢系統（Line 987）→ should_use_ai_query  
3. 第三層智能助手調用（Line 1209+）→ 重複邏輯
```

#### ✅ 正確的統一邏輯：
```python
# ✅ 正確：智能助手作為唯一入口
智能助手 → 理解意圖 → 路由到具體服務
- 車資查詢 → handle_smart_fare_query
- 班次查詢 → AdvancedQueryProcessor
- 其他命令 → 對應處理器
```

### 🔧 修復原則：
1. **智能助手是唯一AI入口**
2. **移除所有 should_use_ai_query 調用**  
3. **統一命令執行邏輯**
4. **避免無限遞歸**

### 📋 檢查清單：
- [ ] 確認只有一個智能助手調用點
- [ ] 移除重複的 should_use_ai_query
- [ ] 統一 handle_smart_fare_query 調用
- [ ] 保持確認框機制完整

**任何修改前都要先檢查這個警告！** 