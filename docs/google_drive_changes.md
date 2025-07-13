# Google Drive 上傳和分享鏈接功能修改

## 日期：2025-03-14

### 問題描述

原有的 Google Drive 上傳功能已經實現，但缺少創建分享鏈接供用戶下載的部分。上傳成功後，只返回文件 ID，用戶無法直接訪問和下載文件。

### 解決方案

1. **修改 `upload_to_google_drive` 函數**
   - 在上傳文件後，添加設置文件權限的代碼
   - 將文件權限設置為 "anyone" 可讀取
   - 獲取文件的 webViewLink 作為分享鏈接
   - 返回分享鏈接而不是文件 ID

2. **創建測試腳本**
   - 創建 `test_google_drive.py` 腳本，用於測試上傳和分享功能
   - 腳本接受文件路徑和可選的文件夾 ID 作為參數
   - 提供詳細的日誌輸出，方便調試

### 代碼修改

1. **在 `app.py` 中修改 `upload_to_google_drive` 函數**
   ```python
   # 上傳文件後獲取文件 ID
   file_id = file.get('id')
   
   # 創建分享鏈接 - 設置文件權限為任何人都可以查看
   permission = {
       'type': 'anyone',
       'role': 'reader'
   }
   
   service.permissions().create(
       fileId=file_id,
       body=permission
   ).execute()
   
   # 獲取文件的分享鏈接
   file = service.files().get(
       fileId=file_id,
       fields='webViewLink'
   ).execute()
   
   share_link = file.get('webViewLink')
   
   return f"文件已上傳到 Google Drive，分享鏈接: {share_link}"
   ```

2. **創建 `test_google_drive.py` 測試腳本**
   - 實現了與 `app.py` 中相同的上傳和分享功能
   - 添加了詳細的日誌輸出
   - 提供了命令行參數處理

### 測試結果

使用測試腳本上傳 `./reports/weekly_report_診所_20250312.xlsx` 文件：

```
文件已上傳，ID: 143BU6GC82fVlAdyaO9s7KlpINGpnqNEd
已設置文件權限為公開可讀
分享鏈接: https://docs.google.com/spreadsheets/d/143BU6GC82fVlAdyaO9s7KlpINGpnqNEd/edit?usp=drivesdk&ouid=117503118146023911875&rtpof=true&sd=true
文件已上傳到 Google Drive，分享鏈接: https://docs.google.com/spreadsheets/d/143BU6GC82fVlAdyaO9s7KlpINGpnqNEd/edit?usp=drivesdk&ouid=117503118146023911875&rtpof=true&sd=true
```

測試成功，文件已上傳到 Google Drive，並生成了可訪問的分享鏈接。

### 注意事項

1. **權限設置**
   - 文件權限設置為 "anyone" 可讀取，意味著任何擁有鏈接的人都可以查看文件
   - 如果需要更嚴格的權限控制，可以修改 permission 參數

2. **憑證管理**
   - 確保 `credentials.json` 和 `token.pickle` 文件存在且有效
   - 如果 token 過期，系統會自動刷新或重新獲取

3. **錯誤處理**
   - 添加了詳細的錯誤處理和日誌輸出
   - 如果上傳或設置權限失敗，會返回具體的錯誤信息 