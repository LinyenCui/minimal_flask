#!/usr/bin/env python3
"""
調試對話狀態工具
幫助檢查為什麼取消命令沒有被識別
"""

def debug_cancel_logic():
    """調試取消邏輯"""
    print("🔍 調試取消命令邏輯")
    print("=" * 50)
    
    # 模擬passenger_leave對話的取消命令列表
    cancel_commands = ['取消請假', '取消', '放棄請假', '退出', '不請假', '放棄', '放棄操作']
    
    test_message = "放棄操作"
    
    print(f"測試訊息: '{test_message}'")
    print(f"支援的取消命令: {cancel_commands}")
    
    # 模擬can_cancel_with邏輯
    message_lower = test_message.lower().strip()
    print(f"轉換後的訊息: '{message_lower}'")
    
    for cmd in cancel_commands:
        if cmd.lower() in message_lower:
            print(f"✅ 匹配到取消命令: '{cmd}'")
            return True
    
    print("❌ 沒有匹配到任何取消命令")
    return False

def check_command_matching():
    """檢查命令匹配邏輯"""
    print("\n🔍 檢查命令匹配邏輯")
    print("=" * 50)
    
    cancel_commands = ['取消請假', '取消', '放棄請假', '退出', '不請假', '放棄', '放棄操作']
    
    test_cases = [
        "放棄",
        "放棄操作", 
        "取消",
        "退出",
        "不請假",
        "普通訊息",
        "放棄操作這個請假"  # 測試包含的情況
    ]
    
    for test_msg in test_cases:
        message_lower = test_msg.lower().strip()
        matches = []
        
        for cmd in cancel_commands:
            if cmd.lower() in message_lower:
                matches.append(cmd)
        
        if matches:
            print(f"✅ '{test_msg}' -> 匹配: {matches}")
        else:
            print(f"❌ '{test_msg}' -> 無匹配")

if __name__ == "__main__":
    debug_cancel_logic()
    check_command_matching()
    
    print("\n🎯 結論:")
    print("如果'放棄操作'沒有被識別為取消命令，問題可能在於：")
    print("1. 對話狀態沒有正確啟動")
    print("2. user_id不匹配")
    print("3. 對話已經過期")
    print("4. 取消檢查邏輯沒有被執行")