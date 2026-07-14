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
  query_reconciliation_text     — 對帳單純文字（直列、可複製/轉傳跟司機對帳）

⚠️ schema 來源：
  legacy modules/services/scheduler_service.py INSERT 反推（models.py 過時）。
  start_point/via_point/end_point 是 text（FK customers.short_name），不是 Integer。
"""

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Optional, List
from sqlalchemy import text

from rewrite.tools.base import (
    ToolResult,
    write_audit,
    diff_fields,
)
# legacy 共用：modification_reason 累加 + modified_by/time 寫入
from modules.utils.modification_utils import append_modification_reason
from modules.utils.taiwan_time import get_taiwan_time
# ✅ 日期解析唯一來源（禁自建）— 對帳 tool 的 str 日期 coerce 用
from modules.utils.unified_date_parser import UnifiedDateParser
# 過去態唯讀受護欄查詢層編譯器（spec docs/specs/04）
from rewrite.tools.query_spec import compile_query_spec, QuerySpecError, MAX_LIMIT as _SPEC_MAX_LIMIT

# 過去態 category 受限值（對齊 legacy handle_modify_category）
VALID_CATEGORIES = ('診所', '東洋', '臨時')


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
    has_fare: bool = False                # 車資總額(錶價+加成)>0（0/空=未記錄）
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
        d['has_fare'] = (d['computed_total'] or 0) > 0  # 總額>0 才算已記錄（0/空=未記錄）
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

# 明細欄組（給受護欄查詢層 detail 模式用，與 _SELECT_ALL 同欄，避免漂移）
_DETAIL_COLUMNS = _SELECT_ALL.split('SELECT', 1)[1].split('FROM', 1)[0].strip()


@dataclass
class GroupedStatView:
    """受護欄查詢層 grouped 模式結果（給 render_grouped_stat_card 用）。"""
    group_cols: List[str]   # 分組欄名，如 ['driver_id']
    agg_cols: List[str]     # 聚合輸出名，如 ['count', '金額']
    rows: List[dict]        # [{'driver_id':5386,'count':124,'金額':141380}, ...]
    subtitle: Optional[str] = None
    agg_kinds: Optional[dict] = None   # {聚合名: 'count'|'money'}，給 render 決定 筆/元


def _coerce_int(v):
    """AI 偶爾把 integer 參數傳成字串 → 轉 int；轉不動回 None。"""
    if isinstance(v, str):
        s = v.strip().lstrip('-')
        return int(v) if s.isdigit() else None
    return v


def _coerce_date(v):
    """AI 傳字串日期 → date（走 unified_date_parser，禁自建解析）；轉不動回 None。"""
    if v is None or isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return UnifiedDateParser.parse(v)
        except Exception:
            return None
    return None


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
    fare_amount: Optional[int] = None,
    fare_min: Optional[int] = None,
    fare_max: Optional[int] = None,
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
        # via_point 可能是 '+'-joined 多段（例如 '中華南路+新建路'），用 string_to_array 拆。
        # start/end 是單值，照舊 exact match（跟 trip.query_trips 一致）。
        where.append(
            "(start_point = :sn OR end_point = :sn "
            "OR :sn = ANY(string_to_array(COALESCE(via_point, ''), '+')))"
        )
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
    # 「已記錄車資」= 車資總額(錶價+加成)>0。錶價 0 或 NULL 都算「未記錄」——
    # 0 是未填的預設值,不是真的免費班次(用戶回報:加總把 0 元班次算成已記錄是錯的)。
    if has_fare is True:
        where.append("(COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0)) > 0")
    elif has_fare is False:
        where.append("(COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0)) <= 0")

    # 車資總額 = COALESCE(錶價,0)+COALESCE(加成,0)。fare_amount 精確、fare_min/max 範圍。
    # schema 宣告 integer 但 AI 偶爾仍傳字串 → 在共用 builder 統一 coerce（list/aggregate 都受惠）
    _TOTAL = "(COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0))"
    fare_amount = _coerce_int(fare_amount)
    if fare_amount is not None:
        where.append(f"{_TOTAL} = :fare_amount")
        params['fare_amount'] = fare_amount
    fare_min = _coerce_int(fare_min)
    if fare_min is not None:
        where.append(f"{_TOTAL} >= :fare_min")
        params['fare_min'] = fare_min
    fare_max = _coerce_int(fare_max)
    if fare_max is not None:
        where.append(f"{_TOTAL} <= :fare_max")
        params['fare_max'] = fare_max

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
    fare_amount: Optional[int] = None,
    fare_min: Optional[int] = None,
    fare_max: Optional[int] = None,
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
        has_fare: True=已記錄車資（總額>0）/ False=未記錄（總額 0 或空）/ None=不過濾
        fare_amount: 依車資總額（錶價+加成）精確篩選（例 1600）
        fare_min / fare_max: 車資總額範圍下/上限（含界，例 大於 1400 → fare_min=1401）
        limit: 上限筆數（預設 80，避免 LINE Flex 50KB 上限）
    """
    where, params = _build_filters(
        date_from=date_from, date_to=date_to,
        driver_id=driver_id,
        customer_short_name=customer_short_name,
        category=category, location=location,
        start_location=start_location, end_location=end_location,
        has_fare=has_fare, fare_amount=fare_amount,
        fare_min=fare_min, fare_max=fare_max,
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
    fare_amount: Optional[int] = None,
    fare_min: Optional[int] = None,
    fare_max: Optional[int] = None,
) -> ToolResult:
    """
    過去態車資統計（對應 legacy「統計金額」/「加總」模式）。

    Return data:
        {
            'total_count': int,        # 符合 filter 的總筆數
            'filled_count': int,       # 車資總額(錶價+加成)>0
            'unfilled_count': int,     # 總額 0 或空（含錶價=0 的未填班次）
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
        has_fare=None, fare_amount=fare_amount,
        fare_min=fare_min, fare_max=fare_max,
    )

    sql = """
        SELECT
            COUNT(*) AS total_count,
            COUNT(CASE
                WHEN (COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0)) > 0 THEN 1
            END) AS filled_count,
            COUNT(CASE
                WHEN (COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0)) <= 0 THEN 1
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


