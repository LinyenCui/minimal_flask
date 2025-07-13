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
    """执行数据库迁移，添加trip_type列到trips和completed_trips表并设置正确的值"""
    print("开始执行数据库迁移...")
    
    # 检查是否提供了SQL脚本路径
    sql_script_path = 'migrations/update_trip_types.sql'
    if not os.path.exists(sql_script_path):
        print(f"错误: 找不到SQL脚本 {sql_script_path}")
        return False
    
    try:
        # 读取SQL脚本内容
        with open(sql_script_path, 'r') as f:
            sql_script = f.read()
        
        # 连接到数据库
        print(f"正在连接到数据库: {database_url}")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # 执行SQL脚本
        print(f"正在执行SQL脚本: {sql_script_path}")
        cursor.execute(sql_script)
        
        # 检查trips表中已设置trip_type的记录数量
        cursor.execute("SELECT COUNT(*) FROM trips WHERE trip_type = 'fixed'")
        fixed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trips WHERE trip_type = 'temp'")
        temp_count = cursor.fetchone()[0]
        
        # 检查completed_trips表中已设置trip_type的记录数量
        cursor.execute("SELECT COUNT(*) FROM completed_trips WHERE trip_type = 'fixed'")
        completed_fixed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM completed_trips WHERE trip_type = 'temp'")
        completed_temp_count = cursor.fetchone()[0]
        
        # 提交事务
        conn.commit()
        
        print("数据库迁移结果:")
        print(f"trips表中的固定班次: {fixed_count}")
        print(f"trips表中的临时班次: {temp_count}")
        print(f"completed_trips表中的固定班次: {completed_fixed_count}")
        print(f"completed_trips表中的临时班次: {completed_temp_count}")
        print("数据库迁移成功完成！")
        
    except Exception as e:
        print(f"执行迁移时出错: {e}")
        # 发生错误时回滚事务
        if 'conn' in locals() and conn:
            conn.rollback()
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