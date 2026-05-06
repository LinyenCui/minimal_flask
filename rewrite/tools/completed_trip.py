"""
completed_trips（過去態）查詢工具

設計：
  - 跟 trip.py 對應，但只查 completed_trips 表
  - 過去態「都已完成」，沒有 status filter
  - mutation 不在 Tier 1（Tier 2: update_fare, update_category）
  - 跨時間態（含「已完成」關鍵字）由 skill prompt 決定該 call 這裡還是 trip_query

工具：
  query_completed_trips         — 多條件查詢（list mode）
  query_completed_trip_by_id    — 單筆詳情（對應 legacy「查看 [id]」）
  aggregate_completed_trips     — 統計（aggregate mode，對應「加總」/「統計金額」）

⚠️ schema 來源：
  legacy modules/services/scheduler_service.py INSERT 反推（models.py 過時）。
  start_point/via_point/end_point 是 text（FK customers.short_name），不是 Integer。
"""

from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import text

from rewrite.tools.base import ToolResult


# ============================================================
# View 結構
# ============================================================

@dataclass
class CompletedTripView:
    """已完成班次展示用結構"""
    id: int

    date: Optional[date] = None
    start_point: Optional[str] = None
    via_point: Optional[str] = None
    end_point: Optional[str] = None

    meter_fare: Optional[int] = None
    extra_fare: Optional[int] = None
    actual_fare: Optional[int] = None  # app 層計算寫入；不一定等於 meter+extra

    category: Optional[str] = None
    driver_id: Optional[int] = None
    unique_code: Optional[str] = None
    trip_type: Optional[str] = None  # 'fixed' / 'temp'

    passenger_name: Optional[str] = None
    passenger_leave_reason: Optional[str] = None
    modification_reason: Optional[str] = None

    created_at: Optional[datetime] = None

    # 計算欄位
    computed_total: Optional[int] = None  # meter+extra（兩者都 NULL→None）
    has_fare: bool = False                # meter_fare 或 extra_fare 任一非 NULL
    is_leave: bool = False                # passenger_leave_reason 非空

    @classmethod
    def from_row(cls, row) -> "CompletedTripView":
        d = dict(row._mapping)

        meter = d.get('meter_fare')
        extra = d.get('extra_fare')
        if meter is None and extra is None:
            d['computed_total'] = None
        else:
            d['computed_total'] = (meter or 0) + (extra or 0)
        d['has_fare'] = meter is not None or extra is not None
        d['is_leave'] = bool(d.get('passenger_leave_reason'))

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
    SELECT id, date,
           start_point, via_point, end_point,
           meter_fare, extra_fare, actual_fare,
           category, driver_id,
           unique_code, trip_type,
           passenger_name, passenger_leave_reason,
           modification_reason, created_at
    FROM completed_trips
