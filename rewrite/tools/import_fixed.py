"""
匯入固定班次到 trips（未來態 fixed_schedules → 現在態 trips）

對應 legacy modules/handlers/import_handler.py:import_week_trips（重做、純函數版）。

設計：
  - **太陽週**：星期日為週起算（重用 modules.utils.week_utils，純函數可直接用）
  - 兩個 atomic tool：
      preview_import_fixed   → 預覽（不寫入），回將匯入筆數 + 衝突
      import_fixed_to_trips  → 執行匯入
  - overwrite=False 預設安全；overwrite=True 才 DELETE 既有

⚠️ 太陽週**不允許匯入過去週次**（業務規則：過去週已過去、班次該已掉入 completed_trips）。
   過去態查詢仍可用「上週」這種 phrase（那是查詢，不是寫入）。

R-5 鎖：不適用（批量寫，無單一 trip 鎖）。
R-6 audit：寫一筆 batch audit，target_id=0（沒有單一 target）。
"""
from datetime import date
from typing import Optional
from sqlalchemy import text

from rewrite.tools.base import ToolResult, write_audit
from rewrite.tools.leave_guard import is_zero_surcharge
# 重用 legacy 太陽週純函數（無 Flask 耦合）
from modules.utils.week_utils import calculate_target_week, is_week_in_past


VALID_IMPORT_CATEGORIES = ('診所', '東洋', '臨時')
"""類別必須在 enum 內 — 跟 legacy import_handler 一致"""

SEQ_RESET_THRESHOLD = 5000
"""trips 序號自動歸位門檻 — 週更清空後序號超過此值才歸 1。

不設成每週歸 1 的原因：聊天室裡舊班次卡片的按鈕帶著 trip_id，
週週重用 id 會讓「上週的請假按鈕」打到「本週的同號班次」。
門檻制讓 id 重用約 8-10 個月才發生一次，舊按鈕早已沉底。
（completed_trips 的 id 是歷史累積、被 #N 指令引用，永不重置。）"""


def reset_trips_sequence(*, session) -> ToolResult:
    """手動重置 trips 序號 — 僅當 trips 已清空才執行（防誤用）。

    Triggers: 「重置班次序號」。
    setval 立即生效且不受 rollback 保護，故不吃 auto_commit 參數。
    """
    count = session.execute(text("SELECT COUNT(*) FROM trips")).scalar()
    seq_name = session.execute(text(
        "SELECT pg_get_serial_sequence('trips', 'trip_id')"
    )).scalar()
    if not seq_name:
        return ToolResult.fail("找不到 trips 的序號 sequence")
    next_val = session.execute(
        text(f"SELECT last_value FROM {seq_name}")).scalar()
    if count and count > 0:
        return ToolResult.fail(
            f"trips 還有 {count} 筆班次（目前序號 #{next_val}），"
            f"清空本週班次後才能重置。序號會在匯入清空時自動歸位，"
            f"通常不需手動操作"
        )
    session.execute(text("SELECT setval(:s, 1, false)"), {'s': seq_name})
    session.commit()
    return ToolResult.success(data={
        'from': int(next_val or 0),
        'message': f"🔁 班次序號已重置：原 #{next_val} → 下一班從 #1 開始",
    })


def _check_existing(*, session, dates, category) -> int:
    """查該週該類別的 fixed_trip_id 既有筆數"""
    return session.execute(text("""
        SELECT COUNT(*) FROM trips
        WHERE date >= :start AND date <= :end
          AND fixed_trip_id IS NOT NULL
          AND category = :category
    """), {'start': dates[0], 'end': dates[6], 'category': category}).scalar() or 0


def _count_purgeable_past(*, session, week_start, category) -> int:
    """算本週起點之前該類別、該被清理的 trips 筆數
    （fixed-typed 或 temp-typed；有意義的應該都已掉入 completed_trips）
    """
    return session.execute(text("""
        SELECT COUNT(*) FROM trips
        WHERE date < :before
          AND category = :category
          AND (fixed_trip_id IS NOT NULL OR trip_type = 'temp')
    """), {'before': week_start, 'category': category}).scalar() or 0


