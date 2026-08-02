"""LIFF 司機自助回報車資 endpoints

Routes
------
GET  /liff/driver/fare          HTML 表單殼（無 auth — 頁面殼）
GET  /liff/driver/fare/state    目前狀態（auth）→ {bound, me, viewing, drivers, trips, week}
POST /liff/driver/fare/bind     綁定「我是誰」（auth）body {driver_id} → 回同 state
POST /liff/driver/fare/submit   逐筆送出車資（auth）→ 回逐筆結果

流程（司機不擅長手機操作，全程只有「點名字」「填數字」「按送出」三步）：
  1. 群組置頂訊息的 LIFF 連結 → 開表單
  2. 第一次開 → 「請問你是哪一位？」點自己 → line_user_id 綁到 drivers
  3. 之後開 → 直接列出「今天要補的車資」＋「本週車資」，填完按送出

管理司機（drivers.is_manager，如老闆 5386）多一層：
  - state 可帶 ?driver_id=N 切換檢視任何一位司機（含已停用的 9999「其他」）
  - submit 可帶 body.driver_id 代填，audit 的 user_name 記「{管理員}代{司機}」
  - **只有管理司機**有這個能力；一般司機傳了 driver_id 一律忽略，用自己的

⚠️ 本 endpoint **不 push、不通知群組** —— 司機在表單內看到逐筆結果即可（省 push 額度）。
⚠️ 車資直接生效（用戶決策）：填錯用既有修改功能改回，audit log 記得到是誰填的。

業務邏輯一律呼叫既有 atomic tools，不重寫：
  現在態 → rewrite.tools.trip.record_fare_current
  過去態 → rewrite.tools.completed_trip.update_completed_trip_fare
  司機/綁定/待補清單 → rewrite.tools.driver

⚠️ blueprint 註冊：本模組要被 import 才會掛上 route。目前在
   modules/__init__.py 的 register_blueprint 前 import（rewrite/handlers/liff/
   __init__.py 有未提交的 WIP，暫不動它）。長期應搬回 __init__.py 那行 import 清單。
"""
import logging
import os

from flask import jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from database import Session
from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required
from rewrite.tools import driver as driver_tools

logger = logging.getLogger(__name__)

# 司機回報的過去態車資，reason 是必填（合規）→ 這裡固定帶司機來源標記，
# 不去問不擅長打字的司機（對齊「過去態才要原因，且問一次為限」的政策）
_DRIVER_REASON = '司機自助回報'
_MAX_DAYS = 14   # 待補清單/白名單的最大回溯天數（測試與補登舊帳都夠用）
_VIA = 'liff_driver'

# 一次送出的上限（單一司機每天 0-3 筆，20 已經很寬鬆；防惡意大 payload）
_MAX_ITEMS = 20


def _to_int_or_none(v):
    if v in (None, '', 'null'):
        return None
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _driver_json(view) -> dict:
    """DriverView → 前端要的最小欄位（不外洩 line_user_id）"""
    return {
        'id': view.id,
        'name': view.name,
        'plate_number': view.plate_number,
        'display_name': view.display_name,
        'is_active': view.is_active,
        'is_bound': view.is_bound,
        'is_manager': view.is_manager,
    }


def _resolve_viewing(session, me, requested_driver_id):
    """決定「這次要看誰的車資」。

    只有管理司機可以指定別人；一般司機傳了 driver_id 一律忽略（不報錯，直接用自己的）
    —— client 端資料不可信，權限判斷全在伺服器這邊做。
    """
    if requested_driver_id is None or requested_driver_id == me.id:
        return me
    if not me.is_manager:
        logger.info(
            f"[LIFF] 非管理司機 #{me.id} 想看 #{requested_driver_id} 的車資 → 忽略，用自己的"
        )
        return me
    got = driver_tools.get_driver_by_id(session=session, driver_id=requested_driver_id)
    if not got.ok or got.data is None:
        logger.info(f"[LIFF] 管理司機 #{me.id} 指定的 #{requested_driver_id} 不存在 → 用自己的")
        return me
    return got.data


