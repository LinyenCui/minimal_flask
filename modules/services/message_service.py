"""
訊息處理服務模組
"""
import logging
from modules.utils.line_bot import create_text_message, create_flex_message
from modules.utils.helpers import extract_command_args
from modules.handlers.trip_status_handler import (
    handle_update_trip_status, handle_confirm_cancel_trip,
    handle_confirm_leave_trip, handle_confirm_conflict_trip
)
from modules.handlers.trip_query_handler import (
    handle_query_fixed_trips, handle_trip_details, create_query_fixed_trips_quick_reply,
    handle_query_today_trips
)
from modules.services.report_service import handle_generate_weekly_report
from linebot.v3.messaging import TextMessage, QuickReply, QuickReplyItem, MessageAction
# 導入時區相關函數
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_message(message_text, user_id, in_group=False):
    """處理用戶消息的主函數"""
    try:
        logger.info(f"處理消息: '{message_text}', 用戶ID: {user_id}, 群組: {in_group}")
        
        # 如果訊息為空，返回錯誤訊息
        if not message_text:
            return create_text_message("收到空消息，請輸入有效的命令。")
        
        # 提取命令
        command, args = extract_command_args(message_text)
        
        # 修改班次狀態命令
        if command in ["修改狀態", "更改狀態"]:
            return create_text_message(handle_update_trip_status(message_text))
        
        # 確認取消班次命令
        elif command == "確認取消":
            return create_text_message(handle_confirm_cancel_trip(message_text))
        
        # 確認請假班次命令
        elif command == "確認請假":
            return create_text_message(handle_confirm_leave_trip(message_text))
        
        # 確認衝突班次命令
        elif command == "確認衝突":
            return create_text_message(handle_confirm_conflict_trip(message_text))
        
        # 查詢固定班次命令
        elif command == "查詢固定班次":
            # 如果只有命令，沒有參數，返回Quick Reply
            if not args:
                logger.info("查詢固定班次，返回Quick Reply選項")
                quick_reply = create_query_fixed_trips_quick_reply()
                text = "請選擇要查詢的日期："
                return TextMessage(text=text, quick_reply=quick_reply)
            else:
                return create_text_message(handle_query_fixed_trips(message_text))
        
        # 班次詳情查詢命令
        elif command.startswith("班次詳情"):
            return create_text_message(handle_trip_details(message_text))
        
        # 查詢班次命令（直接查詢當天班次）
        elif command in ["查詢班次", "查班次"]:
            # 直接查詢當天的所有班次，不需選擇日期
            logger.info("查詢當天所有班次")
            return create_text_message(handle_query_today_trips())
            
        # 生成周報表命令
        elif command in ["生成周報表", "生成週報表", "生成周報", "生成週報"]:
            # 如果只是命令，提供類別選擇
            if not args:
                logger.info("生成周報表，返回類別選項")
                # 創建Quick Reply
                quick_reply = QuickReply(items=[
                    QuickReplyItem(
                        action=MessageAction(
                            label="診所",
                            text="生成周報表 診所"
                        )
                    ),
                    QuickReplyItem(
                        action=MessageAction(
                            label="東洋",
                            text="生成周報表 東洋"
                        )
                    ),
                    QuickReplyItem(
                        action=MessageAction(
                            label="全部",
                            text="生成周報表 全部"
                        )
                    )
                ])
                return TextMessage(text="請選擇要生成報表的類別：", quick_reply=quick_reply)
            else:
                # 調用報表生成處理函數
                logger.info(f"生成周報表，參數: {args}")
                result = handle_generate_weekly_report(message_text)
                return create_text_message(result)
        
        # 幫助命令，可以在這裡加入更多功能的說明
        elif command in ["幫助", "help", "?", "h"]:
            return create_help_message()
        
        # 未知命令
        else:
            if in_group:
                # 如果在群組中，但命令無法識別，忽略不回覆
                logger.info(f"在群組中收到無法識別的命令: {command}")
                return None
            else:
                # 在私聊中，如果命令無法識別，回覆幫助訊息
                return create_text_message(f"無法識別的命令: {command}\n\n請輸入「幫助」查看可用命令。")
    
    except Exception as e:
        logger.error(f"處理消息時出錯: {e}")
        # 出錯時，只在私聊中回覆
        if not in_group:
            return create_text_message("處理您的消息時出現錯誤，請稍後重試。")
        return None

def create_help_message():
    """創建幫助訊息"""
    help_text = (
        "可用命令列表：\n\n"
        "• 預約 - 開始預約流程\n"
        "• 查詢班次 - 查詢今日所有班次\n"
        "• 查詢固定班次 [日期] - 查詢指定日期的固定班次\n"
        "• 班次詳情 [班次ID] - 查看班次詳細信息\n"
        "• 修改狀態 [班次ID] [新狀態] - 更改班次狀態\n"
        "• 確認取消 [班次ID] - 確認取消班次\n"
        "• 確認請假 [班次ID] - 確認請假班次\n"
        "• 確認衝突 [班次ID] - 確認衝突班次\n"
        "• 生成周報表 [類別] - 生成上週班次報表\n"
        "• 幫助 - 顯示此幫助訊息\n\n"
        "如在群組中使用，請在命令前添加前綴：!、# 或 /\n"
        "例如：!預約、#幫助"
    )
    return create_text_message(help_text) 