"""
completed_trip_skill — 過去態（completed_trips）查詢 + 統計

包：3 個 query 工具的 schema + 領域 system prompt。

不含 mutation — 純查詢。Mutation（記錄車資、修改類別）走 trip_mutation_skill 將來補。

Trigger 條件（intent classifier 已篩過）：
  - 含「已完成」/「查已完成」/「查看 N」關鍵字
  - 純過去日期（例「昨天」「上週」「4/21」相對 today）
  - 含「加總」「統計金額」（aggregate mode）
"""
from datetime import date

from rewrite.ai.skill import Skill
from rewrite.tools.completed_trip import (
    query_completed_trips,
    query_completed_trip_by_id,
    aggregate_completed_trips,
    update_completed_trip_fare,
    update_completed_trip_category,
    update_completed_trip_driver,
)
from rewrite.utils.sun_week import sun_week_info


def _system_prompt() -> str:
    today = date.today()
    weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    return f"""\
你是「過去態 completed_trips」助手 — 已完成班次的查詢、統計與修改。

🏭 三時間態世界觀：
- 過去態 completed_trips：已執行完的班次 ← 你只能查這個
- 現在態 trips：生產線上的班次（含今天 + 已匯入未來）（不歸你管）
- 未來態 fixed_schedules：模板（不歸你管）

📅 時間參考：
- 今天 = {today.isoformat()} ({weekdays[today.weekday()]})
- 「昨天」「前天」「3天前」「7月」這類**單純日期** → 自己算 YYYY-MM-DD
- 「7月」沒明確年份的，預設今年 ({today.year})

🗓 **太陽週（Sunday-first）— 業務週定義，不是 ISO 8601**：
- 太陽週 = 星期日 ~ 星期六（不是週一起算！）
- 任何「本週/上週/下週/+N週/第 N 週/W{{N}}」**一律 call sun_week_info 拿正確 dates**，
  **不要自己算**（LLM 預設算成 ISO 週，會差一天）
- 例：用戶「本週」「W18」「第 18 週」 → 先 call sun_week_info → 拿到 5/3-5/9 →
  再 call aggregate / query 帶 date_from=5/3, date_to=5/9
- 用戶單純問「本週是哪一週？」「W17 是哪幾天？」 → 只 call sun_week_info 回答即可

🛠️ 工具選擇：
- 用戶提到週次（本週/上週/+N週/第 N 週/W{{N}}） → **先 call sun_week_info** 拿 dates
- 用戶問「本週是哪一週」「W17 是哪幾天」這種純查週資訊 → 只 call sun_week_info
- 用戶給「completed_trip_id / 查看 820 / #820」 → query_completed_trip_by_id
- 用戶問「加總/統計金額/總計多少」 → aggregate_completed_trips
- 其他條件查詢（日期/司機/類別/客戶/地點）→ query_completed_trips
- 「修改 #N 金額/加成」「記錄車資 N」 → update_completed_trip_fare
- 「修改類別 #N」「#N 改類別」 → update_completed_trip_category
- 「#N 司機改成 M」「換 #N 司機 M」 → update_completed_trip_driver

📌 參數提示（**很重要：分清 category vs location**）：
- **category**：班次的「業務類別」整批分類，目前只有「診所」「東洋」「臨時」幾個固定值
  - 觸發：「診所班次」「東洋班次」「診所總計」「東洋加總」「診所類別」這類「類別+班次/類別+總計」組合
- **location / start_location / end_location**：地點欄位的字串模糊比對（ILIKE）
  - 觸發：「從 X 出發」「到 X」「經過 X」「跟 X 有關」這類**動詞**句
  - 「從 X 出發」/「X 起點」 → 用 `start_location='X'`
  - 「到 X」/「X 終點」 → 用 `end_location='X'`
  - 「經過 X」/「跟 X 有關」 → 用 `location='X'`（任一欄）
- 中文歧義字（**特別注意**）：
  - 「診所」「東洋」既是 category 名也可能是地點關鍵字
  - 「診所班次」/「東洋班次」 → category（類別+「班次」是固定詞）
  - 「**從**診所出發」/「**到**診所」/「從**東洋後門**出發」 → start_location/end_location（看動詞）
  - 「跟診所相關」 → location（萬用比對）
- customer_short_name：客戶簡稱完整且確定（如「龍埔街」「太子龍」），exact match 起/途/終
- driver_id：司機編號（純整數，例 5386, 533）
- has_fare=False：「未記錄車資的班次」「沒車資 / 金額為 0 的班次」這類查詢（錶價 0 也算未記錄）
- fare_amount=N：「金額為 N 的班次」「車資 N 元的班次」「哪幾筆是 N 元」這類精確金額查詢（依總額=錶價+加成）
- fare_min / fare_max：金額範圍。「大於 1400」→ fare_min=1401；「1400 以上」→ fare_min=1400；「小於 X」→ fare_max=X-1；「介於 X~Y」→ fare_min=X, fare_max=Y
- 重要：若用戶的篩選條件目前工具參數**表達不了**，要**明說「目前只能查 ⋯⋯」**，不要默默忽略條件、把全部班次回給用戶（會誤導）

⚠️ 規則：
- ID 區別：trips.trip_id 跟 completed_trips.id **不一樣**。本 skill 的 ID 是 completed_trips.id
- 過去態都已完成，**沒有 status filter**
- 結果太多（meta.truncated=True / 上限警示）→ 建議用戶縮日期或加 filter，或改用「加總」
- **mutation 必須給 reason**（合規）。用戶若沒給原因，tool 會 fail 「請提供修改原因」，
  你**主動問用戶**：「請給修改原因」— 等用戶補完再 call tool。
- 完成單一動作直接回報結果，**不主動追問下一步**、不說「請問還想看什麼」這類客套句
"""


