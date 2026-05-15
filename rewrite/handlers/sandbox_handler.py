"""
Rewrite v0.1 沙盒入口 — 處理 LINE `!`/`！` 前綴訊息

設計（fall-through 策略）：
  1. 用戶打「!明天龍埔街的狀態」這類 → 走進 try_handle_sandbox
  2. classify 意圖：trip_query / trip_mutation / customer / fixed_schedule / unknown
  3. unknown 或 error → 回 False，讓 webhook caller fall-through 給 legacy
     customers_ai_service（仍能處理 booking_create / 匯入固定班次等 rewrite
     沒做的功能）
  4. 認得 → 跑對應 single-skill Agent（含 multi-turn tool loop）→ reply

⚠️ 已在 legacy conversation state（SANDBOX_STATES / active_conversations）的
用戶不應走這條路 — 由 caller webhook.py 判斷。
"""
import logging
import re
from datetime import date as _date
from typing import Optional

from modules.utils.line_bot import reply_message
from modules.utils.unified_date_parser import UnifiedDateParser
from rewrite.ai.agent import Agent
from rewrite.ai.client import GeminiClient
from rewrite.ai.skills.completed_trip import build_completed_trip_skill
from rewrite.ai.skills.customer import build_customer_skill
from rewrite.ai.skills.fixed_schedule import build_fixed_schedule_skill
from rewrite.ai.skills.master import build_master_skill
from rewrite.ai.skills.trip_mutation import build_trip_mutation_skill
from rewrite.ai.skills.trip_query import build_trip_query_skill
from rewrite.conversation_state import (
    set_state as _state_set,
    get_state as _state_get,
    clear_state as _state_clear,
)


# 用戶主動結束對話的關鍵字
_END_CONVERSATION_TEXTS = {
    '結束', '結束對話', '退出', '退出對話', 'exit', 'quit', 'bye',
}

# 觸發 LIFF 新增客戶表單入口（純無參數，AI 自然語言路徑不受影響）
_NEW_CUSTOMER_LIFF_TRIGGERS = {
    '新增客戶', '加客戶', '建檔', '新增客戶 表單', '新增客戶表單',
}

# 觸發 LIFF 預約叫車表單入口
_BOOKING_LIFF_TRIGGERS = {
    '預約叫車', '預約', '新增班次', '預約班次', '叫車', '預約叫車表單',
}

# 觸發 LIFF 匯入固定班次表單入口
_IMPORT_LIFF_TRIGGERS = {
    '匯入固定班次', '匯入', 'import', '匯入班次', '匯入班表',
}

# 觸發 LIFF 新增固定班次模板表單入口
_NEW_FIXED_SCHEDULE_LIFF_TRIGGERS = {
    '新增固定班次', '新增模板', '加固定班次', '建固定班次',
    '新增固定班表', '新增班表', '建班表',
}

# 觸發 LIFF 報表表單入口
_REPORT_LIFF_TRIGGERS = {
    '產報表', '生成報表', '報表',
    '生成日報表', '生成日報',
    '生成週報表', '生成周報表', '生成週報', '生成周報',
    '生成月報表', '生成月報',
    '日報表', '週報表', '周報表', '月報表',
}

# 觸發 帳務處理 主入口（顯示餘額 + 3 個按鈕的 Flex）
_ACCOUNTING_LIFF_TRIGGERS = {
    '帳務處理', '帳務', '餘額', '查餘額', '帳戶餘額',
}

# 帳務明細查詢觸發詞（主選單「📒 查看明細」按鈕送 acct_ledger_start）
_ACCOUNTING_LEDGER_TRIGGERS = {
    'acct_ledger_start',  # 按鈕的 message text
    '帳務明細', '查看明細', '明細',
}

# 帳務明細「篩選區間」觸發詞（進日期 input mode）
_ACCOUNTING_LEDGER_RANGE_TRIGGER = 'acct_ledger_range'

# 帳務明細日期區間 input state type
ACCT_LEDGER_RANGE_INPUT_STATE_TYPE = 'rewrite_acct_ledger_range_input'

# 觸發 LIFF 批量加成表單入口
_BATCH_ALLOWANCE_LIFF_TRIGGERS = {
    '批量加成', '批次加成', '批量改加成', 'batch-allowance',
}

# 觸發資料庫同步流程（admin 工具，橋接呼叫 legacy database_sync_handler）
# 設計選擇：admin 工具不重寫 atomic-tool 風格（580 行業務邏輯 + sysadmin only），
#          rewrite 沙盒只認 trigger，dispatch 給既有 legacy handler 處理
_DB_SYNC_TRIGGERS = {
    '資料庫同步',          # 入口：列出 Render 狀態 + Quick Reply [確認同步/取消同步]
    '確認同步',            # 確認執行
    '確認序號覆蓋',        # 強制同步（序號衝突時）
    '取消同步', '放棄同步',  # 取消
    '同步結果',            # 查詢上次同步結果
}

# 幫助命令（取代 legacy help_router）
_HELP_TRIGGERS = {'幫助', 'help', 'Help', '指令', '說明', '?', '？'}

