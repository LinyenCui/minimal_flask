"""
fixed_schedules（未來態）atomic tools — spec §3.3

工具：
  query_fixed_schedule         — 多條件查詢
  get_fixed_schedule_by_id     — 單筆 ID
  update_fixed_schedule        — 部分更新（白名單）
  apply_fixed_schedule_leave   — 長期請假（status='請假' + note + surcharge）
  restore_fixed_schedule       — 從請假恢復（status='準備'）

⚠️ 跟 trips 不同：
  - 沒有 30 分鐘鎖（模板層級，不是執行層級）
  - 沒有「三層障眼法」— 請假時 status 直接變 '請假'
  - driver_id 是 varchar（legacy schema，不改）

import_fixed_schedules（每週匯入到 trips）暫不做 — 用戶決定走 sandbox
legacy 路徑，等 v0.2 再考慮重做。
"""
from dataclasses import dataclass, asdict
from datetime import datetime, time
from typing import Any, List, Optional

from sqlalchemy import text

from rewrite.tools.base import (
    ToolResult,
    write_audit,
    diff_fields,
)
from rewrite.tools.leave_guard import (
    NEEDS_CONFIRM_KEY,
    is_zero_surcharge,
    warning_text as zero_surcharge_warning,
)


# ============================================================
# View 結構
# ============================================================

# 狀態 → emoji
STATUS_EMOJI = {
    '準備': '🟢',
    '請假': '🏷️',
    '註銷': '❌',
}


@dataclass
class FixedScheduleView:
    id: int
    route_number: Optional[str] = None
    departure_time: Optional[time] = None
    start_point: Optional[str] = None
    via_point: Optional[str] = None
    end_point: Optional[str] = None
    base_fare: Optional[int] = None
    surcharge: Optional[int] = None
    total_fare: Optional[int] = None
    category: Optional[str] = None
    driver_id: Optional[str] = None     # legacy: varchar
    direction: Optional[str] = None     # 來 / 回
    status: Optional[str] = None
    passenger_name: Optional[str] = None   # 乘客/接送順序（008 起；note 只留請假原因）
    note: Optional[str] = None
    modified_by: Optional[str] = None
    modification_time: Optional[datetime] = None

    # 計算欄位
    status_emoji: str = ''

    @classmethod
    def from_row(cls, row) -> "FixedScheduleView":
        d = dict(row._mapping)
        d['status_emoji'] = STATUS_EMOJI.get(d.get('status') or '', '⚪')
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    def to_dict(self) -> dict:
        return asdict(self)

    def short_route(self) -> str:
        parts = [self.start_point or '?']
        if self.via_point:
            parts.append(f"經{self.via_point}")
        parts.append(self.end_point or '?')
        return '→'.join(p for p in parts if p)


# ============================================================
# 共用 SELECT
# ============================================================

_SELECT_ALL = """
    SELECT id, route_number, departure_time,
           start_point, via_point, end_point,
           base_fare, surcharge, total_fare,
           category, driver_id, direction, status, note, passenger_name,
           modified_by, modification_time
    FROM fixed_schedules
"""


# ============================================================
# 查詢
# ============================================================

def query_fixed_schedule(
    *,
    session,
    customer_short_name: Optional[str] = None,
    category: Optional[str] = None,
    driver_id: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    route_number: Optional[str] = None,
    limit: int = 100,
) -> ToolResult:
    """
    多條件查詢固定班次（模板）。

    customer_short_name：起、途、終 任一含此 → 命中
    """
    where: list = []
    params: dict = {}

    if customer_short_name:
        # via_point 多段可能用 '+' 或 '→' 分隔（'中華南路+新建路'、'中華南路→新建路' 都有），用 string_to_array 拆
        where.append(
            "(start_point = :sn OR end_point = :sn "
            "OR :sn = ANY(regexp_split_to_array(COALESCE(via_point, ''), '\\s*[+→]\\s*')))"
        )
        params['sn'] = customer_short_name
    if category:
        where.append("category = :category")
        params['category'] = category
    if driver_id is not None:
        where.append("driver_id = :driver_id")
        params['driver_id'] = str(driver_id)  # legacy varchar
    if direction:
        where.append("direction = :direction")
        params['direction'] = direction
    if status:
        where.append("status = :status")
        params['status'] = status
    if route_number:
        where.append("route_number = :route_number")
        params['route_number'] = route_number

    sql = _SELECT_ALL
    if where:
        sql += '\nWHERE ' + ' AND '.join(where)
    sql += '\nORDER BY departure_time, id\nLIMIT :limit'
    params['limit'] = limit

    rows = session.execute(text(sql), params).fetchall()
    if not rows:
        return ToolResult.fail("找不到符合條件的固定班次")

    return ToolResult.success(
        data=[FixedScheduleView.from_row(r) for r in rows],
        count=len(rows),
        filters={k: str(v)[:50] for k, v in params.items() if k != 'limit'},
    )


