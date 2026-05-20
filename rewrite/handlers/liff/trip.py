"""LIFF 班次狀態管理 endpoints

Routes
------
GET  /liff/trip/<trip_id>/status_form    HTML 狀態管理表單殼（無 auth — 頁面殼）
GET  /liff/trip/<trip_id>                JSON prefill — 表單載入用（auth required）
POST /liff/trip/<trip_id>/status         執行狀態變更（auth required，依 action dispatch）

action 對應 atomic tool：
  - 'leave'    → passenger_leave(reason, surcharge)   ※ reason 必填
  - 'cancel'   → cancel_trip(reason 可空)
  - 'conflict' → mark_conflict(reason 可空)
  - 'restore'  → restore_to_ready

業務邏輯一律呼叫 rewrite.tools.trip 的 atomic tools；30 分鐘鎖 / 狀態檢查 /
audit / modification_reason 累加全部由 atomic tool 內部把關，本檔只做 dispatcher。

共用 customer 的 LIFF App（LIFF_ID 環境變數），靠 customer.py 的
GET /liff/customer/form 看 ?form=trip_status&trip_id=N 重導過來。
"""
import logging
import os
from datetime import date, datetime, time
from typing import Any

from flask import jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from database import Session
from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required
from rewrite.tools import trip as trip_tools

logger = logging.getLogger(__name__)


VALID_ACTIONS = ('leave', 'cancel', 'conflict', 'restore')

_ACTION_LABEL = {
    'leave': '🏷️ 請假',
    'cancel': '🚫 註銷',
    'conflict': '⚠️ 衝突',
    'restore': '🔄 改回準備',
}


def _trip_to_jsonable(view) -> dict:
    """TripView → JSON-safe dict（date/time/datetime → ISO string）"""
    d = view.to_dict() if hasattr(view, 'to_dict') else dict(view)
    for k, v in list(d.items()):
        if isinstance(v, (date, datetime, time)):
            d[k] = v.isoformat()
    return d


def _to_int_or_none(v) -> int | None:
    if v in (None, '', 'null'):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ---------- HTML 殼 ----------

@liff_bp.route('/trip/<int:trip_id>/status_form', methods=['GET'])
def trip_status_form(trip_id):
    """單筆班次狀態管理表單殼（無 auth — 頁面 HTML，實際操作仍走 POST 需 auth）"""
    return render_template(
        'liff/trip_status_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        trip_id=trip_id,
    )


# ---------- JSON prefill ----------

@liff_bp.route('/trip/<int:trip_id>', methods=['GET'])
@liff_auth_required
def trip_get(trip_id):
    """JSON prefill — 表單載入時拿班次當前狀態 / 鎖定資訊用"""
    session = Session()
    try:
        result = trip_tools.query_trip_by_id(trip_id, session=session)
    finally:
        session.close()
    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 404
    return jsonify({'ok': True, 'trip': _trip_to_jsonable(result.data)})


# ---------- POST: dispatch action ----------

@liff_bp.route('/trip/<int:trip_id>/status', methods=['POST'])
@liff_auth_required
def trip_status_change(trip_id):
    """依 body['action'] dispatch 到對應 atomic tool。

    payload：
      { action: 'leave'|'cancel'|'conflict'|'restore',
        reason?: str,              # leave 必填；cancel/conflict 可空；restore 不用
        surcharge?: int,           # leave 用，預設 0
        source?: {type, groupId/roomId} }  # 給 push 用
    """
    body = request.get_json(silent=True) or {}
    action = (body.get('action') or '').strip().lower()
    if action not in VALID_ACTIONS:
        return jsonify({
            'ok': False,
            'error': f"action 必須是 {' / '.join(VALID_ACTIONS)} 之一",
        }), 400

    reason = (body.get('reason') or '').strip()
    surcharge_raw = body.get('surcharge')
    surcharge = _to_int_or_none(surcharge_raw)

    session = Session()
    try:
        if action == 'leave':
            if not reason:
                return jsonify({'ok': False, 'error': '請假必須填原因'}), 400
            if surcharge is None:
                surcharge = 0
            result = trip_tools.passenger_leave(
                session=session, trip_id=trip_id,
                reason=reason, surcharge=surcharge,
                user_id=request.line_user_id, via='liff',
            )
        elif action == 'cancel':
            result = trip_tools.cancel_trip(
                session=session, trip_id=trip_id,
                reason=reason or None,
                user_id=request.line_user_id, via='liff',
            )
        elif action == 'conflict':
            result = trip_tools.mark_conflict(
                session=session, trip_id=trip_id,
                reason=reason or None,
                user_id=request.line_user_id, via='liff',
            )
        else:  # restore
            result = trip_tools.restore_to_ready(
                session=session, trip_id=trip_id,
                user_id=request.line_user_id, via='liff',
            )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception(f"trip_status_change action={action} trip_id={trip_id} failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    trip_data = _trip_to_jsonable(result.data)
    logger.info(
        f"[LIFF] trip #{trip_id} action={action} "
        f"reason={reason!r} surcharge={surcharge} by {request.line_user_id}"
    )
    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    _push_trip_status(target, result.data, action, reason, surcharge)
    return jsonify({'ok': True, 'trip': trip_data})


# ---------- push 結果回 chat ----------

def _push_trip_status(target_id, view, action, reason, surcharge):
    """執行後 push 一則 text + 班次詳情 Flex 到指定目標（群組/聊天室/個人）。"""
    if not target_id:
        return
    try:
        from linebot.v3.messaging import (
            FlexContainer, FlexMessage, PushMessageRequest, TextMessage,
        )
        from modules.utils.line_bot import get_line_bot_api
        from rewrite.views.trip_flex import render_trip_detail

        api = get_line_bot_api()
        label = _ACTION_LABEL.get(action, action)
        sp, _, ep = view.display_route()
        route = f"{sp or '?'}→{ep or '?'}"
        time_str = str(view.time)[:5] if view.time else '?'
        date_str = view.date.isoformat() if view.date else '?'
        lines = [
            f"✅ 班次 #{view.trip_id} 已執行：{label}",
            f"{date_str} {time_str} {route}",
        ]
        if action == 'leave':
            lines.append(f"原因：{reason}")
            lines.append(f"加成：{surcharge:+d} 元" if surcharge else "加成：0 元")
        elif action in ('cancel', 'conflict') and reason:
            lines.append(f"原因：{reason}")
        if action in ('cancel', 'conflict'):
            lines.append("（可用『改回準備』還原）")
        text_msg = TextMessage(text='\n'.join(lines))

        flex_dict = render_trip_detail(view)
        flex_msg = FlexMessage(
            alt_text=f"班次 #{view.trip_id} {label}",
            contents=FlexContainer.from_dict(flex_dict),
        )
        api.push_message(PushMessageRequest(
            to=target_id, messages=[text_msg, flex_msg],
        ))
        logger.info(
            f"[LIFF] pushed trip status #{view.trip_id} ({action}) to {target_id[:8]}"
        )
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push trip status failed: {e} body={body_attr!r}")
