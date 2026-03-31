import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REMOTE_DB_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

data = [
    ("2026-03-03", "龍埔街", "北門路三段", "診所", 61553, 340, 0, 340, None),
    ("2026-03-03", "診所", None, "怡平路", 28530, 140, 0, 140, None),
    ("2026-03-03", "文賢路", "和緯五+安北路", "診所", 61553, 90, 0, 90, None),
    ("2026-03-03", "診所", None, "古堡街", 533, 220, 0, 220, None),
    ("2026-03-03", "南寧街", None, "診所", 61553, 120, 0, 120, None),
    ("2026-03-03", "診所", "湖美街46巷", "土城", 533, 420, 0, 420, None),
    ("2026-03-03", "馬鎮宮", None, "診所", 28530, 330, 0, 330, None),
    ("2026-03-03", "診所", "海安路", "公園南路", 61553, 90, 0, 90, None),
    ("2026-03-03", "診所", "北門路三段", "龍埔街", 61553, 340, 0, 340, None),
    ("2026-03-03", "診所", None, "文賢路", 533, 120, 0, 120, None),
    ("2026-03-03", "診所", None, "南寧街", 533, 90, 0, 90, None),
    ("2026-03-03", "診所", None, "馬鎮宮", 533, 330, 0, 330, None),
    ("2026-03-04", "萬年七街", "中華南路+新建路", "診所", 28530, 330, 0, 330, None),
    ("2026-03-04", "北門路二段", None, "診所", 533, 125, 0, 125, None),
    ("2026-03-04", "中華北路", "和緯二", "診所", 533, 200, 0, 200, None),
    ("2026-03-04", "仁和路", None, "診所", 533, 220, -220, 0, "住院"),
    ("2026-03-04", "診所", None, "長溪路", 61553, 210, 0, 210, None),
    ("2026-03-04", "安定", None, "診所", 5386, 500, 0, 500, None),
    ("2026-03-04", "健康三街", "建平七街+府前二街", "診所", 28530, 250, 0, 250, None),
    ("2026-03-04", "裕民街", None, "診所", 61553, 85, 0, 85, None),
    ("2026-03-04", "診所", None, "北門路二段", 61553, 125, 0, 125, None),
    ("2026-03-04", "診所", "新建路+中華南路", "萬年七街", 28530, 330, 0, 330, None),
    ("2026-03-04", "永大路", None, "診所", 533, 280, 0, 280, None),
    ("2026-03-04", "診所", "和緯二", "中華北路", 533, 200, 0, 200, None),
    ("2026-03-04", "立德八路", None, "診所", 28530, 165, 0, 165, None),
    ("2026-03-04", "診所", None, "仁和路", 533, 220, -220, 0, "住院")
]

def check_customers_exist(session):
    all_points = set()
    for row in data:
        all_points.add(row[1])
        all_points.add(row[3])
    
    missing = []
    for p in all_points:
        exists = session.execute(text("SELECT 1 FROM customers WHERE short_name = :p"), {'p': p}).scalar()
        if not exists:
            missing.append(p)
    return missing

def restore_trips():
    print("🚀 連線至遠端資料庫...")
    engine = create_engine(REMOTE_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        missing_customers = check_customers_exist(session)
        if missing_customers:
            print(f"❌ 發生錯誤，以下地點不在遠端客戶資料庫中: {missing_customers}")
            return

        import uuid

        count = 0
        for row in data:
            date, start_point, via_point, end_point, driver_id, meter_fare, extra_fare, actual_fare, leave_or_remark = row
            
            category = '診所'
            trip_type = 'fixed'
            unique_code = f"restored_{uuid.uuid4().hex[:8]}"
            
            # 處理住院 (請假理由)
            if leave_or_remark == "住院":
                status = '已取消'
                passenger_leave_reason = '住院'
                remarks = None
            else:
                status = '完成'
                passenger_leave_reason = None
                remarks = leave_or_remark

            q = text("""
                INSERT INTO completed_trips 
                (date, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id, remarks, unique_code, status, trip_type, passenger_leave_reason)
                VALUES (:date, :start_point, :via_point, :end_point, :meter_fare, :extra_fare, :actual_fare, :category, :driver_id, :remarks, :unique_code, :status, :trip_type, :passenger_leave_reason)
            """)
            session.execute(q, {
                'date': date,
                'start_point': start_point,
                'via_point': via_point,
                'end_point': end_point,
                'meter_fare': meter_fare,
                'extra_fare': extra_fare,
                'actual_fare': actual_fare,
                'category': category,
                'driver_id': driver_id,
                'remarks': remarks,
                'unique_code': unique_code,
                'status': status,
                'trip_type': trip_type,
                'passenger_leave_reason': passenger_leave_reason
            })
            count += 1

        session.commit()
        print(f"🎉 成功匯入 {count} 筆 completed_trips 紀錄至遠端資料庫！")

    except Exception as e:
        session.rollback()
        print(f"❌ 發生錯誤: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    restore_trips()
