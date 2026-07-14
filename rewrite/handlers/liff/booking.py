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


def _fmt_md(iso_date) -> str:
    """'2026-06-14' → '6/14'（彙總顯示用）；解析失敗回原字串。"""
    if not iso_date:
        return ''
    try:
        d = date.fromisoformat(str(iso_date)[:10])
        return f"{d.month}/{d.day}"
    except ValueError:
        return str(iso_date)


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


def _push_booking(target_id: str | None, view) -> None:
    """建好 push 一則 text + 班次詳情 Flex 到指定目標（群組 / 聊天室 / 個人）。"""
    if not target_id:
        return
    try:
        from linebot.v3.messaging import (
            FlexContainer,
            FlexMessage,
            PushMessageRequest,
            TextMessage,
        )
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled
        from rewrite.views.trip_flex import render_trip_detail

        if not push_notify_enabled():
            logger.info("[LIFF] push skipped (PUSH_NOTIFY off)")
            return
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
            to=target_id,
            messages=[text_msg, flex_msg],
        ))
        logger.info(f"[LIFF] pushed booking #{view.trip_id} to {target_id[:8]}")
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push booking detail failed: {e} body={body_attr!r}")


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

    # 起/終點未對應客戶簡稱（落入「臨時地點」佔位）→ 表單內提醒（不進 push，省額度）。
    # 暗坑：「X的狀態」對 start_point/end_point 精確比對，臨時地點班次永遠查不到，
    # 錯字簡稱在預約當下看起來完全成功，隔天才發現查無此班。
    tv = result.data
    warnings = []
    _tid = trip_data.get('trip_id')
    if getattr(tv, 'start_point', None) == '臨時地點' and getattr(tv, 'custom_start_point', None):
        warnings.append(
            f"起點「{tv.custom_start_point}」未對應客戶簡稱，已存為臨時班次 — "
            f"之後用「{tv.custom_start_point}的狀態」會查不到，需用「班次詳情 {_tid}」查詢。"
            f"若是打錯字，請註銷後重新預約"
        )
    if getattr(tv, 'end_point', None) == '臨時地點' and getattr(tv, 'custom_end_point', None):
        warnings.append(
            f"終點「{tv.custom_end_point}」未對應客戶簡稱，已存為臨時地點"
        )

    # 連續預約：前端逐筆帶 suppress_push=true → 各筆不推,全部做完由
    # /liff/booking/batch_notify 收尾推「一則彙總」,把「N 筆 = N 則 push」
    # 降為「N 筆 = 1 則」,省 LINE 免費月額度（200 則/月）。
    if not bool(body.get('suppress_push')):
        from rewrite.utils.liff_url import resolve_push_target
        target = resolve_push_target(body.get('source'), request.line_user_id)
        _push_booking(target, result.data)
    return jsonify({'ok': True, 'trip': trip_data, 'warnings': warnings}), 201


@liff_bp.route('/booking/batch_notify', methods=['POST'])
@liff_auth_required
def booking_batch_notify():
    """連續預約收尾：把 N 筆新預約彙總成「一則」push 回群組。

    前端逐筆 POST /liff/booking 帶 suppress_push=true（各筆不推），全部做完
    呼叫本 endpoint 推一則彙總 → 把「N 筆 = N 則 push」降為「N 筆 = 1 則」,
    是 LINE 免費月額度（200 則/月）的止血點。沿用 trip.py 的
    batch_status_notify 同款 pattern。

    payload: { bookings:[{trip_id, date, time, start_point, end_point}],
               source?:{type,groupId/roomId} }
    """
    body = request.get_json(silent=True) or {}
    raw = body.get('bookings') or []
    if not isinstance(raw, list):
        return jsonify({'ok': False, 'error': 'bookings 格式錯'}), 400
    bookings = [b for b in raw if isinstance(b, dict) and b.get('trip_id')]
    if not bookings:
        return jsonify({'ok': True, 'skipped': 'no bookings'})

    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    if not target:
        return jsonify({'ok': True, 'skipped': 'no target'})

    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled

        if not push_notify_enabled():
            logger.info("[LIFF] booking batch notify skipped (PUSH_NOTIFY off)")
            return jsonify({'ok': True, 'skipped': 'push off'})

        lines = [f"✅ 已建立 {len(bookings)} 筆預約"]
        for b in bookings:
            tid = b.get('trip_id')
            md = _fmt_md(b.get('date'))
            hm = str(b.get('time') or '')[:5]
            sp = (str(b.get('start_point') or '').strip()) or '?'
            ep = str(b.get('end_point') or '').strip()
            route = f"{sp}→{ep}" if ep else sp
            lines.append(f"　#{tid}　{md} {hm} {route}".rstrip())

        api = get_line_bot_api()
        api.push_message(PushMessageRequest(
            to=target, messages=[TextMessage(text='\n'.join(lines))],
        ))
        logger.info(
            f"[LIFF] booking batch notify n={len(bookings)} → {target[:8]} (1 push)"
        )
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] booking batch notify failed: {e} body={body_attr!r}")
    return jsonify({'ok': True})
