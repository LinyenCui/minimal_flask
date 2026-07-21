"""LIFF 客戶 CRUD endpoints (Phase B)

Routes
------
GET  /liff/customer/form           HTML 新增表單（無 auth — 頁面殼）
GET  /liff/customer/<id>/form      HTML 編輯表單殼
GET  /liff/customer/<id>           JSON 客戶資料供前端 prefill（auth required）
POST /liff/customer                新增（auth required；支援多筆 {customers:[...]}，
                                   同時相容舊單筆 body — LINE 端頁面可能有快取）
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
             'remarks', 'gender', 'medical_record_no', 'dm_care_no'):
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


# 一次新增上限（防呆；正常表單一次頂多幾位）
_BATCH_MAX = 20


def _extract_customer_items(body: dict) -> tuple[list[dict], bool, str | None]:
    """解析 POST /liff/customer 的 body → (items, is_batch, err)

    兩種格式：
      1. 新版多筆：{'customers': [{...}, {...}], 'source': {...}}
      2. 舊版單筆：直接就是欄位 dict（LINE 端頁面可能快取舊表單，必須相容）

    純函數（不碰 Flask / DB），方便單元測試。
    """
    if 'customers' in body:
        raw = body.get('customers')
        if not isinstance(raw, list) or not raw:
            return [], True, "customers 必須是至少一筆的清單"
        if not all(isinstance(item, dict) for item in raw):
            return [], True, "customers 每一筆必須是物件"
        if len(raw) > _BATCH_MAX:
            return [], True, f"一次最多新增 {_BATCH_MAX} 位客戶，請分批送出"
        return list(raw), True, None
    return [body], False, None


def _item_label(item: dict, idx: int) -> str:
    """逐筆結果顯示用的名字：簡稱 → 姓名 → 第 N 位（純函數）"""
    for k in ('short_name', 'name'):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return f"第 {idx + 1} 位"


def _serve_form(customer_id: int | None):
    return render_template(
        'liff/customer_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        customer_id=customer_id,
    )


def _customer_chat_text(view, action_label: str) -> str:
    """單筆成功的聊天室文字（chat_text 協議 — push text+Flex 的純文字等價版）"""
    display = view.short_name or view.name or f'#{view.id}'
    lines = [f"✅ 已{action_label}客戶 #{view.id} {display}"]
    if view.name and view.name != display:
        lines.append(f"姓名：{view.name}")
    if view.address:
        lines.append(f"地址：{view.address}")
    if view.category:
        lines.append(f"類別：{view.category}")
    if view.contact_phone:
        lines.append(f"電話：{view.contact_phone}")
    return '\n'.join(lines)


def _customer_batch_chat_text(created_views: list, failures: list) -> str | None:
    """多筆新增的彙總文字。沒有任何成功回 None（失敗表單頁上已逐筆顯示）。"""
    if not created_views:
        return None
    lines = [f"✅ 已新增 {len(created_views)} 位客戶"]
    for v in created_views:
        display = v.short_name or v.name or ''
        lines.append(f"　#{v.id} {display}".rstrip())
    if failures:
        lines.append(f"❌ {len(failures)} 位新增失敗")
        for label, err in failures:
            lines.append(f"　{label}：{err}")
    return '\n'.join(lines)


def _push_customer(target_id: str | None, view, action_label: str, source=None) -> None:
    """存完 push 一則 text + 客戶詳情 Flex 到指定目標（群組 / 聊天室 / 個人）。

    target_id 是 LINE Messaging API 認的 33 字元 ID（C/R/U + 32 hex）。
    source 傳了，bubble 的「編輯」按鈕 LIFF URL 才會帶 gid/rid，
    使用者點編輯改完 push 才會回到原群組（不是退回操作者私聊）。
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
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled
        from rewrite.views.customer_flex import render_customer_detail

        if not push_notify_enabled():
            logger.info("[LIFF] push skipped (PUSH_NOTIFY off)")
            return
        api = get_line_bot_api()
        display = view.short_name or view.name or f'#{view.id}'
        text_msg = TextMessage(text=f"✅ 已{action_label}客戶 #{view.id} {display}")
        flex_dict = render_customer_detail(view, event_source=source)
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


