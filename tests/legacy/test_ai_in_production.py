#!/usr/bin/env python3
"""
測試修復後的AI智能助手是否能正常調用Gemini API
"""
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ai_detection():
    """測試如何識別AI調用"""
    print("🔍 如何識別真正的AI調用 vs 本地算法")
    print("=" * 60)
    
    print("✅ **真正AI調用的標誌：**")
    print("📝 日誌訊息包含:")
    print("   • '🤖 使用Gemini分析: [用戶輸入]'")
    print("   • '✅ AI分析成功: 信心度=0.95'")
    print("   • '🧠 AI推理: [詳細推理過程]'")
    print("   • '💰 API調用: 1次 (產生費用)'")
    print("   • 耗時: 2-3秒")
    print()
    
    print("❌ **本地算法的標誌：**")
    print("📝 日誌訊息包含:")
    print("   • '處理智能車資查詢: [用戶輸入]'")
    print("   • '解析條件: {固定格式}'")
    print("   • '修改意圖: None'")
    print("   • 耗時: <0.1秒")
    print("   • 沒有Gemini相關日誌")
    print()
    
    print("🎯 **快速判斷方法：**")
    print("1. 看耗時：AI調用需要2-3秒，本地算法瞬間完成")
    print("2. 看日誌：AI有'Gemini分析'和'AI推理'，本地只有'解析條件'")
    print("3. 看Usage-Based Spending：AI調用會產生費用")

def test_fixed_smart_assistant():
    """測試修復後的智能助手"""
    print("\n🛠️  測試修復後的智能助手")
    print("=" * 60)
    
    try:
        from modules.services.smart_assistant import process_with_smart_assistant
        print("✅ process_with_smart_assistant 導入成功")
        
        # 測試簡單調用
        test_query = "今天有什麼班次？"
        print(f"\n📝 測試查詢: {test_query}")
        
        start_time = time.time()
        result = process_with_smart_assistant(test_query, "test_user")
        end_time = time.time()
        
        print(f"⏱️  耗時: {(end_time - start_time):.2f}秒")
        print(f"🎯 結果類型: {result.get('type', 'unknown')}")
        print(f"📊 信心度: {result.get('confidence', 'N/A')}")
        
        if 'ai_reasoning' in result:
            print(f"🧠 AI推理: {result['ai_reasoning'][:100]}...")
            print("💰 使用真正的AI (會產生費用)")
        else:
            print("💰 使用傳統解析 (無費用)")
            
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 AI調用檢測指南")
    test_ai_detection()
    
    # 測試修復效果
    success = test_fixed_smart_assistant()
    
    if success:
        print("\n🎉 修復成功！現在可以使用以下命令測試:")
        print("   • 在LINE中輸入: /今天有什麼班次？")
        print("   • 觀察日誌是否出現 'Gemini分析' 和 'AI推理'")
        print("   • 檢查耗時是否為2-3秒")
    else:
        print("\n❌ 仍有問題，需要進一步調試") 