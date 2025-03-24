import os
import psycopg2
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 獲取資料庫連接資訊
database_url = os.environ.get('DATABASE_URL')

# 輸出檔案名稱
output_file = "database_structure.txt"

def export_database_structure():
    """導出資料庫結構和資料到文字檔"""
    try:
        # 連接到資料庫
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # 打開輸出檔案
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=== 資料庫結構導出 ===\n\n")
            
            # 獲取所有表名
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            
            f.write(f"找到 {len(tables)} 個資料表：\n")
            for table in tables:
                table_name = table[0]
                f.write(f"\n--- 資料表：{table_name} ---\n")
                
                # 獲取表結構
                cursor.execute(f"""
                    SELECT column_name, data_type, character_maximum_length, 
                           is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """)
                columns = cursor.fetchall()
                
                f.write("欄位結構：\n")
                for col in columns:
                    col_name = col[0]
                    data_type = col[1]
                    max_length = col[2]
                    nullable = "可為空" if col[3] == 'YES' else "不可為空"
                    default = col[4] or "無預設值"
                    
                    type_info = f"{data_type}"
                    if max_length:
                        type_info += f"({max_length})"
                    
                    f.write(f"  - {col_name}: {type_info}, {nullable}, 預設值: {default}\n")
                
                # 獲取主鍵
                cursor.execute(f"""
                    SELECT c.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage AS ccu USING (constraint_schema, constraint_name)
                    JOIN information_schema.columns AS c ON c.table_schema = tc.constraint_schema
                      AND tc.table_name = c.table_name AND ccu.column_name = c.column_name
                    WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = '{table_name}'
                """)
                pks = cursor.fetchall()
                
                if pks:
                    f.write("主鍵：\n")
                    for pk in pks:
                        f.write(f"  - {pk[0]}\n")
                
                # 獲取外鍵
                cursor.execute(f"""
                    SELECT
                        tc.constraint_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='{table_name}'
                """)
                fks = cursor.fetchall()
                
                if fks:
                    f.write("外鍵：\n")
                    for fk in fks:
                        f.write(f"  - {fk[1]} 參照 {fk[2]}.{fk[3]}\n")
                
                # 獲取表中的資料（最多10筆）
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 10")
                rows = cursor.fetchall()
                
                if rows:
                    f.write(f"\n資料範例（最多10筆）：\n")
                    # 獲取欄位名稱
                    col_names = [desc[0] for desc in cursor.description]
                    f.write(f"  {', '.join(col_names)}\n")
                    
                    # 輸出資料
                    for row in rows:
                        row_str = []
                        for val in row:
                            if val is None:
                                row_str.append("NULL")
                            else:
                                row_str.append(str(val))
                        f.write(f"  {', '.join(row_str)}\n")
                else:
                    f.write("\n資料表中沒有資料。\n")
            
            f.write("\n=== 導出完成 ===\n")
        
        print(f"資料庫結構已導出到 {output_file}")
        return True
    
    except Exception as e:
        print(f"導出過程中發生錯誤: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    export_database_structure()
