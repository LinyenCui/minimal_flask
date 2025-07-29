# 🚀 派車管理系統安裝指南

## 📋 系統需求

### 🖥️ 硬體需求
- **CPU**: 2核心以上
- **記憶體**: 4GB RAM 以上（建議 8GB）
- **儲存空間**: 20GB 可用空間
- **網路**: 穩定的網際網路連線

### 💻 軟體需求
- **作業系統**: Linux (Ubuntu 20.04+) / macOS 10.15+ / Windows 10+
- **Python**: 3.9 或以上版本
- **PostgreSQL**: 13.0 或以上版本
- **Node.js**: 16.0+ (用於前端工具，可選)

## 🛠️ 環境準備

### 1. 安裝 Python 環境

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

#### macOS
```bash
# 使用 Homebrew
brew install python@3.11

# 或從官網下載安裝
# https://www.python.org/downloads/macos/
```

#### Windows
```bash
# 從官網下載 Python 安裝程式
# https://www.python.org/downloads/windows/
# 安裝時記得勾選 "Add Python to PATH"
```

### 2. 安裝 PostgreSQL

#### Ubuntu/Debian
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS
```bash
brew install postgresql
brew services start postgresql
```

#### Windows
```bash
# 從官網下載 PostgreSQL 安裝程式
# https://www.postgresql.org/download/windows/
```

### 3. 安裝 Git
```bash
# Ubuntu/Debian
sudo apt install git

# macOS
brew install git

# Windows
# 從官網下載 Git 安裝程式
# https://git-scm.com/download/win
```

## 📦 系統安裝

### 1. 下載專案
```bash
git clone <repository-url>
cd minimal_flask
```

### 2. 建立虛擬環境
```bash
python3 -m venv venv

# 啟動虛擬環境
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. 安裝依賴套件
```bash
pip install -r requirements.txt
```

如果遇到 `psycopg2-binary` 安裝問題：
```bash
# Ubuntu/Debian
sudo apt install libpq-dev python3-dev

# macOS
brew install postgresql

# Windows
# 確保已安裝 Microsoft Visual C++ Build Tools
```

### 4. 資料庫設定

#### 建立資料庫
```bash
sudo -u postgres psql

CREATE DATABASE dispatch_db;
CREATE USER dispatch_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dispatch_db TO dispatch_user;
\q
```

#### 初始化資料庫結構
```bash
python3 -c "
from modules.models.base import init_db_app
from modules import create_app
app = create_app()
with app.app_context():
    init_db_app(app)
"
```

## ⚙️ 環境變數配置

### 1. 建立環境變數檔案
```bash
# 本地開發環境
cp .env.example .env.dev

# 生產環境
cp .env.example .env
```

### 2. 設定必要的環境變數

#### `.env.dev` (本地開發)
```bash
# 基本設定
FLASK_ENV=development
DEBUG=True

# 資料庫設定
LOCAL_DB_HOST=localhost
LOCAL_DB_USER=dispatch_user
LOCAL_DB_NAME=dispatch_db
LOCAL_DB_PASSWORD=your_password
LOCAL_DB_PORT=5432

# Line Bot 設定
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_TOKEN=your_line_channel_access_token

# AI 服務設定
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/credentials.json
VERTEX_AI_PROJECT_ID=your_project_id
VERTEX_AI_LOCATION=asia-east1

# Google Drive 設定
GOOGLE_DRIVE_CREDENTIALS=path/to/drive_credentials.json
```

#### `.env` (生產環境)
```bash
# 基本設定
FLASK_ENV=production
DEBUG=False

# 資料庫設定（本地）
LOCAL_DB_HOST=localhost
LOCAL_DB_USER=dispatch_user
LOCAL_DB_NAME=dispatch_db
LOCAL_DB_PASSWORD=production_password

# Render 資料庫設定
RENDER_DB_HOST=your_render_host
RENDER_DB_USER=your_render_user
RENDER_DB_NAME=your_render_db
RENDER_DB_PASSWORD=your_render_password

# Line Bot 設定
LINE_CHANNEL_SECRET=production_line_secret
LINE_CHANNEL_TOKEN=production_line_token

