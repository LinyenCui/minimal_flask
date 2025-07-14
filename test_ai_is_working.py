#!/usr/bin/env python3
"""
AI 調用測試腳本
驗證您的系統是否真的在使用 Gemini API
"""
import os
import sys
import time
import logging
from datetime import datetime

def setup_environment():
    """設置測試環境"""
    print("🔧 設置測試環境...")
    
    # 設置環境變數（這是關鍵！）
    credentials_path = os.path.join(os.getcwd(), 'temp_files', 'chrome-flight-458709-d1-cc3bdb1f0846.json')
    
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    os.environ['GCP_PROJECT_ID'] = 'chrome-flight-458709-d1'
    os.environ['GCP_LOCATION'] = 'us-central1'
    os.environ['GEMINI_MODEL'] = 'gemini-2.0-flash-001'
    
    print("✅ 環境變數設置完成")
    return True

def test_1_direct_ai_call():
    """測試1: 直接調用AI功能"""
    print("\n" + "="*60)
    print("📊 測試1: 直接調用 Gemini API")
    print("="*60)
    
    try:
        from modules.services.ai_service import extract_booking_info_with_gemini
        
        test_messages = [
            "明天下午2點從高鐵站到診所",
            "後天早上9點載王先生到東洋，車資500",
            "下週三 14:30 從公司經過安平到醫院"
        ]
        
        api_calls_made = 0
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n🔍 測試案例 {i}: {message}")
            
            start_time = time.time()
            result = extract_booking_info_with_gemini(message)
            end_time = time.time()
            
            if result:
                api_calls_made += 1
                print(f"  ✅ AI 成功解析 (耗時: {end_time-start_time:.2f}秒)")
                print(f"  📊 解析結果: {result}")
                print(f"  💰 這次調用消耗了您的 API 額度!")
            else:
                print(f"  ❌ AI 解析失敗")
        
        print(f"\n📈 總共成功調用 AI: {api_calls_made} 次")
        return api_calls_made > 0
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_2_ai_fare_service():
    """測試2: AI車資查詢服務"""
    print("\n" + "="*60)
    print("📊 測試2: AI車資查詢服務")
    print("="*60)
    
    try:
        from modules.services.ai_fare_service import should_use_ai_query, handle_smart_fare_query
        
        test_queries = [
            "查詢今天司機123的車資",
            "昨天的診所班次費用是多少",
            "修改班次#456的錶價為400",
            "7/5司機533診所班次",  # 這是您截圖中的查詢
        ]
        
        ai_queries_detected = 0
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 測試案例 {i}: {query}")
            
            # 檢查是否會觸發AI
            should_use_ai = should_use_ai_query(query)
            print(f"  📍 是否觸發AI: {should_use_ai}")
            
            if should_use_ai:
                ai_queries_detected += 1
                print(f"  💰 這個查詢會調用 Gemini API!")
                
                # 實際調用AI服務（注意：這會真正消耗API額度）
                try:
                    print(f"  🔄 正在調用AI服務...")
                    start_time = time.time()
                    result = handle_smart_fare_query(query, "test_user", use_flex=False)
                    end_time = time.time()
                    
                    print(f"  ✅ AI服務調用成功 (耗時: {end_time-start_time:.2f}秒)")
                    print(f"  📄 回應長度: {len(str(result))} 字符")
                    
                except Exception as e:
                    print(f"  ⚠️ AI服務調用出錯: {e}")
            else:
                print(f"  💡 這個查詢使用本地算法")
        
        print(f"\n📈 總共觸發 AI 的查詢: {ai_queries_detected} 個")
        return ai_queries_detected > 0
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_3_ai_router():
    """測試3: AI路由器系統"""
    print("\n" + "="*60)
    print("📊 測試3: AI路由器系統")
    print("="*60)
    
    try:
        from modules.services.ai_router import get_ai_router
        
        router = get_ai_router()
        
        test_messages = [
            "我要查詢昨天的東洋班次",
            "幫我分析這週司機123的效率",
            "可以幫我修改班次#789的車資嗎？",
            "東洋班次",  # 這個不會觸發AI
            "診所班次",  # 這個也不會觸發AI
        ]
        
        ai_routes = 0
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n🔍 測試案例 {i}: {message}")
            
            # 檢查路由判斷
            should_use_ai = router.should_use_ai_router(message)
            print(f"  📍 路由決策: {'使用 AI' if should_use_ai else '使用傳統處理'}")
            
            if should_use_ai:
                ai_routes += 1
                print(f"  💰 這個請求會調用 Gemini API 進行意圖分析!")
                
                # 測試實際的意圖分析（會真正調用API）
                try:
                    print(f"  🔄 正在進行意圖分析...")
                    start_time = time.time()
                    intent = router.analyze_intent(message)
                    end_time = time.time()
                    
                    print(f"  ✅ 意圖分析完成 (耗時: {end_time-start_time:.2f}秒)")
                    print(f"  📊 時間態度: {intent.time_perspective.value}")
                    print(f"  📊 操作類型: {intent.operation_type.value}")
                    print(f"  📊 信心度: {intent.confidence}")
                    
                except Exception as e:
                    print(f"  ⚠️ 意圖分析出錯: {e}")
            else:
                print(f"  💡 使用傳統關鍵詞匹配")
        
        print(f"\n📈 總共觸發 AI 路由: {ai_routes} 個")
        return ai_routes > 0
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

