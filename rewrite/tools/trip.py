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
