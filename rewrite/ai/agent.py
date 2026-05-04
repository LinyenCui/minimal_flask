"""
Agent — 接收用戶訊息 → 跑 Skill → 回 LINE message dict

v0.1 Phase 1：單一 Skill agent（先驗證架構）
v0.1 Phase 2 將加 intent classifier 路由到多 Skill
"""
import logging
from datetime import date, datetime
from typing import Any, Optional

from database import Session
from modules.utils.unified_date_parser import UnifiedDateParser

from rewrite.ai.client import LLMClient, LLMResponse, ToolCall
from rewrite.ai.skill import Skill
from rewrite.tools.base import ToolResult
from rewrite.tools.trip import TripView

logger = logging.getLogger(__name__)


class Agent:
    """
    單一 Skill agent — 接收訊息呼叫 LLM、dispatch tool、render reply

    process(text, user_id) 回 LINE message dict（含 quickReply）
    """

    def __init__(self, llm: LLMClient, skill: Skill):
        self.llm = llm
        self.skill = skill

    def process(self, text: str, user_id: Optional[str] = None) -> dict:
        text = (text or '').strip()
        if not text:
            return {'type': 'text', 'text': '🤔 沒收到訊息內容'}

        try:
            response = self.llm.chat(
                messages=[
                    {'role': 'system', 'content': self.skill.system_prompt},
                    {'role': 'user', 'content': text},
                ],
                tools=self.skill.function_declarations(),
            )
        except Exception as e:
            logger.error(f"[Agent] LLM call failed: {e}", exc_info=True)
            return {'type': 'text', 'text': f'⚠️ AI 呼叫失敗：{str(e)[:100]}'}

        # 沒 tool call → 文字回應
        if not response.has_tool_call:
            return {
                'type': 'text',
                'text': response.text or '🤔 不太理解你的意思',
            }

        # 第一個 tool call（v0.1 一次處理一個工具）
        return self._dispatch_tool_call(response.tool_calls[0], user_id)

    def _dispatch_tool_call(self, tc: ToolCall, user_id: Optional[str]) -> dict:
        fn = self.skill.get_tool(tc.name)
        if not fn:
            logger.warning(f"[Agent] unknown tool: {tc.name}")
            return {
                'type': 'text',
                'text': f'❌ 不支援的工具：{tc.name}（args={tc.args}）',
            }

        # 規範化參數（日期字串 → date 物件等）
        args = self._normalize_args(tc.args)
        logger.info(f"[Agent] dispatch {tc.name}({args})")

        session = Session()
        try:
            result = fn(session=session, **args)
            return self._render_result(result, tc.name, args)
        except TypeError as e:
            # 通常是參數對不上（schema 跟 callable signature 不一致）
            logger.error(f"[Agent] {tc.name} args mismatch: {e}", exc_info=True)
            return {'type': 'text', 'text': f'❌ 工具參數錯：{e}'}
        except Exception as e:
            logger.error(f"[Agent] {tc.name} failed: {e}", exc_info=True)
            return {'type': 'text', 'text': f'❌ {tc.name} 執行錯誤：{str(e)[:120]}'}
        finally:
            session.close()

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
    def _render_result(result: ToolResult, tool_name: str, args: dict) -> dict:
        """ToolResult → LINE message dict"""
        from rewrite.views.trip_flex import (
            render_trip_detail,
            render_trip_list_carousel,
            build_trip_quick_reply,
        )

        if not result.ok:
            return {'type': 'text', 'text': f'❌ {result.error}'}

        data = result.data

        # 單筆 TripView
        if isinstance(data, TripView):
            bubble = render_trip_detail(data)
            qr = build_trip_quick_reply(data)
            msg = {
                'type': 'flex',
                'altText': f'班次 #{data.trip_id} 詳情',
                'contents': bubble,
            }
            if qr:
                msg['quickReply'] = qr
            return msg

        # 多筆 TripView 列表
        if isinstance(data, list) and data and isinstance(data[0], TripView):
            flex = render_trip_list_carousel(data)
            return {
                'type': 'flex',
                'altText': f'查到 {len(data)} 筆班次',
                'contents': flex,
            }

        # 其他
        return {'type': 'text', 'text': str(data)[:1000]}
