"""LIFF 預約叫車 endpoints

Routes
------
GET  /liff/booking/form    HTML 預約表單殼（無 auth — 頁面殼）
POST /liff/booking         建立預約（auth required）

業務邏輯一律呼叫 rewrite.tools.trip.create_trip，不重做。

跟 customer LIFF 共用同一個 LIFF App（LIFF_ID 環境變數），靠
customer.py 的 GET /liff/customer/form 看 ?form=booking redirect 過來。
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


# ---------- helpers ----------

def _trip_to_jsonable(view) -> dict:
    """TripView → JSON-safe dict（date/time/datetime → ISO string）"""
    d = view.to_dict() if hasattr(view, 'to_dict') else dict(view)
    for k in ('date', 'time', 'modification_time'):
        v = d.get(k)
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


def _parse_payload(body: dict) -> tuple[dict, str | None]:
    """form payload → create_trip kwargs。錯誤回 (None, msg)"""
    fields: dict[str, Any] = {}

    # 必填：date / time / start_point
    d_raw = (body.get('date') or '').strip()
    if not d_raw:
        return {}, "請填日期"
    try:
        fields['trip_date'] = date.fromisoformat(d_raw)
    except ValueError:
        return {}, f"日期格式錯（要 YYYY-MM-DD）：{d_raw!r}"

    t_raw = (body.get('time') or '').strip()
    if not t_raw:
        return {}, "請填時間"
    try:
        # HTML time input 可能是 HH:MM 或 HH:MM:SS
        parts = [int(x) for x in t_raw.split(':')]
        if len(parts) < 2:
            raise ValueError
        fields['trip_time'] = time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
    except (ValueError, IndexError):
        return {}, f"時間格式錯（要 HH:MM）：{t_raw!r}"

    sp = (body.get('start_point') or '').strip()
    if not sp:
        return {}, "請填起點"
    fields['start_point'] = sp

    # 選填字串
    for k in ('end_point', 'via_point', 'passenger_name'):
        v = body.get(k)
        if v and isinstance(v, str):
            v = v.strip() or None
        fields[k] = v or None

    # 類別（預設東洋，跟 legacy temp_booking_handler 一致）
    fields['category'] = (body.get('category') or '東洋').strip() or '東洋'

    # 選填數字
    fields['driver_id'] = _to_int_or_none(body.get('driver_id'))
    fields['meter_fare'] = _to_int_or_none(body.get('meter_fare'))
    extra = _to_int_or_none(body.get('extra_fare'))
    fields['extra_fare'] = 0 if extra is None else extra

    return fields, None


def _push_booking_to_user(user_id: str | None, view) -> None:
    """建好 push 一則 text + 班次詳情 Flex 給用戶。失敗只 log。"""
    if not user_id:
        return
    try:
        from linebot.v3.messaging import (
            FlexContainer,
            FlexMessage,
            PushMessageRequest,
            TextMessage,
        )
        from modules.utils.line_bot import get_line_bot_api
        from rewrite.views.trip_flex import render_trip_detail

        api = get_line_bot_api()
        sp, _, ep = view.display_route()
        route = f"{sp or '?'}→{ep or '?'}"
        text_msg = TextMessage(
            text=f"✅ 已建立預約 #{view.trip_id} {view.date} {str(view.time)[:5]} {route}"
        )
        flex_dict = render_trip_detail(view)
        flex_msg = FlexMessage(
            alt_text=f"預約 #{view.trip_id}",
            contents=FlexContainer.from_dict(flex_dict),
        )
        api.push_message(PushMessageRequest(
            to=user_id,
            messages=[text_msg, flex_msg],
        ))
        logger.info(f"[LIFF] pushed booking #{view.trip_id} to {user_id[:8]}")
    except Exception as e:
        logger.warning(f"[LIFF] push booking detail failed: {e}")


# ---------- HTML 殼 ----------

@liff_bp.route('/booking/form', methods=['GET'])
def booking_form():
    return render_template(
        'liff/booking_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
    )


# ---------- JSON API ----------

@liff_bp.route('/booking', methods=['POST'])
@liff_auth_required
def booking_create():
    body = request.get_json(silent=True) or {}
    fields, err = _parse_payload(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    session = Session()
    try:
        result = trip_tools.create_trip(
            session=session,
            user_id=request.line_user_id,
            via='liff',
            **fields,
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("create_trip failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    trip_data = _trip_to_jsonable(result.data)
    logger.info(f"[LIFF] booking #{trip_data.get('trip_id')} created by {request.line_user_id}")
    _push_booking_to_user(request.line_user_id, result.data)
    return jsonify({'ok': True, 'trip': trip_data}), 201
