# app.py
import os
import logging
from dotenv import load_dotenv
from modules import create_app
from flask import request, abort

# 載入環境變數
load_dotenv()

# 創建應用實例
app = create_app()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 顯示配置信息
# 使用 with app.app_context() 替代 before_first_request
def show_config():
    logger.info(f"Channel token: {app.config.get('LINE_CHANNEL_TOKEN')}")
    logger.info(f"Database URL: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

# 在應用啟動前執行配置顯示
with app.app_context():
    show_config()

# 主路由（健康檢查）
@app.route("/")
def hello():
    return "派班系統已啟動！"

# 啟動應用
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
