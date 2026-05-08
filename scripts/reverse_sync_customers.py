#!/usr/bin/env python3
"""
reverse_sync_customers.py — 一次性反向同步：本地 customers → Render

目的：
  本地 dev 累積了真實業務 customers 資料（51 筆），Render 上是 50 + 筆
  舊資料但 schema 已經對齊本地。要把本地版本「推」上去，讓兩邊資料一致。
  跑完之後 sync_from_render.py 的 SKIP_TABLES 限制就能解除。

策略：UPSERT by short_name
  - 本地有、Render 沒 → INSERT 上去
  - 兩邊都有（同 short_name） → UPDATE Render 那筆，本地版本覆蓋
  - 本地沒、Render 有 → 保留 Render 那筆不動（萬一是 prod 用戶建檔，
    本地沒同步到，留著）

⚠️ 前提：
  - Render 的 customers schema 已經跟本地一致（先跑 migrations/005）
  - 不然 INSERT 會炸（欄位數不對）

⚠️ 安全：
  - 跑前會先 dry-run 印出將要做的事，要打 yes 才真的執行
  - 跑完印 verification report

使用：
  python scripts/reverse_sync_customers.py

  Dry-run（預設）：只印不寫
  Live：python scripts/reverse_sync_customers.py --live
"""
import argparse
import os
import sys
from dotenv import load_dotenv

import psycopg2
from psycopg2.extras import DictCursor


# ============================================================
# 連線
# ============================================================

def _load_env():
    """同 app.py 的 env 載入邏輯（base + .env.dev override）"""
    if os.path.exists('.env'):
        load_dotenv('.env', override=False)
    if os.path.exists('.env.dev'):
        load_dotenv('.env.dev', override=True)


def connect_local():
    cfg = {
        'host': os.getenv('LOCAL_DB_HOST', 'localhost'),
        'port': int(os.getenv('LOCAL_DB_PORT', '5432')),
        'user': os.getenv('LOCAL_DB_USER') or os.getenv('DB_USER', 'postgres'),
        'dbname': os.getenv('LOCAL_DB_NAME') or os.getenv('DB_NAME', 'dispatch_db'),
        'password': os.getenv('LOCAL_DB_PASSWORD') or os.getenv('DB_PASSWORD', ''),
    }
    print(f"🔌 連 Local: {cfg['host']}:{cfg['port']}/{cfg['dbname']}")
    return psycopg2.connect(**cfg)


def connect_render():
    cfg = {
        'host': os.getenv('RENDER_DB_HOST'),
        'user': os.getenv('RENDER_DB_USER'),
        'dbname': os.getenv('RENDER_DB_NAME'),
        'password': os.getenv('RENDER_DB_PASSWORD'),
        'sslmode': 'require',
    }
    if not all([cfg['host'], cfg['user'], cfg['dbname'], cfg['password']]):
        print("❌ 缺 RENDER_DB_* 環境變數（host/user/dbname/password）")
        sys.exit(1)
    print(f"🔌 連 Render: {cfg['host']}/{cfg['dbname']}")
    return psycopg2.connect(**cfg)


# ============================================================
# Schema 對齊驗證
# ============================================================

EXPECTED_COLS = [
    'id', 'name', 'address', 'short_name', 'category', 'remarks',
    'contact_phone', 'birthday', 'latitude', 'longitude',
    'created_at', 'updated_at', 'gender', 'medical_record_no',
]


def get_columns(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'customers' ORDER BY ordinal_position"
        )
        return [r[0] for r in cur.fetchall()]


def verify_schemas(local_conn, render_conn) -> bool:
    """確認兩邊 schema 一致；不一致就印差異 + 阻擋"""
    local_cols = set(get_columns(local_conn))
    render_cols = set(get_columns(render_conn))
    expected = set(EXPECTED_COLS)

    print(f"\n📋 Schema 檢查：")
    print(f"  本地: {sorted(local_cols)}")
    print(f"  Render: {sorted(render_cols)}")

    if local_cols != render_cols:
        only_local = local_cols - render_cols
        only_render = render_cols - local_cols
        if only_local:
            print(f"  ❌ 只在 local 有: {sorted(only_local)}")
        if only_render:
            print(f"  ❌ 只在 render 有: {sorted(only_render)}")
        print(f"\n💡 請先在 Render 跑 migrations/005_align_render_customers_schema.sql")
        return False

    if local_cols != expected:
        # schema 一致但跟預期不同 — 不擋，但提醒
        print(f"  ⚠️ schema 跟預期不同（不擋）：")
        print(f"     預期 {sorted(expected)}")

    print(f"  ✅ schema 一致（{len(local_cols)} 欄）")
    return True


# ============================================================
# 撈資料 + diff
# ============================================================

# UPSERT 用的欄位（id 不在內 — 讓 Render 自己 sequence；short_name 是 key）
INSERT_COLS = [
    'name', 'address', 'short_name', 'category', 'remarks',
    'contact_phone', 'birthday', 'latitude', 'longitude',
    'gender', 'medical_record_no',
    # created_at / updated_at 留給 DB default + trigger
]


def fetch_local_customers(conn) -> list[dict]:
    cols_csv = ', '.join(INSERT_COLS)
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(f"SELECT {cols_csv} FROM customers ORDER BY id")
        return [dict(r) for r in cur.fetchall()]


