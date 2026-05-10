"""LIFF 批量加成 endpoints

Routes
------
GET  /liff/batch_allowance/form     批量加成表單殼
POST /liff/batch_allowance/preview  預覽（不寫入）
POST /liff/batch_allowance          執行批量加成（auth required）
"""
import logging
import os
from datetime import date
from typing import Any

from flask import jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from database import Session
from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required
from rewrite.tools import batch_allowance as ba_tools

logger = logging.getLogger(__name__)


def _parse_date_range(body) -> tuple[date | None, date | None, str | None]:
    df_raw = (body.get('date_from') or '').strip()
    dt_raw = (body.get('date_to') or '').strip()
    if not df_raw or not dt_raw:
        return None, None, "請填日期範圍"
    try:
        df = date.fromisoformat(df_raw)
        dt = date.fromisoformat(dt_raw)
    except ValueError:
        return None, None, "日期格式錯（要 YYYY-MM-DD）"
    if df > dt:
        return None, None, "起日不能晚於迄日"
    return df, dt, None


# ---------- HTML 殼 ----------

@liff_bp.route('/batch_allowance/form', methods=['GET'])
def batch_allowance_form():
    return render_template(
        'liff/batch_allowance_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
    )


# ---------- JSON API: 預覽 ----------

@liff_bp.route('/batch_allowance/preview', methods=['POST'])
@liff_auth_required
def batch_allowance_preview():
    body = request.get_json(silent=True) or {}
    df, dt, err = _parse_date_range(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    cat = (body.get('category') or '全部').strip() or '全部'

    session = Session()
    try:
        result = ba_tools.preview_batch_allowance(
            session=session, date_from=df, date_to=dt, category=cat,
        )
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400
    return jsonify({'ok': True, **result.data})


# ---------- JSON API: 執行 ----------

@liff_bp.route('/batch_allowance', methods=['POST'])
@liff_auth_required
def batch_allowance_execute():
    body = request.get_json(silent=True) or {}
    df, dt, err = _parse_date_range(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    cat = (body.get('category') or '全部').strip() or '全部'
    try:
        amount = int(body.get('amount'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': '金額必須是整數'}), 400

    reason = (body.get('reason') or '').strip()
    if not reason:
        return jsonify({'ok': False, 'error': '請填原因'}), 400

    session = Session()
    try:
        result = ba_tools.execute_batch_allowance(
            session=session,
            date_from=df, date_to=dt,
            amount=amount, reason=reason, category=cat,
            user_id=request.line_user_id,
            via='liff',
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("execute_batch_allowance failed")
        return jsonify({'ok': False, 'error': f'DB error: {e}'}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    data = result.data
    logger.info(
        f"[LIFF] batch_allowance updated={data['updated_count']} "
        f"({df}~{dt} {cat} {amount:+d} {reason!r}) by {request.line_user_id}"
    )
    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    _push_batch_allowance(target, data)
    return jsonify({'ok': True, **data}), 201


def _push_batch_allowance(target_id, data) -> None:
    if not target_id:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api
        api = get_line_bot_api()
        amt = data['amount']
        msg = (
            f"💰 已批量加成 {data['updated_count']} 筆\n"
            f"範圍：{data['date_from']} ~ {data['date_to']}（{data['category']}）\n"
            f"加成：{amt:+d} 元\n"
            f"原因：{data['reason']}"
        )
        api.push_message(PushMessageRequest(
            to=target_id, messages=[TextMessage(text=msg)],
        ))
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push batch_allowance failed: {e} body={body_attr!r}")
