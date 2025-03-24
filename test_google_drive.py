#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
測試 Google Drive 上傳和分享鏈接功能
"""

import os
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle

# 定義 Google Drive API 範圍
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def upload_to_google_drive(file_path, folder_id=None):
    """
    上傳文件到 Google Drive 並創建分享鏈接
    
    Args:
        file_path: 要上傳的文件路徑
        folder_id: 可選的 Google Drive 文件夾 ID
        
    Returns:
        str: 上傳結果消息，包含分享鏈接
    """
    try:
        creds = None
        # token.pickle 存儲用戶的訪問和刷新令牌
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
                
        # 如果沒有有效憑證，或者憑證已過期
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # 如果沒有 token.pickle 文件，則從 credentials.json 創建新的憑證
                if not os.path.exists('credentials.json'):
                    return "上傳失敗：找不到 credentials.json 文件"
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                
            # 保存憑證以供下次使用
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        # 創建 Drive API 客戶端
        service = build('drive', 'v3', credentials=creds)
        
        # 準備上傳文件
        file_name = os.path.basename(file_path)
        file_metadata = {'name': file_name}
        
        # 如果指定了文件夾 ID，則將文件上傳到該文件夾
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # 上傳文件
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = file.get('id')
        print(f"文件已上傳，ID: {file_id}")
        
        # 創建分享鏈接 - 設置文件權限為任何人都可以查看
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        
        service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        print("已設置文件權限為公開可讀")
        
        # 獲取文件的分享鏈接
        file = service.files().get(
            fileId=file_id,
            fields='webViewLink'
        ).execute()
        
        share_link = file.get('webViewLink')
        print(f"分享鏈接: {share_link}")
        
        return f"文件已上傳到 Google Drive，分享鏈接: {share_link}"
    
    except Exception as e:
        print(f"錯誤: {str(e)}")
        return f"上傳到 Google Drive 失敗: {str(e)}"

def main():
    """
    主函數，用於測試 Google Drive 上傳和分享鏈接功能
    """
    # 檢查命令行參數
    if len(sys.argv) < 2:
        print("用法: python test_google_drive.py <文件路徑> [文件夾ID]")
        return
    
    file_path = sys.argv[1]
    folder_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 檢查文件是否存在
    if not os.path.exists(file_path):
        print(f"錯誤: 文件 '{file_path}' 不存在")
        return
    
    # 上傳文件並獲取分享鏈接
    result = upload_to_google_drive(file_path, folder_id)
    print(result)

if __name__ == "__main__":
    main() 