# LINE Bot 派班系統重構說明

## 重構概述

此次重構將原有的單一 `app.py` 文件拆分為多個模組，採用了更清晰的架構，提高了代碼的可維護性和擴展性。

### 目錄結構

```
modules/
  ├── __init__.py           # 主模組初始化文件
  ├── config.py             # 應用配置模組
  ├── init_db.py            # 資料庫初始化模組
  ├── flex_designs/         # Flex Message 設計模組
  │   ├── __init__.py
  │   └── booking_flex.py   # 預約相關 Flex 設計
  ├── handlers/             # 處理程序模組
  │   ├── __init__.py
  │   ├── booking_handler.py # 預約處理程序
  │   └── trip_status_handler.py # 班次狀態處理程序
  ├── models/               # 資料庫模型模組
  │   ├── __init__.py
  │   ├── base.py           # 基本資料庫設定
  │   └── models.py         # 資料庫模型定義
  ├── routes/               # 路由模組
  │   ├── __init__.py
  │   └── webhook.py        # Webhook 路由處理
  ├── schedulers/           # 排程任務模組
  │   ├── __init__.py
  │   └── trip_schedulers.py # 班次狀態排程任務
  ├── services/             # 服務模組
  │   ├── __init__.py
  │   ├── message_service.py # 訊息處理服務
  │   └── postback_service.py # Postback 處理服務
  └── utils/                # 工具模組
      ├── __init__.py
      ├── helpers.py        # 通用工具函數
      └── line_bot.py       # LINE Bot 配置和工具
```

## 重要改進

1. **模組化結構**: 採用模組化設計，將不同功能分散到不同模組中
2. **清晰的職責分離**:
   - `models`: 專注於數據結構定義
   - `handlers`: 專注於具體業務邏輯處理
   - `services`: 協調不同處理程序
   - `routes`: 處理 HTTP 請求和路由
   - `utils`: 提供通用工具函數
   - `flex_designs`: 集中管理 Flex Message 設計
   - `schedulers`: 管理自動排程任務

3. **錯誤處理**: 改進了錯誤處理機制，增加了日誌記錄
4. **前綴處理**: 統一處理群組聊天中的命令前綴
5. **PostbackAction**: 使用 PostbackAction 替代 MessageAction，提升群組中的使用體驗

## 功能說明

1. **預約功能**:
   - 完整的預約流程，包含日期選擇、時間選擇、地點選擇、確認等步驟
   - 使用 Flex Message 提供更友好的用戶界面
   - 支持返回前一步、取消預約等操作

2. **班次狀態管理**:
   - 支持修改班次狀態
   - 提供確認機制，避免誤操作
   - 處理特殊狀態（請假、衝突等）

3. **自動排程任務**:
   - 自動將過期的準備狀態班次更新為完成狀態
   - 為未來的班次安排自動更新任務
   - 自動為班次生成唯一識別碼

## 使用方法

1. **安裝依賴**:
```bash
pip install -r requirements.txt
```

2. **設置環境變量**:
創建 `.env` 文件，包含以下內容：
```
LINE_CHANNEL_TOKEN=你的LINE_CHANNEL_TOKEN
LINE_CHANNEL_SECRET=你的LINE_CHANNEL_SECRET
DATABASE_URL=postgresql://使用者名稱:密碼@localhost:5432/資料庫名稱
```

3. **初始化資料庫**:
```bash
python -c "from modules.init_db import create_database, init_db; create_database(); init_db()"
```

4. **啟動應用**:
```bash
python app.py
```

5. **設置 LINE Bot Webhook URL**:
在 LINE Developers 控制台設置 Webhook URL 為 `https://您的域名/callback`

## 命令列表

- `預約` - 開始預約流程
- `修改狀態 [班次ID] [新狀態]` - 更改班次狀態
- `確認取消 [班次ID]` - 確認取消班次
- `確認請假 [班次ID]` - 確認請假班次
- `確認衝突 [班次ID]` - 確認衝突班次
- `幫助` - 顯示幫助訊息

在群組中使用時，需在命令前添加前綴：!、# 或 /，例如：`!預約`、`#幫助` 