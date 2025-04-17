# modules/config.py
import os

# LINE Bot設定
LINE_CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# 資料庫設定
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/dispatch_db')

# 命令前綴設定
COMMAND_PREFIXES = ['!', '#', '/']

# 其他設定
DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
