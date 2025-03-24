import psycopg2
import os

# 資料庫連接參數
db_params = {
    'dbname': 'dispatch_db',
    'user': 'postgres',
    'password': '',  # 如果沒有密碼，保留為空字符串
    'host': 'localhost',
    'port': '5432'
}

# 輸出文件名
output_file = 'db_structure.txt'

# 連接到資料庫
conn = psycopg2.connect(**db_params)
cursor = conn.cursor()

# 打開輸出文件
with open(output_file, 'w') as f:
    # 獲取所有表名
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    f.write("# 資料庫結構\n\n")
    f.write(f"資料庫名稱: {db_params['dbname']}\n\n")
    
    # 遍歷每個表
    for table in tables:
        table_name = table[0]
        f.write(f"## 表名: {table_name}\n\n")
        
        # 獲取表的列信息
        cursor.execute(f"""
            SELECT 
                column_name, 
                data_type, 
                character_maximum_length,
                is_nullable,
                column_default
            FROM 
                information_schema.columns 
            WHERE 
                table_name = '{table_name}'
            ORDER BY 
                ordinal_position
        """)
        columns = cursor.fetchall()
        
        f.write("| 列名 | 數據類型 | 長度 | 可為空 | 默認值 |\n")
        f.write("|------|----------|------|--------|--------|\n")
        
        for column in columns:
            column_name = column[0]
            data_type = column[1]
            max_length = str(column[2]) if column[2] is not None else "-"
            is_nullable = "是" if column[3] == "YES" else "否"
            default_value = str(column[4]) if column[4] is not None else "-"
            
            f.write(f"| {column_name} | {data_type} | {max_length} | {is_nullable} | {default_value} |\n")
        
        # 獲取主鍵信息
        cursor.execute(f"""
            SELECT 
                kcu.column_name
            FROM 
                information_schema.table_constraints tc
            JOIN 
                information_schema.key_column_usage kcu
            ON 
                tc.constraint_name = kcu.constraint_name
            WHERE 
                tc.table_name = '{table_name}'
                AND tc.constraint_type = 'PRIMARY KEY'
        """)
        primary_keys = cursor.fetchall()
        
        if primary_keys:
            f.write("\n**主鍵:** ")
            pk_columns = [pk[0] for pk in primary_keys]
            f.write(", ".join(pk_columns))
            f.write("\n")
        
        # 獲取外鍵信息
        cursor.execute(f"""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM
                information_schema.table_constraints AS tc
            JOIN
                information_schema.key_column_usage AS kcu
            ON
                tc.constraint_name = kcu.constraint_name
            JOIN
                information_schema.constraint_column_usage AS ccu
            ON
                ccu.constraint_name = tc.constraint_name
            WHERE
                tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = '{table_name}'
        """)
        foreign_keys = cursor.fetchall()
        
        if foreign_keys:
            f.write("\n**外鍵:**\n")
            for fk in foreign_keys:
                column_name = fk[0]
                foreign_table = fk[1]
                foreign_column = fk[2]
                f.write(f"- {column_name} -> {foreign_table}.{foreign_column}\n")
        
        f.write("\n\n")

# 關閉連接
cursor.close()
conn.close()

print(f"資料庫結構已導出到 {output_file}")
