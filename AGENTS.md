# 智能 LINE Bot 派班管理系統 - Claude 實作指南

> **最後更新**：2026-01-12

這是一個結合真實 AI 技術與三時間態架構的 Taiwan 計程車調度平台，支援自然語言交互、智能路由決策和企業級派班解決方案。

---

## 核心原則

**重要：在所有程式變更和功能開發中必須遵循以下原則：**

### KISS (Keep It Simple, Stupid)
- 設計應以簡潔為目標，避免過度工程化
- 選擇直觀的解決方案而非複雜的實作

### YAGNI (You Aren't Gonna Need It)
- 只實作當前需要的功能
- 不要為未來可能用到的功能提前開發

### 穩定性優先
- **關鍵業務功能必須有傳統處理路徑**，不能完全依賴 AI
- 任何新功能都必須考慮降級機制
- 修改現有功能時必須確保向後兼容

---

## Cursor Cloud specific instructions

### 服務概覽

This is a Flask-based LINE Bot dispatch management system with PostgreSQL. The main services are:

| Service | How to run | Port |
|---------|-----------|------|
| Flask Web Server | `python3 app.py` | 3000 |
| PostgreSQL | `sudo service postgresql start` | 5432 |

### 環境變數

Set these environment variables before running the app:

```bash
export LINE_CHANNEL_TOKEN="dummy_token_for_local_dev"
export LINE_CHANNEL_SECRET="dummy_secret_for_local_dev"
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/dispatch_db"
export FLASK_ENV="development"
export TZ="Asia/Taipei"
```

For actual LINE Bot testing, real `LINE_CHANNEL_TOKEN` and `LINE_CHANNEL_SECRET` are needed.

### 啟動 PostgreSQL

```bash
sudo service postgresql start
```

Default credentials: `postgres:postgres`, database: `dispatch_db`. Tables are auto-created by `db.create_all()` on app startup.

### 啟動 Flask 應用

```bash
cd /workspace && python3 app.py
```

The app starts on port 3000. Key endpoints:
- `/` — health check
- `/callback` — LINE webhook (requires valid LINE signature)
- `/admin/database-tools` — admin panel
- `/test_env` — environment diagnostics
- `/memory_stats` — memory usage stats
- `/render_diagnosis` — system diagnosis

### 執行測試

```bash
python3 -m pytest tests/ --ignore=tests/legacy/ --ignore=tests/test_line_bot.py -v
```

**注意事項**:
- Tests in `tests/test_models.py` hang because `create_app()` binds SQLAlchemy engine to PostgreSQL, but the test tries to override to SQLite after engine creation. This causes connection pool deadlocks. Running these tests requires PostgreSQL to be running and clean (no stale `idle in transaction` connections).
- If tests hang, check for stale PostgreSQL connections: `PGPASSWORD=postgres psql -h localhost -U postgres -d dispatch_db -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'dispatch_db' AND state = 'idle in transaction' AND pid != pg_backend_pid();"`
- `tests/test_line_bot.py` has a broken import (`modules.flex_designs.quick_reply_designs` does not exist). Skip it with `--ignore=tests/test_line_bot.py`.
- Working test files: `test_utils.py`, `test_unified_date_parser.py`, `test_quick_reply_refactor.py` (these run without PostgreSQL dependencies).

### Lint

```bash
python3 -m flake8 app.py modules/ --max-line-length=120 --select=E9,F63,F7,F82
```

No dedicated lint config file exists. The above command checks for critical errors only.

### 重要注意事項

- **Vertex AI**: The app tries to load a GCP service account key file (`chrome-flight-458709-d1-cc3bdb1f0846.json`) on startup. Without it, AI features are disabled but the app still runs fine with traditional parsing fallback.
- **Port conflicts**: If port 3000 is occupied from previous runs, use `fuser 3000/tcp` to find and kill the process.
- **Scheduler blocking**: `app.py` runs startup tasks (update completed trips, initialize unique codes, schedule trip updates) before `app.run()`. These require a clean PostgreSQL connection. If stale transactions exist, they can block startup.
- Refer to `CLAUDE.md` for detailed architecture, three-time-state design, and development conventions.
