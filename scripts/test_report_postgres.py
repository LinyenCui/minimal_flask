#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
測試使用PostgreSQL數據庫生成週報表
"""

import os
from flask import Flask
from app import generate_weekly_report, db

# 創建一個測試用的 Flask 應用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:0720@localhost:5432/dispatch_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化數據庫
db.init_app(app)

# 在應用上下文中執行測試
with app.app_context():
    print("開始生成週報表...")
    result, filename = generate_weekly_report()
    print(result)

    if filename:
        print(f"報表已生成: {filename}")
        # 檢查文件是否存在
        if os.path.exists(filename):
            print(f"文件大小: {os.path.getsize(filename)} 字節")
        else:
            print("警告: 文件未找到!")
    else:
        print("報表生成失敗!")