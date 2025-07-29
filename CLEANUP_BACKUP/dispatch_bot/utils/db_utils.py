from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# 創建數據庫實例
db = SQLAlchemy()

def init_db(app):
    """初始化數據庫"""
    db.init_app(app)
    return db

def execute_query(query, params=None):
    """執行 SQL 查詢"""
    if params is None:
        params = {}
    return db.session.execute(text(query), params)

def commit():
    """提交事務"""
    db.session.commit() 