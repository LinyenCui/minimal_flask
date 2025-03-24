import os
import sys
import psycopg2
from dotenv import load_dotenv
from models import init_db

# 加载环境变量
load_dotenv()

def create_database():
    """创建PostgreSQL数据库"""
    # 获取数据库URL
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dispatch_system")
    
    # 解析数据库URL
    parts = database_url.split("/")
    db_name = parts[-1]
    connection_string = "/".join(parts[:-1]) + "/postgres"  # 连接到默认的postgres数据库
    
    print(f"尝试创建数据库: {db_name}")
    
    try:
        # 连接到默认数据库
        conn = psycopg2.connect(connection_string)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 检查数据库是否已存在
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
        exists = cursor.fetchone()
        
        if not exists:
            # 创建数据库
            cursor.execute(f"CREATE DATABASE {db_name}")
            print(f"数据库 {db_name} 创建成功")
        else:
            print(f"数据库 {db_name} 已存在")
        
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"创建数据库时出错: {e}")
        return False

if __name__ == "__main__":
    # 创建数据库
    if create_database():
        # 初始化表和数据
        try:
            engine = init_db()
            print("数据库表和初始数据创建成功")
        except Exception as e:
            print(f"初始化数据库表时出错: {e}")
            sys.exit(1)
    else:
        print("无法创建数据库，请检查PostgreSQL连接")
        sys.exit(1) 