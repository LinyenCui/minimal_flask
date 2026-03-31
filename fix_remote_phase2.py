import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

RENDER_DB_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

def fix_remote_db():
    print(f"🚀 連線至遠端資料庫...")
    engine = create_engine(RENDER_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. 補齊 trips 欄位
        trip_cols = [
            "trip_type VARCHAR(20) DEFAULT 'fixed'"
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
            "trip_type VARCHAR(20) DEFAULT 'fixed'"
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

        print("🎉 遠端資料庫 trip_type 欄位修正完成！")

    finally:
        session.close()

if __name__ == '__main__':
    fix_remote_db()
