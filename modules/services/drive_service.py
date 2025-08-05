"""
Google Drive 服務模組 - 處理與Google Drive相關的操作
"""
import os
import json
import tempfile
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def get_drive_service():
    """獲取Google Drive服務並認證"""
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    try:
        # 首先尝试使用Secret File
        secret_file_path = '/etc/secrets/credentials.json'
        if os.path.exists(secret_file_path):
            logger.info(f"使用Secret File: {secret_file_path}")
            credentials = service_account.Credentials.from_service_account_file(
                secret_file_path, scopes=SCOPES)
            service = build('drive', 'v3', credentials=credentials)
            return service
        
        # 如果Secret File不存在，尝试从环境变量获取
        logger.info("Secret File不存在，尝试从环境变量获取凭证")
        creds_json = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
        
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
            service_account_file = 'plucky-mile-456412-p0-ad63114b0da5.json'  # 更新為正確路徑
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