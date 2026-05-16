"""
customer_skill — 客戶領域

8 個 atomic tools：
  query 類：query_customer_by_term / query_customer / get_customer_by_id /
            query_customers_by_birthday_day / query_birthday_day_summary
  CRUD：create_customer / update_customer / delete_customer

業務語境：
  - 客戶有 short_name (簡稱) / medical_record_no (病歷號) 等識別欄位
  - 「病歷層」= 客戶生日的「日」（1-31），同一日的客戶分到同一層
  - ⚠️ 2026-05-08: drop national_id / insurance_type 兩個欄
"""
from rewrite.ai.skill import Skill
from rewrite.tools.customer import (
    query_customer,
    query_customer_by_term,
    get_customer_by_id,
    query_customers_by_birthday_day,
    query_birthday_day_summary,
    create_customer,
    update_customer,
    delete_customer,
)


_SYSTEM_PROMPT = """\
你是客戶資料助手。

🗂️ 客戶資料含：name (全名)、short_name (簡稱)、address、category、
contact_phone、remarks、birthday、gender、medical_record_no (病歷號)、
dm_care_no (糖尿病共同照護網代號，診所內部編號) 等。

🛠️ 工具選擇規則：

【查詢】用戶說「查 太子龍」「太子龍住哪」「龍埔街是誰」→ 一律用
  query_customer_by_term(term=...)。它會自動 cascade fallback：
  病歷號 → short_name → name → address。
  別自己組多個參數呼叫 query_customer（除非用戶明確指定欄位）。

【ID 直接查】「客戶詳情 5」「客戶 #5」 → get_customer_by_id(5)

【病歷層】用戶說「病歷層 15」「15 號生日的有誰」「15 日層」
  → query_customers_by_birthday_day(day=15)
  「病歷層分布」「各層多少人」 → query_birthday_day_summary()

【建檔】「新增客戶 太子龍 龍哥 龍埔街123 諮所」→ create_customer。
  必填：name + short_name + address；category 強烈建議帶（診所/東洋）。
  資訊不全 → 先回問，不要亂猜。

【修改】「太子龍改名為龍哥」「太子龍地址改成龍埔街456」
  → 先用 query_customer_by_term 查到 customer_id，再 update_customer(id, **fields)。
  別只用 short_name 改 — 必須拿到 customer_id 才能改。

【刪除】「刪除太子龍」 → 先 query_customer_by_term 確認 → delete_customer(id)
  ⚠️ 危險動作：先列詳情給用戶看，等用戶確認再執行。

⚠️ 規則：
1. 修改/刪除前必須先 query 確認 — 不要憑用戶說的 short_name 直接改
2. 一次只動一個客戶；批量操作用戶要明說
3. 完成單一操作後直接回報結果，**不主動追問下一步**、不說「請問您需要什麼協助？」
   「還需要什麼幫忙嗎？」這類客套句 — 用戶下一輪自然會打字。
"""


# ============================================================
# Tool schemas
# ============================================================

QUERY_CUSTOMER_BY_TERM_SCHEMA = {
    'description': "Cascade fallback search: tries short_name → medical_record_no → dm_care_no → name → address. 給「查 X」「X 是誰」這類自然詢問用",
    'parameters': {
        'type': 'object',
        'properties': {
            'term': {'type': 'string', 'description': "用戶輸入的搜尋詞（簡稱/姓名/地址/病歷號/共照網代號）"},
            'limit': {'type': 'integer', 'description': "預設 20"},
        },
        'required': ['term'],
    },
}

QUERY_CUSTOMER_SCHEMA = {
    'description': "Multi-field exact/fuzzy customer query. Only use when user explicitly specifies which field.",
    'parameters': {
        'type': 'object',
        'properties': {
            'short_name': {'type': 'string'},
            'name': {'type': 'string'},
            'address': {'type': 'string'},
            'medical_record_no': {'type': 'string', 'description': "病歷號"},
            'dm_care_no': {'type': 'string', 'description': "糖尿病共同照護網代號（診所內部編號）"},
            'fuzzy_name': {'type': 'boolean'},
            'fuzzy_address': {'type': 'boolean'},
            'limit': {'type': 'integer'},
        },
    },
}

