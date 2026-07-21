"""
Agent — 接收用戶訊息 → 跑 Skill (multi-turn tool loop) → 回 LINE message dict

v0.1 Phase 1：單一 Skill agent（先驗證架構）
v0.1 Phase 2 將加 intent classifier 路由到多 Skill

Multi-turn tool loop（spec §6.3 雛形）：
  AI 可以連續呼叫多個 tool（如先 query 拿 id，再 update by id）
  避免 single-turn 限制讓 AI 卡在「先確認再執行」的中間步驟
"""
import inspect
import logging
import re
from datetime import date, datetime
from typing import Any, Optional

from database import Session
from modules.utils.unified_date_parser import UnifiedDateParser
from google.genai import types

from modules.services.ai_service import get_genai_client, MODEL_ID

from rewrite.ai.client import LLMClient, LLMResponse, ToolCall, LLM_TIMEOUT_MS
from rewrite.ai.skill import Skill
from rewrite.conversation_state import (
    set_state,
    PENDING_MUTATION_STATE_TYPE,
    PENDING_MUTATION_TTL_MINUTES,
    MUTATION_CONFIRM_TEXT,
    MUTATION_CANCEL_TEXT,
)
from rewrite.tools.base import ToolResult
from rewrite.tools.trip import TripView
from rewrite.tools.customer import CustomerView
from rewrite.tools.fixed_schedule import FixedScheduleView
from rewrite.tools.completed_trip import (
    CompletedTripView,
    GroupedStatView,
    ReconciliationTextView,
    split_text_for_line,
)

logger = logging.getLogger(__name__)


def _is_quota_error(e: Exception) -> bool:
    """偵測 Vertex AI 429 / quota / resource exhausted 錯誤

    Gemini 在 google.api_core 拋 ResourceExhausted；也可能是 grpc 層的
    StatusCode.RESOURCE_EXHAUSTED 包裝後的 RuntimeError。用字串 fallback 抓。
    """
    try:
        from google.api_core.exceptions import ResourceExhausted, TooManyRequests
        if isinstance(e, (ResourceExhausted, TooManyRequests)):
            return True
    except ImportError:
        pass
    msg = str(e).lower()
    return ('429' in msg or 'resource exhausted' in msg or 'quota' in msg
            or 'rate limit' in msg)


def _is_timeout_error(e: Exception) -> bool:
    """偵測 Gemini 呼叫逾時（http_options.timeout 到期）

    google-genai 底層走 httpx → 逾時拋 httpx.TimeoutException 系列；
    保險起見再用字串 fallback 抓（deadline = grpc DEADLINE_EXCEEDED 包裝）。
    """
    try:
        import httpx
        if isinstance(e, httpx.TimeoutException):
            return True
    except ImportError:
        pass
    msg = str(e).lower()
    return 'timeout' in msg or 'timed out' in msg or 'deadline' in msg


# ============================================================
# ToolResult.fail 文案人話化（英文欄位名 → 業務用語）
# ============================================================

_FIELD_TERMS = {
    'completed_trip_id': '班次編號',
    'trip_id': '班次編號',
    'trip_date': '日期',
    'meter_fare': '錶跳車資',
    'extra_fare': '加成',
    'deposit_date': '入金日期',
    'last4': '帳號末4碼',
    'customer_id': '客戶編號',
    'short_name': '簡稱',
    'driver_id': '司機編號',
    'schedule_id': '固定班次編號',
    'amount': '金額',
    'week_offset': '週次',
    'reason': '原因',
    'category': '類別',
    'status': '狀態',
    'gender': '性別',
}

# 工程詞偵測：前後不是英文字母才算（避免 point 誤中 int、string 誤中 str）
_TECH_WORD_RE = re.compile(
    r'(?<![A-Za-z_])(JSON|json|dict|int|str|float|bool|list|None|'
    r'Traceback|TypeError|ValueError|KeyError)(?![A-Za-z_])'
)


def humanize_tool_error(error: Optional[str]) -> str:
    """ToolResult.fail 的錯誤訊息 → 用戶看得懂的話

    1. 常見英文欄位名替換成業務用語（長 key 先換，避免子字串誤傷）
    2. 替換後若仍含 JSON / dict / int 等工程詞 → 句尾補「幫助」提示
    """
    if not error:
        return '發生未知錯誤，請再試一次'
    msg = error
    for key in sorted(_FIELD_TERMS, key=len, reverse=True):
        msg = msg.replace(key, _FIELD_TERMS[key])
    if _TECH_WORD_RE.search(msg):
        msg += '（輸入格式可打「幫助」查看）'
    return msg


# ============================================================
# 唯讀 / mutation 工具判定 + mutation 彙總（多筆時看得到全貌）
# ============================================================

_READONLY_PREFIXES = ('query_', 'aggregate_', 'get_', 'sun_week')


def _is_readonly_tool(name: str) -> bool:
    """工具是否唯讀（query/aggregate/get/sun_week 開頭）— 非唯讀就算 mutation"""
    return (name or '').startswith(_READONLY_PREFIXES)


