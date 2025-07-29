# modules/__init__.py
from flask import Flask
from linebot.v3 import WebhookParser
from linebot.v3.messaging import MessagingApi, Configuration
from modules.config import Config
from modules.models.base import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 初始化數據庫
    db.init_app(app)
    
    # 導入並註冊藍圖
    from modules.handlers.message_handler import webhook_bp
    app.register_blueprint(webhook_bp)
    
    # 設定日誌
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    return app
