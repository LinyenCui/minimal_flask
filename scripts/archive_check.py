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


def build_report(cutoff: str) -> tuple:
    """回傳 (報告文字, 是否可安全刪除)。給 CLI 與 LINE 指令共用。"""
    lines = []
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

        lines.append("📦 歸檔檢查（Render → 本地備份完整性）")
        lines.append(f"Render：{len(render_ids)} 筆　{r_range[0]} ~ {r_range[1]}")
        lines.append(f"本地　：{len(local_ids)} 筆　{l_range[0]} ~ {l_range[1]}")
        lines.append(f"本地獨有（已歸檔歷史）：{len(local_ids - render_ids)} 筆")
        lines.append("")

        if missing:
            lines.append(f"❌ 本地還缺 {len(missing)} 筆 — 請先打「資料庫同步」再刪！")
            lines.append(f"缺漏範例：{', '.join(sorted(missing)[:5])}")
            return '\n'.join(lines), False

        lines.append("✅ Render 的資料本地都有備份，可安全刪除舊資料")
        lines.append("")
        lines.append(f"📅 {cutoff} 之前的 Render 資料：{deletable} 筆")
        if deletable:
            lines.append("")
            lines.append("── 貼進 Render Adminer 執行 ──")
            lines.append(f"DELETE FROM completed_trips WHERE date < '{cutoff}';")
            lines.append("（刪完本地不受影響，同步只增不減）")
        else:
            lines.append("（該界線前無資料可刪）")
        return '\n'.join(lines), True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', help='刪除界線 YYYY-MM-DD（預設：今天往前 60 天）')
    args = ap.parse_args()
    cutoff = args.before or (date.today() - timedelta(days=60)).isoformat()
    report, ok = build_report(cutoff)
    print(report)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
