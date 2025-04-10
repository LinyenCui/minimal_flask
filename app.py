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
import json
import tempfile
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
# Google Drive API
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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

# Google Drive 服務帳戶認證函數
def get_drive_service():
    """獲取Google Drive服務並認證"""
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    # 從環境變量獲取憑證JSON字符串
    creds_json = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    
    try:
        if creds_json:
            # 使用環境變量中的憑證內容（適用於Render部署）
            # 創建臨時文件
            fd, path = tempfile.mkstemp()
            try:
                with os.fdopen(fd, 'w') as tmp:
                    tmp.write(creds_json)
                credentials = service_account.Credentials.from_service_account_file(
                    path, scopes=SCOPES)
                service = build('drive', 'v3', credentials=credentials)
                return service
            finally:
                # 確保臨時文件被刪除
                os.remove(path)
        else:
            # 本地開發使用本地憑證文件
            service_account_file = 'plucky-mile-456412-p0-ad63114b0da5.json'  # 本地金鑰文件名
            if not os.path.exists(service_account_file):
                logger.error(f"找不到服務帳戶金鑰文件: {service_account_file}")
                return None
                
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file, scopes=SCOPES)
            service = build('drive', 'v3', credentials=credentials)
            return service
    except Exception as e:
        logger.error(f"Google Drive認證失敗: {str(e)}")
        return None

# 上傳文件到Google Drive並返回分享鏈接
def upload_file_to_drive(file_path, file_name=None, folder_id=None):
    """
    上傳文件到Google Drive
    
    Args:
        file_path: 本地文件路徑
        file_name: 上傳後的文件名（可選，默認使用原文件名）
        folder_id: 目標文件夾ID（可選）
        
    Returns:
        tuple: (成功標誌, 消息或鏈接)
    """
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return False, "無法連接到Google Drive服務"
            
        # 如果沒有提供文件名，則使用原文件名
        if not file_name:
            file_name = os.path.basename(file_path)
            
        file_metadata = {'name': file_name}
        
        # 如果提供了文件夾ID，則上傳到該文件夾
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        # 準備上傳
        media = MediaFileUpload(file_path, resumable=True)
        
        # 執行上傳
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()
        
        file_id = file.get('id')
        view_link = file.get('webViewLink', '')
        
        # 設置文件為公開可查看
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        
        drive_service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        
        logger.info(f"文件已上傳到Google Drive: {file_id}, 鏈接: {view_link}")
        return True, view_link
        
    except Exception as e:
        logger.error(f"上傳文件到Google Drive失敗: {str(e)}")
        return False, f"上傳失敗: {str(e)}"

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
