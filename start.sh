#!/bin/bash

# 輸出顏色設定
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==== LINE Bot 派班系統啟動腳本 ====${NC}"

# 檢查虛擬環境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}創建虛擬環境...${NC}"
    python3 -m venv venv
fi

# 啟動虛擬環境
echo -e "${YELLOW}啟動虛擬環境...${NC}"
source venv/bin/activate

# 安裝依賴
echo -e "${YELLOW}安裝依賴...${NC}"
pip install -r requirements.txt

# 檢查 .env 文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}.env 文件不存在，從範例創建...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}請編輯 .env 文件設置您的配置${NC}"
        exit 1
    else
        echo -e "${YELLOW}錯誤：.env.example 不存在${NC}"
        exit 1
    fi
fi

# 初始化資料庫
echo -e "${YELLOW}初始化資料庫...${NC}"
python -c "from modules.init_db import create_database, init_db; create_database(); init_db()"

# 啟動應用
echo -e "${GREEN}啟動應用...${NC}"
python app.py 