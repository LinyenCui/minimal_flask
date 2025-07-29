#!/usr/bin/env python3
"""
測試固定班表查詢修復
"""
import sys
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.handlers.fixed_schedule_query_handler import query_fixed_schedules_by_customer

def test_fixed_schedule_query():
    """測試固定班表查詢修復"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試固定班表查詢修復")
        print("=" * 50)
        
        test_cases = ['北門路', '中華南路', '新建路']
        
        for customer in test_cases:
            print(f"\n📝 測試查詢: {customer}")
            print("-" * 30)
            
            try:
                result = query_fixed_schedules_by_customer(customer, 'test_user')
                
                if isinstance(result, dict) and result.get('type') == 'quick_reply':
                    # 成功找到，分析結果
                    text = result['text']
                    buttons = result['quick_reply']['items']
                    
                    # 提取統計信息
                    lines = text.split('\n')
                    summary_line = lines[0] if lines else ""
                    
                    print(f"✅ {summary_line}")
                    print(f"   操作按鈕數量: {len(buttons)}")
                    
                    # 顯示找到的班次
                    schedule_count = summary_line.split()[1] if '找到' in summary_line else "0"
                    if schedule_count != "0":
                        # 顯示操作按鈕
                        action_buttons = [btn['action']['label'] for btn in buttons if btn['action']['label'] != '取消']
                        if action_buttons:
                            print(f"   可用操作: {', '.join(action_buttons[:3])}{'...' if len(action_buttons) > 3 else ''}")
                    
                elif isinstance(result, str) and '找不到' in result:
                    print(f"❌ {result}")
                else:
                    print(f"⚠️  未預期的結果格式: {type(result)}")
                    
            except Exception as e:
                print(f"❌ 查詢失敗: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 測試完成")

if __name__ == "__main__":
    test_fixed_schedule_query()