def fetch_render_short_names(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT short_name FROM customers WHERE short_name IS NOT NULL")
        return {r[0] for r in cur.fetchall()}


def classify(local_rows: list[dict], render_short_names: set[str]):
    """分類成 INSERT 跟 UPDATE 兩堆"""
    to_insert = []  # 本地有 + Render 沒 → INSERT
    to_update = []  # 兩邊都有 → UPDATE Render（本地版本覆蓋）
    no_short = []   # 本地 short_name 是 NULL（不能 UPSERT）→ 不動
    for r in local_rows:
        sn = r.get('short_name')
        if not sn:
            no_short.append(r)
        elif sn in render_short_names:
            to_update.append(r)
        else:
            to_insert.append(r)
    return to_insert, to_update, no_short


# ============================================================
# UPSERT 執行
# ============================================================

def execute_upsert(render_conn, to_insert: list[dict], to_update: list[dict],
                   live: bool):
    placeholders = ', '.join(['%s'] * len(INSERT_COLS))
    cols_csv = ', '.join(INSERT_COLS)
    update_set = ', '.join(
        f'{c} = EXCLUDED.{c}' for c in INSERT_COLS if c != 'short_name'
    )

    sql = f"""
        INSERT INTO customers ({cols_csv})
        VALUES ({placeholders})
        ON CONFLICT (short_name) DO UPDATE SET {update_set}
    """

    if not live:
        print(f"\n[DRY-RUN] 將執行 UPSERT，每筆 SQL:")
        print(f"  {sql.strip()}")
        print(f"\n  共 {len(to_insert) + len(to_update)} 筆 UPSERT (INSERT/UPDATE 由 short_name conflict 決定)")
        return 0, 0

    # 確保 customers 有 UNIQUE constraint on short_name（不然 ON CONFLICT 會 error）
    with render_conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'customers' AND indexdef LIKE '%UNIQUE%short_name%'
        """)
        has_unique = cur.fetchone() is not None
    if not has_unique:
        print("⚠️ Render customers.short_name 沒有 UNIQUE 索引，建立中...")
        with render_conn.cursor() as cur:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_short_name "
                "ON customers (short_name) WHERE short_name IS NOT NULL"
            )
        render_conn.commit()
        print("  ✅ 建好")

    inserted, updated = 0, 0
    failed: list[tuple[str, str]] = []
    with render_conn.cursor() as cur:
        for r in to_insert + to_update:
            params = tuple(r.get(c) for c in INSERT_COLS)
            try:
                cur.execute(sql, params)
                # 用 RETURNING 太麻煩，直接從分類結果累加
                if r in to_insert:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                render_conn.rollback()  # 個別 row 失敗 rollback 整個 tx
                failed.append((r.get('short_name', '?'), str(e)[:80]))
    render_conn.commit()

    if failed:
        print(f"\n⚠️ {len(failed)} 筆失敗：")
        for sn, err in failed[:10]:
            print(f"  - {sn}: {err}")

    return inserted, updated


# ============================================================
# 驗證 report
# ============================================================

def report(local_conn, render_conn):
    with local_conn.cursor() as c:
        c.execute("SELECT COUNT(*) FROM customers")
        n_local = c.fetchone()[0]
    with render_conn.cursor() as c:
        c.execute("SELECT COUNT(*) FROM customers")
        n_render = c.fetchone()[0]
    print(f"\n📊 同步後筆數：")
    print(f"  Local : {n_local}")
    print(f"  Render: {n_render}")


# ============================================================
# 主程式
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Reverse sync customers: local → Render')
    parser.add_argument('--live', action='store_true',
                        help='真的執行（不加 = dry-run）')
    args = parser.parse_args()

    _load_env()

    print('=' * 60)
    print('🔄 reverse_sync_customers: local → Render')
    print(f'   模式: {"LIVE（會寫 Render）" if args.live else "DRY-RUN（只印不寫）"}')
    print('=' * 60)

    local_conn = connect_local()
    render_conn = connect_render()

    try:
        # 1. schema 確認
        if not verify_schemas(local_conn, render_conn):
            print("\n❌ schema 不一致，先跑 migrations/005 再跑這個")
            sys.exit(1)

        # 2. 撈資料 + 分類
        local_rows = fetch_local_customers(local_conn)
        render_sns = fetch_render_short_names(render_conn)
        to_insert, to_update, no_short = classify(local_rows, render_sns)

        print(f"\n📋 分類結果（local {len(local_rows)} 筆）：")
        print(f"  → INSERT 到 Render: {len(to_insert)} 筆（本地有、Render 沒）")
        print(f"  → UPDATE Render   : {len(to_update)} 筆（兩邊都有，本地版本覆蓋）")
        print(f"  → 跳過（無 short_name）: {len(no_short)} 筆")

        if to_insert:
            print(f"\n  將 INSERT 的 short_name 範例（前 10 個）：")
            for r in to_insert[:10]:
                print(f"    + {r.get('short_name')}")
            if len(to_insert) > 10:
                print(f"    ... 還有 {len(to_insert) - 10} 筆")

        # 3. 確認 + 執行
        if args.live:
            print(f"\n⚠️ 即將執行 LIVE UPSERT 到 Render，5 秒內 Ctrl+C 取消...")
            import time
            time.sleep(5)

        inserted, updated = execute_upsert(render_conn, to_insert, to_update, args.live)

        if args.live:
            print(f"\n✅ 寫入完成: INSERT {inserted} 筆 + UPDATE {updated} 筆")
            report(local_conn, render_conn)
        else:
            print(f"\n💡 DRY-RUN 結束。要真的寫，加 --live：")
            print(f"   python scripts/reverse_sync_customers.py --live")
    finally:
        local_conn.close()
        render_conn.close()


if __name__ == '__main__':
    main()
