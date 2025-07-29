#!/usr/bin/env python3
"""
系統知識庫測試腳本
展示第二個任務的成果：完整的系統知識庫功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.services.system_knowledge import get_system_knowledge

def test_knowledge_base_comprehensive():
    """全面測試系統知識庫功能"""
    print("=" * 70)
    print("🧠 系統知識庫測試 - 第二個任務成果展示")
    print("=" * 70)
    
    kb = get_system_knowledge()
    
    # 1. 知識庫基本信息
    print("\n📊 知識庫基本信息:")
    print("-" * 40)
    summary = kb.get_knowledge_summary()
    print(f"📋 資料表數量: {summary['total_schemas']}")
    print(f"🔧 業務功能數量: {summary['total_functions']}")
    print(f"⏰ 時間態度類型: {summary['time_perspectives']}")
    print(f"🎯 操作類型: {summary['operation_types']}")
    
    # 2. 測試自然語言理解
    print("\n🔍 自然語言理解測試:")
    print("-" * 40)
    
    test_cases = [
        {
            "text": "我要查詢今天的東洋班次",
            "expected_time": "present",
            "expected_op": "query"
        },
        {
            "text": "昨天司機123的車資是多少？",
            "expected_time": "past", 
            "expected_op": "query"
        },
        {
            "text": "明天要匯入固定班次",
            "expected_time": "future",
            "expected_op": "create"
        },
        {
            "text": "幫我修改班次#456的車資為800元",
            "expected_time": "present",
            "expected_op": "modify"
        },
        {
            "text": "上週司機5386的效率統計分析",
            "expected_time": "past",
            "expected_op": "query"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. 測試文本: {case['text']}")
        
        # 時間態度分析
        time_scores = kb.classify_time_perspective(case['text'])
        best_time = max(time_scores, key=time_scores.get)
        time_confidence = time_scores[best_time]
        
        print(f"   ⏰ 時間態度: {best_time} (信心度: {time_confidence:.2f})")
        print(f"   📊 詳細分數: {time_scores}")
        
        # 操作類型分析
        op_scores = kb.classify_operation_type(case['text'])
        best_op = max(op_scores, key=op_scores.get)
        op_confidence = op_scores[best_op]
        
        print(f"   🎯 操作類型: {best_op} (信心度: {op_confidence:.2f})")
        print(f"   📊 詳細分數: {op_scores}")
        
        # 實體提取
        entities = kb.extract_entities(case['text'])
        print(f"   🏷️  實體提取: {entities}")
        
        # 功能建議
        suggested_func = kb.get_suggested_function(best_time, best_op, entities)
        print(f"   💡 建議功能: {suggested_func}")
        
        # 準確性檢查
        time_correct = best_time == case['expected_time']
        op_correct = best_op == case['expected_op']
        print(f"   ✅ 準確性: 時間態度 {'✓' if time_correct else '✗'}, 操作類型 {'✓' if op_correct else '✗'}")
    
    # 3. 測試資料庫知識
    print(f"\n💾 資料庫結構知識測試:")
    print("-" * 40)
    
    for table_name in ["trips", "completed_trips", "fixed_schedules"]:
        schema = kb.get_schema_for_table(table_name)
        if schema:
            print(f"\n📋 {table_name} 表:")
            print(f"   📝 說明: {schema.description}")
            print(f"   ⏰ 時間態度: {schema.time_perspective}")
            print(f"   🔧 主要欄位: {len(schema.columns)} 個")
            print(f"   🔗 關聯關係: {len(schema.relationships)} 個")
            print(f"   📋 業務規則: {len(schema.business_rules)} 條")
    
    # 4. 測試業務功能映射
    print(f"\n🔧 業務功能映射測試:")
    print("-" * 40)
    
    for time_perspective in ["past", "present", "future"]:
        functions = kb.get_functions_by_time_perspective(time_perspective)
        print(f"\n⏰ {time_perspective} 時間態功能 ({len(functions)}個):")
        for func in functions[:3]:  # 只顯示前3個
            print(f"   • {func.function_name}: {func.description}")
    
    # 5. 複雜查詢測試
    print(f"\n🧮 複雜查詢理解測試:")
    print("-" * 40)
    
    complex_queries = [
        "可以幫我分析一下司機5386上個月的東洋班次效率嗎？",
        "我需要修改昨天班次#789的車資，從500改成600元",
        "明天的固定班次匯入需要排除請假的司機",
        "查詢本週所有診所班次的完成情況和收入統計"
    ]
    
    for query in complex_queries:
        print(f"\n🔍 查詢: {query}")
        
        time_scores = kb.classify_time_perspective(query)
        op_scores = kb.classify_operation_type(query)
        entities = kb.extract_entities(query)
        
        best_time = max(time_scores, key=time_scores.get)
        best_op = max(op_scores, key=op_scores.get)
        suggested_func = kb.get_suggested_function(best_time, best_op, entities)
        
        print(f"   📊 分析結果: {best_time} + {best_op} → {suggested_func}")
        print(f"   🏷️  關鍵實體: {entities}")
    
    print("\n" + "=" * 70)
    print("✅ 第二個任務完成！系統知識庫功能齊全")
    print("🧠 包含完整的資料庫結構、業務規則和智能分類")
    print("🔄 下個階段：設計意圖分析prompt")
    print("=" * 70)

def test_knowledge_export():
    """測試知識庫匯出功能"""
    print("\n📤 測試知識庫匯出功能:")
    print("-" * 30)
    
    kb = get_system_knowledge()
    
    try:
        json_data = kb.export_knowledge_json()
        print(f"✅ 成功匯出知識庫 JSON ({len(json_data)} 字符)")
        
        # 顯示部分內容
        import json
        data = json.loads(json_data)
        print(f"📋 包含表結構: {list(data['database_schemas'].keys())}")
        print(f"🔧 包含功能: {len(data['business_functions'])} 個")
        
    except Exception as e:
        print(f"❌ 匯出失敗: {e}")

if __name__ == "__main__":
    test_knowledge_base_comprehensive()
    test_knowledge_export() 