def sun_week_number(d) -> int:
    """太陽週週號（Sunday-first，符合本系統業務週定義）

    用 Python 內建 strftime('%U')。注意這跟 isocalendar().week（ISO 8601 週一起算）不同，
    本系統一律走太陽週（CLAUDE.md「業務週定義」章節）。

    公開 helper：給 LIFF endpoint / skill prompt / view 共用。
    """
    return int(d.strftime('%U'))


# 內部別名（向後相容，新 code 用 sun_week_number）
_sun_week_number = sun_week_number


def _fetch_fixed_for_day(*, session, weekday: int, category: str):
    """撈某星期幾 + 類別的 fixed_schedules（非『停用』）"""
    return session.execute(text("""
        SELECT id, route_number, departure_time,
               start_point, via_point, end_point,
               base_fare, surcharge, total_fare,
               category, driver_id, direction,
               status, note, passenger_name
        FROM fixed_schedules
        WHERE route_number LIKE :pat
          AND (status IS NULL OR status != '停用')
          AND category = :category
    """), {'pat': f'%{weekday}%', 'category': category}).fetchall()


def preview_import_fixed(
    *,
    session,
    week_offset: int = 0,
    category: str = '診所',
) -> ToolResult:
    """
    預覽即將匯入 — 不寫入 DB。

    Args:
        week_offset: 0=本週，1=下週，2=下下週，3+=未來。負數會被擋。
        category: '診所' / '東洋' / '臨時'

    Returns:
        ToolResult.success(data={
            week_label, week_range, date_start, date_end, category,
            will_insert: int,    # 將會嘗試 INSERT 的總筆數
            existing: int,       # 該週該類別現有 fixed-typed trips（衝突來源）
            leave_count: int,    # 將匯入中標記為「請假」的筆數
            zero_surcharge_leave: int,  # 其中加成 0 元（不會扣款）的筆數
            normal_count: int,   # 將匯入中正常的筆數
            need_overwrite: bool,# 有衝突需要 overwrite=True 才能匯
        })
    """
    if category not in VALID_IMPORT_CATEGORIES:
        return ToolResult.fail(
            f"類別必須是 {VALID_IMPORT_CATEGORIES} 之一，給的是 {category!r}"
        )
    if week_offset < 0:
        return ToolResult.fail("不允許匯入過去週次（week_offset 不可負）")

    today = date.today()
    week_start, dates, week_desc = calculate_target_week(today, week_offset)

    if is_week_in_past(dates, today):
        return ToolResult.fail(f"不允許匯入過去時間態：{week_desc}")

    existing = _check_existing(session=session, dates=dates, category=category)

    # 算將匯入筆數（按星期幾撈 fixed_schedules）
    will_insert = 0
    leave_count = 0
    zero_surcharge_leave = 0
    for import_date in dates:
        weekday = import_date.isoweekday()  # 1=Mon..7=Sun
        rows = _fetch_fixed_for_day(
            session=session, weekday=weekday, category=category,
        )
        will_insert += len(rows)
        leave_count += sum(1 for r in rows if r.status == '請假')
        # 模板請假但沒扣款 → 匯進來就是 N 筆 0 元請假班次。
        # 這條路完全不經過 passenger_leave 的閘門（自己 INSERT），
        # 而且量最大（實測占現有請假班次七成以上），所以在預覽就要講明白。
        zero_surcharge_leave += sum(
            1 for r in rows if r.status == '請假' and is_zero_surcharge(r.surcharge)
        )

    purge_count = _count_purgeable_past(
        session=session, week_start=dates[0], category=category,
    )

    return ToolResult.success(
        data={
            'zero_surcharge_leave': zero_surcharge_leave,
            'week_label': '本週' if week_offset == 0
                          else f'+{week_offset}週' if week_offset > 0
                          else f'{week_offset}週',
            'week_range': week_desc,
            'sun_week_number': _sun_week_number(dates[0]),
            'date_start': dates[0],
            'date_end': dates[6],
            'category': category,
            'will_insert': will_insert,
            'existing': existing,
            'leave_count': leave_count,
            'normal_count': will_insert - leave_count,
            'need_overwrite': existing > 0,
            'purge_past_count': purge_count,
        },
    )


