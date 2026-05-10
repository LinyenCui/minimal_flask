"""LIFF 客戶 CRUD endpoints (Phase B)

Routes
------
GET  /liff/customer/form           HTML 新增表單（無 auth — 頁面殼）
GET  /liff/customer/<id>/form      HTML 編輯表單殼
GET  /liff/customer/<id>           JSON 客戶資料供前端 prefill（auth required）
POST /liff/customer                新增（auth required）
POST /liff/customer/<id>           更新（auth required）

業務邏輯一律呼叫 rewrite.tools.customer 的 atomic tools，不重做。
"""
import logging
import os
from datetime import date, datetime
from typing import Any

from flask import jsonify, redirect, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from database import Session
from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required
from rewrite.tools import customer as customer_tools

logger = logging.getLogger(__name__)


# ---------- helpers ----------

def _customer_to_jsonable(view) -> dict:
    """CustomerView → JSON-safe dict（date / datetime → ISO string）"""
    d = view.to_dict() if hasattr(view, 'to_dict') else dict(view)
    for k in ('birthday', 'created_at', 'updated_at'):
        v = d.get(k)
        if isinstance(v, (date, datetime)):
            d[k] = v.isoformat()
    return d


def _parse_payload(body: dict) -> tuple[dict, str | None]:
    """form payload → atomic tool kwargs（空字串轉 None、birthday 轉 date）

    ⚠️ 2026-05-08 drop: national_id / insurance_type 已移除；舊 payload 送
    這兩個 key 也不會破（_parse_payload 只挑現有欄位，atomic tool 也吞）
    """
    fields: dict[str, Any] = {}
    for k in ('name', 'short_name', 'address', 'category', 'contact_phone',
             'remarks', 'gender', 'medical_record_no'):
        v = body.get(k)
        if v == '' or v is None:
            v = None
        elif isinstance(v, str):
            v = v.strip() or None
        fields[k] = v

    bd_raw = body.get('birthday')
    if bd_raw:
        try:
            fields['birthday'] = date.fromisoformat(bd_raw)
        except ValueError:
            return {}, f"birthday 格式錯誤（要 YYYY-MM-DD）: {bd_raw!r}"
    else:
        fields['birthday'] = None
    return fields, None


def _serve_form(customer_id: int | None):
    return render_template(
        'liff/customer_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        customer_id=customer_id,
    )


def _push_customer(target_id: str | None, view, action_label: str) -> None:
    """存完 push 一則 text + 客戶詳情 Flex 到指定目標（群組 / 聊天室 / 個人）。

    target_id 是 LINE Messaging API 認的 33 字元 ID（C/R/U + 32 hex）。
    失敗只 log warning，不 raise — push 不該擋住 LIFF 回應。
    """
    if not target_id:
        return
    try:
        from linebot.v3.messaging import (
            FlexContainer,
            FlexMessage,
            PushMessageRequest,
            TextMessage,
        )
        from modules.utils.line_bot import get_line_bot_api
        from rewrite.views.customer_flex import render_customer_detail

        api = get_line_bot_api()
        display = view.short_name or view.name or f'#{view.id}'
        text_msg = TextMessage(text=f"✅ 已{action_label}客戶 #{view.id} {display}")
        flex_dict = render_customer_detail(view)
        flex_msg = FlexMessage(
            alt_text=f"客戶詳情 #{view.id}",
            contents=FlexContainer.from_dict(flex_dict),
        )
        api.push_message(PushMessageRequest(
            to=target_id,
            messages=[text_msg, flex_msg],
        ))
        logger.info(f"[LIFF] pushed customer #{view.id} ({action_label}) to {target_id[:8]}")
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push customer detail failed: {e} body={body_attr!r}")


# ---------- HTML 殼 ----------

@liff_bp.route('/customer/form', methods=['GET'])
def customer_form_new():
    """LIFF 入口頁（dispatcher）

    LINE Console 設的 endpoint URL 寫死 /liff/customer/form，所以這裡承擔 dispatch 角色：
      - ?form=booking → redirect 到 booking 表單
      - ?form=customer 或無 → 維持新增客戶表單（既有行為）

    這樣多種表單共用同一個 LIFF App / LIFF_ID，不用每加表單就去 Console 開新 App。
    """
    form_kind = (request.args.get('form') or 'customer').strip().lower()
    redirect_targets = {
        'booking': '/liff/booking/form',
        'import': '/liff/import/form',
        'new_schedule': '/liff/fixed_schedule/form',
        'report': '/liff/report/form',
        'deposit': '/liff/accounting/deposit_form',
        'weekly_payment': '/liff/accounting/weekly_payment_form',
        'batch_allowance': '/liff/batch_allowance/form',
    }
    # 動態目標（含 ID）：edit_schedule / leave_schedule
    sched_id = request.args.get('id')
    if form_kind == 'edit_schedule' and sched_id:
        try:
            sid = int(sched_id)
            qs = request.query_string.decode('utf-8')
            target = f'/liff/fixed_schedule/{sid}/form'
            return redirect(f"{target}?{qs}" if qs else target, code=302)
        except ValueError:
            pass
    if form_kind == 'leave_schedule' and sched_id:
        try:
            sid = int(sched_id)
            qs = request.query_string.decode('utf-8')
            target = f'/liff/fixed_schedule/{sid}/leave_form'
            return redirect(f"{target}?{qs}" if qs else target, code=302)
        except ValueError:
            pass

    if form_kind in redirect_targets:
        # 把其他 query string 一起轉過去（保留 liff.state、未來其他參數）
        qs = request.query_string.decode('utf-8')
        target = redirect_targets[form_kind]
        if qs:
            target = f"{target}?{qs}"
        return redirect(target, code=302)
    return _serve_form(customer_id=None)


@liff_bp.route('/customer/<int:customer_id>/form', methods=['GET'])
def customer_form_edit(customer_id):
    return _serve_form(customer_id=customer_id)


# ---------- JSON API ----------

@liff_bp.route('/customer/<int:customer_id>', methods=['GET'])
@liff_auth_required
def customer_get(customer_id):
    """編輯模式 prefill 用（unmasked，因為使用者要編輯整串）"""
    session = Session()
    try:
        result = customer_tools.get_customer_by_id(
            customer_id, session=session, mask_id=False
        )
    finally:
        session.close()
    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 404
    return jsonify({'ok': True, 'customer': _customer_to_jsonable(result.data)})


@liff_bp.route('/customer', methods=['POST'])
@liff_auth_required
def customer_create():
    body = request.get_json(silent=True) or {}
    fields, err = _parse_payload(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    session = Session()
    try:
        result = customer_tools.create_customer(session=session, **fields)
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("create_customer failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    customer_data = _customer_to_jsonable(result.data)
    logger.info(f"[LIFF] customer #{customer_data.get('id')} created by {request.line_user_id}")
    # 決定 push 目標：群組觸發 → 群組；私聊 → 個人
    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    _push_customer(target, result.data, '新增')
    return jsonify({'ok': True, 'customer': customer_data}), 201


@liff_bp.route('/customer/<int:customer_id>', methods=['POST'])
@liff_auth_required
def customer_update(customer_id):
    body = request.get_json(silent=True) or {}
    fields, err = _parse_payload(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    session = Session()
    try:
        result = customer_tools.update_customer(
            session=session,
            customer_id=customer_id,
            **fields,
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("update_customer failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    customer_data = _customer_to_jsonable(result.data)
    logger.info(f"[LIFF] customer #{customer_id} updated by {request.line_user_id}")
    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    _push_customer(target, result.data, '更新')
    return jsonify({'ok': True, 'customer': customer_data})
