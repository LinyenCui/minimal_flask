"""
Postback 事件處理服務模組
"""
import logging
import urllib.parse
from datetime import datetime
from flask import current_app
import traceback

from modules.utils.line_bot import create_text_message, create_flex_message, reply_text, reply_message, reply_flex
from modules.utils.helpers import booking_states
from modules.handlers.booking_handler import (
    handle_booking_start, handle_date_input, handle_time_input,
    handle_location_input
)
from modules.handlers.trip_query_handler import (
    handle_query_fixed_trips, handle_query_today_trips
)
from modules.flex_designs.booking_flex import (
    get_booking_start_flex, get_booking_time_flex,
    get_booking_location_flex, get_booking_confirm_flex
)
from modules.handlers.trip_handler import handle_query_trips, handle_trip_details, handle_change_status
from modules.services.trip_detail_service import handle_trip_details_flex
from modules.services.report_service import handle_generate_weekly_report
from linebot.v3.messaging import QuickReply, QuickReplyItem, PostbackAction
# 導入時區相關函數
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_postback(event):
    """處理 Postback 事件"""
    postback_data = event.postback.data
    reply_token = event.reply_token
    
    try:
        # 解析 postback 數據
        params = {}
        if postback_data:
            param_pairs = postback_data.split('&')
            for pair in param_pairs:
                if '=' in pair:
                    key, value = pair.split('=')
                    params[key] = value
        
        # 根據 action 參數處理不同的 postback
        action = params.get('action', '')
        
        if action == 'query_trips':
            # 使用Flex版本的查詢班次功能
            try:
                logger.info("處理查詢班次postback，使用Flex版本")
                from modules.services.trip_query_service import handle_query_trips_flex, handle_query_trips
                
                # 調用Flex版本的查詢班次
                flex_content, error_message = handle_query_trips_flex('查詢班次')
                
                if flex_content and error_message is None:
                    # 使用Flex版本回覆
                    reply_flex(reply_token, "班次查詢結果", flex_content)
                else:
                    # 如果出錯，使用文本版本
                    logger.warning(f"使用Flex版本失敗，回退到文本版本。錯誤: {error_message}")
                    result = handle_query_trips('查詢班次')
                    reply_text(reply_token, result)
            except Exception as e:
                logger.error(f"處理Flex版本查詢班次時出錯: {e}")
                traceback.print_exc()
                # 使用文本版本作為後備
                result = handle_query_trips('查詢班次')
                reply_text(reply_token, f"Flex消息處理錯誤，使用文本版本：\n{result}")
            
        elif action == 'query_fixed_trips':
            # 使用Flex版本的查詢固定班次功能
            try:
                logger.info("處理查詢固定班次postback，使用Flex版本")
                from modules.services.trip_query_service import handle_query_fixed_trips_flex, handle_query_fixed_trips
                
                # 調用Flex版本的查詢固定班次
                flex_content, error_message = handle_query_fixed_trips_flex('查詢固定班次')
                
                if flex_content and error_message is None:
                    # 使用Flex版本回覆
                    reply_flex(reply_token, "固定班次查詢結果", flex_content)
                else:
                    # 如果出錯，使用文本版本
                    logger.warning(f"使用Flex版本失敗，回退到文本版本。錯誤: {error_message}")
                    result = handle_query_fixed_trips('查詢固定班次')
                    reply_text(reply_token, result)
            except Exception as e:
                logger.error(f"處理Flex版本查詢固定班次時出錯: {e}")
                traceback.print_exc()
                # 使用文本版本作為後備
                result = handle_query_fixed_trips('查詢固定班次')
                reply_text(reply_token, f"Flex消息處理錯誤，使用文本版本：\n{result}")
            
        elif action == 'generate_report':
            # 處理生成報表請求
            category = params.get('category')
            if category:
                logger.info(f"處理生成報表postback，類別: {category}")
                result = handle_generate_weekly_report(f"生成周報表 {category}")
                reply_text(reply_token, result)
            else:
                # 如果沒有類別，創建Quick Reply
                quick_reply = QuickReply(items=[
                    QuickReplyItem(
                        action=PostbackAction(
                            label="診所",
                            data="action=generate_report&category=診所",
                            display_text="生成周報表 診所"
                        )
                    ),
                    QuickReplyItem(
                        action=PostbackAction(
                            label="東洋",
                            data="action=generate_report&category=東洋",
                            display_text="生成周報表 東洋"
                        )
                    ),
                    QuickReplyItem(
                        action=PostbackAction(
                            label="全部",
                            data="action=generate_report&category=全部",
                            display_text="生成周報表 全部"
                        )
                    )
                ])
                text = "請選擇要生成報表的類別："
                message = create_text_message(text, quick_reply=quick_reply)
                reply_message(reply_token, message)
            
        elif action == 'view_trip' and 'trip_id' in params:
            trip_id = params['trip_id']
            result = handle_trip_details(int(trip_id))
            reply_text(reply_token, result)
            
        elif action == 'change_status' and 'trip_id' in params and 'status' in params:
            trip_id = params['trip_id']
            status = params['status']
            result = handle_change_status(f"修改狀態 {trip_id} {status}")
            reply_text(reply_token, result)
            
        elif action == 'help':
            from modules.handlers.message_handler import get_help_text
            help_text = get_help_text()
            reply_text(reply_token, help_text)
            
        elif action == 'update_status':
            # 檢查是否提供了trip_id和status參數
            if 'trip_id' in params and 'status' in params:
                trip_id = params['trip_id']
                new_status = params['status']
                
                # 調用更新狀態的處理程序
                from modules.handlers.trip_handler import handle_change_status
                result = handle_change_status(f"修改狀態 {trip_id} {new_status}")
                reply_text(reply_token, result)
            
            # 如果只有trip_id而沒有status，返回狀態選擇
            elif 'trip_id' in params:
                trip_id = params['trip_id']
                # 查詢班次詳情，提供狀態選擇
                result, _ = handle_trip_details_flex(trip_id)
                
                if result and 'flex_message' in result and 'quick_reply' in result:
                    # 提供狀態選擇
                    quick_reply_items = []
                    for item in result['quick_reply']['items']:
                        action = item['action']
                        quick_reply_items.append(
                            QuickReplyItem(
                                action=PostbackAction(
                                    label=action['label'],
                                    data=action['data'],
                                    display_text=action['displayText']
                                )
                            )
                        )
                    
                    # 構建 Quick Reply
                    quick_reply = QuickReply(items=quick_reply_items)
                    
                    # 發送提示消息
                    from linebot.v3.messaging import TextMessage
                    text_message = TextMessage(
                        text=f"請選擇班次 #{trip_id} 的新狀態：",
                        quick_reply=quick_reply
                    )
                    
                    reply_message(reply_token, [text_message])
                else:
                    reply_text(reply_token, "無法提供狀態選擇，請使用文字命令：修改狀態 [班次ID] [新狀態]")
            else:
                # 缺少參數
                reply_text(reply_token, "修改狀態需要班次ID和新狀態，請使用正確格式：修改狀態 [班次ID] [新狀態]")
            
        else:
            reply_text(reply_token, f"收到未知的 postback: {postback_data}")
            
    except Exception as e:
        current_app.logger.error(f"處理 postback 時出錯: {e}")
        traceback.print_exc()
        reply_text(reply_token, f"處理請求時出錯: {str(e)}")

