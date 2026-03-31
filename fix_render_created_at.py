import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

RENDER_DB_CONFIG = {
    "host": os.getenv('RENDER_DB_HOST'),
    "user": os.getenv('RENDER_DB_USER'),
    "dbname": os.getenv('RENDER_DB_NAME'),
    "password": os.getenv('RENDER_DB_PASSWORD'),
    "sslmode": 'require'
}

def main():
    try:
        conn = psycopg2.connect(**RENDER_DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("SELECT id, created_at, unique_code FROM completed_trips WHERE id = 316;")
        row = cur.fetchone()
        print(f"Row 316: {row}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
