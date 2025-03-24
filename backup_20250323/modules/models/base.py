# modules/models/base.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db_app(app):
    """初始化數據庫與應用程序的連接"""
    db.init_app(app)
    
def get_db():
    """獲取數據庫實例"""
    return db