def get_fixed_schedule_by_id(schedule_id: int, *, session) -> ToolResult:
    row = session.execute(
        text(f"{_SELECT_ALL} WHERE id = :id"),
        {'id': schedule_id},
    ).fetchone()
    if row:
        return ToolResult.success(data=FixedScheduleView.from_row(row))
    return ToolResult.fail(f"找不到固定班次 #{schedule_id}")


# ============================================================
# 修改（更新模板）
# ============================================================

# 白名單：可更新欄位
_UPDATABLE_FIELDS = {
    'route_number',
    'departure_time',
    'start_point',
    'via_point',
    'end_point',
    'base_fare',
    'surcharge',
    'total_fare',
    'category',
    'driver_id',
    'direction',
    'note',
    'passenger_name',
}


def _fetch_schedule_snapshot(*, session, schedule_id: int) -> Optional[dict]:
    row = session.execute(
        text("SELECT * FROM fixed_schedules WHERE id = :id"),
        {'id': schedule_id},
    ).fetchone()
    return dict(row._mapping) if row else None


def update_fixed_schedule(
    *,
    session,
    schedule_id: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
    **fields,
) -> ToolResult:
    """
    部分更新固定班次（白名單）。沒給的欄位不動。

    R-6 audit：寫 fixed_schedule_update。
    """
    before = _fetch_schedule_snapshot(session=session, schedule_id=schedule_id)
    if not before:
        return ToolResult.fail(f"找不到固定班次 #{schedule_id}")

    invalid = set(fields) - _UPDATABLE_FIELDS
    if invalid:
        return ToolResult.fail(f"不允許更新的欄位：{sorted(invalid)}")

    # 過濾沒實際變動 + 沒給的。
    # 清空語意（與 trips update_trip_route 慣例一致）：
    #   None = 沒給，不動；空字串 = 清空該欄（僅限可清空白名單）→ 存 NULL
    _clearable = {'via_point', 'driver_id', 'direction', 'note', 'passenger_name'}
    changes: dict = {}
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            if k not in _clearable:
                continue   # 必要欄位不接受清空
            v = None       # 清空 → NULL
        if before.get(k) != v:
            changes[k] = v

    if not changes:
        return ToolResult.fail("沒有實際變動")

    # 動態 SET
    sets = [f"{k} = :{k}" for k in changes]
    sets.append("modification_time = CURRENT_TIMESTAMP")
    if user_name or user_id:
        sets.append("modified_by = :modified_by")
        changes['modified_by'] = user_name or user_id

    sql = f"UPDATE fixed_schedules SET {', '.join(sets)} WHERE id = :id"
    params = {**changes, 'id': schedule_id}
    session.execute(text(sql), params)

    after = _fetch_schedule_snapshot(session=session, schedule_id=schedule_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='update_fixed_schedule', target_table='fixed_schedules',
        target_id=schedule_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        extra={'fields_set': list(changes.keys())},
        via=via,
    )

    if auto_commit:
        session.commit()
    return get_fixed_schedule_by_id(schedule_id, session=session)


# ============================================================
# 長期請假 / 恢復
# ============================================================

