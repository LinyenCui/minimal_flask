"""LIFF 匯入固定班次 endpoints

Routes
------
GET  /liff/import/form      HTML 匯入表單殼
POST /liff/import/preview   預覽（不寫入 DB），給前端顯示衝突 / 將匯入筆數
POST /liff/import           執行匯入（auth required）

業務邏輯一律呼叫 rewrite.tools.import_fixed.{preview_import_fixed,import_fixed_to_trips}。
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
from rewrite.tools import import_fixed as import_tools

logger = logging.getLogger(__name__)


def _to_jsonable(d: dict) -> dict:
    """date → ISO string for JSON 回傳"""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _parse_payload(body: dict) -> tuple[int, str, bool, bool, str | None]:
    """(week_offset, category, overwrite, purge_past, err)"""
    try:
        week_offset = int(body.get('week_offset', 0))
    except (TypeError, ValueError):
        return 0, '', False, False, "week_offset 必須是整數"
    if week_offset < 0:
        return 0, '', False, False, "week_offset 不可為負（不允許匯入過去週次）"

    category = (body.get('category') or '').strip()
    if not category:
        return 0, '', False, False, "請選類別"

    overwrite = bool(body.get('overwrite'))
    purge_past = bool(body.get('purge_past'))
    return week_offset, category, overwrite, purge_past, None


# ---------- HTML 殼 ----------

@liff_bp.route('/import/form', methods=['GET'])
def import_form():
    # 算 dropdown 選項，每個帶太陽週號（W18 / W19 ...）
    # 一週內值不變，render-time 計算一次塞進 template 即可
    from datetime import date as _date
    from modules.utils.week_utils import calculate_target_week
    from rewrite.tools.import_fixed import sun_week_number

    today = _date.today()
    week_options = []
    for offset, label in [(0, '本週'), (1, '下週'), (2, '下下週'), (3, '+3 週')]:
        week_start, _dates, week_desc = calculate_target_week(today, offset)
        wn = sun_week_number(week_start)
        week_options.append({
            'value': offset,
            'label': f'{label}（W{wn}）{week_desc}',
        })

    return render_template(
        'liff/import_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
        week_options=week_options,
    )


# ---------- JSON API ----------

@liff_bp.route('/import/preview', methods=['POST'])
@liff_auth_required
def import_preview():
    body = request.get_json(silent=True) or {}
    week_offset, category, _overwrite, _purge_past, err = _parse_payload(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    session = Session()
    try:
        result = import_tools.preview_import_fixed(
            session=session,
            week_offset=week_offset,
            category=category,
        )
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    return jsonify({'ok': True, 'preview': _to_jsonable(result.data)})


@liff_bp.route('/import', methods=['POST'])
@liff_auth_required
def import_execute():
    body = request.get_json(silent=True) or {}
    week_offset, category, overwrite, purge_past, err = _parse_payload(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    session = Session()
    try:
        result = import_tools.import_fixed_to_trips(
            session=session,
            week_offset=week_offset,
            category=category,
            overwrite=overwrite,
            purge_past=purge_past,
            user_id=request.line_user_id,
            user_name=None,
            via='liff',
        )
    except SQLAlchemyError as e:
        session.rollback()
        logger.exception("import_fixed_to_trips failed")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    finally:
        session.close()

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    data = _to_jsonable(result.data)
    logger.info(
        f"[LIFF] import {data.get('week_label')} {data.get('category')}: "
        f"inserted={data.get('inserted')} overwritten={data.get('overwritten')} "
        f"by {request.line_user_id}"
    )

    # === 群組廣播：若 source 是 group/room，push 結果讓所有成員看到 ===
    source = body.get('source') or {}
    logger.info(f"[LIFF] import source={source!r}")
    if isinstance(source, dict) and source.get('type') in ('group', 'room'):
        raw_target = source.get('groupId') if source['type'] == 'group' else source.get('roomId')
        # 嚴格清洗：strip whitespace + 拒空字串（LINE API 的 'to' 對格式很嚴）
        target_id = (raw_target or '').strip() if isinstance(raw_target, str) else None
        logger.info(
            f"[LIFF] broadcast target raw={raw_target!r} cleaned={target_id!r} "
            f"len={len(target_id) if target_id else 0}"
        )
        if target_id:
            _push_import_broadcast(target_id, data, operator_user_id=request.line_user_id)
        else:
            logger.warning(f"[LIFF] skip broadcast: target_id 為空（source={source!r}）")

    return jsonify({'ok': True, 'result': data}), 201


def _push_import_broadcast(target_id: str, data: dict, operator_user_id: str | None) -> None:
    """匯入成功後 push 群組／聊天室通知（失敗只 log，不擋 LIFF 回應）"""
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api

        operator = '某位成員'
        if operator_user_id:
            try:
                from modules.utils.line_bot import get_user_display_name
                operator = get_user_display_name(operator_user_id) or operator
            except Exception:
                pass

        wn = data.get('sun_week_number')
        wn_str = f"W{wn} " if wn is not None else ''
        lines = [
            f"✅ {operator} 已匯入固定班次",
            f"📅 {wn_str}{data.get('week_label', '')} {data.get('week_range', '')}",
            f"📁 類別：{data.get('category', '')}",
            f"📥 匯入：{data.get('inserted', 0)} 筆",
        ]
        if data.get('leave_count', 0) > 0:
            lines.append(f"🏷️ 含請假：{data['leave_count']} 筆")
        if data.get('overwritten', 0) > 0:
            lines.append(f"🔄 覆蓋：{data['overwritten']} 筆")
        if data.get('purged_past', 0) > 0:
            lines.append(f"🗑️ 清過去週：{data['purged_past']} 筆")
        if data.get('skipped_dup', 0) > 0:
            lines.append(f"⏭️ 跳過重複：{data['skipped_dup']} 筆")
        if data.get('seq_reset_from'):
            lines.append(f"🔁 班次序號已自動歸位（原 #{data['seq_reset_from']} → 本週從小號重編）")
        msg_text = '\n'.join(lines)

        api = get_line_bot_api()
        # 注意：LINE API 對 to 格式很嚴 — 必須是 33 字元（'C'/'R'/'U' + 32 hex）
        logger.info(
            f"[LIFF] pushing broadcast: to={target_id!r} (len={len(target_id)}) "
            f"msg_len={len(msg_text)}"
        )
        api.push_message(PushMessageRequest(
            to=target_id, messages=[TextMessage(text=msg_text)],
        ))
        logger.info(f"[LIFF] pushed import broadcast to {target_id[:8]}…")
    except Exception as e:
        # 抓 LINE API 的 body — 看 LINE 給的 detailed error
        body_attr = getattr(e, 'body', None)
        status_attr = getattr(e, 'status', None)
        logger.warning(
            f"[LIFF] push import broadcast failed: status={status_attr} "
            f"err_type={type(e).__name__} msg={e} body={body_attr!r}"
        )
