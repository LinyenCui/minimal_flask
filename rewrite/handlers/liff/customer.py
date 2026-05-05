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

from flask import jsonify, render_template, request
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
    """form payload → atomic tool kwargs（空字串轉 None、birthday 轉 date）"""
    fields: dict[str, Any] = {}
    for k in ('name', 'short_name', 'address', 'category', 'contact_phone',
             'remarks', 'gender', 'national_id', 'medical_record_no', 'insurance_type'):
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


# ---------- HTML 殼 ----------

@liff_bp.route('/customer/form', methods=['GET'])
def customer_form_new():
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
    return jsonify({'ok': True, 'customer': customer_data})
