"""
輕路由：報表相關命令（日報、周報、月報）
行為維持不變，僅將主路由的分支搬移到此處。
"""
import logging
from modules.utils.line_bot import reply_text
from modules.services.report_service import (
    handle_generate_weekly_report,
    handle_generate_monthly_report,
    handle_generate_daily_report,
)

logger = logging.getLogger(__name__)

DAILY_PREFIXES = ("生成日報表", "生成日報")
WEEKLY_PREFIXES = ("生成周報表", "生成週報表", "生成周報", "生成週報")
MONTHLY_PREFIXES = ("生成月報表", "生成月報")

def handle_report_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """檢查並處理報表相關命令。處理成功返回 True，否則 False。"""
    try:
        if message_text.startswith(DAILY_PREFIXES):
            logger.info(f"處理生成日報表命令: {message_text}")
            result = handle_generate_daily_report(message_text)
            reply_text(reply_token, result)
            return True
        if message_text.startswith(WEEKLY_PREFIXES):
            logger.info(f"處理生成周報表命令: {message_text}")
            result = handle_generate_weekly_report(message_text)
            reply_text(reply_token, result)
            return True
        if message_text.startswith(MONTHLY_PREFIXES):
            logger.info(f"處理生成月報表命令: {message_text}")
            result = handle_generate_monthly_report(message_text)
            reply_text(reply_token, result)
            return True
        return False
    except Exception as e:
        logger.error(f"報表命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"生成報表失敗: {str(e)}")
        return True