# ============================================================
# 過去態唯讀受護欄查詢層（spec docs/specs/04）
# ============================================================

def _spec_subtitle(spec: dict) -> Optional[str]:
    """從 spec filters 組統計卡副標：日期區間 · 類別 · 司機 …"""
    parts: list = []
    for f in (spec.get('filters') or []):
        if not isinstance(f, dict):
            continue
        col, op, val = f.get('col'), f.get('op'), f.get('value')
        if col == 'date' and op == 'between' and isinstance(val, (list, tuple)) and len(val) == 2:
            parts.append(f"{val[0]}~{val[1]}")
        elif col == 'date':
            parts.append(str(val))
        elif col == 'category':
            parts.append(str(val))
        elif col == 'driver_id':
            parts.append(f"司機{val}")
        elif col == 'total_fare':
            parts.append(f"車資{op}{val}")
        elif col == 'customer':
            parts.append(str(val))
    return ' · '.join(str(p) for p in parts) if parts else None


def query_completed_trips_advanced(*, session, spec: dict) -> ToolResult:
    """過去態唯讀受護欄查詢層：AI 生「查詢規格(spec)」→ 編譯成安全 SQL → 執行。

    取代「每個查詢維度手焊一個參數」。支援:
      - filters：欄位 × 運算子（含範圍 >/</between、in、ilike），全 AND
      - group_by + aggregates：分組統計（count/sum/avg/min/max）—「各司機加總」
      - order_by：排序（「金額最高 5 筆」）
    FROM 固定 completed_trips（過去態）；值全 named-param 綁定；唯讀交易（第二道防線）。
    spec 形狀與可用欄位見 docs/specs/04。
    """
    if not isinstance(spec, dict):
        return ToolResult.fail("查詢規格格式錯（要 JSON 物件）")
    try:
        compiled = compile_query_spec(spec, detail_columns=_DETAIL_COLUMNS)
    except QuerySpecError as e:
        return ToolResult.fail(f"這個查詢條件目前不支援：{e}")
    except Exception as e:  # 殘餘型別/格式錯 → 友善訊息（不讓裸例外穿透）
        return ToolResult.fail(f"查詢規格解析失敗：{str(e)[:100]}")

    # 第二道防線：本次查詢交易設唯讀，即使編譯出意外 mutation 也被 DB 擋
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
    except Exception:
        session.rollback()

    try:
        rows = session.execute(text(compiled.sql), compiled.params).fetchall()
    except Exception as e:
        try:
            session.rollback()   # 還原 failed tx，否則同 session 後續查詢拋 InFailedSqlTrans
        except Exception:
            pass
        return ToolResult.fail(f"查詢執行失敗：{str(e)[:120]}")

    if compiled.mode == 'grouped':
        if not rows:
            return ToolResult.fail("範圍內沒有符合條件的已完成班次")
        return ToolResult.success(
            data=GroupedStatView(
                group_cols=compiled.group_display,
                agg_cols=compiled.agg_display,
                rows=[dict(r._mapping) for r in rows],
                subtitle=_spec_subtitle(spec),
                agg_kinds=compiled.agg_kinds,
            ),
            count=len(rows),
        )

    if not rows:
        return ToolResult.fail("找不到符合條件的已完成班次")
    return ToolResult.success(
        data=[CompletedTripView.from_row(r) for r in rows],
        count=len(rows),
        truncated=len(rows) >= _SPEC_MAX_LIMIT,
    )


