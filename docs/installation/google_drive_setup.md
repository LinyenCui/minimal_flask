# Google Drive 服務帳戶設置指南

## 本地開發配置

1. 將服務帳戶JSON金鑰文件 (`plucky-mile-456412-p0-ad63114b0da5.json`) 放在專案根目錄
2. 確保該文件已添加到 `.gitignore` 中，防止推送到代碼庫
3. 本地運行時，系統會自動使用此文件進行身份驗證

## Render部署配置

在Render上部署時，需要將服務帳戶憑證作為環境變量加入:

1. 登錄您的Render帳號
2. 進入您的服務設置頁面
3. 點擊 "Environment" 標籤
4. 添加新的環境變量:
   - 變量名稱: `GOOGLE_APPLICATION_CREDENTIALS_JSON`
   - 變量值: 將整個JSON金鑰文件的內容複製粘貼到這裡

## 確認Google Drive共享設置

確保您希望上傳報表的Google Drive文件夾已經共享給服務帳戶:

1. 打開您的Google Drive
2. 找到並右鍵點擊您想要共享的文件夾
3. 選擇 "共享"
4. 在輸入框中輸入服務帳戶的電子郵件地址 (格式為: `服務帳戶名稱@plucky-mile-456412-p0.iam.gserviceaccount.com`)
5. 設置權限為 "編輯者" 或 "檢視者" (建議使用 "編輯者")
6. 點擊 "發送"

## 文件夾ID配置

系統中已經設置了以下文件夾ID:

- 診所: `1Wwp1xIxnn9m9qlvX_BwpE30K0AgLVdYe`
- 東洋: `1dctU8QPRWNPn57LxpcYTeKKcsGn_dLOU`

如需更改這些ID，請修改 `modules/services/report_service.py` 文件中的 `CATEGORY_FOLDER_MAPPING` 變量。

## 故障排除

如果上傳失敗:

1. 檢查Render的環境變量是否正確設置
2. 確認服務帳戶有權限訪問Google Drive文件夾
3. 查看Render的日誌輸出，查找錯誤信息
4. 確保Google Drive API已在Google Cloud Platform項目中啟用 