def _push_customer_batch(target_id: str | None, created_views: list, failures: list) -> None:
    """多筆新增完成後推「一則」彙總 text 到來源聊天室。

    比照 booking.py 的 batch_notify 整合推播：把「N 筆 = N 則 push」降為
    「N 筆 = 1 則」，省 LINE 免費月額度（200 則/月）。

    Args:
        created_views: 成功建立的 CustomerView 列表
        failures: [(label, error), ...] 失敗清單（簡稱＋原因）

    沒有任何成功就不推 — 失敗原因表單頁上已逐筆顯示，推到群組只是干擾
    （比照 booking：只彙總已成功建立的）。失敗只 log warning，不 raise。
    """
    if not target_id or not created_views:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled

        if not push_notify_enabled():
            logger.info("[LIFF] customer batch push skipped (PUSH_NOTIFY off)")
            return

        text = _customer_batch_chat_text(created_views, failures)

        api = get_line_bot_api()
        api.push_message(PushMessageRequest(
            to=target_id, messages=[TextMessage(text=text)],
        ))
        logger.info(
            f"[LIFF] customer batch push n={len(created_views)} → {target_id[:8]} (1 push)"
        )
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] customer batch push failed: {e} body={body_attr!r}")


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
        'drug_dx_link': '/liff/drug_diagnosis_links/form',
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
    # 動態目標：trip_status（單筆班次狀態管理 LIFF）
    trip_id_raw = request.args.get('trip_id')
    if form_kind == 'trip_status' and trip_id_raw:
        try:
            tid = int(trip_id_raw)
            qs = request.query_string.decode('utf-8')
            target = f'/liff/trip/{tid}/status_form'
            return redirect(f"{target}?{qs}" if qs else target, code=302)
        except ValueError:
            pass
    # 動態目標：batch_trip_status（批次班次狀態管理 LIFF，trip_ids=CSV）
    if form_kind == 'batch_trip_status':
        qs = request.query_string.decode('utf-8')
        target = '/liff/trips/batch_status_form'
        return redirect(f"{target}?{qs}" if qs else target, code=302)
    # 動態目標：ocr_import_review（OCR 匯入批次審核 LIFF，run_id=...）
    if form_kind == 'ocr_import_review':
        qs = request.query_string.decode('utf-8')
        target = '/liff/ocr-import/review'
        return redirect(f"{target}?{qs}" if qs else target, code=302)

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
    items, is_batch, err = _extract_customer_items(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    if not is_batch:
        # 舊單筆格式（LINE 端頁面可能快取舊表單）— 行為完全不變
        return _customer_create_single(body)
    return _customer_create_batch(items, body)


def _customer_create_single(body: dict):
    """舊單筆路徑：回應格式 / 推播（text + Flex 詳情）都維持原樣。"""
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
    resp = {'ok': True, 'customer': customer_data}
    # chat_text 協議：前端可 sendMessages → 不 push，回 chat_text（免額度）
    if bool(body.get('client_can_send')):
        resp['chat_text'] = _customer_chat_text(result.data, '新增')
    else:
        # 決定 push 目標：群組觸發 → 群組；私聊 → 個人
        # source 也傳進去 — bubble 上的「編輯」按鈕才會帶 gid 讓編輯後 push 回群組
        from rewrite.utils.liff_url import resolve_push_target
        source = body.get('source')
        target = resolve_push_target(source, request.line_user_id)
        _push_customer(target, result.data, '新增', source=source)
    return jsonify(resp), 201


def _customer_create_batch(items: list[dict], body: dict):
    """多筆新增：逐筆獨立 create（各自 commit，比照 booking 連續預約 —
    一筆失敗不影響其他筆），全部處理完只推「一則」整合推播。

    回應 JSON 含逐筆結果（results），讓表單頁能顯示成功打勾 / 失敗原因。
    """
    results: list[dict] = []
    created_views: list = []
    failures: list[tuple[str, str]] = []

    session = Session()
    try:
        for idx, item in enumerate(items):
            label = _item_label(item, idx)
            fields, perr = _parse_payload(item)
            if perr:
                results.append({'ok': False, 'label': label, 'error': perr})
                failures.append((label, perr))
                continue
            try:
                result = customer_tools.create_customer(session=session, **fields)
            except SQLAlchemyError as e:
                session.rollback()
                logger.exception("create_customer failed (batch)")
                results.append({'ok': False, 'label': label, 'error': f"DB error: {e}"})
                failures.append((label, f"DB error: {e}"))
                continue
            if result.ok:
                created_views.append(result.data)
                results.append({
                    'ok': True, 'label': label,
                    'customer': _customer_to_jsonable(result.data),
                })
            else:
                results.append({'ok': False, 'label': label, 'error': result.error})
                failures.append((label, result.error))
    finally:
        session.close()

    n_created = len(created_views)
    logger.info(
        f"[LIFF] customer batch by {request.line_user_id}: "
        f"created={n_created} failed={len(failures)}"
    )

    resp = {
        'ok': True,
        'results': results,
        'created': n_created,
        'failed': len(failures),
    }
    # chat_text 協議：前端可 sendMessages → 不 push，回 chat_text（免額度）
    if bool(body.get('client_can_send')):
        if n_created == 1 and not failures:
            resp['chat_text'] = _customer_chat_text(created_views[0], '新增')
        else:
            chat_text = _customer_batch_chat_text(created_views, failures)
            if chat_text:
                resp['chat_text'] = chat_text
    else:
        from rewrite.utils.liff_url import resolve_push_target
        source = body.get('source')
        target = resolve_push_target(source, request.line_user_id)
        if n_created == 1 and not failures:
            # 一位全成功 → 沿用單筆推播（text + 客戶詳情 Flex，含編輯按鈕）
            _push_customer(target, created_views[0], '新增', source=source)
        else:
            _push_customer_batch(target, created_views, failures)

    status = 201 if n_created and not failures else 200
    return jsonify(resp), status


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
    resp = {'ok': True, 'customer': customer_data}
    # chat_text 協議：前端可 sendMessages → 不 push，回 chat_text（免額度）
    if bool(body.get('client_can_send')):
        resp['chat_text'] = _customer_chat_text(result.data, '更新')
    else:
        from rewrite.utils.liff_url import resolve_push_target
        source = body.get('source')
        target = resolve_push_target(source, request.line_user_id)
        _push_customer(target, result.data, '更新', source=source)
    return jsonify(resp)
