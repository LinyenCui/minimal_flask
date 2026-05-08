"""
工具的共用基礎型別 + R-5 鎖 decorator + audit log helper
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Optional, List, Callable
import json
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

# R-5: 30 分鐘鎖
LOCK_MINUTES = 30


@dataclass
class ToolResult:
    """所有 tool 的統一回傳格式"""
    ok: bool
    data: Any = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    @classmethod
    def success(cls, data: Any = None, **meta) -> "ToolResult":
        return cls(ok=True, data=data, meta=meta)

    @classmethod
    def fail(cls, error: str, **meta) -> "ToolResult":
        return cls(ok=False, error=error, meta=meta)

    def __bool__(self):
        return self.ok


# ============================================================
# R-5: 30 分鐘鎖 decorator
# ============================================================

def require_modifiable_window(allow_in_lock: bool = False):
    """
    強制檢查班次是否在可修改窗口內（執行時間前 30 分鐘）。

    Args:
        allow_in_lock: True 表示鎖內也可執行（用於 assign_driver, unassign_driver,
                       record_fare_current, update_passenger_name 等）
                       False（預設）= 嚴格鎖（status 變更類）

    要求：被裝飾函數必須有 kw 參數 trip_id 和 session。
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if allow_in_lock:
                # 不檢查鎖
                return fn(*args, **kwargs)

            trip_id = kwargs.get('trip_id')
            session = kwargs.get('session')
            if trip_id is None or session is None:
                # 沒給 trip_id 或 session 就無法檢查 → 直接放行
                return fn(*args, **kwargs)

            row = session.execute(
                text("SELECT date, time FROM trips WHERE trip_id = :id"),
                {'id': trip_id}
            ).fetchone()

            if row and row[0] and row[1]:
                trip_dt = datetime.combine(row[0], row[1])
                now = datetime.now()
                if trip_dt > now and (trip_dt - now) < timedelta(minutes=LOCK_MINUTES):
                    minutes_left = int((trip_dt - now).total_seconds() / 60)
                    lock_start = (trip_dt - timedelta(minutes=LOCK_MINUTES)).strftime('%H:%M')
                    return ToolResult.fail(
                        f"⏰ 班次 #{trip_id} 距執行時間還有 {minutes_left} 分鐘，"
                        f"{LOCK_MINUTES} 分鐘內不可修改狀態。\n"
                        f"💡 提示：可改用「撤銷指派」變回「待派」以阻止自動完成。",
                        locked=True, minutes_left=minutes_left, lock_start=lock_start,
                    )

            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# R-6: audit log helper
# ============================================================

def _to_json_safe(obj: Any) -> Any:
    """把 row dict 轉成 JSON 安全格式（datetime → isoformat）"""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def write_audit(
    *,
    session,
    user_id: Optional[str],
    user_name: Optional[str] = None,
    action_type: str,
    target_table: str,
    target_id: int,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
    changed_fields: Optional[List[str]] = None,
    reason: Optional[str] = None,
    extra: Optional[dict] = None,
    via: str = 'unknown',
) -> None:
    """寫一筆 audit log。失敗只 log error 不擋主流程。"""
    try:
        session.execute(
            text("""
                INSERT INTO audit_log (
                    user_id, user_name, action_type, target_table, target_id,
                    before_state, after_state, changed_fields, reason, extra, via
                ) VALUES (
                    :user_id, :user_name, :action_type, :target_table, :target_id,
                    CAST(:before_state AS JSONB), CAST(:after_state AS JSONB),
                    :changed_fields, :reason, CAST(:extra AS JSONB), :via
                )
            """),
            {
                'user_id': user_id,
                'user_name': user_name,
                'action_type': action_type,
                'target_table': target_table,
                'target_id': target_id,
                'before_state': json.dumps(_to_json_safe(before_state), ensure_ascii=False)
                                if before_state else None,
                'after_state': json.dumps(_to_json_safe(after_state), ensure_ascii=False)
                               if after_state else None,
                'changed_fields': changed_fields,
                'reason': reason,
                'extra': json.dumps(_to_json_safe(extra), ensure_ascii=False)
                         if extra else None,
                'via': via,
            }
        )
    except Exception as e:
        logger.error(f"audit log 寫入失敗（不擋主流程）: {e}", exc_info=True)


def fetch_trip_snapshot(*, session, trip_id: int) -> Optional[dict]:
    """取一筆 trip 完整 row 當 audit 快照"""
    row = session.execute(
        text("SELECT * FROM trips WHERE trip_id = :id"),
        {'id': trip_id}
    ).fetchone()
    return dict(row._mapping) if row else None


def diff_fields(before: Optional[dict], after: Optional[dict]) -> List[str]:
    """比對兩個 dict，回傳變更欄位清單"""
    if not before or not after:
        return []
    return [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
