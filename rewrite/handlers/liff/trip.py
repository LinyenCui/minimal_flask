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
from rewrite.tools.leave_guard import NEEDS_CONFIRM_KEY
from rewrite.handlers.liff.auth import liff_auth_required
from rewrite.tools import trip as trip_tools

logger = logging.getLogger(__name__)


VALID_ACTIONS = ('leave', 'cancel', 'conflict', 'restore',
                 'assign', 'unassign')

_ACTION_VERB = {
    'leave':    '🏷️ 已請假',
    'cancel':   '🚫 已註銷',
    'conflict': '⚠️ 已標記衝突',
    'restore':  '🔄 已改回準備',
    'assign':   '🚕 已指派司機',
    'unassign': '↩️ 已撤銷指派',
}

_WEEKDAY_TC = ['一', '二', '三', '四', '五', '六', '日']


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


@liff_bp.route('/trips/batch_status_form', methods=['GET'])
def trip_batch_status_form():
    """批次班次狀態管理表單殼（無 auth — 頁面 HTML）。

    用 URL query `trip_ids=2534,2543` 帶入要批次操作的班次清單。
    前端載入時用單一 GET `/liff/trips/batch?ids=...` 一次撈全部（Alternative A,
    避開 iOS WebView 多 fetch bug），送出時迴圈 POST `/liff/trip/<id>/status`
    （每筆獨立 audit / 失敗逐筆顯示）。
    """
    return render_template(
        'liff/trip_batch_status_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        trip_ids_csv=(request.args.get('trip_ids') or '').strip(),
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


@liff_bp.route('/trips/batch', methods=['GET'])
@liff_auth_required
def trips_batch_get():
    """JSON prefill（批次）— 一次回傳多筆班次狀態。

    Alternative A：批次表單只打這一支,避開 iOS LIFF WebView 對同頁多次
    fetch() 不穩的 bug（實測 Promise.all 與 sequential 都會在 client 端掉、
    server 連 GET 都收不到）。
    query: ids=2534,2543
    回: {ok: True, trips: [{id, ok, trip|error}, ...]}（逐筆標 ok/error,整體恆 ok）
    """
    ids_csv = (request.args.get('ids') or '').strip()
    ids = []
    for part in ids_csv.split(','):
        n = _to_int_or_none(part.strip())
        if n is not None:
            ids.append(n)
    if not ids:
        return jsonify({'ok': False, 'error': 'ids 為空或格式錯'}), 400

    results = []
    drivers = []
    session = Session()
    try:
        # 司機清單搭這支一起回 —— 不能另外開一次 fetch（同頁多次 fetch 在
        # iOS LIFF WebView 會掉，就是本 endpoint 存在的原因）
        try:
            from rewrite.tools import driver as driver_tools
            dr = driver_tools.query_drivers(session=session, active_only=True)
            drivers = [{'id': d.id, 'name': d.name or '',
                        'display_name': getattr(d, 'display_name', None) or str(d.id)}
                       for d in (dr.data or [])]
        except Exception:
            logger.exception('trips_batch_get: 撈司機清單失敗（不影響班次載入）')

        for tid in ids:
            r = trip_tools.query_trip_by_id(tid, session=session)
            if r.ok:
                results.append({'id': tid, 'ok': True, 'trip': _trip_to_jsonable(r.data)})
            else:
                results.append({'id': tid, 'ok': False, 'error': r.error})
    finally:
        session.close()
    return jsonify({'ok': True, 'trips': results, 'drivers': drivers})


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
    # 批次模式:前端逐筆 POST 帶 suppress_push=true,各筆不推;全部做完由前端
    # 呼叫 /trips/batch_status_notify 收尾推「一則彙總」,把「N 筆 = N 則 push
    # (N 個 LINE 額度)」降為「N 筆 = 1 則」(429 monthly limit 主止血點)。
    suppress_push = bool(body.get('suppress_push'))

    session = Session()
    try:
        if action == 'leave':
            if not reason:
                return jsonify({'ok': False, 'error': '請假必須填原因'}), 400
            # surcharge 保持 None（不再靜默補 0）——閘門要分得出「未填」與「填 0」
            result = trip_tools.passenger_leave(
                session=session, trip_id=trip_id,
                reason=reason, surcharge=surcharge,
                user_id=request.line_user_id, via='liff',
                confirm_zero_surcharge=bool(body.get('confirm_zero_surcharge')),
            )
        elif action == 'assign':
            # 指派不受 30 分鐘鎖限制（atomic tool 是 allow_in_lock=True）——
            # 快到點了才更需要能派車
            did = _to_int_or_none(body.get('driver_id'))
            if did is None:
                return jsonify({'ok': False, 'error': '請選司機'}), 400
            result = trip_tools.assign_driver(
                session=session, trip_id=trip_id, driver_id=did,
                user_id=request.line_user_id, via='liff',
            )
        elif action == 'unassign':
            result = trip_tools.unassign_driver(
                session=session, trip_id=trip_id,
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
        # 「請假但 0 元」不是錯誤，是要用戶再確認一次 —— 前端靠這個旗標
        # 跳確認框，按確定後帶 confirm_zero_surcharge 重送
        return jsonify({
            'ok': False,
            'error': result.error,
            NEEDS_CONFIRM_KEY: bool(result.meta.get(NEEDS_CONFIRM_KEY)),
        }), 400

    trip_data = _trip_to_jsonable(result.data)
    logger.info(
        f"[LIFF] trip #{trip_id} action={action} "
        f"reason={reason!r} surcharge={surcharge} by {request.line_user_id}"
    )
    resp = {'ok': True, 'trip': trip_data}
    if not suppress_push:
        from rewrite.handlers.liff.chat_notify import notify_or_chat_text
        from rewrite.utils.liff_url import resolve_push_target
        target = resolve_push_target(body.get('source'), request.line_user_id)
        chat_text = notify_or_chat_text(
            client_can_send=bool(body.get('client_can_send')),
            target_id=target,
            text=_trip_status_chat_text(result.data, action, reason, surcharge),
            label=f'trip status #{trip_id} ({action})',
        )
        if chat_text:
            resp['chat_text'] = chat_text
    return jsonify(resp)


# ---------- 結果通知文字（chat_text 協議；push fallback 同文案） ----------

def _trip_status_chat_text(view, action, reason, surcharge) -> str:
    """執行後回聊天室的精簡 text。

    刻意不附 Flex 詳情卡——使用者剛在 LIFF 內看過該班次資訊,結果再丟一張
    一模一樣的 Flex 出來只會洗版。簡潔通知 + emoji 前綴即可。
    若使用者要查最新狀態,自己打 /dx N 或點 quick reply。
    """
    verb = _ACTION_VERB.get(action, action)
    sp, _, ep = view.display_route()
    route = f"{sp or '?'} → {ep or '?'}"
    if view.date:
        wd = _WEEKDAY_TC[view.date.weekday()]
        date_str = f"{view.date.month}/{view.date.day}({wd})"
    else:
        date_str = '?'
    time_str = str(view.time)[:5] if view.time else '?'

    lines = [
        f"{verb} 班次 #{view.trip_id}",
        f"📅 {date_str} {time_str}",
        f"📍 {route}",
    ]
    if action in ('assign', 'unassign'):
        # 指派類不影響金額，不印車資行；派給誰由 view 的 driver_id 顯示
        if view.driver_id:
            lines.append(f"🚕 司機 #{view.driver_id}")
    if action == 'leave':
        lines.append(f"📝 {reason}")
        # ⚠️ 曾經寫 `if surcharge:` —— 0 是 falsy，害「請假 0 元」的通知連金額
        #    那行都不出現，操作者收到一則看起來完全正常的訊息（用戶回報的根因）
        if surcharge is None or surcharge == 0:
            lines.append("💰 0 元（未扣款）")
        else:
            lines.append(f"💰 {surcharge:+d} 元")
    elif action in ('cancel', 'conflict') and reason:
        lines.append(f"📝 {reason}")
    if action in ('cancel', 'conflict'):
        lines.append("↩️ 可用「改回準備」還原")
    return '\n'.join(lines)


# ---------- POST: 批次收尾彙總 push（措施 1:N 筆 → 1 則） ----------

@liff_bp.route('/trips/batch_status_notify', methods=['POST'])
@liff_auth_required
def trips_batch_status_notify():
    """批次狀態管理收尾:把 N 筆結果彙總成「一則」push 回群組。

    前端逐筆 POST /trip/<id>/status 帶 suppress_push=true(各筆不推),全部
    做完呼叫本 endpoint 推一則彙總 → 把「N 筆 = N 則 push」降為「N 筆 = 1 則」,
    這是 429 monthly limit 的主要止血點。

    payload: { action, results:[{trip_id, ok}], reason?, surcharge?,
               source?:{type,groupId/roomId} }
    """
    body = request.get_json(silent=True) or {}
    action = (body.get('action') or '').strip().lower()
    results = body.get('results') or []
    if action not in VALID_ACTIONS or not isinstance(results, list):
        return jsonify({'ok': False, 'error': 'action/results 格式錯'}), 400

    ok_ids = [r.get('trip_id') for r in results if isinstance(r, dict) and r.get('ok')]
    fail_n = sum(1 for r in results if isinstance(r, dict) and not r.get('ok'))
    if not ok_ids:
        return jsonify({'ok': True, 'skipped': 'no success'})

    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    if not target:
        return jsonify({'ok': True, 'skipped': 'no target'})

    reason = (body.get('reason') or '').strip()
    surcharge = _to_int_or_none(body.get('surcharge'))
    text = _batch_status_text(action, ok_ids, fail_n, reason, surcharge,
                              driver_id=_to_int_or_none(body.get('driver_id')))

    # chat_text 協議：前端可 sendMessages → 不 push，回 chat_text（免額度）
    if bool(body.get('client_can_send')):
        logger.info(
            f"[LIFF] batch status notify ({action}) ok={len(ok_ids)} "
            f"fail={fail_n} → chat_text (0 push)"
        )
        return jsonify({'ok': True, 'chat_text': text})

    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled

        if not push_notify_enabled():
            logger.info("[LIFF] batch status notify skipped (PUSH_NOTIFY off)")
            return jsonify({'ok': True, 'skipped': 'push off'})

        api = get_line_bot_api()
        api.push_message(PushMessageRequest(
            to=target, messages=[TextMessage(text=text)],
        ))
        from modules.utils.push_stats import record_push
        record_push('batch_status', target_id=target)
        logger.info(
            f"[LIFF] batch status notify ({action}) ok={len(ok_ids)} "
            f"fail={fail_n} → {target[:8]} (1 push)"
        )
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] batch status notify failed: {e} body={body_attr!r}")
    return jsonify({'ok': True})


def _batch_status_text(action, ok_ids, fail_n, reason, surcharge,
                       driver_id=None) -> str:
    """批次狀態變更收尾的彙總文字（chat_text 協議；push fallback 同文案）"""
    verb = _ACTION_VERB.get(action, action)
    lines = [f"{verb} 共 {len(ok_ids)} 筆"]
    lines.append("　" + "、".join(f"#{i}" for i in ok_ids))
    if action == 'assign' and driver_id:
        lines.append(f"🚕 指派給司機 #{driver_id}")
    if action == 'leave' and reason:
        # 跟單筆版同一個根因：`if surcharge` 的 0 是 falsy，
        # 會讓 0 元批次請假的彙總看起來跟正常扣款一模一樣
        amt = ("　💰 0 元（未扣款）" if (surcharge is None or surcharge == 0)
               else f"　💰 {surcharge:+d} 元")
        lines.append(f"📝 {reason}{amt}")
    elif action in ('cancel', 'conflict') and reason:
        lines.append(f"📝 {reason}")
    if action in ('cancel', 'conflict'):
        lines.append("↩️ 可用「改回準備」還原")
    if fail_n:
        lines.append(f"⚠️ {fail_n} 筆未成功(詳見表單)")
    return '\n'.join(lines)
