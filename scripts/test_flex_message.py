from app import app, handle_query_fixed_trips_flex
import json

def test_fixed_trips_flex():
    """測試固定班次Flex Message格式"""
    with app.app_context():
        # 測試當前日期的固定班次
        bubble, error = handle_query_fixed_trips_flex('查詢固定班次')
        if bubble:
            print("成功獲取固定班次Flex Message:")
            print(json.dumps(bubble, indent=2, ensure_ascii=False))
        else:
            print(f"錯誤: {error}")
        
        # 測試指定日期的固定班次
        bubble, error = handle_query_fixed_trips_flex('查詢固定班次 2025-03-15')
        if bubble:
            print("\n成功獲取2025-03-15的固定班次Flex Message:")
            print(json.dumps(bubble, indent=2, ensure_ascii=False))
        else:
            print(f"\n錯誤: {error}")

if __name__ == "__main__":
    test_fixed_trips_flex() 