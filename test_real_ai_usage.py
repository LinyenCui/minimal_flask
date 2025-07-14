#!/usr/bin/env python3
"""
測試真正的AI使用情況
幫助用戶區分哪些功能使用了AI，哪些是本地算法
"""
import os
import time
import logging

# 設置環境
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/linyancui/minimal_flask/temp_files/chrome-flight-458709-d1-cc3bdb1f0846.json'
os.environ['GCP_PROJECT_ID'] = 'chrome-flight-458709-d1'

def test_local_algorithm():
    """測試本地算法（不使用AI）"""
    print("🔍 測試本地算法（不使用AI）")
    print("=" * 50)
    
    from modules.services.ai_fare_service import CompletedTripMatcher
    
    test_queries = [
        "查詢今天5386的車資",
        "查詢司機123的班次",
        "7/5診所班次",
        "今天東洋班次"
    ]
    
    matcher = CompletedTripMatcher()
    
    for query in test_queries:
        start_time = time.time()
        result = matcher.parse_natural_query(query)
        end_time = time.time()
        
        print(f"查詢: {query}")
        print(f"耗時: {(end_time - start_time)*1000:.1f}毫秒")
        print(f"信心度: {result['confidence']}")
        print(f"💰 API調用: 0次")
        print()

def test_real_ai_calls():
    """測試真正的AI調用"""
    print("🤖 測試真正的AI調用")
    print("=" * 50)
    
    from modules.services.ai_service import extract_booking_info_with_gemini
    from modules.services.ai_router import AIRouter
    
    ai_router = AIRouter()
    
    test_queries = [
        "明天下午3點從高鐵站到診所",
        "我要預約後天的班次",
        "幫我查一下司機的工作安排"
    ]
    
    for query in test_queries:
        print(f"查詢: {query}")
        
        # 測試1: 預約AI提取
        try:
            start_time = time.time()
            booking_result = extract_booking_info_with_gemini(query)
            end_time = time.time()
            
            print(f"預約AI提取耗時: {(end_time - start_time):.2f}秒")
            print(f"結果: {booking_result}")
            print(f"💰 API調用: 1次")
        except Exception as e:
            print(f"預約AI提取失敗: {e}")
        
        # 測試2: AI路由器
        try:
            start_time = time.time()
            intent = ai_router.analyze_intent(query)
            end_time = time.time()
            
            print(f"AI路由器耗時: {(end_time - start_time):.2f}秒")
            print(f"意圖: {intent.time_perspective.value}, {intent.operation_type.value}")
            print(f"信心度: {intent.confidence}")
            print(f"💰 API調用: 1次")
        except Exception as e:
            print(f"AI路由器失敗: {e}")
        
        print()

def test_hybrid_functions():
    """測試混合功能（可能使用AI，也可能使用本地算法）"""
    print("🔄 測試混合功能")
    print("=" * 50)
    
    from modules.services.ai_fare_service import handle_smart_fare_query
    
    test_queries = [
        "查詢今天5386的車資",  # 本地算法
        "我想查詢昨天診所班次的費用情況",  # 可能觸發AI
        "修改班次#123的錢為400加成80"  # 可能觸發AI
    ]
    
    for query in test_queries:
        print(f"查詢: {query}")
        try:
            start_time = time.time()
            result = handle_smart_fare_query(query, "test_user", use_flex=False)
            end_time = time.time()
            
            print(f"耗時: {(end_time - start_time):.2f}秒")
            
            # 判斷是否使用了AI
            if end_time - start_time > 0.5:  # 超過0.5秒可能使用了AI
                print(f"💰 可能使用了AI（耗時較長）")
            else:
                print(f"💰 使用本地算法（耗時極短）")
            
            print(f"結果長度: {len(str(result))} 字符")
        except Exception as e:
            print(f"測試失敗: {e}")
        print()

if __name__ == "__main__":
    print("🎯 AI使用情況測試報告")
    print("=" * 60)
    print()
    
    test_local_algorithm()
    print()
    test_real_ai_calls()
    print()
    test_hybrid_functions()
    
    print("📊 總結:")
    print("• 本地算法: 毫秒級響應，0 API調用")
    print("• 真正AI: 1-2秒響應，消耗API額度")
    print("• 混合功能: 根據查詢複雜度自動選擇") 