def _build_state(session, line_user_id: str, days: int,
                 requested_driver_id=None, week_offset: int = 0) -> dict:
    """組 state payload：綁定了就回待補清單＋本週車資，沒綁就回可選司機清單"""
    bound = driver_tools.get_driver_by_line_user(session=session, line_user_id=line_user_id)
    if not bound.ok:
        return {'ok': False, 'error': bound.error}

    me = bound.data
    if me is None:
        drivers = driver_tools.query_drivers(session=session, active_only=True)
        # 身分選單排除外車代碼（9999「其他」不是人，不該被誰認領）
        return {
            'ok': True,
            'bound': False,
            'me': None,
            'viewing': None,
            'driver': None,
            'drivers': [_driver_json(d) for d in (drivers.data or [])
                        if d.id not in driver_tools.NON_BINDABLE_DRIVER_IDS],
            'drivers_all': [],
            'trips': [],
            'week': None,
            'days': days,
            'week_offset': week_offset,
        }

    viewing = _resolve_viewing(session, me, requested_driver_id)

    pending = driver_tools.query_driver_pending_fares(
        session=session, driver_id=viewing.id, days=days,
    )
    if not pending.ok:
        return {'ok': False, 'error': pending.error}

    week = driver_tools.query_driver_week_fares(
        session=session, driver_id=viewing.id, week_offset=week_offset)
    if not week.ok:
        return {'ok': False, 'error': week.error}

    # 切換選單只有管理司機拿得到（含停用的 9999「其他」）
    drivers_all = []
    if me.is_manager:
        allr = driver_tools.query_drivers(session=session, include_inactive=True)
        drivers_all = [_driver_json(d) for d in (allr.data or [])]

    return {
        'ok': True,
        'bound': True,
        'me': _driver_json(me),
        'viewing': _driver_json(viewing),
        'driver': _driver_json(viewing),   # 向後相容（舊前端讀 driver）
        'drivers': [],
        'drivers_all': drivers_all,
        'week_offset': week_offset,
        'trips': pending.data,
        'week': {
            'items': week.data,
            'by_category': week.meta.get('by_category') or [],
            'start': week.meta.get('week_start'),
            'end': week.meta.get('week_end'),
            'count': week.meta.get('count'),
            'filled_count': week.meta.get('filled_count'),
            'sum_amount': week.meta.get('sum_amount'),
        },
        'days': days,
    }


# ---------- HTML 殼 ----------

@liff_bp.route('/driver/fare', methods=['GET'])
def driver_fare_form():
    """司機回報車資表單殼（無 auth — 頁面 HTML，實際操作走 POST 需 auth）"""
    return render_template(
        'liff/driver_fare_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
    )


# ---------- JSON API ----------

