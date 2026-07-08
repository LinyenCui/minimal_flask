"""LIFF 報表生成 endpoints

Routes
------
GET  /liff/report/form    HTML 報表表單殼
POST /liff/report         產生報表（auth required，同步等 5-30 秒）

業務邏輯：rewrite.tools.report.generate_report → 包 legacy report_service
（產 Excel + 上傳 Google Drive）。LIFF 同步等結果，回 Drive URL。

報表類型：daily / weekly / monthly
類別：全部 / 診所 / 東洋
"""
import logging
import os
from datetime import date, datetime
from typing import Any

from flask import jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError

from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required
from rewrite.tools import report as report_tools

logger = logging.getLogger(__name__)


def _parse_payload(body: dict) -> tuple[dict, str | None]:
    """form payload → generate_report kwargs"""
    rtype = (body.get('report_type') or '').strip()
    if rtype not in report_tools.VALID_REPORT_TYPES:
        return {}, f"報表類型必須是 {report_tools.VALID_REPORT_TYPES} 之一"

    cat = (body.get('category') or '全部').strip() or '全部'
    if cat not in report_tools.VALID_REPORT_CATEGORIES:
        return {}, f"類別必須是 {report_tools.VALID_REPORT_CATEGORIES} 之一"

    # daily = 指定日期；weekly = 指定「該日所在太陽週」的任一天（通常送週日）
    target_date = None
    if rtype in ('daily', 'weekly'):
        d_raw = (body.get('target_date') or '').strip()
        if d_raw:
            try:
                target_date = date.fromisoformat(d_raw)
            except ValueError:
                return {}, f"日期格式錯（要 YYYY-MM-DD）：{d_raw!r}"

    # monthly = 指定月份 'YYYY-MM'（不給預設上月）
    year = month = None
    if rtype == 'monthly':
        m_raw = (body.get('month') or '').strip()
        if m_raw:
            try:
                y_s, m_s = m_raw.split('-', 1)
                year, month = int(y_s), int(m_s)
                if not (1 <= month <= 12):
                    raise ValueError
            except ValueError:
                return {}, f"月份格式錯（要 YYYY-MM）：{m_raw!r}"

    file_format = (body.get('file_format') or 'xlsx').strip() or 'xlsx'
    if file_format not in report_tools.VALID_FILE_FORMATS:
        return {}, f"檔案格式必須是 {report_tools.VALID_FILE_FORMATS} 之一"

    return {
        'report_type': rtype,
        'category': cat,
        'target_date': target_date,
        'year': year,
        'month': month,
        'file_format': file_format,
    }, None


def _push_report_result(target_id, result_data) -> None:
    """產完 push 到指定目標（群組 / 聊天室 / 個人，含 Drive URL）"""
    if not target_id:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled
        if not push_notify_enabled():
            logger.info("[LIFF] push skipped (PUSH_NOTIFY off)")
            return
        api = get_line_bot_api()
        type_map = {'daily': '日', 'weekly': '週', 'monthly': '月'}
        rt = type_map.get(result_data.get('report_type'), '?')
        cat = result_data.get('category') or '全部'
        msg = f"📊 {cat} {rt}報表已產生"
        # result_text 已含帶標籤的連結行（📊 Excel：… / 📄 PDF：…），直接沿用
        url_lines = [ln for ln in (result_data.get('result_text') or '').split('\n')
                     if 'http' in ln]
        if url_lines:
            msg += '\n' + '\n'.join(url_lines)
        elif result_data.get('drive_url'):
            msg += f"\n📂 {result_data['drive_url']}"
        api.push_message(PushMessageRequest(
            to=target_id, messages=[TextMessage(text=msg)],
        ))
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push report result failed: {e} body={body_attr!r}")


# ---------- HTML 殼 ----------

@liff_bp.route('/report/form', methods=['GET'])
def report_form():
    return render_template(
        'liff/report_form.html',
        liff_id=os.environ.get('LIFF_ID', ''),
    )


# ---------- JSON API ----------

@liff_bp.route('/report', methods=['POST'])
@liff_auth_required
def report_generate():
    body = request.get_json(silent=True) or {}
    fields, err = _parse_payload(body)
    if err:
        return jsonify({'ok': False, 'error': err}), 400

    try:
        result = report_tools.generate_report(
            user_id=request.line_user_id,
            via='liff',
            **fields,
        )
    except SQLAlchemyError as e:
        logger.exception("generate_report DB error")
        return jsonify({'ok': False, 'error': f"DB error: {e}"}), 500
    except Exception as e:
        logger.exception("generate_report failed")
        return jsonify({'ok': False, 'error': str(e)[:200]}), 500

    if not result.ok:
        return jsonify({'ok': False, 'error': result.error}), 400

    data = result.data
    logger.info(
        f"[LIFF] report {data.get('report_type')}/{data.get('category')} "
        f"by {request.line_user_id}, drive_url={data.get('drive_url')}"
    )
    # 順手 push（群組觸發 → push 群組；私聊 → push 個人）
    from rewrite.utils.liff_url import resolve_push_target
    target = resolve_push_target(body.get('source'), request.line_user_id)
    _push_report_result(target, data)
    return jsonify({
        'ok': True,
        'result_text': data.get('result_text', ''),
        'drive_url': data.get('drive_url'),
        'drive_urls': data.get('drive_urls') or [],
        'report_type': data.get('report_type'),
        'category': data.get('category'),
    })
