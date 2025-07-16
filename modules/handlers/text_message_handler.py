# modules/handlers/text_message_handler.py
import traceback
import logging
from flask import current_app
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.helpers import parse_date_input

from modules.utils.line_bot import (
    reply_text, reply_message, reply_flex,
    create_postback_action, create_message_action,
    create_flex_message, get_line_bot_api
)
from modules.handlers.trip_handler import handle_query_trips, handle_trip_details, handle_change_status, handle_record_fare, handle_modify_category, handle_completed_trip_details
from modules.flex_designs.help_flex import get_help_flex
from modules.handlers.temp_booking_handler import (
    handle_temp_booking_start,
    handle_temp_booking_message,
    temp_booking_states,
    handle_temp_booking_help
)
from modules.handlers.sequence_fix_handler import (
    handle_sequence_fix_start,
    handle_sequence_fix_message,
    sequence_fix_states
)
from modules.services.driver_service import handle_driver_assign_request, handle_driver_assign_select, handle_driver_assign_confirm, handle_driver_assign_cancel

# AI功能導入
from modules.services.smart_assistant import process_with_smart_assistant, format_smart_response

# 設定日誌
logger = logging.getLogger(__name__)

def process_text_message(event):
    """處理文本消息的主函數"""
    # 傳入的 event.message.text 應該是已經過 webhook.py 處理的文本
    message_text = event.message.text 
    reply_token = event.reply_token
    
    # 🚨 修復：安全獲取user_id，避免Source沒有user_id屬性的錯誤
    try:
        user_id = event.source.user_id if hasattr(event.source, 'user_id') else None
        if not user_id:
            logger.warning(f"無法獲取user_id，Source類型: {type(event.source)}")
            return
    except Exception as e:
        logger.error(f"獲取user_id時出錯: {e}")
        return
    
    # 記錄將要處理的文本
    command_text_lower = message_text.strip().lower()
    logger.info(f"Processing text message handed over: '{message_text}' (Normalized: '{command_text_lower}')") 
    
    try:
        # 檢查用戶是否在序列修復流程中
        if user_id in sequence_fix_states:
            logger.info(f"用戶 {user_id} 在序列修復流程中，處理消息: {message_text}")
            response = handle_sequence_fix_message(user_id, message_text)
            
            if response:
                reply_text(reply_token, response.get("text", "處理中..."))
            return
        
        # 檢查用戶是否在臨時預約流程中
        if user_id in temp_booking_states:
            # 處理臨時預約消息
            logger.info(f"用戶 {user_id} 在臨時預約流程中，處理消息: {message_text}")
            response = handle_temp_booking_message(user_id, message_text)
            
            if response:
                # 根據回傳的消息類型發送回覆
                    if response.get("type") == "flex":
                        try:
                            # 如果有Quick Reply，使用它
                            if "quick_reply" in response:
                                from linebot.v3.messaging import FlexMessage, FlexContainer
                                
                                # 添加日志记录
                                logger.info(f"臨時預約中帶有QuickReply: {response.get('quick_reply')}")
                                
                                # 更簡單地創建FlexMessage
                                flex_message = {
                                    "type": "flex",
                                    "altText": response.get("alt_text", "預約流程"),
                                    "contents": response.get("contents"),
                                    "quickReply": response.get("quick_reply")
                                }
                                
                                # 發送帶有Quick Reply的Flex消息
                                logger.info("嘗試發送帶有QuickReply的臨時預約Flex消息")
                                reply_message(reply_token, [flex_message])
                                logger.info("臨時預約Flex消息發送成功")
                            else:
                                # 沒有Quick Reply，使用普通的reply_flex
                                reply_flex(reply_token, response.get("alt_text", "預約流程"), response.get("contents"))
                        except Exception as e:
                            logger.error(f"發送Flex消息時出錯: {e}")
                            traceback.print_exc()
                            # 使用文本版本作為後備
                            if "text" in response:
                                reply_text(reply_token, response.get("text"))
                            else:
                                reply_text(reply_token, "處理中...")
                    else:
                        reply_text(reply_token, response.get("text", "處理中..."))
            return
        
        # 檢查用戶是否在批量加成流程中
        from modules.handlers.batch_allowance_handler import batch_allowance_states, handle_batch_allowance_message
        if user_id in batch_allowance_states:
            # 處理批量加成消息
            logger.info(f"用戶 {user_id} 在批量加成流程中，處理消息: {message_text}")
            response = handle_batch_allowance_message(user_id, message_text)
            
            if response:
                reply_text(reply_token, response.get("text", "處理中..."))
            return
        
        # 臨時預約命令
        if command_text_lower == "預約叫車":
            logger.info(f"用戶 {user_id} 請求 預約叫車 (AI流程)")
            response = handle_temp_booking_start(user_id)
            
            if response:
                if response.get("type") == "flex":
                    try:
                        # 如果有Quick Reply，使用它
                        if "quick_reply" in response:
                            from linebot.v3.messaging import FlexMessage, FlexContainer
                            
                            # 添加日志记录
                            logger.info(f"處理帶有QuickReply的請求: {response.get('quick_reply')}")
                            
                            # 更簡單地創建FlexMessage
                            flex_message = {
                                "type": "flex",
                                "altText": response.get("alt_text", "臨時預約"),
                                "contents": response.get("contents"),
                                "quickReply": response.get("quick_reply")
                            }
                            
                            # 發送帶有Quick Reply的Flex消息
                            logger.info("嘗試發送帶有QuickReply的Flex消息")
                            reply_message(reply_token, [flex_message])
                            logger.info("Flex消息發送成功")
                        else:
                            # 沒有Quick Reply，使用普通的reply_flex
                            reply_flex(reply_token, response.get("alt_text", "臨時預約"), response.get("contents"))
                    except Exception as e:
                        logger.error(f"發送Flex消息時出錯: {e}")
                        traceback.print_exc()
                        # 使用文本版本作為後備
                        if "text" in response:
                            reply_text(reply_token, response.get("text"))
                        else:
                            reply_text(reply_token, "開始臨時預約流程...")
                else:
                    reply_text(reply_token, response.get("text", "開始臨時預約流程..."))
            return
        
        # 序列修復命令
        elif command_text_lower == "fix-sequence":
            logger.info(f"用戶 {user_id} 請求序列修復")
            response = handle_sequence_fix_start(user_id)
            
            if response:
                reply_text(reply_token, response.get("text", "檢查序列中..."))
            return
        
        # 批量加成命令
        elif command_text_lower == "batch-allowance" or command_text_lower == "批量加成":
            logger.info(f"用戶 {user_id} 請求批量加成")
            from modules.handlers.batch_allowance_handler import handle_batch_allowance_start
            response = handle_batch_allowance_start(user_id)
            
            if response:
                reply_text(reply_token, response.get("text", "啟動批量加成中..."))
            return
        
        # 東洋班次 (東洋/臨時)
        elif message_text.startswith("東洋班次"):
            try:
                parts = message_text.split()
                # --- 修改：如果帶有日期參數，則執行查詢；否則觸發日期選擇 --- 
                if len(parts) > 1:
                    # 執行實際查詢 (東洋/臨時)
                    logger.info(f"處理東洋班次命令 (帶日期): {message_text}")
                    from modules.services.trip_query_service import handle_query_trips_flex
                    flex_content, result_message = handle_query_trips_flex(message_text)
                    logger.info(f"handle_query_trips_flex返回: flex={bool(flex_content)}, msg='{result_message}'")
                    if flex_content:
                        reply_flex(reply_token, "班次查詢結果", flex_content)
                    elif result_message:
                        reply_text(reply_token, result_message)
                    else:
                        reply_text(reply_token, "查詢完成，但沒有找到任何信息。")
                else:
                    # 觸發日期選擇
                    logger.info(f"處理東洋班次命令 (觸發日期選擇): {message_text}")
                    from modules.services.trip_query_service import request_toyo_temp_trip_date_selection
                    reply_msg, error_message = request_toyo_temp_trip_date_selection()
                    if reply_msg and error_message is None:
                        reply_message(reply_token, [reply_msg])
                    else:
                        reply_text(reply_token, error_message or "無法生成日期選擇")
                return 
            except Exception as e:
                logger.error(f"處理東洋班次時出錯: {e}")
                traceback.print_exc()
                # 使用文本版本作為後備
                from modules.services.trip_query_service import handle_query_trips
                result = handle_query_trips(message_text)
                reply_text(reply_token, f"Flex消息處理錯誤，使用文本版本：\n{result}")
                return
            
        # 班次詳情
        elif message_text.startswith("班次詳情"):
            parts = message_text.split()
            if len(parts) >= 2:
                try:
                    trip_id = int(parts[1])
                    # 确保导入正确的函数
                    from modules.services.trip_detail_service import handle_trip_details_flex
                    
                    # 记录日志便于调试
                    current_app.logger.info(f"处理班次详情: {trip_id}")
                    
                    # 🚨 新增：記錄班次ID到上下文（用於簡單請假格式）
                    try:
                        from modules.utils.conversation_context import conversation_manager
                        conversation_manager.set_recent_trip_id(user_id, trip_id)
                    except Exception as context_error:
                        logger.error(f"記錄班次ID到上下文時出錯: {context_error}")
                    
                    result, error_message = handle_trip_details_flex(trip_id)
                    
                    if result and 'flex_message' in result:
                        current_app.logger.info("获取到Flex内容，准备发送")
                        
                        try:
                            from linebot.v3.messaging import FlexMessage, FlexContainer, QuickReply, QuickReplyItem, PostbackAction
                            
                            flex_message_content = result['flex_message']
                            quick_reply_data = result.get('quick_reply') # 使用 .get() 以安全處理 None

                            quick_reply_obj = None
                            if quick_reply_data and isinstance(quick_reply_data, dict) and 'items' in quick_reply_data and isinstance(quick_reply_data['items'], list):
                                quick_reply_items = []
                                for item_data in quick_reply_data['items']:
                                    action_data = item_data.get('action')
                                    if action_data and isinstance(action_data, dict):
                                        quick_reply_items.append(
                                            QuickReplyItem(
                                                action=PostbackAction(
                                                    label=action_data.get('label'),
                                                    data=action_data.get('data'),
                                                    display_text=action_data.get('displayText')
                                                )
                                            )
                                        )
                                if quick_reply_items: # 只有當 items 列表不為空時才創建 QuickReply 物件
                                    quick_reply_obj = QuickReply(items=quick_reply_items)
                            
                            flex_message = FlexMessage(
                                alt_text=f"班次 #{trip_id} 詳細信息",
                                contents=FlexContainer.from_dict(flex_message_content),
                                quick_reply=quick_reply_obj # quick_reply_obj 可能為 None
                            )
                            
                            reply_message(reply_token, [flex_message])
                            current_app.logger.info("成功发送Flex Message (班次詳情)") # 更新日誌
                            return
                        except Exception as flex_error:
                            current_app.logger.error(f"发送Flex Message時出錯: {flex_error}")
                            traceback.print_exc()
                            # 如果发送Flex失败，使用文本版本
                        
                    # 如果没有Flex内容或者发送失败，使用文本版本
                    if error_message:
                        reply_text(reply_token, error_message)
                    else:
                        from modules.handlers.trip_handler import handle_trip_details
                        result_text = handle_trip_details(trip_id)
                        reply_text(reply_token, result_text)
                except ValueError:
                    reply_text(reply_token, "班次ID必須是數字。")
                except Exception as e:
                    current_app.logger.error(f"处理班次详情时出错: {e}")
                    traceback.print_exc()
                    reply_text(reply_token, f"查询班次详情失败: {str(e)}")
            else:
                reply_text(reply_token, "请提供班次ID，例如：班次详情 123")
            return
            
        # 司機指派相關命令
        # 指派司機請求
        elif message_text.startswith('指派司機') and len(message_text.split()) == 2:
            try:
                trip_id = int(message_text.split()[1])
                logger.info(f"處理指派司機請求: {trip_id}")
                
                # 修改：調用 handle_driver_assign_request，預期返回消息字典或 None
                message_to_send, error_message = handle_driver_assign_request(trip_id)
                
                if message_to_send and error_message is None:
                    # 發送帶 Quick Reply 的文本消息
                    # 假設 reply_message 能處理字典格式的消息
                    logger.info(f"準備發送司機選擇 Quick Reply 消息: {message_to_send}")
                    reply_message(reply_token, [message_to_send])
                    logger.info("司機選擇 Quick Reply 消息已發送")
                else:
                    # 發送錯誤消息
                    reply_text(reply_token, error_message or "無法載入司機列表")
                
                return
            except ValueError:
                reply_text(reply_token, "班次ID必須是數字。")
                return
            except Exception as e:
                logger.error(f"處理指派司機請求時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理指派司機請求失敗: {str(e)}")
                return
        
        # 簡化版指派司機指令 - 支持"指派 2307"格式
        elif message_text.startswith('指派 ') and len(message_text.split()) == 2:
            try:
                trip_id = int(message_text.split()[1])
                logger.info(f"處理簡化指派司機請求: {trip_id}")
                
                # 修改：調用 handle_driver_assign_request，預期返回消息字典或 None
                message_to_send, error_message = handle_driver_assign_request(trip_id)
                
                if message_to_send and error_message is None:
                    # 發送帶 Quick Reply 的文本消息
                    logger.info(f"準備發送司機選擇 Quick Reply 消息 (簡化): {message_to_send}")
                    reply_message(reply_token, [message_to_send])
                    logger.info("司機選擇 Quick Reply 消息已發送 (簡化)")
                else:
                    # 發送錯誤消息
                    reply_text(reply_token, error_message or "無法載入司機列表")
                
                return
            except ValueError:
                reply_text(reply_token, "班次ID必須是數字。")
                return
            except Exception as e:
                logger.error(f"處理簡化指派司機請求時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理指派司機請求失敗: {str(e)}")
                return
        
        # 選擇司機
        elif message_text.startswith('指派司機 ') and len(message_text.split()) == 3:
            try:
                parts = message_text.split()
                trip_id = int(parts[1])
                driver_id = int(parts[2])
                
                logger.info(f"處理司機選擇: 班次={trip_id}, 司機={driver_id}")
                
                result, error_message = handle_driver_assign_select(trip_id, driver_id)
                
                if result and error_message is None:
                    # 檢查返回結果是否包含 flex_message 和 quick_reply
                    if isinstance(result, dict) and 'flex_message' in result and 'quick_reply' in result:
                        # 發送包含 Quick Reply 的確認界面
                        try:
                            from linebot.v3.messaging import FlexMessage, FlexContainer
                            
                            flex_message = FlexMessage(
                                alt_text="確認指派司機",
                                contents=FlexContainer.from_dict(result['flex_message']),
                                quick_reply=result['quick_reply']
                            )
                            
                            reply_message(reply_token, [flex_message])
                            logger.info("成功發送確認指派司機的 Flex Message 與 Quick Reply")
                        except Exception as flex_error:
                            logger.error(f"發送確認指派司機 Flex Message 時出錯: {flex_error}")
                            traceback.print_exc()
                            # 發送文本版本作為後備
                            reply_text(reply_token, "無法顯示確認界面，請直接輸入：確認指派 [班次ID] [司機ID] 或 取消指派 [班次ID]")
                    else:
                        # 兼容舊格式，直接發送 Flex Message
                        reply_flex(reply_token, "確認指派司機", result)
                else:
                    # 發送錯誤消息
                    reply_text(reply_token, error_message or "無法載入確認界面")
                
                return
            except ValueError:
                reply_text(reply_token, "班次ID和司機ID必須是數字。")
                return
            except Exception as e:
                logger.error(f"處理司機選擇時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理司機選擇失敗: {str(e)}")
                return
        
        # 確認指派
        elif message_text.startswith('確認指派 ') and len(message_text.split()) == 3:
            try:
                parts = message_text.split()
                trip_id = int(parts[1])
                driver_id = int(parts[2])
                
                logger.info(f"處理確認指派: 班次={trip_id}, 司機={driver_id}")
                
                result = handle_driver_assign_confirm(trip_id, driver_id)
                reply_text(reply_token, result)
                return
            except ValueError:
                reply_text(reply_token, "班次ID和司機ID必須是數字。")
                return
            except Exception as e:
                logger.error(f"處理確認指派時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理確認指派失敗: {str(e)}")
                return
        
        # 取消指派
        elif message_text.startswith('取消指派 '):
            try:
                parts = message_text.split()
                if len(parts) == 2:
                    trip_id = int(parts[1])
                    
                    logger.info(f"處理取消指派: 班次={trip_id}")
                    
                    result = handle_driver_assign_cancel(trip_id)
                    reply_text(reply_token, result)
                    return
                else:
                    reply_text(reply_token, "取消指派命令格式不正確。正確格式：取消指派 [班次ID]")
                    return
            except ValueError:
                reply_text(reply_token, "班次ID必須是數字。")
                return
            except Exception as e:
                logger.error(f"處理取消指派時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理取消指派失敗: {str(e)}")
                return
            
        # 幫助（Flex Message版本）
        elif message_text == '幫助':
            try:
                logger.info("處理幫助命令")
                help_flex = get_help_flex()
                logger.info(f"獲取到幫助Flex: {type(help_flex)}")
                
                # 记录完整的flex内容便于调试
                logger.info(f"幫助Flex內容: {help_flex}")
                
                if help_flex:
                    try:
                        # 使用正確導入的reply_flex函數
                        logger.info("嘗試发送Flex消息")
                        reply_flex(reply_token, "幫助信息", help_flex)
                        logger.info("Flex消息已发送")
                        return
                    except Exception as flex_error:
                        logger.error(f"發送Flex消息時出錯: {flex_error}")
                        traceback.print_exc()
                        # 如果发送Flex失败，使用文本版本
                        help_text = get_help_text()
                        reply_text(reply_token, f"無法顯示圖形幫助菜單: {str(flex_error)}\n\n{help_text}")
                        return
                else:
                    # 如果無法獲取Flex消息，使用文本版本
                    logger.error("獲取幫助Flex失敗，使用文本版本")
                    help_text = get_help_text()
                    reply_text(reply_token, help_text)
                    return
            except Exception as e:
                logger.error(f"處理幫助命令時出錯: {e}")
                traceback.print_exc()
                # 使用文本版本作為後備
                help_text = get_help_text()
                reply_text(reply_token, f"無法顯示圖形幫助菜單，使用文本版本：\n\n{help_text}")
                return
            
        # 幫助（文字版本）
        elif message_text == '幫助文字':
            help_text = get_help_text()
            reply_text(reply_token, help_text)
            return
            
        # 完整指令列表
        elif message_text == '完整指令':
            from modules.flex_designs.help_flex import get_complete_commands_help
            help_flex = get_complete_commands_help()
            reply_flex(reply_token, "完整指令列表", help_flex)
            return
            
        # 處理匯入固定班次（一整周）
        elif message_text.startswith("匯入固定班次"):
            from modules.handlers.import_handler import handle_import_fixed_trips_week
            result_text = handle_import_fixed_trips_week(message_text)
            reply_text(reply_token, result_text)
            return
            
        # 處理清理trips功能
        elif message_text.startswith("清理trips"):
            from modules.handlers.cleanup_handler import handle_cleanup_trips
            result_text = handle_cleanup_trips(message_text)
            reply_text(reply_token, result_text)
            return
            
        # 診所班次 (Handles "診所班次" and "診所班次 [date]")
        elif message_text.startswith("診所班次"):
            try:
                parts = message_text.split()
                if len(parts) > 1:
                    logger.info(f"處理診所班次命令 (帶日期): {message_text}")
                    from modules.services.trip_query_service import handle_query_clinic_trips_flex
                    
                    flex_content, message = handle_query_clinic_trips_flex(message_text) 

                    if flex_content: # Trips found, send Flex
                        logger.info(f"找到診所班次，發送 Flex Message")
                        reply_flex(reply_token, "診所班次查詢結果", flex_content)
                    else: # No trips found OR error occurred
                         # --- FIX: Directly use the message returned by the service --- 
                         logger.info(f"診所班次查詢無結果或發生錯誤，發送消息: {message}")
                         reply_text(reply_token, message or "查詢診所班次時發生未知錯誤。") # Send the message directly
                         # --- END FIX --- 

                else: # "診所班次" without date
                    logger.info(f"處理診所班次命令 (觸發日期選擇): {message_text}")
                    from modules.services.trip_query_service import request_clinic_trip_date_selection
                    reply_msg, error_message = request_clinic_trip_date_selection()
                    if reply_msg and error_message is None:
                        reply_message(reply_token, [reply_msg]) 
                    else:
                        reply_text(reply_token, error_message or "無法生成日期選擇")
                return 
            except Exception as e:
                logger.error(f"處理診所班次命令時出錯: {e}", exc_info=True)
                reply_text(reply_token, f"處理請求時出錯: {str(e)}")
                return
        
        # 更新已完成班次
        elif message_text == "更新已完成班次":
            from modules.services.scheduler_service import update_completed_trips
            result_text = update_completed_trips()
            reply_text(reply_token, result_text)
            return
            
        # 🔥 新增：查詢班次命令 - 支援複雜條件
        elif message_text.startswith("查詢班次"):
            try:
                logger.info(f"🔍 處理查詢班次命令: {message_text}")
                from modules.services.advanced_query_processor import AdvancedQueryProcessor
                
                # 使用高級查詢處理器
                processor = AdvancedQueryProcessor()
                result = processor.process_complex_query(message_text, user_id)
                
                if result["type"] == "success":
                    reply_text(reply_token, result["message"])
                elif result["type"] == "invalid_status":
                    reply_text(reply_token, result["message"])
                elif result["type"] == "no_results":
                    reply_text(reply_token, result["message"]) 
                elif result["type"] == "error":
                    reply_text(reply_token, result["message"])
                elif result["type"] == "fallback":
                    # 回退到傳統處理
                    reply_text(reply_token, "⚠️ 查詢格式複雜，請使用更具體的命令")
                else:
                    reply_text(reply_token, "🤖 查詢處理中...")
                    
                return
            except Exception as e:
                logger.error(f"❌ 處理查詢班次命令時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"查詢班次失敗: {str(e)}")
                return
            
        # --- 修改：查詢已完成班次 --- 
        elif message_text.startswith("查已完成"):
            try:
                logger.info(f"🔍 處理查已完成命令: {message_text}")
                from modules.services.advanced_query_processor import AdvancedQueryProcessor
                
                # 🔥 修復：使用高級查詢處理器（包含總和計算功能）
                processor = AdvancedQueryProcessor()
                result = processor.process_complex_query(message_text, user_id)
                
                if result["type"] == "success":
                    reply_text(reply_token, result["message"])
                elif result["type"] == "invalid_status":
                    reply_text(reply_token, result["message"])
                elif result["type"] == "no_results":
                    reply_text(reply_token, result["message"]) 
                elif result["type"] == "error":
                    reply_text(reply_token, result["message"])
                elif result["type"] == "fallback":
                    # 回退到傳統處理
                    from modules.services.trip_query_service import handle_query_completed_trips
                    result_text = handle_query_completed_trips(message_text)
                    reply_text(reply_token, result_text)
                else:
                    reply_text(reply_token, "🤖 查詢處理中...")
                    
                return
            except Exception as e:
                logger.error(f"❌ 處理查已完成命令時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"查詢失敗: {str(e)}")
                return
        # --- 結束修改 ---
            
        # 生成周報表
        elif message_text.startswith("生成周報表") or message_text.startswith("生成週報表") or message_text.startswith("生成周報") or message_text.startswith("生成週報"):
            try:
                logger.info(f"處理生成周報表命令: {message_text}")
                from modules.services.report_service import handle_generate_weekly_report
                
                # 調用報表生成函數
                result = handle_generate_weekly_report(message_text)
                reply_text(reply_token, result)
                return
            except Exception as e:
                logger.error(f"處理生成周報表時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"生成報表失敗: {str(e)}")
                return
        
        # 生成月報表
        elif message_text.startswith("生成月報表") or message_text.startswith("生成月報"):
            try:
                logger.info(f"處理生成月報表命令: {message_text}")
                from modules.services.report_service import handle_generate_monthly_report
                
                # 調用報表生成函數
                result = handle_generate_monthly_report(message_text)
                reply_text(reply_token, result)
                return
            except Exception as e:
                logger.error(f"處理生成月報表時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"生成月報表失敗: {str(e)}")
                return
        
        # 班次詳情的簡寫命令
        elif message_text.startswith("班次"):
            parts = message_text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                # 格式是「班次 123」，當作「班次詳情 123」處理
                trip_id = int(parts[1])
                logger.info(f"簡寫命令，處理為班次詳情: {trip_id}")
                # 修改message_text為完整命令，繼續處理
                message_text = f"班次詳情 {trip_id}"
                # 不要return，讓代碼繼續執行
            
        # --- 新增：修改類別 --- 
        elif message_text.startswith("修改類別"):
             result = handle_modify_category(message_text)
             reply_text(reply_token, result)
             return
        # --- 結束新增 ---
            
        # --- 新增：記錄車資 --- 
        elif message_text.startswith("記錄車資"):
             result = handle_record_fare(message_text, user_id)
             reply_text(reply_token, result)
             return
        # --- 結束新增 ---
        
        # --- 新增：固定班表查詢功能 ---
        elif message_text.startswith("固定班表"):
            from modules.handlers.fixed_schedule_query_handler import handle_fixed_schedule_query
            result = handle_fixed_schedule_query(message_text, user_id)
            
            # 檢查回傳的結果類型
            if isinstance(result, dict) and result.get("type") == "quick_reply":
                # 發送帶有 Quick Reply 的訊息
                try:
                    reply_message(reply_token, [result])
                    logger.info("成功發送固定班表查詢的 Quick Reply 訊息")
                except Exception as e:
                    logger.error(f"發送固定班表查詢 Quick Reply 訊息失敗: {e}")
                    # 降級為純文字
                    reply_text(reply_token, result.get("text", "查詢失敗"))
            else:
                # 純文字回應
                reply_text(reply_token, result)
            return
        
        # --- 新增：固定班次請假功能 ---
        elif message_text.startswith("固定班次#") and message_text.endswith("請假"):
            # 處理固定班次#ID請假的交互模式
            import re
            match = re.match(r"固定班次#(\d+)請假", message_text)
            if match:
                schedule_id = match.group(1)
                # 記錄固定班次ID到上下文（用於簡化請假格式）
                try:
                    from modules.utils.conversation_context import conversation_manager
                    conversation_manager.set_recent_fixed_schedule_id(user_id, int(schedule_id))
                    # 🔧 修正：設置請假模式標記，允許簡單請假格式
                    conversation_manager.set_leave_mode(user_id=user_id, trip_id=int(schedule_id))
                    logger.info(f"設置用戶 {user_id} 進入固定班次請假模式，固定班次 #{schedule_id}")
                except Exception as context_error:
                    logger.error(f"記錄固定班次ID到上下文或設置請假模式時出錯: {context_error}")
                
                # 提供交互提示（類似乘客請假）
                reply_text(reply_token, f"固定班次 #{schedule_id} 乘客長期請假\n\n請輸入：[原因] [加成]\n\n例如：\n診所乘客長期住院 -50\n出國一個月 0\n搬家不再需要 -100\n\n💡 提示：先寫原因，最後寫加成金額")
                return
        
        elif message_text.startswith("固定班次請假"):
            from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave_command
            result = handle_fixed_schedule_leave_command(message_text, user_id)
            reply_text(reply_token, result)
            return
            
        elif message_text.startswith("固定班次恢復"):
            from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_restore_command
            result = handle_fixed_schedule_restore_command(message_text, user_id)
            reply_text(reply_token, result)
            return
        # --- 結束新增 ---
        
        # --- AI修改確認處理（保持原格式，但照搬預約叫車邏輯）---
        elif message_text.startswith("確認AI修改"):
            try:
                # 🔥 兼容模式：既支持上下文，也支持命令參數
                from modules.utils.conversation_context import conversation_manager
                pending_modification = conversation_manager.get_pending_modification(user_id)
                
                # 解析確認命令的參數
                parts = message_text.split()
                
                if len(parts) >= 4:
                    # 用戶提供了完整的確認參數
                    trip_id = int(parts[1])
                    new_meter = int(parts[2])
                    new_extra = int(parts[3])
                    reason = " ".join(parts[4:]) if len(parts) > 4 else "AI智能修改"
                    logger.info(f"🔧 從確認命令解析參數: trip_id={trip_id}, meter={new_meter}, extra={new_extra}, reason='{reason}'")
                elif pending_modification:
                    # 從上下文獲取參數
                    trip_id = pending_modification['trip_id']
                    new_meter = pending_modification['meter_fare']
                    new_extra = pending_modification['extra_fare']
                    reason = pending_modification.get('reason', 'AI智能修改')
                    logger.info(f"🔧 從上下文獲取參數: trip_id={trip_id}, meter={new_meter}, extra={new_extra}, reason='{reason}'")
                else:
                    reply_text(reply_token, "❌ 沒有待確認的修改操作，且確認命令格式不正確")
                    return
                
                logger.info(f"🔥 用戶確認AI修改，真正執行數據庫UPDATE: trip_id={trip_id}, meter={new_meter}, extra={new_extra}")
                
                # 🔥 照搬預約叫車：真正執行數據庫操作
                from modules.handlers.trip_handler import handle_record_fare
                modify_command = f"記錄車資 {trip_id} {new_meter} {new_extra} {reason}"
                
                result = handle_record_fare(modify_command, user_id=user_id)
                
                # 🔥 照搬預約叫車：清除待確認狀態（如果存在的話）
                if pending_modification:
                    conversation_manager.clear_pending_modification(user_id)
                
                # 🔥 照搬預約叫車：返回成功消息
                if "需要說明原因" in result or "修改原因" in result:
                    reply_text(reply_token, f"❌ 修改被系統拒絕：{result}")
                else:
                    # 修改成功，重新查詢班次信息以獲取完整數據
                    from modules.models.base import db
                    from sqlalchemy import text
                    
                    try:
                        # 查詢已完成班次的完整信息
                        completed_trip_query = """
                        SELECT start_point, end_point, driver_id, category, meter_fare, extra_fare
                        FROM completed_trips 
                        WHERE id = :trip_id
                        """
                        completed_result = db.session.execute(text(completed_trip_query), {'trip_id': trip_id}).fetchone()
                        
                        if completed_result:
                            # 使用實際的班次數據
                            start_point, end_point, driver_id, category, old_meter, old_extra = completed_result
                            success_info = {
                                'trip_id': trip_id,
                                'category': category or '未分類',
                                'route': f"{start_point or '?'} → {end_point or '?'}",
                                'driver_id': driver_id or 'N/A',
                                'old_meter': old_meter or 0,
                                'old_extra': old_extra or 0,
                                'new_meter': new_meter,
                                'new_extra': new_extra,
                                'total_change': (new_meter + new_extra) - ((old_meter or 0) + (old_extra or 0)),
                                'reason': reason,
                                'success': True
                            }
                        else:
                            # 如果查詢失敗，使用基本信息
                            success_info = {
                                'trip_id': trip_id,
                                'category': '未分類',
                                'route': '? → ?',
                                'driver_id': 'N/A',
                                'old_meter': 0,
                                'old_extra': 0,
                                'new_meter': new_meter,
                                'new_extra': new_extra,
                                'total_change': 0,
                                'reason': reason,
                                'success': True
                            }
                    except Exception as query_error:
                        logger.error(f"查詢班次信息失敗: {query_error}")
                        # 降級為基本信息
                        success_info = {
                            'trip_id': trip_id,
                            'category': '未分類',
                            'route': '? → ?',
                            'driver_id': 'N/A',
                            'old_meter': 0,
                            'old_extra': 0,
                            'new_meter': new_meter,
                            'new_extra': new_extra,
                            'total_change': 0,
                            'reason': reason,
                            'success': True
                        }
                    
                    # 顯示成功界面
                    from modules.flex_designs.ai_fare_query_flex import create_ai_modification_result_flex
                    
                    flex_result = create_ai_modification_result_flex(success_info)
                    if flex_result and isinstance(flex_result, dict) and 'flex_message' in flex_result:
                        try:
                            from linebot.v3.messaging import FlexMessage, FlexContainer
                            
                            flex_message = FlexMessage(
                                alt_text=flex_result.get("alt_text", "AI修改完成"),
                                contents=FlexContainer.from_dict(flex_result['flex_message']),
                                quick_reply=flex_result.get('quick_reply')
                            )
                            
                            reply_message(reply_token, [flex_message])
                            logger.info("✅ 成功發送AI修改完成的 Flex Message")
                        except Exception as flex_error:
                            logger.error(f"發送AI修改完成 Flex Message失敗: {flex_error}")
                            reply_text(reply_token, f"✅ AI修改執行成功\n\n📋 班次：#{trip_id}\n💰 新費用：{new_meter}+{new_extra} = {new_meter + new_extra}元\n📝 原因：{reason}\n\n{result}")
                    else:
                        reply_text(reply_token, f"✅ AI修改執行成功\n\n📋 班次：#{trip_id}\n💰 新費用：{new_meter}+{new_extra} = {new_meter + new_extra}元\n📝 原因：{reason}\n\n{result}")
                
            except Exception as e:
                logger.error(f"處理AI修改確認時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, "❌ 處理確認時出錯")
            return
        
        # 取消AI修改
        elif message_text == "取消AI修改":
            try:
                # 完全重置用戶的對話上下文
                from modules.utils.conversation_context import conversation_manager
                conversation_manager.reset_context(user_id)
                
                logger.info(f"用戶 {user_id} 取消AI修改，已重置對話上下文")
                
                # 🔥 簡化：直接使用可靠的文字反饋，確保用戶一定能看到
                reply_text(reply_token, "✅ 取消修改流程\n\n🔒 數據庫未被修改，您可以重新發起命令。")
                    
            except Exception as e:
                logger.error(f"處理取消AI修改時出錯: {e}")
                reply_text(reply_token, "✅ 取消修改流程")
            return
        # --- 結束新增 ---
            
        # 🔥 新增：翻頁功能 - "更多"命令處理
        elif message_text in ["更多", "下一頁", "更多結果"]:
            try:
                logger.info(f"🔄 處理翻頁命令: {message_text}")
                from modules.utils.conversation_context import get_conversation_context
                
                context = get_conversation_context(user_id)
                next_page_result = context.get_next_page()
                
                if next_page_result:
                    reply_text(reply_token, next_page_result)
                else:
                    reply_text(reply_token, "💡 沒有更多結果或會話已過期\n\n請重新執行查詢命令")
                return
            except Exception as e:
                logger.error(f"❌ 處理翻頁命令時出錯: {e}")
                reply_text(reply_token, "翻頁功能暫時不可用，請重新查詢")
                return
            
        # --- 🤖 智能助手系統整合 ---
        # 優先嘗試智能助手處理
        try:
            logger.info(f"🤖 智能助手處理用戶訊息: {message_text}")
            smart_result = process_with_smart_assistant(message_text, user_id)
            
            if smart_result["type"] == "execute_command":
                command = smart_result["command"]
                
                # 🔥 新增：統計金額命令處理
                if command.startswith("統計金額") or (command.startswith("查已完成") and any(k in command for k in ['總和', '總計', '統計', '金額總和'])):
                    try:
                        from modules.services.advanced_query_processor import AdvancedQueryProcessor
                        processor = AdvancedQueryProcessor()
                        
                        # 強制設為聚合查詢
                        if command.startswith("查已完成"):
                            command = command.replace("查已完成", "統計金額", 1)
                        
                        result = processor.process_complex_query(command, user_id)
                        
                        if result.get('type') == 'aggregation_success':
                            reply_text(reply_token, result['message'])
                            return
                        elif result.get('type') == 'no_results':
                            reply_text(reply_token, result['message'])
                            return
                        else:
                            logger.error(f"統計金額處理失敗: {result}")
                    except Exception as e:
                        logger.error(f"統計金額命令執行失敗: {e}")
                        reply_text(reply_token, f"❌ 統計金額執行失敗：{str(e)}")
                        return
                
                # 🔧 修復無限遞歸：直接執行命令而不是改變message_text
                logger.info(f"🎯 智能助手生成命令: {command}")
                logger.info(f"✅ 智能助手解析成功，執行命令: {command}")
                
                # 🔥 直接執行命令，不要改變message_text避免無限遞歸
                if command.startswith("查已完成"):
                    from modules.services.advanced_query_processor import AdvancedQueryProcessor
                    processor = AdvancedQueryProcessor()
                    result = processor.process_complex_query(command, user_id)
                    
                    if result.get('type') == 'success':
                        reply_text(reply_token, result['message'])
                    elif result.get('type') == 'no_results':
                        reply_text(reply_token, result['message'])
                    else:
                        reply_text(reply_token, f"❌ 查詢執行失敗")
                    return
                
                elif command.startswith("查詢班次"):
                    from modules.services.advanced_query_processor import AdvancedQueryProcessor
                    processor = AdvancedQueryProcessor()
                    result = processor.process_complex_query(command, user_id)
                    
                    if result.get('type') == 'success':
                        reply_text(reply_token, result['message'])
                    elif result.get('type') == 'no_results':
                        reply_text(reply_token, result['message'])
                    else:
                        reply_text(reply_token, f"❌ 查詢執行失敗")
                    return
                
                # 🔥 修復：車資查詢命令整合 - 更精確的觸發條件
                elif any(keyword in command for keyword in ["車資", "錶價", "加成", "修改.*金額", "記錄.*費用"]):
                    # 只有明確的車資操作命令才調用車資AI服務
                    try:
                        from modules.services.ai_fare_service import handle_smart_fare_query
                        result = handle_smart_fare_query(message_text, user_id, use_flex=True)
                        
                        if isinstance(result, str):
                            reply_text(reply_token, result)
                        elif isinstance(result, dict) and 'flex_message' in result:
                            from linebot.v3.messaging import FlexMessage, FlexContainer
                            flex_message = FlexMessage(
                                alt_text=result.get("alt_text", "AI車資查詢結果"),
                                contents=FlexContainer.from_dict(result['flex_message']),
                                quick_reply=result.get('quick_reply')
                            )
                            reply_message(reply_token, [flex_message])
                        else:
                            reply_text(reply_token, result)
                        return
                    except Exception as e:
                        logger.error(f"車資查詢執行失敗: {e}")
                        reply_text(reply_token, f"❌ 車資查詢執行失敗：{str(e)}")
                        return
                
                else:
                    # 其他命令嘗試傳統處理
                    reply_text(reply_token, f"✅ 收到命令：{command}\n正在處理...")
                    return
                
            elif smart_result["type"] == "smart_guidance":
                # 智能助手提供引導
                guidance_text = format_smart_response(smart_result)
                logger.info(f"🎯 智能助手提供引導: {guidance_text}")
                reply_text(reply_token, guidance_text)
                return
                
            elif smart_result["type"] == "suggestions":
                # 智能助手提供建議
                suggestion_text = format_smart_response(smart_result)
                logger.info(f"💡 智能助手提供建議: {suggestion_text}")
                reply_text(reply_token, suggestion_text)
                return
                
        except Exception as smart_error:
            logger.error(f"智能助手處理失敗: {smart_error}")
            # 如果智能助手失敗，繼續使用傳統邏輯
            pass

        # --- 新增：查看已完成班次 ---
        if message_text.startswith("查看"):
            parts = message_text.split()
            if len(parts) >= 2:
                try:
                    completed_trip_id = int(parts[1])
                    logger.info(f"處理查看已完成班次: {completed_trip_id}")
                    
                    result = handle_completed_trip_details(completed_trip_id)
                    reply_text(reply_token, result)
                except ValueError:
                    reply_text(reply_token, "班次ID必須是數字。")
                except Exception as e:
                    logger.error(f"處理查看命令時出錯: {e}")
                    traceback.print_exc()
                    reply_text(reply_token, f"查詢失敗: {str(e)}")
            else:
                reply_text(reply_token, "請提供班次ID，例如：查看 123")
            return
        # --- 結束新增 ---
            
        # 未識別的命令 - 使用智能助手處理
        if True:  # 這裡會處理所有未識別的命令
            # 🚨 新增：檢測簡單請假格式（原因結尾加數字）
            # 🔧 修復：先排除已知的命令格式，避免誤判
            import re
            
            # 先檢查是否是已知的命令格式，避免誤判
            # 檢查「指派1585 5386」這種無效格式並提供正確提示
            invalid_assign_match = re.match(r'^指派(\d+)\s+(\d+)$', message_text.strip())
            if invalid_assign_match:
                trip_id = invalid_assign_match.group(1)
                driver_id = invalid_assign_match.group(2)
                reply_text(reply_token, f"❌ 指派命令格式不正確\n\n正確格式：\n• 指派 {trip_id} （觸發司機選擇）\n• 指派司機 {trip_id} {driver_id} （選擇司機）\n• 確認指派 {trip_id} {driver_id} （確認指派）\n\n💡 建議：使用「指派 {trip_id}」來選擇司機")
                return
            
            known_command_patterns = [
                r'^指派\s+\d+\s+\d+$',  # 指派 1585 5386
                r'^指派司機\s+\d+\s+\d+$',  # 指派司機 1585 5386
                r'^記錄車資\s+\d+\s+\d+\s+\d+',  # 記錄車資 ID 錶價 加成
                r'^修改類別\s+\d+\s+\w+$',  # 修改類別 ID 類別
                r'^查看\s+\d+$',  # 查看 ID
                r'^班次\s+\d+$',  # 班次 ID
                r'^班次詳情\s+\d+$',  # 班次詳情 ID
                r'^確認指派\s+\d+\s+\d+$',  # 確認指派 ID DRIVER_ID
                r'^取消指派\s+\d+$',  # 取消指派 ID
                r'^確認AI修改\s+\d+\s+\d+\s+\d+',  # 確認AI修改 ID 錶價 加成
            ]
            
            is_known_command = False
            for pattern in known_command_patterns:
                if re.match(pattern, message_text.strip()):
                    is_known_command = True
                    logger.info(f"檢測到已知命令格式: {pattern}, 跳過簡單請假格式檢測")
                    break
            
            if not is_known_command:
                # 只有在不是已知命令格式時，才檢測簡單請假格式
                simple_leave_pattern = r'^(.+)\s+(-?\d+)$'
                simple_leave_match = re.match(simple_leave_pattern, message_text.strip())
                
                if simple_leave_match:
                    reason = simple_leave_match.group(1)
                    amount = simple_leave_match.group(2)
                    
                    # 🔧 修正：只有在明確的請假模式下才允許簡單請假格式
                    from modules.utils.conversation_context import conversation_manager
                    is_in_leave_mode = conversation_manager.is_in_leave_mode(user_id)
                    
                    if is_in_leave_mode:
                        # 用戶在請假模式下，處理簡單請假格式
                        recent_trip_id = conversation_manager.get_recent_trip_id(user_id)
                        recent_fixed_schedule_id = conversation_manager.get_recent_fixed_schedule_id(user_id)
                        
                        logger.info(f"請假模式下的簡單請假格式 - 用戶: {user_id}, trips上下文: {recent_trip_id}, 固定班次上下文: {recent_fixed_schedule_id}, 輸入: '{message_text}'")
                        
                        if recent_trip_id:
                            # 處理一般班次請假
                            logger.info(f"檢測到簡單請假格式，班次ID: {recent_trip_id}, 加成: {amount}, 原因: {reason}")
                            
                            # 構造完整的乘客請假命令
                            full_command = f"乘客請假 {recent_trip_id} {amount} {reason}"
                            
                            try:
                                from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
                                result = handle_passenger_leave_command(full_command, user_id)
                                
                                # 處理完成後清除請假模式
                                conversation_manager.clear_leave_mode(user_id)
                                
                                reply_text(reply_token, result)
                                return
                            except Exception as e:
                                logger.error(f"處理簡單請假格式時出錯: {e}")
                                # 如果出錯，繼續往下執行其他邏輯
                        elif recent_fixed_schedule_id:
                            # 如果沒有trips上下文，再處理固定班次請假
                            logger.info(f"檢測到固定班次簡單請假格式，固定班次ID: {recent_fixed_schedule_id}, 加成: {amount}, 原因: {reason}")
                            
                            # 構造完整的固定班次請假命令
                            full_command = f"固定班次請假 {recent_fixed_schedule_id} {amount} {reason}"
                            
                            try:
                                from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave_command
                                result = handle_fixed_schedule_leave_command(full_command, user_id)
                                
                                # 處理完成後清除請假模式
                                conversation_manager.clear_leave_mode(user_id)
                                
                                reply_text(reply_token, result)
                                return
                            except Exception as e:
                                logger.error(f"處理固定班次簡單請假格式時出錯: {e}")
                                # 如果出錯，繼續往下執行其他邏輯
                        else:
                            # 如果找不到最近的班次ID，提示用戶
                            reply_text(reply_token, f"檢測到請假資料（{reason} {amount}），但找不到對應的班次。\n\n請使用完整格式：\n• 乘客請假 [班次ID] {amount} {reason}\n• 固定班次請假 [固定班次ID] {amount} {reason}")
                            return
                    else:
                        # 用戶不在請假模式，不處理簡單請假格式
                        logger.info(f"檢測到類似請假格式但用戶不在請假模式: '{message_text}'")
                        # 繼續往下執行其他邏輯
            
            # 🔥 新增：检查是否有AI上下文需要处理（例如pending_modification）
            from modules.utils.conversation_context import conversation_manager
            pending_modification = conversation_manager.get_pending_modification(user_id)
            
            if pending_modification:
                # 用户可能在回复AI的追问，交给AI处理
                try:
                    logger.info(f"檢測到待執行修改，將消息交給AI處理: {message_text}")
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    
                    result = handle_smart_fare_query(message_text, user_id, use_flex=True)
                    
                    # 🔥 修復：正確處理AI返回的不同類型結果（和上面保持一致）
                    if isinstance(result, str):
                        # 純文字結果
                        reply_text(reply_token, result)
                    elif isinstance(result, dict) and 'flex_message' in result and 'quick_reply' in result:
                        # 🔥 字典格式結果（和司機指派確認一樣）
                        try:
                            from linebot.v3.messaging import FlexMessage, FlexContainer
                            
                            flex_message = FlexMessage(
                                alt_text=result.get("alt_text", "AI處理完成"),
                                contents=FlexContainer.from_dict(result['flex_message']),
                                quick_reply=result['quick_reply']
                            )
                            
                            reply_message(reply_token, [flex_message])
                            logger.info("成功發送AI處理完成的 Flex Message 與 Quick Reply")
                        except Exception as flex_error:
                            logger.error(f"發送AI Flex Message失敗: {flex_error}")
                            traceback.print_exc()
                            # 降級為文字模式
                            try:
                                fallback_result = handle_smart_fare_query(message_text, user_id, use_flex=False)
                                if isinstance(fallback_result, str):
                                    reply_text(reply_token, fallback_result)
                                else:
                                    reply_text(reply_token, "❌ AI處理完成但無法顯示結果")
                            except Exception as fallback_error:
                                logger.error(f"AI文字模式降級也失敗: {fallback_error}")
                                reply_text(reply_token, "❌ AI處理失敗，請稍後再試")
                    else:
                        # 其他未知格式
                        logger.warning(f"AI返回了未知格式的結果: {type(result)}")
                        reply_text(reply_token, "❌ AI返回了無法識別的結果格式")
                    return
                except Exception as e:
                    logger.error(f"AI上下文處理出錯: {e}")
                    traceback.print_exc()
                    # 如果AI处理失败，继续原有逻辑
            
            # 🔥 簡化fallback：當所有處理都失敗時的提示
            if any(keyword in message_text.lower() for keyword in ['車資', '費用', '查詢', '查', '找']):
                suggestions = "💡 建議使用自然語言描述需求：\n\n範例:\n"
                suggestions += "• 前天司機5386所有班次\n"
                suggestions += "• 查詢今天診所車資\n"
                suggestions += "• 明天司機123的車資\n\n"
                suggestions += "或使用「幫助」查看所有可用命令。"
                reply_text(reply_token, suggestions)
            else:
                reply_text(reply_token, "未識別的命令。請使用「幫助」查看可用命令，或嘗試用自然語言描述您的需求。")
            
    except Exception as e:
        logger.error(f"處理消息時出錯: {e}")
        traceback.print_exc()
        reply_text(reply_token, f"處理命令時出錯: {str(e)}")


def get_help_text():
    """取得文字版幫助信息"""
    return """可用命令列表：

🔮 未來時間態 (規劃與預約)
1. 匯入固定班次 [週次] - 太陽週次匯入 (本週/下週)
2. 預約叫車 - 通過自然語言描述開始預約 (推薦)
3. /固定班表 [客戶簡稱] - 查詢固定班次並提供操作選項

⏰ 現在時間態 (進行中班次)
4. 東洋班次 - 查詢東洋/臨時未完成班次(通過日期按鈕選擇)
5. 診所班次 - 查詢診所班次(通過日期按鈕選擇)
6. 班次詳情 [ID] - 查看班次詳細信息 (可修改狀態)
7. 指派司機 [ID] - 為班次指派司機 (通過按鈕選擇)
8. 固定班次請假 [ID] [加成] [原因] - 設定固定班次長期請假
9. 固定班次恢復 [ID] - 恢復固定班次為準備狀態

📚 過去時間態 (歷史記錄)
10. 查已完成 [日期] [類別] - 查已完成班次(日期默認今天, 類別可選)
11. 查看 [ID] - 查看已完成班次詳細信息
12. 記錄車資 [ID] [錶價] [加成] - 記錄費用 (加成可選/可為負, 默認0)
13. 修改類別 [ID] [新類別] - 修改已完成班次的類別 (診所/東洋/臨時)
14. 生成周報表 [類別] - 生成上週班次報表 (類別: 診所/東洋/全部)
15. 生成月報表 [類別] - 生成上個月班次報表 (類別: 診所/東洋/全部)

🛠️ 特殊功能
16. 批量加成 - 問答式批量加成功能 (春節/颱風假期等)
17. 清理trips [選項] - 清理trips表中的過去資料 (已完成/過去/全部)
18. 預約叫車幫助 - 顯示「預約叫車」的說明
19. 幫助 - 顯示此幫助信息

📖 系統指南 (新增)
20. 生產線思維指南 - 理解派班系統的核心概念與三時間態架構
21. 快速參考 - 常用操作與狀態識別速查表
22. 高級請假系統 - 三層次障眼法設計與跨時間態恢復機制

💡 範例：
• 匯入固定班次 下週
• 匯入固定班次 本週 覆蓋
• 清理trips 已完成
• 東洋班次 明天

📚 完整文檔：使用圖形化幫助菜單可訪問更詳細的系統指南
在群組中使用時，可選擇性在命令前添加前綴... (例如 !, #, /)
"""
