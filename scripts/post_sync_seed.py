#!/usr/bin/env python3
"""
post_sync_seed.py — 同步後補 seed 測試資料

目的：
  sync_from_render.py 會 DELETE + INSERT 同步 customers，
  但只同步 Render 既有欄位，且我們的 5 筆範例患者會被清掉。
  此腳本在 sync 後跑，補回本地測試資料。

特性：
  - 冪等（idempotent）：以 medical_record_no 為 UNIQUE key，重跑不會重複
  - 獨立可跑：不依賴 Flask app
  - 自動修序列（防止 INSERT 撞 PK 衝突）

⚠️ 2026-05-08：drop national_id / insurance_type，UPSERT key 改用
   medical_record_no（5 筆 seed 都有，且唯一）

使用：
  python scripts/post_sync_seed.py

  或鏈結在 sync 後：
  python scripts/sync_from_render.py && python scripts/post_sync_seed.py
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 連線設定
# ============================================================

LOCAL_DB_CONFIG = {
    "host": os.getenv('LOCAL_DB_HOST', 'localhost'),
    "port": int(os.getenv('LOCAL_DB_PORT', '5432')),
    "user": os.getenv('LOCAL_DB_USER') or os.getenv('DB_USER', 'postgres'),
    "dbname": os.getenv('LOCAL_DB_NAME') or os.getenv('DB_NAME', 'dispatch_db'),
    "password": os.getenv('LOCAL_DB_PASSWORD') or os.getenv('DB_PASSWORD', ''),
}

# 如果 .env 用 DATABASE_URL（而非分開的 DB_* 變數），改用這個
DATABASE_URL = os.getenv('DATABASE_URL')


# ============================================================
# Seed 資料：謝智超達恩診所 5 筆範例患者
# ============================================================

SEED_PATIENTS = [
    {
        'name': '黃陳玉盆', 'short_name': '黃陳玉盆', 'address': '(待補)',
        'category': '診所', 'remarks': '範例：5/2 處方箋',
        'birthday': '1951-08-23', 'gender': 'F',
        'medical_record_no': '001026',
    },
    {
        'name': '林佳瑋', 'short_name': '林佳瑋', 'address': '(待補)',
        'category': '診所', 'remarks': '範例：4/28 處方箋',
        'birthday': '1986-09-26', 'gender': 'M',
        'medical_record_no': '001676',
    },
    {
        'name': '方怡雁', 'short_name': '方怡雁', 'address': '(待補)',
        'category': '診所', 'remarks': '範例：4/28 處方箋',
        'birthday': '1992-08-01', 'gender': 'F',
        'medical_record_no': '001677',
    },
    {
        'name': '謝家成', 'short_name': '謝家成', 'address': '(待補)',
        'category': '診所', 'remarks': '範例：4/28 處方箋',
        'birthday': '1937-02-17', 'gender': 'M',
        'medical_record_no': '000133',
    },
    {
        'name': '曾紀淑美', 'short_name': '曾紀淑美', 'address': '(待補)',
        'category': '診所', 'remarks': '範例：5/1 處方箋',
        'birthday': '1956-02-13', 'gender': 'F',
        'medical_record_no': '002034',
    },
]


# ============================================================
# 工具函數
# ============================================================

def _normalize_db_url(url: str) -> str:
    """psycopg2 不認 SQLAlchemy 的 driver 後綴，去掉 +xxx"""
    if url.startswith('postgresql+'):
        # postgresql+psycopg://... → postgresql://...
        return 'postgresql://' + url.split('://', 1)[1]
    if url.startswith('postgres+'):
        return 'postgres://' + url.split('://', 1)[1]
    return url


def connect_local():
    """連到本地 DB（優先用 DATABASE_URL）"""
    if DATABASE_URL:
        return psycopg2.connect(_normalize_db_url(DATABASE_URL))
    return psycopg2.connect(**LOCAL_DB_CONFIG)


def fix_customers_sequence(conn):
    """確保 customers id sequence >= MAX(id)"""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_get_serial_sequence('customers', 'id');")
        seq_name = cur.fetchone()[0]
        if not seq_name:
            return None
        cur.execute(f"SELECT last_value FROM {seq_name};")
        last_val = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM customers;")
        max_id = cur.fetchone()[0]
        if last_val < max_id:
            cur.execute(f"SELECT setval(%s, %s);", (seq_name, max_id))
            conn.commit()
            return f"sequence {seq_name}: {last_val} → {max_id}"
        return None


def upsert_patients(conn):
    """以 medical_record_no 為 key，UPSERT 範例患者"""
    inserted, updated = 0, 0
    with conn.cursor() as cur:
        for p in SEED_PATIENTS:
            cur.execute(
                "SELECT id FROM customers WHERE medical_record_no = %s",
                (p['medical_record_no'],)
            )
            existing = cur.fetchone()
            if existing:
                # UPDATE（保留 id，刷新欄位）
                cur.execute(
                    """
                    UPDATE customers SET
                        name = %s, short_name = %s, address = %s,
                        category = %s, remarks = %s,
                        birthday = %s, gender = %s
                    WHERE medical_record_no = %s
                    """,
                    (
                        p['name'], p['short_name'], p['address'],
                        p['category'], p['remarks'],
                        p['birthday'], p['gender'],
                        p['medical_record_no'],
                    )
                )
                updated += 1
            else:
                # INSERT
                cur.execute(
                    """
                    INSERT INTO customers (
                        name, short_name, address, category, remarks,
                        birthday, gender, medical_record_no
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        p['name'], p['short_name'], p['address'],
                        p['category'], p['remarks'],
                        p['birthday'], p['gender'],
                        p['medical_record_no'],
                    )
                )
                inserted += 1
    conn.commit()
    return inserted, updated


def schema_check(conn):
    """檢查 migration 必要欄位是否齊全（drop national_id / insurance_type 後）"""
    required_cols = [
        'birthday', 'latitude', 'longitude', 'created_at', 'updated_at',
        'gender', 'medical_record_no',
    ]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'customers'
            """
        )
        existing = {r[0] for r in cur.fetchall()}
    missing = [c for c in required_cols if c not in existing]
    return missing


# ============================================================
# 主程式
# ============================================================

def main():
    print('=' * 60)
    print('🌱 post_sync_seed: 補 customers 測試資料')
    print('=' * 60)

    try:
        conn = connect_local()
    except Exception as e:
        print(f'❌ 連線失敗: {e}')
        sys.exit(1)

    try:
        # 1. schema 檢查
        missing = schema_check(conn)
        if missing:
            print(f'❌ schema 不完整，缺少欄位: {missing}')
            print(f'   請先執行 migrations/001_*.sql 與 002_*.sql')
            sys.exit(1)
        print('✅ schema 檢查通過（migration 001 + 002 已套用）')

        # 2. 修序列
        seq_msg = fix_customers_sequence(conn)
        if seq_msg:
            print(f'🔧 修正序列: {seq_msg}')
        else:
            print('✅ 序列已正常')

        # 3. UPSERT 患者
        inserted, updated = upsert_patients(conn)
        print(f'\n📊 範例患者: 新增 {inserted} 筆、更新 {updated} 筆')

        # 4. 最終驗證
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, short_name, name, gender, birthday, medical_record_no "
                "FROM customers WHERE medical_record_no IS NOT NULL "
                "ORDER BY medical_record_no"
            )
            for r in cur.fetchall():
                print(f'  #{r[0]:3d}  簡稱:{r[1]:8s}  姓名:{r[2]:8s}  '
                      f'{r[3]}  生日:{r[4]}  病歷:{r[5]}')

        print('\n✅ post_sync_seed 完成')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