def apply_fixed_schedule_leave(
    *,
    session,
    schedule_id: int,
    reason: str,
    surcharge: Optional[int] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
    confirm_zero_surcharge: bool = False,
) -> ToolResult:
    """
    固定班次長期請假。

    跟 trips 的 passenger_leave 不同（沒三層障眼法）：
      - status = '請假'（直接改）
      - note = reason（請假原因）
      - surcharge = 給的值

    用戶情境：客戶長期出國/住院，固定班次模板暫停產出 trip rows。

    ⚠️ 加成沒填 / 0 / -0 → 擋下要確認（同 trip.passenger_leave）。
       模板這層特別嚴重：錯一張，之後**每週匯入都會複製**成 N 筆 0 元請假班次。
       註：不像 trips 有 modification_reason 可以留痕，這裡唯一的文字欄是 note，
       而 note 會被匯入原封複製成 trip 的 passenger_leave_reason，
       所以確認標記不寫進 note（避免污染每一筆匯出的班次），只靠 audit log 記錄。
    """
    if not reason or not reason.strip():
        return ToolResult.fail("請假原因不可空")
    if surcharge is not None and not isinstance(surcharge, int):
        return ToolResult.fail("加成必須是整數（通常負，如 -50）")

    before = _fetch_schedule_snapshot(session=session, schedule_id=schedule_id)
    if not before:
        return ToolResult.fail(f"找不到固定班次 #{schedule_id}")

    if before.get('status') == '請假':
        return ToolResult.fail(
            f"固定班次 #{schedule_id} 已是請假狀態，原因：{before.get('note') or '無'}"
        )

    # 🚧 沒扣款的請假要先確認（擺在存在性/狀態檢查之後）
    if is_zero_surcharge(surcharge) and not confirm_zero_surcharge:
        return ToolResult.fail(
            zero_surcharge_warning(
                target=f"固定班次 #{schedule_id}",
                reason=reason.strip(),
                surcharge=surcharge,
                how_to_confirm='打「確認執行」',
            ) + '\n\n※ 模板請假會在每週匯入時複製成該週所有班次，錯了會一直複製下去。',
            **{NEEDS_CONFIRM_KEY: True}, schedule_id=schedule_id,
            reason=reason.strip(), surcharge=surcharge,
        )
    final_surcharge = 0 if surcharge is None else surcharge

    session.execute(
        text("""
            UPDATE fixed_schedules
            SET status = '請假',
                note = :reason,
                surcharge = :surcharge,
                modified_by = :modified_by,
                modification_time = CURRENT_TIMESTAMP
            WHERE id = :id
        """),
        {
            'reason': reason.strip(),
            'surcharge': surcharge,
            'modified_by': user_name or user_id,
            'id': schedule_id,
        },
    )

    after = _fetch_schedule_snapshot(session=session, schedule_id=schedule_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='apply_fixed_schedule_leave', target_table='fixed_schedules',
        target_id=schedule_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason.strip(),
        extra={'surcharge': surcharge},
        via=via,
    )

    if auto_commit:
        session.commit()
    return get_fixed_schedule_by_id(schedule_id, session=session)


def restore_fixed_schedule(
    *,
    session,
    schedule_id: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    從請假/註銷恢復為「準備」狀態，並一併清 note + surcharge（NULL）。

    為什麼一律清 surcharge：
      fixed_schedules 是「每週匯入到 trips 的模板」，模板上的 surcharge
      99% 是請假設的負加成（避免每週匯入後再一筆一筆請假）。模板恢復成
      「準備」就代表客戶恢復服務，殘留 -50 會在下次匯入時跟著進 trips
      變成 trip.extra_fare=-50 → 帳目錯。

      用戶確認：固定班次 restore 一律清 surcharge=NULL。
      （跟 trips.restore_to_ready 不同 — trips 的 extra_fare 可能是
       等候費等正常加成，所以 trips 那邊只清負數、保留正數。）
    """
    before = _fetch_schedule_snapshot(session=session, schedule_id=schedule_id)
    if not before:
        return ToolResult.fail(f"找不到固定班次 #{schedule_id}")

    if before.get('status') == '準備':
        return ToolResult.fail(f"固定班次 #{schedule_id} 已是準備狀態")

    session.execute(
        text("""
            UPDATE fixed_schedules
            SET status = '準備',
                note = NULL,
                surcharge = NULL,
                modified_by = :modified_by,
                modification_time = CURRENT_TIMESTAMP
            WHERE id = :id
        """),
        {'modified_by': user_name or user_id, 'id': schedule_id},
    )

    after = _fetch_schedule_snapshot(session=session, schedule_id=schedule_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='restore_fixed_schedule', target_table='fixed_schedules',
        target_id=schedule_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        via=via,
    )

    if auto_commit:
        session.commit()
    return get_fixed_schedule_by_id(schedule_id, session=session)


# ============================================================
# Delete — 刪除固定班次模板（整備層;刪它不需先刪 trips）
# ============================================================

def delete_fixed_schedule(
    *,
    session,
    schedule_id: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    刪除固定班次（整備層模板，硬刪除）。

    整備層綁定原則:刪它**不需先刪 trips**——已匯出的 trips 是現在態獨立實例,
    與模板脫鉤,刪模板後既有 trips 照常存在,只是未來不再從此模板匯入。
    刪掉後其 start/end 客戶若不再被其他固定班次引用,該客戶即可被刪
    （delete_customer 的 fixed_schedules 安全閘會通過）。
    """
    before = _fetch_schedule_snapshot(session=session, schedule_id=schedule_id)
    if not before:
        return ToolResult.fail(f"找不到固定班次 #{schedule_id}")

    session.execute(
        text("DELETE FROM fixed_schedules WHERE id = :id"),
        {'id': schedule_id},
    )
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='delete_fixed_schedule', target_table='fixed_schedules',
        target_id=schedule_id,
        before_state=before, after_state=None,
        changed_fields=list(before.keys()) if before else None,
        via=via,
    )
    if auto_commit:
        session.commit()
    return ToolResult.success(data={
        'deleted_id': schedule_id,
        'start_point': before.get('start_point'),
        'end_point': before.get('end_point'),
        'route_number': before.get('route_number'),
    })