# ============================================================
# 對帳單（純文字直列，給複製/轉傳到別的聊天室跟司機對帳）
# ============================================================

# LINE 單則文字訊息上限 5000 字元；留 headroom 在 4900 切分
LINE_TEXT_CHUNK_SIZE = 4900
# LINE reply 一次最多 5 則訊息（API 限制）
LINE_REPLY_MAX_MESSAGES = 5

# date.weekday()：0=星期一 .. 6=星期日
_WEEKDAY_ZH = ('一', '二', '三', '四', '五', '六', '日')


@dataclass
class ReconciliationTextView:
    """對帳單純文字 view — 渲染層直接輸出 text 訊息（可長按複製/轉傳）。

    text 可能超過 LINE 單則 5000 上限 → 渲染層用 split_text_for_line
    切成多則（最多 LINE_REPLY_MAX_MESSAGES 則）。
    """
    text: str
    count: int = 0
    total_amount: int = 0

    def to_dict(self) -> dict:
        # 給 LLM function_response 的摘要 — 全文已直接渲染給用戶，
        # 整份餵回 model 只會撐爆 context。
        # ⚠️ 不放 preview 片段：實測 Gemini 會把 preview 原文抄進收尾文字，
        #    用戶就看到「半張截斷單 + 完整單」黏在一起（2026-07-14 log）
        return {
            'count': self.count,
            'total_amount': self.total_amount,
            'note': '對帳單全文已以純文字訊息直接回覆用戶，你不需要重述內容',
        }


def split_text_for_line(
    text_str: str,
    *,
    chunk_size: int = LINE_TEXT_CHUNK_SIZE,
    max_parts: int = LINE_REPLY_MAX_MESSAGES,
) -> tuple:
    """長文字 → 多則 LINE 訊息切分（純函數，無 DB）。

    - 每則 ≤ chunk_size；優先在換行處切（對帳單一行一筆，不把一筆切兩半），
      單行本身超過 chunk_size 才 hard-split
    - 最多 max_parts 則

    Returns:
        (chunks: list[str], overflow: bool)
        overflow=True = 超過 max_parts 塞不下，chunks 只含前 max_parts 則，
        呼叫端應提示縮小範圍。
    """
    remaining = text_str or ''
    chunks: list = []
    while remaining:
        if len(chunks) >= max_parts:
            return chunks, True
        if len(remaining) <= chunk_size:
            chunks.append(remaining)
            break
        # 在 chunk_size 內找最後一個換行處切（rfind end 參數 exclusive）
        cut = remaining.rfind('\n', 1, chunk_size + 1)
        if cut <= 0:
            # 單行超長 → hard-split
            chunks.append(remaining[:chunk_size])
            remaining = remaining[chunk_size:]
        else:
            chunks.append(remaining[:cut])
            remaining = remaining[cut + 1:]
    if not chunks:
        chunks = ['']
    return chunks, False


