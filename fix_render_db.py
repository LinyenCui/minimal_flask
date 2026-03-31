import os
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

RENDER_DB_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

def sync_render_db():
    print("🚀 正在連線至遠端 Render 資料庫...")
    engine = create_engine(RENDER_DB_URL)
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
                print(f"⚠️ Skipped {q} (可能已存): {e}")

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
                print(f"⚠️ Skipped {q} (可能已存): {e}")

        # 3. 移除導致問題的外鍵綁定
        drop_fks = [
            "ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_start_point_fkey;",
            "ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_via_point_fkey;",
            "ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_end_point_fkey;",
            "ALTER TABLE completed_trips DROP CONSTRAINT IF EXISTS completed_trips_start_point_fkey;",
            "ALTER TABLE completed_trips DROP CONSTRAINT IF EXISTS completed_trips_via_point_fkey;",
            "ALTER TABLE completed_trips DROP CONSTRAINT IF EXISTS completed_trips_end_point_fkey;",
            "ALTER TABLE fixed_schedules DROP CONSTRAINT IF EXISTS fixed_schedules_start_point_fkey;",
            "ALTER TABLE fixed_schedules DROP CONSTRAINT IF EXISTS fixed_schedules_via_point_fkey;",
            "ALTER TABLE fixed_schedules DROP CONSTRAINT IF EXISTS fixed_schedules_end_point_fkey;"
        ]
        for q in drop_fks:
            try:
                session.execute(text(q))
                session.commit()
                print(f"✅ Executed: {q}")
            except Exception as e:
                session.rollback()
                print(f"⚠️ Skipped dropping FK (可能已經不存在): {e}")

        # 4. 加回需要的外鍵與 UNIQUE 約束
        unique_constraints = [
            "ALTER TABLE trips ADD CONSTRAINT trips_start_point_fkey FOREIGN KEY (start_point) REFERENCES customers(short_name);",
            "ALTER TABLE trips ADD CONSTRAINT trips_end_point_fkey FOREIGN KEY (end_point) REFERENCES customers(short_name);",
            "ALTER TABLE completed_trips ADD CONSTRAINT completed_trips_start_point_fkey FOREIGN KEY (start_point) REFERENCES customers(short_name);",
            "ALTER TABLE completed_trips ADD CONSTRAINT completed_trips_end_point_fkey FOREIGN KEY (end_point) REFERENCES customers(short_name);",
            "ALTER TABLE completed_trips ADD CONSTRAINT uk_completed_trips_unique_code UNIQUE (unique_code);"
        ]
        for q in unique_constraints:
            try:
                session.execute(text(q))
                session.commit()
                print(f"✅ Executed Constraint: {q}")
            except Exception as e:
                session.rollback()
                print(f"⚠️ Skipped Constraint (可能已套用或重複): {e}")

        # 5. 復原 Driver 表
        print("🚚 開始復原遠端 drivers 資料表資料...")
        try:
            content = open('CLEANUP_BACKUP/auto_backup_20250719_233146.sql', 'r', encoding='utf-8', errors='ignore').read()
            start_marker = "COPY public.drivers (id, name, plate_number, car_brand, car_model) FROM stdin;"
            start_idx = content.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                end_idx = content.find("\\.", start_idx)
                copy_data = content[start_idx:end_idx].strip()
                
                # We DO NOT TRUNCATE because there might be existing trips tied to these drivers via FKs.
                # Instead, we gently UPSERT the drivers.
                lines = copy_data.split('\n')
                restored_count = 0
                for line in lines:
                    parts = line.split('\t')
                    if len(parts) >= 5:
                        did, name, plate, brand, model = parts[:5]
                        plate = None if plate == '\\N' else plate
                        brand = None if brand == '\\N' else brand
                        model = None if model == '\\N' else model
                        session.execute(
                            text("INSERT INTO drivers (id, name, plate_number, car_brand, car_model) VALUES (:id, :name, :plate, :brand, :model) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, plate_number=EXCLUDED.plate_number, car_brand=EXCLUDED.car_brand, car_model=EXCLUDED.car_model"),
                            {"id": int(did), "name": name, "plate": plate, "brand": brand, "model": model}
                        )
                        restored_count += 1
                session.execute(text("SELECT setval('drivers_id_seq', (SELECT MAX(id) FROM drivers) + 1)"))
                session.commit()
                print(f"✅ Successfully restored {restored_count} drivers to Render.")
            else:
                print("❌ Could not find COPY public.drivers in local backup.")
        except Exception as e:
            session.rollback()
            print(f"❌ Error restoring remote drivers: {e}")

        # 6. 加入「臨時地點」特殊客戶
        print("🧑‍🤝‍🧑 加入缺失的地點與佔位符號(臨時地點)...")
        try:
            existing = session.execute(text("SELECT id FROM customers WHERE short_name = '臨時地點'")).fetchone()
            if not existing:
                session.execute(text("SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers) + 1)"))
                max_id = session.execute(text("SELECT MAX(id) FROM customers")).scalar() or 0
                session.execute(
                    text("INSERT INTO customers (id, name, short_name, address, category) VALUES (:id, :name, :short_name, :address, :cat)"),
                    {"id": max_id + 1, "name": "(臨時地點)", "short_name": "臨時地點", "address": "(系統自動復原)", "cat": "系統專用"}
                )
                session.commit()
                print("✅ Successfully injected '臨時地點' into remote customers.")
            else:
                print("ℹ️ '臨時地點' already exists in Render DB.")
        except Exception as e:
            session.rollback()
            print(f"❌ Error setting placeholder customer: {e}")

        print("🎉 遠端資料庫同步作業完成！")

    finally:
        session.close()

if __name__ == '__main__':
    sync_render_db()
