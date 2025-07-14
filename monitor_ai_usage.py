#!/usr/bin/env python3
"""
AI使用量監控工具
實時監控您的Gemini API調用情況
"""
import os
import time
from datetime import datetime

def setup_environment():
    """設置環境變數"""
    credentials_path = os.path.join(os.getcwd(), 'temp_files', 'chrome-flight-458709-d1-cc3bdb1f0846.json')
    
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    os.environ['GCP_PROJECT_ID'] = 'chrome-flight-458709-d1'
    os.environ['GCP_LOCATION'] = 'us-central1'
    os.environ['GEMINI_MODEL'] = 'gemini-2.0-flash-001'

def single_api_test():
    """進行一次快速API測試"""
    print("🔍 進行一次快速API測試...")
    
    try:
        from modules.services.ai_service import extract_booking_info_with_gemini
        
        start_time = time.time()
        result = extract_booking_info_with_gemini("測試：明天上午9點從高鐵站到醫院")
        end_time = time.time()
        
        if result:
            print(f"✅ API調用成功！耗時: {end_time-start_time:.2f}秒")
            print(f"📊 解析結果: {result}")
            print(f"💰 這次調用消耗了您的API額度")
            return True
        else:
            print("❌ API調用失敗")
            return False
            
    except Exception as e:
        print(f"❌ 測試出錯: {e}")
        return False

def test_different_scenarios():
    """測試不同場景的API使用"""
    print("\n🧪 測試不同AI功能的API調用...")
    
    scenarios = [
        ("預約解析", "明天下午3點從台中到彰化"),
        ("複雜預約", "後天早上8點載張先生從高鐵站經過市區到東洋，車資400"),
        ("簡單預約", "今天 14:00 診所"),
    ]
    
    total_calls = 0
    
    for name, test_input in scenarios:
        print(f"\n📋 {name}: {test_input}")
        
        try:
            from modules.services.ai_service import extract_booking_info_with_gemini
            
            start_time = time.time()
            result = extract_booking_info_with_gemini(test_input)
            end_time = time.time()
            
            if result:
                total_calls += 1
                print(f"  ✅ 成功 (耗時: {end_time-start_time:.2f}秒)")
                print(f"  💰 API調用 #{total_calls}")
            else:
                print(f"  ❌ 失敗")
                
        except Exception as e:
            print(f"  ❌ 錯誤: {e}")
    
    print(f"\n📊 總共進行了 {total_calls} 次API調用")
    print(f"💰 這些調用都會計入您的使用量")
    
    return total_calls

def show_usage_estimate(api_calls):
    """顯示使用量估算"""
    print(f"\n💰 使用量估算")
    print("=" * 40)
    
    # Gemini API 的大致定價（可能會變動）
    estimated_cost_per_call = 0.001  # 大約每次調用$0.001
    estimated_cost = api_calls * estimated_cost_per_call
    
    print(f"📊 今次測試調用次數: {api_calls}")
    print(f"💵 估算成本: ${estimated_cost:.4f}")
    print(f"📈 剩餘額度概估: ${50 - estimated_cost:.4f}")
    
    # 預測可用調用次數
    remaining_calls = int((50 - estimated_cost) / estimated_cost_per_call)
    print(f"🔢 大約還可調用: {remaining_calls:,} 次")
    
    print(f"\n📅 使用頻率預測:")
    daily_scenarios = [
        ("輕度使用 (5次/天)", 5, remaining_calls // 5),
        ("中度使用 (20次/天)", 20, remaining_calls // 20),
        ("重度使用 (100次/天)", 100, remaining_calls // 100),
    ]
    
    for scenario, daily_calls, days in daily_scenarios:
        print(f"  📊 {scenario}: 可用 {days} 天")

def main():
    """主程序"""
    print("🎯 AI使用量監控工具")
    print("=" * 50)
    print(f"⏰ 時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 設置環境
    setup_environment()
    print("✅ 環境已設置")
    
    # 快速測試
    print("\n" + "=" * 50)
    single_success = single_api_test()
    
    if single_success:
        # 進行多場景測試
        print("\n" + "=" * 50)
        total_calls = test_different_scenarios()
        
        # 顯示使用量估算
        show_usage_estimate(total_calls + 1)  # +1 包含快速測試
        
        print(f"\n🎉 監控完成！")
        print(f"📊 您可以到 Cursor Dashboard 查看實際使用量變化")
        print(f"💡 建議：定期監控確保不超出預算")
    else:
        print(f"\n😞 AI功能似乎沒有工作")
        print(f"🔧 請檢查環境配置")

if __name__ == "__main__":
    main() 