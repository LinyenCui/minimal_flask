#!/usr/bin/env python3
"""
修復 Render 生產環境的重複記錄
1. 連接到 Render PostgreSQL
2. 清理重複的 completed_trips 記錄
3. 添加唯一約束防止未來重複
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta

# Render PostgreSQL 連線資訊
RENDER_DB_CONFIG = {
    "host": "dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com",
    "user": "dispatch_system_db_user",
    "dbname": "dispatch_system_db",
    "password": "rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP",
    "port": 5432
}

def get_render_connection():
    """建立 Render 資料庫連線"""
    try:
        print("🔌 正在連接到 Render PostgreSQL...")
        conn = psycopg2.connect(**RENDER_DB_CONFIG)
        print("✅ 成功連接到 Render PostgreSQL")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ 無法連接到 Render PostgreSQL: {e}", file=sys.stderr)
        return None

def backup_duplicate_records(conn):
    """備份重複記錄"""
    print("\n📦 備份重複記錄")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 創建備份表
            cur.execute("""
            CREATE TABLE IF NOT EXISTS completed_trips_duplicates_backup AS
            SELECT * FROM completed_trips 
            WHERE id IN (
                SELECT id FROM completed_trips 
                WHERE unique_code IN (
                    SELECT unique_code 
                    FROM completed_trips 
                    GROUP BY unique_code 
                    HAVING COUNT(*) > 1
                )
            )
            """)
            conn.commit()
            print("✅ 已創建重複記錄備份表: completed_trips_duplicates_backup")
            
            # 檢查備份記錄數
            cur.execute("SELECT COUNT(*) FROM completed_trips_duplicates_backup")
            backup_count = cur.fetchone()[0]
            print(f"   備份記錄數: {backup_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ 備份重複記錄時發生錯誤: {e}", file=sys.stderr)
        conn.rollback()
        return False

def clean_duplicate_records(conn):
    """清理重複記錄"""
    print("\n🧹 清理重複記錄")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 找出重複的 unique_code
            cur.execute("""
            SELECT unique_code, array_agg(id ORDER BY id) as ids
            FROM completed_trips 
            GROUP BY unique_code 
            HAVING COUNT(*) > 1
            """)
            
            duplicates = cur.fetchall()
            print(f"🔍 找到 {len(duplicates)} 個重複的 unique_code")
            
            total_deleted = 0
            for unique_code, ids in duplicates:
                print(f"\n🔧 處理 unique_code: {unique_code}")
                print(f"   記錄IDs: {ids}")
                
                # 保留第一個記錄，刪除其他重複記錄
                keep_id = ids[0]
                delete_ids = ids[1:]
                
                print(f"   保留ID: {keep_id}")
                print(f"   刪除IDs: {delete_ids}")
                
                # 刪除重複記錄
                cur.execute("""
                DELETE FROM completed_trips 
                WHERE id = ANY(%s)
                """, (delete_ids,))
                
                deleted_count = cur.rowcount
                total_deleted += deleted_count
                print(f"   ✅ 已刪除 {deleted_count} 筆重複記錄")
            
            conn.commit()
            print(f"\n✅ 總共刪除了 {total_deleted} 筆重複記錄")
            return True
            
    except Exception as e:
        print(f"❌ 清理重複記錄時發生錯誤: {e}", file=sys.stderr)
        conn.rollback()
        return False

def add_unique_constraint(conn):
    """添加唯一約束"""
    print("\n🔒 添加唯一約束")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 檢查是否已有約束
            cur.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'completed_trips' 
              AND constraint_type = 'UNIQUE'
              AND constraint_name = 'unique_completed_trip_code'
            """)
            
            existing_constraints = cur.fetchall()
            if existing_constraints:
                print("✅ unique_code 唯一約束已存在")
                return True
            
            # 添加唯一約束
            print("🔧 添加 unique_code 唯一約束...")
            cur.execute("""
            ALTER TABLE completed_trips 
            ADD CONSTRAINT unique_completed_trip_code 
            UNIQUE (unique_code)
            """)
            conn.commit()
            print("✅ 成功添加 unique_code 唯一約束")
            return True
            
    except Exception as e:
        print(f"❌ 添加唯一約束時發生錯誤: {e}", file=sys.stderr)
        conn.rollback()
        return False

def verify_cleanup(conn):
    """驗證清理結果"""
    print("\n✅ 驗證清理結果")
    print("-" * 50)
    
    try:
        with conn.cursor() as cur:
            # 檢查是否還有重複記錄
            cur.execute("""
            SELECT COUNT(*) as total_trips,
                   COUNT(DISTINCT unique_code) as unique_trips
            FROM completed_trips
            """)
            
            stats = cur.fetchone()
            total_trips, unique_trips = stats
            
            print(f"📊 清理後統計:")
            print(f"   總班次數: {total_trips}")
            print(f"   唯一班次數: {unique_trips}")
            print(f"   重複率: {((total_trips - unique_trips) / total_trips * 100):.2f}%" if total_trips > 0 else "   重複率: 0%")
            
            if total_trips == unique_trips:
                print("✅ 清理成功！沒有重複記錄")
                return True
            else:
                print("❌ 清理失敗！仍有重複記錄")
                return False
                
    except Exception as e:
        print(f"❌ 驗證清理結果時發生錯誤: {e}", file=sys.stderr)
        return False

def main():
    """主函數"""
    print("🚨 修復 Render 生產環境重複記錄")
    print("=" * 60)
    print("⚠️  這將修改生產環境資料庫！")
    print("=" * 60)
    
    # 連接 Render 資料庫
    conn = get_render_connection()
    if not conn:
        return False
    
    try:
        # 步驟1: 備份重複記錄
        if not backup_duplicate_records(conn):
            print("❌ 備份失敗，停止執行")
            return False
        
        # 步驟2: 清理重複記錄
        if not clean_duplicate_records(conn):
            print("❌ 清理失敗")
            return False
        
        # 步驟3: 添加唯一約束
        if not add_unique_constraint(conn):
            print("❌ 添加約束失敗")
            return False
        
        # 步驟4: 驗證清理結果
        if not verify_cleanup(conn):
            print("❌ 驗證失敗")
            return False
        
        print("\n🎉 Render 生產環境修復完成！")
        print("=" * 60)
        print("✅ 重複記錄已清理")
        print("✅ 唯一約束已添加")
        print("✅ 可以安全生成週報表")
        
        return True
        
    except Exception as e:
        print(f"❌ 修復過程中發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("⚠️  警告：這將修改生產環境資料庫！")
    response = input("確定要繼續嗎？(yes/no): ")
    
    if response.lower() == 'yes':
        success = main()
        exit(0 if success else 1)
    else:
        print("❌ 操作已取消")
        exit(1)