_HELP_TEXT = """🤖 派班小幫手指令清單
（群組需 / 開頭，私聊不用）

📋 查詢
  查太子龍 / 客戶詳情 5
  病歷層 15
  今天診所班次 / 今天東洋班次
  班次詳情 1234 / 待派班次
  查已完成 昨天 司機5386

🎯 狀態管理（最常用）
  今天X的狀態  / 5/9 X的狀態
   → 列班次 + 批次按鈕：請假 / 註銷 / 衝突 / 改回準備

✏️ 修改（自然語言）
  1234 化療 -30          請假
  1234 註銷 / 衝突        改狀態
  派司機 5386 給 #1234    指派
  記錄車資 1234 380       車資

📝 LIFF 表單
  新增客戶 / 預約叫車 / 匯入固定班次
  生成週報表 / 月報表
  帳務處理 / 批量加成
  新增固定班次 / 編輯固定班次

⚙️ 系統
  資料庫同步 / 同步結果

💡 多輪對話 90 秒內可不加 / 前綴回覆"""


# ====== 「[date][location]的狀態」狀態管理流程 ======
# 用戶常用：「!今天二井家的狀態」「!5/9馬鎮宮的狀態」
# 流程：parse → query trips → render picker (Flex + Quick Reply)
#       → 用戶按 [全部請假/註銷/衝突/改回準備] → 對 trip_ids 批次操作
#       → 「全部請假」需要再問 [原因] [加成]，其他按了直接執行
TRIP_STATUS_PICKER_STATE_TYPE = 'rewrite_trip_status_picker'
TRIP_STATUS_LEAVE_INPUT_STATE_TYPE = 'rewrite_trip_status_leave_input'
TRIP_STATUS_TTL_MINUTES = 5.0  # 5 分鐘思考時間（比 SANDBOX_ACTIVE 90 秒長）

# 批次操作觸發詞 → action label
_BATCH_STATUS_ACTIONS = {
    '全部請假': 'leave',     # 需問 [原因] [加成]，進 leave_input state
    '全部註銷': 'cancel',
    '全部衝突': 'conflict',
    '全部改回準備': 'restore',
}

# 用戶用 / 開頭時剝掉再 match：「/今天二井家的狀態」也認
_RE_STATUS_QUERY = re.compile(r'^/?(.+?)的狀態$')
# 嘗試解析 date prefix：今天/明天/昨天/前天/後天 + 數字日期格式
_RE_DATE_PREFIXES = (
    re.compile(r'^(前天|昨天|今天|明天|後天)'),
    re.compile(r'^(\d{4}-\d{1,2}-\d{1,2})'),
    re.compile(r'^(\d{1,2}/\d{1,2})日?'),  # 5/11日 也接（日當尾綴吞掉）
    re.compile(r'^(\d{1,2}-\d{1,2})'),
    re.compile(r'^(\d{1,2}月\d{1,2}日)'),
    re.compile(r'^(\d{3,4})(?=[^\d])'),  # MMDD 後面要有非數字
)


def _parse_status_query(text: str) -> Optional[tuple[_date, str, str]]:
    """嘗試解析「[date][location]的狀態」

    Returns:
        (date_obj, location, date_label) 或 None
    """
    text = text.strip()
    m = _RE_STATUS_QUERY.match(text)
    if not m:
        return None
    body = m.group(1).strip()
    if not body:
        return None

    # peel off date prefix
    for pat in _RE_DATE_PREFIXES:
        dm = pat.match(body)
        if not dm:
            continue
        date_str = dm.group(1)
        location = body[len(dm.group(0)):].strip()
        if not location:
            continue
        try:
            d = UnifiedDateParser.parse(date_str)
        except Exception:
            continue
        return d, location, date_str
    return None

# 短 follow-up 詞：sandbox-active 狀態下這類訊息 classifier 常判 unknown，
# 但其實是上一輪 AI 問題的回答（確認/拒絕/補資訊）→ 直接帶 last_skill 走
_SHORT_FOLLOWUP_TOKENS = {
    '是', '否', '對', '不', '要', '不要', '可以', '不可以',
    '確認', '確定', '取消', '好', '好的', '繼續',
    'y', 'n', 'yes', 'no', 'ok', 'cancel', 'confirm',
}


def _is_short_followup(text: str) -> bool:
    """判斷是否為短 follow-up 回覆（確認 / 補資訊 / 選編號）

    用於 sandbox-active state 下 bypass classifier — 因為 classifier 對
    這類短訊息常判 unknown 導致 fall-through 到 legacy，破壞對話連續性。
    """
    s = (text or '').strip()
    if not s:
        return False
    if s.lower() in _SHORT_FOLLOWUP_TOKENS:
        return True
    # 純數字 / 加減數字（補加成 -50、選編號 1）
    cleaned = s.replace('-', '').replace('+', '').replace('.', '')
    if cleaned.isdigit():
        return True
    # 短訊息（≤4 chars）多半是補資訊型 follow-up
    if len(s) <= 4:
        return True
    return False


# Sandbox active state — rewrite agent 處理完訊息後設此 state，
# webhook 看到此 state 的用戶下一句訊息**不需 ! 前綴**也會被攔截，
# 維持多輪對話連續（如 AI 問「原因和加成？」 → 用戶答「出國 -50」）
SANDBOX_ACTIVE_STATE_TYPE = 'rewrite_sandbox_active'
SANDBOX_ACTIVE_TTL_MINUTES = 1.5  # 90 秒，避免長期卡住

