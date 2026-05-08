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
    return jsonify({'ok': True, 'result': data}), 201
