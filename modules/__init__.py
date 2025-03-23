# modules/__init__.py
from flask import Flask
from linebot.v3 import WebhookParser
from linebot.v3.messaging import MessagingApi, Configuration
from modules.config import LINE_CHANNEL_TOKEN, LINE_CHANNEL_SECRET, DATABASE_URL, DEBUG
from modules.models.base import init_db_app
import os

def create_app():
    app = Flask(__name__)
    
    # 配置
    app.config['LINE_CHANNEL_TOKEN'] = os.environ.get('LINE_CHANNEL_TOKEN', '')
    app.config['LINE_CHANNEL_SECRET'] = os.environ.get('LINE_CHANNEL_SECRET', '')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/dispatch_db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # 初始化數據庫
    init_db_app(app)
    
    # 導入並註冊藍圖
    from modules.routes.webhook import webhook_bp
    app.register_blueprint(webhook_bp)
    
    # 設定日誌
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    return app
