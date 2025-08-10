"""
輕路由：固定班表/固定班次請假/恢復
行為維持不變，僅將主路由相同邏輯搬移到此處。
"""
import logging
import re
from modules.utils.line_bot import reply_text, reply_message, reply_message_with_quick_reply
from modules.utils.conversation_context import conversation_manager

logger = logging.getLogger(__name__)


def handle_fixed_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    try:
        # 固定班表
        if message_text.startswith("固定班表"):
            from modules.handlers.fixed_schedule_query_handler import handle_fixed_schedule_query
            result = handle_fixed_schedule_query(message_text, user_id)
            if isinstance(result, dict) and result.get("type") == "quick_reply":
                try:
                    reply_message(reply_token, [result])
                    logger.info("成功發送固定班表查詢的 Quick Reply 訊息")
                except Exception as e:
                    logger.error(f"發送固定班表查詢 Quick Reply 訊息失敗: {e}")
                    reply_text(reply_token, result.get("text", "查詢失敗"))
            else:
                reply_text(reply_token, result)
            return True

        # 固定班次#ID請假 快捷格式
        if message_text.startswith("固定班次#") and message_text.endswith("請假"):
            match = re.match(r"固定班次#(\d+)請假", message_text)
            if match:
                schedule_id = match.group(1)
                try:
                    conversation_manager.set_recent_fixed_schedule_id(user_id, int(schedule_id))
                    conversation_manager.set_leave_mode(user_id=user_id, fixed_schedule_id=int(schedule_id))
                    logger.info(f"✅ 設置用戶 {user_id} 進入固定班次請假模式，固定班次 #{schedule_id}")
                except Exception as e:
                    logger.error(f"❌ 記錄固定班次ID或設置請假模式時出錯: {e}")
                # 建立 Quick Reply 退出
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                quick_reply_items = [
                    QuickReplyItem(action=MessageAction(label="❌ 放棄操作", text="放棄操作"))
                ]
                quick_reply = QuickReply(items=quick_reply_items)
                msg_text = (
                    f"固定班次 #{schedule_id} 乘客長期請假\n\n請輸入：[原因] [加成]\n\n例如：\n診所乘客長期住院 -50\n出國一個月 0\n搬家不再需要 -100\n\n💡 提示：先寫原因，最後寫加成金額\n\n🚪 退出方式：點擊下方「放棄操作」按鈕"
                )
                reply_message_with_quick_reply(reply_token, msg_text, quick_reply)
                return True

        # 固定班次請假 指令
        if message_text.startswith("固定班次請假"):
            from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave_command
            result = handle_fixed_schedule_leave_command(message_text, user_id)
            reply_text(reply_token, result)
            return True

        # 固定班次恢復 指令
        if message_text.startswith("固定班次恢復"):
            from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_restore_command
            result = handle_fixed_schedule_restore_command(message_text, user_id)
            reply_text(reply_token, result)
            return True

        return False
    except Exception as e:
        logger.error(f"固定班表/請假命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"處理固定班表/請假命令失敗: {str(e)}")
        return True
