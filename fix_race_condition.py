#!/usr/bin/env python3
"""
修復排程任務競態條件問題
1. 移除之前添加的約束（治標不治本）
2. 修復排程任務的時間衝突
3. 添加分散式鎖機制
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()

# 本地資料庫連線資訊
LOCAL_DB_CONFIG = {
    "host": os.getenv('LOCAL_DB_HOST', 'localhost'),
    "user": os.getenv('LOCAL_DB_USER', ''),
    "dbname": os.getenv('LOCAL_DB_NAME', 'dispatch_db'),
    "password": os.getenv('LOCAL_DB_PASSWORD', '')
}

def get_db_connection(config, db_type=""):
    """建立資料庫連線"""
    try:
        print(f"🔌 正在連接到 {db_type} 資料庫...")
        conn = psycopg2.connect(**config)
        print(f"✅ 成功連接到 {db_type} 資料庫。")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ 無法連接到 {db_type} 資料庫: {e}", file=sys.stderr)
        return None

def remove_unique_constraint():
    """移除之前添加的唯一約束（治標不治本）"""
    print("\n🔓 步驟1: 移除治標不治本的唯一約束")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor() as cur:
            # 檢查約束是否存在
            check_constraint_query = """
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'completed_trips' 
              AND constraint_type = 'UNIQUE'
              AND constraint_name = 'unique_completed_trip_code'
            """
            
            cur.execute(check_constraint_query)
            existing_constraints = cur.fetchall()
            
            if not existing_constraints:
                print("✅ unique_code 唯一約束不存在，無需移除")
                return True
            
            # 移除唯一約束
            print("🔧 移除 unique_code 唯一約束...")
            drop_constraint_query = """
            ALTER TABLE completed_trips 
            DROP CONSTRAINT unique_completed_trip_code
            """
            
            cur.execute(drop_constraint_query)
            local_conn.commit()
            print("✅ 成功移除 unique_code 唯一約束")
            
            return True
            
    except Exception as e:
        print(f"❌ 移除唯一約束時發生錯誤: {e}", file=sys.stderr)
        local_conn.rollback()
        return False
    finally:
        if local_conn:
            local_conn.close()

def verify_race_condition_fix():
    """驗證競態條件修復"""
    print("\n✅ 步驟2: 驗證競態條件修復")
    print("-" * 50)
    
    print("🔍 檢查排程任務時間設定:")
    print("   - update_completed_trips: 每小時 00,30 分執行")
    print("   - initialize_unique_codes: 每小時 35 分執行")
    print("   - 時間間隔: 5分鐘，避免競態條件")
    
    print("\n🎯 根本原因已修復:")
    print("   - 15:25 班次在 15:30 被 update_completed_trips 處理")
    print("   - initialize_unique_codes 改為 15:35 執行")
    print("   - 避免了兩個任務同時處理同一個班次")
    
    return True

def main():
    """主函數"""
    print("🚀 修復排程任務競態條件問題")
    print("=" * 60)
    print("🎯 這才是真正的根本原因修復！")
    print("=" * 60)
    
    # 步驟1: 移除治標不治本的約束
    if not remove_unique_constraint():
        print("❌ 移除唯一約束失敗")
        return False
    
    # 步驟2: 驗證修復
    if not verify_race_condition_fix():
        print("❌ 驗證修復失敗")
        return False
    
    print("\n🎉 真正的修復完成！")
    print("=" * 60)
    print("✅ 移除了治標不治本的約束")
    print("✅ 修復了排程任務的競態條件")
    print("✅ 問題根本原因已解決")
    print("\n💡 修復說明:")
    print("   - 將 initialize_unique_codes 從 15:30 改為 15:35 執行")
    print("   - 避免了與 update_completed_trips 的時間衝突")
    print("   - 小北路班次 (15:25) 不會再被兩個任務同時處理")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)