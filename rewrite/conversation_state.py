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
_LOCK = threading.Lock()


def set_state(user_id: str, state_type: str, payload: dict,
              ttl_minutes: Optional[float] = None) -> None:
    """設定 user 的對話狀態（會覆蓋既有的）

    ttl_minutes：自訂 TTL（分鐘），None = 預設 30 分鐘
    """
    ttl = timedelta(minutes=ttl_minutes) if ttl_minutes is not None else _TTL
    with _LOCK:
        _STATES[user_id] = {
            'type': state_type,
            'payload': dict(payload),
            'expires_at': datetime.now() + ttl,
        }
    logger.info(f"[conversation_state] set {user_id[:8]}.. type={state_type} ttl={ttl} payload={payload}")


def get_state(user_id: str) -> Optional[dict]:
    """取 user 的當前狀態（過期會自動清除並回 None）"""
    with _LOCK:
        s = _STATES.get(user_id)
        if not s:
            return None
        if datetime.now() > s['expires_at']:
            del _STATES[user_id]
            logger.info(f"[conversation_state] expired {user_id[:8]}..")
            return None
        return dict(s)  # 回 copy，避免 caller 改到內部


def clear_state(user_id: str) -> None:
    """清除 user 的狀態（無就略過）"""
    with _LOCK:
        if _STATES.pop(user_id, None) is not None:
            logger.info(f"[conversation_state] cleared {user_id[:8]}..")


def state_count() -> int:
    """目前活躍 state 總數（debug 用）"""
    with _LOCK:
        return len(_STATES)
