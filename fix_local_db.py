import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("❌ No DATABASE_URL found in .env")
    exit(1)

if db_url.startswith('postgresql+psycopg://'):
    db_url = db_url.replace('postgresql+psycopg://', 'postgresql://') 

def fix_local_db():
    print(f"🚀 連線至本地資料庫: {db_url}")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. 補齊 trips 欄位
        trip_cols = [
            "custom_start_point VARCHAR(100)",
            "custom_via_point VARCHAR(100)",
            "custom_end_point VARCHAR(100)",
            "modified_by TEXT",
            "modification_reason TEXT",
            "modification_time TIMESTAMP WITHOUT TIME ZONE",
            "passenger_name TEXT",
            "passenger_leave_reason TEXT"
        ]
        for col in trip_cols:
            q = f"ALTER TABLE trips ADD COLUMN IF NOT EXISTS {col};"
            try:
                session.execute(text(q))
                session.commit()
                print(f"✅ Executed: {q}")
            except Exception as e:
                session.rollback()
                print(f"⚠️ Skipped {q}: {e}")

        # 2. 補齊 completed_trips 欄位
        ct_cols = [
            "status VARCHAR(20)",
            "modified_by TEXT",
            "modification_reason TEXT",
            "modification_time TIMESTAMP WITHOUT TIME ZONE",
            "passenger_name TEXT",
            "passenger_leave_reason TEXT"
        ]
        for col in ct_cols:
            q = f"ALTER TABLE completed_trips ADD COLUMN IF NOT EXISTS {col};"
            try:
                session.execute(text(q))
                session.commit()
                print(f"✅ Executed: {q}")
            except Exception as e:
                session.rollback()
                print(f"⚠️ Skipped {q}: {e}")

        # 3. 加回 UNIQUE 約束
        unique_constraints = [
            "ALTER TABLE completed_trips ADD CONSTRAINT uk_completed_trips_unique_code UNIQUE (unique_code);"
        ]
        for q in unique_constraints:
            try:
                session.execute(text(q))
                session.commit()
                print(f"✅ Executed Constraint: {q}")
            except Exception as e:
                session.rollback()
                print(f"⚠️ Skipped Constraint: {e}")

        print("🎉 本地資料庫修正完成！")

    finally:
        session.close()

if __name__ == '__main__':
    fix_local_db()
