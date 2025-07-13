@echo off
chcp 65001 >nul

echo 🔧 快速修復資料庫序列
echo 適用於：TRUNCATE + 匯入資料後
echo ================================

REM 檢查Python腳本是否存在
if not exist "fix_sequence_after_import.py" (
    echo ❌ 找不到 fix_sequence_after_import.py
    pause
    exit /b 1
)

REM 執行快速修復
python fix_sequence_after_import.py --quick

echo.
echo 🎉 修復完成！
echo 💡 提示：你也可以訪問 http://localhost:3000/admin/database-tools 使用網頁介面
pause 