"""
輕路由：幫助系統入口
行為維持不變，委派給既有 HelpHandler。
"""
import logging
from modules.utils.line_bot import reply_text
from modules.help_system.help_handler import HelpHandler

logger = logging.getLogger(__name__)

_help_handler = HelpHandler()

HELP_TRIGGERS = {"幫助", "幫助文字", "完整指令列表", "搜尋幫助", "help_system_check"}

def handle_help_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    try:
        if message_text in HELP_TRIGGERS or message_text.startswith(("help_category_", "help_item_", "help_search_", "help_demo_")):
            handled = _help_handler.handle_help_request(message_text, user_id, reply_token)
            if not handled:
                reply_text(reply_token, "無可用的幫助項目")
            # 若是帳務處理分類，直接顯示餘額與Quick Reply（可操作）
            if message_text == "help_category_accounting":
                try:
                    from modules.handlers.accounting import show_accounting_menu
                    show_accounting_menu(reply_token)
                except Exception as e:
                    logger.error(f"[help_router] 帳務處理分類顯示失敗: {e}")
                    from modules.utils.line_bot import reply_text
                    reply_text(reply_token, "帳務處理暫時不可用")
                return True
            return True
        return False
    except Exception as e:
        logger.error(f"[help_router] 幫助命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, "幫助系統暫時不可用")
        return True
