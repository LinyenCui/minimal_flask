#!/usr/bin/env python3
"""
測試增強後的AI系統
驗證能否正確處理您的難題：金額條件、狀態查詢等複雜邏輯
"""
import time
import logging
from modules.services.smart_assistant import process_with_smart_assistant
from modules.services.advanced_query_processor import process_ai_complex_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_enhanced_ai_system():
    """測試增強後的AI系統"""
    print("🚀 測試增強後的AI智能助手系統")
    print("=" * 70)
    
    # 您的難題測試案例
    difficult_queries = [
        {
            "query": "今天金額大於200的診所班次",
            "expected": "應該只返回總金額>200的診所班次，不是所有診所班次"
        },
        {
            "query": "找狀態為待派的班次", 
            "expected": "應該只返回status='待派'的班次"
        },
        {
            "query": "司機533昨天的車資",
            "expected": "應該查詢completed_trips表中司機533昨天的記錄"
        },
        {
            "query": "現在運行的班次有沒有狀態為待派的班次",
            "expected": "應該理解為查詢trips表中status='待派'的班次"
        }
    ]
    
    for i, test_case in enumerate(difficult_queries, 1):
        print(f"\n📝 測試 {i}: {test_case['query']}")
        print(f"📋 期望: {test_case['expected']}")
        print("-" * 60)
        
        try:
            # 第一階段：AI意圖分析
            start_time = time.time()
            ai_result = process_with_smart_assistant(test_case['query'], "test_user")
            analysis_time = time.time() - start_time
            
            print(f"⏱️  AI分析耗時: {analysis_time:.2f}秒")
            print(f"🎯 AI結果類型: {ai_result.get('type')}")
            print(f"📊 AI信心度: {ai_result.get('confidence')}")
            
            if 'ai_reasoning' in ai_result:
                print(f"🧠 AI推理: {ai_result['ai_reasoning'][:150]}...")
                print("💰 真正調用Gemini API (產生費用)")
            else:
                print("💰 使用傳統解析 (無費用)")
            
            # 第二階段：命令執行
            if ai_result.get('type') == 'execute_command':
                command = ai_result['command']
                print(f"✅ AI生成命令: {command}")
                
                # 如果是複雜查詢，測試高級處理器
                if command.startswith(("查已完成", "查詢班次")):
                    print(f"🔍 使用高級查詢處理器執行...")
                    
                    query_start = time.time()
                    query_result = process_ai_complex_query(command, "test_user")
                    query_time = time.time() - query_start
                    
                    print(f"⏱️  查詢執行耗時: {query_time:.2f}秒")
                    print(f"📊 查詢結果類型: {query_result.get('type')}")
                    
                    if query_result.get('type') == 'success':
                        print(f"🎉 查詢成功！找到 {query_result.get('count', 0)} 筆結果")
                        if 'total_amount' in query_result:
                            print(f"💰 總金額: {query_result['total_amount']:.0f}元")
                        print(f"📝 結果預覽:\n{query_result['message'][:200]}...")
                    elif query_result.get('type') == 'no_results':
                        print(f"📭 無結果: {query_result['message']}")
                    else:
                        print(f"❌ 查詢失敗: {query_result.get('message', '未知錯誤')}")
                else:
                    print(f"🔄 標準命令，將使用傳統處理")
            else:
                print(f"❌ AI無法理解或需要澄清")
                
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("🎯 測試完成！")

def test_ai_knowledge_base():
    """測試AI知識庫載入"""
    print("\n🧠 測試AI知識庫...")
    
    try:
        from modules.services.system_knowledge_base import (
            get_system_knowledge, get_table_info, analyze_time_perspective
        )
        
        knowledge = get_system_knowledge()
        print(f"✅ 知識庫載入成功")
        print(f"📊 資料庫表數量: {len(knowledge['database_schema'])}")
        print(f"🎯 可用功能數量: {len(knowledge['available_functions']['query_functions'])}")
        print(f"🔍 查詢範例數量: {len(knowledge['query_examples']['complex_queries'])}")
        
        # 測試時間態分析
        perspective, info = analyze_time_perspective("今天金額大於200的診所班次")
        print(f"🕐 時間態分析: {perspective} - {info['description']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 知識庫測試失敗: {e}")
        return False

if __name__ == "__main__":
    print("🔬 增強型AI系統完整測試")
    print("=" * 70)
    
    # 測試知識庫
    kb_success = test_ai_knowledge_base()
    
    if kb_success:
        # 測試完整AI系統
        test_enhanced_ai_system()
        
        print("\n💡 如果看到以下跡象，表示AI升級成功:")
        print("✅ AI分析耗時2-3秒 (真正調用Gemini)")
        print("✅ 生成正確的複雜查詢命令")
        print("✅ 高級查詢處理器正確解析條件")
        print("✅ 返回準確的篩選結果")
        print("\n📈 現在可以在LINE中測試您的難題了！")
    else:
        print("❌ 知識庫測試失敗，請檢查系統配置") 