def _fmt_month_day(d: date) -> str:
    """7/6 這類無前導零的 月/日"""
    return f"{d.month}/{d.day}"


def _short_loc(s: Optional[str], max_len: int = 10) -> str:
    """地點精簡：過長截斷（對帳單一行放 起→終，途經省略）"""
    s = (s or '?').strip() or '?'
    return s if len(s) <= max_len else s[:max_len - 1] + '…'


def query_reconciliation_text(
    *,
    session,
    date_from,
    date_to,
    driver_id: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = 200,
) -> ToolResult:
    """
    對帳單（純文字直列）— 給複製/轉傳到別的聊天室跟司機對帳用。唯讀。

    Triggers: 「對帳」「對帳單」「班次對帳」，如「上週司機28530東洋班次對帳」。
    跟 query_completed_trips 的 Flex carousel 不同：carousel 不能轉傳，
    這裡輸出純文字，可長按複製/轉傳。

    格式：
      📋 對帳單 2026/7/5～7/11
      司機 28530｜東洋
      ──────────

      【7/6（一）】2 筆
      #2585 萬年七街→太子龍 330
      #2593 健康三街→建平七街 請假 -30
      　小計 300 元

      【7/8（三）】…（每天空行分段；單日查詢不顯示小計）

      ──────────
      共 23 筆｜合計 5,285 元

    - 金額口徑 = 錶價+加成（同 aggregate_completed_trips）
    - 請假班次標「請假」但金額照列（照常計入合計）
    - 起→終精簡（過長截斷），途經省略
    """
    date_from = _coerce_date(date_from)
    date_to = _coerce_date(date_to)
    if not date_from or not date_to:
        return ToolResult.fail(
            "對帳需要 date_from 與 date_to（週次講法先用 sun_week_info 拿日期）"
        )
    if date_from > date_to:
        return ToolResult.fail("date_from 不能晚於 date_to")
    driver_id = _coerce_int(driver_id)
    limit = _coerce_int(limit) or 200
    if category:
        category = str(category).strip()
        if category not in VALID_CATEGORIES:
            return ToolResult.fail(
                f"無效的類別 '{category}'，必須是：{', '.join(VALID_CATEGORIES)}"
            )

    where, params = _build_filters(
        date_from=date_from, date_to=date_to,
        driver_id=driver_id,
        customer_short_name=None,
        category=category, location=None,
    )
    sql = _SELECT_ALL + '\nWHERE ' + ' AND '.join(where)
    sql += '\nORDER BY date, id\nLIMIT :limit'
    params['limit'] = limit

    rows = session.execute(text(sql), params).fetchall()
    if not rows:
        return ToolResult.fail("找不到符合條件的已完成班次")

    views = [CompletedTripView.from_row(r) for r in rows]
    truncated = len(views) >= limit

    # ---- header ----
    if date_from == date_to:
        range_str = f"{date_from.year}/{_fmt_month_day(date_from)}"
    elif date_from.year == date_to.year:
        range_str = (
            f"{date_from.year}/{_fmt_month_day(date_from)}"
            f"～{_fmt_month_day(date_to)}"
        )
    else:
        range_str = (
            f"{date_from.year}/{_fmt_month_day(date_from)}"
            f"～{date_to.year}/{_fmt_month_day(date_to)}"
        )
    lines = [f"📋 對帳單 {range_str}"]
    filter_parts = []
    if driver_id is not None:
        filter_parts.append(f"司機 {driver_id}")
    if category:
        filter_parts.append(category)
    if filter_parts:
        lines.append("｜".join(filter_parts))
    divider = "──────────"
    lines.append(divider)

    # ---- body（按日期分段：空行 +【7/6（一）】N 筆 + 逐筆 + 小計）----
    # 先分組（views 已按 date 排序）
    day_groups: list = []   # [(date, [views])]
    for v in views:
        if day_groups and day_groups[-1][0] == v.date:
            day_groups[-1][1].append(v)
        else:
            day_groups.append((v.date, [v]))

    total = 0
    multi_day = len(day_groups) > 1
    for d, group in day_groups:
        lines.append("")   # 每天前空一行，跟上一段隔開
        header = (f"【{_fmt_month_day(d)}（{_WEEKDAY_ZH[d.weekday()]}）】"
                  if d else "【無日期】")
        lines.append(f"{header} {len(group)} 筆")
        day_sum = 0
        for v in group:
            amount = v.computed_total
            total += amount or 0
            day_sum += amount or 0
            amount_str = f"{amount:,}" if amount is not None else '未記錄'
            leave_mark = "請假 " if v.is_leave else ""
            route = f"{_short_loc(v.start_point)}→{_short_loc(v.end_point)}"
            lines.append(f"#{v.id} {route} {leave_mark}{amount_str}")
        # 單日查詢時小計＝合計，不重複顯示
        if multi_day:
            lines.append(f"　小計 {day_sum:,} 元")

    # ---- footer ----
    lines.append("")
    lines.append(divider)
    lines.append(f"共 {len(views)} 筆｜合計 {total:,} 元")
    if truncated:
        lines.append(f"⚠️ 超過 {limit} 筆已截斷，請縮小日期範圍")

    return ToolResult.success(
        data=ReconciliationTextView(
            text='\n'.join(lines),
            count=len(views),
            total_amount=total,
        ),
        count=len(views),
        truncated=truncated,
    )


