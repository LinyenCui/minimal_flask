"""
Intent classifier — 用戶訊息 → 該載入哪個 Skill (spec §6.2)

設計：
  - 用一個小 prompt 給 LLM 快速分類（不帶任何 tool）
  - 回傳 skill 名稱（'trip_query' / 'trip_mutation' / 'customer' / 'unknown'）
  - 加 unknown 分類，避免 AI 硬塞分類不對的請求

優先 prompt 簡短 + temperature 低，讓回答穩定。
"""
import logging
from typing import Set

from rewrite.ai.client import LLMClient

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
你是意圖分類器。看用戶的訊息，回傳該交給哪個專業助手處理。

可用助手：
- trip_query：查班次（如「明天龍埔街的狀態」「今天診所班次」「待派班次」「班次詳情1077」）
- trip_mutation：改班次（如「1077請假化療-30」「99502註銷」「指派司機533給1077」「改乘客名」「改車資」）
- customer：客戶資料（如「查太子龍」「龍埔街是誰」「新增客戶」「太子龍改地址」「病歷層15」「病歷層分布」）
- unknown：不屬以上（如閒聊、問機器人功能、固定班次、報表生成、預約叫車等）

📌 規則：
- 只回一個詞，全部小寫，不加標點。
- 「狀態」+ 客戶名 = trip_query（不是 mutation）
- 創建/修改/刪除「客戶」資料 = customer
- 「請假」「註銷」「衝突」「指派司機」=  trip_mutation
- 「預約」「booking」「新增班次」= unknown（rewrite 還沒做這個）
- 「固定班次」= unknown（rewrite 還沒做這個）

範例：
用戶：「明天龍埔街的狀態」 → trip_query
用戶：「1077化療-30」 → trip_mutation
用戶：「查太子龍」 → customer
用戶：「!新增客戶 王小明」 → customer
用戶：「!匯入固定班次 本週」 → unknown
用戶：「你好嗎？」 → unknown
"""


VALID_INTENTS: Set[str] = {'trip_query', 'trip_mutation', 'customer', 'unknown'}


def classify(llm: LLMClient, text: str) -> str:
    """
    回傳 intent 名稱，必為 VALID_INTENTS 之一。
    LLM 失敗或回奇怪詞 → 'unknown'（fail-safe）
    """
    text = (text or '').strip()
    if not text:
        return 'unknown'

    try:
        response = llm.chat(
            messages=[
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {'role': 'user', 'content': text},
            ],
            tools=None,  # 純分類不給工具
        )
    except Exception as e:
        logger.error(f"[intent] classify failed: {e}", exc_info=True)
        return 'unknown'

    raw = (response.text or '').strip().lower()
    # 抓第一個有效字 — 防 AI 多話
    for token in raw.replace('\n', ' ').split():
        token_clean = token.strip('.,;:!?，。；：！？「」`「』')
        if token_clean in VALID_INTENTS:
            logger.info(f"[intent] {text!r} → {token_clean}")
            return token_clean

    logger.warning(f"[intent] no valid intent in response: {raw!r} → unknown")
    return 'unknown'