def parse_postback_data(data):
    """解析 postback 數據"""
    try:
        # 解析 query string 格式的數據
        params = {}
        for item in data.split("&"):
            if "=" in item:
                key, value = item.split("=", 1)
                params[key] = urllib.parse.unquote(value)
        return params
    except Exception as e:
        logger.error(f"解析 Postback 數據時出錯: {e}")
        return {}

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
        "• 幫助 - 顯示此幫助訊息\n\n"
        "如在群組中使用，請在命令前添加前綴：!、# 或 /\n"
        "例如：!預約、#幫助"
    )
    return create_text_message(help_text)

def handle_confirm_input(user_id, message_text, states):
    """處理用戶確認預約（從 booking_handler 移植）"""
    from modules.handlers.booking_handler import handle_confirm_input
    return handle_confirm_input(user_id, message_text, states)

def handle_help_section(section):
    """處理幫助命令的不同部分"""
    if section == "booking":
        help_text = (
            "預約功能說明：\n\n"
            "輸入「預約」開始預約流程，按照提示選擇：\n"
            "1. 日期\n"
            "2. 時間\n"
            "3. 地點\n"
            "完成後會收到確認信息。"
        )
        return create_text_message(help_text)
    
    elif section == "query":
        help_text = (
            "查詢功能說明：\n\n"
            "• 查詢班次 - 查詢今日所有班次\n"
            "• 查詢固定班次 - 查詢固定班次，可選擇日期\n"
            "• 班次詳情 [班次ID] - 查看班次詳細信息"
        )
        return create_text_message(help_text)
    
    elif section == "status":
        help_text = (
            "狀態管理功能說明：\n\n"
            "• 修改狀態 [班次ID] [新狀態] - 更改班次狀態\n"
            "• 確認取消 [班次ID] - 確認取消班次\n"
            "• 確認請假 [班次ID] - 確認請假班次\n"
            "• 確認衝突 [班次ID] - 確認衝突班次"
        )
        return create_text_message(help_text)
    
    else:
        help_text = (
            "請選擇您想了解的功能：\n\n"
            "• 預約功能\n"
            "• 查詢功能\n"
            "• 狀態管理"
        )
        return create_text_message(help_text) 