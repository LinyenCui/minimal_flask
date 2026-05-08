"""
R-3 統一請假介面（apply_leave）

跨時間態請假：根據 target_id 所在表自動分流。
- trips 表          → 呼叫 passenger_leave（現在態，三層障眼法，已實作）
- fixed_schedules → 暫回 fallback 訊息（v0.1 跳過此路徑，由 sandbox 舊流程處理）
- 都不在          → fail

修 B-1 / C-3：原 sandbox 「！行程id1043請假」永遠路由到 fixed_schedule_leave
的 bug。AI agent 只看到 apply_leave 一個介面，不需了解三時間態差別。

優先順序：trips 優先於 fixed_schedules（若 ID 同時存在於兩表，視為 trip）。
"""
from typing import Optional

from sqlalchemy import text

from rewrite.tools.base import ToolResult
from rewrite.tools.trip import passenger_leave


def apply_leave(
    *,
    session,
    target_id: int,
    reason: str,
    surcharge: int = 0,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """
    統一請假介面（R-3）

    Args:
        target_id: 不指定是 trip_id 或 fixed_schedule_id，由 wrapper 判斷
        reason / surcharge / user_*: 跟 passenger_leave 一致

    Returns:
        ToolResult — meta 含 routed_to 標明走哪條路徑：
        - 'trips'             → 已轉給 passenger_leave 處理
        - 'fixed_schedules'   → fallback 提示（暫不執行）
        - 'none'              → 找不到
    """
    # ---- 基本型別驗證 ----
    if not isinstance(target_id, int):
        return ToolResult.fail("target_id 必須是整數", routed_to='none')

    # ---- 1. 先查 trips（優先順序）----
    in_trips = session.execute(
        text("SELECT 1 FROM trips WHERE trip_id = :id"),
        {'id': target_id}
    ).fetchone()

    if in_trips:
        result = passenger_leave(
            session=session,
            trip_id=target_id,
            reason=reason,
            surcharge=surcharge,
            user_id=user_id,
            user_name=user_name,
            via=via,
            auto_commit=auto_commit,
        )
        # 在 meta 加註 routed_to，方便 caller 知道走哪條路
        result.meta['routed_to'] = 'trips'
        return result

    # ---- 2. 查 fixed_schedules ----
    in_fixed = session.execute(
        text("SELECT 1 FROM fixed_schedules WHERE id = :id"),
        {'id': target_id}
    ).fetchone()

    if in_fixed:
        return ToolResult.fail(
            f"班次 #{target_id} 是固定班次模板（fixed_schedules）。\n"
            f"v0.1 暫跳過此路徑，請改用 sandbox 舊流程：\n"
            f"  ！固定班次 {target_id} 請假 {reason}",
            routed_to='fixed_schedules',
            target_table='fixed_schedules',
            target_id=target_id,
            sandbox_command=f"！固定班次 {target_id} 請假 {reason}",
        )

    # ---- 3. 都不在 ----
    return ToolResult.fail(
        f"找不到班次 #{target_id}（trips 跟 fixed_schedules 都沒有）",
        routed_to='none',
    )
