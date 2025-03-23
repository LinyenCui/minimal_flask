# modules/handlers/text_message_handler.py
import traceback
import logging
from flask import current_app

from modules.utils.line_bot import reply_text, reply_flex, reply_message
from modules.handlers.trip_handler import handle_query_trips, handle_trip_details, handle_change_status
from modules.flex_designs.help_flex import get_help_flex

# 設定日誌
logger = logging.getLogger(__name__)

def process_text_message(event):
    """處理文本消息的主函數"""
    message_text = event.message.text
    reply_token = event.reply_token
    user_id = event.source.user_id
    
    try:
        # 查詢班次
        if message_text.startswith("查詢班次"):
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
                    # 使用限定名稱調用函數，避免命名衝突
                    from modules.utils.line_bot import reply_flex as send_flex
                    send_flex(reply_token, "班次查詢結果", flex_content)
                    return
                else:
                    # 如果出錯或沒有結果，顯示錯誤消息或使用文本版本
                    logger.info(f"無Flex內容或有錯誤，使用文本版本。錯誤: {error_message}")
                    result = handle_query_trips(message_text)
                    from modules.utils.line_bot import reply_text as send_text
                    send_text(reply_token, result)
                    return
            except Exception as e:
                logger.error(f"處理查詢班次時出錯: {e}")
                traceback.print_exc()
                # 使用文本版本作為後備
                from modules.services.trip_query_service import handle_query_trips
                result = handle_query_trips(message_text)
                from modules.utils.line_bot import reply_text as send_text
                send_text(reply_token, f"Flex消息處理錯誤，使用文本版本：\n{result}")
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
                            from modules.utils.line_bot import reply_flex, reply_message
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
            
        # 修改狀態
        elif message_text.startswith('修改狀態'):
            result = handle_change_status(message_text)
            reply_text(reply_token, result)
            
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
                        # 直接使用字典作为参数传递给reply_flex
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
            
        # 處理匯入固定班次（一整周）
        elif message_text.startswith("匯入固定班次"):
            from modules.handlers.import_handler import handle_import_fixed_trips_week
            result_text = handle_import_fixed_trips_week(message_text)
            reply_text(reply_token, result_text)
            return
            
        # 查詢固定班次
        elif message_text.startswith("查詢固定班次"):
            try:
                logger.info(f"處理查詢固定班次命令: {message_text}")
                # 優先使用Flex Message版本
                from modules.services.fixed_trip_service import handle_query_fixed_trips_flex, handle_query_fixed_trips
                
                # 记录调用前的状态
                logger.info("即將調用handle_query_fixed_trips_flex函數")
                flex_content, error_message = handle_query_fixed_trips_flex(message_text)
                logger.info(f"handle_query_fixed_trips_flex返回結果: flex_content類型={type(flex_content)}, error_message={error_message}")
                
                if flex_content and error_message is None:
                    # 如果有Flex內容，使用Flex Message回覆
                    logger.info("使用Flex回覆查詢結果")
                    # 使用限定名稱調用函數，避免命名衝突
                    from modules.utils.line_bot import reply_flex as send_flex
                    send_flex(reply_token, "固定班次查詢結果", flex_content)
                    return
                else:
                    # 如果出錯或沒有結果，顯示錯誤消息或使用文本版本
                    logger.info(f"無Flex內容或有錯誤，使用文本版本。錯誤: {error_message}")
                    result = handle_query_fixed_trips(message_text)
                    from modules.utils.line_bot import reply_text as send_text
                    send_text(reply_token, result)
                    return
            except Exception as e:
                logger.error(f"處理查詢固定班次時出錯: {e}")
                traceback.print_exc()
                # 使用文本版本作為後備
                from modules.services.fixed_trip_service import handle_query_fixed_trips
                result = handle_query_fixed_trips(message_text)
                from modules.utils.line_bot import reply_text as send_text
                send_text(reply_token, f"Flex消息處理錯誤，使用文本版本：\n{result}")
                return
            
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
            
        # 其他命令...可以繼續添加
        else:
            reply_text(reply_token, "未識別的命令。請使用「幫助」查看可用命令。")
            
    except Exception as e:
        logger.error(f"處理消息時出錯: {e}")
        traceback.print_exc()
        reply_text(reply_token, f"處理命令時出錯: {str(e)}")

def get_help_text():
    """取得文字版幫助信息"""
    return """可用命令列表：
1. 查詢班次 [日期] - 查詢指定日期的班次
2. 班次詳情 [班次ID] - 查看班次詳細信息
3. 修改狀態 [班次ID] [新狀態] - 修改班次狀態
4. 幫助 - 顯示此幫助信息

在群組中使用時，需在命令前添加前綴：!、# 或 /
例如：!查詢班次、#幫助
"""
