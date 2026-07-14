"""
批量加成 atomic tools（LIFF 用）

對齊 legacy modules/handlers/batch_allowance_handler.py 業務邏輯：
  - 對 completed_trips 範圍內班次批量 UPDATE extra_fare += amount
  - modification_reason 累加 [N] 原因（用 modules.utils.modification_utils.append_modification_reason）
  - 業務 case：颱風假/春節等批量調整

兩個 atomic tool：
  preview_batch_allowance — 純查詢，回符合條件的 trips list（給 LIFF 預覽用）
  execute_batch_allowance — 執行 batch UPDATE
"""
import logging
from datetime import date as _date, timedelta
from typing import Optional

from sqlalchemy import text

from rewrite.tools.base import ToolResult, write_audit
from modules.utils.modification_utils import append_modification_reason

logger = logging.getLogger(__name__)


VALID_BATCH_CATEGORIES = ('全部', '診所', '東洋', '臨時')


def preview_batch_allowance(
    *,
    session,
    date_from: _date,
    date_to: _date,
    category: Optional[str] = None,
) -> ToolResult:
    """預覽：撈出符合條件的 completed_trips 範圍內班次

    Args:
        date_from / date_to: 日期範圍
        category: '全部' / '診所' / '東洋' / '臨時'（None / '全部' = 不過濾）

    Returns:
        data={
            'count': int,            # 總筆數
            'preview': [{...}, ...], # 前 10 筆（id/date/route/category/current_total）
            'total_current_fare': int,  # 範圍內目前總車資（便於估後額）
        }
    """
    if not date_from or not date_to:
        return ToolResult.fail("date_from / date_to 必填")
    if date_from > date_to:
        return ToolResult.fail("date_from 不能晚於 date_to")
    if category and category not in VALID_BATCH_CATEGORIES:
        return ToolResult.fail(
            f"類別必須是 {VALID_BATCH_CATEGORIES} 之一（給的是 {category!r}）"
        )

    where = ["date >= :start_date", "date <= :end_date"]
    params = {'start_date': date_from, 'end_date': date_to}
    if category and category != '全部':
        where.append("category = :category")
        params['category'] = category

    rows = session.execute(text(f"""
        SELECT id, date, start_point, end_point, category,
               COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0) AS current_total,
               driver_id
        FROM completed_trips
        WHERE {' AND '.join(where)}
        ORDER BY date, id
    """), params).fetchall()

    if not rows:
        return ToolResult.success(data={
            'count': 0, 'preview': [], 'total_current_fare': 0,
        })

    preview = []
    total_fare = 0
    for r in rows[:10]:
        preview.append({
            'id': r[0],
            'date': r[1].isoformat() if r[1] else None,
            'route': f"{r[2] or '?'}→{r[3] or '?'}",
            'category': r[4],
            'current_total': int(r[5] or 0),
            'driver_id': r[6],
        })
    for r in rows:
        total_fare += int(r[5] or 0)

    return ToolResult.success(data={
        'count': len(rows),
        'preview': preview,
        'total_current_fare': total_fare,
    })


