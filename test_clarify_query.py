#!/usr/bin/env python3
"""
測試 clarify_user_intent 的查詢邏輯
檢查是否會把無關班次列出來
"""
import os
import sys

# 設置環境
os.environ.setdefault('FLASK_APP', 'app.py')

from app import app
from modules.models.base import db
from sqlalchemy.sql import text
from modules.utils.unified_date_parser import UnifiedDateParser
from modules.utils.taiwan_time import get_taiwan_date

def test_query_logic():
    """測試查詢邏輯"""
    parser = UnifiedDateParser()
    today = get_taiwan_date()
    
    print("=" * 70)
    print("🧪 測試 clarify_user_intent 查詢邏輯")
    print("=" * 70)
    print(f"📅 今天: {today} ({today.strftime('%A')})")
    print()
    
    # 測試案例
    test_cases = [
        ("今天", "久保田家"),
        ("明天", "久保田家"),
        ("後天", "久保田家"),
        ("今天", "和緯四"),
        ("12/13", "和緯四"),
        ("12/14", "和緯四"),  # 星期六
    ]
    
    with app.app_context():
        for date_str, location in test_cases:
            print("-" * 70)
            parsed_date = parser.parse(date_str)
            if not parsed_date:
                print(f"❌ 無法解析日期: {date_str}")
                continue
            
            weekday = parsed_date.strftime('%A')
            print(f"🔍 測試: {date_str} {location}")
            print(f"   解析日期: {parsed_date} ({weekday})")
            
            # 判斷時間態
            if parsed_date < today:
                table_name = "completed_trips"
                id_field = "id"
            else:
                table_name = "trips"
                id_field = "trip_id"
            
            print(f"   查詢表: {table_name}")
            
            # 模擬 _query_trips_for_clarify 的查詢
            if table_name == "trips":
                query = text(f"""
                    SELECT {id_field} as id, date, time, start_point, end_point, status, passenger_leave_reason
                    FROM {table_name}
                    WHERE date = :date
                    AND (start_point LIKE :location OR via_point LIKE :location OR end_point LIKE :location)
                    ORDER BY time
                    LIMIT 10
                """)
            else:
                query = text(f"""
                    SELECT {id_field} as id, date, start_point, end_point, passenger_leave_reason
                    FROM {table_name}
                    WHERE date = :date
                    AND (start_point LIKE :location OR via_point LIKE :location OR end_point LIKE :location)
                    ORDER BY id
                    LIMIT 10
                """)
            
            params = {
                "date": parsed_date.strftime("%Y-%m-%d"),
                "location": f"%{location}%"
            }
            
            print(f"   查詢參數: date={params['date']}, location={params['location']}")
            
            results = db.session.execute(query, params).fetchall()
            
            if results:
                print(f"   ✅ 找到 {len(results)} 個班次:")
                for r in results:
                    print(f"      #{r.id} | {r.start_point}→{r.end_point} | {r.status if hasattr(r, 'status') else ''}")
            else:
                print(f"   📭 沒有找到相關班次")
            
            # 額外檢查：該日期有多少班次（不限地點）
            count_query = text(f"""
                SELECT COUNT(*) as cnt FROM {table_name} WHERE date = :date
            """)
            total = db.session.execute(count_query, {"date": params["date"]}).fetchone()
            print(f"   📊 該日期總班次數: {total.cnt}")
            
            print()
    
    print("=" * 70)
    print("🔍 檢查 _query_trips_for_clarify 原始代碼邏輯")
    print("=" * 70)
    
    # 讀取並顯示原始查詢代碼
    from modules.core.intent_executor import IntentExecutor
    import inspect
    
    # 獲取方法源代碼
    source = inspect.getsource(IntentExecutor._query_trips_for_clarify)
    
    # 找出 SQL 查詢部分
    print("📝 _query_trips_for_clarify 的 SQL 查詢:")
    print()
    
    # 檢查是否有 location 條件
    if "location" in source.lower():
        print("✅ 代碼中有 location 條件")
    else:
        print("❌ 代碼中可能缺少 location 條件！")
    
    # 顯示關鍵部分
    lines = source.split('\n')
    in_query = False
    for line in lines:
        if 'base_query' in line or 'SELECT' in line.upper():
            in_query = True
        if in_query:
            print(f"  {line}")
        if in_query and ('"""' in line or "'''" in line) and 'SELECT' not in line.upper():
            in_query = False


if __name__ == "__main__":
    test_query_logic()
