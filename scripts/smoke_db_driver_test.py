#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡易煙囪測試：驗證 db 驅動、URL 以及最小 SELECT 1。
不修改資料，只印出狀態，方便本地與 Render 同步檢查。

用法：
  python3 scripts/smoke_db_driver_test.py
"""
from __future__ import annotations

import os
import sys

# 確保可以從專案根目錄匯入（避免從其他工作目錄啟動時找不到 database）
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 優先載入 .env / .env.dev（若存在）
try:  # optional
    from dotenv import load_dotenv  # type: ignore
    # 兩個都試，後載入的會覆蓋前者
    load_dotenv(os.path.join(ROOT_DIR, '.env'))
    load_dotenv(os.path.join(ROOT_DIR, '.env.dev'))
except Exception:
    pass

# 版本資訊
try:
    import sqlalchemy
except Exception as exc:  # pragma: no cover
    print("[X] SQLAlchemy 未安裝:", exc)
    sys.exit(1)

try:
    import psycopg
except Exception as exc:  # pragma: no cover
    print("[X] psycopg3 未安裝:", exc)
    sys.exit(1)

from sqlalchemy import text

print("Python:", sys.version.split()[0])
print("SQLAlchemy:", sqlalchemy.__version__)
print("psycopg:", psycopg.__version__)

# 顯示（遮罩後的）DATABASE_URL
raw_env_url = os.environ.get("DATABASE_URL", "<未設定>")
print("ENV DATABASE_URL:", raw_env_url)

# 直接從 database.py 取得底層 engine（含自動升級邏輯）
from database import engine as raw_engine
print("Raw engine driver =", raw_engine.url.drivername)
print("Raw engine url    =", raw_engine.url)

# 透過 Flask‑SQLAlchemy 取得 app engine 與 db
from modules import create_app, db
app = create_app()
with app.app_context():
    print("App engine driver =", db.engine.url.drivername)
    print("App engine url    =", db.engine.url)
    # 最小連線測試
    try:
        db.session.execute(text("SELECT 1"))
        print("SELECT 1 → OK")
    except Exception as e:
        print("SELECT 1 → FAIL:", repr(e))
        sys.exit(2)

print("[OK] 驅動、URL 與連線檢查完成")
