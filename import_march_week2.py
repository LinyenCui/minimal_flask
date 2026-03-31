import os
import uuid
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

REMOTE_DB_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

def sync():
    print("🚀 連線至遠端資料庫, 準備匯入 3月第2週 資料...")
    engine = create_engine(REMOTE_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 刪除 03-08 到 03-14 避免重複
        session.execute(text("DELETE FROM completed_trips WHERE date >= '2026-03-08' AND date <= '2026-03-14'"))
        
        with open('march_week2.txt', 'r', encoding='utf-8') as f:
            raw_lines = f.readlines()

        # Handle multiline rows
        lines = []
        for line in raw_lines:
            line = line.strip('\n') # keep tabs
            if not line.strip():
                continue
            # If the line starts with 4-digit ID
            if re.match(r'^\d{4}\t', line):
                lines.append(line)
            else:
                # it's a continuation of the previous string
                if lines:
                    lines[-1] += "\n" + line.strip()

        total_fare = 0
        count = 0
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 10:
                try:
                    trip_id = parts[0]
                    date = parts[1]
                    start_point = parts[3]
                    via_point = parts[4].strip() if parts[4].strip() else None
                    end_point = parts[5].strip()
                    driver_id = parts[6].strip()
                    meter_fare = int(parts[7].strip())
                    extra_fare = int(parts[8].strip()) if parts[8].strip() else 0
                    actual_fare = int(parts[9].strip())
                    
                    leave_or_remark = None
                    if len(parts) > 10 and parts[10].strip():
                        leave_or_remark = parts[10].strip()
                        # clean up surrounding quotes if it was a multiline Excel cell export
                        if leave_or_remark.startswith('"') and leave_or_remark.endswith('"'):
                            leave_or_remark = leave_or_remark[1:-1]
                    
                    category = '診所'
                    trip_type = 'fixed'
                    unique_code = f"restored_{uuid.uuid4().hex[:8]}"

                    modification_reason = None
                    passenger_leave_reason = None
                    
                    if leave_or_remark:
                        if leave_or_remark.startswith("[1]"):
                            modification_reason = leave_or_remark
                        else:
                            passenger_leave_reason = leave_or_remark

                    if actual_fare == 0 or passenger_leave_reason == "住院":
                        status = '已取消'
                    else:
                        status = '完成'

                    q = text("""
                        INSERT INTO completed_trips 
                        (date, start_point, via_point, end_point, meter_fare, extra_fare, actual_fare, category, 
                         driver_id, unique_code, status, trip_type, passenger_leave_reason, modification_reason)
                        VALUES (:date, :start_point, :via_point, :end_point, :meter_fare, :extra_fare, :actual_fare, :category, 
                         :driver_id, :unique_code, :status, :trip_type, :passenger_leave_reason, :modification_reason)
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
                        'unique_code': unique_code,
                        'status': status,
                        'trip_type': trip_type,
                        'passenger_leave_reason': passenger_leave_reason,
                        'modification_reason': modification_reason
                    })
                    count += 1
                    total_fare += actual_fare
                except Exception as e:
                    print(f"Error parsing line: {line}\nException: {e}")

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
