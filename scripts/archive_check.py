#!/usr/bin/env python3
"""歸檔檢查 — 刪 Render 的 completed_trips 前，確認本地備份完整。

用戶流程（2026-07-27 定調）：Render 是唯一真相、本地是歷史累積備份；
定期把 Render 的舊 completed_trips 刪掉節省空間，刪之前用這支確認
「Render 有的本地都有」，並產生可直接貼進 Adminer 的刪除 SQL。

用法：
    python scripts/archive_check.py            # 檢查 + 建議
    python scripts/archive_check.py --before 2026-06-01   # 指定刪除界線
"""
import os
import re
import sys
import argparse
from datetime import date, timedelta

import psycopg2
from dotenv import load_dotenv

load_dotenv()
load_dotenv('.env.dev', override=True)


def _local_conn():
    dsn = re.sub(r'^postgresql\+\w+://', 'postgresql://', os.environ['DATABASE_URL'])
    return psycopg2.connect(dsn)


def _render_conn(read_only=True):
    opts = '-c default_transaction_read_only=on' if read_only else None
    return psycopg2.connect(
        host=os.environ['RENDER_DB_HOST'], user=os.environ['RENDER_DB_USER'],
        dbname=os.environ['RENDER_DB_NAME'], password=os.environ['RENDER_DB_PASSWORD'],
        port=os.environ.get('RENDER_DB_PORT', 5432), sslmode='require',
        options=opts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', help='刪除界線 YYYY-MM-DD（預設：今天往前 60 天）')
    args = ap.parse_args()

    cutoff = args.before or (date.today() - timedelta(days=60)).isoformat()

    with _local_conn() as lconn, _render_conn() as rconn:
        lcur, rcur = lconn.cursor(), rconn.cursor()
        # 比對鍵：unique_code（業務唯一鍵）— 本地排程也會產生 completed_trips，
        # 同一趟兩邊 id 不同，用 id 比對會誤報缺漏
        rcur.execute("SELECT COALESCE(unique_code, 'id:' || id) FROM completed_trips")
        render_keys = {r[0] for r in rcur.fetchall()}
        lcur.execute("SELECT COALESCE(unique_code, 'id:' || id) FROM completed_trips")
        local_keys = {r[0] for r in lcur.fetchall()}
        render_ids, local_ids = render_keys, local_keys

        missing = render_keys - local_keys
        rcur.execute("SELECT COUNT(*) FROM completed_trips WHERE date < %s", (cutoff,))
        deletable = rcur.fetchone()[0]
        rcur.execute("SELECT MIN(date), MAX(date) FROM completed_trips")
        r_range = rcur.fetchone()
        lcur.execute("SELECT MIN(date), MAX(date) FROM completed_trips")
        l_range = lcur.fetchone()

        print("=" * 56)
        print("📦 歸檔檢查（Render → 本地備份完整性）")
        print("=" * 56)
        print(f"Render : {len(render_ids):>5} 筆  {r_range[0]} ~ {r_range[1]}")
        print(f"本地   : {len(local_ids):>5} 筆  {l_range[0]} ~ {l_range[1]}")
        print(f"本地獨有（已歸檔的歷史）: {len(local_ids - render_ids)} 筆")
        print()

        if missing:
            print(f"❌ 本地還缺 {len(missing)} 筆 — 請先在 LINE 打「資料庫同步」再刪！")
            print(f"   缺漏 unique_code 範例: {sorted(missing)[:10]}")
            return 1

        print("✅ Render 的資料本地都有備份，可安全刪除舊資料")
        print()
        print(f"📅 界線 {cutoff} 之前的 Render 資料：{deletable} 筆")
        if deletable:
            print()
            print("── 貼進 Render Adminer 執行（刪除前建議先跑一次上面的同步）──")
            print(f"DELETE FROM completed_trips WHERE date < '{cutoff}';")
            print("── 刪完後本地資料不受影響（同步只增不減）──")
        else:
            print("（該界線前無資料可刪）")
        return 0


if __name__ == '__main__':
    sys.exit(main())
