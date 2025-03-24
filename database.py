# 資料庫連接模塊

from sqlalchemy import create_engine, Column, Integer, String, Date, Time, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

# 使用環境變量或配置獲取資料庫連接信息
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'password')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'dispatch_db')

# 創建資料庫引擎
engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# 創建會話
Session = sessionmaker(bind=engine)

# 創建基類
Base = declarative_base() 