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
    '已完成': '☑️',   # 灰勾框（避免跟「準備」🟢 混淆）— 多數情況下「已完成」會被列表過濾不顯示
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

    # 預約班次（trip_type='temp'）的真實地點 — 避開 start_point 對 customer
    # short_name 的約束（DB 寫「臨時地點」placeholder，custom_* 才是真值）
    custom_start_point: Optional[str] = None
    custom_via_point: Optional[str] = None
    custom_end_point: Optional[str] = None

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

    def display_route(self) -> tuple:
        """回傳該顯示的 (起點, 途經, 終點)。

        - trip_type='temp' → 用 custom_*（真實地址；start_point 在 DB 是「臨時地點」placeholder）
        - trip_type='fixed' / 其他 → 直接用 start_point / via_point / end_point
        """
        if self.trip_type == 'temp':
            return (
                self.custom_start_point or self.start_point,
                self.custom_via_point or self.via_point,
                self.custom_end_point or self.end_point,
            )
        return (self.start_point, self.via_point, self.end_point)

    def short_route(self) -> str:
        """簡短路線：起點→終點（含途經括號）"""
        sp, vp, ep = self.display_route()
        parts = [sp or '?']
        if vp:
            parts.append(f"經{vp}")
        parts.append(ep or '?')
        return '→'.join(p for p in parts if p)


# ============================================================
# 共用 SELECT
# ============================================================

_SELECT_ALL = """
    SELECT trip_id, date, time, start_point, via_point, end_point,
           custom_start_point, custom_via_point, custom_end_point,
           driver_id, meter_fare, extra_fare, actual_fare, category,
           status, passenger_leave_reason, passenger_name,
           modified_by, modification_reason, modification_time,
           fixed_trip_id, week_number, trip_type, unique_code
    FROM trips
"""


# ============================================================
# 查詢函數
# ============================================================

def _coerce_time_arg(v) -> Optional[time]:
    """AI 傳的時間字串 → time。接受 '09:00' / '9:00' / '0900' / '9'。

    解析失敗 raise ValueError（呼叫端轉 ToolResult.fail）。
    """
    if v is None or isinstance(v, time):
        return v
    s = str(v).strip().replace('：', ':')
    import re as _re
    m = _re.match(r'^(\d{1,2})(?::?(\d{2}))?$', s)
    if not m:
        raise ValueError(f"時間格式看不懂：{v}（請用 09:00 格式）")
    hh, mm = int(m.group(1)), int(m.group(2) or 0)
    if hh > 23 or mm > 59:
        raise ValueError(f"時間格式看不懂：{v}（請用 09:00 格式）")
    return time(hh, mm)


