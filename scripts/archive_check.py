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


def assert_not_on_render():
    """確保只在本機執行 — prod 上「本地庫」就是 Render 自己，
    備份比對會自己跟自己比而永遠通過，purge 等於無備份刪生產資料。
    """
    if os.environ.get('RENDER'):
        raise RuntimeError(
            '歸檔功能只能在本機執行（Render 上的「本地庫」就是自己，'
            '備份檢查沒有意義）')
    local = re.sub(r'^postgresql\+\w+://', 'postgresql://',
                   os.environ.get('DATABASE_URL', ''))
    rhost = os.environ.get('RENDER_DB_HOST', '')
    if rhost and rhost in local:
        raise RuntimeError('本地 DATABASE_URL 指向 Render — 拒絕執行歸檔功能')


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
    assert_not_on_render()
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
            lines.append(f"　清理後剩餘 {len(render_ids) - deletable} 筆會重編為 "
                         f"#1〜#{len(render_ids) - deletable}（序號歸位）")
            lines.append("")
            lines.append("用「歸檔清理」指令執行（會一併重編）；或手動貼進 Adminer 只刪不重編：")
            lines.append(f"DELETE FROM completed_trips WHERE date < '{cutoff}';")
            lines.append("（刪完本地不受影響，本地 id 獨立、歷史照舊）")
        else:
            lines.append("（該界線前無資料可刪）")
        return '\n'.join(lines), True


# 保護線：早於今天 N 天的資料才准刪（防手滑刪到近期）
PURGE_MIN_AGE_DAYS = 30

# 重編時先把所有 id 抬到這個位移之上，再重編成 1..N。
# 單段 UPDATE 會在途中撞到還沒改的舊 id（第一次做時 MIN=205 < COUNT=3928）。
RENUMBER_OFFSET = 1_000_000


def renumber_completed_trips(cur, *, set_sequence: bool = True) -> tuple:
    """把 completed_trips 重編成 #1..#N（按 date, id 排），序號設到 N。

    用戶需求（2026-09-20）：過去態 id 大約半年歸一次。掛在「歸檔清理」上 ——
    每次清完 Render 舊資料就順手重編，半年清一次 = 半年歸一次，
    不必另外一個指令或排程。每月 ~615 筆 → 半年 ~3,700 筆 → 永遠 4 碼。

    為什麼能放心重編（已逐一驗過）：
      · id 只是流水號，unique_code 才是身份 —— 同步、鏡射、歸檔比對全用 unique_code，
        3,928 筆沒有一筆缺 code
      · 同步刷新的欄位清單（sync_from_render._REFRESH_COLS）不含 id；
        補漏新增明講「不沿用 Render 的 id」→ 本地的 id 不受影響，歷史照舊
      · 沒有任何 FK 指向 completed_trips
    代價：剩餘班次的 #編號全變，舊訊息裡的 #N 作廢（確認訊息會警告）；
    audit_log.target_id 對這些列過時，但 before_state 存了整列內容仍可對回。

    兩段式：先全部 +RENUMBER_OFFSET，再重編 —— 新號 1..N 永遠小於位移後的舊號，
    UPDATE 途中不會撞 PK。

    Args:
        cur: 已在 transaction 內的 cursor（呼叫端負責 commit）
        set_sequence: 測試時給 False —— setval 不受 rollback 保護
    Returns:
        (N, old_min, old_max)；表空回 (0, None, None)
    """
    cur.execute("SELECT COUNT(*), MIN(id), MAX(id) FROM completed_trips")
    n, old_min, old_max = cur.fetchone()
    if not n:
        if set_sequence:
            cur.execute("SELECT setval(pg_get_serial_sequence('completed_trips','id'), 1, false)")
        return 0, None, None
    cur.execute("UPDATE completed_trips SET id = id + %s", (RENUMBER_OFFSET,))
    cur.execute("""
        UPDATE completed_trips c
        SET id = m.rn
        FROM (SELECT id, ROW_NUMBER() OVER (ORDER BY date, id) AS rn
              FROM completed_trips) m
        WHERE c.id = m.id
    """)
    if set_sequence:
        cur.execute("SELECT setval(pg_get_serial_sequence('completed_trips','id'), %s, true)", (n,))
    return int(n), int(old_min), int(old_max)


def purge_render(cutoff: str) -> tuple:
    """刪除 Render 上 date < cutoff 的 completed_trips，並把剩餘的重編成 #1..#N。
    回 (訊息, 刪除筆數)。

    ⚠️ 這是唯一會「寫」Render 的地方，故層層設防：
      1. 先跑 build_report — 本地備份不完整一律拒絕
      2. cutoff 必須早於今天 PURGE_MIN_AGE_DAYS 天（防刪到近期資料）
      3. SQL 是寫死的參數化語句（非 AI 生成、非字串拼接）
      4. 刪除筆數先查後刪，回報實際影響列數
      5. 刪除與重編在**同一個 transaction**：重編失敗則刪除一併回滾
    """
    assert_not_on_render()   # 防呆 0：prod 一律拒絕

    # 防呆 1：日期格式與保護線
    try:
        cut_d = date.fromisoformat(cutoff)
    except ValueError:
        return f"❌ 日期格式錯誤：{cutoff}（要 YYYY-MM-DD）", 0
    limit_d = date.today() - timedelta(days=PURGE_MIN_AGE_DAYS)
    if cut_d > limit_d:
        return (f"❌ 界線 {cutoff} 太近了 — 只准刪 {limit_d} 之前的資料"
                f"（保護線：{PURGE_MIN_AGE_DAYS} 天）"), 0

    # 防呆 2：本地備份必須完整
    report, ok = build_report(cutoff)
    if not ok:
        return f"❌ 備份不完整，拒絕刪除\n\n{report}", 0

    # 執行刪除 + 重編（同一 transaction；可寫連線；語句寫死、日期參數綁定）
    with _render_conn(read_only=False) as rconn:
        cur = rconn.cursor()
        cur.execute("SELECT COUNT(*) FROM completed_trips WHERE date < %s", (cutoff,))
        n = cur.fetchone()[0]
        if not n:
            return f"ℹ️ {cutoff} 之前沒有資料可刪", 0
        cur.execute("DELETE FROM completed_trips WHERE date < %s", (cutoff,))
        deleted = cur.rowcount
        remaining, old_min, old_max = renumber_completed_trips(cur)
        rconn.commit()

    renum = (f"　剩餘 {remaining} 筆已重編為 #1〜#{remaining}"
             f"（原 #{old_min}〜#{old_max}），序號歸位\n"
             f"　⚠️ 舊訊息裡的 #編號已作廢，操作前請重新查詢"
             if remaining else "　Render 已清空，序號歸 1")
    return (f"🧹 已清理 Render 舊資料\n"
            f"　刪除：{deleted} 筆（{cutoff} 之前）\n"
            f"{renum}\n"
            f"　本地備份不受影響，歷史查詢照常"), deleted


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
