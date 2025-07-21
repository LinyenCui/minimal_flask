#!/usr/bin/env python3
# 全面架構檢視

print("🔍 架構問題全面檢視")
print("=" * 50)

print("❌ 當前問題：")
print("1. 智能助手解析：'7/21所有班次' → '查詢班次 7/21'")  
print("2. 命令路由：'查詢班次' → advanced_query_processor")
print("3. 結果：純文字消息 + Quick Reply錯誤")
print("4. 用戶期望：Flex Message")
print()

print("🎯 命令路由邏輯檢視：")

# 分析text_message_handler.py中的命令路由
with open('modules/handlers/text_message_handler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找查詢班次的處理邏輯
lines = content.split('\n')
query_trip_handlers = []
ai_service_handlers = []

for i, line in enumerate(lines):
    if '查詢班次' in line and ('startswith' in line or 'elif' in line):
        context = lines[max(0, i-2):min(len(lines), i+5)]
        query_trip_handlers.append((i+1, context))
    
    if 'handle_smart_fare_query' in line:
        context = lines[max(0, i-2):min(len(lines), i+3)]  
        ai_service_handlers.append((i+1, context))

print(f"📍 找到 {len(query_trip_handlers)} 個查詢班次處理點")
print(f"📍 找到 {len(ai_service_handlers)} 個AI服務調用點")
print()

print("🔧 問題根源：")
print("智能助手生成的所有'查詢班次'命令都被路由到advanced_query_processor")
print("而不是AI車資服務，所以沒有Flex Message")
print()

print("✅ 解決方案：")
print("1. 統一所有智能助手生成的命令都走AI車資服務")
print("2. 或者修復advanced_query_processor的Quick Reply格式")
print("3. 或者重新設計命令路由架構")
print()

print("💡 建議：")
print("暫停小修補，進行一次徹底的架構重構")
print("確定：智能助手 → AI服務 → Flex Message 的統一路徑")