# ============================================================
# Create — 新增固定班次模板（legacy 沒對應，rewrite 補齊）
# ============================================================

VALID_CATEGORIES = ('診所', '東洋', '臨時')
VALID_DIRECTIONS = ('來', '回', '單')

def create_fixed_schedule(
    *,
    session,
    route_number: str,
    departure_time: time,
    start_point: str,
    category: str,
    via_point: Optional[str] = None,
    end_point: Optional[str] = None,
    base_fare: Optional[int] = None,
    surcharge: Optional[int] = None,
    driver_id: Optional[str] = None,
    direction: Optional[str] = None,
    note: Optional[str] = None,
    passenger_name: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """新增固定班次模板（legacy 沒對應 UI，本地手動 INSERT 痛點）。

    必填:
        route_number: 含星期幾的字串（'1234567' 表週一到週日）
                      legacy import_handler 用 LIKE '%{weekday}%' 過濾
        departure_time: 出發時間
        start_point: 起點客戶簡稱
        category: 診所 / 東洋 / 臨時

    選填: via_point/end_point/base_fare/surcharge/driver_id/direction/note/passenger_name
    （note 只放請假原因等備註；乘客/接送順序放 passenger_name — 不會進請款報表）

    自動: status='準備'、modified_by、modification_time
    """
    # ---- 驗證 ----
    if not route_number or not route_number.strip():
        return ToolResult.fail("route_number 必填（含星期幾數字，如 '147' 表週一週四週日）")
    rn = route_number.strip()
    if not rn.isdigit() or any(c not in '1234567' for c in rn):
        return ToolResult.fail(f"route_number 只能含 1-7 數字（給的是 {rn!r}）")

    if not departure_time:
        return ToolResult.fail("departure_time 必填")

    if not start_point or not start_point.strip():
        return ToolResult.fail("start_point 必填")

    if not category or category not in VALID_CATEGORIES:
        return ToolResult.fail(
            f"category 必填且必須是 {VALID_CATEGORIES} 之一（給的是 {category!r}）"
        )

    if direction is not None and direction not in VALID_DIRECTIONS:
        return ToolResult.fail(
            f"direction 必須是 {VALID_DIRECTIONS} 之一（給的是 {direction!r}）"
        )

    if base_fare is not None and not isinstance(base_fare, int):
        return ToolResult.fail("base_fare 必須是整數或 None")
    if surcharge is not None and not isinstance(surcharge, int):
        return ToolResult.fail("surcharge 必須是整數或 None")

    # ---- INSERT ----
    result = session.execute(text("""
        INSERT INTO fixed_schedules (
            route_number, departure_time,
            start_point, via_point, end_point,
            base_fare, surcharge,
            category, driver_id, direction,
            note, passenger_name, status,
            modified_by, modification_time
        ) VALUES (
            :route_number, :departure_time,
            :start_point, :via_point, :end_point,
            :base_fare, :surcharge,
            :category, :driver_id, :direction,
            :note, :passenger_name, '準備',
            :modified_by, CURRENT_TIMESTAMP
        )
        RETURNING id
    """), {
        'route_number': rn,
        'departure_time': departure_time,
        'start_point': start_point.strip(),
        'via_point': (via_point or '').strip() or None,
        'end_point': (end_point or '').strip() or None,
        'base_fare': base_fare,
        'surcharge': surcharge,
        'category': category,
        'driver_id': (driver_id or '').strip() or None if isinstance(driver_id, str) else driver_id,
        'direction': direction,
        'note': (note or '').strip() or None,
        'passenger_name': (passenger_name or '').strip() or None,
        'modified_by': user_name or user_id,
    })
    new_id = result.fetchone()[0]

    # audit log
    after = _fetch_schedule_snapshot(session=session, schedule_id=new_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='create_fixed_schedule',
        target_table='fixed_schedules', target_id=new_id,
        before_state=None, after_state=after,
        changed_fields=list(after.keys()) if after else None,
        extra={
            'route_number': rn, 'category': category,
            'start_point': start_point,
        },
        via=via,
    )

    if auto_commit:
        session.commit()
    return get_fixed_schedule_by_id(new_id, session=session)
