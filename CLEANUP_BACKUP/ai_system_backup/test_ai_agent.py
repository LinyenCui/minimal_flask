"""
AI Agent 功能測試
測試AI Agent架構的各個組件
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.ai_agent.tool_registry import tool_registry
from modules.ai_agent.knowledge_base import knowledge_base
from modules.ai_agent.agent_core import dispatch_agent
from modules.ai_agent.ai_router import ai_router

def test_tool_registry():
    """測試工具註冊表"""
    print("🔧 測試工具註冊表...")
    
    # 測試獲取所有工具
    all_tools = tool_registry.get_all_tools()
    print(f"  註冊的工具數量: {len(all_tools)}")
    
    # 測試獲取特定工具
    tool = tool_registry.get_tool("query_dongyang_trips")
    if tool:
        print(f"  ✅ 東洋班次查詢工具: {tool.description}")
    else:
        print("  ❌ 找不到東洋班次查詢工具")
    
    # 測試按分類獲取工具
    from modules.ai_agent.tool_registry import ToolCategory
    query_tools = tool_registry.get_tools_by_category(ToolCategory.QUERY)
    print(f"  查詢類工具數量: {len(query_tools)}")
    
    print()

def test_knowledge_base():
    """測試知識庫"""
    print("📚 測試知識庫...")
    
    # 測試獲取資料庫結構
    trips_schema = knowledge_base.get_schema("trips")
    if trips_schema:
        print(f"  ✅ trips表結構: {len(trips_schema.columns)} 個欄位")
    else:
        print("  ❌ 找不到trips表結構")
    
    # 測試獲取業務規則
    rules = knowledge_base.get_business_rules()
    print(f"  業務規則數量: {len(rules)}")
    
    # 測試獲取使用範例
    examples = knowledge_base.get_examples()
    print(f"  使用範例數量: {len(examples)}")
    
    print()

def test_ai_router():
    """測試AI路由器"""
    print("🤖 測試AI路由器...")
    
    test_cases = [
        ("東洋班次", False, "傳統命令"),
        ("今天有什麼班次嗎？", True, "自然語言查詢"),
        ("請幫我查一下明天的診所班次", True, "自然語言請求"),
        ("班次詳情 1585", False, "精確命令"),
        ("如果明天下雨，班次要怎麼安排？", True, "複雜邏輯"),
        ("指派司機 1585 5386", False, "參數化命令"),
    ]
    
    for message, expected_ai, description in test_cases:
        decision = ai_router.should_use_ai_agent(message)
        result = "✅" if decision.use_ai_agent == expected_ai else "❌"
        print(f"  {result} 「{message}」 → {decision.reasoning} (信心度: {decision.confidence:.2f})")
    
    print()

def test_agent_core():
    """測試AI Agent核心（簡化版）"""
    print("🧠 測試AI Agent核心...")
    
    # 由於Gemini API可能不可用，我們只測試結構
    try:
        # 測試關鍵字提取
        from modules.ai_agent.agent_core import DispatchAgent
        agent = DispatchAgent()
        
        keywords = agent._extract_keywords("今天有什麼東洋班次")
        print(f"  關鍵字提取: {keywords}")
        
        # 測試回退規劃
        plan = agent._fallback_planning("東洋班次查詢")
        print(f"  回退規劃: {plan.tools}")
        
        print("  ✅ AI Agent核心結構正常")
        
    except Exception as e:
        print(f"  ❌ AI Agent核心測試失敗: {e}")
    
    print()

def test_integration():
    """測試整體集成"""
    print("🔗 測試整體集成...")
    
    # 測試模組導入
    try:
        from modules.ai_agent import (
            tool_registry, knowledge_base, dispatch_agent, ai_router
        )
        print("  ✅ 模組導入成功")
    except ImportError as e:
        print(f"  ❌ 模組導入失敗: {e}")
        return
    
    # 測試基本功能
    decision = ai_router.should_use_ai_agent("幫我查一下今天的班次")
    print(f"  路由決策: {decision.use_ai_agent} ({decision.reasoning})")
    
    print()

if __name__ == "__main__":
    print("🚀 AI Agent 功能測試")
    print("=" * 50)
    
    test_tool_registry()
    test_knowledge_base()
    test_ai_router()
    test_agent_core()
    test_integration()
    
    print("=" * 50)
    print("✅ 測試完成") 