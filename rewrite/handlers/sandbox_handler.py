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
from typing import Optional

from modules.utils.line_bot import reply_message
from rewrite.ai.agent import Agent
from rewrite.ai.client import GeminiClient
from rewrite.ai.intent import classify
from rewrite.ai.skills.completed_trip import build_completed_trip_skill
from rewrite.ai.skills.customer import build_customer_skill
from rewrite.ai.skills.fixed_schedule import build_fixed_schedule_skill
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

# 觸發 LIFF 批量加成表單入口
_BATCH_ALLOWANCE_LIFF_TRIGGERS = {
    '批量加成', '批次加成', '批量改加成', 'batch-allowance',
}

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
# 第一次呼叫才 init Gemini（避免 import 時就連線）
# ============================================================
_llm: Optional[GeminiClient] = None
_skills: Optional[dict] = None


def _init():
    global _llm, _skills
    if _llm is None:
        _llm = GeminiClient()
        _skills = {
            'trip_query': build_trip_query_skill(),
            'trip_mutation': build_trip_mutation_skill(),
            'completed_trip': build_completed_trip_skill(),
            'customer': build_customer_skill(),
            'fixed_schedule': build_fixed_schedule_skill(),
        }
        logger.info(f"[rewrite sandbox] initialized {len(_skills)} skills")


def _strip_prefix(text: str) -> str:
    """剝掉 sandbox 前綴：!  ！  /!  /！"""
    if not text:
        return ''
    text = text.strip()
    for p in ('/!', '/！', '!', '！'):
        if text.startswith(p):
            return text[len(p):].lstrip()
    return text


# Hard fall-through 關鍵字 — rewrite **明確沒做**的功能，不論 classifier
# 怎麼判斷都直接讓 legacy 處理。比 LLM-based intent 判斷更可靠。
# （legacy customers_ai_service 仍能處理這些）
_HARD_FALLTHROUGH_KEYWORDS = (
    '匯入',  # 匯入固定班次 / 匯入本週
    '預約',  # 預約叫車 / 預約班次（booking_create）
    '報表',  # 生成週報表 / 日報表
    '日報',
    '週報',
    '周報',
    'booking',
    'import',
)


def _should_hard_fallthrough(text: str) -> bool:
    """訊息含「匯入」「預約」「報表」等 → 直接 fall-through legacy"""
    lower = text.lower()
    return any(kw in lower for kw in _HARD_FALLTHROUGH_KEYWORDS)


