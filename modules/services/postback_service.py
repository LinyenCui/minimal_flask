"""
Postback 事件處理服務模組
"""
import logging
import urllib.parse
from datetime import datetime
from flask import current_app
import traceback

from modules.utils.line_bot import create_text_message, create_flex_message, reply_text, reply_message, reply_flex, reply_message_with_quick_reply
from modules.handlers.trip_query_handler import (
    handle_query_fixed_trips, handle_query_today_trips
)
from modules.handlers.trip_handler import handle_query_trips, handle_trip_details, handle_change_status
from modules.services.trip_detail_service import handle_trip_details_flex
from modules.services.report_service import handle_generate_weekly_report
from linebot.v3.messaging import QuickReply, QuickReplyItem, PostbackAction
# 導入時區相關函數
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date
from modules.utils.quick_reply_manager import QuickReplyManager
from modules.utils.response_handler import ResponseHandler
from modules.handlers.text_message_handler import get_help_text

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_postback(event):
    """處理 Postback 事件"""
    postback_data = event.postback.data
    reply_token = event.reply_token
    user_id = event.source.user_id if hasattr(event, 'source') else None
    
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
            # 使用Flex版本的東洋班次功能
            try:
                logger.info("處理東洋班次postback，使用Flex版本")
                from modules.services.trip_query_service import handle_query_trips_flex, handle_query_trips
                
                # 調用Flex版本的東洋班次
                flex_content, error_message = handle_query_trips_flex('東洋班次')
                
                if flex_content and error_message is None:
                    # 使用Flex版本回覆
                    reply_flex(reply_token, "班次查詢結果", flex_content)
                else:
                    # 如果出錯，使用文本版本
                    logger.warning(f"使用Flex版本失敗，回退到文本版本。錯誤: {error_message}")
                    result = handle_query_trips('東洋班次')
                    reply_text(reply_token, result)
            except Exception as e:
                logger.error(f"處理Flex版本東洋班次時出錯: {e}")
                traceback.print_exc()
                # 使用文本版本作為後備
                result = handle_query_trips('東洋班次')
                reply_text(reply_token, f"Flex消息處理錯誤，使用文本版本：\n{result}")
            
        elif action == 'query_fixed_trips':
            try:
                logger.info("處理查詢固定班次 postback (應通過日期選擇觸發Message) - 目標改為診所")
                from modules.services.trip_query_service import handle_query_fixed_trips_flex, handle_query_fixed_trips
                flex_content, error_message = handle_query_fixed_trips_flex('診所班次') 
                if flex_content and error_message is None:
                     reply_flex(reply_token, "診所班次查詢結果", flex_content)
                else:
                     logger.warning(f"固定班次 postback Flex 失敗，回退文本: {error_message}")
                     result = handle_query_fixed_trips('診所班次')
                     reply_text(reply_token, result)
            except Exception as e:
                logger.error(f"處理固定班次 postback 時出錯: {e}")
                traceback.print_exc()
                result = handle_query_fixed_trips('診所班次')
                reply_text(reply_token, f"Flex消息處理錯誤，使用文本版本：\n{result}")
            
        elif action == 'query_clinic_trips_date_select':
            try:
                logger.info("處理診所班次日期選擇請求")
                from modules.services.trip_query_service import request_clinic_trip_date_selection
                reply_msg, error_message = request_clinic_trip_date_selection()
                
                if reply_msg and error_message is None:
                    reply_message(reply_token, [reply_msg]) 
                else:
                    reply_text(reply_token, error_message or "無法生成日期選擇")
            except Exception as e:
                logger.error(f"處理診所班次日期選擇時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理請求時出錯: {str(e)}")
            
        elif action == 'generate_report':
            # 處理生成報表請求
            category = params.get('category')
            if category:
                logger.info(f"處理生成報表postback，類別: {category}")
                result = handle_generate_weekly_report(f"生成周報表 {category}")
                reply_text(reply_token, result)
            else:
                # 如果沒有類別，使用新的 Quick Reply 標準格式
                category_buttons = [
                    {"label": "診所", "text": "生成周報表 診所", "type": "postback", "data": "action=generate_report&category=診所"},
                    {"label": "東洋", "text": "生成周報表 東洋", "type": "postback", "data": "action=generate_report&category=東洋"},
                    {"label": "全部", "text": "生成周報表 全部", "type": "postback", "data": "action=generate_report&category=全部"}
                ]
                text = "請選擇要生成報表的類別："
                response = QuickReplyManager.create_text_response(text, category_buttons)
                ResponseHandler.handle_legacy_format(reply_token, response)
            
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
            from modules.handlers.text_message_handler import get_help_text
            help_text = get_help_text()
            reply_text(reply_token, help_text)
            
        elif action == 'help_text':
            from modules.handlers.text_message_handler import get_help_text
            help_text = get_help_text()
            reply_text(reply_token, help_text)
            
        # 新的分層級幫助功能
        elif action == 'help_future_mode':
            from modules.flex_designs.help_flex import get_future_mode_help
            help_flex = get_future_mode_help()
            reply_flex(reply_token, "未來時間態功能說明", help_flex)
            
        elif action == 'help_ai_features':
            from modules.flex_designs.help_flex import get_ai_features_help
            help_flex = get_ai_features_help()
            reply_flex(reply_token, "AI功能說明", help_flex)
            
        elif action == 'help_fixed_schedule':
            from modules.flex_designs.help_flex import get_fixed_schedule_help
            help_flex = get_fixed_schedule_help()
            reply_flex(reply_token, "固定班次功能", help_flex)
            
        elif action == 'help_leave_status':
            from modules.flex_designs.help_flex import get_leave_status_help
            help_flex = get_leave_status_help()
            reply_flex(reply_token, "請假與狀態", help_flex)
            
        elif action == 'help_reports':
            from modules.flex_designs.help_flex import get_reports_help
            help_flex = get_reports_help()
            reply_flex(reply_token, "報表與匯出", help_flex)
            
        elif action == 'help_maintenance':
            from modules.flex_designs.help_flex import get_maintenance_help
            help_flex = get_maintenance_help()
            reply_flex(reply_token, "維護工具", help_flex)
            
        # 新增的系統指南功能
        elif action == 'help_production_line':
            from modules.flex_designs.help_flex import get_production_line_help
            help_flex = get_production_line_help()
            reply_flex(reply_token, "生產線思維指南", help_flex)
            
        elif action == 'help_quick_reference':
            from modules.flex_designs.help_flex import get_quick_reference_help
            help_flex = get_quick_reference_help()
            reply_flex(reply_token, "快速參考指南", help_flex)
            
        elif action == 'help_advanced_leave':
            from modules.flex_designs.help_flex import get_advanced_leave_help
            help_flex = get_advanced_leave_help()
            reply_flex(reply_token, "高級請假系統", help_flex)
            
        elif action == 'update_status' and 'trip_id' in params:
            trip_id = params['trip_id']
            
            if 'status' in params:
                # 情況 1: 帶 status 參數 (來自 Quick Reply)，執行更新
                new_status = params['status']
                
                # 🚨 新增：檢查基於執行時間的30分鐘限制
                try:
                    from modules.models.trip import Trip
                    from modules.models.base import db
                    
                    trip = db.session.query(Trip).filter_by(trip_id=trip_id).first()
                    
                    if trip and not trip.can_modify_status():
                        # 在限制期間，不允許修改狀態
                        restriction_message = trip.get_restriction_message()
                        reply_text(reply_token, restriction_message or f"⚠️ 班次 {trip_id} 目前無法修改狀態")
                        return
                    
                except Exception as check_error:
                    logger.error(f"檢查修改權限時出錯: {check_error}")
                    # 如果檢查失敗，允許繼續（向下兼容）
                
                # 🚨 新增：所有狀態修改都使用新的處理邏輯
                from modules.handlers.trip_status_handler import handle_update_trip_status
                result = handle_update_trip_status(f"修改狀態 {trip_id} {new_status}", user_id=user_id)
                
                # 🔄 處理傳統請假功能的特殊返回格式
                if isinstance(result, dict) and result.get("type") == "text_with_quick_reply_traditional":
                    # 傳統請假功能的Quick Reply格式
                    reply_message_with_quick_reply(reply_token, result["text"], result["quick_reply"])
                else:
                    # 其他情況：直接處理字符串返回
                    reply_text(reply_token, result)
            else:
                # 情況 2: 不帶 status 參數 (來自 Flex 主按鈕)，重新顯示詳情+QuickReply
                logger.info(f"收到修改狀態請求 (無 status)，重新顯示詳情: trip_id={trip_id}")
                try:
                    # 需要重新查詢詳情並獲取 Flex 和 QuickReply
                    from modules.services.trip_detail_service import handle_trip_details_flex
                    from linebot.v3.messaging import FlexMessage, FlexContainer, QuickReply as LineQuickReply # 避免命名衝突
                    
                    result_data, error_message = handle_trip_details_flex(trip_id)
                    
                    if result_data and 'flex_message' in result_data and 'quick_reply' in result_data:
                        flex_content = result_data['flex_message']
                        quick_reply_dict = result_data['quick_reply']
                        
                        # 重新構造 Flex Message 對象
                        flex_msg_obj = FlexMessage(
                            alt_text=f"班次 #{trip_id} 詳細信息",
                            contents=FlexContainer.from_dict(flex_content),
                            quick_reply=LineQuickReply.from_dict(quick_reply_dict) # 從字典創建 QuickReply
                        )
                        reply_message(reply_token, [flex_msg_obj])
                    elif error_message:
                         reply_text(reply_token, f"無法獲取班次詳情: {error_message}")
                    else:
                         reply_text(reply_token, "無法獲取班次詳情以提供狀態修改選項。")
                         
                except Exception as e:
                    logger.error(f"重新顯示班次詳情時出錯: {e}")
                    traceback.print_exc()
                    reply_text(reply_token, "處理修改狀態請求時出錯。")
            
        else:
            # 對於其他未知 postback 或缺少參數的 update_status，給出提示
            logger.warning(f"收到未知的 postback 或缺少參數: {postback_data}")
            reply_text(reply_token, f"收到未知的操作請求: {postback_data}")
            
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