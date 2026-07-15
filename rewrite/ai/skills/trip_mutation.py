"""
trip_mutation_skill — 班次修改領域

7 個 mutation 工具（atomic tools 已含 R-5 鎖 + R-6 audit log）：
  passenger_leave / cancel_trip / mark_conflict / restore_to_ready
  assign_driver / unassign_driver / update_passenger_name / record_fare_current

設計原則：
  - 用戶一句話完整給 trip_id + 必填參數時 → AI 直接執行
  - 缺資訊時 → AI 回問（spec §6.3 的 propose-confirm-execute 之後 Phase 加）
  - 30 分鐘鎖、狀態檢查、audit log 都由 atomic tool 內部 decorator 強制
  - 不確定的 mutation 寧可 query 給用戶看再讓他下命令
"""
from datetime import date

from rewrite.ai.skill import Skill
from rewrite.tools.trip import (
    query_trips,
    query_trip_by_id,
    passenger_leave,
    cancel_trip,
    mark_conflict,
    restore_to_ready,
    assign_driver,
    unassign_driver,
    update_passenger_name,
    record_fare_current,
    update_trip_category,
    update_trip_time,
    update_trip_route,
)


def _system_prompt() -> str:
    today = date.today()
    return f"""\
你是「現在態 trips」班次修改助手。三時間態世界觀：
- 現在態 trips：你只能改這個
- 過去態 completed_trips：已執行完不歸你管
- 未來態 fixed_schedules：模板不歸你管

📅 今天 = {today.isoformat()}

🛠️ 工具選擇：
- 乘客請假（三層障眼法：status 仍'準備'，但 leave_reason 記原因）→ passenger_leave
- 註銷（不再服務這班）→ cancel_trip
- 衝突（時間或資源衝突，可救回）→ mark_conflict
- 改回準備（從請假/註銷/衝突恢復）→ restore_to_ready
- 指派/換司機 → assign_driver
- 撤銷司機指派（軟取消，避免落入已完成）→ unassign_driver
- 改乘客名 → update_passenger_name
- 記錄/修改現在態車資（錶價/加成）→ record_fare_current
- 改類別（key 錯時用，例「東洋」改「診所」）→ update_trip_category（reason 選填）
- 改時間（同日改時段，例「#2575 改成 11:45」）→ update_trip_time
  （reason 選填；註銷/已完成不可改；30 分鐘鎖內擋；不改日期）
- 改起點/終點/途經（例「#2841 終點改南紡」「起點改X」「途經改Y」「清空途經」）
  → update_trip_route（new_start/new_end/new_via 任一或多個；reason 選填；
  可填非客戶地點；清空途經傳 new_via 空字串或「無」；註銷/已完成不可改）

⚠️ 規則：
1. trip_id 必填。用戶說「那筆」「剛剛那班」這種，問清楚再執行
2. 請假時 reason + surcharge 都要齊（surcharge 通常是負數，例 -30、-50、-100）
   只給原因沒給數字 → 不要呼叫工具，回問用戶數字
3. 多筆班次（如「明天龍埔街都請假」）→ 先用 query_trips 查出來，列給用戶看，
   讓他確認 trip_ids 後再一筆一筆執行（v0.1 暫不支援自動批量）
4. 30 分鐘鎖內的狀態變更（請假/註銷/衝突）會被工具擋下回 fail —
   這是正常規則，不是錯誤
5. **用戶完整給 trip_id + driver_id（如「指派司機 1190 28530」「派司機 28530 給 #1190」
   「將 1190 的司機改成 28530」「換 1190 司機 28530」）→ 直接 call assign_driver，
   不要先 query_trip_by_id 確認 → 不要先反問**。
   即使該班次已有司機（換司機是合法操作，atomic tool 會自動寫
   modification_reason「換司機 OLD→NEW」）。
6. 用戶模糊指稱（「那筆」「剛剛那班」）才需要 query 先 → query_trip_by_id 或 query_trips
7. 完成單一操作後直接回報結果，**不主動追問下一步**、不說「請問您需要什麼協助？」
   「還需要什麼幫忙嗎？」這類客套句 — 用戶下一輪自然會打字。

🚀 **執行優先**：用戶下達明確 mutation 命令（trip_id 確定 + 動作清楚）→ 直接呼叫
   對應 atomic tool。不要因為「謹慎起見先 query 再說」浪費 token 跟時間。
   atomic tool 自己會驗 trip 存在 / 狀態合法 / 司機存在等，validate 失敗會回
   ToolResult.fail，那時你再回報錯誤即可。

🎯 用詞理解：
- 「自己來 -100」「化療 -30」「身體不適 -50」「住院 -200」這類
  = passenger_leave 的 reason + surcharge
- 「乘客叫 XX」「改名」 = update_passenger_name
- 「車資 380」「等候 +50」 = record_fare_current
"""


