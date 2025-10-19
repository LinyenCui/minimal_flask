#!/usr/bin/env python3
"""
修復重複班次問題的腳本
1. 清理現有的重複記錄
2. 添加資料庫唯一約束
3. 修改程式碼使用原子性插入
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

def clean_duplicate_records():
    """清理重複記錄，保留較早的記錄"""
    print("\n🧹 步驟1: 清理重複記錄")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor(cursor_factory=DictCursor) as cur:
            # 找出所有重複的 unique_code
            print("🔍 查找重複的 unique_code...")
            
            duplicate_query = """
            SELECT unique_code, COUNT(*) as count
            FROM completed_trips 
            WHERE unique_code IS NOT NULL
            GROUP BY unique_code 
            HAVING COUNT(*) > 1
            ORDER BY unique_code
            """
            
            cur.execute(duplicate_query)
            duplicates = cur.fetchall()
            
            print(f"找到 {len(duplicates)} 個重複的 unique_code:")
            for dup in duplicates:
                print(f"  - {dup['unique_code']}: {dup['count']} 筆記錄")
            
            # 對每個重複的 unique_code，保留最早的記錄，刪除其他
            total_deleted = 0
            for dup in duplicates:
                unique_code = dup['unique_code']
                
                # 找出該 unique_code 的所有記錄，按 created_at 排序
                records_query = """
                SELECT id, created_at
                FROM completed_trips 
                WHERE unique_code = %s
                ORDER BY created_at ASC
                """
                
                cur.execute(records_query, (unique_code,))
                records = cur.fetchall()
                
                if len(records) > 1:
                    # 保留第一筆（最早的），刪除其他
                    keep_id = records[0]['id']
                    delete_ids = [r['id'] for r in records[1:]]
                    
                    print(f"  保留 ID {keep_id}，刪除 IDs: {delete_ids}")
                    
                    # 刪除重複記錄
                    delete_query = "DELETE FROM completed_trips WHERE id = ANY(%s)"
                    cur.execute(delete_query, (delete_ids,))
                    deleted_count = cur.rowcount
                    total_deleted += deleted_count
                    
                    print(f"  已刪除 {deleted_count} 筆重複記錄")
            
            # 提交事務
            local_conn.commit()
            print(f"\n✅ 總共刪除了 {total_deleted} 筆重複記錄")
            
            return True
            
    except Exception as e:
        print(f"❌ 清理重複記錄時發生錯誤: {e}", file=sys.stderr)
        local_conn.rollback()
        return False
    finally:
        if local_conn:
            local_conn.close()

def add_unique_constraint():
    """添加 unique_code 的唯一約束"""
    print("\n🔒 步驟2: 添加唯一約束")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor() as cur:
            # 檢查是否已經有唯一約束
            check_constraint_query = """
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'completed_trips' 
              AND constraint_type = 'UNIQUE'
              AND constraint_name LIKE '%unique_code%'
            """
            
            cur.execute(check_constraint_query)
            existing_constraints = cur.fetchall()
            
            if existing_constraints:
                print("✅ unique_code 唯一約束已存在")
                return True
            
            # 添加唯一約束
            print("🔧 添加 unique_code 唯一約束...")
            add_constraint_query = """
            ALTER TABLE completed_trips 
            ADD CONSTRAINT unique_completed_trip_code UNIQUE (unique_code)
            """
            
            cur.execute(add_constraint_query)
            local_conn.commit()
            print("✅ 成功添加 unique_code 唯一約束")
            
            return True
            
    except Exception as e:
        print(f"❌ 添加唯一約束時發生錯誤: {e}", file=sys.stderr)
        local_conn.rollback()
        return False
    finally:
        if local_conn:
            local_conn.close()

def verify_fix():
    """驗證修復結果"""
    print("\n✅ 步驟3: 驗證修復結果")
    print("-" * 50)
    
    local_conn = get_db_connection(LOCAL_DB_CONFIG, "Local")
    if not local_conn:
        return False
    
    try:
        with local_conn.cursor(cursor_factory=DictCursor) as cur:
            # 檢查是否還有重複記錄
            duplicate_check_query = """
            SELECT unique_code, COUNT(*) as count
            FROM completed_trips 
            WHERE unique_code IS NOT NULL
            GROUP BY unique_code 
            HAVING COUNT(*) > 1
            """
            
            cur.execute(duplicate_check_query)
            remaining_duplicates = cur.fetchall()
            
            if remaining_duplicates:
                print(f"❌ 仍有 {len(remaining_duplicates)} 個重複的 unique_code:")
                for dup in remaining_duplicates:
                    print(f"  - {dup['unique_code']}: {dup['count']} 筆記錄")
                return False
            else:
                print("✅ 沒有發現重複記錄")
            
            # 檢查約束是否成功添加
            constraint_check_query = """
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'completed_trips' 
              AND constraint_type = 'UNIQUE'
              AND constraint_name LIKE '%unique_code%'
            """
            
            cur.execute(constraint_check_query)
            constraints = cur.fetchall()
            
            if constraints:
                print("✅ unique_code 唯一約束已生效")
                return True
            else:
                print("❌ unique_code 唯一約束未找到")
                return False
                
    except Exception as e:
        print(f"❌ 驗證修復結果時發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        if local_conn:
            local_conn.close()

def main():
    """主函數"""
    print("🚀 開始修復重複班次問題")
    print("=" * 60)
    
    # 步驟1: 清理重複記錄
    if not clean_duplicate_records():
        print("❌ 清理重複記錄失敗")
        return False
    
    # 步驟2: 添加唯一約束
    if not add_unique_constraint():
        print("❌ 添加唯一約束失敗")
        return False
    
    # 步驟3: 驗證修復結果
    if not verify_fix():
        print("❌ 驗證修復結果失敗")
        return False
    
    print("\n🎉 修復完成！")
    print("=" * 60)
    print("✅ 重複記錄已清理")
    print("✅ 唯一約束已添加")
    print("✅ 問題已解決")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)