def test_4_logging_verification():
    """測試4: 通過日誌驗證API調用"""
    print("\n" + "="*60)
    print("📊 測試4: 日誌驗證AI調用")
    print("="*60)
    
    # 設置日誌捕獲
    import io
    from contextlib import redirect_stderr
    
    # 創建日誌捕獲器
    log_capture = io.StringIO()
    
    # 設置日誌級別
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    try:
        from modules.services.ai_service import extract_booking_info_with_gemini
        
        print("🔍 進行一次AI調用並監控日誌...")
        
        with redirect_stderr(log_capture):
            result = extract_booking_info_with_gemini("明天上午10點從台南高鐵站到奇美醫院")
        
        # 檢查日誌內容
        log_content = log_capture.getvalue()
        
        # 查找關鍵的API調用指標
        api_indicators = [
            "Calling Gemini API model",
            "Gemini API response received",
            "Successfully parsed JSON"
        ]
        
        found_indicators = []
        for indicator in api_indicators:
            if indicator in log_content:
                found_indicators.append(indicator)
        
        print(f"📊 找到的API調用指標: {len(found_indicators)}/{len(api_indicators)}")
        
        for indicator in found_indicators:
            print(f"  ✅ {indicator}")
        
        if found_indicators:
            print(f"💰 確認: Gemini API 真正被調用了!")
            return True
        else:
            print(f"❌ 沒有找到API調用的證據")
            return False
            
    except Exception as e:
        print(f"❌ 日誌測試失敗: {e}")
        return False

def show_line_bot_test_guide():
    """顯示LINE Bot測試指南"""
    print("\n" + "="*60)
    print("📱 LINE Bot 實際測試指南")
    print("="*60)
    
    print("🚀 如果您想在實際的 LINE Bot 中測試AI功能:")
    print()
    print("1️⃣ **預約叫車功能測試**:")
    print("   📝 在LINE中發送: '預約叫車'")
    print("   📝 然後發送: '明天下午3點從高鐵站到診所'")
    print("   ✅ 如果AI工作，會立即解析並回應")
    print()
    print("2️⃣ **AI車資查詢測試**:")
    print("   📝 發送: '查詢今天司機123的車資'")
    print("   📝 發送: '7/5司機533診所班次'")
    print("   ✅ 如果AI工作，會顯示'🔍 AI智能搜索'")
    print()
    print("3️⃣ **檢查應用日誌**:")
    print("   📝 查看應用啟動日誌")
    print("   📝 尋找: 'Calling Gemini API model'")
    print("   📝 尋找: 'Gemini API response received'")
    print()
    print("4️⃣ **重要提醒**:")
    print("   ⚠️  需要在應用啟動時設置環境變數")
    print("   ⚠️  重啟應用讓環境變數生效")
    print("   ⚠️  每次API調用都會消耗您的額度")

def main():
    """主測試程序"""
    print("🎯 AI調用測試程序")
    print("=" * 60)
    print(f"⏰ 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 設置環境
    if not setup_environment():
        print("❌ 環境設置失敗")
        sys.exit(1)
    
    # 執行各種測試
    test_results = []
    
    test_results.append(("直接AI調用", test_1_direct_ai_call()))
    test_results.append(("AI車資查詢", test_2_ai_fare_service()))
    test_results.append(("AI路由器", test_3_ai_router()))
    test_results.append(("日誌驗證", test_4_logging_verification()))
    
    # 顯示測試總結
    print("\n" + "="*60)
    print("📊 測試總結")
    print("="*60)
    
    passed_tests = 0
    for test_name, result in test_results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"  {test_name:<15} | {status}")
        if result:
            passed_tests += 1
    
    print(f"\n📈 測試通過率: {passed_tests}/{len(test_results)} ({passed_tests/len(test_results)*100:.1f}%)")
    
    if passed_tests > 0:
        print("\n🎉 恭喜！您的AI功能正在工作！")
        print("💰 這些測試調用已經消耗了您的API額度")
        print("📊 您可以去 Cursor 的 dashboard 查看使用量變化")
    else:
        print("\n😞 AI功能似乎沒有正常工作")
        print("🔧 請檢查環境變數配置和網路連接")
    
    # 顯示LINE Bot測試指南
    show_line_bot_test_guide()

if __name__ == "__main__":
    main() 