# ============================================================
# Tool schemas（給 Gemini FunctionDeclaration 用）
# ============================================================

QUERY_COMPLETED_TRIPS_SCHEMA = {
    'description': (
        "Query completed_trips (past tense). Use for date/driver/category/customer/location list queries. "
        "Default for 「查已完成」「昨天班次」etc."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'date_from': {'type': 'string', 'description': "Start date YYYY-MM-DD"},
            'date_to': {'type': 'string', 'description': "End date YYYY-MM-DD (omit if single day)"},
            'driver_id': {'type': 'integer', 'description': "Driver ID (e.g. 5386, 533)"},
            'category': {
                'type': 'string',
                'description': (
                    "業務類別 enum：『診所』『東洋』『臨時』之一。"
                    "**只在用戶明說『診所班次』『東洋班次』『X類別』時才填**。"
                    "若用戶說『從診所出發』『到東洋』這類動詞句，**不要**填 category，"
                    "改用 start_location/end_location"
                ),
            },
            'customer_short_name': {
                'type': 'string',
                'description': "客戶簡稱完整（exact，比對起/途/終任一）；不確定就用 location",
            },
            'location': {
                'type': 'string',
                'description': (
                    "萬用地點模糊比對（ILIKE 任一 start/via/end）。"
                    "用於『經過 X』『跟 X 有關』。「從 X 出發/到 X」要用 start_location/end_location"
                ),
            },
            'start_location': {
                'type': 'string',
                'description': "起點模糊比對（ILIKE start_point）。「從 X 出發」「X 起點」用這個",
            },
            'end_location': {
                'type': 'string',
                'description': "終點模糊比對（ILIKE end_point）。「到 X」「X 結束」用這個",
            },
            'has_fare': {
                'type': 'boolean',
                'description': "True=已記錄車資(總額>0)，False=未記錄(總額 0 或空，含錶價=0)。「未記錄車資」傳 False",
            },
            'fare_amount': {
                'type': 'integer',
                'description': (
                    "依車資總額(錶價+加成)精確篩選。"
                    "Triggers:「金額為 X 的班次」「車資 X 元的班次」「X 元的班次」「哪幾筆是 X 元」"
                ),
            },
            'fare_min': {
                'type': 'integer',
                'description': "車資總額下限(含)。「大於 X」用 X+1；「X 以上/≥X」用 X;「介於 X~Y」配 fare_max",
            },
            'fare_max': {
                'type': 'integer',
                'description': "車資總額上限(含)。「小於 Y」用 Y-1；「Y 以下/≤Y」用 Y;「介於 X~Y」配 fare_min",
            },
            'limit': {'type': 'integer', 'description': "Max rows，預設 80"},
        },
    },
}

QUERY_COMPLETED_TRIP_BY_ID_SCHEMA = {
    'description': (
        "Query single completed trip by completed_trip_id. "
        "Use when user says「查看 820」「#820」「明細 820」etc."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'completed_trip_id': {
                'type': 'integer',
                'description': "completed_trips.id（不是 trips.trip_id）",
            },
        },
        'required': ['completed_trip_id'],
    },
}

AGGREGATE_COMPLETED_TRIPS_SCHEMA = {
    'description': (
        "Aggregate completed_trips fares (sum/count). "
        "Use when user wants total amount over a range — 「加總」「統計金額」「總計」「本月共多少」."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'date_from': {'type': 'string', 'description': "Start date YYYY-MM-DD"},
            'date_to': {'type': 'string', 'description': "End date YYYY-MM-DD"},
            'driver_id': {'type': 'integer', 'description': "Driver ID"},
            'category': {
                'type': 'string',
                'description': (
                    "業務類別『診所』『東洋』『臨時』之一。"
                    "只在『診所總計』『東洋加總』時填；"
                    "『從X出發的金額』要用 start_location"
                ),
            },
            'customer_short_name': {'type': 'string'},
            'location': {'type': 'string', 'description': "萬用地點模糊（任一欄）"},
            'start_location': {'type': 'string', 'description': "起點模糊比對"},
            'end_location': {'type': 'string', 'description': "終點模糊比對"},
            'fare_amount': {
                'type': 'integer',
                'description': "依車資總額(錶價+加成)精確篩選再加總（「金額為 X 的班次加總」）",
            },
            'fare_min': {'type': 'integer', 'description': "車資總額下限(含);「大於 X」用 X+1"},
            'fare_max': {'type': 'integer', 'description': "車資總額上限(含);「小於 Y」用 Y-1"},
        },
        'required': ['date_from', 'date_to'],
    },
}


