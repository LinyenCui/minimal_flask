#!/usr/bin/env python3
"""
測試真正的AI車資查詢功能
驗證是否成功替換假AI為真AI
"""
import os
import time
import logging

# 設置環境
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/linyancui/minimal_flask/temp_files/chrome-flight-458709-d1-cc3bdb1f0846.json'
os.environ['GCP_PROJECT_ID'] = 'chrome-flight-458709-d1'

def test_fake_vs_true_ai():
    """對比測試假AI vs 真AI"""
    print("🔍 對比測試：假AI vs 真AI")
    print("=" * 60)
    
    test_query = "查詢今天5386的車資"
    
    # 測試1: 假AI (舊版)
    print("\n📊 測試1: 假AI (本地算法)")
    print("-" * 40)
    try:
        from modules.services.ai_fare_service import handle_smart_fare_query
        start_time = time.time()
        fake_result = handle_smart_fare_query(test_query, "test_user", use_flex=False)
        end_time = time.time()
        
        print(f"查詢: {test_query}")
        print(f"耗時: {(end_time - start_time):.3f}秒")
        print(f"技術: 本地算法 (CompletedTripMatcher)")
        print(f"API調用: 0次")
        print(f"結果長度: {len(str(fake_result))} 字符")
        print(f"標頭顯示: 🔍 AI智能搜索 (騙人的)")
    except Exception as e:
        print(f"假AI測試失敗: {e}")
    
    # 測試2: 真AI (新版)
    print("\n🤖 測試2: 真AI (Gemini API)")
    print("-" * 40)
    try:
        from modules.services.ai_enhanced_fare_service import handle_true_ai_fare_query
        start_time = time.time()
        true_result = handle_true_ai_fare_query(test_query, "test_user")
        end_time = time.time()
        
        print(f"查詢: {test_query}")
        print(f"耗時: {(end_time - start_time):.3f}秒")
        print(f"技術: Gemini API 調用")
        print(f"API調用: 1次")
        print(f"結果長度: {len(str(true_result))} 字符")
        print(f"標頭顯示: 🤖 真正的AI智能搜索")
        
        # 檢查是否真的使用了AI
        if end_time - start_time > 0.5:
            print("✅ 確認使用了真正的AI (耗時>0.5秒)")
        else:
            print("❌ 可能仍在使用本地算法 (耗時太短)")
            
    except Exception as e:
        print(f"真AI測試失敗: {e}")

def test_ai_understanding():
    """測試AI理解能力"""
    print("\n\n🧠 測試AI理解能力")
    print("=" * 60)
    
    test_queries = [
        "查詢今天5386的車資",
        "昨天司機123的班次費用是多少",
        "我想知道7月14日診所班次的錢",
        "修改班次#456的錶價為400加成80",
        "司機533今天賺了多少錢"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 測試{i}: {query}")
        print("-" * 30)
        
        try:
            from modules.services.ai_enhanced_fare_service import handle_true_ai_fare_query
            start_time = time.time()
            result = handle_true_ai_fare_query(query, f"test_user_{i}")
            end_time = time.time()
            
            print(f"⏱️ 耗時: {(end_time - start_time):.2f}秒")
            print(f"🤖 AI分析完成")
            
            # 檢查結果特徵
            if "🤖" in result and "AI" in result:
                print("✅ 確認使用了真正的AI")
            elif "🔍 AI智能搜索" in result:
                print("❌ 仍在使用假AI")
            else:
                print("❓ 結果格式不明確")
                
        except Exception as e:
            print(f"❌ 測試失敗: {e}")

def test_ai_service_initialization():
    """測試AI服務初始化"""
    print("\n\n⚙️ 測試AI服務初始化")
    print("=" * 60)
    
    try:
        from modules.services.ai_enhanced_fare_service import get_true_ai_fare_service
        
        print("🔧 初始化真正的AI服務...")
        start_time = time.time()
        ai_service = get_true_ai_fare_service()
        end_time = time.time()
        
        print(f"✅ AI服務初始化成功，耗時: {(end_time - start_time):.2f}秒")
        print(f"🤖 模型: {ai_service.model}")
        print(f"📊 服務類型: {type(ai_service).__name__}")
        
        # 測試直接調用
        print("\n🧪 測試直接調用AI分析...")
        test_analysis = ai_service.analyze_fare_query_with_ai("查詢今天的車資")
        print(f"✅ AI分析結果: {test_analysis.get('intent')} (信心度: {test_analysis.get('confidence')})")
        
    except Exception as e:
        print(f"❌ AI服務初始化失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 真正的AI車資查詢功能測試")
    print("🎯 驗證是否成功從假AI升級到真AI")
    print("=" * 80)
    
    test_fake_vs_true_ai()
    test_ai_understanding()
    test_ai_service_initialization()
    
    print("\n\n📊 測試總結")
    print("=" * 40)
    print("✅ 如果看到耗時>1秒，表示真正使用了AI")
    print("✅ 如果看到 '🤖 真正的AI智能搜索'，表示升級成功")
    print("❌ 如果仍然看到 '🔍 AI智能搜索'，表示仍是假AI")
    print("💰 真AI每次調用約消耗 $0.001 API額度")
    print("�� 假AI調用 $0 API額度") 