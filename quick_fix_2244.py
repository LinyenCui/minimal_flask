#!/usr/bin/env python3
# 快速修復日誌2244問題

print("🔧 修復日誌2244問題：")
print("1. 確認對話後保持使用AI車資服務（Flex Message）")
print("2. 修復Quick Reply格式錯誤") 
print("3. 避免回到純文字消息")

# 檢查關鍵修復點
import os
import re

def check_fixes():
    fixes_applied = []
    
    # 檢查text_message_handler.py
    with open('modules/handlers/text_message_handler.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'skip_parsing=True' in content:
        fixes_applied.append("✅ 確認對話支持skip_parsing")
    
    if 'handle_smart_fare_query(original_query, user_id, use_flex=True' in content:
        fixes_applied.append("✅ 確認後仍使用AI車資服務")
        
    if 'message_text = result.get("message") or result.get("text")' in content:
        fixes_applied.append("✅ handle_ai_fare_result錯誤修復")
    
    # 檢查ai_fare_service.py
    with open('modules/services/ai_fare_service.py', 'r', encoding='utf-8') as f:
        service_content = f.read()
        
    if 'skip_parsing=False' in service_content:
        fixes_applied.append("✅ AI車資服務支持skip_parsing參數")
    
    print("\n🎯 已應用的修復：")
    for fix in fixes_applied:
        print(f"  {fix}")
    
    # 主要問題：Quick Reply格式
    print("\n⚠️  還需修復：Quick Reply格式錯誤")
    print("   - advanced_query_processor.py中的to_dict()問題")
    print("   - 需要使用正確的字典格式")
    
    print("\n💡 建議：")
    print("1. 測試「七月十九日東洋班次」→確認→應該顯示Flex Message")
    print("2. 修復Quick Reply items缺少action.text的問題")
    print("3. 確保整個流程使用Flex Message而不是純文字")

check_fixes()
