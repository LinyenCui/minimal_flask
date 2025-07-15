#!/usr/bin/env python3
"""
測試真正的AI智能助手功能
驗證Gemini API是否正確調用，Usage-Based Spending是否開始計費
"""
import time
import logging
from modules.services.smart_assistant import process_with_smart_assistant, format_smart_response

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ai_assistant():
    """測試真正的AI智能助手"""
    print("🤖 測試真正的AI智能助手功能")
    print("=" * 60)
    
    test_queries = [
        "今天有什麼班次嗎？",
        "我想查詢明天的東洋班次",
        "司機123今天工作安排如何？",
        "幫我匯入下週的固定班次",
        "昨天診所班次的收入是多少？",
        "我要請假不能搭車",
        "修改班次456的車資為500元"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 測試 {i}: {query}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            
            # 調用真正的AI智能助手
            result = process_with_smart_assistant(query, "test_user")
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"⏱️  耗時: {duration:.2f}秒")
            print(f"🎯 結果類型: {result.get('type', 'unknown')}")
            print(f"📊 信心度: {result.get('confidence', 'N/A')}")
            
            if 'ai_reasoning' in result:
                print(f"🧠 AI推理: {result['ai_reasoning']}")
                print("💰 API調用: 1次 (產生費用)")
            else:
                print("💰 API調用: 0次 (使用傳統解析)")
            
            # 格式化並顯示回應
            response_text = format_smart_response(result)
            print(f"💬 回應:\n{response_text}")
            
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(test_queries):
            print("\n⏳ 等待2秒避免API限制...")
            time.sleep(2)
    
    print("\n" + "=" * 60)
    print("🎯 測試完成！檢查您的Usage-Based Spending是否有變化")

def test_ai_initialization():
    """測試AI初始化狀態"""
    print("🔧 檢查AI初始化狀態")
    print("-" * 40)
    
    try:
        from modules.services.smart_assistant import smart_assistant
        
        print(f"AI是否可用: {smart_assistant.ai_enabled}")
        print(f"模型狀態: {'已初始化' if smart_assistant.model else '未初始化'}")
        
        if smart_assistant.ai_enabled:
            print("✅ AI系統正常，將產生API調用費用")
            return True
        else:
            print("❌ AI系統未啟用，將使用傳統解析")
            return False
            
    except Exception as e:
        print(f"❌ AI初始化檢查失敗: {e}")
        return False

if __name__ == "__main__":
    print("🚀 真正的AI智能助手測試程序")
    print("=" * 60)
    
    # 檢查AI初始化
    ai_ready = test_ai_initialization()
    
    print("\n")
    
    # 執行AI功能測試
    test_ai_assistant()
    
    if ai_ready:
        print("\n🎉 如果看到「AI推理」和「耗時1-3秒」，說明真正的AI正在工作！")
        print("💰 您的Usage-Based Spending應該開始計費了")
    else:
        print("\n⚠️  AI未啟用，檢查環境變數和憑證配置") 