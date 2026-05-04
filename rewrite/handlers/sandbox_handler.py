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
from rewrite.ai.skills.customer import build_customer_skill
from rewrite.ai.skills.fixed_schedule import build_fixed_schedule_skill
from rewrite.ai.skills.trip_mutation import build_trip_mutation_skill
from rewrite.ai.skills.trip_query import build_trip_query_skill

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

    # 1. 分類意圖
    try:
        intent = classify(_llm, text)
    except Exception as e:
        logger.error(f"[rewrite sandbox] classify failed for {short_uid}: {e}",
                     exc_info=True)
        return False

    if intent == 'unknown' or intent not in _skills:
        logger.info(
            f"[rewrite sandbox] {short_uid} text={text!r} → {intent}, fall-through")
        return False

    # 2. 跑對應 skill（含 multi-turn tool loop）
    try:
        agent = Agent(_llm, _skills[intent])
        msg = agent.process(text, user_id)
    except Exception as e:
        logger.error(
            f"[rewrite sandbox] {short_uid} skill={intent} failed: {e}",
            exc_info=True,
        )
        return False  # error 也 fall-through legacy

    # 3. reply
    try:
        reply_message(event.reply_token, msg)
        logger.info(
            f"[rewrite sandbox] {short_uid} text={text!r} skill={intent} ✅")
        return True
    except Exception as e:
        logger.error(
            f"[rewrite sandbox] {short_uid} reply failed: {e}", exc_info=True)
        return True  # 已執行 mutation／LLM call，不再 fall-through 避免重複
