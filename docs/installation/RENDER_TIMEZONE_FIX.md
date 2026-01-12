# Render 時區修復指南

## 問題分析
- **本地端（台灣）**："昨天" = 7/25 → 21筆正確結果
- **Render端（美國）**："昨天" = 7/24 → 42-47筆錯誤結果
- **絕對日期正常**：7/24、7/25 查詢結果一致

## 解決方案

### 方法1：設置Render環境變數（推薦）

在Render Dashboard中設置環境變數：
```
Key: TZ
Value: Asia/Taipei
```

### 方法2：修改代碼（備用）

如果環境變數無效，可在代碼中強制設置：

```python
# 在 app.py 或 modules/__init__.py 開頭添加
import os
os.environ['TZ'] = 'Asia/Taipei'
import time
time.tzset()  # 僅在Unix系統有效
```

### 驗證方法

部署後在LINE中測試：
1. 輸入：`昨天診所班次` 
2. 期望結果：21筆（與本地端一致）
3. 如果仍然是42-47筆，時區設置無效

## 技術說明

相對日期解析流程：
1. `get_taiwan_time()` 獲取當前台灣時間
2. `parse_date_input("昨天")` 計算昨天日期
3. 如果Render端時區錯誤，"昨天"會是錯誤日期
4. 導致查詢不同天的數據

絕對日期不受影響，因為直接指定了具體日期。 