_TOOL_ACTION_LABELS = {
    'passenger_leave': '請假',
    'cancel_trip': '註銷',
    'mark_conflict': '標記衝突',
    'restore_to_ready': '改回準備',
    'assign_driver': '指派司機',
    'unassign_driver': '撤銷指派',
    'update_passenger_name': '改乘客名',
    'record_fare_current': '記錄車資',
    'update_trip_category': '改類別',
    'update_trip_time': '改時間',
    'update_trip_route': '改起終點',
    'update_completed_trip_fare': '修改車資',
    'update_completed_trip_category': '改類別',
    'update_completed_trip_driver': '改司機',
    'create_customer': '新增客戶',
    'update_customer': '更新客戶',
    'delete_customer': '刪除客戶',
    'create_fixed_schedule': '新增固定班次',
    'update_fixed_schedule': '更新固定班次',
    'apply_fixed_schedule_leave': '固定班次請假',
    'restore_fixed_schedule': '恢復固定班次',
    'delete_fixed_schedule': '刪除固定班次',
    'void_ledger_entry': '沖正帳務分錄',
}


# ============================================================
# 機制層確認（pending mutation）
#   AI 自然語言路徑發出的 mutation call 先攔下不執行 → 產生人話預覽 +
#   [✅ 確認執行 / ❌ 取消操作]，用戶確認後 sandbox_handler 呼叫
#   execute_confirmed_calls 才真正寫入。防「key 錯 id 直接進資料庫」。
# ============================================================

# 預覽的參數 key → 中文（humanize 對照表 _FIELD_TERMS 為底，補 mutation 常見參數）
_ARG_LABELS = {
    **_FIELD_TERMS,
    'surcharge': '加成',
    'passenger_name': '乘客名',
    'new_category': '新類別',
    'new_time': '新時間',
    'new_start': '新起點',
    'new_end': '新終點',
    'new_via': '新途經',
    'name': '姓名',
    'address': '地址',
    'contact_phone': '電話',
    'remarks': '備註',
    'birthday': '生日',
    'note': '備註',
    'memo': '備註',
    'route_number': '路線編號',
    'departure_time': '出發時間',
    'start_point': '起點',
    'via_point': '途經',
    'end_point': '終點',
    'direction': '方向',
    'base_fare': '基本車資',
    'total_fare': '車資總額',
    'actual_fare': '實收車資',
    'new_driver_id': '新司機編號',
}

# 預覽編號 ①②③…
_CIRCLED_NUMBERS = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'

# 目標資料的 id key（順序 = 優先序；第一個非 None 的當目標）
_PENDING_TARGET_KEYS = (
    'trip_id', 'completed_trip_id', 'customer_id', 'ledger_id', 'schedule_id',
)

# 預覽不顯示的 context / 技術參數
_PENDING_HIDDEN_KEYS = {'session', 'user_id', 'user_name', 'via', 'auto_commit'}


def _chat_id_from_source(event_source: Any, user_id: Optional[str]) -> Optional[str]:
    """從 webhook event.source 抽 chat_id（群組/聊天室/私聊統一）；
    無 event_source（測試 / repl）→ 用 user_id 當私聊 chat_id。"""
    if event_source is not None:
        cid = (
            getattr(event_source, 'group_id', None)
            or getattr(event_source, 'room_id', None)
            or getattr(event_source, 'user_id', None)
        )
        if cid:
            return cid
    return user_id


def _fmt_preview_value(v: Any) -> str:
    """預覽的參數值 → 人話字串"""
    if isinstance(v, bool):
        return '是' if v else '否'
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return str(v)


def _describe_mutation_target(session, args: dict) -> Optional[str]:
    """撈 pending mutation 的目標資料 → 一行人話描述；撈不到回 None（只列參數）"""
    try:
        if args.get('trip_id') is not None:
            from rewrite.tools.trip import query_trip_by_id
            r = query_trip_by_id(int(args['trip_id']), session=session)
            if r.ok and isinstance(r.data, TripView):
                t = r.data
                d = f"{t.date.month}/{t.date.day}" if t.date else '?'
                hm = t.time.strftime('%H:%M') if t.time else '?'
                start = t.custom_start_point or t.start_point or '?'
                end = t.custom_end_point or t.end_point or '?'
                drv = f"司機{t.driver_id}" if t.driver_id else '未指派'
                who = f"{t.passenger_name} " if t.passenger_name else ''
                return (f"#{t.trip_id} {who}{d} {hm} {start}→{end}"
                        f"（{drv}｜{t.display_status or '?'}）")
        if args.get('completed_trip_id') is not None:
            from rewrite.tools.completed_trip import query_completed_trip_by_id
            r = query_completed_trip_by_id(
                int(args['completed_trip_id']), session=session)
            if r.ok and isinstance(r.data, CompletedTripView):
                t = r.data
                d = f"{t.date.month}/{t.date.day}" if t.date else '?'
                who = f"{t.passenger_name} " if t.passenger_name else ''
                drv = f"司機{t.driver_id}" if t.driver_id else '無司機'
                return (f"#{t.id} {who}{d} {t.short_route()}"
                        f"（{drv}｜錶{t.meter_fare or 0} 加{t.extra_fare or 0}）")
        if args.get('customer_id') is not None:
            from rewrite.tools.customer import get_customer_by_id
            r = get_customer_by_id(int(args['customer_id']), session=session)
            if r.ok and isinstance(r.data, CustomerView):
                c = r.data
                addr = f"｜{c.address}" if c.address else ''
                return f"#{c.id} {c.name or '?'}（{c.short_name or '—'}{addr}）"
        if args.get('ledger_id') is not None:
            from rewrite.tools.accounting import query_ledger_entry
            r = query_ledger_entry(session=session, ledger_id=args['ledger_id'])
            if r.ok and isinstance(r.data, str) and r.data:
                return r.data.split('\n')[0].replace('📒 帳務分錄 ', '')
        if args.get('schedule_id') is not None:
            from rewrite.tools.fixed_schedule import get_fixed_schedule_by_id
            r = get_fixed_schedule_by_id(int(args['schedule_id']), session=session)
            if r.ok and isinstance(r.data, FixedScheduleView):
                s = r.data
                hm = (s.departure_time.strftime('%H:%M')
                      if s.departure_time else '?')
                drv = f"司機{s.driver_id}" if s.driver_id else '未指派'
                return f"#{s.id} 固定班次 {hm} {s.short_route()}（{drv}｜{s.status or '?'}）"
    except Exception as e:
        logger.warning(f"[Agent] describe mutation target failed: {e}")
        try:
            session.rollback()
        except Exception:
            pass
    return None


