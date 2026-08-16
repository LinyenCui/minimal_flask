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
    # AI mutation 機制層確認共用常數（定義在 conversation_state 這個 leaf
    # module 防 import 循環）— 從這裡 re-export 給 webhook / 測試用
    PENDING_MUTATION_STATE_TYPE,
    PENDING_MUTATION_TTL_MINUTES,
    MUTATION_CONFIRM_TEXT as _MUTATION_CONFIRM_TEXT,
    MUTATION_CANCEL_TEXT as _MUTATION_CANCEL_TEXT,
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

# 觸發藥名 ↔ 診斷碼關聯維護 LIFF 入口（v3 最小版）
_DRUG_DX_LINK_LIFF_TRIGGERS = {
    '藥診關聯', '新增藥診關聯',
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
# 單一來源：rewrite/help_registry.py（觸發詞 + 全部文案都在那，新功能記得去加一行）
# 註：不要放 '?' / '？' —— 群聊極常用,會被當 help 誤觸（同「藥」裸字教訓）。
from rewrite.help_registry import (
    HELP_TRIGGERS as _HELP_TRIGGERS,
    try_handle_help as _try_handle_help,
)

# 群聊閘門 / sandbox-active 共用：所有「exact-match 即視為指令」的觸發詞聯集。
# 單一來源,避免和上面各 *_LIFF_TRIGGERS 漂移。
# (修舊 bug：今天X的狀態 / 新增客戶 / 帳務處理 / 生成月報表 / 批量加成 /
#  新增固定班次 等因白名單漏列,在群聊無 / 前綴時被靜默丟棄。)
# 「的狀態」是 suffix pattern,另在 looks_like_quick_command 用 _RE_STATUS_QUERY 補認。
_ALL_EXACT_COMMAND_TRIGGERS = (
    _NEW_CUSTOMER_LIFF_TRIGGERS
    | _BOOKING_LIFF_TRIGGERS
    | _IMPORT_LIFF_TRIGGERS
    | _NEW_FIXED_SCHEDULE_LIFF_TRIGGERS
    | _REPORT_LIFF_TRIGGERS
    | _ACCOUNTING_LIFF_TRIGGERS
    | _ACCOUNTING_LEDGER_TRIGGERS
    | _BATCH_ALLOWANCE_LIFF_TRIGGERS
    | _DB_SYNC_TRIGGERS
    | _HELP_TRIGGERS
    | {'重置班次序號', '歸檔檢查', '備份檢查', '歸檔狀態',
       '推播用量', '推播統計', '推播額度', 'push用量',
       '歸檔清理', '確認清理', '取消清理'}
)
# 註：_DRUG_DX_LINK_LIFF_TRIGGERS 刻意不納入聯集 —— 藥診關聯在群組有自己的前綴
# 政策（_is_drug_dx_link_liff_trigger 群組只收 / ! ！ 前綴）。若把裸字「藥診關聯」
# 放進群聊放行,閘門會放行但 dispatch 不接,白白多燒一次 AI call。

# ====== 「[date][location]的狀態」狀態管理流程 ======
# 用戶常用：「!今天二井家的狀態」「!5/9馬鎮宮的狀態」
# 流程：parse → query trips → render picker (Flex + Quick Reply)
#       → 用戶按 [全部請假/註銷/衝突/改回準備] → 對 trip_ids 批次操作
#       → 「全部請假」需要再問 [原因] [加成]，其他按了直接執行
ARCHIVE_PURGE_STATE_TYPE = 'rewrite_archive_purge'   # 歸檔清理待確認
TRIP_STATUS_PICKER_STATE_TYPE = 'rewrite_trip_status_picker'
TRIP_STATUS_LEAVE_INPUT_STATE_TYPE = 'rewrite_trip_status_leave_input'

from rewrite.conversation_state import MUTATION_CONFIRM_TEXT
from rewrite.tools.leave_guard import (
    is_zero_surcharge,
    warning_text as zero_surcharge_warning,
)
TRIP_STATUS_TTL_MINUTES = 5.0  # 5 分鐘思考時間（比 SANDBOX_ACTIVE 90 秒長）

# 批次操作觸發詞 → action label
_BATCH_STATUS_ACTIONS = {
    '全部請假': 'leave',     # 需問 [原因] [加成]，進 leave_input state
    '全部註銷': 'cancel',
    '全部衝突': 'conflict',
    '全部改回準備': 'restore',
}

# ====== AI mutation 機制層確認 ======
# agent.py 的 tool loop 攔下 AI 發出的 mutation calls（不執行）後設此 state，
# payload = {'calls': [(tool_name, args)], 'preview': str}，chat_id 必填（防跨對話）。
# 用戶按 [✅ 確認執行] 才由 execute_confirmed_calls 真正執行、[❌ 取消操作] 放棄。
# 常數本體在 rewrite/conversation_state.py（頂部 import 進來 re-export）。

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

# 同指令進行中防抖 — Gemini 偶發慢呼叫（實測 40s+）時用戶會重發同一句，
# 兩個請求平行打 Gemini 互撞 429、又各回一則造成重複（2026-07-14 log）。
# in-flight dict：(user_id, text) → 開始時間；處理完 finally 清除，
# MAX_SECONDS 是崩潰未清時的保險失效線。
_AGENT_INFLIGHT: dict = {}
_AGENT_INFLIGHT_MAX_SECONDS = 120

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


def _is_drug_dx_link_liff_trigger(raw: str, source_type: str | None) -> bool:
    """藥診關聯 LIFF 入口（全部 exact-match）：
    群組 group/room 收 / 與 ! / ！ 前綴；私聊 user 另收無前綴。
    """
    cleaned = (raw or '').strip()
    if source_type in ('group', 'room'):
        return cleaned in {
            '/藥診關聯',
            '/新增藥診關聯',
            '!藥診關聯',
            '!新增藥診關聯',
            '！藥診關聯',
            '！新增藥診關聯',
        }
    if source_type == 'user':
        return cleaned in {
            '藥診關聯',
            '新增藥診關聯',
            '/藥診關聯',
            '/新增藥診關聯',
            '!藥診關聯',
            '!新增藥診關聯',
            '！藥診關聯',
            '！新增藥診關聯',
        }
    return False


# ====== 司機管理（admin 指令，全部 reply 零 push）======
# 司機清單一律動態撈 DB（不寫死）→ 增減司機不用改程式，
# 這也是「司機自助回報車資」LIFF 表單「請問你是哪一位？」的資料來源。
_DRIVER_LIST_TRIGGERS = {'司機列表', '司機清單'}
_DRIVER_ADMIN_PREFIXES = ('新增司機', '停用司機', '啟用司機', '解綁司機')


def _looks_like_driver_admin(text: str) -> bool:
    s = (text or '').strip()
    return s in _DRIVER_LIST_TRIGGERS or s.startswith(_DRIVER_ADMIN_PREFIXES)


def _render_driver_list(drivers) -> str:
    """司機列表純文字（ID／姓名／車號／綁定狀態／停用標記）"""
    if not drivers:
        return '目前沒有任何司機\n💡 用「新增司機 <編號> <姓名> [車號]」建立'
    lines = [f"🚕 司機列表（共 {len(drivers)} 位）"]
    for d in drivers:
        bits = [f"#{d.id} {d.name or ''}".strip()]
        if d.plate_number:
            bits.append(d.plate_number)
        bits.append('🔗 已綁定' if d.is_bound else '⚪ 未綁定')
        if not d.is_active:
            bits.append('⏸️ 停用')
        lines.append('・' + '｜'.join(bits))
    lines.append('')
    lines.append('💡 新增司機 <編號> <姓名> [車號]')
    lines.append('💡 停用司機 / 啟用司機 / 解綁司機 <編號>')
    return '\n'.join(lines)


def _handle_driver_admin(text: str, user_id: Optional[str]) -> str:
    """司機管理指令 → 回覆文字（業務邏輯全在 rewrite/tools/driver.py）"""
    from database import Session
    from rewrite.tools import driver as driver_tools

    s = (text or '').strip()
    session = Session()
    try:
        if s in _DRIVER_LIST_TRIGGERS:
            r = driver_tools.query_drivers(session=session, active_only=False)
            return _render_driver_list(r.data) if r.ok else f"❌ {r.error}"

        kw = next(k for k in _DRIVER_ADMIN_PREFIXES if s.startswith(k))
        parts = s[len(kw):].strip().split()

        if kw == '新增司機':
            if len(parts) < 2 or not parts[0].isdigit():
                return ('用法：新增司機 <編號> <姓名> [車號]\n'
                        '例：新增司機 61888 陳大文 TDE-1888\n'
                        '💡 編號就是你們慣用的司機車號編號')
            r = driver_tools.create_driver(
                session=session, driver_id=int(parts[0]), name=parts[1],
                plate_number=parts[2] if len(parts) > 2 else None,
                user_id=user_id, via='line_admin',
            )
            if not r.ok:
                return f"❌ {r.error}"
            d = r.data
            plate = f"（{d.plate_number}）" if d.plate_number else ''
            return (f"✅ 已新增司機 #{d.id} {d.name}{plate}\n"
                    f"💡 請他開群組置頂的「回報車資」連結，點自己的名字完成綁定")

        if not parts or not parts[0].isdigit():
            return f"用法：{kw} <司機編號>\n例：{kw} 5386\n💡 打「司機列表」看編號"
        did = int(parts[0])

        if kw in ('停用司機', '啟用司機'):
            active = (kw == '啟用司機')
            r = driver_tools.set_driver_active(
                session=session, driver_id=did, active=active,
                user_id=user_id, via='line_admin',
            )
            if not r.ok:
                return f"❌ {r.error}"
            verb = '啟用' if active else '停用'
            tail = '' if active else '\n（歷史班次不受影響，只是不再出現在司機選單）'
            return f"✅ 已{verb}司機 #{r.data.id} {r.data.name or ''}{tail}"

        # 解綁司機
        r = driver_tools.unbind_driver(
            session=session, driver_id=did, user_id=user_id, via='line_admin',
        )
        if not r.ok:
            return f"❌ {r.error}"
        return (f"✅ 已解除司機 #{r.data.id} {r.data.name or ''} 的 LINE 綁定\n"
                f"💡 他下次開表單會重新出現「請問你是哪一位？」")
    except Exception as e:  # noqa: BLE001 — admin 指令不讓例外冒到 webhook
        logger.error(f"司機管理指令失敗 {text!r}: {e}", exc_info=True)
        return f"❌ 司機管理失敗：{str(e)[:150]}"
    finally:
        session.close()


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
    # 司機管理（admin）：讓「司機列表」「新增司機 61888 陳大文」在群聊免 / 也過閘門
    '司機列表', '司機清單', '新增司機', '停用司機', '啟用司機', '解綁司機',
    # 幫助系統：startswith 讓「幫助 查詢」「幫助 全部」等分類按鈕文字在群聊過閘門
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
    # 藥診關聯 LIFF 群聊入口：! / ！ exact-match 放行（webhook 群聊閘門用本函式）
    # 僅放行這四個精確字串，不開放所有 ! 前綴；尾綴 xxx 不放行
    if text.strip() in {
        '!藥診關聯', '!新增藥診關聯',
        '！藥診關聯', '！新增藥診關聯',
    }:
        return True
    # 剝掉 / # 前綴（群組命令格式）
    cleaned = text.strip().lstrip('/').lstrip('#').strip()
    if cleaned.startswith(_QUICK_COMMAND_PREFIXES):
        return True
    # 已知 LIFF / 命令觸發詞（exact match）— 與 sandbox 實際能處理的一致,
    # 修群聊閘門白名單漏列導致常用指令（今天X的狀態 / 新增客戶 / 帳務處理 /
    # 生成月報表 / 批量加成 / 新增固定班次）在群組無 / 前綴時被靜默丟棄
    if cleaned in _ALL_EXACT_COMMAND_TRIGGERS:
        return True
    # 「[日期][地點]的狀態」（最高頻群聊指令）— 用 _parse_status_query 而非寬鬆的
    # _RE_STATUS_QUERY,確保只放行「有日期前綴 + 地點」的真指令(如 今天二井家的狀態 /
    # 5/9馬鎮宮的狀態),不讓「他的狀態 / 病人的狀態 / 今天的狀態」這類群聊閒聊越過
    # 閘門被丟給 AI(隱私 + 成本外洩)。相容 ! ／ ！ 前綴(用戶常打「!今天X的狀態」),
    # 但只在這條 status 判斷剝 !,不動 cleaned —— date_calc 外掛靠 ! 辨識,不能全域剝。
    if _parse_status_query(cleaned.lstrip('!').lstrip('！').strip()):
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
    source_type = getattr(event.source, 'type', None)
    text = _strip_prefix(raw)

    if not text:
        return False

    short_uid = (user_id or 'anon')[:8]

    # 0⁻. 破壞性指令的管理員閘門（司機自助回報上線後，司機也能接觸 bot）。
    #     未設 ADMIN_USER_IDS 時全部放行 — 不會因為忘了設定而把自己鎖在外面。
    from rewrite.admin_guard import check as _admin_check
    _deny = _admin_check(text, user_id)
    if _deny:
        reply_message(event.reply_token, {'type': 'text', 'text': _deny})
        logger.info(f"[rewrite sandbox] {short_uid} → admin_guard 擋下 {text[:16]!r}")
        return True

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

    # 0a'. AI mutation 機制層確認：[✅ 確認執行] / [❌ 取消操作]
    #      （在 master agent 之前攔，避免確認詞被丟給 AI 燒 call）
    pending_handled = _try_handle_pending_mutation(event, user_id, text, short_uid)
    if pending_handled is not None:
        return pending_handled

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

    if text in _DRUG_DX_LINK_LIFF_TRIGGERS and _is_drug_dx_link_liff_trigger(raw, source_type):
        from rewrite.views.drug_diagnosis_link_flex import render_drug_diagnosis_link_entry
        reply_message(event.reply_token, render_drug_diagnosis_link_entry(event_source=event.source))
        logger.info(f"[rewrite sandbox] {short_uid} → LIFF drug-diagnosis link entry")
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

    # 0b'''. 幫助命令（單一來源 rewrite/help_registry.py）
    #        「幫助」→ 總覽＋分類 Quick Reply；「幫助 查詢」→ 分類清單；
    #        「幫助 全部」→ 全清單。「幫助 <不認得>」回 None 留給 AI（不劫持）。
    _help_msg = _try_handle_help(text)
    if _help_msg is not None:
        reply_message(event.reply_token, _help_msg)
        logger.info(f"[rewrite sandbox] {short_uid} → help ({text[:20]!r})")
        return True

    # 0b''''. 手動重置班次序號（維護指令；trips 非空會被工具拒絕，防誤用）
    # 歸檔清理：直接刪 Render 舊班次（免手貼 Adminer）。兩段式：
    #   「歸檔清理 [YYYY-MM-DD]」→ 檢查+預覽+確認鈕 →「確認清理」→ 真正執行
    # 安全欄杆在 scripts/archive_check.purge_render：備份不完整拒絕、
    # 30 天保護線、寫死的參數化 SQL（非 AI 生成）
    if text.startswith('歸檔清理'):
        try:
            import os as _os, sys as _sys
            from datetime import date as _d, timedelta as _td
            if _os.getcwd() not in _sys.path:
                _sys.path.insert(0, _os.getcwd())
            from scripts.archive_check import build_report, PURGE_MIN_AGE_DAYS
            _arg = text[len('歸檔清理'):].strip()
            _cut = _arg or (_d.today() - _td(days=60)).isoformat()
            _report, _ok = build_report(_cut)
            if not _ok:
                reply_message(event.reply_token, {'type': 'text', 'text': _report})
                return True
            _limit = (_d.today() - _td(days=PURGE_MIN_AGE_DAYS)).isoformat()
            if _cut > _limit:
                reply_message(event.reply_token, {
                    'type': 'text',
                    'text': f"❌ 界線 {_cut} 太近 — 只准清理 {_limit} 之前"
                            f"（保護線 {PURGE_MIN_AGE_DAYS} 天）",
                })
                return True
            if user_id:
                from rewrite.conversation_state import get_chat_id_from_event
                _state_set(user_id, ARCHIVE_PURGE_STATE_TYPE, {'cutoff': _cut},
                           ttl_minutes=5.0,
                           chat_id=get_chat_id_from_event(event))
            reply_message(event.reply_token, {
                'type': 'quick_reply',
                'text': f"{_report}\n\n⚠️ 確認要刪除 Render 上這些資料嗎？",
                'items': [
                    {'label': '🧹 確認清理', 'text': '確認清理'},
                    {'label': '❌ 取消', 'text': '取消清理'},
                ],
            })
            logger.info(f"[rewrite sandbox] {short_uid} → archive_purge preview cutoff={_cut}")
        except Exception as _p_err:
            logger.error(f"歸檔清理預覽失敗: {_p_err}", exc_info=True)
            reply_message(event.reply_token,
                          {'type': 'text', 'text': f"❌ 歸檔清理失敗：{str(_p_err)[:150]}"})
        return True

    if text in ('確認清理', '取消清理'):
        from rewrite.conversation_state import (
            pop_state as _pop, get_chat_id_from_event as _chat_of,
        )
        _st = _pop(user_id, ARCHIVE_PURGE_STATE_TYPE,
                   chat_id=_chat_of(event)) if user_id else None
        if not _st:
            reply_message(event.reply_token,
                          {'type': 'text', 'text': '沒有待確認的歸檔清理（可能已逾時）'})
            return True
        if text == '取消清理':
            reply_message(event.reply_token, {'type': 'text', 'text': '🚫 已取消，Render 資料未變動'})
            return True
        try:
            import os as _os, sys as _sys
            if _os.getcwd() not in _sys.path:
                _sys.path.insert(0, _os.getcwd())
            from scripts.archive_check import purge_render
            _msg, _n = purge_render((_st.get('payload') or {}).get('cutoff'))
            logger.info(f"[rewrite sandbox] {short_uid} → archive_purge executed n={_n}")
        except Exception as _px_err:
            logger.error(f"歸檔清理執行失敗: {_px_err}", exc_info=True)
            _msg = f"❌ 清理失敗：{str(_px_err)[:150]}"
        reply_message(event.reply_token, {'type': 'text', 'text': _msg})
        return True

    # 推播用量：本月的 LINE push 被哪些功能吃掉（純唯讀、reply 零 push）
    if text in ('推播用量', '推播統計', '推播額度', 'push用量'):
        try:
            from modules.utils.push_stats import render_summary_text
            _txt = render_summary_text()
        except Exception as _ps_err:
            logger.error(f"推播用量查詢失敗: {_ps_err}", exc_info=True)
            _txt = f"❌ 查詢失敗：{str(_ps_err)[:150]}"
        reply_message(event.reply_token, {'type': 'text', 'text': _txt})
        logger.info(f"[rewrite sandbox] {short_uid} → push_stats")
        return True

    # 歸檔檢查：刪 Render 舊班次前確認本地備份完整（純唯讀、reply 零 push）
    if text in ('歸檔檢查', '備份檢查', '歸檔狀態'):
        try:
            import os as _os
            import sys as _sys
            from datetime import date as _d, timedelta as _td
            if _os.getcwd() not in _sys.path:
                _sys.path.insert(0, _os.getcwd())
            from scripts.archive_check import build_report
            _report, _ok = build_report((_d.today() - _td(days=60)).isoformat())
        except Exception as _arc_err:
            logger.error(f"歸檔檢查失敗: {_arc_err}", exc_info=True)
            _report = f"❌ 歸檔檢查失敗：{str(_arc_err)[:150]}"
        reply_message(event.reply_token, {'type': 'text', 'text': _report})
        logger.info(f"[rewrite sandbox] {short_uid} → archive_check")
        return True

    # 司機管理：司機列表 / 新增司機 / 停用司機 / 啟用司機 / 解綁司機（reply 零 push）
    # 「司機自助回報車資」LIFF 的後台 —— 司機清單動態撈 DB，增減司機不用改程式
    if _looks_like_driver_admin(text):
        reply_message(event.reply_token,
                      {'type': 'text', 'text': _handle_driver_admin(text, user_id)})
        logger.info(f"[rewrite sandbox] {short_uid} → driver admin: {text[:20]!r}")
        return True

    if text == '重置班次序號':
        from database import Session
        from rewrite.tools.import_fixed import reset_trips_sequence
        _seq_sess = Session()
        try:
            _seq_r = reset_trips_sequence(session=_seq_sess)
        finally:
            _seq_sess.close()
        reply_message(event.reply_token, {
            'type': 'text',
            'text': _seq_r.data['message'] if _seq_r.ok else f"❌ {_seq_r.error}",
        })
        logger.info(f"[rewrite sandbox] {short_uid} → reset_trips_sequence ok={_seq_r.ok}")
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

    # 0.6 同指令進行中防抖：同 user 同文字且前一則還在跑 → 擋下不開新 agent run
    _inflight_key = None
    if user_id:
        from datetime import datetime as _dt
        _inflight_key = (user_id, text)
        _started = _AGENT_INFLIGHT.get(_inflight_key)
        if _started and (_dt.now() - _started).total_seconds() < _AGENT_INFLIGHT_MAX_SECONDS:
            logger.info(f"[rewrite sandbox] {short_uid} duplicate in-flight blocked: {text[:30]!r}")
            reply_message(event.reply_token, {
                'type': 'text',
                'text': '⏳ 上一則相同指令還在處理中（AI 偶爾要跑十幾秒），請稍候，不用重發。',
            })
            return True
        _AGENT_INFLIGHT[_inflight_key] = _dt.now()

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
    finally:
        if _inflight_key:
            _AGENT_INFLIGHT.pop(_inflight_key, None)

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
            f"\n\n💬 對話模式進行中（{int(SANDBOX_ACTIVE_TTL_MINUTES * 60)}秒內可不加 / 前綴回覆）"
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
        payload = state.get('payload') or {}
        # 已警示過 0 元 → 按「確認執行」沿用剛才暫存的原因/加成
        # （要擺在 _parse_leave_input 之前，否則「確認執行」會被當成格式錯誤）
        if payload.get('zero_confirmed') and text.strip() == MUTATION_CONFIRM_TEXT:
            parsed = (payload['pending_reason'], payload['pending_surcharge'])
        else:
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
        trip_ids = payload.get('trip_ids') or []

        # 🚧 批次 0 元請假 → 先警示。批次比單筆嚴重：一次 N 筆全部沒扣款
        if is_zero_surcharge(surcharge) and not payload.get('zero_confirmed'):
            from rewrite.conversation_state import get_chat_id_from_event
            _state_set(
                user_id, TRIP_STATUS_LEAVE_INPUT_STATE_TYPE,
                {**payload, 'zero_confirmed': True,
                 'pending_reason': reason, 'pending_surcharge': surcharge},
                ttl_minutes=TRIP_STATUS_TTL_MINUTES,
                chat_id=get_chat_id_from_event(event),
            )
            reply_message(event.reply_token, {
                'type': 'quick_reply',
                'text': zero_surcharge_warning(
                    target=f"{', '.join(f'#{i}' for i in trip_ids[:5])}"
                           + (f" 等 {len(trip_ids)} 筆" if len(trip_ids) > 5 else ""),
                    reason=reason, surcharge=surcharge,
                    how_to_confirm=f"按下方「{MUTATION_CONFIRM_TEXT}」",
                    count=len(trip_ids),
                ),
                'quick_reply': {'items': [
                    {'type': 'action', 'action': {
                        'type': 'message', 'label': f'✅ {MUTATION_CONFIRM_TEXT}',
                        'text': MUTATION_CONFIRM_TEXT}},
                    {'type': 'action', 'action': {
                        'type': 'message', 'label': '❌ 取消', 'text': '結束對話'}},
                ]},
            })
            logger.info(f"[rewrite sandbox] {short_uid} batch-leave 0 元警示 "
                        f"({len(trip_ids)} 筆, reason={reason})")
            return True

        _execute_batch_passenger_leave(
            event, user_id, short_uid, trip_ids, reason, surcharge,
            confirm_zero=bool(payload.get('zero_confirmed')),
        )
        return True

    return None


def _try_handle_pending_mutation(event, user_id: Optional[str], text: str,
                                  short_uid: str) -> Optional[bool]:
    """AI mutation 機制層確認：處理 [✅ 確認執行] / [❌ 取消操作]

    - 確認執行：原子 pop state（type + chat_id 都符合才取出）→ **先 pop 再執行**
      防雙擊重複執行 → execute_confirmed_calls 逐筆執行 stashed calls（不經 Gemini）
      → 單筆走既有 flex 渲染、多筆走文字彙總
    - 取消操作：pop 掉 state，回「已取消」
    - 沒 pending / 已逾時 / chat_id 不符 → 友善提示（不動別的對話的 pending）

    Returns:
        True — 已處理；None — 非本流程訊息（caller 繼續正常流程）
    """
    if text not in (_MUTATION_CONFIRM_TEXT, _MUTATION_CANCEL_TEXT):
        return None

    from rewrite.conversation_state import get_chat_id_from_event, pop_state
    state = None
    if user_id:
        state = pop_state(
            user_id,
            state_type=PENDING_MUTATION_STATE_TYPE,
            chat_id=get_chat_id_from_event(event),
        )
    if state is None:
        reply_message(event.reply_token, {
            'type': 'text',
            'text': '⌛ 沒有待確認的修改（可能已逾時或已處理），請重新下指令',
        })
        logger.info(
            f"[rewrite sandbox] {short_uid} pending-mutation {text!r} "
            f"but no matching state"
        )
        return True

    if text == _MUTATION_CANCEL_TEXT:
        reply_message(event.reply_token, {
            'type': 'text', 'text': '🚫 已取消，未做任何修改',
        })
        logger.info(f"[rewrite sandbox] {short_uid} pending-mutation cancelled")
        return True

    calls = (state.get('payload') or {}).get('calls') or []
    if not calls:
        reply_message(event.reply_token, {
            'type': 'text', 'text': '⌛ 待確認清單是空的，請重新下指令',
        })
        return True

    from rewrite.ai.agent import execute_confirmed_calls
    results = execute_confirmed_calls(calls, user_id)
    if len(results) == 1:
        name, args, r = results[0]
        # 單筆：走既有 flex 渲染路徑（成功回詳情卡、失敗回人話錯誤）
        msg = Agent._render_result(r, name, args, event_source=event.source)
    else:
        msg = Agent._render_mutation_summary(results)
    try:
        reply_message(event.reply_token, msg)
    except Exception as e:
        logger.error(
            f"[rewrite sandbox] {short_uid} pending-mutation reply failed: {e}",
            exc_info=True,
        )
    logger.info(
        f"[rewrite sandbox] {short_uid} pending-mutation executed "
        f"{len(results)} call(s), ok={sum(1 for _, _, r in results if r.ok)}"
    )
    return True


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
    confirm_zero: bool = False,
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
                confirm_zero_surcharge=confirm_zero,
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