UPDATE_COMPLETED_TRIP_FARE_SCHEMA = {
    'description': (
        "Record/modify fare on a completed trip. "
        "Triggers: 「修改 #N 金額 X 加成 Y」「記錄車資 N X Y 原因」「#N 車資改為 X」. "
        "Reason is REQUIRED — if user didn't give one, ask for it before calling."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'completed_trip_id': {
                'type': 'integer',
                'description': "completed_trips.id（不是 trip_id）",
            },
            'meter_fare': {'type': 'integer', 'description': "新錶價（None=不改）"},
            'extra_fare': {'type': 'integer', 'description': "新加成（None=不改）"},
            'reason': {
                'type': 'string',
                'description': "修改原因（必填，合規）。例：「等候3小時」「報帳分類錯誤」",
            },
        },
        'required': ['completed_trip_id', 'reason'],
    },
}

UPDATE_COMPLETED_TRIP_CATEGORY_SCHEMA = {
    'description': (
        "Modify category of a completed trip (用於 key 錯類別需要更正). "
        "Triggers: 「修改類別 N 新類別 原因」「#N 改類別為 診所」. "
        "Reason REQUIRED."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'completed_trip_id': {'type': 'integer'},
            'new_category': {
                'type': 'string',
                'description': "『診所』『東洋』『臨時』之一",
            },
            'reason': {
                'type': 'string',
                'description': "修改原因（必填）",
            },
        },
        'required': ['completed_trip_id', 'new_category', 'reason'],
    },
}

UPDATE_COMPLETED_TRIP_DRIVER_SCHEMA = {
    'description': (
        "Modify the assigned driver of a completed trip (用於 key 錯司機 / "
        "司機臨時換人補登). Triggers: 「#N 司機改成 M」「換 #N 司機 M」"
        "「將已完成 #N 司機改成 M」. Reason 可選。"
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'completed_trip_id': {'type': 'integer', 'description': "completed_trips.id"},
            'new_driver_id': {'type': 'integer', 'description': "新司機 ID（drivers.id）"},
            'reason': {'type': 'string', 'description': "修改原因（可選）"},
        },
        'required': ['completed_trip_id', 'new_driver_id'],
    },
}


SUN_WEEK_INFO_SCHEMA = {
    'description': (
        "Get sun-week (Sunday-first) info for date/range conversion. "
        "Use this BEFORE query/aggregate when user mentions 「本週/上週/下週/+N週/第 N 週/W{N}」. "
        "Returns date_start (Sunday) + date_end (Saturday) + week_number + label. "
        "AI must NOT compute these dates itself — LLM defaults to ISO week (Mon-first), "
        "which is OFF BY ONE DAY for this business."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'week_number': {
                'type': 'integer',
                'description': "整年第 N 週（太陽週號 strftime '%U'，1-based）。例：用戶說「第 17 週」傳 17",
            },
            'week_offset': {
                'type': 'integer',
                'description': "0=本週、-1=上週、1=下週、2=下下週、-2=兩週前 ... 用戶說「本週/上週/下週/+3週」用這個",
            },
            'target_date': {
                'type': 'string',
                'description': "YYYY-MM-DD 任一日期，回該日所在週。用戶說「5/7 那週」用這個",
            },
            'year': {
                'type': 'integer',
                'description': "year 預設今年；跨年查詢才指定",
            },
        },
    },
}


def build_completed_trip_skill() -> Skill:
    return Skill(
        name='completed_trip',
        system_prompt=_system_prompt(),
        tools=[
            (sun_week_info, SUN_WEEK_INFO_SCHEMA),
            (query_completed_trips, QUERY_COMPLETED_TRIPS_SCHEMA),
            (query_completed_trip_by_id, QUERY_COMPLETED_TRIP_BY_ID_SCHEMA),
            (aggregate_completed_trips, AGGREGATE_COMPLETED_TRIPS_SCHEMA),
            (update_completed_trip_fare, UPDATE_COMPLETED_TRIP_FARE_SCHEMA),
            (update_completed_trip_category, UPDATE_COMPLETED_TRIP_CATEGORY_SCHEMA),
            (update_completed_trip_driver, UPDATE_COMPLETED_TRIP_DRIVER_SCHEMA),
        ],
    )
