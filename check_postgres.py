#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
檢查PostgreSQL數據庫中的completed_trips表數據
"""

from flask import Flask
from sqlalchemy import create_engine, text

# 創建一個測試用的 Flask 應用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:0720@localhost:5432/dispatch_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 直接使用SQLAlchemy引擎
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])

# 查詢PostgreSQL數據庫中的completed_trips表數據
try:
    with engine.connect() as conn:
        # 檢查表是否存在
        result = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'completed_trips')"))
        table_exists = result.scalar()
        
        if not table_exists:
            print("PostgreSQL數據庫中不存在completed_trips表")
        else:
            # 查詢表中的數據
            result = conn.execute(text("SELECT * FROM completed_trips"))
            rows = result.fetchall()
            
            print(f"PostgreSQL數據庫中的completed_trips表有 {len(rows)} 條記錄:")
            for row in rows:
                print(row)
except Exception as e:
    print(f"連接PostgreSQL數據庫時出錯: {str(e)}")

# 查詢SQLite數據庫中的completed_trips表數據
import sqlite3

try:
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM completed_trips")
    rows = cursor.fetchall()
    
    print(f"\nSQLite數據庫中的completed_trips表有 {len(rows)} 條記錄:")
    for row in rows:
        print(row)
    
    conn.close()
except Exception as e:
    print(f"連接SQLite數據庫時出錯: {str(e)}") 