# ============================================================
# Tool schemas
# ============================================================

PASSENGER_LEAVE_SCHEMA = {
    'description': "Passenger requests leave (三層障眼法: status remains '準備', records leave_reason)",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
            'reason': {'type': 'string', 'description': "請假原因（如 化療、身體不適、住院、出國）"},
            'surcharge': {'type': 'integer', 'description': "加成金額（通常負數，如 -30 / -50 / -100）"},
        },
        'required': ['trip_id', 'reason', 'surcharge'],
    },
}

CANCEL_TRIP_SCHEMA = {
    'description': "Cancel a trip (status → '註銷')",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
            'reason': {'type': 'string', 'description': "註銷原因（可選）"},
        },
        'required': ['trip_id'],
    },
}

MARK_CONFLICT_SCHEMA = {
    'description': "Mark a trip as conflict (status → '衝突')",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
            'reason': {'type': 'string', 'description': "衝突原因（可選）"},
        },
        'required': ['trip_id'],
    },
}

RESTORE_TO_READY_SCHEMA = {
    'description': "Restore trip back to '準備' (clear leave_reason; from 請假/衝突/註銷 to 準備)",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
        },
        'required': ['trip_id'],
    },
}

ASSIGN_DRIVER_SCHEMA = {
    'description': "Assign or change driver (待派 → 準備 if status was 待派)",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
            'driver_id': {'type': 'integer', 'description': "司機 ID（如 533, 28530, 5386）"},
        },
        'required': ['trip_id', 'driver_id'],
    },
}

UNASSIGN_DRIVER_SCHEMA = {
    'description': "Unassign driver (driver → NULL, status → 待派, soft-cancel: 避免班次自動掉到 completed)",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
        },
        'required': ['trip_id'],
    },
}

UPDATE_PASSENGER_NAME_SCHEMA = {
    'description': "Update or clear passenger name on a trip",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
            'passenger_name': {
                'type': 'string',
                'description': "New passenger name (empty string to clear)",
            },
        },
        'required': ['trip_id'],
    },
}

RECORD_FARE_CURRENT_SCHEMA = {
    'description': "Record/modify current trip's fare (meter_fare and/or extra_fare)",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID"},
            'meter_fare': {'type': 'integer', 'description': "錶價（只給要改的）"},
            'extra_fare': {'type': 'integer', 'description': "加成（只給要改的，可正可負）"},
            'reason': {'type': 'string', 'description': "備註（如 等候 25 分鐘）"},
        },
        'required': ['trip_id'],
    },
}

UPDATE_TRIP_CATEGORY_SCHEMA = {
    'description': (
        "Modify category of a current trip (用於 key 錯類別需要更正). "
        "Triggers: 「修改類別 [trip_id] 新類別」「#N 改類別為 診所」(現在態 / 未完成班次). "
        "Reason optional (現在態不進報表，不用問原因)."
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID（現在態 trips.trip_id）"},
            'new_category': {
                'type': 'string',
                'description': "『診所』『東洋』『臨時』之一",
            },
            'reason': {
                'type': 'string',
                'description': "修改原因（必填）",
            },
        },
        'required': ['trip_id', 'new_category'],
    },
}

UPDATE_TRIP_TIME_SCHEMA = {
    'description': (
        "Modify a CURRENT trip's time (same-day re-time only, does NOT change date). "
        "Triggers: 「#N 改成 HH:MM」「把 N 的時間改成 11:45」「現在態 N 改時間」. "
        "Rejected if status 註銷/已完成, or inside 30-min lock. Reason optional (不用問原因). "
        "改日期請勿用本工具（會連動週次/編號，尚未支援）。"
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID（現在態 trips.trip_id）"},
            'new_time': {
                'type': 'string',
                'description': "新時間 HH:MM（24 小時制，例 11:45）",
            },
            'reason': {'type': 'string', 'description': "修改原因（選填，用戶有講才帶，不用主動問）"},
        },
        'required': ['trip_id', 'new_time'],
    },
}


