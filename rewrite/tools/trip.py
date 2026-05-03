"""
trips（現在態）查詢工具

設計：
  R-1：時間態判斷由呼叫方決定（這裡只查 trips 表）
  R-4：純函數，session 從參數傳入

工具：
  query_trips                    — 條件查詢
  query_trip_by_id               — 單筆詳情
  query_today_trips              — 今天班次（最常用）
  query_pending_dispatch         — 待派班次

⚠️ 過去態（completed_trips）暫不支援，v0.2 補完。
"""

from dataclasses import dataclass, asdict, field
from datetime import date, datetime, time, timedelta
from typing import Optional, List, Any
from sqlalchemy import text

from rewrite.tools.base import ToolResult


# ============================================================
# 狀態 → 視覺標記
# ============================================================
STATUS_EMOJI = {
    '準備': '🟢',
    '已完成': '✅',
    '待派': '🔴',
    '註銷': '❌',
    '衝突': '⚠️',
    '請假': '🏷️',
}

LOCK_MINUTES = 30


# ============================================================
# View 結構
# ============================================================

@dataclass
class TripView:
    """班次展示用結構（含計算欄位）"""
    trip_id: int

    # 時間 / 路線
    date: Optional[date] = None
    time: Optional[time] = None
    start_point: Optional[str] = None
    via_point: Optional[str] = None
    end_point: Optional[str] = None

    # 司機 / 車資
    driver_id: Optional[int] = None
    meter_fare: Optional[int] = None
    extra_fare: Optional[int] = None
    actual_fare: Optional[int] = None
    category: Optional[str] = None

    # 狀態 / 請假
    status: Optional[str] = None
    passenger_leave_reason: Optional[str] = None
    passenger_name: Optional[str] = None

    # 修改追蹤
    modified_by: Optional[str] = None
    modification_reason: Optional[str] = None
    modification_time: Optional[datetime] = None

    # 模板關聯
    fixed_trip_id: Optional[int] = None
    week_number: Optional[int] = None
    trip_type: Optional[str] = None
    unique_code: Optional[str] = None

    # 計算欄位
    display_status: str = ''        # 含障眼法後的真實狀態（請假/準備）
    status_emoji: str = ''
    is_locked: bool = False         # 30 分鐘鎖內
    minutes_until_trip: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> "TripView":
        d = dict(row._mapping)

        # 三層障眼法：status='準備' + passenger_leave_reason 視為「請假」
        raw_status = d.get('status')
        leave = d.get('passenger_leave_reason')
        if leave and raw_status == '準備':
            display = '請假'
        else:
            display = raw_status or ''
        d['display_status'] = display
        d['status_emoji'] = STATUS_EMOJI.get(display, '⚪')

        # 30 分鐘鎖計算
        td = d.get('date')
        tt = d.get('time')
        if td and tt:
            trip_dt = datetime.combine(td, tt)
            now = datetime.now()
            delta = (trip_dt - now).total_seconds() / 60
            d['minutes_until_trip'] = int(delta) if delta > -10000 else None
            d['is_locked'] = 0 < delta < LOCK_MINUTES
        else:
            d['minutes_until_trip'] = None
            d['is_locked'] = False

        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    def to_dict(self) -> dict:
        return asdict(self)

    def short_route(self) -> str:
        """簡短路線：起點→終點（含途經括號）"""
        parts = [self.start_point or '?']
        if self.via_point:
            parts.append(f"經{self.via_point}")
        parts.append(self.end_point or '?')
        return '→'.join(p for p in parts if p)


# ============================================================
# 共用 SELECT
# ============================================================

_SELECT_ALL = """
    SELECT trip_id, date, time, start_point, via_point, end_point,
           driver_id, meter_fare, extra_fare, actual_fare, category,
           status, passenger_leave_reason, passenger_name,
           modified_by, modification_reason, modification_time,
           fixed_trip_id, week_number, trip_type, unique_code
    FROM trips
"""


# ============================================================
# 查詢函數
# ============================================================

