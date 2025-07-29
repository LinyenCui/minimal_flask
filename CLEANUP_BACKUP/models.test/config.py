# modules/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE Bot設定
    LINE_CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN')
    LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
    
    # 資料庫設定
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 其他設定
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