# ============================================================
# Mutation 工具（無 R-5 鎖：過去態無時間鎖意義）
# 共用：modification_reason 累加（[N] 格式）+ modified_by + time 寫入
#       audit log（R-6）
# ============================================================

def _fetch_completed_trip_snapshot(
    *, session, completed_trip_id: int,
) -> Optional[dict]:
    """取一筆 completed_trip 完整 row 當 audit before/after 快照"""
    row = session.execute(
        text("SELECT * FROM completed_trips WHERE id = :id"),
        {'id': completed_trip_id}
    ).fetchone()
    return dict(row._mapping) if row else None


def _weekly_charge_warning(*, session, trip_date, delta: int) -> Optional[str]:
    """改錢後的帳務勾稽提示：若班次所在太陽週已記過（有效的）週扣款，
    回警語字串提醒補沖正/補記；只提示不自動改帳。"""
    if not trip_date or not delta:
        return None
    try:
        # lazy import 避免 completed_trip ↔ accounting 循環 import
        from rewrite.tools.accounting import find_weekly_charge_for_week
        from rewrite.utils.sun_week import sun_week_start
        ws = sun_week_start(trip_date)
        we = ws + timedelta(days=6)
        charge = find_weekly_charge_for_week(session=session, week_end_date=we)
        if not charge:
            return None
        return (
            f"⚠️ 該週（{ws.month}/{ws.day}〜{we.month}/{we.day}）已記扣款 "
            f"NT$ {charge['amount_out']:,}，本次調整差額 {delta:+,}，"
            f"帳務需補沖正/補記"
        )
    except Exception as e:  # 勾稽查詢失敗不擋主流程
        import logging
        logging.getLogger(__name__).warning(f"weekly_charge 勾稽檢查失敗: {e}")
        return None


