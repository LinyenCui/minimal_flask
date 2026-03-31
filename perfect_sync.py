import os
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REMOTE_DB_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

def sync():
    print("🚀 連線至遠端資料庫, 準備執行完美同步...")
    engine = create_engine(REMOTE_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. 刪除該週舊資料避免重複
        session.execute(text("DELETE FROM completed_trips WHERE date >= '2026-03-01' AND date <= '2026-03-07'"))
        
        # 2. 讀取 user_trips.txt
        with open('user_trips.txt', 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]

        total_fare = 0
        count = 0
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 10:
                try:
                    trip_id = parts[0]
                    date = parts[1]
                    # col 2 = weekday
                    start_point = parts[3]
                    via_point = parts[4] if parts[4] else None
                    end_point = parts[5]
                    driver_id = parts[6]
                    meter_fare = int(parts[7])
                    extra_fare = int(parts[8]) if parts[8] else 0
                    actual_fare = int(parts[9])
                    leave_or_remark = parts[10] if len(parts) > 10 and parts[10] else None
                    
                    category = '診所'
                    trip_type = 'fixed'
                    unique_code = f"restored_{uuid.uuid4().hex[:8]}"

                    if leave_or_remark == "住院" or actual_fare == 0:
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
                    total_fare += actual_fare
                except ValueError:
                    pass

        session.commit()
        print(f"🎉 成功匯入 {count} 筆 completed_trips 紀錄！")
        print(f"💰 資料庫加總核對: {total_fare} 元")

    except Exception as e:
        session.rollback()
        print(f"❌ 發生錯誤: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    sync()