def build_mutation_preview(calls: list) -> str:
    """pending mutation calls → 人話預覽文字

    calls: [(tool_name, args_dict)]
    每筆：動作名（_TOOL_ACTION_LABELS）+ 目標資料（DB 撈）+ 參數（key 轉中文）。
    """
    lines = [f"📋 即將執行 {len(calls)} 筆修改，請確認："]
    session = Session()
    try:
        for i, (name, args) in enumerate(calls):
            label = _TOOL_ACTION_LABELS.get(name, name)
            args = args if isinstance(args, dict) else {}
            no = _CIRCLED_NUMBERS[i] if i < len(_CIRCLED_NUMBERS) else f"{i + 1}."
            target_key = next(
                (k for k in _PENDING_TARGET_KEYS if args.get(k) is not None), None)
            target = _describe_mutation_target(session, args)
            if target is None and target_key:
                target = f"#{args[target_key]}"
            lines.append(f"{no} {label}" + (f" — {target}" if target else ""))
            parts = []
            for k, v in args.items():
                if k in _PENDING_HIDDEN_KEYS or k == target_key or v is None:
                    continue
                parts.append(f"{_ARG_LABELS.get(k, k)}：{_fmt_preview_value(v)}")
            if parts:
                lines.append("　 " + "｜".join(parts))
    finally:
        session.close()
    lines.append("確認後才會寫入。")
    return '\n'.join(lines)


def stash_pending_mutations(calls: list, user_id: str,
                            event_source: Any = None) -> dict:
    """把攔下的 mutation calls 存 conversation state（**覆蓋**既有 pending），
    回「待確認」預覽訊息（quick_reply 帶 [✅ 確認執行 / ❌ 取消操作]）。

    calls: [(tool_name, args_dict)] — args 已 repair + normalize 過，
    in-memory state 直接存 python 物件（date 等不需序列化）。
    """
    preview = build_mutation_preview(calls)
    set_state(
        user_id,
        PENDING_MUTATION_STATE_TYPE,
        {'calls': calls, 'preview': preview},
        ttl_minutes=PENDING_MUTATION_TTL_MINUTES,
        chat_id=_chat_id_from_source(event_source, user_id),
    )
    logger.info(
        f"[Agent] stashed {len(calls)} pending mutation(s) "
        f"for {(user_id or '?')[:8]}.. : {[c[0] for c in calls]}"
    )
    return {
        'type': 'quick_reply',
        'text': preview,
        'quick_reply': {'items': [
            {'type': 'action',
             'action': {'type': 'message',
                        'label': f'✅ {MUTATION_CONFIRM_TEXT}',
                        'text': MUTATION_CONFIRM_TEXT}},
            {'type': 'action',
             'action': {'type': 'message',
                        'label': f'❌ {MUTATION_CANCEL_TEXT}',
                        'text': MUTATION_CANCEL_TEXT}},
        ]},
    }


def resolve_tool(name: str):
    """從 master skill 註冊表 resolve atomic tool。

    pending state 只存 tool_name 不存 fn 本身，「確認執行」時用這個換回 callable。
    """
    from rewrite.ai.skills.master import build_master_skill
    return build_master_skill().get_tool(name)


def execute_confirmed_calls(calls: list, user_id: Optional[str]) -> list:
    """執行用戶「確認執行」後的 stashed mutation calls（不經 Gemini）。

    calls: [(tool_name, args_dict)]（args 已在攔截時 repair + normalize 過）

    Returns:
        [(tool_name, args, ToolResult)] — 單筆走 Agent._render_result、
        多筆走 Agent._render_mutation_summary 渲染
    """
    results: list = []
    for name, stored_args in calls:
        fn = resolve_tool(name)
        if fn is None:
            logger.warning(f"[Agent confirm] unknown tool: {name}")
            results.append(
                (name, stored_args, ToolResult.fail(f"unknown tool: {name}")))
            continue
        # audit（R-6）記得到誰確認執行的
        args = _inject_context_args(fn, dict(stored_args), user_id=user_id)
        session = Session()
        try:
            r = fn(session=session, **args)
        except TypeError as e:
            logger.error(f"[Agent confirm] {name} args mismatch: {e}",
                         exc_info=True)
            r = ToolResult.fail(f"工具參數錯：{e}")
        except Exception as e:
            logger.error(f"[Agent confirm] {name} failed: {e}", exc_info=True)
            r = ToolResult.fail(f"執行錯誤：{str(e)[:120]}")
        finally:
            session.close()
        logger.info(f"[Agent confirm] {name} ok={r.ok}")
        results.append((name, args, r))
    return results


