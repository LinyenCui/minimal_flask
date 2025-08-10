"""
輕路由：修改類別/修改車資/記錄車資（傳統）
行為維持不變，僅將主路由相同邏輯搬移到此處。
"""
import logging
from modules.utils.line_bot import reply_text, reply_message_with_quick_reply

logger = logging.getLogger(__name__)


def handle_modification_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    try:
        # 修改類別
        if message_text.startswith("修改類別"):
            from modules.handlers.trip_handler import handle_modify_category
            result = handle_modify_category(message_text)
            reply_text(reply_token, result)
            return True

        # 修改車資（已廢止，提示改用「記錄車資」）
        if message_text.startswith("修改車資"):
            reply_text(reply_token, "此指令已改為：記錄車資 [ID] [錶價] [加成] [原因]\n請改用『記錄車資』。")
            return True

        # 記錄車資（傳統）
        if message_text.startswith("記錄車資"):
            parts = message_text.split()
            if len(parts) < 3:
                reply_text(
                    reply_token,
                    "❌ 命令格式不正確\n\n✅ 正確格式：\n• 記錄車資 [ID] [錶價] [加成] [原因]\n• 記錄車資 [ID] [錶價] [加成]\n\n💡 如果沒有提供原因，系統會引導您輸入"
                )
                return True
            if len(parts) < 5:
                try:
                    trip_id = int(parts[1]); meter_fare = int(parts[2]); extra_fare = int(parts[3]) if len(parts) >= 4 else 0
                except ValueError:
                    reply_text(reply_token, "❌ 參數格式錯誤\n\n• ID、錶價、加成必須是數字\n• 請檢查格式：記錄車資 2014 280 50")
                    return True
                from modules.utils.conversation_context import conversation_manager
                from modules.utils.quick_reply_manager import QuickReplyManager
                from modules.utils.response_handler import ResponseHandler
                conversation_manager.start_conversation(
                    user_id,
                    'fare_modification',
                    'waiting_reason',
                    {
                        'trip_id': trip_id,
                        'meter_fare': meter_fare,
                        'extra_fare': extra_fare,
                        'operation': 'traditional_record_fare'
                    },
                    f"✅ 車資資料已準備：\n班次 #{trip_id}\n錶價：{meter_fare}元\n加成：{extra_fare}元\n\n❓ 請提供修改原因："
                )
                response = QuickReplyManager.create_text_response(
                    f"✅ 車資資料已準備：\n班次 #{trip_id}\n錶價：{meter_fare}元\n加成：{extra_fare}元\n\n❓ 請提供修改原因：",
                    [{"label": "❌ 取消修改", "text": "取消修改", "type": "message"}]
                )
                if not ResponseHandler.send_response(reply_token, response):
                    reply_text(reply_token, f"✅ 車資資料已準備：\n班次 #{trip_id}\n錶價：{meter_fare}元\n加成：{extra_fare}元\n\n❓ 請提供修改原因：\n\n💡 請直接輸入修改原因，或輸入「取消修改」取消操作")
                return True
            from modules.handlers.trip_handler import handle_record_fare
            result = handle_record_fare(message_text, user_id)
            reply_text(reply_token, result)
            return True

        return False
    except Exception as e:
        logger.error(f"修改命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, f"❌ 修改處理失敗: {str(e)}")
        return True
