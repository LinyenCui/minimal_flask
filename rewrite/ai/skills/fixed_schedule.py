"""
fixed_schedule_skill — 固定班次（未來態）模板管理

7 個工具（4 atomic + 3 helper 給 multi-turn 用）：
  - query_fixed_schedule (多條件) / get_fixed_schedule_by_id
  - update_fixed_schedule (時間/地點/車資/司機等)
  - apply_fixed_schedule_leave (長期請假)
  - restore_fixed_schedule (從請假恢復)

不含：import_fixed_schedules（用戶決定走 sandbox legacy）

語境：
  - 「固定班次」「固定」「模板」 = fixed_schedules 表
  - 跟 trips 不同：是「每週重複的模板」，匯入後才產生 trip rows
  - 「長期請假」= 模板狀態變請假 → 之後匯入週次時不會產生 trip
  - 「下週起取消」「客戶出國」等情境用這個
"""
from rewrite.ai.skill import Skill
from rewrite.tools.fixed_schedule import (
    query_fixed_schedule,
    get_fixed_schedule_by_id,
    update_fixed_schedule,
    apply_fixed_schedule_leave,
    restore_fixed_schedule,
    create_fixed_schedule,
)
from rewrite.utils.sun_week import sun_week_info


_SYSTEM_PROMPT = """\
你是「未來態 fixed_schedules」固定班次模板助手。三時間態世界觀：
- 現在態 trips：生產線上具體班次（不歸你管）
- 過去態 completed_trips：已執行完（不歸你管）
- 未來態 fixed_schedules：每週模板 ← 你只管這個

🛠️ 工具選擇：
- 用戶說「查太子龍的固定班次」「龍埔街的固定班表」→ query_fixed_schedule(customer_short_name=...)
- 用戶給「固定班次 #21」「固定班次21」→ get_fixed_schedule_by_id(21)
- 用戶說「修改」「改時間」「改地點」「改車資」→ update_fixed_schedule
- 用戶說「請假」「長期請假」「出國」「住院」→ apply_fixed_schedule_leave
- 用戶說「恢復」「改回準備」「不請假了」→ restore_fixed_schedule
- 用戶說「新增固定班次」「建模板」（**通常該走 LIFF 表單**，欄位多 AI 容易漏，
  建議引導用戶打「新增固定班次」觸發 LIFF；若用戶堅持自然語言給齊欄位才 call）
  → create_fixed_schedule（必填: route_number/departure_time/start_point/category）

⚠️ 規則：
1. schedule_id 必填（schedule_id 不是 trip_id！這是模板層）
   用戶說「修改 21」就是 schedule_id=21
2. apply_fixed_schedule_leave 需要 reason + surcharge（surcharge 通常是負數）
   缺資訊 → 回問用戶，不要亂猜
3. 修改前可先 query 確認班次內容
4. 不要混淆 trips 和 fixed_schedules — 用戶說「班次 1077 請假」是 trips，
   說「固定班次 21 請假」才是 fixed_schedules
5. 完成單一操作後直接回報結果，**不主動追問下一步**、不說「請問您需要什麼協助？」
   這類客套句 — 用戶下一輪自然會打字。

📝 用詞：
- 「下週起暫停」「暫時不來」「長期不來」 → apply_fixed_schedule_leave
- 「恢復服務」「重新開始」「請假結束」 → restore_fixed_schedule

🗓 太陽週（Sunday-first）— 用戶問週次直接用 sun_week_info 答：
- 「本週是哪一週」「上週幾號到幾號」「W17 是哪幾天」 → call sun_week_info 回答
- 太陽週 = 星期日 ~ 星期六（**不是 ISO 週一起算**），不要自己算
"""


# ============================================================
# Tool schemas
# ============================================================

QUERY_FIXED_SCHEDULE_SCHEMA = {
    'description': "Query fixed schedules by multiple filters. customer_short_name 會 match start_point/via_point/end_point",
    'parameters': {
        'type': 'object',
        'properties': {
            'customer_short_name': {'type': 'string', 'description': "客戶簡稱，如「龍埔街」「太子龍」"},
            'category': {'type': 'string', 'description': "診所/東洋"},
            'driver_id': {'type': 'string', 'description': "司機 ID（varchar，如 '533')"},
            'direction': {'type': 'string', 'description': "來/回"},
            'status': {'type': 'string', 'description': "準備/請假/註銷"},
            'route_number': {'type': 'string'},
            'limit': {'type': 'integer'},
        },
    },
}