def execute_batch_allowance(
    *,
    session,
    date_from: _date,
    date_to: _date,
    amount: int,
    reason: str,
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """執行批量加成

    對範圍內所有 completed_trips：
      extra_fare = COALESCE(extra_fare, 0) + amount
      modification_reason 累加「[N] {reason}」

    Args:
        amount: 可正可負（颱風 +50 / 自己來 -100）
        reason: 修改原因（必填）
        category: 同 preview，None / '全部' = 不過濾
    """
    if not date_from or not date_to:
        return ToolResult.fail("date_from / date_to 必填")
    if date_from > date_to:
        return ToolResult.fail("date_from 不能晚於 date_to")
    if not isinstance(amount, int):
        return ToolResult.fail("amount 必須是整數")
    if amount == 0:
        return ToolResult.fail("amount 不能是 0（沒意義）")
    if not reason or not reason.strip():
        return ToolResult.fail("reason 必填")
    if category and category not in VALID_BATCH_CATEGORIES:
        return ToolResult.fail(
            f"類別必須是 {VALID_BATCH_CATEGORIES} 之一"
        )
    reason = reason.strip()

    # 先撈所有符合的 trips（拿 modification_reason 累加用）
    where = ["date >= :start_date", "date <= :end_date"]
    params = {'start_date': date_from, 'end_date': date_to}
    if category and category != '全部':
        where.append("category = :category")
        params['category'] = category

    rows = session.execute(text(f"""
        SELECT id, date, modification_reason, category
        FROM completed_trips
        WHERE {' AND '.join(where)}
        ORDER BY id
    """), params).fetchall()

    if not rows:
        return ToolResult.fail(
            f"範圍內 ({date_from} ~ {date_to} {category or '全部'}) 沒有符合的班次"
        )

    # 逐筆 UPDATE（modification_reason 累加要看舊值）
    updated = 0
    for trip_id, _trip_date, current_reason, _trip_category in rows:
        new_reason = append_modification_reason(
            current_reason, reason, 'completed_trips',
        )
        result = session.execute(text("""
            UPDATE completed_trips
            SET extra_fare = COALESCE(extra_fare, 0) + :amount,
                modification_reason = :new_reason
            WHERE id = :id
        """), {'amount': amount, 'new_reason': new_reason, 'id': trip_id})
        if result.rowcount > 0:
            updated += 1

    # batch audit
    write_audit(
        session=session,
        user_id=user_id, user_name=user_name,
        action_type='batch_allowance',
        target_table='completed_trips', target_id=0,
        before_state=None,
        after_state={
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
            'category': category or '全部',
            'amount': amount, 'reason': reason,
            'updated': updated,
        },
        changed_fields=None,
        extra={'updated_count': updated, 'matched_count': len(rows)},
        via=via,
    )

    if auto_commit:
        session.commit()

    return ToolResult.success(data={
        'updated_count': updated,
        'matched_count': len(rows),
        'amount': amount,
        'reason': reason,
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'category': category or '全部',
        # 帳務勾稽：受影響太陽週若已記週扣款 → 附警語（只提示不改帳）
        'weekly_charge_warnings': _weekly_charge_warnings(
            session=session, rows=rows, amount=amount,
        ),
    })


def _weekly_charge_warnings(*, session, rows, amount: int) -> list:
    """算批量加成影響到的太陽週勾稽警語清單

    rows: [(id, date, modification_reason, category), ...]（本次被加成的班次）
    ⚠️ 只統計「診所」類班次 — weekly_charge 是達恩診所的車資週扣款，
    東洋/臨時班次與週扣款無關（用戶實測回報 2026-07）。
    每個受影響太陽週若已有「有效」weekly_charge 分錄，
    差額 = amount × 該週被加成的**診所**筆數；該週沒有診所班次就不出警語。
    """
    try:
        # lazy import 避免循環 import
        from rewrite.tools.accounting import find_weekly_charge_for_week
        from rewrite.utils.sun_week import sun_week_start

        week_counts: dict = {}
        for _trip_id, trip_date, _reason, trip_category in rows:
            if not trip_date or trip_category != '診所':
                continue
            ws = sun_week_start(trip_date)
            week_counts[ws] = week_counts.get(ws, 0) + 1

        warnings = []
        for ws in sorted(week_counts):
            we = ws + timedelta(days=6)
            charge = find_weekly_charge_for_week(session=session, week_end_date=we)
            if not charge:
                continue
            delta = amount * week_counts[ws]
            warnings.append(
                f"⚠️ 該週（{ws.month}/{ws.day}〜{we.month}/{we.day}）已記扣款 "
                f"NT$ {charge['amount_out']:,}，本次調整差額 {delta:+,}，"
                f"帳務需補沖正/補記"
            )
        return warnings
    except Exception as e:  # 勾稽失敗不擋主流程
        logger.warning(f"batch_allowance weekly_charge 勾稽檢查失敗: {e}")
        return []
