from datetime import datetime, date, time, timedelta
import os
import sys
from sqlalchemy.sql import text

# 確保可匯入專案根目錄下的 modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules import create_app, db

"""
插入 7 筆測試班次（今天 18:30 ~ 19:30，每 10 分鐘一筆），
路線在「海東六街」與「診所」間交替，狀態為「準備」、類別「診所」、乘客「自動測試」。
- 若 customers 中沒有對應 short_name，先建立（診所、海東六街）
- driver_id 設定為 5386，trip_type 設為 'fixed'（僅供測試）
"""

def ensure_customer(short_name: str):
    """在 customers 表建立指定 short_name。僅依賴安全欄位以避免欄位差異。"""
    try:
        sql = text(
            """
            INSERT INTO customers (short_name)
            VALUES (:short_name)
            ON CONFLICT (short_name) DO NOTHING
            """
        )
        db.session.execute(sql, {"short_name": short_name})
        db.session.commit()
    except Exception:
        db.session.rollback()
        sql2 = text(
            """
            INSERT INTO customers (name, address, short_name, category)
            VALUES (:name, :address, :short_name, :category)
            ON CONFLICT (short_name) DO NOTHING
            """
        )
        db.session.execute(
            sql2,
            {
                "name": short_name,
                "address": short_name,
                "short_name": short_name,
                "category": "診所",
            },
        )
        db.session.commit()


def main():
    app = create_app()
    with app.app_context():
        today = date.today()
        # 確保地點存在
        ensure_customer("診所")
        ensure_customer("海東六街")

        # 建立 7 筆：18:30, 18:40, ..., 19:30
        start_dt = datetime.combine(today, time(18, 30))
        times = [start_dt + timedelta(minutes=10 * i) for i in range(7)]

        insert_sql = text(
            """
            INSERT INTO trips (
                date, time, start_point, via_point, end_point,
                meter_fare, extra_fare, category, driver_id,
                status, trip_type, passenger_name
            ) VALUES (
                :date, :time, :start_point, NULL, :end_point,
                0, 0, '診所', :driver_id,
                '準備', 'fixed', '自動測試'
            )
            RETURNING trip_id
            """
        )

        created_ids = []
        for idx, dt in enumerate(times):
            if idx % 2 == 0:
                start_name, end_name = "海東六街", "診所"
            else:
                start_name, end_name = "診所", "海東六街"

            params = {
                "date": dt.date(),
                "time": dt.time(),
                "start_point": start_name,
                "end_point": end_name,
                "driver_id": 5386,
            }
            r = db.session.execute(insert_sql, params)
            row = r.fetchone()
            created_ids.append(row[0] if row else None)

        db.session.commit()
        print(f"✅ 已建立 7 筆測試班次: {created_ids}")


if __name__ == "__main__":
    main()
