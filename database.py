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

# 創建資料庫引擎（優先使用環境變數 DATABASE_URL；動態選擇驅動）
def _resolve_sqlalchemy_db_url(raw_url: str) -> str:
    url = raw_url or ''
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if '+psycopg' in url or '+psycopg2' in url:
        return url
    driver = None
    try:
        import psycopg  # psycopg3
        driver = 'psycopg'
    except Exception:
        try:
            import psycopg2  # noqa: F401
            driver = 'psycopg2'
        except Exception:
            driver = None
    if driver and url.startswith('postgresql://'):
        url = f'postgresql+{driver}://' + url[len('postgresql://'):]
    return url

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    url = _resolve_sqlalchemy_db_url(DATABASE_URL)
else:
    url = _resolve_sqlalchemy_db_url(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

engine = create_engine(url)

# 創建會話
Session = sessionmaker(bind=engine)

# 創建基類
Base = declarative_base() 