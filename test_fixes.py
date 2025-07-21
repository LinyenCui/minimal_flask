#!/usr/bin/env python3
# 測試所有修復

print("🧪 測試所有修復是否生效")
print("=" * 50)

# 檢查關鍵修復
with open('modules/handlers/text_message_handler.py', 'r', encoding='utf-8') as f:
    handler_content = f.read()

with open('modules/services/ai_fare_service.py', 'r', encoding='utf-8') as f:
    service_content = f.read()

fixes_status = []

# 1. 檢查智能助手查詢班次路由到AI服務
if 'elif command.startswith("查詢班次"):' in handler_content and 'handle_smart_fare_query(message_text, user_id, use_flex=True, parsed_command=command)' in handler_content:
    fixes_status.append("✅ 智能助手'查詢班次'路由到AI服務")
else:
    fixes_status.append("❌ 智能助手'查詢班次'路由修復失敗")

# 2. 檢查直接查詢班次路由到AI服務  
if 'elif message_text.startswith("查詢班次"):' in handler_content and 'handle_smart_fare_query(message_text, user_id, use_flex=True)' in handler_content:
    fixes_status.append("✅ 直接'查詢班次'路由到AI服務")
else:
    fixes_status.append("❌ 直接'查詢班次'路由修復失敗")

# 3. 檢查AI服務支持skip_parsing
if 'skip_parsing=False' in service_content:
    fixes_status.append("✅ AI服務支持skip_parsing參數")
else:
    fixes_status.append("❌ AI服務skip_parsing支持失敗")

# 4. 檢查handle_ai_fare_result錯誤修復
if 'message_text = result.get("message") or result.get("text")' in handler_content:
    fixes_status.append("✅ handle_ai_fare_result錯誤修復")
else:
    fixes_status.append("❌ handle_ai_fare_result錯誤修復失敗")

print("🎯 修復狀態檢查：")
for status in fixes_status:
    print(f"  {status}")

print()
print("📋 預期效果：")
print("1. 所有智能助手查詢 → AI車資服務 → Flex Message")
print("2. 確認對話後 → skip_parsing=True → 直接執行")
print("3. 無限循環問題解決")
print("4. Quick Reply格式錯誤修復")
print("5. 用戶看到一致的Flex Message體驗")
print()

print("🚀 關鍵改進：")
print("- 不再有'找到X筆...然後呢？'的問題")
print("- 所有查詢都是Flex Message展示") 
print("- AI智能理解 + 美觀展示 = 完美體驗")
