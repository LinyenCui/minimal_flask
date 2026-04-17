#!/bin/bash

# 快速修復資料庫序列腳本
# 用於資料搬移後的序列修復

echo "🔧 快速修復資料庫序列"
echo "適用於：TRUNCATE + 匯入資料後"
echo "================================"

# 檢查Python腳本是否存在
if [ ! -f "fix_sequence_after_import.py" ]; then
    echo "❌ 找不到 fix_sequence_after_import.py"
    exit 1
fi

# 執行快速修復
python fix_sequence_after_import.py --quick

echo ""
echo "🎉 修復完成！"
