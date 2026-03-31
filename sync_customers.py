import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def sync_customers():
    local_url = os.environ.get('DATABASE_URL').replace('postgresql+psycopg', 'postgresql')
    remote_url = 'postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db'

    print("🚀 從本地資料庫讀取 customers...")
    local_engine = create_engine(local_url)
    remote_engine = create_engine(remote_url)

    LocSession = sessionmaker(bind=local_engine)
    RemSession = sessionmaker(bind=remote_engine)
    
    loc_session = LocSession()
    rem_session = RemSession()

    try:
        # Read from local
        local_customers = loc_session.execute(text("SELECT id, name, short_name, address, category FROM customers")).fetchall()
        print(f"📊 找到 {len(local_customers)} 筆本地客戶資料")

        # Upsert to remote
        count = 0
        for customer in local_customers:
            q = text("""
                INSERT INTO customers (id, name, short_name, address, category)
                VALUES (:id, :name, :short_name, :address, :category)
                ON CONFLICT (id) DO UPDATE SET 
                    name=EXCLUDED.name, 
                    short_name=EXCLUDED.short_name, 
                    address=EXCLUDED.address, 
                    category=EXCLUDED.category
            """)
            try:
                rem_session.execute(q, {
                    'id': customer.id, 'name': customer.name, 'short_name': customer.short_name, 
                    'address': customer.address, 'category': customer.category
                })
                count += 1
            except Exception as e:
                print(f"⚠️ 同步客戶 {customer.short_name} 失敗: {e}")
                
        rem_session.execute(text("SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers) + 1)"))
        rem_session.commit()
        print(f"🎉 成功同步 {count} 筆客戶資料至遠端資料庫！")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        rem_session.rollback()
    finally:
        loc_session.close()
        rem_session.close()

if __name__ == '__main__':
    sync_customers()
