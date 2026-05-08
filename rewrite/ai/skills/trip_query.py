"""
trip_query_skill — 班次查詢領域（v0.1 第一個 skill）

包：5 個 query 工具的 schema + 領域 system prompt。

不含 mutation — 純查詢。Mutation 走 trip_mutation_skill（將來做）。
"""
from datetime import date

from rewrite.ai.skill import Skill
from rewrite.tools.trip import (
    query_trips,
    query_trip_by_id,
    query_today_trips,
    query_pending_dispatch,
)


def _system_prompt() -> str:
    today = date.today()
    weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    return f"""\
你是「現在態 trips」班次查詢助手。

🏭 三時間態世界觀：
- 現在態 trips：生產線上的班次（含今天 + 已匯入未來）← 你只能查這個
- 過去態 completed_trips：已執行完（不歸你管）
- 未來態 fixed_schedules：模板（不歸你管）

📅 時間參考：
- 今天 = {today.isoformat()} ({weekdays[today.weekday()]})
- 用戶說「明天」「下週一」「5/4」等都要轉成 YYYY-MM-DD 格式給工具

🛠️ 工具選擇規則：
- 用戶給「班次號 / trip_id / #1077」 → query_trip_by_id
- 用戶問「今天的班次」「今天診所」 → query_today_trips
- 用戶問「待派班次」「沒指派的」「待派」 → query_pending_dispatch
- 其他條件查詢（日期/類別/司機/客戶簡稱）→ query_trips

📌 customer_short_name：用戶說「龍埔街」「新建路」「太子龍」這類客戶簡稱
   就直接傳給 customer_short_name，工具會自動 match 起點/途經/終點。

⚠️ 規則：
- 「狀態」這個詞通常指「該客戶當天的所有班次」 → query_trips（含 customer_short_name + date）
- 預設過濾「已完成」班次（exclude_status=['已完成']），除非用戶明示要看
- 別亂猜參數，用戶沒說就別填
- 完成查詢直接回報結果，**不主動追問下一步**、不說「請問您需要什麼協助？」
  「還想看什麼？」這類客套句 — 用戶下一輪自然會打字。
"""


# ============================================================
# Tool schemas（給 Gemini FunctionDeclaration 用）
# ============================================================

QUERY_TRIPS_SCHEMA = {
    'description': "Query trips with multiple AND filters. Use this for date/driver/category/customer queries.",
    'parameters': {
        'type': 'object',
        'properties': {
            'date_from': {'type': 'string', 'description': "Start date YYYY-MM-DD"},
            'date_to': {'type': 'string', 'description': "End date YYYY-MM-DD (omit if single day)"},
            'driver_id': {'type': 'integer', 'description': "Driver ID (e.g. 533, 28530)"},
            'category': {'type': 'string', 'description': "診所 or 東洋"},
            'customer_short_name': {
                'type': 'string',
                'description': "客戶簡稱（如「龍埔街」「新建路」），會自動 match 起點/途經/終點",
            },
            'exclude_status': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': "要排除的狀態，預設 ['已完成']",
            },
            'limit': {'type': 'integer', 'description': "Max rows，預設 200"},
        },
    },
}

QUERY_TRIP_BY_ID_SCHEMA = {
    'description': "Query a single trip by trip_id (用戶給 班次號/班次/#NNNN 時用).",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
        },
        'required': ['trip_id'],
    },
}

QUERY_TODAY_TRIPS_SCHEMA = {
    'description': "Query today's trips (shortcut for query_trips with today's date).",
    'parameters': {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'description': "診所/東洋（None = 全部）"},
            'include_completed': {'type': 'boolean', 'description': "預設 true 含已完成"},
        },
    },
}

QUERY_PENDING_DISPATCH_SCHEMA = {
    'description': "Query trips pending driver assignment (status=待派 or driver_id=NULL).",
    'parameters': {
        'type': 'object',
        'properties': {
            'date_from': {'type': 'string', 'description': "Start date YYYY-MM-DD (omit = from today)"},
        },
    },
}


def build_trip_query_skill() -> Skill:
    return Skill(
        name='trip_query',
        system_prompt=_system_prompt(),
        tools=[
            (query_trips, QUERY_TRIPS_SCHEMA),
            (query_trip_by_id, QUERY_TRIP_BY_ID_SCHEMA),
            (query_today_trips, QUERY_TODAY_TRIPS_SCHEMA),
            (query_pending_dispatch, QUERY_PENDING_DISPATCH_SCHEMA),
        ],
    )
