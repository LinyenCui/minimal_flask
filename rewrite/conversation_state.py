"""
rewrite v0.1 對話狀態（in-memory，dev 期間用）

模仿原系統的「請假模式」/「批量請假模式」流程：
  1. 用戶按 [請假] → set_state(user_id, 'leave_input', {trip_id})
  2. bot 回提示，等用戶輸入 [原因] [負加成]
  3. 用戶下一則訊息進來時，先 get_state 確認是否在 input mode
  4. 解析或失敗或退出 → clear_state

⚠️ 進程內 dict（多 worker 不同步），spec N-3 標記 v0.2 改 DB 持久化。
   v0.1 dev 期沿用此簡化版（單 worker + 30 分鐘 TTL 已夠用）。
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# user_id → {type: str, payload: dict, expires_at: datetime}
_STATES: dict = {}
_TTL = timedelta(minutes=30)
# 過期後的 grace 期：條目過期先不刪，保留這段時間讓 webhook 能用
# peek_recently_expired 判斷「剛逾時」提示用戶一次，超過 grace 才真正清除。
# get_state 對過期條目仍回 None（語義不變）。
_GRACE = timedelta(minutes=3)
_LOCK = threading.Lock()


def set_state(user_id: str, state_type: str, payload: dict,
              ttl_minutes: Optional[float] = None,
              chat_id: Optional[str] = None) -> None:
    """設定 user 的對話狀態（會覆蓋既有的）

    Args:
        ttl_minutes：自訂 TTL（分鐘），None = 預設 30 分鐘
        chat_id：訊息來源的對話 ID（群組用 group_id、聊天室用 room_id、私聊用 user_id）。
            存在 state 裡，webhook 用來判定「active state bypass / 規則」是否應在
            當前對話生效——避免私聊 active state 跨到群組讓所有閒聊被當 bot 訊息。
    """
    ttl = timedelta(minutes=ttl_minutes) if ttl_minutes is not None else _TTL
    with _LOCK:
        _STATES[user_id] = {
            'type': state_type,
            'payload': dict(payload),
            'chat_id': chat_id,
            'expires_at': datetime.now() + ttl,
        }
    logger.info(
        f"[conversation_state] set {user_id[:8]}.. type={state_type} "
        f"ttl={ttl} chat={(chat_id or '?')[:8]}.. payload={payload}"
    )


def get_chat_id_from_event(event) -> Optional[str]:
    """從 webhook event 抽 chat_id（群組/聊天室/私聊統一抽法）。

    set_state 時用同函式抽 chat_id，跟 webhook 比對才一致。
    """
    src = getattr(event, 'source', None)
    if src is None:
        return None
    return (
        getattr(src, 'group_id', None)
        or getattr(src, 'room_id', None)
        or getattr(src, 'user_id', None)
    )


def get_state(user_id: str) -> Optional[dict]:
    """取 user 的當前狀態（過期一律回 None）

    過期條目不會馬上刪：保留 _GRACE 期供 peek_recently_expired 判斷
    「剛逾時」，超過 grace 才真正清除。對 caller 語義不變（過期 = None）。
    """
    with _LOCK:
        s = _STATES.get(user_id)
        if not s:
            return None
        now = datetime.now()
        if now > s['expires_at']:
            if now > s['expires_at'] + _GRACE:
                del _STATES[user_id]
                logger.info(f"[conversation_state] expired {user_id[:8]}..")
            return None
        return dict(s)  # 回 copy，避免 caller 改到內部


def peek_recently_expired(user_id: str, chat_id: Optional[str] = None) -> bool:
    """該 user 是否有「剛過期（grace 期內）」的對話狀態。

    給 webhook 群組閘門用：多輪對話剛逾時、用戶又送了無 / 前綴訊息時，
    可提示一次「對話已逾時」而不是靜默吞掉。純 peek，不刪條目——
    提示過後由 caller 呼叫 clear_state 清掉標記（避免每句閒聊都被回）。

    Args:
        chat_id：若給定，只在 state 記錄的 chat_id 相同時才算
            （防止私聊逾時的 state 讓群組閒聊被提示；比照 webhook
            active-state bypass 的同對話判定）。
    """
    with _LOCK:
        s = _STATES.get(user_id)
        if not s:
            return False
        now = datetime.now()
        if not (s['expires_at'] < now <= s['expires_at'] + _GRACE):
            return False
        if chat_id is not None and s.get('chat_id') != chat_id:
            return False
        return True


def clear_state(user_id: str) -> None:
    """清除 user 的狀態（無就略過）"""
    with _LOCK:
        if _STATES.pop(user_id, None) is not None:
            logger.info(f"[conversation_state] cleared {user_id[:8]}..")


def state_count() -> int:
    """目前活躍 state 總數（debug 用）"""
    with _LOCK:
        return len(_STATES)


def sweep_expired() -> int:
    """主動掃過所有 state，清掉已過期的，回清掉的數量。

    平常 get_state 會 lazy expire（被查到才 pop），但有些 state 設了沒人再查
    就會留在 dict 裡到永遠（直到下次同 user_id 進來才被驗）。
    給 scheduler 5 分鐘呼叫一次，主動掃。

    只清「過期超過 grace 期」的條目——grace 期內的保留，
    讓 webhook 的 peek_recently_expired 還來得及提示一次。
    """
    now = datetime.now()
    cleaned = 0
    with _LOCK:
        for user_id in list(_STATES.keys()):
            s = _STATES.get(user_id)
            if s and now > s['expires_at'] + _GRACE:
                del _STATES[user_id]
                cleaned += 1
    if cleaned > 0:
        logger.info(f"[conversation_state] sweep cleaned {cleaned} expired states")
    return cleaned