# 已知的「快速命令」前綴（包含 rewrite + legacy 常用）
# sandbox-active 期間，用戶若打這類命令 → 不該攔，讓他做別的事
_QUICK_COMMAND_PREFIXES = (
    # rewrite quick commands
    '查客戶', '客戶詳情', '病歷層',
    '查班次', '診所班次', '東洋班次',
    '班次詳情', '待派班次',
    '班次註銷', '班次衝突', '班次請假',
    '班次恢復', '班次撤銷指派',
    '批量請假',
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
    return cleaned.startswith(_QUICK_COMMAND_PREFIXES)


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

    # 0b. LIFF 表單 exact-match 觸發詞（要在 hard fall-through 之前 check）
    #     rewrite 已用 LIFF 接管 customer/booking/import → 訊息 in *_LIFF_TRIGGERS
    #     會被 hard_fallthrough 的「預約」/「匯入」keyword 偷走，所以順序要調整。
    #
    #     entry render 函數回完整 message dict（type=quick_reply 帶 LIFF uri action）。
    #     Quick Reply 按完即消失，不留歷史殘留 — 比 Flex bubble 體驗好。
    if text in _NEW_CUSTOMER_LIFF_TRIGGERS:
        from rewrite.views.customer_flex import render_new_customer_entry
        reply_message(event.reply_token, render_new_customer_entry())
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF new-customer entry")
        return True

    if text in _BOOKING_LIFF_TRIGGERS:
        from rewrite.views.booking_flex import render_booking_entry
        reply_message(event.reply_token, render_booking_entry())
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF booking entry")
        return True

    if text in _IMPORT_LIFF_TRIGGERS:
        from rewrite.views.import_flex import render_import_entry
        reply_message(event.reply_token, render_import_entry())
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF import entry")
        return True

    if text in _NEW_FIXED_SCHEDULE_LIFF_TRIGGERS:
        from rewrite.views.fixed_schedule_flex import render_new_fixed_schedule_entry
        reply_message(event.reply_token, render_new_fixed_schedule_entry())
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF new-fixed-schedule entry")
        return True

    if text in _REPORT_LIFF_TRIGGERS:
        from rewrite.views.report_flex import render_report_entry
        reply_message(event.reply_token, render_report_entry())
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
        reply_message(event.reply_token, render_accounting_menu(balance))
        logger.info(f"[rewrite sandbox] {short_uid} → 帳務處理 menu (餘額 {balance})")
        return True

    if text in _BATCH_ALLOWANCE_LIFF_TRIGGERS:
        from rewrite.views.batch_allowance_flex import render_batch_allowance_entry
        reply_message(event.reply_token, render_batch_allowance_entry())
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF batch_allowance entry")
        return True

    # 0c. Hard fall-through 關鍵字（rewrite 明確沒做的功能 / 帶參數的舊 booking 流程）
    #     用戶若打「!預約 明天3點台北」這種帶參數版仍走 legacy（rewrite LIFF 是空 form 起步）
    if _should_hard_fallthrough(text):
        logger.info(
            f"[rewrite sandbox] {short_uid} text={text!r} → hard fall-through "
            f"(keyword match)"
        )
        return False

    # 0.5 取上一輪 context（給 classifier hint + agent prompt prefix 用）
    #     history 是跨輪累積（含本輪前的 user/ai 對），讓 AI 看到完整脈絡
    #     例：「!固定班次29請假」→「原因？」→「出國」→「加成？」→「-50」
    #         turn 3 必須看得到 turn 1 的 schedule_id=29
    last_skill = None
    last_user_text = None
    last_ai_text = None
    history: list = []
    if user_id:
        prev = _state_get(user_id)
        if prev and prev.get('type') == SANDBOX_ACTIVE_STATE_TYPE:
            payload = prev.get('payload') or {}
            last_skill = payload.get('last_skill')
            last_user_text = payload.get('last_user_text')
            last_ai_text = payload.get('last_ai_text')
            history = payload.get('history') or []

    # 1. 分類意圖
    #    1a. sandbox-active + 短 follow-up → 直接用 last_skill，bypass classifier
    #        （classifier 對「是」「確認」「14」常判 unknown，會破壞對話連續）
    if last_skill and last_skill in _skills and _is_short_followup(text):
        intent = last_skill
        logger.info(
            f"[rewrite sandbox] {short_uid} short follow-up text={text!r} → "
            f"bypass classifier, use last_skill={intent}")
    else:
        try:
            intent = classify(_llm, text, last_skill=last_skill)
        except Exception as e:
            logger.error(f"[rewrite sandbox] classify failed for {short_uid}: {e}",
                         exc_info=True)
            return False

        # 1b. 對話模式保護：sandbox-active 期間 classifier 判 unknown
        #     + 訊息不像快速命令 → 留 last_skill 不 fall-through。
        #     防止用戶補資訊式訊息（如 '$235（一般記賬）'、'一般紀錄'）長度過長
        #     沒被 _is_short_followup 抓到，被 classifier 判 unknown 後
        #     hijack 到 legacy 的 booking_create / customer_sandbox。
        #     用戶想切換主題：(a) 打 `!` + 新指令；(b) 打「結束對話」清 state
        if (intent == 'unknown' and last_skill and last_skill in _skills
                and not looks_like_quick_command(text)):
            logger.info(
                f"[rewrite sandbox] {short_uid} text={text!r} → unknown but "
                f"sandbox-active({last_skill}) → 留 last_skill 保護對話")
            intent = last_skill
        elif intent == 'unknown' or intent not in _skills:
            logger.info(
                f"[rewrite sandbox] {short_uid} text={text!r} → {intent}, "
                f"fall-through")
            return False

    # 2. 跑對應 skill（含 multi-turn tool loop + 跨輪對話 context）
    try:
        agent = Agent(_llm, _skills[intent])
        # 把跨輪對話塞進 prompt，讓 AI 看到完整脈絡（含 turn 1 的 schedule_id 等）
        text_for_agent = text
        if history and last_skill == intent:
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
        msg = agent.process(text_for_agent, user_id)
    except Exception as e:
        logger.error(
            f"[rewrite sandbox] {short_uid} skill={intent} failed: {e}",
            exc_info=True,
        )
        return False  # error 也 fall-through legacy

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
            f"[rewrite sandbox] {short_uid} text={text!r} skill={intent} "
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

        # 累積 history：本輪 user + ai 追加進去，但不同 skill 切換時清掉重來
        if last_skill != intent:
            history = []
        history = history + [{'user': text[:300], 'ai': ai_text_summary}]
        # cap 最近 5 輪，避免 prompt 撐爆
        history = history[-5:]

        _state_set(
            user_id,
            SANDBOX_ACTIVE_STATE_TYPE,
            {
                'last_skill': intent,
                'last_user_text': text[:300],
                'last_ai_text': ai_text_summary,
                'history': history,
            },
            ttl_minutes=SANDBOX_ACTIVE_TTL_MINUTES,
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
