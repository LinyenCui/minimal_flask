"""
測試「歸檔清理」順手把 completed_trips 重編為 #1..#N

背景（2026-09-20 用戶：「過去態的 id 大概半年左右就能重置」）：
    不另開指令 —— 掛在既有的「歸檔清理」上：刪完 Render 舊資料後，
    剩下的列按 (date, id) 重編成 1..N、序號設到 N。半年清一次 = 半年歸一次。
    每月 ~615 筆 → 半年 ~3,700 筆 → 永遠 4 碼。

    本地不受影響（同步／鏡射／歸檔比對全靠 unique_code，刷新欄位不含 id，
    補漏不沿用 Render 的 id）—— 所以這裡只測重編本身與它有沒有接進 purge_render。

    T1  重編：(date, id) 排序、新號連續、unique_code 對得回去
    T2  兩段式真的擋住「MIN < COUNT」的自撞（第一次做時 MIN=205 < COUNT=3928）
    T3  表空的分支
    T4  接線：purge_render 在 commit 前呼叫重編；setval 用 pg_get_serial_sequence
    T5  本地序號沒被動（測試用 set_sequence=False；setval 不受 rollback 保護）

對本地 DB 在一個 transaction 裡先清空再塞 fixture，最後 rollback —— 真資料不動。
"""
import inspect
import sys
from datetime import date

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from scripts import archive_check as ac
from scripts.archive_check import (
    RENUMBER_OFFSET, _local_conn, purge_render, renumber_completed_trips,
)


def banner(label):
    print(f'\n{"=" * 62}\n# {label}\n{"=" * 62}')


def ok(cond, label):
    print(f'  {"✅" if cond else "❌"} {label}')
    assert cond, label


conn = _local_conn()
conn.autocommit = False
cur = conn.cursor()
try:
    cur.execute("SELECT last_value FROM completed_trips_id_seq1")
    seq_before = cur.fetchone()[0]

    # 在 tx 內清空，塞可控的 fixture（最後 rollback，真資料不動）
    cur.execute("DELETE FROM completed_trips")

    def seed(cid, d, code):
        cur.execute("""
            INSERT INTO completed_trips
                (id, date, start_point, end_point, meter_fare, extra_fare,
                 category, driver_id, unique_code, trip_type)
            VALUES (%s, %s, '起', '迄', 100, 0, '診所', NULL, %s, 'temp')
        """, (cid, d, code))

    # 刻意讓 id 順序 ≠ (date, id) 順序，且含 MIN(id)=2 < COUNT=5 的自撞情境
    seed(4000, date(2026, 3, 2), 'A_mar')
    seed(205,  date(2026, 5, 1), 'B_may')
    seed(7000, date(2026, 5, 1), 'C_may_later_id')   # 同日 → 用 id 分先後
    seed(6500, date(2026, 4, 10), 'D_apr')
    seed(2,    date(2026, 9, 19), 'E_sep')

    # ========================================================
    banner('T1: 重編 — (date, id) 排序、連續、對得回去')
    # ========================================================
    n, old_min, old_max = renumber_completed_trips(cur, set_sequence=False)
    ok((n, old_min, old_max) == (5, 2, 7000), f'回 (N, old_min, old_max) = {(n, old_min, old_max)}')
    cur.execute("SELECT id, unique_code FROM completed_trips ORDER BY id")
    rows = cur.fetchall()
    ok([r[0] for r in rows] == [1, 2, 3, 4, 5], f'新 id 連續 1..5 → {[r[0] for r in rows]}')
    want = ['A_mar', 'D_apr', 'B_may', 'C_may_later_id', 'E_sep']
    ok([r[1] for r in rows] == want,
       f'按 (date, id) 排：{[r[1] for r in rows]}')
    ok(rows[2][1] == 'B_may' and rows[3][1] == 'C_may_later_id',
       '同一天的兩筆保持原本 id 先後（205 在 7000 前）')
    cur.execute("SELECT COUNT(*) FROM completed_trips WHERE id >= %s", (RENUMBER_OFFSET,))
    ok(cur.fetchone()[0] == 0, '沒有列停在位移區（兩段都做完）')

    # ========================================================
    banner('T2: 兩段式擋住自撞')
    # ========================================================
    # 上面的 fixture 已含 id=2 與 205：單段 UPDATE 把 4000→1 沒事、但 6500→2 會撞到
    # 還沒改的 id=2（E_sep）。兩段式先全抬到 1,000,000+ 就不會。T1 沒炸 = 通過。
    ok(True, 'T1 在 MIN(2) < COUNT(5) 的情境下沒有 PK 撞擊')
    src = inspect.getsource(renumber_completed_trips)
    ok('RENUMBER_OFFSET' in src and 'id + %s' in src, '先 +位移再重編（兩段式）')
    ok('ROW_NUMBER() OVER (ORDER BY date, id)' in src, '重編依 (date, id)')

    # ========================================================
    banner('T3: 表空')
    # ========================================================
    cur.execute("DELETE FROM completed_trips")
    ok(renumber_completed_trips(cur, set_sequence=False) == (0, None, None),
       '表空 → (0, None, None)，不炸')

    # ========================================================
    banner('T4: 接線 — purge_render 在同一 transaction 內刪完就重編')
    # ========================================================
    psrc = inspect.getsource(purge_render)
    i_del = psrc.index('DELETE FROM completed_trips WHERE date < %s')
    i_ren = psrc.index('renumber_completed_trips(cur)')
    i_commit = psrc.index('rconn.commit()')
    ok(i_del < i_ren < i_commit, '順序：DELETE → 重編 → commit（同一 transaction）')
    ok("pg_get_serial_sequence('completed_trips','id')" in src,
       'setval 用 pg_get_serial_sequence 解析真正的序號（不寫死名字）')
    ok('#編號已作廢' in psrc or '作廢' in psrc, '結果訊息警告舊 #編號作廢')

    # 確認流程（LINE 端）也要警告
    import pathlib
    hsrc = pathlib.Path('/Users/linyancui/minimal_flask/rewrite/handlers/'
                        'sandbox_handler.py').read_text(encoding='utf-8')
    ok('重編為 #1 起' in hsrc, '「確認清理」的提示有講會重編')

finally:
    conn.rollback()
    # ========================================================
    banner('T5: 本地序號沒被動')
    # ========================================================
    cur.execute("SELECT last_value FROM completed_trips_id_seq1")
    seq_after = cur.fetchone()[0]
    ok(seq_before == seq_after, f'completed_trips_id_seq1 {seq_before} → {seq_after}')
    cur.execute("SELECT COUNT(*) FROM completed_trips")
    ok(cur.fetchone()[0] > 0, 'rollback 後真資料都在')
    cur.close()
    conn.close()

print('\n' + '=' * 62)
print('✅ 全部通過 — 歸檔清理會把剩餘班次重編為 #1..#N')
print('=' * 62)