"""


def _build_filters(
    *,
    date_from: Optional[date],
    date_to: Optional[date],
    driver_id: Optional[int],
    customer_short_name: Optional[str],
    category: Optional[str],
    location: Optional[str],
    start_location: Optional[str] = None,
    end_location: Optional[str] = None,
    has_fare: Optional[bool] = None,
) -> tuple:
    """共用 WHERE 組合。回傳 (where_clause_list, params_dict)."""
    where: list = []
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
    if customer_short_name:
        # exact 比對 start/via/end 任一（跟 trip.query_trips 一致）
        where.append("(start_point = :sn OR via_point = :sn OR end_point = :sn)")
        params['sn'] = customer_short_name
    if location:
        # ILIKE 模糊比對任一欄（萬用通配，給「跟 X 有關」這類查詢用）
        where.append(
            "(start_point ILIKE :loc OR via_point ILIKE :loc OR end_point ILIKE :loc)"
        )
        params['loc'] = f'%{location}%'
    if start_location:
        # 「從 X 出發」精準比對 start_point
        where.append("start_point ILIKE :start_loc")
        params['start_loc'] = f'%{start_location}%'
    if end_location:
        # 「到 X」精準比對 end_point
        where.append("end_point ILIKE :end_loc")
        params['end_loc'] = f'%{end_location}%'
    if has_fare is True:
        where.append("(meter_fare IS NOT NULL OR extra_fare IS NOT NULL)")
    elif has_fare is False:
        where.append("(meter_fare IS NULL AND extra_fare IS NULL)")

    return where, params


# ============================================================
# 查詢函數
# ============================================================

def query_completed_trips(
    *,
    session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    driver_id: Optional[int] = None,
    customer_short_name: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    start_location: Optional[str] = None,
    end_location: Optional[str] = None,
    has_fare: Optional[bool] = None,
    limit: int = 80,
) -> ToolResult:
    """
    多條件查詢 completed_trips（過去態）。

    所有條件 AND。沒給就不限制。

    Args:
        date_from/date_to: 日期範圍
        driver_id: 司機 ID
        customer_short_name: 客戶簡稱（exact，比對 start/via/end 任一）
        category: 業務類別（'診所' / '東洋' / '臨時'）— 整批班次的分類，**不是地點**
        location: 模糊地點（ILIKE 任一 start/via/end）— 用於「跟 X 有關」「經過 X」這類
        start_location: 模糊地點（ILIKE 僅 start_point）— 用於「從 X 出發」「X 起點」
        end_location: 模糊地點（ILIKE 僅 end_point）— 用於「到 X」「X 結束」
        has_fare: True=已記錄車資 / False=未記錄 / None=不過濾
        limit: 上限筆數（預設 80，避免 LINE Flex 50KB 上限）
    """
    where, params = _build_filters(
        date_from=date_from, date_to=date_to,
        driver_id=driver_id,
        customer_short_name=customer_short_name,
        category=category, location=location,
        start_location=start_location, end_location=end_location,
        has_fare=has_fare,
    )

    sql = _SELECT_ALL
    if where:
        sql += '\nWHERE ' + ' AND '.join(where)
    sql += '\nORDER BY date, id\nLIMIT :limit'
    params['limit'] = limit

    rows = session.execute(text(sql), params).fetchall()
    if not rows:
        return ToolResult.fail("找不到符合條件的已完成班次")

    truncated = len(rows) >= limit
    return ToolResult.success(
        data=[CompletedTripView.from_row(r) for r in rows],
        count=len(rows),
        truncated=truncated,
        filters={k: str(v)[:50] for k, v in params.items() if k != 'limit'},
    )


def query_completed_trip_by_id(
    completed_trip_id: int,
    *,
    session,
) -> ToolResult:
    """
    單筆已完成班次詳情（對應 legacy「查看 [completed_trip_id]」）。

    ⚠️ 參數名 `completed_trip_id`，不是 `trip_id`：
       trips.trip_id 跟 completed_trips.id 是兩套不同的編號。
    """
    row = session.execute(
        text(f"{_SELECT_ALL} WHERE id = :id"),
        {'id': completed_trip_id}
    ).fetchone()
    if row:
        return ToolResult.success(data=CompletedTripView.from_row(row))
    return ToolResult.fail(f"找不到已完成班次 #{completed_trip_id}")


def aggregate_completed_trips(
    *,
    session,
    date_from: date,
    date_to: date,
    driver_id: Optional[int] = None,
    customer_short_name: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    start_location: Optional[str] = None,
    end_location: Optional[str] = None,
) -> ToolResult:
    """
    過去態車資統計（對應 legacy「統計金額」/「加總」模式）。

    Return data:
        {
            'total_count': int,        # 符合 filter 的總筆數
            'filled_count': int,       # meter_fare 或 extra_fare 任一非 NULL
            'unfilled_count': int,     # 兩欄都 NULL
            'sum_amount': int,         # NULL → 0 累加
        }

    SQL 直接對齊 legacy modules/services/date_range_query_service.py 的算法。
    """
    if not date_from or not date_to:
        return ToolResult.fail("aggregate 必須給 date_from 與 date_to")

    where, params = _build_filters(
        date_from=date_from, date_to=date_to,
        driver_id=driver_id,
        customer_short_name=customer_short_name,
        category=category, location=location,
        start_location=start_location, end_location=end_location,
        has_fare=None,
    )

    sql = """
        SELECT
            COUNT(*) AS total_count,
            COUNT(CASE
                WHEN meter_fare IS NOT NULL OR extra_fare IS NOT NULL THEN 1
            END) AS filled_count,
            COUNT(CASE
                WHEN meter_fare IS NULL AND extra_fare IS NULL THEN 1
            END) AS unfilled_count,
            COALESCE(SUM(CASE
                WHEN meter_fare IS NULL AND extra_fare IS NULL THEN 0
                WHEN meter_fare IS NULL THEN extra_fare
                WHEN extra_fare IS NULL THEN meter_fare
                ELSE meter_fare + extra_fare
            END), 0) AS sum_amount
        FROM completed_trips
    """
    if where:
        sql += '\nWHERE ' + ' AND '.join(where)

    row = session.execute(text(sql), params).fetchone()
    if not row or row.total_count == 0:
        return ToolResult.fail("範圍內沒有已完成班次")

    return ToolResult.success(
        data={
            'total_count': int(row.total_count),
            'filled_count': int(row.filled_count or 0),
            'unfilled_count': int(row.unfilled_count or 0),
            'sum_amount': int(row.sum_amount or 0),
        },
        filters={k: str(v)[:50] for k, v in params.items()},
    )