def _inject_context_args(fn, args: dict, *, user_id: Optional[str] = None,
                         user_name: Optional[str] = None) -> dict:
    """工具若明確接受 user_id / user_name / via 參數 → 注入 agent context

    audit log（R-6）才記得到「誰、經由哪裡」改的。
    - 不覆蓋 AI 已明確傳的同名參數
    - 只認「具名參數」— **kwargs 型工具（如 update_customer 的 **fields）不注入，
      避免 user_id 被當成業務欄位寫進資料
    """
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return args
    context = {'user_id': user_id, 'user_name': user_name, 'via': 'ai_agent'}
    out = dict(args)
    for key, value in context.items():
        p = params.get(key)
        if (p is not None
                and p.kind in (inspect.Parameter.KEYWORD_ONLY,
                               inspect.Parameter.POSITIONAL_OR_KEYWORD)
                and key not in out
                and value is not None):
            out[key] = value
    return out


def _lev_le1(a: str, b: str) -> bool:
    """a, b 編輯距離 ≤ 1（一次 增/刪/改）。"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    i = 0
    while i < min(la, lb) and a[i] == b[i]:
        i += 1
    if la == lb:          # 替換
        return a[i + 1:] == b[i + 1:]
    if la > lb:           # a 多一字 → 刪
        return a[i + 1:] == b[i:]
    return a[i:] == b[i + 1:]  # a 少一字 → 增


def _repair_arg_keys(fn, args: dict) -> dict:
    """修 AI 偶爾打錯的參數名。

    gemini-2.5-flash 在 function-calling 會「確定性地」把某些參數名插入數字
    （實測 reason→reas1on、passenger_name→pas1senger_name，與 thinking/溫度/
    schema 路徑無關）。未知 key → 先去數字比對、再編輯距離 1 比對到合法參數名，
    修不了才原樣（讓 tool 自己報錯）。
    """
    if not isinstance(args, dict):
        return args
    try:
        valid = set(inspect.signature(fn).parameters) - {'session'}
    except (TypeError, ValueError):
        return args
    out: dict = {}
    for k, v in args.items():
        if k in valid:
            out[k] = v
            continue
        stripped = re.sub(r'\d', '', k)
        if stripped in valid and stripped not in args:
            logger.warning(f"[Agent] repaired arg key {k!r} → {stripped!r}")
            out[stripped] = v
            continue
        cands = [p for p in valid if p not in args and _lev_le1(k, p)]
        if len(cands) == 1:
            logger.warning(f"[Agent] repaired arg key {k!r} → {cands[0]!r}")
            out[cands[0]] = v
        else:
            out[k] = v
    return out


def _to_json_safe(obj: Any) -> Any:
    """date / datetime / 其他物件 → JSON 友善 (給 LLM tool_response 用)"""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def _summarize_filters(args: dict) -> Optional[str]:
    """args dict → 「4/26-5/2 東洋」這類副標。給 aggregate_card header 用"""
    if not args:
        return None
    parts: list = []
    df, dt = args.get('date_from'), args.get('date_to')
    if df and dt:
        df_s = df.isoformat() if hasattr(df, 'isoformat') else str(df)
        dt_s = dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
        parts.append(f"{df_s} ~ {dt_s}" if df_s != dt_s else df_s)
    elif df:
        parts.append(str(df))
    if args.get('driver_id'):
        parts.append(f"司機{args['driver_id']}")
    if args.get('category'):
        parts.append(args['category'])
    if args.get('customer_short_name'):
        parts.append(args['customer_short_name'])
    if args.get('location'):
        parts.append(f"~{args['location']}")
    return ' · '.join(parts) if parts else None


class Agent:
    """
    單一 Skill agent — 接收訊息呼叫 LLM、dispatch tool、render reply

    process(text, user_id) 回 LINE message dict（含 quickReply）
    """

    MAX_TOOL_LOOPS = 5  # 多輪 tool call 上限（避免 infinite loop）

    def __init__(self, llm: LLMClient, skill: Skill):
        self.llm = llm
        self.skill = skill

    def process(self, text: str, user_id: Optional[str] = None, event_source: Any = None) -> dict:
        """
        Multi-turn tool loop：
          1. AI 看 prompt → 可能 call function
          2. 我們執行 function → 把結果 feed 回 chat
          3. AI 看結果 → 可能再 call function 或回最終 answer
          4. 直到沒有 function call 或達 MAX_TOOL_LOOPS

        最後一個 tool call 的結果會用 _render_result 轉 LINE message；
        若 AI 最後回純文字，回 text reply。

        Args:
            event_source: webhook event.source（傳了，render 出的 Flex bubble 上的
                LIFF 按鈕會帶 gid/rid，編輯/請假後 push 才會回到群組）
        """
        text = (text or '').strip()
        if not text:
            return {'type': 'text', 'text': '🤔 沒收到訊息內容'}

        try:
            return self._chat_with_tool_loop(text, user_id, event_source)
        except Exception as e:
            # Gemini 呼叫逾時（LLM_TIMEOUT_MS）用友善訊息，技術細節進 log
            if _is_timeout_error(e):
                logger.warning(f"[Agent] Gemini timeout: {str(e)[:200]}")
                return {'type': 'text', 'text': '⏳ AI 處理逾時，請再試一次。'}
            # Vertex AI 429 配額/burst 用友善訊息，技術細節進 log
            if _is_quota_error(e):
                logger.warning(f"[Agent] Vertex AI 429: {str(e)[:200]}")
                return {
                    'type': 'text',
                    'text': '⏳ AI 目前忙線中（Gemini 配額瞬間 burst），請稍候 30 秒再試一次。',
                }
            logger.error(f"[Agent] tool loop failed: {e}", exc_info=True)
            return {'type': 'text', 'text': f'⚠️ AI 處理錯誤：{str(e)[:120]}'}

    def _chat_with_tool_loop(self, text: str, user_id: Optional[str], event_source: Any = None) -> dict:
        """跑 multi-turn chat，每輪檢查是否有 function_call → 執行 → feed back"""
        client = get_genai_client()
        gemini_tools = [types.Tool(function_declarations=self.skill.function_declarations())]
        # tools 掛在 chat 的 config；對話 history 由 chat 物件自動維護
        # （取代舊 vertexai 的 model.start_chat()）
        chat = client.chats.create(
            model=MODEL_ID,
            config=types.GenerateContentConfig(
                tools=gemini_tools,
                # 低溫穩定 tool calling — 不設會用模型預設 1.0，同一句話
                # 這次抽出 reason、下次反問原因，行為抽獎（實測 log 2026-07-10）
                temperature=0.2,
                # 逾時保護：HttpOptions.timeout 單位是毫秒（見 client.LLM_TIMEOUT_MS）
                http_options=types.HttpOptions(timeout=LLM_TIMEOUT_MS),
            ),
        )

        # 第一輪：system prompt + user message 合併
        full_prompt = f"{self.skill.system_prompt}\n\n用戶訊息：{text}"
        response = chat.send_message(full_prompt)

        last_tool_result: Optional[ToolResult] = None
        last_tool_name: Optional[str] = None
        last_tool_args: Optional[dict] = None
        # 本輪全部「非唯讀」工具的結果 — ≥2 筆時改渲染文字彙總（部分成功要看得到全貌）
        # 註：有 user_id 時 mutation 會先被 _intercept_mutations 攔成 pending，
        #     這條只剩「無 user_id（測試 / repl）直接執行」的 fallback 路徑會走到
        mutation_results: list = []  # [(tool_name, args, ToolResult)]

        for iteration in range(self.MAX_TOOL_LOOPS):
            fc_parts = self._extract_function_calls(response)
            if not fc_parts:
                # AI 沒再要 function call → 終止 loop
                break

            tool_calls = [
                ToolCall(
                    name=fc.name,
                    args={k: v for k, v in fc.args.items()} if fc.args else {},
                )
                for fc in fc_parts
            ]

            # 機制層確認：batch 內含 mutation → 全部 mutation 攔下不執行、
            # 存 pending state、回「待確認」預覽（唯讀 call 照常執行）。
            # 防 AI 自然語言路徑 key 錯 id 的錯誤修改直接進資料庫。
            pending_msg = self._intercept_mutations(tool_calls, user_id, event_source)
            if pending_msg is not None:
                return pending_msg

            # Gemini 同一輪可能回「多個」function_call(parallel function calling)
            # — 例如用戶一句話要改時間+途經+終點+乘客。必須**全部執行**並回
            #   **等量的 function_response**,否則 Gemini 報 400「response parts !=
            #   call parts」。逐一執行,蒐集 response parts 一次送回。
            response_parts = []
            for tc in tool_calls:
                logger.info(f"[Agent loop {iteration+1}] {tc.name}({tc.args})")
                result, args_used = self._execute_tool(tc, user_id)
                # 記住最後「成功且可渲染」的結果供回覆;失敗也記(才有錯誤訊息)
                last_tool_result = result
                last_tool_name = tc.name
                last_tool_args = args_used
                if not _is_readonly_tool(tc.name):
                    mutation_results.append((tc.name, args_used, result))
                response_parts.append(types.Part.from_function_response(
                    name=tc.name,
                    response={'result': self._serialize_tool_result(result)},
                ))

            # 一次回等量 responses（數量必須 == 這輪的 fc 數）；
            # genai chat.send_message 收 list[Part]，自動包成 function_response 回合
            response = chat.send_message(response_parts)
        else:
            logger.warning(f"[Agent] hit MAX_TOOL_LOOPS={self.MAX_TOOL_LOOPS}")

        # 決定 reply
        # mutation ≥2 筆 → 不走 flex，渲染文字彙總（逐筆列成功/失敗，全貌可見）
        if len(mutation_results) >= 2:
            rendered = self._render_mutation_summary(mutation_results)
            ai_text = self._extract_text(response)
            if ai_text:
                rendered['text'] = ai_text + '\n\n' + rendered['text']
            return rendered

        # 幫助問答特例：get_command_help 的資料是給 AI 挑選用的，
        # 回覆一律用 AI 整理出的文字（不渲染目錄本體）
        if last_tool_name == 'get_command_help':
            ai_text = self._extract_text(response)
            if ai_text:
                return {'type': 'text', 'text': ai_text}
            from rewrite.help_registry import render_overview
            return {'type': 'text', 'text': render_overview()}

        # 優先：最後執行的 tool 結果（如果有）渲染 → LINE flex/text
        if last_tool_result is not None:
            rendered = self._render_result(last_tool_result, last_tool_name, last_tool_args or {}, event_source=event_source)
            # 如果 AI 結尾還有補充文字，附加在前頭（除非 rendered 是 flex
            # 或多則 list — 對帳單切多則時不併 AI 文字）。
            # 對帳單（reconciliation）一律不前綴 AI 文字 — view 自足，
            # 且 Gemini 收尾常複述單子內容造成重複（2026-07-14 實測）
            ai_text = self._extract_text(response)
            if (ai_text and isinstance(rendered, dict) and rendered.get('type') == 'text'
                    and last_tool_name != 'query_reconciliation_text'):
                rendered['text'] = ai_text + '\n\n' + rendered['text']
            return rendered

        # AI 純文字回應（無 tool call）
        ai_text = self._extract_text(response)
        return {'type': 'text', 'text': ai_text or '🤔 不太理解你的意思'}

    def _intercept_mutations(self, tool_calls: list, user_id: Optional[str],
                             event_source: Any = None) -> Optional[dict]:
        """機制層確認：本輪 tool call batch 含「非唯讀」工具時攔截。

        - 全部 mutation calls **不執行**、原封收集成 pending state
          （args 先 repair + normalize，確認執行時直接用）
        - 同 batch 的唯讀 call **跳過不執行**：本輪 loop 隨即被預覽訊息終止，
          查詢結果既不渲染給用戶也不 feed 回 AI，執行只是浪費 DB 查詢
        - 無 user_id 且無 event_source（測試 / repl 直呼）→ 回 None（照原流程執行）
        - 無 user_id 但**有 event_source**（真實 webhook 事件 — 群組成員未加
          bot 好友 / 未同意授權時 source.user_id 可為 None）→ fail-closed：
          pending state 無法綁定確認者身分，mutation 一律不執行，回提示訊息
          （純唯讀 batch 不受影響 — 上面 mutation 檢查先回 None 放行）

        Returns:
            「待確認」預覽訊息 dict / fail-closed 提示 dict，
            或 None（batch 無 mutation / 測試 repl 不攔截）
        """
        if not any(not _is_readonly_tool(tc.name) for tc in tool_calls):
            return None
        if not user_id:
            if event_source is None:
                return None  # 測試 / repl：無確認流程可走
            logger.warning(
                "[Agent intercept] mutation blocked: real event without "
                f"user_id, tools={[tc.name for tc in tool_calls]}"
            )
            return {
                'type': 'text',
                'text': '⚠️ 無法識別操作者身分（請先加 bot 好友並同意授權），'
                        '修改類指令未執行',
            }

        pending_calls: list = []
        for tc in tool_calls:
            if _is_readonly_tool(tc.name):
                logger.info(f"[Agent intercept] skip readonly {tc.name}({tc.args})")
                continue
            fn = self.skill.get_tool(tc.name)
            args = _repair_arg_keys(fn, tc.args) if fn else dict(tc.args)
            args = self._normalize_args(args)
            logger.info(f"[Agent intercept] pending mutation {tc.name}({args})")
            pending_calls.append((tc.name, args))

        return stash_pending_mutations(pending_calls, user_id, event_source)

    def _execute_tool(self, tc: ToolCall,
                       user_id: Optional[str]) -> tuple:
        """執行 tool call，回 (ToolResult, args_used)"""
        fn = self.skill.get_tool(tc.name)
        if not fn:
            logger.warning(f"[Agent] unknown tool: {tc.name}")
            return ToolResult.fail(f"unknown tool: {tc.name}"), tc.args

        args = _repair_arg_keys(fn, tc.args)   # 修 AI 打錯的參數名（reas1on→reason）
        args = self._normalize_args(args)
        # audit（R-6）要記得到誰改的：工具接受 user_id / via 就注入 agent context
        args = _inject_context_args(fn, args, user_id=user_id)
        session = Session()
        try:
            result = fn(session=session, **args)
            return result, args
        except TypeError as e:
            logger.error(f"[Agent] {tc.name} args mismatch: {e}", exc_info=True)
            return ToolResult.fail(f"工具參數錯：{e}"), args
        except Exception as e:
            logger.error(f"[Agent] {tc.name} failed: {e}", exc_info=True)
            return ToolResult.fail(f"執行錯誤：{str(e)[:120]}"), args
        finally:
            session.close()

    @staticmethod
    def _extract_function_calls(response):
        """從 Gemini response 抽出**所有** function_call parts（支援 parallel
        function calling — 同一輪多個 fc）。回 list,無則空 list。"""
        if not response.candidates:
            return []
        content = response.candidates[0].content
        if not content or not content.parts:
            return []
        out = []
        for part in content.parts:
            fc = getattr(part, 'function_call', None)
            if fc and fc.name:
                out.append(fc)
        return out

    @staticmethod
    def _extract_text(response) -> Optional[str]:
        """抽 response 的所有 text parts"""
        if not response.candidates:
            return None
        content = response.candidates[0].content
        if not content or not content.parts:
            return None
        parts = []
        for part in content.parts:
            t = getattr(part, 'text', None)
            if t:
                parts.append(t)
        return ''.join(parts) if parts else None

    @staticmethod
    def _serialize_tool_result(result: ToolResult) -> dict:
        """把 ToolResult 轉 JSON-serializable dict 給 LLM 看"""
        if not result.ok:
            return {'ok': False, 'error': result.error}

        data = result.data
        # CustomerView / TripView → dict
        if hasattr(data, 'to_dict'):
            data = data.to_dict()
        elif isinstance(data, list):
            data = [
                d.to_dict() if hasattr(d, 'to_dict') else d
                for d in data[:20]  # 給 AI 看的列表上限 20 筆，太多會撐爆 context
            ]
        # date / datetime → str
        return {
            'ok': True,
            'data': _to_json_safe(data),
            'meta': result.meta,
        }

    @staticmethod
    def _render_mutation_summary(results: list) -> dict:
        """多筆 mutation 結果 → 文字彙總（格式比照 sandbox 批次操作回報）

        results: [(tool_name, args, ToolResult)]
        """
        ok_lines: list = []
        fail_lines: list = []
        for name, args, r in results:
            label = _TOOL_ACTION_LABELS.get(name, name)
            target = ''
            for key in ('trip_id', 'completed_trip_id', 'schedule_id', 'customer_id'):
                if isinstance(args, dict) and args.get(key) is not None:
                    target = f"#{args[key]} "
                    break
            if r.ok:
                ok_lines.append(f"  ・{target}{label} 完成")
            else:
                err = humanize_tool_error(r.error)[:80]
                fail_lines.append(f"  ・{target}{label}：{err}")

        lines = [f"📋 本次共執行 {len(results)} 筆修改"]
        if ok_lines:
            lines.append(f"✅ 成功 {len(ok_lines)} 筆")
            lines.extend(ok_lines)
        if fail_lines:
            lines.append(f"❌ 失敗 {len(fail_lines)} 筆")
            lines.extend(fail_lines)
        return {'type': 'text', 'text': '\n'.join(lines)}

    @staticmethod
    def _normalize_args(args: dict) -> dict:
        """LLM 給的字串日期 → date 物件等"""
        normalized: dict = {}
        for k, v in args.items():
            # date_*  欄位
            if k in ('date_from', 'date_to', 'trip_date') and isinstance(v, str):
                try:
                    v = UnifiedDateParser.parse(v)
                except Exception:
                    logger.warning(f"[Agent] date parse failed for {k}={v!r}")
            normalized[k] = v
        return normalized

    @staticmethod
    def _render_result(result: ToolResult, tool_name: str, args: dict, event_source: Any = None):
        """ToolResult → LINE message dict（或 list[dict]）

        event_source 沿用過來給 Flex bubble 上的 LIFF 按鈕用（編輯/請假後 push 才會回到群組）。

        ⚠️ ReconciliationTextView（對帳單）超過 LINE 單則 5000 字上限時回
        list[dict]（多則 text）— reply_message 收 list，其他呼叫端維持 dict。
        """
        from rewrite.views.trip_flex import (
            render_trip_detail,
            render_trip_list_carousel,
            build_trip_quick_reply,
        )
        from rewrite.views.customer_flex import (
            render_customer_detail,
            render_birthday_layer_carousel,
        )
        from rewrite.views.completed_trip_flex import (
            render_completed_trip_detail,
            render_completed_trip_list_carousel,
            render_aggregate_card,
            render_grouped_stat_card,
        )

        if not result.ok:
            return {'type': 'text', 'text': f'❌ {humanize_tool_error(result.error)}'}

        data = result.data

        # ----- CompletedTripView -----
        if isinstance(data, CompletedTripView):
            # 帳務勾稽警語（update_completed_trip_fare 設 meta.warning）：
            # flex bubble 塞不下警語 → 改回文字訊息把警語帶出來
            warning = result.meta.get('warning')
            if warning:
                return {
                    'type': 'text',
                    'text': (
                        f"✅ 已完成班次 #{data.id} 已更新"
                        f"（錶價 {data.meter_fare or 0}、加成 {data.extra_fare or 0}）\n"
                        f"{warning}"
                    ),
                }
            bubble = render_completed_trip_detail(data)
            return {
                'type': 'flex',
                'altText': f'已完成班次 #{data.id}',
                'contents': bubble,
            }

        if isinstance(data, list) and data and isinstance(data[0], CompletedTripView):
            flex = render_completed_trip_list_carousel(
                data,
                truncated=bool(result.meta.get('truncated')),
            )
            return {
                'type': 'flex',
                'altText': f'查到 {len(data)} 筆已完成班次',
                'contents': flex,
            }

        # ----- ReconciliationTextView（對帳單純文字 — 可長按複製/轉傳）-----
        if isinstance(data, ReconciliationTextView):
            chunks, overflow = split_text_for_line(data.text)
            if overflow:
                chunks[-1] += '\n\n⚠️ 對帳單過長已截斷，請縮小日期範圍或加司機/類別條件'
            msgs = [{'type': 'text', 'text': c} for c in chunks]
            # 單則維持 dict（既有契約）；多則回 list（reply_message 收 list，
            # LINE reply 一次最多 5 則 — split_text_for_line 已 cap）
            return msgs[0] if len(msgs) == 1 else msgs

        # ----- GroupedStatView（受護欄查詢層 grouped 結果：各司機加總…）-----
        if isinstance(data, GroupedStatView):
            bubble = render_grouped_stat_card(data)
            return {
                'type': 'flex',
                'altText': f'分組統計 {result.meta.get("count", len(data.rows))} 組',
                'contents': bubble,
            }

        # ----- sun_week_info dict（純查週資訊「本週是哪一週」）-----
        if isinstance(data, dict) and 'week_number' in data and 'description' in data:
            return {'type': 'text', 'text': '🗓 ' + data['description']}

        # ----- aggregate dict（aggregate_completed_trips 回傳）-----
        if isinstance(data, dict) and 'sum_amount' in data:
            filters_text = _summarize_filters(args)
            bubble = render_aggregate_card(data, filters_text=filters_text)
            return {
                'type': 'flex',
                'altText': f'金額統計 {data.get("sum_amount", 0):,} 元',
                'contents': bubble,
            }

        # ----- TripView -----
        if isinstance(data, TripView):
            bubble = render_trip_detail(data)
            qr = build_trip_quick_reply(data, event_source=event_source)
            msg = {
                'type': 'flex',
                'altText': f'班次 #{data.trip_id} 詳情',
                'contents': bubble,
            }
            if qr:
                msg['quickReply'] = qr
            return msg

        if isinstance(data, list) and data and isinstance(data[0], TripView):
            # 批次「對這批做狀態管理」LIFF 入口（Alternative A：批次 LIFF 改用
            # 單一 GET /liff/trips/batch 一次撈,避開 iOS WebView 多 fetch bug）。
            # legacy 的「X 的狀態」regex picker 仍維持原文字 QR,兩條路並存。
            flex = render_trip_list_carousel(data)
            from rewrite.views.trip_flex import build_trip_list_batch_quick_reply
            batch_qr = build_trip_list_batch_quick_reply(data, event_source=event_source)
            msg = {
                'type': 'flex',
                'altText': f'查到 {len(data)} 筆班次',
                'contents': flex,
            }
            if batch_qr:
                msg['quickReply'] = batch_qr
            return msg

        # ----- CustomerView -----
        if isinstance(data, CustomerView):
            bubble = render_customer_detail(data, event_source=event_source)
            return {
                'type': 'flex',
                'altText': f'客戶 #{data.id} {data.name}',
                'contents': bubble,
            }

        if isinstance(data, list) and data and isinstance(data[0], CustomerView):
            # 多筆 → 病歷層 carousel（如果有 birthday_day 等）或文字列表
            day = args.get('day')
            if day is not None:
                flex = render_birthday_layer_carousel(int(day), data)
                return {
                    'type': 'flex',
                    'altText': f'病歷層 {day} 日（{len(data)} 人）',
                    'contents': flex,
                }
            # 一般客戶列表 → 簡短文字
            lines = [f"找到 {len(data)} 筆客戶："]
            for c in data[:20]:
                lines.append(f"  #{c.id} {c.name}（{c.short_name or '—'}）")
            if len(data) > 20:
                lines.append(f"  …還有 {len(data) - 20} 筆")
            lines.append("\n💡 用「客戶詳情 <ID>」看單筆")
            return {'type': 'text', 'text': '\n'.join(lines)}

        # ----- birthday summary list[(day, count)] -----
        if (isinstance(data, list) and data
                and isinstance(data[0], tuple) and len(data[0]) == 2):
            lines = ["📋 病歷層分布"]
            for d, n in data:
                lines.append(f"  {d:2d} 日: {'█' * min(n, 20)} ({n})")
            return {'type': 'text', 'text': '\n'.join(lines)}

        # ----- FixedScheduleView -----
        if isinstance(data, FixedScheduleView):
            from rewrite.views.fixed_schedule_flex import render_fixed_schedule_detail
            bubble = render_fixed_schedule_detail(data, event_source=event_source)
            return {
                'type': 'flex',
                'altText': f'固定班次 #{data.id}',
                'contents': bubble,
            }

        if isinstance(data, list) and data and isinstance(data[0], FixedScheduleView):
            from rewrite.views.fixed_schedule_flex import render_fixed_schedule_list_carousel
            flex = render_fixed_schedule_list_carousel(data, event_source=event_source)
            return {
                'type': 'flex',
                'altText': f'查到 {len(data)} 筆固定班次',
                'contents': flex,
            }

        # ----- 空 list 或 None -----
        if data is None or (isinstance(data, list) and not data):
            return {'type': 'text', 'text': '✅ 沒有符合的資料'}

        # ----- 其他 -----
        return {'type': 'text', 'text': str(data)[:1000]}