logger = logging.getLogger(__name__)


# ============================================================
# 全域 lazy-init agent / skill registry
# - Gemini client lazy（避免 import 時就連線）
# - Skills 每次都重 build：trip_query / trip_mutation / completed_trip 的
#   system prompt 內嵌 date.today()，process 不重啟就會凍結在啟動那天。
#   rebuild 成本是 5 個 dataclass instantiation + 字串 interpolation，
#   亞毫秒級，跟 Gemini call 比可忽略。
# ============================================================
_llm: Optional[GeminiClient] = None
_skills: Optional[dict] = None
_master_skill = None


def _init():
    global _llm, _skills, _master_skill
    if _llm is None:
        _llm = GeminiClient()
        logger.info("[rewrite sandbox] Gemini client ready")
    # 每次都重 build — 讓 prompt 內的「今天」跟上系統時鐘
    # master_skill 是運行時用的合一 skill；_skills 保留給測試 / multi_skill_agent
    _skills = {
        'trip_query': build_trip_query_skill(),
        'trip_mutation': build_trip_mutation_skill(),
        'completed_trip': build_completed_trip_skill(),
        'customer': build_customer_skill(),
        'fixed_schedule': build_fixed_schedule_skill(),
    }
    _master_skill = build_master_skill()


def _strip_prefix(text: str) -> str:
    """剝掉群組指令前綴 / # 跟舊 sandbox 前綴 ! ！

    Phase B 後群組統一用 / 開頭；! ! / 等保留只是過渡期相容（用戶習慣）。
    """
    if not text:
        return ''
    text = text.strip()
    for p in ('/!', '/！', '/', '#', '!', '！'):
        if text.startswith(p):
            return text[len(p):].lstrip()
    return text


# 已知的「快速命令」+「Flex/quickReply 按鈕 callback」前綴
#
# 兩個用途：
#   1. sandbox-active 期間，用戶若打這類命令 → 不該攔當 follow-up
#   2. webhook 群組過濾：群組裡按 Flex 按鈕（type='message'）送的 callback 文字
#      沒 `/` 前綴會被擋掉，這裡列入白名單讓過
#
# 加新按鈕／新命令時：把 callback text 的前綴加到這裡
_QUICK_COMMAND_PREFIXES = (
    # rewrite quick commands
    '查客戶', '客戶詳情', '病歷層',
    '查班次', '診所班次', '東洋班次',
    '班次詳情', '待派班次',
    '班次註銷', '班次衝突', '班次請假',
    '班次恢復', '班次撤銷指派',
    '批量請假',
    '車資試算',
    # rewrite Flex 按鈕 callback（type='message' 送的文字）
    '固定班次恢復',         # fixed_schedule_flex「↩️ 恢復」
    '查看 ',                # completed_trip_flex「#N 詳情」
    'acct_ledger_start',    # accounting_flex「📒 查看明細」
    'acct_ledger_range',    # accounting_flex「篩選區間」
    'acct_ledger_next:',    # accounting_flex 翻頁 payload（acct_ledger_next:ts:id:fd:td）
    '帳務處理',             # accounting_flex「回帳務處理」
    '結束對話',             # 各處對話 cancel
    '放棄操作',             # router.py 取消
    # legacy 常用快速命令
    '資料庫同步', '確認同步', '取消同步',
    '生成日報表', '生成週報表', '生成周報表',
    '匯入固定班次',
    '修改狀態', '指派司機', '撤銷指派',
    '記錄車資',
    '幫助', 'help',
)


def looks_like_quick_command(text: str) -> bool:
    """
    訊息是否看起來像「快速命令」（不該被 sandbox-active state 攔下）

    用戶在 sandbox-active 90 秒期間想做別的事（查班次、同步、生成報表等）
    打這些命令時不該被當成 follow-up 攔到 rewrite agent — 讓它走原本的
    快速命令路徑。
    """
    if not text:
        return False
    # 剝掉 / # 前綴（群組命令格式）
    cleaned = text.strip().lstrip('/').lstrip('#').strip()
    if cleaned.startswith(_QUICK_COMMAND_PREFIXES):
        return True
    # 回診日期計算外掛：!日期 / ！日期 — 不是 prefix 字串型，regex 認
    from rewrite.tools.date_calc import is_date_calc_command
    if is_date_calc_command(cleaned):
        return True
    return False