UPDATE_TRIP_ROUTE_SCHEMA = {
    'description': (
        "Modify a CURRENT trip's start/end/via point (起點/終點/途經). "
        "Triggers: 「#N 終點改南紡購物中心」「#N 起點改成X」「途經改成Y」「途經改null/清空途經」. "
        "new_start / new_end / new_via 至少給一個。起終點/途經可為非客戶地點（如商場、車站）。"
        "清空途經：new_via 傳空字串或「無」「null」。Rejected if 註銷/已完成. Reason optional (不用問原因). "
        "只改本班次,不影響固定班次模板與其他班次。"
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer', 'description': "Trip ID（現在態 trips.trip_id）"},
            'new_start': {'type': 'string', 'description': "新起點（可選;客戶簡稱或任意地點名）"},
            'new_end': {'type': 'string', 'description': "新終點（可選;客戶簡稱或任意地點名，如『南紡購物中心』）"},
            'new_via': {'type': 'string', 'description': "新途經（可選;設值或傳空字串/「無」表清空途經）"},
            'reason': {'type': 'string', 'description': "修改原因（選填，用戶有講才帶，不用主動問）"},
        },
        'required': ['trip_id'],
    },
}


# 也讓 mutation skill 能呼叫 query 類工具（規則 3：多筆 mutation 前先 query 確認）
QUERY_TRIPS_SCHEMA = {
    'description': "Query trips for confirmation before mutation (e.g. user says 「明天龍埔街都請假」, query first to confirm trip_ids)",
    'parameters': {
        'type': 'object',
        'properties': {
            'date_from': {'type': 'string', 'description': "YYYY-MM-DD"},
            'date_to': {'type': 'string', 'description': "YYYY-MM-DD。省略=不設上限；查單日要跟 date_from 同值"},
            'driver_id': {'type': 'integer'},
            'category': {'type': 'string', 'description': "診所/東洋"},
            'customer_short_name': {'type': 'string', 'description': "客戶簡稱"},
            'start_location': {'type': 'string', 'description': "起點含此字串（「從X出發」）"},
            'end_location': {'type': 'string', 'description': "終點含此字串（「到X」）"},
            'time_from': {'type': 'string', 'description': "執行時間下限 HH:MM（「九點之後」→'09:00'）"},
            'time_to': {'type': 'string', 'description': "執行時間上限 HH:MM"},
        },
    },
}

QUERY_TRIP_BY_ID_SCHEMA = {
    'description': "Lookup a single trip's full info before deciding mutation",
    'parameters': {
        'type': 'object',
        'properties': {
            'trip_id': {'type': 'integer'},
        },
        'required': ['trip_id'],
    },
}


def build_trip_mutation_skill() -> Skill:
    return Skill(
        name='trip_mutation',
        system_prompt=_system_prompt(),
        tools=[
            (passenger_leave, PASSENGER_LEAVE_SCHEMA),
            (cancel_trip, CANCEL_TRIP_SCHEMA),
            (mark_conflict, MARK_CONFLICT_SCHEMA),
            (restore_to_ready, RESTORE_TO_READY_SCHEMA),
            (assign_driver, ASSIGN_DRIVER_SCHEMA),
            (unassign_driver, UNASSIGN_DRIVER_SCHEMA),
            (update_passenger_name, UPDATE_PASSENGER_NAME_SCHEMA),
            (record_fare_current, RECORD_FARE_CURRENT_SCHEMA),
            (update_trip_category, UPDATE_TRIP_CATEGORY_SCHEMA),
            (update_trip_time, UPDATE_TRIP_TIME_SCHEMA),
            (update_trip_route, UPDATE_TRIP_ROUTE_SCHEMA),
            # 規則 3 用：mutation 前先 query 確認
            (query_trips, QUERY_TRIPS_SCHEMA),
            (query_trip_by_id, QUERY_TRIP_BY_ID_SCHEMA),
        ],
    )
