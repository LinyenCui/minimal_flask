# modules/handlers/text_message_handler.py
import traceback
import logging
from flask import current_app

from modules.utils.line_bot import (
    reply_text, reply_message, reply_flex,
    create_postback_action, create_message_action,
    create_flex_message
)
from modules.handlers.trip_handler import handle_query_trips, handle_trip_details, handle_change_status
from modules.flex_designs.help_flex import get_help_flex
from modules.handlers.temp_booking_handler import handle_temp_booking_start, handle_temp_booking_message, temp_booking_states, handle_temp_booking_help
from modules.services.driver_service import handle_driver_assign_request, handle_driver_assign_select, handle_driver_assign_confirm, handle_driver_assign_cancel

# 設定日誌
logger = logging.getLogger(__name__)

def process_text_message(event):
    """處理文本消息的主函數"""
    # 傳入的 event.message.text 應該是已經過 webhook.py 處理的文本
    message_text = event.message.text 
    reply_token = event.reply_token
    user_id = event.source.user_id
    
    # 記錄將要處理的文本
    logger.info(f"Processing text message handed over: {message_text}") 
    
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
        elif message_text == "臨時預約" or message_text.lower() in ["!臨時預約", "#臨時預約", "/臨時預約"]:
            logger.info(f"用戶 {user_id} 請求臨時預約，消息: {message_text}")
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
            
        # 臨時預約幫助
        elif message_text == "臨時預約幫助":
            logger.info(f"用戶 {user_id} 請求臨時預約幫助")
            response = handle_temp_booking_help()
            reply_text(reply_token, response.get("text", "臨時預約使用說明..."))
            return
        
        # 查詢班次
        elif message_text.startswith("查詢班次"):
            try:
                logger.info(f"處理查詢班次命令: {message_text}")
                # 優先使用Flex Message版本
                from modules.services.trip_query_service import handle_query_trips_flex, handle_query_trips
                
                # 记录调用前的状态
                logger.info("即將調用handle_query_trips_flex函數")
                flex_content, error_message = handle_query_trips_flex(message_text)
                logger.info(f"handle_query_trips_flex返回結果: flex_content類型={type(flex_content)}, error_message={error_message}")
                
                if flex_content and error_message is None:
                    # 如果有Flex內容，使用Flex Message回覆
                    logger.info("使用Flex回覆查詢結果")
                    reply_flex(reply_token, "班次查詢結果", flex_content)
                    return
                else:
                    # 如果出錯或沒有結果，顯示錯誤消息或使用文本版本
                    logger.info(f"無Flex內容或有錯誤，使用文本版本。錯誤: {error_message}")
                    result = handle_query_trips(message_text)
                    reply_text(reply_token, result)
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
                            # 尝试使用Flex版本回复
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
                                                data=action['data'],
                                                display_text=action['displayText']
                                            )
                                        )
                                    )
                                
                                quick_reply = QuickReply(items=quick_reply_items)
                                flex_message = FlexMessage(
                                    alt_text=f"班次 #{trip_id} 詳細信息",
                                    contents=FlexContainer.from_dict(result['flex_message']),
                                    quick_reply=quick_reply
                                )
                                
                                # 发送带Quick Reply的Flex Message
                                reply_message(reply_token, [flex_message])
                            else:
                                # 发送普通Flex Message
                                reply_flex(reply_token, f"班次 #{trip_id} 詳細信息", result['flex_message'])
                            
                            current_app.logger.info("成功发送Flex Message")
                            return
                        except Exception as flex_error:
                            current_app.logger.error(f"发送Flex Message时出错: {flex_error}")
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
            
        # 查詢固定班次
        elif message_text.startswith("查詢固定班次"):
            # --- 恢復條件判斷邏輯 --- 
            try:
                parts = message_text.split()
                if len(parts) > 1:
                    # 如果命令包含日期或其他參數，執行實際查詢
                    logger.info(f"處理查詢固定班次命令 (帶日期): {message_text}")
                    # 優先使用Flex Message版本
                    from modules.services.trip_query_service import handle_query_fixed_trips_flex, handle_query_fixed_trips
                    flex_content, error_message = handle_query_fixed_trips_flex(message_text)
                    if flex_content and error_message is None:
                        reply_flex(reply_token, "固定班次查詢結果", flex_content)
                    else:
                        logger.info(f"固定班次查詢 Flex 失敗或無結果，回退文本: {error_message}")
                        result = handle_query_fixed_trips(message_text)
                        reply_text(reply_token, result)
                else:
                    # 如果命令只有"查詢固定班次"，觸發日期選擇
                    logger.info(f"處理查詢固定班次命令 (觸發日期選擇): {message_text}")
                    from modules.services.trip_query_service import request_fixed_trip_date_selection
                    reply_msg, error_message = request_fixed_trip_date_selection()
                    if reply_msg and error_message is None:
                        reply_message(reply_token, [reply_msg]) 
                    else:
                        reply_text(reply_token, error_message or "無法生成日期選擇")
                return # 處理完畢

            except Exception as e:
                logger.error(f"處理查詢固定班次時出錯: {e}")
                traceback.print_exc()
                reply_text(reply_token, f"處理請求時出錯: {str(e)}")
                return
            # --- 結束恢復 ---
            
        # 更新已完成班次
        elif message_text == "更新已完成班次":
            from modules.services.scheduler_service import update_completed_trips
            result_text = update_completed_trips()
            reply_text(reply_token, result_text)
            return
            
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
            
        # 未識別的命令
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
1. 查詢班次 [日期] - 查詢指定日期的班次（包含固定和臨時）
2. 查詢固定班次 [日期] - 只查詢固定班次，不包含臨時班次
3. 班次詳情 [ID] - 查看班次詳細信息 (可從此處修改狀態)
4. 指派司機 [ID] - 為班次指派司機
5. 臨時預約 - 開始臨時預約流程
6. 臨時預約幫助 - 顯示臨時預約相關說明
7. 幫助 - 顯示此幫助信息

在群組中使用時，可以選擇性在命令前添加前綴：!、# 或 /
例如：!查詢班次、#幫助，也可以直接輸入「查詢班次」「幫助」等
"""
