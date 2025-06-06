# modules/handlers/text_message_handler.py
import traceback
import logging
from flask import current_app
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.helpers import parse_date_input

from modules.utils.line_bot import (
    reply_text, reply_message, reply_flex,
    create_postback_action, create_message_action,
    create_flex_message
)
from modules.handlers.trip_handler import handle_query_trips, handle_trip_details, handle_change_status, handle_record_fare, handle_modify_category, handle_completed_trip_details
from modules.flex_designs.help_flex import get_help_flex
from modules.handlers.temp_booking_handler import (
    handle_temp_booking_start,
    handle_temp_booking_message,
    temp_booking_states,
    handle_temp_booking_help
)
from modules.services.driver_service import handle_driver_assign_request, handle_driver_assign_select, handle_driver_assign_confirm, handle_driver_assign_cancel

# AI功能導入
from modules.services.ai_fare_service import should_use_ai_query

# 設定日誌
logger = logging.getLogger(__name__)

def process_text_message(event):
    """處理文本消息的主函數"""
    # 傳入的 event.message.text 應該是已經過 webhook.py 處理的文本
    message_text = event.message.text 
    reply_token = event.reply_token
    user_id = event.source.user_id
    
    # 記錄將要處理的文本
    command_text_lower = message_text.strip().lower()
    logger.info(f"Processing text message handed over: '{message_text}' (Normalized: '{command_text_lower}')") 
    
    try:
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
        
        # 查詢班次 (東洋/臨時)
        elif message_text.startswith("查詢班次"):
            try:
                parts = message_text.split()
                # --- 修改：如果帶有日期參數，則執行查詢；否則觸發日期選擇 --- 
                if len(parts) > 1:
                    # 執行實際查詢 (東洋/臨時)
                    logger.info(f"處理查詢班次命令 (帶日期): {message_text}")
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
                    logger.info(f"處理查詢班次命令 (觸發日期選擇): {message_text}")
                    from modules.services.trip_query_service import request_toyo_temp_trip_date_selection
                    reply_msg, error_message = request_toyo_temp_trip_date_selection()
                    if reply_msg and error_message is None:
                        reply_message(reply_token, [reply_msg])
                    else:
                        reply_text(reply_token, error_message or "無法生成日期選擇")
                return 
            except Exception as e:
                logger.error(f"處理查詢班次時出錯: {e}")
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
                
                flex_content, error_message = handle_driver_assign_select(trip_id, driver_id)
                
                if flex_content and error_message is None:
                    # 發送確認界面
                    reply_flex(reply_token, "確認指派司機", flex_content)
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
            
        # 處理匯入固定班次（一整周）
        elif message_text.startswith("匯入固定班次"):
            from modules.handlers.import_handler import handle_import_fixed_trips_week
            result_text = handle_import_fixed_trips_week(message_text)
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
            
        # --- 修改：查詢已完成班次 --- 
        elif message_text.startswith("查已完成"):
             try:
                 parts = message_text.split()
                 date_str = None
                 category_filter = None
                 query_date = get_taiwan_date() # 默認日期為今天

                 # 解析參數
                 if len(parts) > 1:
                     # 嘗試解析第一個參數為日期
                     try:
                         query_date = parse_date_input(parts[1])
                         date_str = parts[1] # 記錄用戶輸入的日期字符串
                         if len(parts) > 2:
                             category_filter = parts[2]
                     except ValueError:
                         # 如果第一個參數不是日期，則假定它是類別
                         category_filter = parts[1]
                         date_str = query_date.strftime("%Y-%m-%d") # 使用默認日期
                         
                 if category_filter:
                     # 如果提供了類別，直接查詢
                     from modules.services.trip_query_service import handle_query_completed_trips
                     result_text = handle_query_completed_trips(message_text) # 傳遞原始命令文本
                     reply_text(reply_token, result_text)
                 else:
                     # 如果沒有提供類別，顯示類別選擇 Quick Reply
                     from modules.services.trip_query_service import request_completed_trip_category_selection
                     reply_msg, error_message = request_completed_trip_category_selection(query_date)
                     if reply_msg and error_message is None:
                         reply_message(reply_token, [reply_msg])
                     else:
                         reply_text(reply_token, error_message or "無法生成類別選擇")
             except Exception as e:
                 logger.error(f"處理查已完成命令時出錯: {e}")
                 traceback.print_exc()
                 reply_text(reply_token, f"查詢已完成班次失敗: {str(e)}")
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
        
        # 班次詳情的簡寫命令
        elif message_text.startswith("班次"):
            parts = message_text.split()
            if len(parts) >= 2 and parts[1].isdigit():
                # 格式是「班次 123」，當作「班次詳情 123」處理
                trip_id = int(parts[1])
                logger.info(f"簡寫命令，處理為班次詳情: {trip_id}")
                # 遞迴調用自己，但使用完整命令
                process_text_message_with_text(f"班次詳情 {trip_id}", reply_token, user_id)
                return
            
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
            
        # --- 🔥 修改：AI智能車資查詢檢測 ---
        elif should_use_ai_query(message_text):
            try:
                logger.info(f"檢測到AI智能車資查詢: {message_text}")
                from modules.services.ai_fare_service import handle_smart_fare_query
                
                # 使用完整的智能車資查詢服務
                result = handle_smart_fare_query(message_text, user_id)
                reply_text(reply_token, result)
                return
            except Exception as e:
                logger.error(f"AI智能車資查詢出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"❌ AI處理出錯: {str(e)}")
                return
        # --- 結束修改 ---
            
        # --- 新增：查看已完成班次 ---
        elif message_text.startswith("查看"):
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
            
        # 未識別的命令
        else:
            # 🔥 新增：检查是否有AI上下文需要处理（例如pending_modification）
            from modules.utils.conversation_context import conversation_manager
            pending_modification = conversation_manager.get_pending_modification(user_id)
            
            if pending_modification:
                # 用户可能在回复AI的追问，交给AI处理
                try:
                    logger.info(f"檢測到待執行修改，將消息交給AI處理: {message_text}")
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    
                    result = handle_smart_fare_query(message_text, user_id)
                    reply_text(reply_token, result)
                    return
                except Exception as e:
                    logger.error(f"AI上下文處理出錯: {e}")
                    traceback.print_exc()
                    # 如果AI处理失败，继续原有逻辑
            
            # 檢查是否可能是AI查詢但檢測失敗
            if any(keyword in message_text.lower() for keyword in ['車資', '費用', '查詢', '查', '找']):
                # 提供AI查詢建議
                suggestions = "💡 可能您想要使用AI車資查詢功能？\n\n範例:\n"
                suggestions += "• 查詢今天台中車資\n"
                suggestions += "• 查詢明天彰化車資\n" 
                suggestions += "• 查詢6/1診所車資\n"
                suggestions += "• 修改班次123車資500\n\n"
                suggestions += "或使用「幫助」查看所有可用命令。"
                reply_text(reply_token, suggestions)
            else:
                reply_text(reply_token, "未識別的命令。請使用「幫助」查看可用命令。")
            
    except Exception as e:
        logger.error(f"處理消息時出錯: {e}")
        traceback.print_exc()
        reply_text(reply_token, f"處理命令時出錯: {str(e)}")

# 輔助函數，用於處理特定文本的消息處理
def process_text_message_with_text(message_text, reply_token, user_id):
    """使用指定的文本處理消息，模擬收到該消息"""
    from linebot.v3.webhooks import TextMessageContent, MessageEvent, Source
    
    # 創建一個模擬的事件對象
    fake_message = TextMessageContent(text=message_text, id="custom_message_id")
    fake_event = MessageEvent(
        type="message",
        mode="active",
        timestamp=0,
        source=Source(type="user", user_id=user_id),
        message=fake_message,
        reply_token=reply_token
    )
    
    # 調用消息處理函數
    process_text_message(fake_event)

def get_help_text():
    """取得文字版幫助信息"""
    return """可用命令列表：
1. 查詢班次 - 查詢東洋/臨時未完成班次(通過日期按鈕選擇)
2. 診所班次 - 查詢診所班次(通過日期按鈕選擇)
3. 查已完成 [日期] [類別] - 查已完成班次(日期默認今天, 類別可選)
4. 班次詳情 [ID] - 查看班次詳細信息 (可修改狀態)
5. 查看 [ID] - 查看已完成班次詳細信息
6. 指派司機 [ID] - 為班次指派司機 (通過按鈕選擇)
7. 記錄車資 [ID] [錶價] [加成] - 記錄費用 (加成可選/可為負, 默認0)
8. 修改類別 [ID] [新類別] - 修改已完成班次的類別 (診所/東洋/臨時)
9. 預約叫車 - 通過自然語言描述開始預約 (推薦)
10. 預約叫車幫助 - 顯示「預約叫車」的說明
11. 幫助 - 顯示此幫助信息

在群組中使用時，可選擇性在命令前添加前綴... (例如 !, #, /)
"""