def query_trips(
    *,
    session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    driver_id: Optional[int] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    customer_short_name: Optional[str] = None,
    exclude_status: Optional[List[str]] = None,
    limit: int = 200,
) -> ToolResult:
    """
    多條件查詢 trips（現在態）。

    所有條件 AND。沒給就不限制。

    customer_short_name：起、途、終 任一含此 → 命中（用於「龍埔街今天的班次」這類查詢）
    exclude_status：要排除的狀態列表（例：排除「已完成」）
    """
    where = []
    params: dict = {}

    if date_from:
        where.append('date >= :date_from')
        params['date_from'] = date_from
    if date_to:
        where.append('date <= :date_to')
        params['date_to'] = date_to
    if driver_id is not None:
        where.append('driver_id = :driver_id')
        params['driver_id'] = driver_id
    if category:
        where.append('category = :category')
        params['category'] = category
    if status:
        where.append('status = :status')
        params['status'] = status
    if customer_short_name:
        where.append("(start_point = :sn OR via_point = :sn OR end_point = :sn)")
        params['sn'] = customer_short_name
    if exclude_status:
        # 用 ANY array，避免逐個 OR
        where.append('(status IS NULL OR NOT (status = ANY(:excl)))')
        params['excl'] = list(exclude_status)

    sql = _SELECT_ALL
    if where:
        sql += '\nWHERE ' + ' AND '.join(where)
    sql += '\nORDER BY date, time, trip_id\nLIMIT :limit'
    params['limit'] = limit

    rows = session.execute(text(sql), params).fetchall()
    if not rows:
        return ToolResult.fail("找不到符合條件的班次")

    return ToolResult.success(
        data=[TripView.from_row(r) for r in rows],
        count=len(rows),
        filters={k: str(v)[:50] for k, v in params.items() if k != 'limit'},
    )


def query_trip_by_id(trip_id: int, *, session) -> ToolResult:
    """單筆班次詳情"""
    row = session.execute(
        text(f"{_SELECT_ALL} WHERE trip_id = :id"),
        {'id': trip_id}
    ).fetchone()
    if row:
        return ToolResult.success(data=TripView.from_row(row))
    return ToolResult.fail(f"找不到班次 #{trip_id}")


def query_today_trips(
    *,
    session,
    category: Optional[str] = None,
    include_completed: bool = True,
) -> ToolResult:
    """
    今天的班次（最常用查詢）。

    Args:
        category: '診所' / '東洋' / '臨時' 等。None = 全部
        include_completed: 是否包含已完成班次（預設含，與 main 行為一致）
    """
    today = date.today()
    excl = [] if include_completed else ['已完成']
    return query_trips(
        session=session,
        date_from=today,
        date_to=today,
        category=category,
        exclude_status=excl or None,
    )


# ============================================================
# Mutation 工具（R-5 鎖 + R-6 audit log）
# ============================================================

from rewrite.tools.base import (
    require_modifiable_window,
    write_audit,
    fetch_trip_snapshot,
    diff_fields,
)


