from app import app, handle_query_trips_flex
import json
import traceback

def test_query_trips_flex():
    """測試班次查詢Flex Message格式，並找出bs_flex錯誤的來源"""
    with app.app_context():
        try:
            # 測試當前日期的班次
            bubble, error = handle_query_trips_flex('查詢班次')
            if bubble:
                print("成功獲取班次Flex Message:")
                print(json.dumps(bubble, indent=2, ensure_ascii=False))
            else:
                print(f"錯誤: {error}")
        except Exception as e:
            print(f"發生異常: {str(e)}")
            traceback.print_exc()
            
        try:
            # 測試指定日期的班次
            bubble, error = handle_query_trips_flex('查詢班次 2025-03-15')
            if bubble:
                print("\n成功獲取2025-03-15的班次Flex Message:")
                print(json.dumps(bubble, indent=2, ensure_ascii=False))
            else:
                print(f"\n錯誤: {error}")
        except Exception as e:
            print(f"發生異常: {str(e)}")
            traceback.print_exc()

if __name__ == "__main__":
    test_query_trips_flex() 