def try_handle_sandbox(event) -> bool:
    """
    試處理 sandbox event；rewrite 不認識 → 回 False（讓 caller fall-through）

    Returns:
        True  — rewrite 處理完了，已 reply
        False — rewrite 不認識（intent=unknown 或 error），caller 走 legacy
    """
    _init()
    user_id = getattr(event.source, 'user_id', None)
    raw = (event.message.text or '').strip()
    text = _strip_prefix(raw)

    if not text:
        return False

    short_uid = (user_id or 'anon')[:8]

    # 0. 用戶主動結束對話模式
    if text in _END_CONVERSATION_TEXTS:
        if user_id:
            _state_clear(user_id)
        reply_message(event.reply_token, {
            'type': 'text',
            'text': '👋 已結束對話模式',
        })
        logger.info(f"[rewrite sandbox] {short_uid} ended conversation by user")
        return True

    # 0a. trip_status 流程的 state-aware action handlers（要在 LIFF 觸發詞之前
    #     check，因為「全部請假/註銷/衝突/改回準備」是流程內按鈕，不該被當成
    #     一般文字訊息）
    trip_status_handled = _try_handle_trip_status_actions(event, user_id, text, short_uid)
    if trip_status_handled is not None:
        return trip_status_handled

    # 0b. LIFF 表單 exact-match 觸發詞（要在 hard fall-through 之前 check）
    #     rewrite 已用 LIFF 接管 customer/booking/import → 訊息 in *_LIFF_TRIGGERS
    #     會被 hard_fallthrough 的「預約」/「匯入」keyword 偷走，所以順序要調整。
    #
    #     entry render 函數回完整 message dict（type=quick_reply 帶 LIFF uri action）。
    #     Quick Reply 按完即消失，不留歷史殘留 — 比 Flex bubble 體驗好。
    if text in _NEW_CUSTOMER_LIFF_TRIGGERS:
        from rewrite.views.customer_flex import render_new_customer_entry
        # 傳 event.source 才能在群組廣播結果（同 import 的處理）
        reply_message(event.reply_token, render_new_customer_entry(event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF new-customer entry")
        return True

    if text in _BOOKING_LIFF_TRIGGERS:
        from rewrite.views.booking_flex import render_booking_entry
        reply_message(event.reply_token, render_booking_entry(event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF booking entry")
        return True

    if text in _IMPORT_LIFF_TRIGGERS:
        from rewrite.views.import_flex import render_import_entry
        # 把 event.source 傳進去 — 渲染時把 webhook 拿到的真 group_id 塞進 LIFF URL，
        # 否則 LIFF SDK 端拿到的 groupId 是 UUID 格式（≠ LINE 平台 ID），無法 push 廣播
        reply_message(event.reply_token, render_import_entry(event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF import entry")
        return True

    if text in _NEW_FIXED_SCHEDULE_LIFF_TRIGGERS:
        from rewrite.views.fixed_schedule_flex import render_new_fixed_schedule_entry
        reply_message(event.reply_token, render_new_fixed_schedule_entry(event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF new-fixed-schedule entry")
        return True

    if text in _REPORT_LIFF_TRIGGERS:
        from rewrite.views.report_flex import render_report_entry
        reply_message(event.reply_token, render_report_entry(event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF report entry")
        return True

    if text in _ACCOUNTING_LIFF_TRIGGERS:
        # 主入口：查餘額 + 3 按鈕 Flex
        from database import Session
        from rewrite.tools.accounting import query_balance
        from rewrite.views.accounting_flex import render_accounting_menu
        sess = Session()
        try:
            r = query_balance(session=sess)
        finally:
            sess.close()
        balance = r.data.get('balance', 0) if r.ok else 0
        reply_message(event.reply_token, render_accounting_menu(balance, event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → 帳務處理 menu (餘額 {balance})")
        return True

    if text in _ACCOUNTING_LEDGER_TRIGGERS:
        # 查看明細：carousel 橫向翻頁（仿診所班次）
        _render_ledger_carousel(event, short_uid)
        return True

    if text == _ACCOUNTING_LEDGER_RANGE_TRIGGER:
        # 進入日期區間 input mode
        if user_id:
            from rewrite.conversation_state import get_chat_id_from_event
            _state_set(
                user_id,
                ACCT_LEDGER_RANGE_INPUT_STATE_TYPE,
                {},
                ttl_minutes=5.0,
                chat_id=get_chat_id_from_event(event),
            )
        reply_message(event.reply_token, {
            'type': 'quick_reply',
            'text': '請輸入：YYYY-MM-DD YYYY-MM-DD\n例：2026-04-01 2026-04-30',
            'quick_reply': {
                'items': [{
                    'type': 'action',
                    'action': {'type': 'message', 'label': '❌ 取消',
                               'text': '結束對話'},
                }],
            },
        })
        logger.info(f"[rewrite sandbox] {short_uid} → 帳務明細 input range mode")
        return True

    # 帳務明細日期區間 input mode follow-up
    if user_id:
        st = _state_get(user_id)
        if st and st.get('type') == ACCT_LEDGER_RANGE_INPUT_STATE_TYPE:
            handled = _handle_ledger_range_input(event, user_id, short_uid, text)
            if handled:
                return True

    if text in _BATCH_ALLOWANCE_LIFF_TRIGGERS:
        from rewrite.views.batch_allowance_flex import render_batch_allowance_entry
        reply_message(event.reply_token, render_batch_allowance_entry(event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF batch_allowance entry")
        return True

    # 0b'''. 幫助命令（取代 legacy help_router）
    if text in _HELP_TRIGGERS:
        reply_message(event.reply_token, {'type': 'text', 'text': _HELP_TEXT})
        logger.info(f"[rewrite sandbox] {short_uid} → help")
        return True

    # 0b''. admin 命令橋接：資料庫同步（保留 legacy database_sync_handler 業務邏輯）
    if text in _DB_SYNC_TRIGGERS:
        from modules.handlers.sync_router import handle_sync_commands
        try:
            handle_sync_commands(text, user_id, event.reply_token)
            logger.info(f"[rewrite sandbox] {short_uid} → DB sync bridge: {text!r}")
        except Exception as e:
            logger.error(f"[rewrite sandbox] {short_uid} DB sync bridge failed: {e}",
                         exc_info=True)
            reply_message(event.reply_token, {
                'type': 'text', 'text': f'❌ 資料庫同步失敗: {e}',
            })
        return True

    # 0b'. 「[date][location]的狀態」入口（regex match，搬 legacy clarify_user_intent）
    parsed = _parse_status_query(text)
    if parsed:
        d, location, date_str = parsed
        _render_trip_status_picker_for_user(
            event, user_id, short_uid, d, location, date_str,
        )
        return True

    # 0.5 取上一輪 context（給 master agent prompt prefix 用）
    #     history 跨輪累積（含本輪前的 user/ai 對），讓 AI 看到完整脈絡
    #     例：「!固定班次29請假」→「原因？」→「出國」→「加成？」→「-50」
    #         turn 3 必須看得到 turn 1 的 schedule_id=29
    history: list = []
    if user_id:
        prev = _state_get(user_id)
        if prev and prev.get('type') == SANDBOX_ACTIVE_STATE_TYPE:
            payload = prev.get('payload') or {}
            history = payload.get('history') or []

    # 1. 跑 Master Agent — 一個 LLM call 含全部 ~25 atomic tools
    #    取代原本「intent classifier (call 1) + skill agent (call 2+)」雙 call 架構
    #    收益：延遲砍 ~50%、無 intent misclassify 風險
    #    對 short follow-up 的處理：靠 history prepend 讓 master 自己看上下文判斷
    #    （不再需要「sandbox-active + last_skill bypass classifier」hack）
    try:
        agent = Agent(_llm, _master_skill)
        text_for_agent = text
        if history:
            lines = []
            for h in history:
                u = (h.get('user') or '').strip()
                a = (h.get('ai') or '').strip()
                if u:
                    lines.append(f"用戶：{u}")
                if a:
                    lines.append(f"你：{a[:200]}")
            if lines:
                text_for_agent = (
                    "[最近對話歷程 — 跨多輪 follow-up]\n"
                    + "\n".join(lines)
                    + f"\n[本輪用戶說]\n{text}"
                )
        msg = agent.process(text_for_agent, user_id, event_source=event.source)
    except Exception as e:
        logger.error(
            f"[rewrite sandbox] {short_uid} master agent failed: {e}",
            exc_info=True,
        )
        reply_message(event.reply_token, {
            'type': 'text',
            'text': '⚠️ 處理時發生錯誤，請稍後再試或輸入「幫助」',
        })
        return True

    # 3. 判斷 AI 是否在等 follow-up
    #    是 → decorate（進度條 + 結束按鈕）+ 設 sandbox-active state（90 秒可不加 !）
    #    否 → 不 decorate、不設 state（用戶下一句要 ! 前綴）
    waiting_followup = _ai_is_waiting_for_followup(msg)
    if waiting_followup:
        _decorate_with_conversation_hint(msg)

    # 4. reply
    try:
        reply_message(event.reply_token, msg)
        logger.info(
            f"[rewrite sandbox] {short_uid} text={text!r} master_agent "
            f"followup={waiting_followup} ✅")
    except Exception as e:
        logger.error(
            f"[rewrite sandbox] {short_uid} reply failed: {e}", exc_info=True)
        return True  # 已執行 mutation／LLM call，不再 fall-through 避免重複

    # 5. 只有 AI 在等 follow-up 時才設 sandbox-active state
    #    （AI 完成單一動作就 reply 完了，不該再攔下一句訊息）
    if user_id and waiting_followup:
        ai_text_summary: str = ''
        if isinstance(msg, dict):
            mt = msg.get('type')
            # decoration 會把 type 從 text 改成 quick_reply，兩個都認
            if mt in ('text', 'quick_reply'):
                ai_text_summary = (msg.get('text') or '')[:300]
            elif mt == 'flex':
                ai_text_summary = f"[flex] {msg.get('altText', '')}"

        # 累積 history：本輪 user + ai 追加進去（master 模式不分 skill，一直累）
        history = history + [{'user': text[:300], 'ai': ai_text_summary}]
        # cap 最近 5 輪，避免 prompt 撐爆
        history = history[-5:]

        from rewrite.conversation_state import get_chat_id_from_event
        _state_set(
            user_id,
            SANDBOX_ACTIVE_STATE_TYPE,
            {
                'last_skill': 'master',
                'last_user_text': text[:300],
                'last_ai_text': ai_text_summary,
                'history': history,
            },
            ttl_minutes=SANDBOX_ACTIVE_TTL_MINUTES,
            chat_id=get_chat_id_from_event(event),
        )
    return True


# AI 是否在等 follow-up 的判斷字眼
_FOLLOWUP_INDICATOR_KEYWORDS = (
    '請問', '請提供', '請輸入', '請告訴', '請告知', '請說明', '請確認',
    '請給', '請填', '請補充', '請選擇',
    '是否確認', '是否要', '確定要', '確認要',
    '需要', '想要', '想知道',
)


def _ai_is_waiting_for_followup(msg: dict) -> bool:
    """
    判斷 AI 的 reply 是否在等用戶 follow-up（如缺資訊、要確認等）

    啟發式：
    - 結尾有問號 (？/?)
    - 含「請問」「請提供」「請輸入」「請確認」「是否要」等請求字眼
    - flex 訊息（詳情卡 / 列表）視為「結果回覆」，不算 follow-up

    用於決定是否：
    1. 在 reply 加「對話模式進行中」提示 + 結束按鈕
    2. 設 sandbox-active state（90 秒攔下一句免 ! 前綴）
    """
    if not isinstance(msg, dict) or msg.get('type') != 'text':
        return False
    text = (msg.get('text') or '').strip()
    if not text:
        return False
    # 結尾問號 → 等回答
    if text.rstrip().endswith(('？', '?')):
        return True
    # 含請求字眼
    return any(kw in text for kw in _FOLLOWUP_INDICATOR_KEYWORDS)


def _decorate_with_conversation_hint(msg: dict) -> None:
    """
    給 reply 加「對話模式進行中」視覺提示（in-place）：
      - text 訊息：append 提示文字 + Quick Reply [❌ 結束對話]
        ⚠️ legacy modules/utils/line_bot.py reply_message 對 type=text
           不處理 quickReply 欄位，只認 type=quick_reply + quick_reply（snake_case）。
           所以這裡把 type 改成 quick_reply（不是 LINE API 原生格式但 main 自定義）。
      - flex 訊息：不動（避免擠掉原 quickReply 如 [註銷] [衝突] [請假]）

    用戶可隨時打「結束」「結束對話」「退出」清掉 sandbox-active state。
    """
    if not isinstance(msg, dict):
        return
    if msg.get('type') != 'text':
        return  # flex 訊息不處理

    # append 進行中提示
    original = msg.get('text', '')
    if '對話模式' not in original:
        msg['text'] = original.rstrip() + (
            f"\n\n💬 對話模式進行中（{int(SANDBOX_ACTIVE_TTL_MINUTES * 60)}秒內可不加 ! 前綴回覆）"
        )

    # 切到 type=quick_reply 讓 line_bot.py 的 quickReply 邏輯生效
    msg['type'] = 'quick_reply'

    # 收 quickReply / quick_reply 兩種 key 寫法都接
    qr_dict = msg.pop('quickReply', None) or msg.get('quick_reply') or {}
    items = list(qr_dict.get('items') or [])
    has_end_btn = any(
        i.get('action', {}).get('text') in _END_CONVERSATION_TEXTS
        for i in items
    )
    if not has_end_btn:
        items.append({
            'type': 'action',
            'action': {
                'type': 'message',
                'label': '❌ 結束對話',
                'text': '結束對話',
            },
        })
    msg['quick_reply'] = {'items': items}


# ============================================================
# 「[date][location]的狀態」流程：picker render + 批次 actions + leave input
# ============================================================

def _render_trip_status_picker_for_user(
    event, user_id: Optional[str], short_uid: str,
    d: _date, location: str, date_label: str,
) -> None:
    """跑 query → render picker → reply → 設 state（讓後續 Quick Reply 免前綴）"""
    from database import Session
    from rewrite.tools.trip import query_trips
    from rewrite.views.trip_status_flex import render_trip_status_picker

    session = Session()
    try:
        result = query_trips(
            session=session,
            date_from=d, date_to=d,
            customer_short_name=location,
            exclude_status=['已完成'],
        )
    finally:
        session.close()

    if not result.ok:
        reply_message(event.reply_token, {
            'type': 'text',
            'text': f'📭 沒找到 {date_label}「{location}」的相關班次\n\n💡 確認日期和客戶簡稱',
        })
        logger.info(f"[rewrite sandbox] {short_uid} status query empty: {date_label} {location}")
        return

    trips = result.data
    msg = render_trip_status_picker(
        trips, date_label=date_label, location_label=location,
    )
    reply_message(event.reply_token, msg)

    # 設 state，讓後續按鈕（全部請假/註銷/衝突/改回準備）能找到 trip_ids
    if user_id:
        from rewrite.conversation_state import get_chat_id_from_event
        trip_ids = [t.trip_id for t in trips]
        _state_set(
            user_id,
            TRIP_STATUS_PICKER_STATE_TYPE,
            {
                'trip_ids': trip_ids,
                'date': d.isoformat(),
                'date_label': date_label,
                'location': location,
            },
            ttl_minutes=TRIP_STATUS_TTL_MINUTES,
            chat_id=get_chat_id_from_event(event),
        )
    logger.info(
        f"[rewrite sandbox] {short_uid} status picker {date_label} {location} "
        f"({len(trips)} trips)"
    )


def _try_handle_trip_status_actions(event, user_id: Optional[str], text: str,
                                     short_uid: str) -> Optional[bool]:
    """trip_status state-aware action handlers

    Returns:
        True / False — 已處理（True=ok, False=讓 caller fall-through）
        None — 不適用此 handler（caller 繼續正常流程）
    """
    if not user_id:
        return None
    state = _state_get(user_id)
    if not state:
        return None
    state_type = state.get('type')

    # ---- (1) Picker 階段：用戶按了批次操作按鈕 ----
    if state_type == TRIP_STATUS_PICKER_STATE_TYPE:
        action = _BATCH_STATUS_ACTIONS.get(text)
        if not action:
            # 不是批次按鈕（可能是「班次詳情 N」、新查詢、雜訊）→ 不處理，
            # 讓 caller 走原本流程（會 hit LIFF triggers / hard_fallthrough / classifier）
            return None
        payload = state.get('payload') or {}
        trip_ids = payload.get('trip_ids') or []
        if not trip_ids:
            _state_clear(user_id)
            reply_message(event.reply_token, {
                'type': 'text', 'text': '❌ 班次清單已過期，請重新查詢',
            })
            return True

        if action == 'leave':
            # 進 leave_input state，等用戶輸入 [原因] [加成]
            from rewrite.conversation_state import get_chat_id_from_event
            _state_set(
                user_id,
                TRIP_STATUS_LEAVE_INPUT_STATE_TYPE,
                {
                    'trip_ids': trip_ids,
                    'date_label': payload.get('date_label'),
                    'location': payload.get('location'),
                },
                ttl_minutes=TRIP_STATUS_TTL_MINUTES,
                chat_id=get_chat_id_from_event(event),
            )
            reply_message(event.reply_token, {
                'type': 'quick_reply',
                'text': (
                    f"📋 批量請假模式（{len(trip_ids)} 班）\n\n"
                    f"🚕 班次：{', '.join(f'#{i}' for i in trip_ids[:5])}"
                    + (f" 等 {len(trip_ids)} 筆" if len(trip_ids) > 5 else "")
                    + "\n\n請輸入：[原因] [加成]\n例：化療 -30 / 出國 -50"
                ),
                'quick_reply': {
                    'items': [{
                        'type': 'action',
                        'action': {'type': 'message', 'label': '❌ 取消',
                                   'text': '結束對話'},
                    }],
                },
            })
            logger.info(
                f"[rewrite sandbox] {short_uid} batch-leave mode "
                f"trip_ids={trip_ids[:5]}{'...' if len(trip_ids) > 5 else ''}"
            )
            return True

        # cancel / conflict / restore：直接執行
        _execute_batch_status_action(
            event, user_id, short_uid, action, trip_ids, payload,
        )
        return True

    # ---- (2) Leave-input 階段：用戶輸入 [原因] [加成] ----
    if state_type == TRIP_STATUS_LEAVE_INPUT_STATE_TYPE:
        parsed = _parse_leave_input(text)
        if parsed is None:
            # 格式不符 → 提醒，但不清 state（讓用戶重試）
            reply_message(event.reply_token, {
                'type': 'quick_reply',
                'text': (
                    f"❌ 格式不對，要 [原因] [加成]\n"
                    f"例：化療 -30、出國 -50、自己來 -100\n"
                    f"輸入「結束對話」取消"
                ),
                'quick_reply': {
                    'items': [{
                        'type': 'action',
                        'action': {'type': 'message', 'label': '❌ 取消',
                                   'text': '結束對話'},
                    }],
                },
            })
            return True

        reason, surcharge = parsed
        payload = state.get('payload') or {}
        trip_ids = payload.get('trip_ids') or []
        _execute_batch_passenger_leave(
            event, user_id, short_uid, trip_ids, reason, surcharge,
        )
        return True

    return None


def _parse_leave_input(text: str) -> Optional[tuple[str, int]]:
    """parse 「[原因] [加成]」like '化療 -30'  '出國 -50'

    Returns (reason, surcharge_int) or None。
    需嚴格 2 個 space-separated tokens，第二個必須是 int（可正可負）。
    """
    parts = text.strip().split()
    if len(parts) != 2:
        return None
    reason, num_str = parts[0].strip(), parts[1].strip()
    if not reason:
        return None
    try:
        surcharge = int(num_str)
    except ValueError:
        return None
    return reason, surcharge


def _execute_batch_status_action(
    event, user_id: str, short_uid: str,
    action: str, trip_ids: list, payload: dict,
) -> None:
    """執行批次 cancel / conflict / restore（無 follow-up）"""
    from database import Session
    from rewrite.tools.trip import cancel_trip, mark_conflict, restore_to_ready

    op_map = {
        'cancel': (cancel_trip, '註銷', '🚫'),
        'conflict': (mark_conflict, '衝突', '⚠️'),
        'restore': (restore_to_ready, '改回準備', '✅'),
    }
    op_fn, action_label, emoji = op_map[action]

    success_ids: list[int] = []
    failed: list[tuple[int, str]] = []

    for tid in trip_ids:
        sess = Session()
        try:
            r = op_fn(
                session=sess, trip_id=tid,
                user_id=user_id, via='sandbox_status_picker',
            )
            if r.ok:
                success_ids.append(tid)
            else:
                failed.append((tid, r.error or 'unknown'))
        except Exception as e:
            sess.rollback()
            failed.append((tid, str(e)[:60]))
        finally:
            sess.close()

    _state_clear(user_id)

    location = payload.get('location') or ''
    date_label = payload.get('date_label') or ''
    msg_lines = [
        f"{emoji} 批量{action_label}完成",
        f"📍 {date_label}｜{location}",
        f"✅ 成功 {len(success_ids)}/{len(trip_ids)} 筆",
    ]
    if success_ids:
        msg_lines.append(f"🚕 班次：{', '.join(f'#{i}' for i in success_ids[:8])}"
                         + (f" 等" if len(success_ids) > 8 else ""))
    if failed:
        msg_lines.append("\n⚠️ 失敗：")
        for tid, err in failed[:3]:
            msg_lines.append(f"  #{tid}：{err[:50]}")

    reply_message(event.reply_token, {'type': 'text', 'text': '\n'.join(msg_lines)})
    logger.info(
        f"[rewrite sandbox] {short_uid} batch {action_label} "
        f"ok={len(success_ids)} fail={len(failed)}"
    )


def _execute_batch_passenger_leave(
    event, user_id: str, short_uid: str,
    trip_ids: list, reason: str, surcharge: int,
) -> None:
    """執行批次 passenger_leave（leave_input 階段執行）"""
    from database import Session
    from rewrite.tools.trip import passenger_leave

    success_ids: list[int] = []
    failed: list[tuple[int, str]] = []

    for tid in trip_ids:
        sess = Session()
        try:
            r = passenger_leave(
                session=sess, trip_id=tid,
                reason=reason, surcharge=surcharge,
                user_id=user_id, via='sandbox_status_picker',
            )
            if r.ok:
                success_ids.append(tid)
            else:
                failed.append((tid, r.error or 'unknown'))
        except Exception as e:
            sess.rollback()
            failed.append((tid, str(e)[:60]))
        finally:
            sess.close()

    _state_clear(user_id)

    msg_lines = [
        f"🏥 批量請假完成",
        f"✅ 成功 {len(success_ids)}/{len(trip_ids)} 筆",
        f"📝 原因：{reason}",
        f"💰 加成：{surcharge:+d} 元",
    ]
    if success_ids:
        msg_lines.append(
            f"🚕 班次：{', '.join(f'#{i}' for i in success_ids[:8])}"
            + (f" 等" if len(success_ids) > 8 else "")
        )
    if failed:
        msg_lines.append("\n⚠️ 失敗：")
        for tid, err in failed[:3]:
            msg_lines.append(f"  #{tid}：{err[:50]}")

    reply_message(event.reply_token, {'type': 'text', 'text': '\n'.join(msg_lines)})
    logger.info(
        f"[rewrite sandbox] {short_uid} batch passenger_leave "
        f"ok={len(success_ids)} fail={len(failed)} reason={reason!r} surcharge={surcharge}"
    )


# ============================================================
# 帳務明細：cursor pagination + 日期區間篩選（對齊 main 版完整功能）
# ============================================================

def _render_ledger_carousel(
    event, short_uid: str,
    *,
    from_date_str: Optional[str] = None,
    to_date_str: Optional[str] = None,
) -> None:
    """帳務明細 carousel 渲染（橫向翻頁，仿診所班次風格）

    一次撈 LEDGER_CAROUSEL_MAX_ROWS 筆，view 切成 12 bubbles × 10 筆
    超過上限最後一張 bubble 顯「還有 N+ 筆」提示。
    """
    from database import Session
    from rewrite.tools.accounting import query_balance, query_ledger_carousel
    from rewrite.views.accounting_flex import render_ledger_carousel as render_carousel

    fd = _date.fromisoformat(from_date_str) if from_date_str else None
    td = _date.fromisoformat(to_date_str) if to_date_str else None

    sess = Session()
    try:
        r_bal = query_balance(session=sess)
        r_log = query_ledger_carousel(session=sess, from_date=fd, to_date=td)
    finally:
        sess.close()

    balance = r_bal.data.get('balance', 0) if r_bal.ok else 0
    rows = r_log.data if r_log.ok else []
    has_more = bool(r_log.meta.get('has_more')) if r_log.ok else False

    msg = render_carousel(
        rows,
        balance=balance,
        from_date=from_date_str,
        to_date=to_date_str,
        has_more=has_more,
    )
    reply_message(event.reply_token, msg)
    logger.info(
        f"[rewrite sandbox] {short_uid} 帳務明細 carousel "
        f"rows={len(rows)} has_more={has_more} range={from_date_str}~{to_date_str}"
    )


def _handle_ledger_range_input(event, user_id: str, short_uid: str, text: str) -> bool:
    """日期區間 input mode follow-up parser

    Returns:
        True — 已處理（不論 OK / 格式錯）
        False — 不處理（讓上層繼續流程）
    """
    parts = text.strip().split()
    if len(parts) != 2:
        reply_message(event.reply_token, {
            'type': 'quick_reply',
            'text': '❌ 格式：YYYY-MM-DD YYYY-MM-DD\n請重新輸入或取消',
            'quick_reply': {
                'items': [{
                    'type': 'action',
                    'action': {'type': 'message', 'label': '❌ 取消',
                               'text': '結束對話'},
                }],
            },
        })
        return True

    try:
        fd = _date.fromisoformat(parts[0])
        td = _date.fromisoformat(parts[1])
    except ValueError:
        reply_message(event.reply_token, {
            'type': 'quick_reply',
            'text': '❌ 日期格式錯（要 YYYY-MM-DD）\n例：2026-04-01 2026-04-30',
            'quick_reply': {
                'items': [{
                    'type': 'action',
                    'action': {'type': 'message', 'label': '❌ 取消',
                               'text': '結束對話'},
                }],
            },
        })
        return True

    if fd > td:
        reply_message(event.reply_token, {
            'type': 'text', 'text': '❌ 起日不能晚於迄日',
        })
        return True

    # 套用篩選 → carousel
    _state_clear(user_id)
    _render_ledger_carousel(
        event, short_uid,
        from_date_str=fd.isoformat(),
        to_date_str=td.isoformat(),
    )
    return True