def update_completed_trip_fare(
    *,
    session,
    completed_trip_id: int,
    meter_fare: Optional[int] = None,
    extra_fare: Optional[int] = None,
    reason: str,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    記錄/修改過去態班次車資（對應 legacy「記錄車資 [id] 錶價 加成 原因」）。

    對齊 0013.txt log 第 90-95 行的 trip 820 修改流程：
      - 比較 DB 現值 vs 新值，沒變動 → fail（避免無意義 audit）
      - modification_reason 累加：'[N] 改車資: 錶價 0→1250, 加成 0→750 (等候3小時)'
      - 更新 modified_by, modification_time（沿用 legacy modification_utils 慣例）
      - 寫 audit log

    Args:
        completed_trip_id: completed_trips.id（不是 trips.trip_id）
        meter_fare: 新錶價（None=不改；至少 meter/extra 其中一個要給）
        extra_fare: 新加成（同上）
        reason: 修改原因（必填，合規）— 空字串 → fail，AI follow-up 收原因

    R-5 鎖：不適用（過去態已完成）
    """
    if not reason or not reason.strip():
        return ToolResult.fail("請提供修改原因")
    if meter_fare is None and extra_fare is None:
        return ToolResult.fail("至少要給 meter_fare 或 extra_fare 其中一個")
    if meter_fare is not None and not isinstance(meter_fare, int):
        return ToolResult.fail("meter_fare 必須是整數")
    if extra_fare is not None and not isinstance(extra_fare, int):
        return ToolResult.fail("extra_fare 必須是整數")

    before = _fetch_completed_trip_snapshot(
        session=session, completed_trip_id=completed_trip_id,
    )
    if not before:
        return ToolResult.fail(f"找不到已完成班次 #{completed_trip_id}")

    # 動態 SET：只更新有給且有變動的欄位
    sets: list = []
    params: dict = {'id': completed_trip_id}
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

    note = f"改車資: {', '.join(diffs)} ({reason.strip()})"
    new_mod = append_modification_reason(
        before.get('modification_reason'), note, table_name='completed_trips',
    )

    sets.extend([
        'modification_reason = :mod',
        'modified_by = :who',
        'modification_time = :mtime',
    ])
    params['mod'] = new_mod
    params['who'] = user_name or user_id or '系統'
    params['mtime'] = get_taiwan_time()

    sql = f"UPDATE completed_trips SET {', '.join(sets)} WHERE id = :id"
    session.execute(text(sql), params)

    after = _fetch_completed_trip_snapshot(
        session=session, completed_trip_id=completed_trip_id,
    )
    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='update_completed_trip_fare',
        target_table='completed_trips', target_id=completed_trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason.strip(),
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

    # 帳務勾稽：車資總額有變且該週已記週扣款 → meta 附警語（只提示不改帳；
    # data 仍回 CompletedTripView，渲染層決定怎麼顯示警語）
    # ⚠️ 僅限「診所」類班次 — weekly_charge 是達恩診所的車資週扣款，
    #    東洋/臨時班次與週扣款無關，改錢不該跳警語（用戶實測回報 2026-07）
    warning = None
    if before.get('category') == '診所':
        old_total = (before.get('meter_fare') or 0) + (before.get('extra_fare') or 0)
        new_total = (
            (meter_fare if meter_fare is not None else (before.get('meter_fare') or 0))
            + (extra_fare if extra_fare is not None else (before.get('extra_fare') or 0))
        )
        warning = _weekly_charge_warning(
            session=session, trip_date=before.get('date'), delta=new_total - old_total,
        )
    result = query_completed_trip_by_id(completed_trip_id, session=session)
    if warning and result.ok:
        result.meta['warning'] = warning
    return result


def update_completed_trip_category(
    *,
    session,
    completed_trip_id: int,
    new_category: str,
    reason: str,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    修改過去態班次類別（對應 legacy「修改類別 [id] [新類別]」）。

    跟 legacy 不同的是：legacy 只 SET category（沒留軌跡），這版會：
      - 累加 modification_reason（'[N] 改類別: 東洋→診所 (報帳分類錯誤)'）
      - 寫 modified_by + modification_time
      - audit log

    Args:
        new_category: '診所' / '東洋' / '臨時' 之一
        reason: 修改原因（必填）

    R-5 鎖：不適用
    """
    if not reason or not reason.strip():
        return ToolResult.fail("請提供修改原因")
    if not new_category or not new_category.strip():
        return ToolResult.fail("new_category 不可空")
    new_category = new_category.strip()
    if new_category not in VALID_CATEGORIES:
        return ToolResult.fail(
            f"無效的類別 '{new_category}'，必須是：{', '.join(VALID_CATEGORIES)}"
        )

    before = _fetch_completed_trip_snapshot(
        session=session, completed_trip_id=completed_trip_id,
    )
    if not before:
        return ToolResult.fail(f"找不到已完成班次 #{completed_trip_id}")

    old_category = before.get('category')
    if old_category == new_category:
        return ToolResult.fail(
            f"班次 #{completed_trip_id} 類別已是『{new_category}』，無需修改"
        )

    note = f"改類別: {old_category}→{new_category} ({reason.strip()})"
    new_mod = append_modification_reason(
        before.get('modification_reason'), note, table_name='completed_trips',
    )

    session.execute(text("""
        UPDATE completed_trips SET
            category = :cat,
            modification_reason = :mod,
            modified_by = :who,
            modification_time = :mtime
        WHERE id = :id
    """), {
        'cat': new_category,
        'mod': new_mod,
        'who': user_name or user_id or '系統',
        'mtime': get_taiwan_time(),
        'id': completed_trip_id,
    })

    after = _fetch_completed_trip_snapshot(
        session=session, completed_trip_id=completed_trip_id,
    )
    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='update_completed_trip_category',
        target_table='completed_trips', target_id=completed_trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=reason.strip(),
        extra={'old_category': old_category, 'new_category': new_category},
        via=via,
    )

    if auto_commit:
        session.commit()
    return query_completed_trip_by_id(completed_trip_id, session=session)


