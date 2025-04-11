#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
測試服務帳戶認證和Google Drive上傳功能
"""

import os
import sys
from modules.services.drive_service import get_drive_service, upload_file_to_drive

def test_drive_connection():
    """測試Google Drive連接"""
    print("測試Google Drive服務連接...")
    
    service = get_drive_service()
    if service:
        print("✅ 服務帳戶認證成功！")
        
        # 列出最近的10個文件
        try:
            results = service.files().list(
                pageSize=10, 
                fields="nextPageToken, files(id, name, webViewLink)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                print("沒有找到任何文件。")
            else:
                print("\n最近的文件:")
                for file in files:
                    print(f"文件: {file.get('name')}, ID: {file.get('id')}")
        except Exception as e:
            print(f"❌ 列出文件時出錯: {str(e)}")
    else:
        print("❌ 服務帳戶認證失敗！請檢查憑證文件。")

def test_file_upload(file_path=None):
    """測試文件上傳功能"""
    if not file_path:
        # 創建一個測試文件
        test_file = "test_upload.txt"
        with open(test_file, "w") as f:
            f.write("這是一個測試文件，用於測試Google Drive上傳功能。")
        file_path = test_file
        print(f"已創建測試文件: {test_file}")
    
    print(f"\n測試上傳文件: {file_path}")
    success, result = upload_file_to_drive(file_path)
    
    if success:
        print(f"✅ 文件上傳成功！")
        print(f"分享鏈接: {result}")
    else:
        print(f"❌ 文件上傳失敗: {result}")

def main():
    """主函數"""
    print("=" * 50)
    print("Google Drive 服務帳戶測試程序")
    print("=" * 50)
    
    # 測試服務連接
    test_drive_connection()
    
    # 測試文件上傳
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        test_file_upload(file_path)
    else:
        test_file_upload()

if __name__ == "__main__":
    main() 