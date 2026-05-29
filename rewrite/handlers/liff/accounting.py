"""LIFF 帳務處理 endpoints

Routes
------
GET  /liff/accounting/deposit_form          入金表單殼
GET  /liff/accounting/weekly_payment_form   上週扣款表單殼
POST /liff/accounting/deposit               記入金（auth required）
POST /liff/accounting/weekly_payment        記上週扣款（auth required）

業務邏輯：rewrite.tools.accounting 的三個 atomic tools。
"""
import logging
import os
from datetime import date, datetime
from typing import Any

from flask import jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from database import Session
from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required
from rewrite.tools import accounting as acct_tools

logger = logging.getLogger(__name__)


# ---------- HTML 殼 ----------

@liff_bp.route('/accounting/deposit_form', methods=['GET'])
def accounting_deposit_form():
    return render_template(
        'liff/deposit_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
    )


@liff_bp.route('/accounting/weekly_payment_form', methods=['GET'])
def accounting_weekly_payment_form():
    return render_template(
        'liff/weekly_payment_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
    )


# ---------- JSON API: 入金 ----------

@liff_bp.route('/accounting/deposit', methods=['POST'])
@liff_auth_required
def accounting_deposit():
    body = request.get_json(silent=True) or {}

    d_raw = (body.get('deposit_date') or '').strip()
    if not d_raw:
        return jsonify({'ok': False, 'error': '請填日期'}), 400
    try:
        deposit_date = date.fromisoformat(d_raw)
    except ValueError:
        return jsonify({'ok': False, 'error': f'日期格式錯：{d_raw!r}'}), 400

    try:
        amount = int(body.get('amount'))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': '金額必須是正整數'}), 400

    bank_name = (body.get('bank_name') or '').strip()
    if not bank_name:
        return jsonify({'ok': False, 'error': '請填銀行名稱'}), 400

    last4 = (body.get('last4') or '').strip()
    if not (len(last4) == 4 and last4.isdigit()):
        return jsonify({'ok': False, 'error': '帳號後四碼必須是 4 位數字'}), 400

    session = Session()
    try:
        result = acct_tools.record_deposit(
            session=session,
            deposit_date=deposit_date,
            amount=amount,
            bank_name=bank_name,
            last4=last4,
            user_id=request.line_user_id,
            via='liff',
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("record_deposit failed")
        return jsonify({'ok': False, 'error': f'DB error: {e}'}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    data = result.data
    logger.info(
        f"[LIFF] deposit #{data['payment_id']} amount={data['amount']} "
        f"by {request.line_user_id}"
    )
    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    _push_deposit(target, data)
    return jsonify({'ok': True, **data}), 201


# ---------- JSON API: 週扣款 ----------

@liff_bp.route('/accounting/weekly_payment', methods=['POST'])
@liff_auth_required
def accounting_weekly_payment():
    body = request.get_json(silent=True) or {}
    try:
        amount = int(body.get('amount'))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': '金額必須是正整數'}), 400

    session = Session()
    try:
        result = acct_tools.record_weekly_charge(
            session=session,
            amount=amount,
            user_id=request.line_user_id,
            via='liff',
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("record_weekly_charge failed")
        return jsonify({'ok': False, 'error': f'DB error: {e}'}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    data = result.data
    logger.info(
        f"[LIFF] weekly_charge amount={data['amount']} "
        f"week_end={data['week_end_date']} by {request.line_user_id}"
    )
    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    _push_weekly_charge(target, data)
    return jsonify({'ok': True, **data}), 201


def _push_deposit(target_id, data) -> None:
    if not target_id:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled
        if not push_notify_enabled():
            logger.info("[LIFF] push skipped (PUSH_NOTIFY off)")
            return
        api = get_line_bot_api()
        msg = (
            f"➕ 已記錄入金 NT$ {data['amount']:,}\n"
            f"日期：{data['deposit_date']}\n"
            f"銀行：{data['bank_name']} {data['last4']}"
        )
        api.push_message(PushMessageRequest(
            to=target_id, messages=[TextMessage(text=msg)],
        ))
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push deposit failed: {e} body={body_attr!r}")


def _push_weekly_charge(target_id, data) -> None:
    if not target_id:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled
        if not push_notify_enabled():
            logger.info("[LIFF] push skipped (PUSH_NOTIFY off)")
            return
        api = get_line_bot_api()
        msg = (
            f"💵 已記錄週扣款 NT$ {data['amount']:,}\n"
            f"鎖定時間：{data['occurred_at']}（上週六 23:59）"
        )
        api.push_message(PushMessageRequest(
            to=target_id, messages=[TextMessage(text=msg)],
        ))
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push weekly_charge failed: {e} body={body_attr!r}")