def update_completed_trip_driver(
    *,
    session,
    completed_trip_id: int,
    new_driver_id: int,
    reason: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    修改過去態班次司機（key 錯司機 / 司機臨時換人補登）。

    跟 update_completed_trip_category 同 pattern：
      - 驗證 driver_id 在 drivers 表
      - 累加 modification_reason（'[N] 換司機: 5386→28530'）
      - 寫 modified_by + modification_time
      - audit log

    R-5 鎖：不適用（過去態）
    """
    before = _fetch_completed_trip_snapshot(
        session=session, completed_trip_id=completed_trip_id,
    )
    if not before:
        return ToolResult.fail(f"找不到已完成班次 #{completed_trip_id}")

    # 驗證司機存在
    drv = session.execute(
        text("SELECT id FROM drivers WHERE id = :id"),
        {'id': new_driver_id}
    ).fetchone()
    if not drv:
        return ToolResult.fail(f"找不到司機 ID {new_driver_id}")

    old_driver_id = before.get('driver_id')
    if old_driver_id == new_driver_id:
        return ToolResult.fail(
            f"班次 #{completed_trip_id} 司機已是 #{new_driver_id}，無需修改"
        )

    note_parts = [f"換司機: {old_driver_id or '無'}→{new_driver_id}"]
    if reason and reason.strip():
        note_parts.append(reason.strip())
    note = ' '.join(note_parts)
    new_mod = append_modification_reason(
        before.get('modification_reason'), note, table_name='completed_trips',
    )

    session.execute(text("""
        UPDATE completed_trips SET
            driver_id = :driver_id,
            modification_reason = :mod,
            modified_by = :who,
            modification_time = :mtime
        WHERE id = :id
    """), {
        'driver_id': new_driver_id,
        'mod': new_mod,
        'who': user_name or user_id or '系統',
        'mtime': get_taiwan_time(),
        'id': completed_trip_id,
    })

    after = _fetch_completed_trip_snapshot(
        session=session, completed_trip_id=completed_trip_id,
    )
    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='update_completed_trip_driver',
        target_table='completed_trips', target_id=completed_trip_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        reason=(reason.strip() if reason else None),
        extra={'old_driver_id': old_driver_id, 'new_driver_id': new_driver_id},
        via=via,
    )

    if auto_commit:
        session.commit()
    return query_completed_trip_by_id(completed_trip_id, session=session)