@liff_bp.route('/driver/fare/state', methods=['GET'])
@liff_auth_required
def driver_fare_state():
    """表單載入用：我是誰 + 待補車資 + 本週車資（?days=3 看前 3 天）

    ?driver_id=N 切換檢視對象 —— **只有管理司機有效**，一般司機傳了會被忽略。
    """
    days = _to_int_or_none(request.args.get('days')) or 1
    days = max(1, min(days, _MAX_DAYS))
    week_offset = _to_int_or_none(request.args.get('week')) or 0
    week_offset = 0 if week_offset > 0 else max(week_offset, -4)  # 只往回看，最多 4 週
    want_driver = _to_int_or_none(request.args.get('driver_id'))
    session = Session()
    try:
        state = _build_state(session, request.line_user_id, days, want_driver,
                             week_offset=week_offset)
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("driver_fare_state failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()
    if not state.get('ok'):
        return jsonify(state), 400
    return jsonify(state)


@liff_bp.route('/driver/fare/bind', methods=['POST'])
@liff_auth_required
def driver_fare_bind():
    """「請問你是哪一位？」點名字 → 綁定，回同 state（前端直接換畫面）"""
    body = request.get_json(silent=True) or {}
    driver_id = _to_int_or_none(body.get('driver_id'))
    if driver_id is None:
        return jsonify({'ok': False, 'error': '請選一位司機'}), 400
    days = _to_int_or_none(body.get('days')) or 1
    days = max(1, min(days, _MAX_DAYS))

    session = Session()
    try:
        result = driver_tools.bind_driver_line_user(
            session=session, driver_id=driver_id,
            line_user_id=request.line_user_id,
            user_id=request.line_user_id, user_name=request.line_user_name,
            via=_VIA,
        )
        if not result.ok:
            return jsonify({'ok': False, 'error': result.error}), 400
        state = _build_state(session, request.line_user_id, days)
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception(f"driver_fare_bind driver_id={driver_id} failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    logger.info(f"[LIFF] driver #{driver_id} 綁定 LINE 帳號 {request.line_user_id[:8]}")
    if not state.get('ok'):
        return jsonify(state), 400
    return jsonify(state)


@liff_bp.route('/driver/fare/submit', methods=['POST'])
@liff_auth_required
def driver_fare_submit():
    """逐筆寫車資。

    payload: {items: [{source:'trip'|'completed', id, meter_fare, extra_fare}],
              driver_id?（管理司機代填用，一般司機傳了會被忽略）, days?}
    回:      {ok: True, results: [{ok, id, source, error?}], ...}

    ⚠️ 不 push、不通知群組（司機在表單內看到結果即可）。
    每筆獨立 commit（atomic tool 預設 auto_commit=True）→ 一筆失敗不影響其他筆。
    """
    body = request.get_json(silent=True) or {}
    items = body.get('items')
    if not isinstance(items, list) or not items:
        return jsonify({'ok': False, 'error': '沒有要送出的車資'}), 400
    if len(items) > _MAX_ITEMS:
        return jsonify({'ok': False, 'error': f'一次最多送 {_MAX_ITEMS} 筆'}), 400
    want_driver = _to_int_or_none(body.get('driver_id'))

    from rewrite.tools.completed_trip import update_completed_trip_fare
    from rewrite.tools.trip import record_fare_current

    session = Session()
    results = []
    audit_name = None
    try:
        bound = driver_tools.get_driver_by_line_user(
            session=session, line_user_id=request.line_user_id,
        )
        me = bound.data if bound.ok else None
        if me is None:
            return jsonify({'ok': False, 'error': '尚未綁定司機，請重新開啟表單選擇你的名字'}), 400

        # 車資要寫到誰頭上：管理司機可代填，其他人一律自己（權限判斷在伺服器端）
        target = _resolve_viewing(session, me, want_driver)
        on_behalf = target.id != me.id
        # audit 的 modified_by 看得出是代填
        audit_name = f"{me.name}代{target.name}" if on_behalf else me.name

        # 待補清單快照（送出當下重算，作為唯一可寫入的白名單）
        _pending_keys = set()
        try:
            _pr = driver_tools.query_driver_pending_fares(
                session=session, driver_id=target.id, days=_MAX_DAYS)
            if _pr.ok:
                _pending_keys = {(it['source'], it['id']) for it in _pr.data}
        except Exception:
            logger.warning('[driver_fare] 待補清單快照失敗', exc_info=True)

        for raw in items:
            if not isinstance(raw, dict):
                results.append({'ok': False, 'id': None, 'source': None, 'error': '格式錯誤'})
                continue
            source = (raw.get('source') or '').strip()
            rec_id = _to_int_or_none(raw.get('id'))
            meter = _to_int_or_none(raw.get('meter_fare'))
            extra = _to_int_or_none(raw.get('extra_fare'))
            base = {'id': rec_id, 'source': source}

            if rec_id is None:
                results.append({**base, 'ok': False, 'error': '缺班次編號'})
                continue
            if meter is None and extra is None:
                results.append({**base, 'ok': False, 'error': '請填車資'})
                continue

            owns = driver_tools.check_driver_owns_record(
                session=session, driver_id=target.id, source=source, record_id=rec_id,
                acting_driver=me,
            )
            if not owns.ok:
                results.append({**base, 'ok': False, 'error': owns.error})
                continue

            # 只接受「送出當下仍在待補清單」的班次 — 同時擋掉兩件事：
            #  (a) 排程 race：司機開表單時是 trip，送出前 +5 分鐘排程已把它複製進
            #      completed_trips（快照當下的 NULL 車資）→ 寫 trips 會靜默無效
            #  (b) 竄改舊資料：手動組 payload 改半年前已結算的班次（實測可行）
            if (source, rec_id) not in _pending_keys:
                results.append({**base, 'ok': False,
                                'error': '這筆已不在待補清單（可能剛入庫或已填過），請重新整理'})
                continue

            try:
                if source == 'trip':
                    r = record_fare_current(
                        session=session, trip_id=rec_id,
                        meter_fare=meter, extra_fare=extra,
                        user_id=request.line_user_id, user_name=audit_name,
                        via=_VIA,
                    )
                else:
                    r = update_completed_trip_fare(
                        session=session, completed_trip_id=rec_id,
                        meter_fare=meter, extra_fare=extra,
                        reason=_DRIVER_REASON,
                        user_id=request.line_user_id, user_name=audit_name,
                        via=_VIA,
                    )
            except SQLAlchemyError as e:
                session.rollback()
                logger.exception(f"driver_fare_submit {source} #{rec_id} failed")
                results.append({**base, 'ok': False, 'error': f'寫入失敗：{e}'})
                continue

            results.append({**base, 'ok': bool(r.ok), 'error': None if r.ok else r.error})
    finally:
        session.close()

    ok_n = sum(1 for r in results if r['ok'])
    logger.info(
        f"[LIFF] driver fare submit by {request.line_user_id[:8]} "
        f"({audit_name or '?'}) ok={ok_n}/{len(results)} (0 push)"
    )
    return jsonify({'ok': True, 'results': results, 'ok_count': ok_n})
