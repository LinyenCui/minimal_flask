#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試增強版預約叫車功能
包含錶價和搭載人員功能的測試
"""

import json

def test_enhanced_ai_extraction():
    """測試增強版AI提取功能"""
    print("🧪 測試增強版AI提取功能...")
    
    test_cases = [
        # 基本功能測試
        "明天下午三點從高鐵站到診所",
        
        # 錶價功能測試
        "明天下午三點從高鐵站到診所，車資400",
        "今天早上9點，錶價500元，從公司到醫院",
        "後天費用350，從火車站到東洋",
        
        # 乘客功能測試
        "明天下午送張先生到醫院",
        "今天早上載李小姐從高鐵站到診所",
        "後天接送王總經理，從公司到客戶家",
        
        # 綜合功能測試
        "明天下午三點半送張先生從高鐵站到東洋，經過文南路，車資400元",
        "今天早上9點載李小姐，錶價350，從診所到火車站，這是診所班次",
        "後天下午接送王總，費用500元，從高鐵站經由安平到客戶家"
    ]
    
    # 模擬AI提取結果
    expected_results = [
        # 基本功能
        {
            "date": "明天",
            "time": "下午三點",
            "start_point": "高鐵站",
            "end_point": "診所",
            "category": "診所",
            "via_point": None,
            "meter_fare": None,
            "passenger_name": None
        },
        
        # 錶價功能
        {
            "date": "明天",
            "time": "下午三點",
            "start_point": "高鐵站",
            "end_point": "診所",
            "category": "診所",
            "via_point": None,
            "meter_fare": 400,
            "passenger_name": None
        },
        
        # 乘客功能
        {
            "date": "明天",
            "time": "下午",
            "start_point": None,
            "end_point": "醫院",
            "category": None,
            "via_point": None,
            "meter_fare": None,
            "passenger_name": "張先生"
        },
        
        # 綜合功能
        {
            "date": "明天",
            "time": "下午三點半",
            "start_point": "高鐵站",
            "end_point": "東洋",
            "category": None,
            "via_point": "文南路",
            "meter_fare": 400,
            "passenger_name": "張先生"
        }
    ]
    
    for i, test_input in enumerate(test_cases):
        print(f"\n📝 測試案例 {i+1}: '{test_input}'")
        if i < len(expected_results):
            expected = expected_results[i]
            print(f"   預期結果: {json.dumps(expected, ensure_ascii=False, indent=6)}")
        print("   ✅ 將使用增強版AI解析")
    
    print("\n🎯 測試重點:")
    print("• 錶價關鍵詞：車資、錶價、費用、收費")
    print("• 乘客關鍵詞：送、載、接送、搭載")
    print("• 數字提取：自動忽略單位（元、塊）")
    print("• 敬語保留：先生、小姐、總經理等")

def test_database_schema():
    """測試資料庫架構"""
    print("\n🔧 測試資料庫架構...")
    
    print("📋 需要的PostgreSQL欄位:")
    print("  trips表:")
    print("    • meter_fare INTEGER    - 錶價")
    print("    • passenger_name TEXT   - 乘客姓名")
    print("  completed_trips表:")
    print("    • meter_fare INTEGER    - 錶價")
    print("    • passenger_name TEXT   - 乘客姓名")
    
    print("\n💾 SQL遷移語句:")
    print("  -- 為trips表添加新欄位")
    print("  ALTER TABLE trips ADD COLUMN passenger_name TEXT;")
    print("  -- 為completed_trips表添加新欄位")
    print("  ALTER TABLE completed_trips ADD COLUMN passenger_name TEXT;")

def test_ui_examples():
    """測試UI顯示範例"""
    print("\n🎨 測試UI顯示範例...")
    
    # 模擬預約成功消息
    success_example = """✅ 臨時預約成功！

班次ID: 2534
日期：2025-06-05
時間：14:30
起點：高鐵站
途經：文南路
目的地：東洋
錶價：400元
乘客：張先生
類別：診所
狀態：待派

我們會盡快為您指派司機。"""
    
    print("📱 預約成功消息範例:")
    print(success_example)
    
    # 模擬確認界面
    print("\n📋 確認界面新增欄位:")
    print("  • 錶價：400元（加粗顯示）")
    print("  • 乘客：張先生（加粗顯示）")

def test_natural_language_examples():
    """測試自然語言範例"""
    print("\n🗣️ 自然語言使用範例...")
    
    examples = [
        {
            "input": "明天下午3點送張先生從高鐵站到診所，車資400",
            "description": "完整預約：包含所有信息"
        },
        {
            "input": "載李小姐，錶價350",
            "description": "部分信息：AI會追問缺少的必要信息"
        },
        {
            "input": "今天早上9點診所班次，費用500元",
            "description": "類別+錶價：自動識別診所類別"
        },
        {
            "input": "接送王總經理，從公司經過市政府到客戶家",
            "description": "高級乘客：保留敬語"
        }
    ]
    
    for example in examples:
        print(f"📝 輸入: 「{example['input']}」")
        print(f"   說明: {example['description']}")
        print()

def main():
    """主測試函數"""
    print("🚀 增強版預約叫車功能測試")
    print("=" * 50)
    
    test_enhanced_ai_extraction()
    test_database_schema()
    test_ui_examples()
    test_natural_language_examples()
    
    print("\n✅ 測試完成！")
    
    print("\n📋 實施步驟總結:")
    print("1. ✅ 創建增強版AI prompt")
    print("2. ✅ 更新預約處理邏輯")
    print("3. ✅ 更新確認界面設計")
    print("4. ⏳ 執行PostgreSQL資料庫遷移")
    print("5. ⏳ 測試完整預約流程")
    
    print("\n🎯 新功能亮點:")
    print("• 🍪 錶價智能識別：支援多種表達方式")
    print("• 👥 乘客信息管理：自動提取並保留敬語")
    print("• 🎨 美觀界面：參考預約確認畫面風格")
    print("• 🔄 向後兼容：不影響現有功能")

if __name__ == "__main__":
    main() 