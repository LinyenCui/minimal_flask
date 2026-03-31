import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REMOTE_DB_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

data = [
    # Photo 1 (6755 ~ 6786)
    ("2026-03-06", "大福街", None, "診所", 61553, 85, 0, 85, None),
    ("2026-03-06", "仁和路", None, "診所", 533, 220, -220, 0, "住院"),
    ("2026-03-06", "診所", None, "長溪路", 61553, 210, 0, 210, None),
    ("2026-03-06", "安定", None, "診所", 5386, 500, 0, 500, None),
    ("2026-03-06", "健康三街", "建平七街+府前二街", "診所", 28530, 250, 0, 250, None),
    ("2026-03-06", "裕民街", None, "診所", 61553, 85, 0, 85, None),
    ("2026-03-06", "診所", None, "北門路二段", 61553, 125, 0, 125, None),
    ("2026-03-06", "診所", "新建路+中華南路", "萬年七街", 28530, 330, 0, 330, None),
    ("2026-03-06", "永大路", None, "診所", 533, 280, 0, 280, None),
    ("2026-03-06", "診所", "和緯二", "中華北路", 533, 200, 0, 200, None),
    ("2026-03-06", "診所", None, "仁和路", 533, 220, -220, 0, "住院"),
    ("2026-03-06", "同安路", None, "診所", 61553, 220, 0, 220, None),
    ("2026-03-06", "診所", None, "永大路", 61553, 280, 0, 280, None),
    ("2026-03-06", "診所", None, "安定", 5386, 500, 0, 500, None),
    ("2026-03-06", "小北路", "民德105", "診所", 533, 120, 0, 120, None),
    ("2026-03-06", "診所", None, "裕民街", 533, 85, 0, 85, None),
    ("2026-03-06", "診所", "府前二街+建平七街", "健康三街", 28530, 250, 0, 250, None),
    ("2026-03-06", "立德八路", None, "診所", 28530, 165, 0, 165, None),
    ("2026-03-06", "診所", None, "立德八路", 61553, 165, 0, 165, None),
    ("2026-03-07", "怡平路", None, "診所", 28530, 140, 0, 140, None),
    ("2026-03-07", "安北路", "古堡街+和緯五", "診所", 28530, 230, 0, 230, None),
    ("2026-03-07", "土城", "湖美街46巷", "診所", 533, 420, 0, 420, None),
    ("2026-03-07", "公園南路", "海安路", "診所", 533, 90, 0, 90, None),
    ("2026-03-07", "龍埔街", "北門路三段", "診所", 61553, 340, 0, 340, None),
    ("2026-03-07", "文賢路", None, "診所", 61553, 90, 0, 90, None),
    ("2026-03-07", "診所", None, "怡平路", 533, 140, 0, 140, None),

    # Photo 2 (6787 ~ 6795)
    ("2026-03-07", "診所", "和緯五+安北路", "古堡街", 28530, 220, 0, 220, None),
    ("2026-03-07", "南寧街", None, "診所", 61553, 120, 0, 120, None),
    ("2026-03-07", "診所", "湖美街46巷", "土城", 533, 420, 0, 420, None),
    ("2026-03-07", "馬鎮宮", None, "診所", 28530, 330, 0, 330, None),
    ("2026-03-07", "診所", "海安路", "公園南路", 533, 90, 0, 90, None),
    ("2026-03-07", "診所", "北門路三段", "龍埔街", 28530, 340, 0, 340, None),
    ("2026-03-07", "診所", None, "文賢路", 533, 90, 0, 90, None),
    ("2026-03-07", "診所", None, "南寧街", 533, 120, 0, 120, None),
    ("2026-03-07", "診所", None, "馬鎮宮", 533, 330, 0, 330, None)
]

def restore_trips():
    print("🚀 連線至遠端資料庫...")
    engine = create_engine(REMOTE_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        import uuid

        count = 0
        for row in data:
            date, start_point, via_point, end_point, driver_id, meter_fare, extra_fare, actual_fare, leave_or_remark = row
            
            category = '診所'
            trip_type = 'fixed'
            unique_code = f"restored_{uuid.uuid4().hex[:8]}"
            
            # 如果說明是住院，轉成請假理由
            if leave_or_remark == "住院":
                status = '已取消'
                passenger_leave_reason = '住院'
                remarks = None
            elif leave_or_remark is not None:
                status = '完成'
                passenger_leave_reason = None
                remarks = leave_or_remark
            else:
                status = '完成'
                passenger_leave_reason = None
                remarks = None

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