GET_CUSTOMER_BY_ID_SCHEMA = {
    'description': "Get customer by integer ID",
    'parameters': {
        'type': 'object',
        'properties': {
            'customer_id': {'type': 'integer'},
        },
        'required': ['customer_id'],
    },
}

QUERY_BIRTHDAY_DAY_SCHEMA = {
    'description': "List customers whose birthday is on given day (1-31). 病歷層查詢",
    'parameters': {
        'type': 'object',
        'properties': {
            'day': {'type': 'integer', 'description': "1-31"},
        },
        'required': ['day'],
    },
}

QUERY_BIRTHDAY_SUMMARY_SCHEMA = {
    'description': "Show birthday-day distribution (counts per day 1-31). 病歷層分布",
    'parameters': {
        'type': 'object',
        'properties': {},
    },
}

CREATE_CUSTOMER_SCHEMA = {
    'description': "Create a new customer. name + short_name + address required.",
    'parameters': {
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'description': "全名"},
            'short_name': {'type': 'string', 'description': "簡稱（必填）"},
            'address': {'type': 'string', 'description': "地址"},
            'category': {'type': 'string', 'description': "診所/東洋 等"},
            'contact_phone': {'type': 'string'},
            'remarks': {'type': 'string'},
            'birthday': {'type': 'string', 'description': "YYYY-MM-DD"},
            'gender': {'type': 'string', 'description': "M/F"},
            'medical_record_no': {'type': 'string', 'description': "病歷號"},
            'dm_care_no': {'type': 'string', 'description': "糖尿病共同照護網代號（診所內部編號，約 4 位數）"},
        },
        'required': ['name', 'short_name', 'address'],
    },
}

UPDATE_CUSTOMER_SCHEMA = {
    'description': "Update customer fields by id. Get id from query first.",
    'parameters': {
        'type': 'object',
        'properties': {
            'customer_id': {'type': 'integer'},
            'name': {'type': 'string'},
            'short_name': {'type': 'string'},
            'address': {'type': 'string'},
            'category': {'type': 'string'},
            'contact_phone': {'type': 'string'},
            'remarks': {'type': 'string'},
            'birthday': {'type': 'string', 'description': "YYYY-MM-DD"},
            'gender': {'type': 'string'},
            'medical_record_no': {'type': 'string'},
            'dm_care_no': {'type': 'string', 'description': "糖尿病共同照護網代號（診所內部編號）"},
        },
        'required': ['customer_id'],
    },
}

DELETE_CUSTOMER_SCHEMA = {
    'description': "Delete customer by id (rejects if any trip references the customer's short_name)",
    'parameters': {
        'type': 'object',
        'properties': {
            'customer_id': {'type': 'integer'},
        },
        'required': ['customer_id'],
    },
}


def build_customer_skill() -> Skill:
    return Skill(
        name='customer',
        system_prompt=_SYSTEM_PROMPT,
        tools=[
            (query_customer_by_term, QUERY_CUSTOMER_BY_TERM_SCHEMA),
            (query_customer, QUERY_CUSTOMER_SCHEMA),
            (get_customer_by_id, GET_CUSTOMER_BY_ID_SCHEMA),
            (query_customers_by_birthday_day, QUERY_BIRTHDAY_DAY_SCHEMA),
            (query_birthday_day_summary, QUERY_BIRTHDAY_SUMMARY_SCHEMA),
            (create_customer, CREATE_CUSTOMER_SCHEMA),
            (update_customer, UPDATE_CUSTOMER_SCHEMA),
            (delete_customer, DELETE_CUSTOMER_SCHEMA),
        ],
    )
