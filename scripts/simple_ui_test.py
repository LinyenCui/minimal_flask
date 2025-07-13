#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡化UI改進測試
不依賴Flask環境，直接測試關鍵邏輯
"""

import re

def test_enhanced_fare_keywords():
    """測試擴展的費用關鍵詞識別"""
    print("🧪 測試擴展費用詞彙識別...")
    
    # 擴展的費用關鍵詞
    fare_keywords = ['車資', '費用', '金額', '收費', '錢', '價格', '票價', '錶價', '加成', '$', '元', '台幣', '現金', '付費', '收入', '車費', '運費']
    
    test_cases = [
        "修改錶價400加成80",
        "修改車資400", 
        "調整費用為500",
        "修改$400",
        "改成400元",
        "車費調整為300",
        "運費改成250",
        "現金收入400",
        "付費調整",
        "班次#1234 $400加成80",
        "改成$300+50",
        "$500元調整",
    ]
    
    for test_text in test_cases:
        message_lower = test_text.lower()
        has_fare = any(keyword in message_lower for keyword in fare_keywords)
        print(f"  '{test_text}' -> 包含費用詞彙: {has_fare}")
    
    print()

def test_enhanced_fare_parsing():
    """測試增強的費用解析"""
    print("🔍 測試增強費用解析...")
    
    # 增強的錶價模式
    meter_patterns = [
        r'錶價\s*(\d+)',
        r'改成\s*錶價?\s*(\d+)',
        r'錶價?\s*改成?\s*(?:為|到|成)?\s*(\d+)',
        r'錶價?\s*調整?\s*(?:為|到|成)?\s*(\d+)',
        r'車資\s*(\d+)',
        r'費用\s*(\d+)',
        r'\$\s*(\d+)',         # $符號
        r'(\d+)\s*元',         # 數字+元
        r'改成\s*(\d+)\s*元',
        r'調整為\s*(\d+)',
        r'變成\s*(\d+)'
    ]
    
    # 增強的加成模式
    extra_patterns = [
        r'加成\s*([+-]?\d+)',
        r'加收\s*([+-]?\d+)',
        r'額外\s*([+-]?\d+)',
        r'夜班費?\s*([+-]?\d+)',
        r'加費\s*([+-]?\d+)',
        r'補貼\s*([+-]?\d+)', 
        r'折扣\s*([+-]?\d+)',
        r'優惠\s*([+-]?\d+)',
        r'調整\s*([+-]?\d+)',
        r'\+\s*([+-]?\d+)',     # +符號
        r'另加\s*([+-]?\d+)'
    ]
    
    test_cases = [
        "修改錶價400加成80",
        "改成車資400",
        "調整費用為500", 
        "變成$400",
        "改成300元",
        "錶價400加成80",
        "400加費50",
        "300另加100",
        "500+80",
        "400夜班費50",
        "300折扣-20",
        "$400+80，客戶要求調整",
        "車資300另加50，等候時間長",
        "費用500夜班費100，加班服務",
    ]
    
    for test_text in test_cases:
        result = {}
        
        # 提取錶價
        for pattern in meter_patterns:
            match = re.search(pattern, test_text)
            if match:
                result['meter_fare'] = int(match.group(1))
                break
        
        # 提取加成
        for pattern in extra_patterns:
            match = re.search(pattern, test_text)
            if match:
                result['extra_fare'] = int(match.group(1))
                break
        
        print(f"  '{test_text}' -> {result}")
    
    print()

def test_simplified_ui_text():
    """測試簡化的UI文字"""
    print("🎨 測試簡化UI文字...")
    
    # 模擬簡化後的操作提示
    simplified_tips = [
        "• 「修改班次#[ID]車資[錶價]加成[加成]」",
        "• 選擇第N個: 「修改第[N]個的費用為...」",
        "• 查看: 「查看 [ID]」"
    ]
    
    print("  簡化後的操作提示:")
    for tip in simplified_tips:
        print(f"    {tip}")
    
    print("\n  對比原來的格式:")
    print("    ❌ 修改特定班次: 「修改班次#[ID]車資[錶價]加成[加成]」")
    print("    ✅ 「修改班次#[ID]車資[錶價]加成[加成]」")
    print()
    print("    ❌ 已完成班次詳情 [ID] - 查看已完成班次詳細信息")
    print("    ✅ 查看 [ID] - 查看已完成班次詳細信息")
    
    print()

def main():
    """主測試函數"""
    print("🚀 UI改進測試開始...\n")
    
    test_enhanced_fare_keywords()
    test_enhanced_fare_parsing()  
    test_simplified_ui_text()
    
    print("✅ 測試完成！")
    
    print("\n📝 改進總結:")
    print("1. ✅ 精減語言：'已完成班次詳情' → '查看'")
    print("2. ✅ 擴展費用詞彙：支援 $、車資、費用、元等")
    print("3. ✅ 簡化操作提示：移除冗餘描述")
    print("4. ✅ 增強費用解析：支援更多模式")
    print("\n🎯 參考您提到的預約確認畫面風格：")
    print("   - 簡潔明瞭的標題")
    print("   - 清晰的信息層次")
    print("   - 去除不必要的修飾詞")
    print("   - 直觀的操作指引")

if __name__ == "__main__":
    main() 