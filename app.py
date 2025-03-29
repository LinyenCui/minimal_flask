# app.py
import os
from dotenv import load_dotenv

# 檢查是否在本地運行
is_local = os.environ.get('FLASK_ENV') == 'development'

# 環境變量加載邏輯
if is_local:
    print("本地開發環境：加載 .env.dev")
    load_dotenv('.env.dev', override=True)
elif not os.environ.get('RENDER'):  # 如果不是在 Render 上運行
    print("非 Render 環境：加載 .env")
    load_dotenv('.env', override=True)
else:
    print("Render 環境：使用 Render 環境變量")

# 驗證配置
print(f"使用的 Channel Secret: {os.environ.get('LINE_CHANNEL_SECRET')}")
print(f"使用的 Channel Token: {os.environ.get('LINE_CHANNEL_TOKEN')}")

# 其他的 import
import logging
from modules import create_app
from flask import request, abort
from modules.services.scheduler_service import (
    schedule_all_trip_updates,
    update_completed_trips,
    initialize_unique_codes
)
from flask_apscheduler import APScheduler
import flask
import sqlalchemy

# 版本檢查
flask_version = flask.__version__
sqlalchemy_version = sqlalchemy.__version__
print(f"Flask version: {flask_version}")
print(f"SQLAlchemy version: {sqlalchemy_version}")
if flask_version.startswith("3."):
    print("使用 Flask 3.x 兼容模式")
else:
    print("使用 Flask 2.x 或更早版本兼容模式")

# 創建應用實例
app = create_app()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 顯示配置信息
def show_config():
    logger.info(f"Channel token: {app.config.get('LINE_CHANNEL_TOKEN')}")
    logger.info(f"Database URL: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    logger.info(f"Channel Secret: {app.config.get('LINE_CHANNEL_SECRET')}")

# 在應用啟動前執行配置顯示
with app.app_context():
    show_config()

# 在創建 app 時
app.config['LINE_CHANNEL_SECRET'] = os.environ.get('LINE_CHANNEL_SECRET')

# 主路由（健康檢查）
@app.route("/")
def hello():
    return "派班系統已啟動！"

# 設置排程器
scheduler = APScheduler()
app.scheduler = scheduler  # 將排程器附加到應用程序實例

# 在應用程序啟動時初始化
with app.app_context():
    # 初始化排程器
    scheduler.init_app(app)
    
    # 添加每日更新任務
    scheduler.add_job(
        id='schedule_daily_updates',
        func=schedule_all_trip_updates,
        args=[app],
        trigger='cron',
        hour=0,
        minute=0,
        replace_existing=True
    )
    
    # 添加每小時更新已完成班次的任務
    scheduler.add_job(
        id='hourly_update_completed',
        func=update_completed_trips,
        trigger='cron',
        hour='*',
        minute=0,
        replace_existing=True
    )
    
    # 添加每小時更新唯一識別碼的任務
    scheduler.add_job(
        id='hourly_update_unique_codes',
        func=initialize_unique_codes,
        trigger='cron',
        hour='*',
        minute=30,
        replace_existing=True
    )
    
    # 啟動排程器
    scheduler.start()
    
    # 應用啟動時，處理所有已過期的班次
    update_completed_trips()
    
    # 應用啟動時，初始化所有沒有唯一識別碼的班次
    initialize_unique_codes()
    
    # 應用啟動時，安排所有未來班次的自動更新任務
    schedule_all_trip_updates(app)

# 啟動應用
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
