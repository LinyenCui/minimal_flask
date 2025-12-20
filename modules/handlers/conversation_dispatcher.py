"""
對話分發器 - 集中管理所有對話處理邏輯
將 text_message_handler.py 中的對話處理函數集中到此處
"""

import logging
from modules.utils.conversation_context import conversation_manager
from modules.utils.line_bot import reply_text, reply_message, reply_flex, reply_message_with_quick_reply
from modules.utils.response_handler import ResponseHandler

logger = logging.getLogger(__name__)


def dispatch_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """
    根據對話類型分發到對應的處理函數
    
    Args:
        conversation: 活躍對話對象
        message_text: 用戶輸入
        user_id: 用戶ID
        reply_token: LINE回覆token
    """
    conversation_type = conversation.conversation_type
    
    logger.info(f"🎯 分發對話: 類型={conversation_type}, 步驟={conversation.current_step}")
    
    # 根據對話類型分發
    handlers = {
        'temp_booking': handle_temp_booking_conversation,
        'driver_assign': handle_driver_assign_conversation,
        'query_clarification': handle_query_clarification_conversation,
        'query_confirmation': handle_query_confirmation_conversation,
        'fare_modification_reason': handle_ai_modification_reason_conversation,
        'ai_modification_reason': handle_ai_modification_reason_conversation,  # ai_fare_service.py 使用這個名稱
    }
    
    handler = handlers.get(conversation_type)
    
    if handler:
        return handler(conversation, message_text, user_id, reply_token)
    else:
        logger.warning(f"⚠️ 未知的對話類型: {conversation_type}")
        conversation_manager.end_conversation(user_id, "未知對話類型")
        reply_text(reply_token, "❌ 對話處理錯誤，請重新開始")


def handle_temp_booking_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理預約叫車對話"""
    logger.info(f"🎯 處理預約叫車對話: 步驟={conversation.current_step}")
    
    # 使用外觀層邏輯，確保成功/取消時結束對話
    from modules.handlers.temp_booking_session import handle_booking_message
    response = handle_booking_message(user_id, message_text)
    
    if response:
        # 依據回傳類型正確發送（避免將Flex字典當文字印出）
        if response.get("type") == "flex":
            try:
                if "quick_reply" in response:
                    # 以字典形式交由 reply_message 生成 FlexMessage + QuickReply
                    flex_message = {
                        "type": "flex",
                        "altText": response.get("alt_text", "預約流程"),
                        "contents": response.get("contents"),
                        "quickReply": response.get("quick_reply")
                    }
                    reply_message(reply_token, [flex_message])
                else:
                    reply_flex(reply_token, response.get("alt_text", "預約流程"), response.get("contents"))
            except Exception as e:
                logger.error(f"預約叫車對話發送Flex失敗: {e}")
                # 降級為文字
                if "text" in response:
                    reply_text(reply_token, response.get("text"))
                else:
                    reply_text(reply_token, "處理中...")
            return
        elif response.get("type") == "text":
            text_content = response.get("text", "處理中...")
            if "quick_reply" in response:
                logger.info("對話模式發送帶有QuickReply的文字消息")
                reply_message_with_quick_reply(reply_token, text_content, response.get("quick_reply"))
            else:
                reply_text(reply_token, text_content)
            return
        else:
            # 嘗試使用統一響應處理器；若仍無法處理，再降級為文字
            handled = ResponseHandler.handle_legacy_format(reply_token, response)
            if not handled:
                reply_text(reply_token, str(response))
            return
    
    # 如果沒有回覆，結束對話
    conversation_manager.end_conversation(user_id, "預約流程結束")
    reply_text(reply_token, "預約流程已結束")


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
    
    if conversation.current_step == 'waiting_clarification':
        # 用戶提供了澄清信息，重新處理查詢
        logger.info(f"🔄 用戶提供澄清信息，重新處理: {message_text}")
        
        # 結束澄清對話
        conversation_manager.end_conversation(user_id, "澄清完成")
        
        # 重新處理用戶的查詢（遞歸調用）
        try:
            # 統一使用智能助手作為唯一入口
            from modules.services.smart_assistant import process_with_smart_assistant
            smart_result = process_with_smart_assistant(message_text, user_id)
            
            if smart_result["type"] == "execute_command":
                # 智能助手解析出了標準命令，執行對應命令
                command = smart_result["command"]
                logger.info(f"🎯 澄清後智能助手生成命令: {command}")
                
                # 統一命令執行邏輯
                if command.startswith("記錄車資"):
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    from modules.handlers.text_message_handler import handle_ai_fare_result
                    result = handle_smart_fare_query(message_text, user_id, use_flex=True, parsed_command=command)
                    handle_ai_fare_result(result, reply_token)
                elif command.startswith("查已完成"):
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    from modules.handlers.text_message_handler import handle_ai_fare_result
                    result = handle_smart_fare_query(command, user_id, use_flex=True, parsed_command=command)
                    handle_ai_fare_result(result, reply_token)
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
    
    if conversation.current_step == 'waiting_confirmation':
        # 檢查用戶的回覆類型
        confirmation_keywords = ['確認', '對的', '正確', 'yes', '是', '對', 'ok', '好', '確認正確']
        rejection_keywords = ['不對', '錯誤', '不是', 'no', '錯', '不正確', '理解錯誤']
        cancel_keywords = ['放棄', '取消', '退出', '放棄查詢']
        
        message_lower = message_text.lower().strip()
        
        # 檢查用戶是否要取消操作
        if any(keyword in message_lower for keyword in cancel_keywords):
            # 用戶要取消查詢
            logger.info(f"🚫 用戶取消查詢操作")
            
            # 結束確認對話
            conversation_manager.end_conversation(user_id, "用戶取消查詢")
            
            reply_text(reply_token, """🚫 已取消查詢操作
            