@require_modifiable_window(allow_in_lock=False)
def passenger_leave(
    *,
    session,
    trip_id: int,
    reason: str,
    surcharge: int = 0,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    乘客請假（三層障眼法）

    - status 維持 '準備'
    - passenger_leave_reason = reason
    - extra_fare = surcharge（通常負，例：-100 表示乘客自己來扣 100）
    - modification_reason 累加 '[N] 乘客請假: reason' 形式

    R-5：30 分鐘鎖內拒絕（decorator）
    R-6：寫 audit log
    """
    if not reason or not reason.strip():
        return ToolResult.fail("請假原因不可空")
    if not isinstance(surcharge, int):
        return ToolResult.fail("加成必須是整數（通常負，如 -100）")

    # 確認 trip 存在 + 取 before
    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")

    # 檢查狀態：已完成 / 註銷 不可再請假
    if before.get('status') in ('已完成', '註銷'):
        return ToolResult.fail(
            f"班次 #{trip_id} 狀態為「{before.get('status')}」，無法請假"
        )

    # 計算新的 modification_reason（疊加）
    old_mod = before.get('modification_reason') or ''
    next_idx = 1 + old_mod.count('[')
    suffix = f"[{next_idx}] 乘客請假: {reason.strip()}"
    new_mod = (old_mod + '; ' + suffix) if old_mod else suffix

    # UPDATE
    session.execute(
        text("""
            UPDATE trips SET
                status = '準備',
                passenger_leave_reason = :reason,
                extra_fare = :surcharge,
                modification_reason = :mod_reason,
                modified_by = :user_name,
                modification_time = CURRENT_TIMESTAMP
            WHERE trip_id = :trip_id
        """),
        {
            'reason': reason.strip(),
            'surcharge': surcharge,
            'mod_reason': new_mod,
            'user_name': user_name or user_id,
            'trip_id': trip_id,
        }
    )

    # after snapshot
    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    changed = diff_fields(before, after)

    # audit log
    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='passenger_leave',
        target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=changed,
        reason=reason.strip(),
        extra={'surcharge': surcharge},
        via=via,
    )

    if auto_commit:
        session.commit()

    # 回傳更新後的 TripView
    return query_trip_by_id(trip_id, session=session)


def _bump_modification_reason(old: Optional[str], suffix: str) -> str:
    """累加 modification_reason"""
    old = old or ''
    next_idx = 1 + old.count('[')
    new_suffix = f"[{next_idx}] {suffix}"
    return (old + '; ' + new_suffix) if old else new_suffix


@require_modifiable_window(allow_in_lock=False)
def cancel_trip(
    *,
    session,
    trip_id: int,
    reason: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """註銷班次（status → '註銷'）"""
    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")
    if before.get('status') == '已完成':
        return ToolResult.fail(f"班次 #{trip_id} 已完成，無法註銷")
    if before.get('status') == '註銷':
        return ToolResult.fail(f"班次 #{trip_id} 已是註銷狀態")

    new_mod = _bump_modification_reason(
        before.get('modification_reason'),
        f"註銷{'：' + reason if reason else ''}"
    )

    session.execute(text("""
        UPDATE trips SET
            status = '註銷',
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {'mod': new_mod, 'who': user_name or user_id, 'id': trip_id})

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='cancel_trip', target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason, via=via,
    )
    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