# AI 服務設定
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
VERTEX_AI_PROJECT_ID=your_production_project
VERTEX_AI_LOCATION=asia-east1
```

## 🔑 第三方服務設定

### 1. Line Bot 設定
參考 [Line Bot 開發者指南](https://developers.line.biz/zh-hant/)

1. 建立 Line Messaging API 頻道
2. 取得 Channel Secret 和 Channel Access Token
3. 設定 Webhook URL: `https://your-domain.com/callback`

### 2. Google Cloud AI 設定
參考 [Gemini API 設定指南](./GEMINI_API_SETUP_GUIDE.md)

1. 建立 Google Cloud 專案
2. 啟用 Vertex AI API
3. 建立服務帳號金鑰
4. 下載憑證檔案

### 3. Google Drive 設定
參考 [Google Drive 設定指南](./google_drive_setup.md)

1. 建立 Google Cloud 專案（可與 AI 共用）
2. 啟用 Google Drive API
3. 建立服務帳號
4. 分享目標資料夾給服務帳號

## 🚀 啟動系統

### 1. 開發環境啟動
```bash
# 啟動虛擬環境
source venv/bin/activate

# 啟動開發服務器
python3 app.py
```

系統會在 `http://localhost:3000` 上運行

### 2. 生產環境部署

#### 使用 Gunicorn
```bash
# 安裝 Gunicorn
pip install gunicorn

# 啟動服務
gunicorn -w 4 -b 0.0.0.0:3000 app:app
```

#### 使用 Docker（建議）
```bash
# 建立 Docker 映像
docker build -t dispatch-system .

# 運行容器
docker run -d \
  -p 3000:3000 \
  -v /path/to/credentials:/app/credentials \
  --env-file .env \
  dispatch-system
```

## 🧪 系統測試

### 1. 基本功能測試
```bash
# 測試資料庫連接
python3 -c "
from modules.models.base import db
from modules import create_app
app = create_app()
with app.app_context():
    db.engine.execute('SELECT 1')
    print('資料庫連接成功')
"

# 測試 AI 服務
python3 -c "
from modules.services.ai_service import extract_booking_info_with_gemini
result = extract_booking_info_with_gemini('明天下午2點要去機場')
print('AI 服務測試:', result is not None)
"
```

### 2. Line Bot 測試
1. 在 Line 後台設定正確的 Webhook URL
2. 加入 Bot 為好友
3. 傳送測試訊息：`幫助`
4. 確認收到回應

### 3. 增量同步測試
```bash
# 執行同步測試
python3 test_incremental_sync.py

# 或在 Line 中測試
# 傳送：同步狀態
```

## 🔧 常見問題排除

### 資料庫連接問題
```bash
# 檢查 PostgreSQL 服務狀態
sudo systemctl status postgresql

# 檢查資料庫連接
psql -h localhost -U dispatch_user -d dispatch_db
```

### Python 套件安裝問題
```bash
# 升級 pip
pip install --upgrade pip

# 清除套件快取
pip cache purge

# 重新安裝套件
pip install -r requirements.txt --force-reinstall
```

### 權限問題
```bash
# 修正檔案權限
chmod +x app.py

# 修正目錄權限
chmod -R 755 modules/
```

## 📊 效能調整

### 1. 資料庫優化
```sql
-- 建立索引
CREATE INDEX idx_trips_date ON trips(date);
CREATE INDEX idx_trips_status ON trips(status);
CREATE INDEX idx_completed_trips_date ON completed_trips(date);
```

### 2. 系統監控
```bash
# 安裝系統監控工具
pip install psutil

# 設定日誌輪轉
sudo apt install logrotate
```

## 🔄 系統更新

### 1. 更新程式碼
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### 2. 資料庫遷移
```bash
# 備份資料庫
pg_dump dispatch_db > backup_$(date +%Y%m%d).sql

# 執行遷移
python3 scripts/migrate_database.py
```

### 3. 重啟服務
```bash
# 開發環境
# Ctrl+C 停止，然後重新啟動

# 生產環境
sudo systemctl restart dispatch-system
```

## 📞 技術支援

### 問題回報
- 查看 [常見問題](../troubleshooting/FAQ.md)
- 檢查 [調試指南](../troubleshooting/DEBUGGING.md)
- 聯繫技術支援團隊

### 獲得幫助
- 在 Line 群組中輸入 `技術支援`
- 查看 [完整文檔](../README.md)
- 參考 [API 文檔](../api/)

---

*安裝完成後，建議閱讀 [快速入門指南](../user-guides/QUICK_START.md) 了解系統基本使用方法。*