# modules/__init__.py
from flask import Flask
from linebot.v3 import WebhookParser
from linebot.v3.messaging import MessagingApi, Configuration
from modules.config import LINE_CHANNEL_TOKEN, LINE_CHANNEL_SECRET, DATABASE_URL, DEBUG
from modules.models.base import init_db_app, db
import os

# Import the init function
from modules.services.ai_service import init_vertexai

def create_app():
    # 設置正確的模板文件夾路徑（相對於項目根目錄）
    import os
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    app = Flask(__name__, template_folder=template_dir)
    
    # 配置
    app.config['LINE_CHANNEL_TOKEN'] = os.environ.get('LINE_CHANNEL_TOKEN', '')
    app.config['LINE_CHANNEL_SECRET'] = os.environ.get('LINE_CHANNEL_SECRET', '')
    # 統一資料庫連線：優先讀 DATABASE_URL，動態選擇驅動（psycopg3 → psycopg2 回退）
    def _resolve_sqlalchemy_db_url(raw_url: str) -> str:
        url = raw_url or ''
        # 將舊的 postgres:// 改為 postgresql://（不強制指定驅動）
        if url.startswith('postgres://'):
            url = 'postgresql://' + url[len('postgres://'):]
        # 若已指定驅動則直接返回
        if '+psycopg' in url or '+psycopg2' in url:
            return url
        # 動態偵測可用驅動
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

    _db_url_env = os.environ.get('DATABASE_URL')
    if _db_url_env:
        _db_url = _resolve_sqlalchemy_db_url(_db_url_env)
    else:
        _db_url = _resolve_sqlalchemy_db_url('postgresql://postgres:postgres@localhost:5432/dispatch_db')
    app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        # 統一顯示與排序邏輯，使用 UTC 作為會話時區，
        # 與 Render 端一致，避免 8 小時差異
        'pool_size': 3,
        'max_overflow': 0,
        'pool_timeout': 30,
        'connect_args': {
            'options': "-c timezone=UTC"
        }
    }
    
    # 初始化數據庫
    init_db_app(app)
    # 確保新表存在（無 migration，使用 create_all）
    try:
        from modules.models import clinic_location  # noqa: F401 引入模型
        from modules.models import chat_settings   # noqa: F401 引入模型
        from modules.models import group_location_meta  # noqa: F401 引入模型
        from modules.models.base import db
        with app.app_context():
            db.create_all()
    except Exception as e:
        app.logger.error(f"創建資料表失敗（可忽略不阻擋啟動）：{e}")
    
    # Initialize Vertex AI
    try:
        init_vertexai()
    except Exception as ai_init_e:
        app.logger.error(f"Vertex AI initialization failed during app startup: {ai_init_e}", exc_info=True)
    
    # 導入並註冊藍圖
    from modules.routes.webhook import webhook_bp
    app.register_blueprint(webhook_bp)
    
    # 註冊管理後台藍圖
    from modules.routes.admin_routes import admin_bp
    app.register_blueprint(admin_bp)
    
    # 設定日誌
    import logging
    from modules.utils.security import MaskSecretsFilter
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # 掛載全域遮罩過濾器到 root logger handlers
    _mask_filter = MaskSecretsFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers or []:
        handler.addFilter(_mask_filter)
    
    return app

# 導出 db，供外部 from modules import db 使用
__all__ = ['create_app', 'db']
