# modules/handlers/text_message_handler.py
import traceback
import logging
from flask import current_app
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.unified_date_parser import parse_date_input

from modules.utils.line_bot import (
    reply_text, reply_message, reply_flex,
    create_postback_action, create_message_action,
    create_flex_message, get_line_bot_api,
    reply_message_with_quick_reply
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
from modules.handlers.database_sync_handler import (
    handle_database_sync_request,
    handle_database_sync_confirm,
    handle_database_sync_confirm_free,
    handle_sync_result_query
)
from modules.services.driver_service import handle_driver_assign_request, handle_driver_assign_select, handle_driver_assign_confirm, handle_driver_assign_cancel

# AI功能導入
from modules.services.smart_assistant import process_with_smart_assistant, format_smart_response

# 設定日誌
logger = logging.getLogger(__name__)

def handle_ai_fare_result(result, reply_token: str):
    """統一處理AI車資查詢結果，支持quick_reply"""
    try:
        if isinstance(result, dict):
            if result.get("type") == "text_with_quick_reply":
                # 🔥 修復：使用統一的quick_reply處理方式
                message_text = result.get("message") or result.get("text") or "處理完成"
                quick_reply = result.get("quick_reply")
                
                if quick_reply:
                    # 使用統一的reply_message_with_quick_reply函數
                    reply_message_with_quick_reply(reply_token, message_text, quick_reply)
                else:
                    reply_text(reply_token, message_text)
            elif result.get("type") == "text":
                # 🔥 純文字消息
                message_text = result.get("message") or result.get("text") or "處理完成"
                reply_text(reply_token, message_text)
            elif 'flex_message' in result:
                # 原有的Flex消息處理
                from linebot.v3.messaging import FlexMessage, FlexContainer
                flex_message = FlexMessage(
                    alt_text=result.get("alt_text", "AI智能結果"),
                    contents=FlexContainer.from_dict(result['flex_message']),
                    quick_reply=result.get('quick_reply')
                )
                reply_message(reply_token, [flex_message])
            else:
                # 🔥 修復：兜底處理，檢查所有可能的文字字段
                message_text = result.get("message") or result.get("text") or str(result)
                reply_text(reply_token, message_text)
        elif isinstance(result, str):
            reply_text(reply_token, result)
        else:
            reply_text(reply_token, str(result))
    except Exception as e:
        logger.error(f"處理AI車資查詢結果時出錯: {e}")
        reply_text(reply_token, "❌ 處理查詢結果時出現錯誤")

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
    logger.info(f"Processing text message handed over: '{message_text}' (Normalized: '{message_text}')")
    
    # 🔥 統一對話狀態檢查 - 防止智能助手搶戲
    from modules.utils.conversation_context import conversation_manager
    
    # 1. 檢查是否有活躍對話
    active_conversation = conversation_manager.get_active_conversation(user_id)
    if active_conversation:
        logger.info(f"🎯 用戶在活躍對話中: {active_conversation.conversation_type}, 步驟: {active_conversation.current_step}")
        
        # 2. 檢查是否是取消命令
        if conversation_manager.can_user_cancel_with_message(user_id, message_text):
            conversation_manager.end_conversation(user_id, f"用戶取消: {message_text}")
            reply_text(reply_token, "✅ 已取消操作\n\n💡 您可以重新發起新的命令")
            return
        
        # 3. 根據對話類型分發處理
        if active_conversation.conversation_type == 'fare_modification':
            # 車資修改對話
            return handle_fare_modification_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'temp_booking':
            # 預約叫車對話
            return handle_temp_booking_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'passenger_leave':
            # 乘客請假對話
            return handle_passenger_leave_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'driver_assign':
            # 司機指派對話
            return handle_driver_assign_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'query_clarification':
            # 查詢澄清對話
            return handle_query_clarification_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'query_confirmation':
            # 查詢確認對話
            return handle_query_confirmation_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'ai_modification_reason':
            # AI車資修改原因對話
            return handle_ai_modification_reason_conversation(active_conversation, message_text, user_id, reply_token)
        else:
            logger.warning(f"未知的對話類型: {active_conversation.conversation_type}")
            conversation_manager.end_conversation(user_id, "未知對話類型")
    
    # 4. 沒有活躍對話，進入正常處理流程...
    
    try:
        # 🔥 新增：處理查詢範例命令（來自Quick Reply）
        if message_text in ["查詢範例", "查看範例格式", "範例格式", "我想查詢具體的班次資料"]:
            example_text = """📋 **AI智能查詢範例**

🗓️ **日期查詢：**
• 7/15司機533診所班次
• 今天東洋班次
• 昨天司機123的車資

👨‍💼 **司機查詢：**
• 司機533所有班次
• 533號司機今天車資
• 查詢司機123本週收入

🏥 **類別查詢：**
• 診所班次車資統計
• 東洋類別今天收入
• 臨時班次費用查詢

🔧 **修改車資：**
• 修改班次#2014車資280加成-50
• 修改班次2014$280 -50
• 班次2014改為280元加成-50元

💡 **組合查詢：**
• 7/15司機533診所班次車資
• 今天司機123到診所的費用
• 修改昨天533號司機班次車資

✨ **智能理解：**
AI會自動理解您的自然語言描述，無需記憶固定格式！"""
            
            reply_text(reply_token, example_text)
            return
        
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
                        # 🔥 修復：處理帶有 Quick Reply 的文字消息
                        text_content = response.get("text", "處理中...")
                        if "quick_reply" in response:
                            logger.info(f"發送帶有QuickReply的文字消息: {response.get('quick_reply')}")
                            reply_message_with_quick_reply(reply_token, text_content, response.get("quick_reply"))
                        else:
                            reply_text(reply_token, text_content)
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
        if message_text.startswith("預約叫車"):
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
                    # 🔥 修復：處理帶有 Quick Reply 的文字消息
                    text_content = response.get("text", "開始臨時預約流程...")
                    if "quick_reply" in response:
                        logger.info(f"預約叫車開始發送帶有QuickReply的文字消息")
                        reply_message_with_quick_reply(reply_token, text_content, response.get("quick_reply"))
                    else:
                        reply_text(reply_token, text_content)
            return
        
        # 序列修復命令
        elif message_text.startswith("fix-sequence"):
            logger.info(f"用戶 {user_id} 請求序列修復")
            try:
                response = handle_sequence_fix_start(user_id)
                
                if response and response.get("text"):
                    # 檢查是否需要修復（包含「需要修復」關鍵字）
                    if "需要修復" in response["text"]:
                        # 提供 Quick Reply 按鈕
                        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                        
                        quick_reply_items = [
                            QuickReplyItem(
                                action=MessageAction(
                                    label="✅ 確認修復",
                                    text="確認修復"
                                )
                            ),
                            QuickReplyItem(
                                action=MessageAction(
                                    label="❌ 取消操作",
                                    text="取消"
                                )
                            )
                        ]
                        
                        quick_reply = QuickReply(items=quick_reply_items)
                        reply_message_with_quick_reply(reply_token, response["text"], quick_reply)
                    else:
                        # 序列正常，也提供Quick Reply按鈕
                        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                        
                        quick_reply_items = [
                            QuickReplyItem(
                                action=MessageAction(
                                    label="✅ 確定",
                                    text="取消"
                                )
                            )
                        ]
                        
                        quick_reply = QuickReply(items=quick_reply_items)
                        reply_message_with_quick_reply(reply_token, response["text"], quick_reply)
                else:
                    reply_text(reply_token, "檢查序列中...")
            except Exception as e:
                logger.error(f"序列修復命令處理失敗: {e}")
                reply_text(reply_token, f"❌ 序列檢查失敗: {str(e)}")
            return
        
        # 資料庫同步命令
        elif message_text == "資料庫同步":
            logger.info(f"用戶 {user_id} 請求資料庫同步檢查")
            try:
                # 創建模擬的event對象來適配原函數
                class MockEvent:
                    def __init__(self, user_id):
                        self.source = type('', (), {'user_id': user_id})()
                
                mock_event = MockEvent(user_id)
                result = handle_database_sync_request(mock_event, None)
                
                if result and result.get("text"):
                    # 如果檢查成功，提供Quick Reply按鈕
                    if "❌" not in result["text"]:  # 沒有錯誤
                        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                        
                        quick_reply_items = [
                            QuickReplyItem(
                                action=MessageAction(
                                    label="✅ 確認同步",
                                    text="確認同步"
                                )
                            ),
                            QuickReplyItem(
                                action=MessageAction(
                                    label="❌ 取消操作",
                                    text="取消"
                                )
                            )
                        ]
                        
                        quick_reply = QuickReply(items=quick_reply_items)
                        reply_message_with_quick_reply(reply_token, result["text"], quick_reply)
                    else:
                        # 有錯誤，只顯示文字
                        reply_text(reply_token, result["text"])
                else:
                    reply_text(reply_token, "❌ 無法獲取資料庫狀態")
            except Exception as e:
                logger.error(f"資料庫同步命令處理失敗: {e}")
                reply_text(reply_token, f"❌ 資料庫同步檢查失敗: {str(e)}")
            return
        
        # 確認同步命令
        elif message_text == "確認同步":
            logger.info(f"用戶 {user_id} 確認執行資料庫同步")
            try:
                # 創建模擬的event對象來適配原函數
                class MockEvent:
                    def __init__(self, user_id, reply_token):
                        self.source = type('', (), {'user_id': user_id})()
                        self.reply_token = reply_token
                
                mock_event = MockEvent(user_id, reply_token)
                
                # 使用免費版兼容的同步函數
                from modules.handlers.database_sync_handler import handle_database_sync_confirm_free
                result = handle_database_sync_confirm_free(mock_event, None)
                
                # handle_database_sync_confirm_free 自己處理回覆邏輯，返回None是正常的
                # 不需要額外的回覆處理
                
            except Exception as e:
                logger.error(f"確認同步命令處理失敗: {e}")
                reply_text(reply_token, f"❌ 同步執行失敗: {str(e)}")
            return
        
        # 同步結果查詢命令
        elif message_text == "同步結果":
            logger.info(f"用戶 {user_id} 查詢同步結果")
            try:
                # 創建模擬的event對象
                class MockEvent:
                    def __init__(self, user_id, reply_token):
                        self.source = type('', (), {'user_id': user_id})()
                        self.reply_token = reply_token
                
                mock_event = MockEvent(user_id, reply_token)
                result = handle_sync_result_query(mock_event, None)
                
                # handle_sync_result_query 自己處理回覆邏輯
                
            except Exception as e:
                logger.error(f"同步結果查詢失敗: {e}")
                reply_text(reply_token, f"❌ 查詢同步結果失敗: {str(e)}")
            return
        
        # 批量加成命令
        elif message_text.startswith("batch-allowance") or message_text.startswith("批量加成"):
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
                # --- 恢復原有邏輯：如果帶有日期參數，則執行查詢；否則觸發日期選擇 --- 
                if len(parts) > 1:
                    # 執行實際查詢 (東洋/臨時) - 保持原有的Flex Message格式
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
                    # 使用原有的美麗Flex Message服務
                    logger.info(f"處理班次詳情Flex Message: {trip_id}")
                    from modules.services.trip_detail_service import handle_trip_details_flex
                    
                    result, error_message = handle_trip_details_flex(trip_id)
                    
                    if result and 'flex_message' in result:
                        logger.info("獲取到Flex內容，準備發送")
                        
                        try:
                            # 使用Flex版本回複
                            from linebot.v3.messaging import FlexMessage, FlexContainer, QuickReply, QuickReplyItem, PostbackAction
                            
                            # 添加Quick Reply
                            if 'quick_reply' in result:
                                quick_reply_items = []
                                for item in result['quick_reply']['items']:
                                    action = item['action']
                                    quick_reply_items.append(
                                        QuickReplyItem(
                                            action=PostbackAction(
                                                label=action['label'],
                                                text=action.get('text', action['displayText']),
                                                data=action['data']
                                            )
                                        )
                                    )
                                
                                quick_reply = QuickReply(items=quick_reply_items)
                                flex_message = FlexMessage(
                                    alt_text=f"班次 #{trip_id} 詳細信息",
                                    contents=FlexContainer.from_dict(result['flex_message']),
                                    quick_reply=quick_reply
                                )
                            else:
                                flex_message = FlexMessage(
                                    alt_text=f"班次 #{trip_id} 詳細信息",
                                    contents=FlexContainer.from_dict(result['flex_message'])
                                )
                            
                            reply_message(reply_token, [flex_message])
                            
                            # 記錄班次ID到上下文（用於簡單請假格式）
                            try:
                                from modules.utils.conversation_context import conversation_manager
                                conversation_manager.set_recent_trip_id(user_id, trip_id)
                            except Exception as context_error:
                                logger.error(f"記錄班次ID到上下文時出錯: {context_error}")
                            
                        except Exception as flex_error:
                            logger.error(f"發送Flex Message失敗: {flex_error}")
                            # 回退到文本版本
                            from modules.handlers.trip_handler import handle_trip_details
                            text_result = handle_trip_details(trip_id)
                            reply_text(reply_token, text_result)
                    else:
                        reply_text(reply_token, error_message or f"找不到班次 #{trip_id}")
                except ValueError:
                    reply_text(reply_token, "班次ID必須是數字。")
                except Exception as e:
                    logger.error(f"處理班次詳情失敗: {e}")
                    traceback.print_exc()
                    reply_text(reply_token, f"班次查詢失敗: {str(e)}")
            else:
                reply_text(reply_token, "請提供班次ID，例如：班次詳情 123")
            return

        # 🔥 新增：查看已完成班次詳情
        elif message_text.startswith("查看"):
            parts = message_text.split()
            if len(parts) >= 2:
                try:
                    completed_trip_id = int(parts[1])
                    logger.info(f"處理查看已完成班次詳情: {completed_trip_id}")
                    from modules.handlers.trip_handler import handle_completed_trip_details
                    result = handle_completed_trip_details(completed_trip_id)
                    reply_text(reply_token, result)
                except ValueError:
                    reply_text(reply_token, "班次ID必須是數字。")
                except Exception as e:
                    logger.error(f"處理查看已完成班次失敗: {e}")
                    traceback.print_exc()
                    reply_text(reply_token, f"查看班次失敗: {str(e)}")
            else:
                reply_text(reply_token, "請提供班次ID，例如：查看 2207")
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
                            reply_text(reply_token, "無法顯示確認界面，請直接輸入：確認指派 [班次ID] [司機ID] 或 取消指派 [班次ID] 或 放棄指派 [班次ID]")
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
        
        # 取消指派/放棄指派
        elif message_text.startswith('取消指派 ') or message_text.startswith('放棄指派 '):
            try:
                parts = message_text.split()
                if len(parts) == 2:
                    trip_id = int(parts[1])
                    
                    logger.info(f"處理取消/放棄指派: 班次={trip_id}")
                    
                    result = handle_driver_assign_cancel(trip_id)
                    reply_text(reply_token, result)
                    return
                else:
                    reply_text(reply_token, "取消/放棄指派命令格式不正確。正確格式：取消指派 [班次ID] 或 放棄指派 [班次ID]")
                    return
            except ValueError:
                reply_text(reply_token, "班次ID必須是數字。")
                return
            except Exception as e:
                logger.error(f"處理取消/放棄指派時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理取消/放棄指派失敗: {str(e)}")
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
                         logger.info(f"診所班次查詢無結果或發生錯誤，發送消息: {message}")
                         reply_text(reply_token, message or "查詢診所班次時發生未知錯誤。")

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
                # 🔥 修復：查詢班次應該使用AdvancedQueryProcessor，返回Text+QuickReply格式
                from modules.services.advanced_query_processor import AdvancedQueryProcessor
                processor = AdvancedQueryProcessor()
                result = processor.process_complex_query(message_text, user_id)
                
                if result.get('type') == 'success':
                    reply_text(reply_token, result['message'])
                elif result.get('type') == 'success_with_pagination':
                    # 支持帶Quick Reply的分頁結果  
                    reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
                elif result.get('type') == 'no_results':
                    reply_text(reply_token, result['message'])
                else:
                    reply_text(reply_token, result.get('message', '查詢完成'))
                return
            except Exception as e:
                logger.error(f"❌ 處理查詢班次命令時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"查詢班次失敗: {str(e)}")
                return
            
        # --- 🔥 修復：查詢已完成班次使用AI車資服務的Flex Message --- 
        elif message_text.startswith("查已完成"):
            try:
                logger.info(f"🎯 處理查已完成命令，使用AI車資服務: {message_text}")
                # 🔥 關鍵修復：使用AI車資服務來顯示可點擊的Flex Message，並傳遞parsed_command
                from modules.services.ai_fare_service import handle_smart_fare_query
                result = handle_smart_fare_query(message_text, user_id, use_flex=True, parsed_command=message_text)
                handle_ai_fare_result(result, reply_token)
                return
            except Exception as e:
                logger.error(f"❌ AI車資服務處理失敗，回退到AdvancedQueryProcessor: {e}")
                # 🔥 回退到原有邏輯
                from modules.services.advanced_query_processor import AdvancedQueryProcessor
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
            
        # --- 🔥 新增：修改車資命令處理 --- 
        elif message_text.startswith("修改車資"):
            try:
                from modules.handlers.trip_handler import handle_modify_fare
                result = handle_modify_fare(message_text, user_id)
                reply_text(reply_token, result)
                return
            except Exception as e:
                logger.error(f"修改車資處理失敗: {e}")
                reply_text(reply_token, f"❌ 修改車資失敗：{str(e)}")
                return
        # --- 結束新增 ---
        
        # --- 🔥 修改：記錄車資統一使用智能引導模式 --- 
        elif message_text.startswith("記錄車資"):
            # 統一使用智能引導模式，而不是直接處理
            try:
                from modules.services.ai_fare_service import handle_smart_fare_query
                result = handle_smart_fare_query(message_text, user_id, use_flex=True, parsed_command=message_text)
                handle_ai_fare_result(result, reply_token)
                return
            except Exception as e:
                logger.error(f"智能車資處理失敗: {e}")
                reply_text(reply_token, f"❌ 車資處理失敗：{str(e)}")
                return
        # --- 結束修改 ---
        
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
                    # 🔧 修正：設置請假模式標記，正確使用 fixed_schedule_id 參數
                    conversation_manager.set_leave_mode(user_id=user_id, fixed_schedule_id=int(schedule_id))
                    logger.info(f"✅ 設置用戶 {user_id} 進入固定班次請假模式，固定班次 #{schedule_id}")
                except Exception as context_error:
                    logger.error(f"❌ 記錄固定班次ID到上下文或設置請假模式時出錯: {context_error}")
                    import traceback
                    logger.error(f"❌ 詳細錯誤: {traceback.format_exc()}")
                
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
                query_state = context.get_query_result()
                
                if not query_state:
                    reply_text(reply_token, "�� 沒有可用的查詢結果或會話已過期\n\n請重新執行查詢命令")
                    return
                
                current_page = query_state.get('current_page', 0)
                page_result = context.get_page_results(current_page + 1)
                
                if page_result and page_result.get('type') == 'success':
                    result_message = page_result.get('message')
                    quick_reply = page_result.get('quick_reply')
                    
                    if quick_reply:
                        # 🔥 修復：支持Quick Reply的翻頁結果
                        from linebot.v3.messaging import TextMessage
                        text_msg = TextMessage(text=result_message, quick_reply=quick_reply)
                        reply_message(reply_token, [text_msg])
                        logger.info(f"✅ 發送帶Quick Reply的翻頁結果")
                    else:
                        reply_text(reply_token, result_message)
                        logger.info(f"✅ 發送純文本翻頁結果")
                else:
                    reply_text(reply_token, "💡 沒有更多結果或會話已過期\n\n請重新執行查詢命令")
                return
            except Exception as e:
                logger.error(f"❌ 處理翻頁命令時出錯: {e}")
                reply_text(reply_token, "翻頁功能暫時不可用，請重新查詢")
                return
            
        # --- 🤖 智能助手系統整合 ---
        # 排除特定命令，不交給智能助手處理
        excluded_commands = ["資料庫同步", "確認同步", "同步結果", "fix-sequence", "batch-allowance", "批量加成"]
        if message_text in excluded_commands:
            logger.info(f"❌ 命令 '{message_text}' 在排除列表中，但沒有被正確處理")
            reply_text(reply_token, f"❌ 未識別的命令: {message_text}\n\n請使用「幫助」查看可用命令")
            return
        
        # 🔥 修復：優先檢查簡單請假格式，避免被智能助手攔截
        # 檢測簡單請假格式（原因+數字）並檢查是否在請假模式
        import re
        simple_leave_pattern = r'^(.+)\s+(-?\d+)$'
        simple_leave_match = re.match(simple_leave_pattern, message_text.strip())
        
        logger.info(f"🔍 檢查簡單請假格式: '{message_text}' → 匹配結果: {simple_leave_match is not None}")
        
        if simple_leave_match:
            # 檢查是否在請假模式
            from modules.utils.conversation_context import conversation_manager
            is_in_leave_mode = conversation_manager.is_in_leave_mode(user_id)
            
            logger.info(f"🔍 用戶 {user_id} 請假模式狀態: {is_in_leave_mode}")
            
            if is_in_leave_mode:
                reason = simple_leave_match.group(1).strip()
                amount = simple_leave_match.group(2).strip()
                
                recent_trip_id = conversation_manager.get_recent_trip_id(user_id)
                recent_fixed_schedule_id = conversation_manager.get_recent_fixed_schedule_id(user_id)
                
                logger.info(f"🔍 上下文狀態 - recent_trip_id: {recent_trip_id}, recent_fixed_schedule_id: {recent_fixed_schedule_id}")
                logger.info(f"🎯 優先處理簡單請假格式 - 用戶: {user_id}, trips上下文: {recent_trip_id}, 固定班次上下文: {recent_fixed_schedule_id}, 輸入: '{message_text}'")
                
                if recent_trip_id:
                    # 處理一般班次請假
                    full_command = f"乘客請假 {recent_trip_id} {amount} {reason}"
                    logger.info(f"🚗 構造一般班次請假命令: '{full_command}'")
                    
                    try:
                        from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
                        result = handle_passenger_leave_command(full_command, user_id)
                        conversation_manager.clear_leave_mode(user_id)
                        reply_text(reply_token, result)
                        return
                    except Exception as e:
                        logger.error(f"處理一般班次簡單請假格式時出錯: {e}")
                        
                elif recent_fixed_schedule_id:
                    # 處理固定班次請假
                    full_command = f"固定班次請假 {recent_fixed_schedule_id} {amount} {reason}"
                    logger.info(f"🚌 構造固定班次請假命令: '{full_command}'")
                    logger.info(f"🚌 參數詳情 - ID: {recent_fixed_schedule_id} (類型: {type(recent_fixed_schedule_id)}), 加成: {amount}, 原因: {reason}")
                    
                    try:
                        from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave_command
                        logger.info(f"🚌 開始調用 handle_fixed_schedule_leave_command...")
                        result = handle_fixed_schedule_leave_command(full_command, user_id)
                        logger.info(f"🚌 handle_fixed_schedule_leave_command 返回結果: {result[:100] if isinstance(result, str) else result}...")
                        conversation_manager.clear_leave_mode(user_id)
                        reply_text(reply_token, result)
                        return
                    except Exception as e:
                        logger.error(f"❌ 處理固定班次簡單請假格式時出錯: {e}")
                        import traceback
                        logger.error(f"❌ 完整錯誤堆疊: {traceback.format_exc()}")
                        # 提供錯誤回饋給用戶
                        reply_text(reply_token, f"❌ 處理固定班次請假時發生錯誤，請稍後再試或聯繫管理員。\n錯誤: {str(e)}")
                else:
                    # 如果找不到最近的班次ID，提示用戶
                    reply_text(reply_token, f"檢測到請假資料（{reason} {amount}），但找不到對應的班次。\n\n請使用完整格式：\n• 乘客請假 [班次ID] {amount} {reason}\n• 固定班次請假 [固定班次ID] {amount} {reason}")
                    return

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
                
                # 🔥 修復無限遞歸：直接執行命令而不是改變message_text
                logger.info(f"🎯 智能助手生成命令: {command}")
                logger.info(f"✅ 智能助手解析成功，執行命令: {command}")
                
                # 🔥 智能引導模式：AI理解意圖後直接處理，不要生成標準命令
                if command.startswith("記錄車資"):
                    # 🎯 核心邏輯：AI已經理解用戶意圖，直接進入智能引導模式
                    try:
                        from modules.services.ai_fare_service import handle_smart_fare_query
                        result = handle_smart_fare_query(message_text, user_id, use_flex=True, parsed_command=command, skip_parsing=True)
                        handle_ai_fare_result(result, reply_token)
                        return
                    except Exception as e:
                        logger.error(f"智能車資引導失敗: {e}")
                        reply_text(reply_token, f"❌ 智能引導失敗：{str(e)}")
                        return
                
                # 🔥 修復路由邏輯：查已完成命令使用AI車資服務
                elif command.startswith("查已完成"):
                    # 🔥 關鍵修復：智能助手路由的查已完成也使用AI車資服務，並傳遞parsed_command
                    try:
                        logger.info(f"🎯 智能助手路由查已完成命令，使用AI車資服務: {command}")
                        from modules.services.ai_fare_service import handle_smart_fare_query
                        # 🔥 關鍵修復：傳遞parsed_command參數和skip_parsing=True，避免重複解析
                        result = handle_smart_fare_query(command, user_id, use_flex=True, parsed_command=command, skip_parsing=True)
                        handle_ai_fare_result(result, reply_token)
                        return
                    except Exception as e:
                        logger.error(f"❌ AI車資服務處理失敗，回退到AdvancedQueryProcessor: {e}")
                        # 🔥 回退到原有邏輯
                        from modules.services.advanced_query_processor import AdvancedQueryProcessor
                        processor = AdvancedQueryProcessor()
                        result = processor.process_complex_query(command, user_id)
                        
                        if result.get('type') == 'success':
                            reply_text(reply_token, result['message'])
                        elif result.get('type') == 'success_with_pagination':
                            # 支持帶Quick Reply的分頁結果
                            reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
                        elif result.get('type') == 'no_results':
                            reply_text(reply_token, result['message'])
                        else:
                            reply_text(reply_token, "❌ 查詢執行失敗")
                        return
                
                # 🔥 修復路由邏輯：標準命令直接用AdvancedQueryProcessor
                elif command.startswith("查已完成"):
                    # 🔥 修復：標準"查已完成"命令應該直接使用AdvancedQueryProcessor
                    try:
                        logger.info(f"🎯 處理標準查已完成命令: {command}")
                        from modules.services.advanced_query_processor import AdvancedQueryProcessor
                        processor = AdvancedQueryProcessor()
                        result = processor.process_complex_query(command, user_id)
                        
                        if result.get('type') == 'success':
                            reply_text(reply_token, result['message'])
                        elif result.get('type') == 'success_with_pagination':
                            # 支持帶Quick Reply的分頁結果
                            reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
                        elif result.get('type') == 'no_results':
                            reply_text(reply_token, result['message'])
                        else:
                            reply_text(reply_token, "❌ 查詢執行失敗")
                        return
                    except Exception as e:
                        logger.error(f"AdvancedQueryProcessor處理失敗: {e}")
                        reply_text(reply_token, f"❌ 查詢執行失敗: {str(e)}")
                        return
                
                elif command.startswith("查詢班次"):
                    # 🔥 修復：未來日期查詢應該使用AdvancedQueryProcessor，不是AI車資服務
                    try:
                        from modules.services.advanced_query_processor import AdvancedQueryProcessor
                        processor = AdvancedQueryProcessor()
                        result = processor.process_complex_query(command, user_id)
                        
                        if result.get('type') == 'success':
                            reply_text(reply_token, result['message'])
                        elif result.get('type') == 'success_with_pagination':
                            reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
                        elif result.get('type') == 'no_results':
                            reply_text(reply_token, result['message'])
                        else:
                            reply_text(reply_token, f"❌ 查詢執行失敗")
                        return
                    except Exception as e:
                        logger.error(f"智能查詢處理失敗，回退到advanced_query_processor: {e}")
                        # 回退到原來的處理方式
                        from modules.services.advanced_query_processor import AdvancedQueryProcessor
                        processor = AdvancedQueryProcessor()
                        result = processor.process_complex_query(command, user_id)
                        
                        if result.get('type') == 'success':
                            reply_text(reply_token, result['message'])
                        elif result.get('type') == 'success_with_pagination':
                            # 🔥 新增：支持帶Quick Reply的分頁結果
                            reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
                        elif result.get('type') == 'no_results':
                            reply_text(reply_token, result['message'])
                        else:
                            reply_text(reply_token, f"❌ 查詢執行失敗")
                        return
                
                # 🔥 統計金額命令的智能處理
                elif command.startswith("統計金額"):
                    try:
                        from modules.services.advanced_query_processor import AdvancedQueryProcessor
                        processor = AdvancedQueryProcessor()
                        result = processor.process_complex_query(command, user_id)
                        
                        if result.get('type') == 'aggregation_success':
                            reply_text(reply_token, result['message'])
                        elif result.get('type') == 'no_results':
                            reply_text(reply_token, result['message'])
                        else:
                            reply_text(reply_token, f"❌ 統計執行失敗")
                        return
                    except Exception as e:
                        logger.error(f"統計金額執行失敗: {e}")
                        reply_text(reply_token, f"❌ 統計執行失敗：{str(e)}")
                        return
                
                # 🔥 新增：乘客請假命令的智能處理
                elif command.startswith("乘客請假"):
                    try:
                        from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
                        result = handle_passenger_leave_command(command, user_id)
                        
                        # 🔥 請假完成後清除請假模式
                        from modules.utils.conversation_context import conversation_manager
                        conversation_manager.clear_leave_mode(user_id)
                        
                        reply_text(reply_token, result)
                        return
                    except Exception as e:
                        logger.error(f"乘客請假執行失敗: {e}")
                        reply_text(reply_token, f"❌ 請假執行失敗：{str(e)}")
                        return
                
                # 🔥 新增：統一班次查詢命令的智能處理
                elif command.startswith("統一班次查詢"):
                    try:
                        # 解析班次ID
                        parts = command.strip().split()
                        if len(parts) >= 2:
                            trip_id = parts[1]
                            logger.info(f"🔍 智能助手調用統一班次查詢: {trip_id}")
                            
                            # 執行統一班次查詢邏輯
                            from modules.services.trip_detail_service import handle_trip_details_flex
                            from modules.services.trip_service import get_completed_trip_details
                            
                            # 1. 先嘗試查詢現在態 (trips表)
                            flex_message, text_fallback = handle_trip_details_flex(trip_id)
                            
                            if flex_message and flex_message != "找不到班次":
                                # 找到現在態班次
                                logger.info(f"✅ 找到現在態班次 #{trip_id}")
                                # 🔥 修復：使用正確的Flex消息回覆方式
                                if isinstance(flex_message, dict) and 'flex_message' in flex_message:
                                    # 使用完整的Flex消息處理
                                    from linebot.v3.messaging import FlexMessage, FlexContainer
                                    flex_msg = FlexMessage(
                                        alt_text=flex_message.get("alt_text", f"班次 #{trip_id} 詳細信息"),
                                        contents=FlexContainer.from_dict(flex_message['flex_message']),
                                        quick_reply=flex_message.get('quick_reply')
                                    )
                                    reply_message(reply_token, [flex_msg])
                                else:
                                    # 降級為文字回覆
                                    reply_text(reply_token, text_fallback or f"班次 #{trip_id} 信息")
                                return
                            else:
                                # 如果現在態沒找到，查詢過去態 (completed_trips表)
                                logger.info(f"🔍 現在態未找到，查詢過去態班次 #{trip_id}")
                                completed_result = get_completed_trip_details(trip_id)
                                
                                if completed_result:
                                    reply_text(reply_token, completed_result)
                                    return
                                else:
                                    # 都沒找到
                                    reply_text(reply_token, f"❌ 找不到班次 #{trip_id}\n\n💡 提示：\n• 確認班次ID是否正確\n• 該班次可能已被刪除")
                                    return
                        else:
                            reply_text(reply_token, "❌ 統一班次查詢格式錯誤\n正確格式：統一班次查詢 [班次ID]")
                            return
                    except Exception as e:
                        logger.error(f"統一班次查詢執行失敗: {e}")
                        reply_text(reply_token, f"❌ 統一班次查詢失敗：{str(e)}")
                        return
                
                else:
                    # 其他命令暫時保持原有邏輯
                    reply_text(reply_token, f"🤖 AI理解您的需求：{command}\n正在處理...")
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
            
            # 🔥 移除重複的簡單請假格式檢測邏輯 - 已在智能助手之前優先處理
            
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
                                handle_ai_fare_result(fallback_result, reply_token)
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

# === 🔥 統一對話處理函數 ===

def handle_fare_modification_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理車資修改對話"""
    # 🔥 修復：導入 conversation_manager
    from modules.utils.conversation_context import conversation_manager
    
    logger.info(f"🎯 處理車資修改對話: 步驟={conversation.current_step}, 消息='{message_text}'")
    
    if conversation.current_step == 'waiting_reason':
        # 用戶在回答修改原因
        reason_indicators = ['原因', '因為', '由於', '要求', '調整', '客戶', '等候', '等待', '夜班', '加班', '延誤', '來不及', '臨時', '不適', '有事', '路況', '塞車']
        
        # 檢查是否包含原因關鍵詞，或者是簡單的原因描述
        is_reason_response = False
        if any(keyword in message_text for keyword in reason_indicators):
            is_reason_response = True
        elif len(message_text.strip()) > 3 and not any(num in message_text for num in ['0','1','2','3','4','5','6','7','8','9']):
            # 如果沒有數字且長度大於3，可能是原因描述
            is_reason_response = True
        
        if is_reason_response:
            # 提取原因
            extracted_reason = message_text.strip()
            
            # 清理原因文本（移除"原因："等前綴）
            import re
            cleaned_reason = re.sub(r'^原因[：:]\s*', '', extracted_reason)
            cleaned_reason = re.sub(r'^因為\s*', '', cleaned_reason)
            cleaned_reason = re.sub(r'^由於\s*', '', cleaned_reason)
            cleaned_reason = cleaned_reason.strip()
            
            if len(cleaned_reason) > 0:
                # 從對話上下文獲取修改信息
                context_data = conversation.context_data
                trip_id = context_data['trip_id']
                new_meter = context_data['meter_fare']
                new_extra = context_data['extra_fare']
                original_meter = context_data['original_meter']
                original_extra = context_data['original_extra']
                trip = context_data['trip']
                
                logger.info(f"🎯 用戶提供修改原因: {cleaned_reason}，準備顯示確認框")
                
                # 🔥 重建確認框機制：更新對話狀態為等待確認
                context_data['modification_reason'] = cleaned_reason
                conversation_manager.update_conversation(
                    user_id=user_id,
                    current_step='waiting_confirmation',
                    context_data=context_data
                )
                
                # 🔥 建立確認框Flex消息 with Quick Reply
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                
                quick_reply_items = [
                    QuickReplyItem(
                        action=MessageAction(
                            label="✅ 確認修改",
                            text="確認修改"
                        )
                    ),
                    QuickReplyItem(
                        action=MessageAction(
                            label="❌ 取消修改",
                            text="取消修改"
                        )
                    )
                ]
                
                quick_reply = QuickReply(items=quick_reply_items)
                
                confirmation_message = f"""⚠️ 確認修改

🤖 AI智能修改確認

📋 班次：#{trip_id} ({trip['category']})
📍 路線：{trip['start_point']} → {trip['end_point']}
🚗 司機：#{trip.get('driver_id', 'N/A')}

💰 費用變更：{original_meter}+{original_extra} → {new_meter}+{new_extra}
📊 總計變化：{(new_meter + new_extra) - (original_meter + original_extra):+d} 元
📝 修改原因：{cleaned_reason}

請確認是否執行此修改？"""
                
                # 發送確認框消息
                reply_message_with_quick_reply(reply_token, confirmation_message, quick_reply)
                return
            else:
                reply_text(reply_token, "⚠️ 修改原因不能為空，請重新輸入修改原因")
                return
        else:
            # 用戶輸入不像是原因回答，提示重新輸入
            status_message = conversation_manager.get_conversation_status_message(user_id)
            reply_text(reply_token, f"💭 請提供修改原因\n\n{status_message}")
            return
    
    elif conversation.current_step == 'waiting_confirmation':
        # 🔥 新增：處理用戶確認選擇
        if message_text in ['確認修改', '確認', '是', 'yes', 'Y', 'y']:
            # 用戶確認執行修改
            context_data = conversation.context_data
            trip_id = context_data['trip_id']
            new_meter = context_data['meter_fare']
            new_extra = context_data['extra_fare']
            cleaned_reason = context_data['modification_reason']
            
            logger.info(f"🔥 用戶確認執行AI智能修改: trip_id={trip_id}, meter={new_meter}, extra={new_extra}, reason='{cleaned_reason}'")
            
            # 執行修改
            from modules.handlers.trip_handler import handle_record_fare
            modify_command = f"記錄車資 {trip_id} {new_meter} {new_extra} {cleaned_reason}"
            result = handle_record_fare(modify_command, user_id=user_id)
            
            # 結束對話
            conversation_manager.end_conversation(user_id, "修改完成")
            
            if "需要說明原因" in result or "修改原因" in result:
                reply_text(reply_token, f"❌ 修改被系統拒絕：{result}")
            else:
                reply_text(reply_token, f"""✅ AI智能修改執行成功！

📋 班次：#{trip_id}
💰 新費用：{new_meter}+{new_extra} = {new_meter + new_extra}元
📝 修改原因：{cleaned_reason}

{result}""")
            return
            
        elif message_text in ['取消修改', '取消', '否', 'no', 'N', 'n']:
            # 用戶取消修改
            conversation_manager.end_conversation(user_id, "用戶取消修改")
            reply_text(reply_token, """❌ 已取消修改流程

🔒 數據庫未被修改，您可以重新發起命令。""")
            return
        else:
            # 用戶回覆不明確，提示重新選擇
            reply_text(reply_token, """⚠️ 請明確選擇：

✅ 回覆「確認修改」執行修改
❌ 回覆「取消修改」放棄修改""")
            return
    
    # 其他步驟的處理...
    logger.warning(f"未處理的車資修改對話步驟: {conversation.current_step}")

def handle_temp_booking_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理預約叫車對話"""
    logger.info(f"🎯 處理預約叫車對話: 步驟={conversation.current_step}")
    
    # 使用現有的temp_booking_handler邏輯
    from modules.handlers.temp_booking_handler import handle_temp_booking_message
    response = handle_temp_booking_message(user_id, message_text)
    
    if response and response.get("type") == "text":
        # 🔥 修復：處理帶有 Quick Reply 的文字消息
        text_content = response.get("text", "處理中...")
        if "quick_reply" in response:
            logger.info(f"對話模式發送帶有QuickReply的文字消息")
            reply_message_with_quick_reply(reply_token, text_content, response.get("quick_reply"))
        else:
            reply_text(reply_token, text_content)
    elif response:
        # 處理其他類型的回覆
        reply_text(reply_token, str(response))
    else:
        # 如果沒有回覆，結束對話
        from modules.utils.conversation_context import conversation_manager
        conversation_manager.end_conversation(user_id, "預約流程結束")
        reply_text(reply_token, "預約流程已結束")

def handle_passenger_leave_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理乘客請假對話"""
    logger.info(f"🎯 處理乘客請假對話: 步驟={conversation.current_step}")
    
    # 使用現有的passenger_leave_handler邏輯
    from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
    result = handle_passenger_leave_command(message_text, user_id)
    
    # 結束對話
    conversation_manager.end_conversation(user_id, "請假處理完成")
    reply_text(reply_token, result)

def handle_driver_assign_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理司機指派對話"""
    logger.info(f"🎯 處理司機指派對話: 步驟={conversation.current_step}")
    
    # 使用現有的driver_service邏輯
    from modules.services.driver_service import handle_driver_assign_request
    # 根據對話步驟處理...
    
    # 暫時結束對話
    conversation_manager.end_conversation(user_id, "指派處理完成")
    reply_text(reply_token, "司機指派處理完成")

def handle_query_clarification_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理查詢澄清對話"""
    logger.info(f"🎯 處理查詢澄清對話: 消息='{message_text}'")
    
    # 🔥 修復：導入conversation_manager
    from modules.utils.conversation_context import conversation_manager
    
    if conversation.current_step == 'waiting_clarification':
        # 用戶提供了澄清信息，重新處理查詢
        logger.info(f"🔄 用戶提供澄清信息，重新處理: {message_text}")
        
        # 結束澄清對話
        conversation_manager.end_conversation(user_id, "澄清完成")
        
        # 重新處理用戶的查詢（遞歸調用）
        try:
            # 🔥 移除重複AI邏輯，統一使用智能助手作為唯一入口
            from modules.services.smart_assistant import process_with_smart_assistant
            smart_result = process_with_smart_assistant(message_text, user_id)
            
            if smart_result["type"] == "execute_command":
                # 智能助手解析出了標準命令，執行對應命令
                command = smart_result["command"]
                logger.info(f"🎯 澄清後智能助手生成命令: {command}")
                
                # 🔥 統一命令執行邏輯
                if command.startswith("記錄車資"):
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    result = handle_smart_fare_query(message_text, user_id, use_flex=True)
                    handle_ai_fare_result(result, reply_token)
                elif command.startswith("查已完成"):
                    from modules.services.advanced_query_processor import AdvancedQueryProcessor
                    processor = AdvancedQueryProcessor()
                    result = processor.process_complex_query(command, user_id)
                    if result.get('type') == 'success':
                        reply_text(reply_token, result['message'])
                    else:
                        reply_text(reply_token, "❌ 查詢執行失敗")
                else:
                    reply_text(reply_token, f"收到澄清後的命令：{command}")
            else:
                reply_text(reply_token, "謝謝您的澄清，但我仍然無法理解。請嘗試更具體的描述。")
        except Exception as e:
            logger.error(f"處理澄清後的查詢失敗: {e}")
            reply_text(reply_token, "處理您的澄清查詢時出現錯誤，請重新嘗試。")

def handle_query_confirmation_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理查詢確認對話"""
    logger.info(f"🎯 處理查詢確認對話: 消息='{message_text}'")
    
    # 🔥 修復：導入conversation_manager
    from modules.utils.conversation_context import conversation_manager
    
    if conversation.current_step == 'waiting_confirmation':
        # 檢查用戶是否確認
        confirmation_keywords = ['確認', '對的', '正確', 'yes', '是', '對', 'ok', '好']
        rejection_keywords = ['不對', '錯誤', '不是', 'no', '錯', '不正確']
        
        message_lower = message_text.lower().strip()
        
        if any(keyword in message_lower for keyword in confirmation_keywords):
            # 用戶確認理解正確，執行原查詢
            logger.info(f"✅ 用戶確認理解正確，執行查詢")
            
            context_data = conversation.context_data
            original_query = context_data.get('original_query', message_text)
            
            # 結束確認對話
            conversation_manager.end_conversation(user_id, "確認完成")
            
            # 🔥 修復無限循環：使用智能助手已經生成的標準命令，而不是重新解析原始查詢
            try:
                # 檢查是否有已解析的標準命令
                parsed_command = context_data.get('parsed_command')
                if parsed_command:
                    logger.info(f"🎯 執行智能助手已解析的命令: {parsed_command}")
                    
                    # 🔥 修復：確認後仍使用AI車資服務（保持Flex Message），但跳過重新解析
                    try:
                        from modules.services.ai_fare_service import handle_smart_fare_query
                        # 🔥 關鍵修復：使用skip_parsing參數，直接執行已解析命令
                        result = handle_smart_fare_query(original_query, user_id, use_flex=True, 
                                                       parsed_command=parsed_command, skip_parsing=True)
                        handle_ai_fare_result(result, reply_token)
                    except Exception as e:
                        logger.error(f"AI車資服務執行失敗，回退到AdvancedQueryProcessor: {e}")
                        # 回退方案
                        from modules.services.advanced_query_processor import AdvancedQueryProcessor
                        processor = AdvancedQueryProcessor()
                        result = processor.process_complex_query(parsed_command, user_id)
                        
                        if result.get('type') == 'success':
                            reply_text(reply_token, result['message'])
                        elif result.get('type') == 'success_with_pagination':
                            reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
                        elif result.get('type') == 'no_results':
                            reply_text(reply_token, result['message'])
                        else:
                            reply_text(reply_token, "❌ 查詢執行失敗")
                else:
                    # 降級：如果沒有已解析命令，使用AI車資服務（可能觸發循環，但至少有回退）
                    logger.warning("⚠️ 沒有已解析命令，降級使用AI車資服務")
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    result = handle_smart_fare_query(original_query, user_id, use_flex=True)
                    handle_ai_fare_result(result, reply_token)
                
            except Exception as e:
                logger.error(f"執行確認後的查詢失敗: {e}")
                reply_text(reply_token, f"❌ 執行查詢時出現錯誤: {str(e)}")
        elif any(keyword in message_lower for keyword in rejection_keywords):
            # 用戶認為理解不正確
            logger.info(f"❌ 用戶認為理解不正確，請求重新描述")
            
            # 結束確認對話
            conversation_manager.end_conversation(user_id, "用戶否認理解")
            
            reply_text(reply_token, """💭 理解，請提供更準確的描述

💡 請嘗試：
• 使用具體的日期格式（如 7/15）
• 明確指定司機號碼（如 司機533）
• 包含班次類別（如 診所、東洋）
• 如果要修改，請說明具體的錶價和加成

或使用「查已完成」查看完整列表後再選擇。""")
        else:
            # 用戶回覆不明確，請求明確回答
            status_message = conversation_manager.get_conversation_status_message(user_id)
            reply_text(reply_token, f"💭 請明確回答「確認」或「不對」\n\n{status_message}")
    else:
        logger.warning(f"未處理的查詢確認對話步驟: {conversation.current_step}")
        conversation_manager.end_conversation(user_id, "未知步驟")

def handle_ai_modification_reason_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理AI車資修改原因對話"""
    logger.info(f"🎯 處理AI修改原因對話: 步驟={conversation.current_step}, 消息='{message_text}'")
    
    from modules.utils.conversation_context import conversation_manager
    
    if conversation.current_step == 'waiting_reason':
        # 用戶提供了修改原因
        reason = message_text.strip()
        
        # 過濾明顯不是原因的輸入
        if len(reason) < 2 or reason.isdigit():
            reply_text(reply_token, "⚠️ 請提供有效的修改原因，如：客戶要求調整、等候時間過長等")
            return
        
        # 從對話上下文獲取修改數據
        context_data = conversation.context_data
        trip_id = context_data.get('trip_id')
        meter_fare = context_data.get('meter_fare')
        extra_fare = context_data.get('extra_fare')
        
        if not all([trip_id, meter_fare is not None, extra_fare is not None]):
            logger.error(f"AI修改原因對話上下文數據不完整: {context_data}")
            conversation_manager.end_conversation(user_id, "數據錯誤")
            reply_text(reply_token, "❌ 對話數據錯誤，請重新發起修改")
            return
        
        logger.info(f"🔥 用戶提供修改原因，顯示確認框: trip_id={trip_id}, meter={meter_fare}, extra={extra_fare}, reason='{reason}'")
        
        # 更新對話上下文，添加原因並保存待執行修改
        context_data['reason'] = reason
        trip_data = context_data.get('trip', {})
        
        # 保存待執行修改（類似execute_fare_modification的邏輯）
        conversation_manager.set_pending_modification(user_id, {
            'trip_id': trip_id,
            'meter_fare': meter_fare,
            'extra_fare': extra_fare,
            'reason': reason,
            'trip': trip_data,
            'timestamp': __import__('time').time()
        })
        
        # 結束原因詢問對話
        conversation_manager.end_conversation(user_id, "原因已收集")
        
        # 生成修改確認Flex Message（使用現有的execute_fare_modification邏輯）
        try:
            from modules.services.ai_fare_service import execute_fare_modification
            modification_intent = {
                'trip_id': trip_id,
                'meter_fare': meter_fare,
                'extra_fare': extra_fare,
                'reason': reason
            }
            
            # 調用execute_fare_modification來生成確認界面
            result = execute_fare_modification(trip_data, modification_intent, user_id)
            
            # 處理返回結果
            if isinstance(result, dict) and 'flex_message' in result:
                # Flex格式結果
                handle_ai_fare_result(result, reply_token)
            else:
                # 文字格式結果
                reply_text(reply_token, str(result))
                
        except Exception as e:
            logger.error(f"生成確認界面失敗: {e}")
            # 降級處理：顯示文字確認
            reply_text(reply_token, f"""🎯 請確認修改班次#{trip_id}的車資：

📊 當前記錄：錶價 {trip_data.get('meter_fare', 0)}, 加成 {trip_data.get('extra_fare', 0)}
🔄 修改為：錶價 {meter_fare}, 加成 {extra_fare}
📝 修改原因：{reason}

請回覆「確認AI修改 {trip_id} {meter_fare} {extra_fare} {reason}」來執行修改""")
    else:
        logger.warning(f"未處理的AI修改原因對話步驟: {conversation.current_step}")
        conversation_manager.end_conversation(user_id, "未知步驟")
        reply_text(reply_token, "❌ 對話狀態錯誤，請重新發起修改")
