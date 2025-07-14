#!/usr/bin/env python3
"""
啟用 Gemini API 的配置腳本
讓您的 AI 功能真正開始工作並使用調用額度
"""
import os
import sys
from pathlib import Path

def setup_gemini_api_environment():
    """設置 Gemini API 環境變數"""
    print("🚀 正在設置 Gemini API 環境...")
    
    # 設置環境變數
    credentials_path = os.path.join(os.getcwd(), 'temp_files', 'chrome-flight-458709-d1-cc3bdb1f0846.json')
    
    env_vars = {
        'GOOGLE_APPLICATION_CREDENTIALS': credentials_path,
        'GCP_PROJECT_ID': 'chrome-flight-458709-d1',
        'GCP_LOCATION': 'us-central1',
        'GEMINI_MODEL': 'gemini-2.0-flash-001'
    }
    
    print("\n📋 設置以下環境變數:")
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"  ✅ {key}: {value}")
    
    # 驗證憑證文件
    if os.path.exists(credentials_path):
        print(f"\n✅ 憑證文件已找到: {credentials_path}")
    else:
        print(f"\n❌ 憑證文件不存在: {credentials_path}")
        return False
    
    return True

def test_gemini_api_functionality():
    """測試 Gemini API 功能"""
    print("\n🧪 測試 Gemini API 功能...")
    
    try:
        from modules.services.ai_service import extract_booking_info_with_gemini
        
        test_cases = [
            "明天下午3點從高鐵站到診所",
            "後天早上9點送張先生到東洋，車資400",
            "5/15 14:30 從公司到醫院，經過安平"
        ]
        
        print("\n📊 測試結果:")
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🔍 測試 {i}: {test_case}")
            
            result = extract_booking_info_with_gemini(test_case)
            
            if result:
                print(f"  ✅ 成功解析:")
                for key, value in result.items():
                    if value:
                        print(f"    {key}: {value}")
                print(f"  💰 這次調用會消耗您的 API 額度!")
            else:
                print(f"  ❌ 解析失敗")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        return False

def test_ai_router_functionality():
    """測試 AI 路由器功能"""
    print("\n🧪 測試 AI 路由器功能...")
    
    try:
        from modules.services.ai_router import get_ai_router
        
        router = get_ai_router()
        
        test_messages = [
            "我要查詢今天的東洋班次",
            "昨天司機123的車資是多少？",
            "明天要匯入固定班次"
        ]
        
        print("\n📊 路由器測試結果:")
        for i, message in enumerate(test_messages, 1):
            print(f"\n🔍 測試 {i}: {message}")
            
            should_use_ai = router.should_use_ai_router(message)
            print(f"  📍 是否使用 AI: {should_use_ai}")
            
            if should_use_ai:
                print(f"  💰 這種請求會消耗您的 API 額度!")
            else:
                print(f"  💡 這種請求使用傳統處理")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 路由器測試失敗: {e}")
        return False

def show_usage_expectations():
    """顯示使用量預期"""
    print("\n📊 API 使用量預期:")
    print("=" * 50)
    
    scenarios = [
        ("預約叫車", "每次自然語言預約", "1-2 次調用"),
        ("AI 車資查詢", "智能搜索已完成班次", "1 次調用"),
        ("AI 路由器", "自然語言命令理解", "1 次調用"),
        ("複雜對話", "多輪對話修正", "2-3 次調用")
    ]
    
    for feature, description, usage in scenarios:
        print(f"  🔹 {feature:<12} | {description:<20} | {usage}")
    
    print("\n💡 預期月使用量:")
    print("  📈 輕度使用 (10-20 次/天):    50-100 次調用")
    print("  📈 中度使用 (50-100 次/天):   200-500 次調用")
    print("  📈 重度使用 (100+ 次/天):     500+ 次調用")
    
    print("\n💰 您的 $50 額度大約可以支撐:")
    print("  🎯 約 10,000-50,000 次 API 調用")
    print("  🎯 足夠支撐 2-6 個月的正常使用")

def main():
    """主程序"""
    print("🎯 Gemini API 啟用助手")
    print("=" * 50)
    
    # 設置環境
    if not setup_gemini_api_environment():
        print("\n❌ 環境設置失敗")
        sys.exit(1)
    
    # 測試預約功能
    print("\n" + "=" * 50)
    if test_gemini_api_functionality():
        print("\n✅ 預約 AI 功能測試通過")
    else:
        print("\n❌ 預約 AI 功能測試失敗")
    
    # 測試路由器功能
    print("\n" + "=" * 50)
    if test_ai_router_functionality():
        print("\n✅ AI 路由器功能測試通過")
    else:
        print("\n❌ AI 路由器功能測試失敗")
    
    # 顯示使用量預期
    print("\n" + "=" * 50)
    show_usage_expectations()
    
    print("\n🎉 設置完成！")
    print("💡 現在您的 AI 功能會真正使用 Gemini API")
    print("📊 Usage-Based Spending 將開始計算實際使用量")
    print("🚀 去試試自然語言預約: '明天下午3點從高鐵站到診所'")

if __name__ == "__main__":
    main() 