def query_trips(
    *,
    session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    driver_id: Optional[int] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    customer_short_name: Optional[str] = None,
    start_location: Optional[str] = None,
    end_location: Optional[str] = None,
    time_from: Optional[time] = None,
    time_to: Optional[time] = None,
    exclude_status: Optional[List[str]] = None,
    limit: int = 200,
) -> ToolResult:
    """
    多條件查詢 trips（現在態）。

    所有條件 AND。沒給就不限制。

    customer_short_name：起、途、終 任一含此 → 命中（用於「龍埔街今天的班次」這類查詢）
    start_location / end_location：方向性地點（ILIKE 含），「從 X 出發」「到 X」用
    time_from / time_to：執行時間篩選（「九點之後」→ time_from=09:00）
    exclude_status：要排除的狀態列表（例：排除「已完成」）
    """
    try:
        time_from = _coerce_time_arg(time_from)
        time_to = _coerce_time_arg(time_to)
    except ValueError as e:
        return ToolResult.fail(str(e))

    where = []
    params: dict = {}

    if date_from:
        where.append('date >= :date_from')
        params['date_from'] = date_from
    if date_to:
        where.append('date <= :date_to')
        params['date_to'] = date_to
    if time_from is not None:
        where.append('time >= :time_from')
        params['time_from'] = time_from
    if time_to is not None:
        where.append('time <= :time_to')
        params['time_to'] = time_to
    if start_location:
        where.append('start_point ILIKE :sl')
        params['sl'] = f'%{start_location}%'
    if end_location:
        where.append('end_point ILIKE :el')
        params['el'] = f'%{end_location}%'
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
        # via_point 可能是 '+'-joined 多段（例如 '中華南路+新建路'），
        # 用 string_to_array 拆開後檢查任一段命中。start/end 是單值，照舊 exact match。
        where.append(
            "(start_point = :sn OR end_point = :sn "
            "OR :sn = ANY(string_to_array(COALESCE(via_point, ''), '+')))"
        )
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

    # ⚠️ 指派/換司機不寫 modification_reason（2026-07-31 用戶定調）：
    # 純調度動作、不影響車資，卻會被帶進請款報表的說明欄污染版面。
    # 完整軌跡（誰、何時、前後司機）已由 write_audit 記在 audit_log。
    session.execute(text("""
        UPDATE trips SET
            driver_id = :driver_id,
            status = :status,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {
        'driver_id': driver_id, 'status': new_status,
        'who': user_name or user_id, 'id': trip_id
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
    # 同 assign_driver：撤銷指派是調度動作，不進 modification_reason（audit_log 有記）
    session.execute(text("""
        UPDATE trips SET
            driver_id = NULL,
            status = '待派',
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {'who': user_name or user_id, 'id': trip_id})

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


VALID_TRIP_CATEGORIES = ('診所', '東洋', '臨時')


@require_modifiable_window(allow_in_lock=True)  # 鎖內也可（key 錯類別不影響執行）
def update_trip_category(
    *,
    session,
    trip_id: int,
    new_category: str,
    reason: str = '',
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    修改現在態班次類別（key 錯時用，跟 completed_trip 對稱）。

    legacy 沒這個工具（只有過去態的 handle_modify_category）；rewrite 補齊。

    Args:
        new_category: '診所' / '東洋' / '臨時'
        reason: 修改原因（選填，空值記「修改」）

    R-5 鎖：allow_in_lock=True（改類別不影響時間執行）
    """
    # 現在態不進報表，reason 不強制（防改錯靠機制層確認卡）；空值記通用「修改」
    reason = (reason or '').strip() or '修改' 
    if not new_category or not new_category.strip():
        return ToolResult.fail("new_category 不可空")
    new_category = new_category.strip()
    if new_category not in VALID_TRIP_CATEGORIES:
        return ToolResult.fail(
            f"無效的類別 '{new_category}'，必須是：{', '.join(VALID_TRIP_CATEGORIES)}"
        )

    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")

    old_category = before.get('category')
    if old_category == new_category:
        return ToolResult.fail(
            f"班次 #{trip_id} 類別已是『{new_category}』，無需修改"
        )

    note = f"改類別: {old_category}→{new_category} ({reason.strip()})"
    new_mod = _bump_modification_reason(
        before.get('modification_reason'), note,
    )

    session.execute(text("""
        UPDATE trips SET
            category = :cat,
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {
        'cat': new_category,
        'mod': new_mod,
        'who': user_name or user_id,
        'id': trip_id,
    })

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='update_trip_category',
        target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason.strip(),
        extra={'old_category': old_category, 'new_category': new_category},
        via=via,
    )

    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


