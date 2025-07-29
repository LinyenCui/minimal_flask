#!/usr/bin/env python3
"""
簡單測試 - 檢查固定班次請假是否正常工作
"""

# 模擬檢查請假邏輯
def test_leave_detection():
    """測試請假格式檢測"""
    message = "測試 -0"
    
    print(f"🧪 測試訊息: '{message}'")
    
    # 簡化版的請假檢測邏輯（從text_message_handler.py抄來的）
    import re
    
    # 請假檢測模式
    leave_patterns = [
        r'^(.+)\s+(-?\d+)$',  # 原因 加成
        r'^(-?\d+)\s+(.+)$',  # 加成 原因  
    ]
    
    for pattern in leave_patterns:
        match = re.match(pattern, message.strip())
        if match:
            group1 = match.group(1).strip()
            group2 = match.group(2).strip()
            
            # 檢查哪個是數字（加成）
            try:
                amount = int(group1)
                reason = group2
                print(f"✅ 模式匹配: 加成={amount}, 原因='{reason}'")
                break
            except ValueError:
                try:
                    amount = int(group2) 
                    reason = group1
                    print(f"✅ 模式匹配: 原因='{reason}', 加成={amount}")
                    break
                except ValueError:
                    continue
    else:
        print("❌ 不匹配任何請假格式")
        return
    
    # 模擬檢查上下文
    print(f"🔍 檢查上下文...")
    
    # 如果沒有上下文，會顯示什麼錯誤
    print(f"❌ 找不到最近的班次ID - 這就是用戶看到的錯誤")
    
    print(f"\n💡 解決方案:")
    print(f"   1. 用戶需要先點擊「固定班次#17請假」按鈕")
    print(f"   2. 然後再輸入「測試 -0」")
    print(f"   3. 或者直接使用完整格式：固定班次請假 17 -0 測試")

if __name__ == "__main__":
    test_leave_detection()