GET_FIXED_SCHEDULE_BY_ID_SCHEMA = {
    'description': "Get a single fixed schedule by id (用戶給「固定班次 21」就用這個)",
    'parameters': {
        'type': 'object',
        'properties': {
            'schedule_id': {'type': 'integer'},
        },
        'required': ['schedule_id'],
    },
}

UPDATE_FIXED_SCHEDULE_SCHEMA = {
    'description': "Update fixed schedule fields (departure_time/start/via/end_point/base_fare/surcharge/category/driver_id/direction/note/route_number)",
    'parameters': {
        'type': 'object',
        'properties': {
            'schedule_id': {'type': 'integer'},
            'departure_time': {'type': 'string', 'description': "HH:MM:SS or HH:MM"},
            'start_point': {'type': 'string'},
            'via_point': {'type': 'string'},
            'end_point': {'type': 'string'},
            'base_fare': {'type': 'integer'},
            'surcharge': {'type': 'integer'},
            'category': {'type': 'string'},
            'driver_id': {'type': 'string', 'description': "varchar"},
            'direction': {'type': 'string', 'description': "來/回"},
            'note': {'type': 'string'},
            'route_number': {'type': 'string'},
        },
        'required': ['schedule_id'],
    },
}

APPLY_LEAVE_SCHEMA = {
    'description': "Long-term leave: status → 請假, note=reason, surcharge=given. Use for 出國/住院 etc.",
    'parameters': {
        'type': 'object',
        'properties': {
            'schedule_id': {'type': 'integer'},
            'reason': {'type': 'string', 'description': "請假原因（出國/住院/化療等）"},
            'surcharge': {'type': 'integer', 'description': "加成（通常負數，如 -50）"},
        },
        'required': ['schedule_id', 'reason', 'surcharge'],
    },
}

RESTORE_SCHEMA = {
    'description': "Restore from 請假/註銷 to 準備. Clears note.",
    'parameters': {
        'type': 'object',
        'properties': {
            'schedule_id': {'type': 'integer'},
        },
        'required': ['schedule_id'],
    },
}


CREATE_FIXED_SCHEDULE_SCHEMA = {
    'description': (
        "Create a new fixed schedule template. Most users should use LIFF form "
        "(打「新增固定班次」會回 LIFF 按鈕). 只有用戶自然語言給齊所有必填才 call 這個。"
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'route_number': {
                'type': 'string',
                'description': "週幾組合，1-7 數字（'147' = 週一週四週日）",
            },
            'departure_time': {'type': 'string', 'description': "HH:MM"},
            'start_point': {'type': 'string'},
            'category': {'type': 'string', 'description': "診所/東洋/臨時"},
            'via_point': {'type': 'string'},
            'end_point': {'type': 'string'},
            'base_fare': {'type': 'integer'},
            'surcharge': {'type': 'integer'},
            'driver_id': {'type': 'string'},
            'direction': {'type': 'string', 'description': "來/回/單"},
            'note': {'type': 'string'},
        },
        'required': ['route_number', 'departure_time', 'start_point', 'category'],
    },
}


SUN_WEEK_INFO_SCHEMA = {
    'description': (
        "Get sun-week (Sunday-first) info. Use when user asks「本週是哪一週」"
        "「上週幾號到幾號」「W17 是哪幾天」. AI must NOT compute these — "
        "LLM defaults to ISO week which is OFF BY ONE DAY for this business."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'week_number': {'type': 'integer', 'description': "整年第 N 週"},
            'week_offset': {'type': 'integer', 'description': "0=本週/-1=上週/1=下週"},
            'target_date': {'type': 'string', 'description': "YYYY-MM-DD 任一日期"},
            'year': {'type': 'integer'},
        },
    },
}


def build_fixed_schedule_skill() -> Skill:
    return Skill(
        name='fixed_schedule',
        system_prompt=_SYSTEM_PROMPT,
        tools=[
            (sun_week_info, SUN_WEEK_INFO_SCHEMA),
            (query_fixed_schedule, QUERY_FIXED_SCHEDULE_SCHEMA),
            (get_fixed_schedule_by_id, GET_FIXED_SCHEDULE_BY_ID_SCHEMA),
            (update_fixed_schedule, UPDATE_FIXED_SCHEDULE_SCHEMA),
            (apply_fixed_schedule_leave, APPLY_LEAVE_SCHEMA),
            (restore_fixed_schedule, RESTORE_SCHEMA),
            (create_fixed_schedule, CREATE_FIXED_SCHEDULE_SCHEMA),
        ],
    )
