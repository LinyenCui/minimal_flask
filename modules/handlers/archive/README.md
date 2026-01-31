# 歸檔：舊預約系統

> **歸檔日期**：2026-01-13
> **原因**：遷移到 AI Function Calling 預約系統

## 歸檔檔案

| 檔案 | 說明 |
|------|------|
| `temp_booking_handler.py` | 舊的預約叫車 handler（使用 AI 提取信息 + 多輪追問） |
| `temp_booking_session.py` | 預約狀態管理外觀層 |

## 新系統

預約功能現在由 `customers_ai_handler.py` 處理，使用 Gemini Function Calling：

- **入口**：`webhook.py` 智能判斷預約意圖
- **處理**：`customers_ai_service.py` 的 `booking_create` Function
- **優點**：
  - 不需要「預約叫車」觸發詞
  - 自然語言直接描述即可
  - 缺失信息自動追問
  - 統一的確認機制

## 備用開關

如需切回舊系統：

```python
# webhook.py
USE_AI_BOOKING = False  # 切回舊系統
```

然後取消 `text_message_handler.py` 中的註釋。
