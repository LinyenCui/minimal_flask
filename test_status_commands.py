#!/usr/bin/env python3
"""
測試狀態查詢命令
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from modules.services.smart_assistant import SmartAssistant

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_status_commands():
    """測試各種狀態查詢命令"""
    assistant = SmartAssistant()
    
    test_commands = [
        "/取消班次",
        "/註銷班次", 
        "/衝突班次",
        "/待派班次",
        "/準備班次",
        "/請假班次",
        "衝突班次",
        "待派班次",
        "準備班次",
        "註銷班次",
        "取消班次",
        "請假班次"
    ]
    
    print("=== 測試狀態查詢命令 ===\n")
    
    for cmd in test_commands:
        print(f"🔍 測試命令: '{cmd}'")
        try:
            result = assistant._analyze_with_ai(cmd, "test_user")
            print(f"   AI 回應: {result}")
            print(f"   信心度: {result.get('confidence', 'N/A')}")
            print(f"   生成命令: {result.get('command', 'N/A')}")
            print()
        except Exception as e:
            print(f"   ❌ 錯誤: {e}")
            print()

if __name__ == "__main__":
    test_status_commands()