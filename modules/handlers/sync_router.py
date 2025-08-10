"""
輕路由：資料庫同步相關命令
行為維持不變，僅包裝主路由分支。
"""
import logging
from modules.utils.line_bot import reply_text

logger = logging.getLogger(__name__)


def handle_sync_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    try:
        if message_text == "資料庫同步":
            logger.info(f"用戶 {user_id} 請求資料庫同步檢查")
            from modules.handlers.database_sync_handler import handle_database_sync_request

            class MockEvent:
                def __init__(self, uid):
                    self.source = type('', (), {'user_id': uid})()

            mock_event = MockEvent(user_id)
            result = handle_database_sync_request(mock_event, None)
            if result and result.get("text"):
                if "❌" not in result["text"]:
                    from modules.utils.response_handler import send_text_response
                    buttons = [
                        {"label": "✅ 確認同步", "text": "確認同步", "type": "message"},
                        {"label": "❌ 放棄操作", "text": "放棄", "type": "message"}
                    ]
                    send_text_response(reply_token, result["text"], buttons)
                else:
                    reply_text(reply_token, result["text"])
            else:
                reply_text(reply_token, "❌ 無法獲取資料庫狀態")
            return True

        if message_text == "確認同步":
            logger.info(f"用戶 {user_id} 確認執行資料庫同步")
            from modules.handlers.database_sync_handler import handle_database_sync_confirm_free

            class MockEvent:
                def __init__(self, uid, token):
                    self.source = type('', (), {'user_id': uid})()
                    self.reply_token = token

            mock_event = MockEvent(user_id, reply_token)
            handle_database_sync_confirm_free(mock_event, None)
            return True

        if message_text == "同步結果":
            logger.info(f"用戶 {user_id} 查詢同步結果")
            from modules.handlers.database_sync_handler import handle_sync_result_query

            class MockEvent:
                def __init__(self, uid, token):
                    self.source = type('', (), {'user_id': uid})()
                    self.reply_token = token

            mock_event = MockEvent(user_id, reply_token)
            handle_sync_result_query(mock_event, None)
            return True

        # 新增：幫助分類「帳務處理」直接顯示可操作餘額菜單
        if message_text == "help_category_accounting":
            from modules.handlers.accounting import show_accounting_menu
            show_accounting_menu(reply_token)
            return True

        return False
    except Exception as e:
        logger.error(f"資料庫同步命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"❌ 資料庫同步處理失敗: {str(e)}")
        return True
