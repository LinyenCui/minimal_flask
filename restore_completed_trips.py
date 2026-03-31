import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REMOTE_DB_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

data = [
    ("2026-03-02", "萬年七街", "中華南路+新建路", "診所", 28530, 330, 0, 330, None),
    ("2026-03-02", "北門路二段", None, "診所", 533, 125, 0, 125, None),
    ("2026-03-02", "中華北路", "和緯二", "診所", 533, 200, 0, 200, None),
    ("2026-03-02", "仁和路", None, "診所", 533, 220, 0, 220, None),
    ("2026-03-02", "診所", None, "長溪路", 61553, 210, 0, 210, None),
    ("2026-03-02", "安定", None, "診所", 5386, 500, -220, 0, "住院"),
    ("2026-03-02", "健康三街", "建平七街+府前二街", "診所", 28530, 250, 0, 250, None),
    ("2026-03-02", "裕民街", None, "診所", 61553, 85, 0, 85, None),
    ("2026-03-02", "診所", None, "北門路二段", 61553, 125, 0, 125, None),
    ("2026-03-02", "診所", "新建路+中華南路", "萬年七街", 28530, 330, 0, 330, None),
    ("2026-03-02", "永大路", None, "診所", 533, 280, 0, 280, None),
    ("2026-03-02", "診所", "和緯二", "中華北路", 533, 200, 0, 200, None),
    ("2026-03-02", "診所", None, "仁和路", 61553, 220, -220, 0, "住院"),
    ("2026-03-02", "同安路", None, "診所", 533, 220, 0, 220, None),
    ("2026-03-02", "診所", None, "永大路", 61553, 280, 0, 280, None),
    ("2026-03-02", "診所", None, "安定", 5386, 500, 0, 500, None),
    ("2026-03-02", "小北路", "民德105", "診所", 533, 120, 0, 120, None),
    ("2026-03-02", "診所", None, "裕民街", 533, 85, 0, 85, None),
    ("2026-03-02", "診所", "府前二街+建平七街", "健康三街", 28530, 250, 0, 250, None),
    ("2026-03-02", "立德八路", None, "診所", 533, 165, 0, 165, None),
    ("2026-03-03", "怡平路", "古堡街+和緯五", "診所", 5386, 140, 0, 140, None),
    ("2026-03-03", "安北路", None, "診所", 5386, 230, 0, 230, None),
    ("2026-03-03", "土城", None, "診所", 533, 420, 0, 420, None),
    ("2026-03-03", "公園南路", "海安路", "診所", 533, 90, 0, 90, None)
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
            date, start_point, via_point, end_point, driver_id, meter_fare, extra_fare, actual_fare, remarks = row
            status = '完成'
            category = '診所'
            trip_type = 'fixed'
            # generate unique code to not violate constraints
            unique_code = f"restored_{uuid.uuid4().hex[:8]}"

            q = text("""
                INSERT INTO completed_trips 
                (date, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, driver_id, remarks, unique_code, status, trip_type)
                VALUES (:date, :start_point, :via_point, :end_point, :meter_fare, :extra_fare, :actual_fare, :category, :driver_id, :remarks, :unique_code, :status, :trip_type)
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
                'trip_type': trip_type
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
