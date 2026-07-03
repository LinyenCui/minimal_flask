"""
報表生成 wrapper（包裝 legacy report_service.py，不重做業務邏輯）

legacy report_service.py 1174 行業務邏輯（產 Excel + 上傳 Google Drive）
留在原處，rewrite 只做：結構化參數 → 組成 legacy 預期 text → call → 回結果。

支援：
  generate_daily_report   日報表（指定日期 / 預設昨天）
  generate_weekly_report  週報表（預設上週）
  generate_monthly_report 月報表（預設上月）

return: {'ok': bool, 'result_text': str, 'drive_url': str|None}
"""
import logging
import re
from datetime import date
from typing import Optional

from rewrite.tools.base import ToolResult

logger = logging.getLogger(__name__)


VALID_REPORT_CATEGORIES = ('全部', '診所', '東洋')
VALID_REPORT_TYPES = ('daily', 'weekly', 'monthly')
VALID_FILE_FORMATS = ('xlsx', 'pdf', 'both')


def _extract_drive_urls(result_text: str) -> list:
    """從 legacy return 字串抽所有 Drive URL（xlsx/pdf 各一）"""
    if not result_text:
        return []
    return re.findall(r'https?://[^\s）)]+', result_text)


def generate_report(
    *,
    session=None,  # 簽名一致，不用 DB（report_service 自己拿 session）
    report_type: str,
    target_date: Optional[date] = None,
    category: Optional[str] = '全部',
    file_format: str = 'xlsx',
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
) -> ToolResult:
    """產報表（包 legacy handle_generate_*_report）

    Args:
        report_type: 'daily' / 'weekly' / 'monthly'
        target_date: 只 daily 用（可選；不給用 legacy 預設「昨天」）
        category: '全部' / '診所' / '東洋'（預設全部）
        file_format: 'xlsx'（預設）/ 'pdf' / 'both'

    Returns:
        ToolResult.success(data={
            'result_text': str,     # legacy 完整訊息（含成功/失敗 + 統計）
            'drive_url': str|None,  # 第一個 Drive 連結（向後相容）
            'drive_urls': list,     # 所有 Drive 連結（xlsx / pdf）
            'report_type': str,
        })
    """
    if report_type not in VALID_REPORT_TYPES:
        return ToolResult.fail(
            f"報表類型必須是 {VALID_REPORT_TYPES} 之一（給的是 {report_type!r}）"
        )
    if category and category not in VALID_REPORT_CATEGORIES:
        return ToolResult.fail(
            f"類別必須是 {VALID_REPORT_CATEGORIES} 之一（給的是 {category!r}）"
        )
    if file_format not in VALID_FILE_FORMATS:
        return ToolResult.fail(
            f"檔案格式必須是 {VALID_FILE_FORMATS} 之一（給的是 {file_format!r}）"
        )
    cat = category or '全部'

    # 組 legacy 預期 text
    parts = []
    if report_type == 'daily':
        parts.append('生成日報表')
        if target_date:
            parts.append(f'{target_date.month}/{target_date.day}')
        if cat != '全部':
            parts.append(cat)
    elif report_type == 'weekly':
        parts.append('生成週報表')
        if cat != '全部':
            parts.append(cat)
    elif report_type == 'monthly':
        parts.append('生成月報表')
        if cat != '全部':
            parts.append(cat)
    text = ' '.join(parts)

    logger.info(
        f"[report wrapper] type={report_type} cat={cat} date={target_date} "
        f"→ legacy text={text!r}"
    )

    # call legacy
    try:
        if report_type == 'daily':
            from modules.services.report_service import handle_generate_daily_report
            result_text = handle_generate_daily_report(text, file_format=file_format)
        elif report_type == 'weekly':
            from modules.services.report_service import handle_generate_weekly_report
            result_text = handle_generate_weekly_report(text, file_format=file_format)
        else:
            from modules.services.report_service import handle_generate_monthly_report
            result_text = handle_generate_monthly_report(text, file_format=file_format)
    except Exception as e:
        logger.exception("legacy report 失敗")
        return ToolResult.fail(f"報表生成失敗：{str(e)[:200]}")

    drive_urls = _extract_drive_urls(result_text)
    drive_url = drive_urls[0] if drive_urls else None

    # 失敗檢測（legacy 回的字串開頭可能是錯誤）
    if (
        '失敗' in result_text and not drive_url
        or '出錯' in result_text and not drive_url
    ):
        return ToolResult.fail(result_text)

    return ToolResult.success(
        data={
            'result_text': result_text,
            'drive_url': drive_url,
            'drive_urls': drive_urls,
            'report_type': report_type,
            'category': cat,
            'target_date': target_date,
        },
    )
