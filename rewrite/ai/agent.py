"""
Agent — 接收用戶訊息 → 跑 Skill (multi-turn tool loop) → 回 LINE message dict

v0.1 Phase 1：單一 Skill agent（先驗證架構）
v0.1 Phase 2 將加 intent classifier 路由到多 Skill

Multi-turn tool loop（spec §6.3 雛形）：
  AI 可以連續呼叫多個 tool（如先 query 拿 id，再 update by id）
  避免 single-turn 限制讓 AI 卡在「先確認再執行」的中間步驟
"""
import logging
from datetime import date, datetime
from typing import Any, Optional

from database import Session
from modules.utils.unified_date_parser import UnifiedDateParser
from vertexai.generative_models import (
    GenerativeModel, Tool, Content, Part,
)

from modules.services.ai_service import init_vertexai, MODEL_ID

from rewrite.ai.client import LLMClient, LLMResponse, ToolCall
from rewrite.ai.skill import Skill
from rewrite.tools.base import ToolResult
from rewrite.tools.trip import TripView
from rewrite.tools.customer import CustomerView
from rewrite.tools.fixed_schedule import FixedScheduleView
from rewrite.tools.completed_trip import CompletedTripView

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
        # init_vertexai() 已 idempotent（module-level _VERTEX_INITED guard），
        # 這裡 call 是 defense in depth — 萬一 GeminiClient 沒先 init 過
        init_vertexai()
        gemini_tools = [Tool(function_declarations=self.skill.function_declarations())]
        model = GenerativeModel(MODEL_ID, tools=gemini_tools)
        chat = model.start_chat()

        # 第一輪：system prompt + user message 合併
        full_prompt = f"{self.skill.system_prompt}\n\n用戶訊息：{text}"
        response = chat.send_message(full_prompt)

        last_tool_result: Optional[ToolResult] = None
        last_tool_name: Optional[str] = None
        last_tool_args: Optional[dict] = None

        for iteration in range(self.MAX_TOOL_LOOPS):
            fc_part = self._extract_function_call(response)
            if not fc_part:
                # AI 沒再要 function call → 終止 loop
                break

            tc = ToolCall(
                name=fc_part.name,
                args={k: v for k, v in fc_part.args.items()} if fc_part.args else {},
            )
            logger.info(f"[Agent loop {iteration+1}] {tc.name}({tc.args})")

            # 執行 tool
            result, args_used = self._execute_tool(tc, user_id)
            last_tool_result = result
            last_tool_name = tc.name
            last_tool_args = args_used

            # 把 result feed 回 chat（讓 AI 看到結果決定下一步）
            tool_response_payload = self._serialize_tool_result(result)
            response = chat.send_message(
                Content(parts=[Part.from_function_response(
                    name=tc.name,
                    response={'result': tool_response_payload},
                )])
            )
        else:
            logger.warning(f"[Agent] hit MAX_TOOL_LOOPS={self.MAX_TOOL_LOOPS}")

        # 決定 reply
        # 優先：最後執行的 tool 結果（如果有）渲染 → LINE flex/text
        if last_tool_result is not None:
            rendered = self._render_result(last_tool_result, last_tool_name, last_tool_args or {}, event_source=event_source)
            # 如果 AI 結尾還有補充文字，附加在前頭（除非 rendered 是 flex）
            ai_text = self._extract_text(response)
            if ai_text and rendered.get('type') == 'text':
                rendered['text'] = ai_text + '\n\n' + rendered['text']
            return rendered

        # AI 純文字回應（無 tool call）
        ai_text = self._extract_text(response)
        return {'type': 'text', 'text': ai_text or '🤔 不太理解你的意思'}

    def _execute_tool(self, tc: ToolCall,
                       user_id: Optional[str]) -> tuple:
        """執行 tool call，回 (ToolResult, args_used)"""
        fn = self.skill.get_tool(tc.name)
        if not fn:
            logger.warning(f"[Agent] unknown tool: {tc.name}")
            return ToolResult.fail(f"unknown tool: {tc.name}"), tc.args

        args = self._normalize_args(tc.args)
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
    def _extract_function_call(response):
        """從 Gemini response 抽出第一個 function_call part"""
        if not response.candidates:
            return None
        for part in response.candidates[0].content.parts:
            fc = getattr(part, 'function_call', None)
            if fc and fc.name:
                return fc
        return None

    @staticmethod
    def _extract_text(response) -> Optional[str]:
        """抽 response 的所有 text parts"""
        if not response.candidates:
            return None
        parts = []
        for part in response.candidates[0].content.parts:
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
    def _render_result(result: ToolResult, tool_name: str, args: dict, event_source: Any = None) -> dict:
        """ToolResult → LINE message dict

        event_source 沿用過來給 Flex bubble 上的 LIFF 按鈕用（編輯/請假後 push 才會回到群組）。
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
        )

        if not result.ok:
            return {'type': 'text', 'text': f'❌ {result.error}'}

        data = result.data

        # ----- CompletedTripView -----
        if isinstance(data, CompletedTripView):
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