@require_modifiable_window(allow_in_lock=False)  # 改時間屬時間敏感 → 30 分鐘鎖內照擋
def update_trip_time(
    *,
    session,
    trip_id: int,
    new_time: str,
    reason: str = '',
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    修改現在態班次「時間」（同日改時段）。

    範圍刻意只改 time：不改 date —— 改日期會連動 week_number(isocalendar)
    與 unique_code(T_{id}_{YYYYMMDD})，留待後續 slice 穩做。

    不影響註銷：status in ('已完成','註銷') 直接拒絕（與 cancel_trip 對稱），
    註銷態班次完全不被本工具觸碰；本函式不讀寫 status，純改 time。

    R-5 鎖：allow_in_lock=False（時間敏感，30 分鐘鎖內擋）
    R-6 audit：寫 'update_trip_time'
    """
    # 現在態不進報表，reason 不強制（防改錯靠機制層確認卡）；空值記通用「修改」
    reason = (reason or '').strip() or '修改' 
    if not new_time or not str(new_time).strip():
        return ToolResult.fail("new_time 不可空")
    raw = str(new_time).strip()
    try:
        parts = [int(x) for x in raw.split(':')]
        if len(parts) < 2:
            raise ValueError
        parsed = time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
    except (ValueError, IndexError):
        return ToolResult.fail(f"時間格式錯（要 HH:MM）：{raw!r}")

    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")
    status = before.get('status')
    if status == '已完成':
        return ToolResult.fail(f"班次 #{trip_id} 已完成，無法改時間")
    if status == '註銷':
        return ToolResult.fail(
            f"班次 #{trip_id} 為註銷狀態，無法改時間（如要恢復請先『改回準備』）"
        )

    old_time = before.get('time')
    old_hm = str(old_time)[:5] if old_time is not None else None
    new_hm = parsed.strftime('%H:%M')
    if old_hm == new_hm:
        return ToolResult.fail(f"班次 #{trip_id} 時間已是 {new_hm}，無需修改")

    note = f"改時間: {old_hm}→{new_hm} ({reason.strip()})"
    new_mod = _bump_modification_reason(before.get('modification_reason'), note)

    session.execute(text("""
        UPDATE trips SET
            time = :t,
            modification_reason = :mod,
            modified_by = :who,
            modification_time = CURRENT_TIMESTAMP
        WHERE trip_id = :id
    """), {'t': parsed, 'mod': new_mod, 'who': user_name or user_id, 'id': trip_id})

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='update_trip_time', target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason.strip(),
        extra={'old_time': old_hm, 'new_time': new_hm},
        via=via,
    )

    if auto_commit:
        session.commit()
    return query_trip_by_id(trip_id, session=session)


@require_modifiable_window(allow_in_lock=True)  # 改地點不影響執行時間,鎖內可
def update_trip_route(
    *,
    session,
    trip_id: int,
    new_start: Optional[str] = None,
    new_end: Optional[str] = None,
    new_via: Optional[str] = None,
    reason: str = '',
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    修改現在態班次「起點 / 終點 / 途經」。

    現在態鬆綁原則：trips 起終點對 customers 的 FK 已移除,故可改成
    「南紡購物中心」這類**非客戶地點**。寫入依 trip_type 決定欄位,確保
    display_route() 正確：
      - trip_type='temp'：display_route 讀 custom_*，故寫 custom_start/via/end_point
        （並同步 start/via/end_point 供 query 過濾，沿用 create_trip 雙寫精神）
      - 其他（fixed 等）：display_route 讀 start/via/end_point，直接寫該欄

    途經 new_via 語意（trips 是單欄 via_point，與未來態 fixed_schedules 的途經
    規劃無關）：
      - None（未傳）→ 不動途經
      - 空字串 / '無' / 'null' / 'none' → 清空途經（設 NULL）
      - 其他 → 設為該途經點

    只動本班次(實例覆寫),不影響模板與其他班次。
    已完成 / 註銷 拒絕。reason 選填。R-5 鎖：allow_in_lock=True。
    """
    # 現在態不進報表，reason 不強制（防改錯靠機制層確認卡）；空值記通用「修改」
    reason = (reason or '').strip() or '修改' 
    ns = (new_start or '').strip()
    ne = (new_end or '').strip()
    # 途經三態：未傳(None)=不動;傳了=要改(可能設值或清空)
    via_touched = new_via is not None
    nv_raw = (new_via or '').strip()
    via_clear = via_touched and nv_raw.lower() in ('', '無', 'null', 'none', '清空', '取消')
    nv = '' if via_clear else nv_raw
    if not ns and not ne and not via_touched:
        return ToolResult.fail("請至少提供 new_start / new_end / new_via 其一")

    before = fetch_trip_snapshot(session=session, trip_id=trip_id)
    if not before:
        return ToolResult.fail(f"找不到班次 #{trip_id}")
    status = before.get('status')
    if status == '已完成':
        return ToolResult.fail(f"班次 #{trip_id} 已完成，無法改起終點")
    if status == '註銷':
        return ToolResult.fail(
            f"班次 #{trip_id} 為註銷狀態，無法改起終點（如要恢復請先『改回準備』）"
        )

    is_temp = before.get('trip_type') == 'temp'
    sets, params, notes = [], {}, []

    if ns:
        old_sp = (before.get('custom_start_point') if is_temp else None) or before.get('start_point')
        if is_temp:
            sets.append("start_point = :sp")
            sets.append("custom_start_point = :sp")
        else:
            sets.append("start_point = :sp")
        params['sp'] = ns
        notes.append(f"起點 {old_sp or '?'}→{ns}")
    if ne:
        old_ep = (before.get('custom_end_point') if is_temp else None) or before.get('end_point')
        if is_temp:
            sets.append("end_point = :ep")
            sets.append("custom_end_point = :ep")
        else:
            sets.append("end_point = :ep")
        params['ep'] = ne
        notes.append(f"終點 {old_ep or '?'}→{ne}")
    if via_touched:
        old_vp = (before.get('custom_via_point') if is_temp else None) or before.get('via_point')
        new_vp = None if via_clear else nv   # 清空→NULL
        if is_temp:
            sets.append("via_point = :vp")
            sets.append("custom_via_point = :vp")
        else:
            sets.append("via_point = :vp")
        params['vp'] = new_vp
        notes.append(f"途經 {old_vp or '無'}→{new_vp or '無'}")

    note = f"改路線: {', '.join(notes)} ({reason.strip()})"
    new_mod = _bump_modification_reason(before.get('modification_reason'), note)
    sets.append("modification_reason = :mod")
    sets.append("modified_by = :who")
    sets.append("modification_time = CURRENT_TIMESTAMP")
    params['mod'] = new_mod
    params['who'] = user_name or user_id
    params['id'] = trip_id

    session.execute(
        text(f"UPDATE trips SET {', '.join(sets)} WHERE trip_id = :id"),
        params,
    )

    after = fetch_trip_snapshot(session=session, trip_id=trip_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='update_trip_route', target_table='trips', target_id=trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason.strip(),
        extra={'new_start': ns or None, 'new_end': ne or None,
               'new_via': ('(清空)' if via_clear else nv) if via_touched else None},
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
        # modification_reason 只記「對班次的修改」;建立不是修改(建立已由
        # audit log action_type='create_trip' 記錄),故初始 NULL,與匯入固定
        # 班次一致。首筆真實修改由 _bump_modification_reason 自動編號為 [1]。
        'mod_reason': None,
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
