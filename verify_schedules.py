from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Schedule, CompletedSchedule
from datetime import datetime

def verify_schedules():
    engine = create_engine('sqlite:///database.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("\n=== 總覽表（未完成班次）===")
        schedules = session.query(Schedule).order_by(Schedule.time).all()
        for s in schedules:
            print(f"時間: {s.time}")
            print(f"路線: {s.start_point} -> {s.end_point}")
            print(f"狀態: {s.status}")
            print("------------------------")

        print("\n=== 完成表（已完成班次）===")
        completed = session.query(CompletedSchedule).order_by(CompletedSchedule.time).all()
        for c in completed:
            print(f"時間: {c.time}")
            print(f"路線: {c.start_point} -> {c.end_point}")
            print("------------------------")

    except Exception as e:
        print(f"查詢時發生錯誤：{str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    verify_schedules()
