"""
Gemini Function Calling 定義（精簡版）

設計理念：
- 只定義「需要智能理解」的操作：請假、車資修改
- 查詢操作仍走傳統路徑（已驗證穩定）
- FC 是輔助，不是替代

為什麼不把查詢也放進來？
1. 現有查詢系統已經很穩定
2. 查詢的變化太多（日期範圍、多條件組合）
3. 請假/車資修改的意圖更明確，FC 效果更好
"""

import logging

logger = logging.getLogger(__name__)

# FC 可識別的所有操作
GEMINI_FUNCTIONS = [
    {
        "name": "query_trips_by_context",
        "description": """
🔍 查詢班次信息（優先使用！大多數情況都是查詢）

⚠️ 觸發條件（滿足任一即可）：
1. 包含「班次」關鍵字
2. 包含「查詢」「查看」「有哪些」等查詢詞
3. 包含日期範圍（如 12/1-12/6）
4. 包含「已完成」「統計」「加總」等

使用場景：
✅ "12/13 533診所班次" → 查詢（有「班次」關鍵字）
✅ "明天診所班次" → 查詢（有「班次」關鍵字）
✅ "12/1-12/6 5386東洋班次" → 範圍查詢
✅ "今天有哪些班次" → 查詢
✅ "昨天已完成班次" → 查詢

🚨 重要例外：
❌ 包含「狀態」「狀況」的查詢（如 "明天狀態" "12/24狀態"）→ 必須使用 clarify_user_intent
❌ 只要有「班次」這個詞，才是查詢！沒有「班次」且有「狀態」，請用 clarify_user_intent
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "日期，如：明天、今天、12/11"},
                "date_range": {"type": "string", "description": "日期範圍，如：12/1-12/6"},
                "driver_id": {"type": "integer", "description": "司機編號"},
                "location": {"type": "string", "description": "地點關鍵字"},
                "category": {"type": "string", "description": "類別：診所、東洋、臨時"}
            },
            "required": []
        }
    },
    {
        "name": "clarify_user_intent",
        "description": """
🤔 意圖不明確 或 查詢狀態 時使用。

⚠️ 觸發條件（滿足任一即可）：
1. 包含「狀態」「狀況」關鍵字（如：明天二井家狀態、12/24狀態）
2. 只有日期或地點，沒有「班次」也沒有操作關鍵字

使用場景：
✅ "明天二井家狀態" → 狀態查詢
✅ "12/24 二井家狀態" → 狀態查詢
✅ "明天和緯四" → 只有日期和地點，沒說要做什麼
✅ "12/11 公園南路" → 只有日期和地點

❌ 不要使用的場景：
❌ "12/13 533診所班次" → 有「班次」，應使用 query_trips_by_context
❌ "明天診所班次" → 有「班次」，應使用 query_trips_by_context
❌ "12/11和緯四請假" → 有「請假」，應使用 passenger_leave
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "日期，如：明天、今天、12/11"},
                "location": {"type": "string", "description": "地點關鍵字，如：和緯四、公園南路"},
                "driver_id": {"type": "integer", "description": "司機編號（如有提及）"},
                "category": {"type": "string", "description": "類別：診所、東洋、臨時（如有提及）"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "passenger_leave",
        "description": """
處理乘客請假操作。

⚠️ 觸發條件（必須同時滿足）：
1. 包含「請假」「乘客請假」「病患請假」「不來」「不用載」「取消載送」等關鍵字
2. 有日期或地點信息

使用場景：
✅ "明天公園南路的病患請假"
✅ "12/11 久保田家請假"
✅ "班次 658 乘客請假"
✅ "今天5386診所的客人請假"

非使用場景（這些應該走傳統查詢）：
❌ "明天公園南路的班次" → 這是查詢
❌ "12/1-12/6 5386東洋班次" → 這是範圍查詢
❌ "今天診所班次" → 這是查詢
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "日期，如：明天、今天、12/11、下週一"
                },
                "location": {
                    "type": "string",
                    "description": "地點關鍵字，如：公園南路、久保田家、診所"
                },
                "driver_id": {
                    "type": "integer",
                    "description": "司機編號（如果提到）"
                },
                "reason": {
                    "type": "string",
                    "description": "請假原因，如：住院、出國、臨時有事。如果沒提到，留空"
                },
                "allowance": {
                    "type": "integer",
                    "description": "加成調整（通常是負數），默認 0",
                    "default": 0
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "update_fare",
        "description": """
修改已完成班次的車資。

⚠️ 觸發條件（必須同時滿足）：
1. 有班次號碼（#xxx 或 班次xxx）
2. 有金額信息（$xxx 或 數字）
3. 包含「修改」「記錄」「車資」等關鍵字

使用場景：
✅ "修改#4996$90（一般記賬）"
✅ "把 4914 的車資加 75"
✅ "班次2014車資改成500"

非使用場景：
❌ "12/1 5386東洋班次" → 這是查詢
❌ "查看班次4996" → 這是查看詳情
        """,
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "integer",
                    "description": "班次編號"
                },
                "meter_fare": {
                    "type": "integer",
                    "description": "新的錶價（直接設定）"
                },
                "extra_fare": {
                    "type": "integer",
                    "description": "新的加成（直接設定）"
                },
                "adjustment": {
                    "type": "integer",
                    "description": "調整金額（+/- 多少）"
                },
                "reason": {
                    "type": "string",
                    "description": "修改原因。⚠️ 注意：只有在用戶輸入中明確包含原因文字時才提取（如括號內的文字）。如果用戶沒有提供原因，這裡必須留空字串！絕對不要自己編造或填寫「一般記賬」等預設值！"
                }
            },
            "required": ["trip_id"]
        }
    },
    {
        "name": "confirm_operation",
        "description": """
確認執行待確認的操作。

觸發條件：
- 用戶回答「確認」「是」「對」「執行」「確認請假」「確認修改」「全部請假」「是，改回準備」
        """,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "cancel_operation",
        "description": """
取消當前操作。

觸發條件：
- 用戶回答「取消」「算了」「不要了」「放棄」
        """,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


def should_use_function_calling(message_text: str) -> bool:
    """
    判斷是否應該使用 Function Calling
    
    這是關鍵的「門檻」函數，決定流量分發
    
    Returns:
        True: 使用 FC 處理（請假、車資修改、確認/取消）
        False: 走傳統路徑（查詢等）
    """
    message_lower = message_text.lower()
    
    # 1. 請假相關關鍵字
    leave_keywords = [
        '請假', '乘客請假', '病患請假', '客人請假',
        '不來', '不用載', '取消載送', '不去了'
    ]
    
    # 2. 車資修改相關關鍵字（需要同時有班次號和金額）
    fare_keywords = ['修改', '記錄車資', '車資', '改成', '調整']
    has_trip_id = '#' in message_text or '班次' in message_text
    has_amount = '$' in message_text or any(c.isdigit() for c in message_text)
    
    # 3. 確認/取消操作
    confirm_keywords = ['確認', '確認請假', '確認修改', '是，改回準備']
    cancel_keywords = ['取消', '算了', '不要了', '放棄', '不用，謝謝', '放棄AI修改']
    
    # 判斷邏輯
    if any(kw in message_text for kw in leave_keywords):
        logger.info(f"🎯 檢測到請假意圖: {message_text}")
        return True
    
    if any(kw in message_text for kw in fare_keywords) and has_trip_id and has_amount:
        logger.info(f"🎯 檢測到車資修改意圖: {message_text}")
        return True
    
    if any(kw in message_text for kw in confirm_keywords):
        logger.info(f"🎯 檢測到確認操作: {message_text}")
        return True
    
    if any(kw in message_text for kw in cancel_keywords):
        logger.info(f"🎯 檢測到取消操作: {message_text}")
        return True
    
    # 其他情況走傳統路徑
    return False


def get_function_schemas():
    """獲取 Gemini Function Calling 的 Schema"""
    return GEMINI_FUNCTIONS
