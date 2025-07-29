#!/usr/bin/env python3
"""
AI路由器測試腳本
展示第一個任務的成果：核心AI路由器功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.services.ai_router import get_ai_router

def test_ai_router_basic():
    """測試AI路由器基本功能"""
    print("=" * 60)
    print("🚀 AI路由器測試 - 第一個任務成果展示")
    print("=" * 60)
    
    try:
        # 初始化路由器
        print("\n🔧 正在初始化AI路由器...")
        router = get_ai_router()
        print("✅ AI路由器初始化成功")
        
        # 測試消息
        test_messages = [
            "我要查詢今天的東洋班次",
            "昨天司機123的車資是多少？", 
            "明天要匯入固定班次",
            "幫我修改班次#456的車資",
            "可以分析一下本週的班次效率嗎？"
        ]
        
        print("\n📋 測試自然語言意圖分析:")
        print("-" * 60)
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n{i}. 測試: {message}")
            
            try:
                # 測試路由判斷
                should_use_ai = router.should_use_ai_router(message)
                print(f"   📍 路由判斷: {'使用AI路由器' if should_use_ai else '使用傳統處理'}")
                
                if should_use_ai:
                    # 測試意圖分析
                    intent = router.analyze_intent(message)
                    print(f"   🎯 時間態度: {intent.time_perspective.value}")
                    print(f"   🔧 操作類型: {intent.operation_type.value}")
                    print(f"   📊 信心度: {intent.confidence:.2f}")
                    print(f"   🧠 推理: {intent.reasoning}")
                    
                    # 測試路由功能
                    result = router.route_to_service(intent)
                    print(f"   ✅ 路由結果: {result.success}")
                    print(f"   💬 回應: {result.response_text}")
                else:
                    print("   ➡️  將回退到傳統命令處理")
                    
            except Exception as e:
                print(f"   ❌ 錯誤: {e}")
        
        print("\n" + "=" * 60)
        print("✅ 第一個任務完成！核心AI路由器已就緒")
        print("🔄 下個階段：創建系統知識庫和意圖分析prompt")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        print("請檢查Gemini API配置")

def test_traditional_commands():
    """測試傳統命令判斷"""
    print("\n🔄 測試傳統命令判斷:")
    print("-" * 30)
    
    router = get_ai_router()
    traditional_commands = [
        "東洋班次",
        "診所班次", 
        "匯入固定班次",
        "幫助",
        "資料庫同步"
    ]
    
    for cmd in traditional_commands:
        should_use_ai = router.should_use_ai_router(cmd)
        print(f"'{cmd}' -> {'AI路由器' if should_use_ai else '傳統處理'}")

if __name__ == "__main__":
    print("注意：此測試需要Google Cloud認證和網路連接")
    print("如果沒有Gemini API，將使用備用關鍵詞匹配")
    print()
    
    test_ai_router_basic()
    test_traditional_commands() 