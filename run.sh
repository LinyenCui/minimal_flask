#\!/bin/bash

# 派車管理系統啟動腳本

echo "🚀 啟動派車管理系統..."

# 確保在正確目錄
cd "$(dirname "$0")"
echo "📁 當前目錄: $(pwd)"

# 檢查虛擬環境
if [ \! -f "venv/bin/python3" ]; then
    echo "❌ 虛擬環境不存在！"
    echo "請先執行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 啟動應用
echo "🐍 使用虛擬環境 Python..."
venv/bin/python3 app.py
EOF < /dev/null