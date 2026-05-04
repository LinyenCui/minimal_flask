"""
MultiSkillAgent — 用 intent classifier 路由到對應 Skill (spec §6.2)

流程：
  process(text, user_id)
    ↓
  classify(text) → 'trip_query' / 'trip_mutation' / 'customer' / 'unknown'
    ↓
  載入對應 Skill → 跑 Agent (single-skill, with multi-turn loop)
    ↓
  unknown → 回友善訊息（之後可 fall-through 給 legacy）

好處：
  - AI 不用看 22 個工具的 prompt（單一 skill 4-10 個工具，更聚焦、更快、更不容易選錯）
  - 加新 skill（如 fixed_schedule）時不影響既有 skill 的判斷準確度
  - 'unknown' 出口讓 webhook 整合時可 fall-through 給 legacy
"""
import logging
from typing import Dict, Optional

from rewrite.ai.client import LLMClient
from rewrite.ai.skill import Skill
from rewrite.ai.agent import Agent
from rewrite.ai.intent import classify

logger = logging.getLogger(__name__)


# 用戶看到 unknown 時的 reply（不接 webhook 時用）
_UNKNOWN_REPLY = (
    "🤔 我不太懂這句話的意思。\n\n"
    "目前我能處理：\n"
    "  • 班次查詢（如「明天龍埔街的狀態」「待派班次」）\n"
    "  • 班次修改（如「1077請假化療-30」「99502註銷」）\n"
    "  • 客戶資料（如「查太子龍」「病歷層15」）\n\n"
    "💡 其他功能（預約、固定班次、報表等）請用既有命令"
)


class MultiSkillAgent:
    def __init__(self, llm: LLMClient, skills: Dict[str, Skill],
                 unknown_handler: Optional[callable] = None):
        """
        Args:
            llm: shared LLMClient（intent classifier 跟 skill 都用它）
            skills: dict {'trip_query': Skill, 'trip_mutation': Skill, 'customer': Skill}
            unknown_handler: 'unknown' 時呼叫的 callback (text, user_id) → message dict
                             None = 回 _UNKNOWN_REPLY
        """
        self.llm = llm
        self.skills = skills
        self.unknown_handler = unknown_handler

    def process(self, text: str, user_id: Optional[str] = None) -> dict:
        text = (text or '').strip()
        if not text:
            return {'type': 'text', 'text': '🤔 沒收到訊息內容'}

        # 1. 分類意圖
        intent = classify(self.llm, text)
        logger.info(f"[MultiSkill] {text!r} → intent={intent}")

        # 2. unknown 出口
        if intent == 'unknown' or intent not in self.skills:
            if self.unknown_handler:
                return self.unknown_handler(text, user_id)
            return {'type': 'text', 'text': _UNKNOWN_REPLY}

        # 3. 載對應 Skill 跑 single-skill Agent
        skill = self.skills[intent]
        agent = Agent(self.llm, skill)
        return agent.process(text, user_id)


def build_default_multi_skill_agent(llm: Optional[LLMClient] = None) -> MultiSkillAgent:
    """方便外部建立 v0.1 標準配置的 MultiSkillAgent"""
    from rewrite.ai.client import GeminiClient
    from rewrite.ai.skills.trip_query import build_trip_query_skill
    from rewrite.ai.skills.trip_mutation import build_trip_mutation_skill
    from rewrite.ai.skills.customer import build_customer_skill

    return MultiSkillAgent(
        llm=llm or GeminiClient(),
        skills={
            'trip_query': build_trip_query_skill(),
            'trip_mutation': build_trip_mutation_skill(),
            'customer': build_customer_skill(),
        },
    )
