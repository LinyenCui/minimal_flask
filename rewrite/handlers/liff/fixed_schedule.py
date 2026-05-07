"""LIFF 固定班次（fixed_schedule）endpoints

Routes
------
GET  /liff/fixed_schedule/form    HTML 新增表單殼
POST /liff/fixed_schedule         新增（auth required）

業務邏輯一律呼叫 rewrite.tools.fixed_schedule.create_fixed_schedule。
共用 customer 的 LIFF App，靠 ?form=new_schedule dispatch。
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
from rewrite.tools import fixed_schedule as fs_tools

logger = logging.getLogger(__name__)


def _schedule_to_jsonable(view) -> dict:
    """FixedScheduleView → JSON-safe dict"""
    d = view.to_dict() if hasattr(view, 'to_dict') else dict(view)
    for k, v in d.items():
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
    """form payload → create_fixed_schedule kwargs。錯誤回 (None, msg)"""
    fields: dict[str, Any] = {}

    rn = (body.get('route_number') or '').strip()
    if not rn:
        return {}, "請選每週幾"
    fields['route_number'] = rn

    t_raw = (body.get('departure_time') or '').strip()
    if not t_raw:
        return {}, "請填出發時間"
    try:
        parts = [int(x) for x in t_raw.split(':')]
        if len(parts) < 2:
            raise ValueError
        fields['departure_time'] = time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
    except (ValueError, IndexError):
        return {}, f"時間格式錯（要 HH:MM）：{t_raw!r}"

    sp = (body.get('start_point') or '').strip()
    if not sp:
        return {}, "請填起點"
    fields['start_point'] = sp

    cat = (body.get('category') or '').strip()
    if not cat:
        return {}, "請選類別"
    fields['category'] = cat

    # 選填字串
    for k in ('via_point', 'end_point', 'driver_id', 'direction', 'note'):
        v = body.get(k)
        if v and isinstance(v, str):
            v = v.strip() or None
        fields[k] = v or None

    # 選填數字
    fields['base_fare'] = _to_int_or_none(body.get('base_fare'))
    fields['surcharge'] = _to_int_or_none(body.get('surcharge'))

    return fields, None


def _push_schedule_to_user(user_id: str | None, view) -> None:
    """建好 push 一則 text 給用戶（沿用 customer/booking 模式）"""
    if not user_id:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api

        api = get_line_bot_api()
        wd_map = {'1': '一', '2': '二', '3': '三', '4': '四',
                  '5': '五', '6': '六', '7': '日'}
        wd_str = ''.join(wd_map.get(c, c) for c in view.route_number or '')
        msg = (
            f"✅ 已建立固定班次 #{view.id}\n"
            f"每週{wd_str} {str(view.departure_time)[:5] if view.departure_time else '?'}\n"
            f"{view.start_point or '?'} → {view.end_point or '?'}\n"
            f"類別：{view.category or '?'}"
        )
        api.push_message(PushMessageRequest(
            to=user_id,
            messages=[TextMessage(text=msg)],
        ))
        logger.info(f"[LIFF] pushed schedule #{view.id} to {user_id[:8]}")
    except Exception as e:
        logger.warning(f"[LIFF] push schedule detail failed: {e}")


# ---------- HTML 殼 ----------

@liff_bp.route('/fixed_schedule/form', methods=['GET'])
def fixed_schedule_form_new():
    return render_template(
        'liff/fixed_schedule_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        schedule_id=None,
    )


@liff_bp.route('/fixed_schedule/<int:schedule_id>/form', methods=['GET'])
def fixed_schedule_form_edit(schedule_id):
    """編輯模式表單殼（HTML），跟新增共用同 template"""
    return render_template(
        'liff/fixed_schedule_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        schedule_id=schedule_id,
    )


@liff_bp.route('/fixed_schedule/<int:schedule_id>', methods=['GET'])
@liff_auth_required
def fixed_schedule_get(schedule_id):
    """JSON prefill — 編輯模式 JS 載入用"""
    session = Session()
    try:
        result = fs_tools.get_fixed_schedule_by_id(schedule_id, session=session)
    finally:
        session.close()
    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 404
    return jsonify({'ok': True, 'schedule': _schedule_to_jsonable(result.data)})


@liff_bp.route('/fixed_schedule/<int:schedule_id>/leave_form', methods=['GET'])
def fixed_schedule_leave_form(schedule_id):
    """請假表單殼"""
    return render_template(
        'liff/fixed_schedule_leave_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        schedule_id=schedule_id,
    )


@liff_bp.route('/fixed_schedule/<int:schedule_id>/leave', methods=['POST'])
@liff_auth_required
def fixed_schedule_leave(schedule_id):
    """執行請假（apply_fixed_schedule_leave）"""
    body = request.get_json(silent=True) or {}
    reason = (body.get('reason') or '').strip()
    if not reason:
        return jsonify({'ok': False, 'error': '請填請假原因'}), 400
    surcharge = _to_int_or_none(body.get('surcharge'))
    if surcharge is None:
        surcharge = 0

    session = Session()
    try:
        result = fs_tools.apply_fixed_schedule_leave(
            session=session,
            schedule_id=schedule_id,
            reason=reason,
            surcharge=surcharge,
            user_id=request.line_user_id,
            via='liff',
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("apply_fixed_schedule_leave failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    schedule_data = _schedule_to_jsonable(result.data)
    logger.info(
        f"[LIFF] fixed_schedule #{schedule_id} 請假 ({reason}, {surcharge}) "
        f"by {request.line_user_id}"
    )
    _push_schedule_leave_to_user(request.line_user_id, result.data, reason, surcharge)
    return jsonify({'ok': True, 'schedule': schedule_data})


def _push_schedule_leave_to_user(user_id, view, reason, surcharge):
    if not user_id:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api
        api = get_line_bot_api()
        wd_map = {'1': '一', '2': '二', '3': '三', '4': '四',
                  '5': '五', '6': '六', '7': '日'}
        wd_str = ''.join(wd_map.get(c, c) for c in view.route_number or '')
        msg = (
            f"🏷️ 已將固定班次 #{view.id} 設為請假\n"
            f"每週{wd_str} {str(view.departure_time)[:5] if view.departure_time else '?'}\n"
            f"原因：{reason}\n"
            f"加成：{surcharge:+d} 元"
        )
        api.push_message(PushMessageRequest(
            to=user_id, messages=[TextMessage(text=msg)],
        ))
    except Exception as e:
        logger.warning(f"[LIFF] push schedule leave failed: {e}")


# ---------- JSON API ----------

@liff_bp.route('/fixed_schedule/<int:schedule_id>', methods=['POST'])
@liff_auth_required
def fixed_schedule_update(schedule_id):
    """更新（編輯模式提交）"""
    body = request.get_json(silent=True) or {}
    # 編輯模式可空欄位（未改 = None），不做必填強制
    fields, err = _parse_payload_for_update(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    session = Session()
    try:
        result = fs_tools.update_fixed_schedule(
            session=session,
            schedule_id=schedule_id,
            user_id=request.line_user_id,
            via='liff',
            **fields,
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("update_fixed_schedule failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    schedule_data = _schedule_to_jsonable(result.data)
    logger.info(
        f"[LIFF] fixed_schedule #{schedule_id} updated by {request.line_user_id}"
    )
    _push_schedule_update_to_user(request.line_user_id, result.data)
    return jsonify({'ok': True, 'schedule': schedule_data})


def _parse_payload_for_update(body: dict) -> tuple[dict, str | None]:
    """編輯模式 — 都是選填，跟 _parse_payload 不同"""
    fields: dict[str, Any] = {}

    rn = (body.get('route_number') or '').strip() or None
    if rn:
        fields['route_number'] = rn

    t_raw = (body.get('departure_time') or '').strip() or None
    if t_raw:
        try:
            parts = [int(x) for x in t_raw.split(':')]
            if len(parts) < 2:
                raise ValueError
            fields['departure_time'] = time(parts[0], parts[1],
                                              parts[2] if len(parts) > 2 else 0)
        except (ValueError, IndexError):
            return {}, f"時間格式錯（要 HH:MM）：{t_raw!r}"

    for k in ('start_point', 'via_point', 'end_point',
              'driver_id', 'direction', 'note', 'category'):
        v = body.get(k)
        if v and isinstance(v, str):
            v = v.strip() or None
        if v:
            fields[k] = v

    bf = _to_int_or_none(body.get('base_fare'))
    if bf is not None:
        fields['base_fare'] = bf
    sc = _to_int_or_none(body.get('surcharge'))
    if sc is not None:
        fields['surcharge'] = sc

    if not fields:
        return {}, "沒給任何要更新的欄位"

    return fields, None


def _push_schedule_update_to_user(user_id: str | None, view) -> None:
    """更新後 push text"""
    if not user_id:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api
        api = get_line_bot_api()
        wd_map = {'1': '一', '2': '二', '3': '三', '4': '四',
                  '5': '五', '6': '六', '7': '日'}
        wd_str = ''.join(wd_map.get(c, c) for c in view.route_number or '')
        msg = (
            f"✅ 已更新固定班次 #{view.id}\n"
            f"每週{wd_str} {str(view.departure_time)[:5] if view.departure_time else '?'}\n"
            f"{view.start_point or '?'} → {view.end_point or '?'}\n"
            f"類別：{view.category or '?'}"
        )
        api.push_message(PushMessageRequest(
            to=user_id, messages=[TextMessage(text=msg)],
        ))
    except Exception as e:
        logger.warning(f"[LIFF] push schedule update failed: {e}")


@liff_bp.route('/fixed_schedule', methods=['POST'])
@liff_auth_required
def fixed_schedule_create():
    body = request.get_json(silent=True) or {}
    fields, err = _parse_payload(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    session = Session()
    try:
        result = fs_tools.create_fixed_schedule(
            session=session,
            user_id=request.line_user_id,
            via='liff',
            **fields,
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("create_fixed_schedule failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    schedule_data = _schedule_to_jsonable(result.data)
    logger.info(
        f"[LIFF] fixed_schedule #{schedule_data.get('id')} created by {request.line_user_id}"
    )
    _push_schedule_to_user(request.line_user_id, result.data)
    return jsonify({'ok': True, 'schedule': schedule_data}), 201
