"""
輕路由：司機指派相關命令
行為維持不變，僅包裝主路由分支。
"""
import logging
from modules.utils.line_bot import reply_message, reply_text, reply_flex
from modules.services.driver_service import (
    handle_driver_assign_request,
    handle_driver_assign_select,
    handle_driver_assign_confirm,
    handle_driver_assign_cancel,
)

logger = logging.getLogger(__name__)

def handle_driver_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """檢查並處理指派相關命令。處理成功返回 True，否則 False。"""
    try:
        # 指派司機 請求（兩種格式）
        if (message_text.startswith('指派司機') and len(message_text.split()) == 2) or \
           (message_text.startswith('指派 ') and len(message_text.split()) == 2):
            trip_id = int(message_text.split()[1])
            logger.info(f"處理指派司機請求: {trip_id}")
            message_to_send, error_message = handle_driver_assign_request(trip_id)
            if message_to_send and error_message is None:
                reply_message(reply_token, [message_to_send])
            else:
                reply_text(reply_token, error_message or "無法載入司機列表")
            return True
        # 選擇司機
        if message_text.startswith('指派司機 ') and len(message_text.split()) == 3:
            parts = message_text.split()
            trip_id = int(parts[1])
            driver_id = int(parts[2])
            logger.info(f"處理司機選擇: 班次={trip_id}, 司機={driver_id}")
            result, error_message = handle_driver_assign_select(trip_id, driver_id)
            if result and error_message is None:
                if isinstance(result, dict) and 'flex_message' in result and 'quick_reply' in result:
                    from linebot.v3.messaging import FlexMessage, FlexContainer
                    flex_message = FlexMessage(
                        alt_text="確認指派司機",
                        contents=FlexContainer.from_dict(result['flex_message']),
                        quick_reply=result['quick_reply']
                    )
                    reply_message(reply_token, [flex_message])
                else:
                    reply_flex(reply_token, "確認指派司機", result)
            else:
                reply_text(reply_token, error_message or "無法載入確認界面")
            return True
        # 確認指派
        if message_text.startswith('確認指派 ') and len(message_text.split()) == 3:
            parts = message_text.split()
            trip_id = int(parts[1])
            driver_id = int(parts[2])
            result = handle_driver_assign_confirm(trip_id, driver_id)
            reply_text(reply_token, result)
            return True
        # 取消/放棄 指派
        if message_text.startswith('取消指派 ') or message_text.startswith('放棄指派 '):
            parts = message_text.split()
            if len(parts) == 2:
                trip_id = int(parts[1])
                result = handle_driver_assign_cancel(trip_id)
                reply_text(reply_token, result)
            else:
                reply_text(reply_token, "取消/放棄指派命令格式不正確。正確格式：取消指派 [班次ID] 或 放棄指派 [班次ID]")
            return True
        return False
    except ValueError:
        reply_text(reply_token, "班次ID和司機ID必須是數字。")
        return True
    except Exception as e:
        logger.error(f"指派相關命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"處理指派命令失敗: {str(e)}")
        return True