@require_modifiable_window(allow_in_lock=False)
def mark_conflict(
    *,
    session,
    trip_id: int,
    reason: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """標記衝突（status → '衝突'）"""
    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")
    if before.get('status') == '已完成':
        return ToolResult.fail(f"班次 #{trip_id} 已完成，無法標記衝突")

    new_mod = _bump_modification_reason(
        before.get('modification_reason'),
        f"衝突{'：' + reason if reason else ''}"
    )

    session.execute(text("""
        UPDATE trips SET
            status = '衝突',
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {'mod': new_mod, 'who': user_name or user_id, 'id': trip_id})

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='mark_conflict', target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason, via=via,
    )
    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


@require_modifiable_window(allow_in_lock=True)  # 鎖內也允許救回
def restore_to_ready(
    *,
    session,
    trip_id: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    改回準備（清請假/註銷/衝突 → '準備'）

    - 已完成 → 拒絕
    - 待派（無司機）→ 拒絕，請先指派司機
    - 其他 → status='準備'、清 leave_reason、若 extra_fare<0 則歸零
    """
    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")
    if before.get('status') == '已完成':
        return ToolResult.fail(f"班次 #{trip_id} 已完成，無法改回準備")
    if before.get('status') == '待派' or not before.get('driver_id'):
        return ToolResult.fail(f"班次 #{trip_id} 未指派司機，請先指派")

    # 計算新 extra_fare（負數視為請假負加成，歸零；正數保留）
    cur_extra = before.get('extra_fare') or 0
    new_extra = 0 if cur_extra < 0 else cur_extra

    new_mod = _bump_modification_reason(
        before.get('modification_reason'),
        "改回準備"
    )

    session.execute(text("""
        UPDATE trips SET
            status = '準備',
            passenger_leave_reason = NULL,
            extra_fare = :extra,
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {'extra': new_extra, 'mod': new_mod, 'who': user_name or user_id, 'id': trip_id})

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='restore_to_ready', target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        via=via,
    )
    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


@require_modifiable_window(allow_in_lock=True)
def assign_driver(
    *,
    session,
    trip_id: int,
    driver_id: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    指派司機。

    - 驗證 driver_id 在 drivers 表
    - 若原狀態為「待派」→ 升級為「準備」
    - 若原已有司機，覆蓋（換司機）
    """
    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")
    if before.get('status') in ('已完成', '註銷'):
        return ToolResult.fail(f"班次 #{trip_id} 狀態為「{before.get('status')}」，無法指派")

    # 驗證司機存在
    drv = session.execute(
        text("SELECT id FROM drivers WHERE id = :id"),
        {'id': driver_id}
    ).fetchone()
    if not drv:
        return ToolResult.fail(f"找不到司機 ID {driver_id}")

    # 待派 → 準備
    new_status = '準備' if before.get('status') == '待派' else before.get('status')

    note = f"指派司機 {driver_id}" if not before.get('driver_id') else \
           f"換司機 {before.get('driver_id')}→{driver_id}"
    new_mod = _bump_modification_reason(before.get('modification_reason'), note)

    session.execute(text("""
        UPDATE trips SET
            driver_id = :driver_id,
            status = :status,
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {
        'driver_id': driver_id, 'status': new_status,
        'mod': new_mod, 'who': user_name or user_id, 'id': trip_id
    })

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='assign_driver', target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        extra={'new_driver_id': driver_id, 'old_driver_id': before.get('driver_id')},
        via=via,
    )
    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


@require_modifiable_window(allow_in_lock=True)
def unassign_driver(
    *,
    session,
    trip_id: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    撤銷司機指派（軟取消）

    - driver_id → NULL
    - status → '待派'
    - 結果：時間到不會自動掉入 completed_trips（軟取消設計）
    """
    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")
    if before.get('status') in ('已完成', '註銷'):
        return ToolResult.fail(
            f"班次 #{trip_id} 狀態為「{before.get('status')}」，無法撤銷指派"
        )
    if not before.get('driver_id'):
        return ToolResult.fail(f"班次 #{trip_id} 本來就沒指派司機")

    old_driver = before.get('driver_id')
    new_mod = _bump_modification_reason(
        before.get('modification_reason'),
        f"撤銷司機 {old_driver} 指派"
    )

    session.execute(text("""
        UPDATE trips SET
            driver_id = NULL,
            status = '待派',
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {'mod': new_mod, 'who': user_name or user_id, 'id': trip_id})

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='unassign_driver', target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        extra={'old_driver_id': old_driver},
        via=via,
    )
    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


# ============================================================
# 小型 mutation（鎖內可、不需確認）— spec §3.1
# ============================================================

@require_modifiable_window(allow_in_lock=True)
def update_passenger_name(
    *,
    session,
    trip_id: int,
    passenger_name: Optional[str],
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    改乘客名稱（鎖內可、不需確認，spec §3.1）

    傳 None / 空白 → 清空（passenger_name=NULL）
    沒變動 → fail，避免無意義 audit
    """
    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")

    new_name = (passenger_name.strip() if passenger_name else None) or None
    old_name = before.get('passenger_name')
    if old_name == new_name:
        return ToolResult.fail("乘客名稱沒變動")

    note = f"改乘客名: {old_name!r} → {new_name!r}"
    new_mod = _bump_modification_reason(before.get('modification_reason'), note)

    session.execute(text("""
        UPDATE trips SET
            passenger_name = :name,
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {'name': new_name, 'mod': new_mod,
           'who': user_name or user_id, 'id': trip_id})

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='update_passenger_name', target_table='trips',
        target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        extra={'old_name': old_name, 'new_name': new_name},
        via=via,
    )
    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


@require_modifiable_window(allow_in_lock=True)
def record_fare_current(
    *,
    session,
    trip_id: int,
    meter_fare: Optional[int] = None,
    extra_fare: Optional[int] = None,
    reason: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    記錄現在態車資（trips 表）— spec §3.1

    至少給 meter_fare 或 extra_fare 其中一個。沒變動 → fail。
    鎖內可、不需確認。

    ⚠️ 跟過去態車資（completed_trips 的 record_fare_completed）不同，
    那是 v0.2 的工作。此函數只動 trips。
    """
    if meter_fare is None and extra_fare is None:
        return ToolResult.fail("至少要給 meter_fare 或 extra_fare 其中一個")
    if meter_fare is not None and not isinstance(meter_fare, int):
        return ToolResult.fail("meter_fare 必須是整數")
    if extra_fare is not None and not isinstance(extra_fare, int):
        return ToolResult.fail("extra_fare 必須是整數")

    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")

    # 動態 SET：只更新有給的欄位
    sets = []
    params: dict = {'id': trip_id}
    diffs: list = []

    if meter_fare is not None and before.get('meter_fare') != meter_fare:
        sets.append('meter_fare = :meter_fare')
        params['meter_fare'] = meter_fare
        diffs.append(f"錶價 {before.get('meter_fare')}→{meter_fare}")

    if extra_fare is not None and before.get('extra_fare') != extra_fare:
        sets.append('extra_fare = :extra_fare')
        params['extra_fare'] = extra_fare
        diffs.append(f"加成 {before.get('extra_fare')}→{extra_fare}")

    if not diffs:
        return ToolResult.fail("車資沒變動")

    note = "改車資: " + ", ".join(diffs)
    if reason:
        note += f" ({reason})"
    new_mod = _bump_modification_reason(before.get('modification_reason'), note)

    sets.extend([
        'modification_reason = :mod',
        'modified_by = :who',
        'modification_time = CURRENT_TIMESTAMP',
    ])
    params['mod'] = new_mod
    params['who'] = user_name or user_id

    sql = f"UPDATE trips SET {', '.join(sets)} WHERE trip_id = :id"
    session.execute(text(sql), params)

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='record_fare_current', target_table='trips',
        target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason,
        extra={
            'old_meter': before.get('meter_fare'),
            'new_meter': meter_fare,
            'old_extra': before.get('extra_fare'),
            'new_extra': extra_fare,
        },
        via=via,
    )
    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


# ============================================================
# 創建（trips 增）— 取代沙盒 booking_create
# ============================================================

def _resolve_endpoint(session, raw: Optional[str]) -> tuple:
    """
    解析起 / 終點：FK 校驗 + 「臨時地點」fallback

    回傳 (fk_value, custom_value)：
      - raw 為空 → (None, None)
      - raw 在 customers.short_name → (raw, raw)  雙寫（給 query + scheduler 都用）
      - raw 不在 → ('臨時地點', raw)  FK fallback，實際值放 custom

    為什麼雙寫：scheduler 對 trip_type='temp' 一律從 custom_* 取地點寫入
    completed_trips；query_trips 的 customer_short_name 過濾是看 start/end_point。
    雙寫讓兩邊都拿得到資料。
    """
    if not raw or not raw.strip():
        return (None, None)
    raw = raw.strip()
    row = session.execute(
        text("SELECT 1 FROM customers WHERE short_name = :sn"),
        {'sn': raw}
    ).fetchone()
    if row:
        return (raw, raw)
    return ('臨時地點', raw)


def create_trip(
    *,
    session,
    trip_date: date,
    trip_time: time,
    start_point: str,
    end_point: Optional[str] = None,
    via_point: Optional[str] = None,
    category: str = '診所',
    driver_id: Optional[int] = None,
    meter_fare: Optional[int] = None,
    extra_fare: int = 0,
    passenger_name: Optional[str] = None,
    trip_type: str = 'temp',
    fixed_trip_id: Optional[int] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    建立新班次（trips 增）

    起終點 FK 校驗（_resolve_endpoint）：
      - 在 customers.short_name → 雙寫 start_point + custom_start_point
      - 不在 → start_point='臨時地點' + custom_start_point=實際值

    狀態：
      - 給 driver_id → '準備'
      - 沒給        → '待派'

    自動產：
      - unique_code = T_{trip_id}_{YYYYMMDD}（沿用 legacy 格式）
      - week_number = 從 ISO 週次計算

    R-5 鎖：不適用（新建 trip 不可能在鎖內）
    R-6 audit：寫 'create_trip'，before_state=None，after_state=完整 snapshot
    """
    # ---- 基本驗證 ----
    if not trip_date:
        return ToolResult.fail("trip_date 必填")
    if not trip_time:
        return ToolResult.fail("trip_time 必填")
    if not start_point or not start_point.strip():
        return ToolResult.fail("start_point 必填")
    if not isinstance(extra_fare, int):
        return ToolResult.fail("extra_fare 必須是整數")
    if meter_fare is not None and not isinstance(meter_fare, int):
        return ToolResult.fail("meter_fare 必須是整數或 None")

    # ---- 司機驗證 ----
    if driver_id is not None:
        drv = session.execute(
            text("SELECT id FROM drivers WHERE id = :id"),
            {'id': driver_id}
        ).fetchone()
        if not drv:
            return ToolResult.fail(f"找不到司機 ID {driver_id}")

    # ---- 起終點 FK 解析 ----
    sp_fk, sp_custom = _resolve_endpoint(session, start_point)
    ep_fk, ep_custom = _resolve_endpoint(session, end_point)
    via_clean = via_point.strip() if via_point and via_point.strip() else None

    # ---- 狀態 ----
    new_status = '準備' if driver_id else '待派'

    # ---- ISO 週次 ----
    _, week_number, _ = trip_date.isocalendar()

    # ---- INSERT ----
    result = session.execute(text("""
        INSERT INTO trips (
            date, time,
            start_point, end_point, via_point,
            custom_start_point, custom_end_point, custom_via_point,
            category, status, trip_type, fixed_trip_id,
            driver_id, meter_fare, extra_fare,
            passenger_name, week_number,
            modified_by, modification_reason, modification_time
        ) VALUES (
            :date, :time,
            :sp, :ep, :via,
            :sp_custom, :ep_custom, :via_custom,
            :category, :status, :trip_type, :fixed_trip_id,
            :driver_id, :meter_fare, :extra_fare,
            :passenger_name, :week_number,
            :user_name, :mod_reason, CURRENT_TIMESTAMP
        )
        RETURNING trip_id
    """), {
        'date': trip_date, 'time': trip_time,
        'sp': sp_fk, 'ep': ep_fk, 'via': via_clean,
        'sp_custom': sp_custom, 'ep_custom': ep_custom,
        'via_custom': via_clean,
        'category': category, 'status': new_status,
        'trip_type': trip_type, 'fixed_trip_id': fixed_trip_id,
        'driver_id': driver_id,
        'meter_fare': meter_fare, 'extra_fare': extra_fare,
        'passenger_name': passenger_name,
        'week_number': week_number,
        'user_name': user_name or user_id,
        'mod_reason': '[1] 新建班次',
    })
    new_trip_id = result.fetchone()[0]

    # ---- unique_code ----
    date_str = trip_date.strftime('%Y%m%d')
    unique_code = f"T_{new_trip_id}_{date_str}"
    session.execute(
        text("UPDATE trips SET unique_code = :uc WHERE trip_id = :id"),
        {'uc': unique_code, 'id': new_trip_id}
    )

    # ---- audit log ----
    after = fetch_trip_snapshot(session=session, trip_id=new_trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='create_trip', target_table='trips',
        target_id=new_trip_id,
        before_state=None, after_state=after,
        changed_fields=list(after.keys()) if after else None,
        extra={
            'trip_type': trip_type,
            'fk_resolved': {
                'start': sp_fk, 'start_custom': sp_custom,
                'end': ep_fk, 'end_custom': ep_custom,
                'via': via_clean,
            },
            'unique_code': unique_code,
        },
        via=via,
    )

    if auto_commit:
        session.commit()

    return query_trip_by_id(new_trip_id, session=session)


def query_pending_dispatch(
    *,
    session,
    date_from: Optional[date] = None,
) -> ToolResult:
    """
    待派班次（沒指派司機 / 狀態為「待派」）

    沒指定日期 → 從今天起的所有未來。
    """
    where = ["(driver_id IS NULL OR status = '待派')"]
    params: dict = {}

    if date_from:
        where.append('date >= :date_from')
        params['date_from'] = date_from
    else:
        where.append("date >= CURRENT_DATE")

    sql = _SELECT_ALL + '\nWHERE ' + ' AND '.join(where)
    sql += '\nORDER BY date, time, trip_id\nLIMIT 100'

    rows = session.execute(text(sql), params).fetchall()
    if not rows:
        return ToolResult.fail("無待派班次 🎉")

    return ToolResult.success(
        data=[TripView.from_row(r) for r in rows],
        count=len(rows),
    )