def import_fixed_to_trips(
    *,
    session,
    week_offset: int = 0,
    category: str = '診所',
    overwrite: bool = False,
    purge_past: bool = False,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    執行匯入 — 從 fixed_schedules 批量複製到 trips。

    流程（對齊 legacy import_handler.import_week_trips）：
      1. 太陽週起點計算 + 過去週擋下
      2. 衝突檢測：該週該類別已有 fixed-typed trips？
         - 有 + overwrite=False → fail（提示加 overwrite）
         - 有 + overwrite=True  → DELETE 既有，再插入
         - 無 → 直接插入
      3. 對每天（7 天）按星期幾撈 fixed_schedules
      4. 對每筆 fixed_schedule：
         - 算 unique_code = f"{fixed_id}_{day_of_year}_{week_number}"
         - 本週 + 非覆蓋模式：檢查 (fixed_id, date) 重複跳過
         - status='請假' → trip 帶 passenger_leave_reason=note + extra_fare=surcharge
         - 其他 → trip 沒 leave_reason，extra_fare=surcharge or 0
         - INSERT trips 帶 trip_type='fixed', status='準備'

    Args:
        week_offset: 0=本週，1=下週，... (>= 0)
        category: '診所' / '東洋' / '臨時'
        overwrite: 既有衝突時是否 DELETE 重做
    """
    if category not in VALID_IMPORT_CATEGORIES:
        return ToolResult.fail(
            f"類別必須是 {VALID_IMPORT_CATEGORIES} 之一"
        )
    if week_offset < 0:
        return ToolResult.fail("不允許匯入過去週次")

    today = date.today()
    week_start, dates, week_desc = calculate_target_week(today, week_offset)

    if is_week_in_past(dates, today):
        return ToolResult.fail(f"不允許匯入過去時間態：{week_desc}")

    existing = _check_existing(session=session, dates=dates, category=category)
    if existing > 0 and not overwrite:
        return ToolResult.fail(
            f"{week_desc}（{category}）已匯入過 {existing} 筆。"
            f"如需覆蓋請傳 overwrite=True（注意：原先對班次的修改會失效）"
        )

    deleted_count = 0
    if overwrite and existing > 0:
        result = session.execute(text("""
            DELETE FROM trips
            WHERE date >= :start AND date <= :end
              AND fixed_trip_id IS NOT NULL
              AND category = :category
        """), {'start': dates[0], 'end': dates[6], 'category': category})
        deleted_count = result.rowcount

    # 清理過去週同類別的 stuck trips（fixed-typed 或 temp-typed）
    # 業務假設：有意義的資料應該已掉入 completed_trips
    purged_count = 0
    if purge_past:
        result = session.execute(text("""
            DELETE FROM trips
            WHERE date < :before
              AND category = :category
              AND (fixed_trip_id IS NOT NULL OR trip_type = 'temp')
        """), {'before': dates[0], 'category': category})
        purged_count = result.rowcount

    # === 序號自動歸位 ===
    # 週更清完舊班次後，trips 若已清空且序號墊高過門檻 → 歸 1（用戶需求：
    # 序號不要無限堆高）。⚠️ setval 不受 rollback 保護 — 先 commit 上面的
    # DELETE 再 reset，之後 INSERT 若失敗回滾，也不會出現「舊班次還在、
    # 序號卻歸 1」的 PK 撞擊（重匯即可，fixed_schedules 是資料來源）。
    seq_reset_from = None
    if auto_commit:  # 測試的 rollback 模式（auto_commit=False）不動序號
        remaining = session.execute(text("SELECT COUNT(*) FROM trips")).scalar()
        if remaining == 0:
            seq_name = session.execute(text(
                "SELECT pg_get_serial_sequence('trips', 'trip_id')"
            )).scalar()
            if seq_name:
                next_val = session.execute(
                    text(f"SELECT last_value FROM {seq_name}")).scalar()
                if next_val and next_val >= SEQ_RESET_THRESHOLD:
                    session.commit()   # 先落地 DELETE
                    session.execute(text("SELECT setval(:s, 1, false)"),
                                    {'s': seq_name})
                    session.commit()
                    seq_reset_from = int(next_val)

    # week_offset 重算（防 user 給負/錯）
    week_offset_actual = (week_start - today).days // 7

    inserted = 0
    leave_count = 0
    normal_count = 0
    skipped_dup = 0

    # === 效能：一次撈該週所有 (fixed_trip_id, date) 已存在組合（避免 N 次 SELECT）===
    # 之前每筆 INSERT 前 SELECT 1 dup 檢查 → 114 筆 × ~100ms 在 Render 撞 30s gunicorn timeout
    # 現在收集成 set，in-memory 比對
    existing_keys: set[tuple] = set()
    if week_offset_actual == 0 and not overwrite:
        rows = session.execute(text("""
            SELECT fixed_trip_id AS fid, date
            FROM trips
            WHERE date >= :start AND date <= :end
              AND fixed_trip_id IS NOT NULL
        """), {'start': dates[0], 'end': dates[6]}).fetchall()
        existing_keys = {(r.fid, r.date) for r in rows}

    # === 收集要 INSERT 的 batch（不立即執行）===
    insert_batch: list[dict] = []

    for import_date in dates:
        weekday = import_date.isoweekday()
        rows = _fetch_fixed_for_day(
            session=session, weekday=weekday, category=category,
        )

        for r in rows:
            day_of_year = import_date.timetuple().tm_yday
            _, week_number, _ = import_date.isocalendar()
            unique_code = f"{r.id}_{day_of_year}_{week_number}"

            # status='請假' → 帶請假原因
            is_leave = r.status == '請假' and r.note
            if is_leave:
                leave_reason = r.note
                leave_count += 1
            else:
                leave_reason = None
                normal_count += 1
            extra_fare = r.surcharge if r.surcharge is not None else 0

            # in-memory dup 檢查（不再 SELECT 每筆）
            if (r.id, import_date) in existing_keys:
                skipped_dup += 1
                if is_leave:
                    leave_count -= 1
                else:
                    normal_count -= 1
                continue

            insert_batch.append({
                'fid': r.id, 'date': import_date, 'time': r.departure_time,
                'sp': r.start_point, 'vp': r.via_point, 'ep': r.end_point,
                'meter': r.base_fare, 'extra': extra_fare,
                'cat': r.category, 'did': r.driver_id,
                'leave': leave_reason,
                'pname': r.passenger_name,   # 乘客/接送順序 → 班次詳情顯示，不進報表
                'uc': unique_code, 'wn': week_number,
            })
            inserted += 1

    # === 一次 batch INSERT（SQLAlchemy executemany 性能比 loop 中個別 execute 快很多）===
    if insert_batch:
        session.execute(text("""
            INSERT INTO trips
            (fixed_trip_id, date, time,
             start_point, via_point, end_point,
             meter_fare, extra_fare, category, driver_id,
             status, passenger_leave_reason, passenger_name,
             unique_code, week_number, trip_type)
            VALUES
            (:fid, :date, :time,
             :sp, :vp, :ep,
             :meter, :extra, :cat, :did,
             '準備', :leave, :pname,
             :uc, :wn, 'fixed')
        """), insert_batch)

    # batch audit log
    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='import_fixed_to_trips',
        target_table='trips', target_id=0,
        before_state=None,
        after_state={
            'week_range': week_desc, 'category': category,
            'inserted': inserted,
            'overwritten': deleted_count,
            'purged_past': purged_count,
        },
        changed_fields=None,
        extra={
            'week_offset': week_offset,
            'overwrite': overwrite,
            'purge_past': purge_past,
            'leave_count': leave_count,
            'normal_count': normal_count,
            'skipped_dup': skipped_dup,
        },
        via=via,
    )

    if auto_commit:
        session.commit()

    return ToolResult.success(
        data={
            'week_label': '本週' if week_offset == 0 else f'+{week_offset}週',
            'week_range': week_desc,
            'sun_week_number': _sun_week_number(dates[0]),
            'date_start': dates[0],
            'date_end': dates[6],
            'category': category,
            'inserted': inserted,
            'overwritten': deleted_count,
            'purged_past': purged_count,
            'leave_count': leave_count,
            'normal_count': normal_count,
            'skipped_dup': skipped_dup,
            'seq_reset_from': seq_reset_from,
        },
    )
