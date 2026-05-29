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

# 連線池韌性 — 修 Render Postgres 閒置斷線造成的
# 「SSL connection has been closed unexpectedly」(查詢/LIFF 完成後 push 間歇性失敗):
#   pool_pre_ping  取連線前先 ping,死連線自動丟棄重連(根治 stale 連線被發出)
#   pool_recycle   連線用超過 280s 就主動回收,早於 Render 閒置斷線門檻
#   keepalives     TCP 層保活,減少閒置被中斷(libpq 參數,psycopg/psycopg2 皆通用)
_engine_kwargs = {
    'pool_pre_ping': True,
    'pool_recycle': 280,
}
if url.startswith('postgresql'):
    _engine_kwargs['connect_args'] = {
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
    }
engine = create_engine(url, **_engine_kwargs)

# 創建會話
Session = sessionmaker(bind=engine)

# 創建基類
Base = declarative_base() 