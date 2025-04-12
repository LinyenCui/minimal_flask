#!/usr/bin/env python
import os
import sys
import psycopg2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取数据库连接URL
database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dispatch_system")

def run_migration():
    """执行数据库迁移，添加trip_type列到trips和completed_trips表"""
    print("开始执行数据库迁移...")
    
    try:
        # 连接到数据库
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # 检查trips表中是否已存在trip_type列
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trips' AND column_name = 'trip_type'
        """)
        
        trips_has_column = cursor.fetchone() is not None
        
        # 检查completed_trips表中是否已存在trip_type列
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'completed_trips' AND column_name = 'trip_type'
        """)
        
        completed_trips_has_column = cursor.fetchone() is not None
        
        # 如果列不存在，则添加
        if not trips_has_column:
            print("在trips表中添加trip_type列...")
            cursor.execute("ALTER TABLE trips ADD COLUMN trip_type VARCHAR(20) DEFAULT 'fixed'")
            
            # 更新现有数据
            print("更新trips表中的现有数据...")
            cursor.execute("UPDATE trips SET trip_type = 'fixed' WHERE fixed_trip_id IS NOT NULL")
            cursor.execute("UPDATE trips SET trip_type = 'temp' WHERE fixed_trip_id IS NULL")
        else:
            print("trips表中已存在trip_type列，跳过。")
        
        if not completed_trips_has_column:
            print("在completed_trips表中添加trip_type列...")
            cursor.execute("ALTER TABLE completed_trips ADD COLUMN trip_type VARCHAR(20) DEFAULT 'fixed'")
        else:
            print("completed_trips表中已存在trip_type列，跳过。")
        
        # 提交事务
        conn.commit()
        print("数据库迁移成功完成！")
        
    except Exception as e:
        # 发生错误时回滚事务
        if 'conn' in locals() and conn:
            conn.rollback()
        print(f"执行迁移时出错: {e}")
        return False
    finally:
        # 关闭数据库连接
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
    
    return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1) 