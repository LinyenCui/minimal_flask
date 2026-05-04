"""
Intent classifier — 用戶訊息 → 該載入哪個 Skill (spec §6.2)

設計：
  - 用一個小 prompt 給 LLM 快速分類（不帶任何 tool）
  - 回傳 skill 名稱（'trip_query' / 'trip_mutation' / 'customer' / 'unknown'）
  - 加 unknown 分類，避免 AI 硬塞分類不對的請求

優先 prompt 簡短 + temperature 低，讓回答穩定。
"""
import logging
from typing import Optional, Set

from rewrite.ai.client import LLMClient

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
你是意圖分類器。看用戶的訊息，回傳該交給哪個專業助手處理。

可用助手：
- trip_query：查現在態班次（trips 表）
  例：「明天龍埔街的狀態」「今天診所班次」「待派班次」「班次詳情1077」
- trip_mutation：改現在態班次
  例：「1077請假化療-30」「99502註銷」「指派司機533給1077」「改乘客名」「改車資」
- customer：客戶資料 CRUD
  例：「查太子龍」「龍埔街是誰」「新增客戶」「太子龍改地址」「病歷層15」「病歷層分布」
- fixed_schedule：未來態固定班次模板（每週重複）
  例：「太子龍的固定班次」「固定班次21修改時間」「固定班次14請假」「恢復固定班次5」
  ⚠️ 「匯入固定班次 本週」這種匯入動作 → unknown（rewrite 還沒做匯入）
- unknown：不屬以上（如閒聊、機器人功能、報表生成、預約叫車、匯入固定班次等）

📌 關鍵規則：
- 只回一個詞，全部小寫，不加標點。
- 用戶說「班次」+ 數字 = trips（trip_query / trip_mutation）
- 用戶說「固定班次」+ 數字 = fixed_schedule
- 「狀態」+ 客戶名 = trip_query
- 創建/修改/刪除「客戶」資料 = customer
- 「請假」要看 context：
  * 「班次X請假」「乘客請假」 → trip_mutation
  * 「固定班次X請假」「客戶長期請假」「客戶出國」 → fixed_schedule
- 「匯入」「booking 預約」「報表」 → unknown

範例：
「明天龍埔街的狀態」 → trip_query
「1077化療-30」 → trip_mutation
「查太子龍」 → customer
「太子龍的固定班次」 → fixed_schedule
「固定班次14設為請假」 → fixed_schedule
「匯入固定班次 本週」 → unknown
「你好嗎？」 → unknown
"""


VALID_INTENTS: Set[str] = {
    'trip_query', 'trip_mutation', 'customer', 'fixed_schedule', 'unknown',
}


def classify(llm: LLMClient, text: str,
             last_skill: Optional[str] = None) -> str:
    """
    回傳 intent 名稱，必為 VALID_INTENTS 之一。
    LLM 失敗或回奇怪詞 → 'unknown'（fail-safe）

    last_skill: 上一輪的 skill name（從 sandbox-active state 取得），
                給 LLM 當 context hint，處理 ambiguous follow-up
                （如單獨「14」、「出國 -50」等補資訊訊息）
    """
    text = (text or '').strip()
    if not text:
        return 'unknown'

    user_message = text
    if last_skill and last_skill in (VALID_INTENTS - {'unknown'}):
        # 給 hint，但不強制 — 新訊息明顯切到別領域時 LLM 仍能切
        user_message = (
            f"[hint：用戶上一輪走 {last_skill}，這次若是 follow-up "
            f"（如單獨數字、補資訊），傾向同 skill；若明顯切換主題則照新內容判斷]\n\n"
            f"訊息：{text}"
        )

    try:
        response = llm.chat(
            messages=[
                {'role': 'system', 'content': _SYSTEM_PROMPT},
                {'role': 'user', 'content': user_message},
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
            logger.info(f"[intent] {text!r} (hint={last_skill}) → {token_clean}")
            return token_clean

    logger.warning(f"[intent] no valid intent in response: {raw!r} → unknown")
    return 'unknown'