💡 您可以重新發起查詢，或使用以下方式：
• 傳統命令：查已完成 昨天 司機5386
• 別名命令：完成記錄
• 自然語言：/昨天5386班次""")
            
        elif any(keyword in message_lower for keyword in confirmation_keywords):
            # 用戶確認理解正確，執行原查詢
            logger.info(f"✅ 用戶確認理解正確，執行查詢")
            
            context_data = conversation.context_data
            original_query = context_data.get('original_query', message_text)
            
            # 結束確認對話
            conversation_manager.end_conversation(user_id, "確認完成")
            
            # 修復無限循環：使用智能助手已經生成的標準命令，而不是重新解析原始查詢
            try:
                # 檢查是否有已解析的標準命令
                parsed_command = context_data.get('parsed_command')
                if parsed_command:
                    logger.info(f"🎯 執行智能助手已解析的命令: {parsed_command}")
                    
                    # 確認後仍使用AI車資服務（保持Flex Message），但跳過重新解析
                    try:
                        from modules.services.ai_fare_service import handle_smart_fare_query
                        from modules.handlers.text_message_handler import handle_ai_fare_result
                        # 關鍵修復：使用skip_parsing參數，直接執行已解析命令
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
                    # CRITICAL修復：避免無限循環，如果沒有已解析命令，直接使用AdvancedQueryProcessor
                    logger.warning("⚠️ 沒有已解析命令，使用AdvancedQueryProcessor避免循環")
                    from modules.services.advanced_query_processor import AdvancedQueryProcessor
                    processor = AdvancedQueryProcessor()
                    result = processor.process_complex_query(original_query, user_id)
                    
                    if result.get('type') == 'success':
                        reply_text(reply_token, result['message'])
                    elif result.get('type') == 'success_with_pagination':
                        reply_message_with_quick_reply(reply_token, result['message'], result['quick_reply'])
                    elif result.get('type') == 'no_results':
                        reply_text(reply_token, result['message'])
                    else:
                        reply_text(reply_token, "❌ 查詢執行失敗")
                
            except Exception as e:
                logger.error(f"執行確認後的查詢失敗: {e}")
                reply_text(reply_token, f"❌ 執行查詢時出現錯誤: {str(e)}")
        else:
            # 用戶行為不可測，輸入其他內容時直接取消對話
            logger.info(f"🚫 用戶輸入其他內容，直接取消對話: '{message_text}'")
            
            # 結束確認對話
            conversation_manager.end_conversation(user_id, "用戶輸入其他內容，自動取消")
            
            reply_text(reply_token, """🚫 已取消查詢操作
            
💡 您可以重新發起查詢，或使用以下方式：
• 傳統命令：查已完成 昨天 司機5386
• 別名命令：完成記錄
• 自然語言：/昨天5386班次""")
    else:
        logger.warning(f"未處理的查詢確認對話步驟: {conversation.current_step}")
        conversation_manager.end_conversation(user_id, "未知步驟")


def handle_ai_modification_reason_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """處理AI車資修改原因對話"""
    logger.info(f"🎯 處理AI修改原因對話: 步驟={conversation.current_step}, 消息='{message_text}'")
    
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
        
        # 結束原因收集對話
        conversation_manager.end_conversation(user_id, "原因已收集")
        
        # 顯示確認框（使用現有的 execute_fare_modification）
        try:
            from modules.services.ai_fare_service import execute_fare_modification
            
            modification_intent = {
                'meter_fare': meter_fare,
                'extra_fare': extra_fare,
                'reason': reason
            }
            
            flex_result = execute_fare_modification(trip_data, modification_intent, user_id)
            
            if flex_result and isinstance(flex_result, dict):
                from modules.handlers.text_message_handler import handle_ai_fare_result
                handle_ai_fare_result(flex_result, reply_token)
            else:
                # 降級為文字確認
                reply_text(reply_token, f"""📋 請確認車資修改

班次：#{trip_id}
錶價：{meter_fare}元
加成：{extra_fare}元
原因：{reason}

請回覆「確認AI修改 {trip_id} {meter_fare} {extra_fare} {reason}」來執行修改""")
        except Exception as e:
            logger.error(f"生成確認框失敗: {e}")
            reply_text(reply_token, f"""📋 請確認車資修改

班次：#{trip_id}
錶價：{meter_fare}元
加成：{extra_fare}元  
修改原因：{reason}

請回覆「確認AI修改 {trip_id} {meter_fare} {extra_fare} {reason}」來執行修改""")
    else:
        logger.warning(f"未處理的AI修改原因對話步驟: {conversation.current_step}")
        conversation_manager.end_conversation(user_id, "未知步驟")
        reply_text(reply_token, "❌ 對話狀態錯誤，請重新發起修改")
