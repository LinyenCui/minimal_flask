#!/usr/bin/env python3
"""
測試固定班次查詢的精確匹配功能
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.handlers.fixed_schedule_query_handler import query_fixed_schedules_by_customer

def test_exact_matching():
    """測試精確匹配功能"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試固定班次查詢精確匹配")
        print("=" * 60)
        
        # 先查看資料庫中的實際地點名稱
        print("1️⃣ 查看資料庫中的地點資料")
        print("-" * 40)
        
        from modules.models.base import db
        from sqlalchemy.sql import text
        
        query = """
        SELECT DISTINCT start_point FROM fixed_schedules WHERE start_point IS NOT NULL
        UNION
        SELECT DISTINCT via_point FROM fixed_schedules WHERE via_point IS NOT NULL  
        UNION
        SELECT DISTINCT end_point FROM fixed_schedules WHERE end_point IS NOT NULL
        ORDER BY 1
        """
        
        locations = db.session.execute(text(query)).fetchall()
        
        print("   資料庫中的地點:")
        for loc in locations[:10]:  # 只顯示前10個
            print(f"      {loc[0]}")
        
        # 測試精確匹配
        print(f"\n2️⃣ 測試精確匹配")
        print("-" * 40)
        
        test_cases = [
            "北門路二段",
            "大灣二街", 
            "診所",
            "新建路"
        ]
        
        for customer in test_cases:
            print(f"\n   測試查詢: '{customer}'")
            print(f"   {'-' * 30}")
            
            try:
                result = query_fixed_schedules_by_customer(customer, 'test_user')
                
                if isinstance(result, dict) and result.get('type') == 'quick_reply':
                    # 成功找到，分析結果
                    text = result['text']
                    buttons = result['quick_reply']['items']
                    
                    # 提取統計信息
                    lines = text.split('\n')
                    summary_line = lines[0] if lines else ""
                    
                    print(f"   ✅ {summary_line}")
                    
                    # 查找班次詳情，確認沒有誤匹配
                    for line in lines:
                        if "📍 路線：" in line:
                            print(f"      {line.strip()}")
                    
                elif isinstance(result, str) and '找不到' in result:
                    print(f"   ❌ {result}")
                else:
                    print(f"   ⚠️  未預期的結果格式")
                    
            except Exception as e:
                print(f"   ❌ 查詢失敗: {e}")
        
        print(f"\n" + "=" * 60)
        print("🎉 精確匹配測試完成")

if __name__ == "__main__":
    test_exact_matching()