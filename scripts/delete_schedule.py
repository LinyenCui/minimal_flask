from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Schedule

def delete_schedule():
    engine = create_engine('sqlite:///database.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 顯示現有班次供選擇
        schedules = session.query(Schedule).all()
        print("\n=== 現有班次列表 ===")
        for schedule in schedules:
            print(f"ID: {schedule.id}")
            print(f"日期時間: {schedule.date} {schedule.time}")
            print(f"路線: {schedule.start_point} -> {schedule.end_point}")
            print("------------------------")

        # 使用ID刪除
        schedule_id = input("請輸入要刪除的班次ID: ")
        schedule = session.query(Schedule).filter_by(id=schedule_id).first()
        
        if schedule:
            session.delete(schedule)
            session.commit()
            print("班次刪除成功！")
        else:
            print("找不到指定的班次！")

    except Exception as e:
        print(f"刪除時發生錯誤：{str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    delete_schedule()
