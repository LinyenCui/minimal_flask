# modules/handlers/text_message_handler.py
# 測試修改 - 觸發自動文檔同步檢查
import traceback
import logging
from flask import current_app
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.unified_date_parser import parse_date_input
from modules.utils.conversation_context import conversation_manager

from modules.utils.line_bot import (
    reply_text, reply_message, reply_flex,
    create_postback_action, create_message_action,
    create_flex_message, get_line_bot_api,
    reply_message_with_quick_reply
)
from modules.utils.response_handler import ResponseHandler
from modules.utils.quick_reply_manager import QuickReplyManager
from modules.handlers.trip_handler import handle_query_trips, handle_trip_details, handle_change_status, handle_record_fare, handle_modify_category, handle_completed_trip_details
from modules.flex_designs.help_flex import get_help_flex
from modules.help_system.help_handler import HelpHandler
from modules.handlers.temp_booking_handler import (
    handle_temp_booking_help
)
from modules.handlers.temp_booking_session import (
    is_booking_active,
    start_booking,
    handle_booking_message
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
from modules.services.report_service import handle_generate_weekly_report

# AI功能導入
from modules.services.smart_assistant import process_with_smart_assistant, format_smart_response

# 設定日誌
logger = logging.getLogger(__name__)

def handle_ai_fare_result(result, reply_token: str):
    """統一處理AI車資查詢結果，使用新的響應處理器"""
    try:
        # 使用統一的響應處理器
        success = ResponseHandler.handle_legacy_format(reply_token, result)
        
        if not success:
            logger.warning("使用響應處理器失敗，回退到基本文字回覆")
            reply_text(reply_token, "❌ 處理查詢結果時出現錯誤")
            
    except Exception as e:
        logger.error(f"處理AI車資查詢結果時出錯: {e}")
        reply_text(reply_token, "❌ 處理查詢結果時出現錯誤")

# 初始化幫助系統處理器
help_handler = HelpHandler()

def process_text_message(event):
    """處理文本消息的主函數"""
    # 傳入的 event.message.text 應該是已經過 webhook.py 處理的文本
    message_text = event.message.text 
    reply_token = event.reply_token
    
    # 🚨 修復：安全獲取user_id，避免Source沒有user_id屬性的錯誤
    try:
        # 🚕 車資試算（配置驅動，安全插入點）
        # 在進入大量路由前，先快速匹配以避免被其他處理攔截
        try:
            from modules.handlers.fare_calc_handler import is_fare_calc_command, looks_like_fare_calc, handle_fare_calc
            # 嚴格匹配或寬鬆判斷都先攔截，避免落入AI
            if is_fare_calc_command(message_text) or looks_like_fare_calc(message_text):
                try:
                    reply_text(reply_token, handle_fare_calc(message_text))
                except Exception as calc_err:
                    logger.error(f"車資試算處理失敗：{calc_err}")
                    reply_text(reply_token, "❌ 車資試算失敗，請稍後再試\n用法：車資試算 <公里> [停等分鐘] [日間|夜間]")
                return
        except Exception as fare_cmd_err:
            logger.error(f"車資試算命令處理失敗或未載入：{fare_cmd_err}")
        user_id = event.source.user_id if hasattr(event.source, 'user_id') else None
        if not user_id:
            logger.warning(f"無法獲取user_id，Source類型: {type(event.source)}")
            return
    except Exception as e:
        logger.error(f"獲取user_id時出錯: {e}")
        return
    
    # 記錄將要處理的文本
    logger.info(f"Processing text message handed over: '{message_text}' (Normalized: '{message_text}')")
    
    # 🔥🔥🔥🔥🔥 霸王清除指令 - 強制重置所有對話狀態回到本初
    # 支援：!!!!!、見相非相、reset
    if message_text.strip() in ['!!!!!', '見相非相', 'reset', 'RESET']:
        logger.info(f"🔥🔥🔥🔥🔥 霸王清除！用戶 {user_id} 觸發強制重置")
        # 清除所有可能的對話狀態
        conversation_manager.clear_pending_operation(user_id)
        conversation_manager.clear_leave_mode(user_id)
        try:
            conversation_manager.end_conversation(user_id, "霸王清除")
        except:
            pass
        # 清除序列修復狀態（已在文件頂部導入）
        if user_id in sequence_fix_states:
            del sequence_fix_states[user_id]
        # 清除批量加成狀態
        try:
            from modules.handlers.batch_allowance_handler import batch_allowance_states as bas
            if user_id in bas:
                del bas[user_id]
        except:
            pass
        # 清除臨時預約狀態
        try:
            from modules.handlers.temp_booking_session import end_booking
            end_booking(user_id)
        except:
            pass
        
        reply_text(reply_token, "🔥🔥🔥🔥🔥 見諸相非相，即見如來\n\n✨ 所有對話狀態已清除，回到本初\n💡 您可以重新開始任何操作")
        return
    
    # 🔥 統一對話狀態檢查 - 防止智能助手搶戲
    
    # 1. 檢查是否有活躍對話
    active_conversation = conversation_manager.get_active_conversation(user_id)
    logger.info(f"🔍 對話狀態檢查 - 用戶: {user_id}, 活躍對話: {active_conversation}")
    if active_conversation:
        logger.info(f"🎯 用戶在活躍對話中: {active_conversation.conversation_type}, 步驟: {active_conversation.current_step}")
        
        # 2. 檢查是否是取消命令
        if conversation_manager.can_user_cancel_with_message(user_id, message_text):
            conversation_manager.end_conversation(user_id, f"用戶取消: {message_text}")
            reply_text(reply_token, "✅ 已取消操作\n\n💡 您可以重新發起新的命令")
            return
        
        # 3. 根據對話類型分發處理
        if active_conversation.conversation_type == 'fare_modification':
            # 車資修改對話 - 使用新的處理器
            from modules.handlers.fare_modification_handler import handle_fare_modification_conversation
            return handle_fare_modification_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'passenger_leave':
            # 乘客請假對話 - 使用新的處理器
            from modules.handlers.leave_mode_handler import handle_passenger_leave_conversation
            return handle_passenger_leave_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'accounting_deposit':
            # 記錄入金對話（新帳務處理）
            from modules.handlers.accounting import handle_deposit_input
            return handle_deposit_input(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'accounting_weekly_charge':
            # 記錄上週扣款對話（新帳務處理）
            from modules.handlers.accounting import handle_weekly_input
            return handle_weekly_input(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type in ['query_clarification', 'query_confirmation', 
                                                        'ai_modification_reason', 'temp_booking', 
                                                        'driver_assign']:
            # 使用統一的對話分發器處理
            from modules.handlers.conversation_dispatcher import dispatch_conversation
            return dispatch_conversation(active_conversation, message_text, user_id, reply_token)
        else:
            logger.warning(f"未知的對話類型: {active_conversation.conversation_type}")
            conversation_manager.end_conversation(user_id, "未知對話類型")
    
    # 4. 沒有活躍對話，進入正常處理流程...
    
    # 🔥 2025-12 修復：智能清除舊的 pending_operation
    # 只有當用戶輸入「完全無關的新命令」時才清除，對話流程中的命令不清除
    pending_op = conversation_manager.get_pending_operation(user_id)
    if pending_op:
        msg_stripped = message_text.strip()
        
        # 🔥 對話流程中的命令（不應該清除 pending_operation）
        conversation_flow_commands = [
            # 取消/放棄命令
            '取消', '算了', '放棄', '放棄操作', '取消操作',
            # 第一層選擇命令
            '選擇請假', '選擇註銷', '選擇衝突',
            # 批量操作命令
            '全部請假', '全部註銷', '全部衝突', '全部改回準備',
        ]
        
        # 檢查是否是對話流程命令（包括 #ID請假、#ID改回、修改狀態 等模式）
        import re
        is_modify_status_cmd = bool(re.match(r'^修改狀態\s+\d+\s+\S+$', msg_stripped))  # 修改狀態 852 註銷
        
        is_conversation_cmd = (
            msg_stripped in conversation_flow_commands or
            msg_stripped.endswith('請假') or  # 如 #852請假
            msg_stripped.endswith('改回') or  # 如 #852改回
            msg_stripped.endswith('註銷') or  # 如 #852註銷
            msg_stripped.endswith('衝突') or  # 如 #852衝突
            msg_stripped.startswith('班次詳情') or  # 班次詳情 xxx
            is_modify_status_cmd  # 修改狀態 852 註銷
        )
        
        if not is_conversation_cmd:
            # 用戶輸入了完全無關的新命令，自動清除舊的對話狀態
            old_action = pending_op.get('action', '未知')
            logger.info(f"🔄 用戶 {user_id} 輸入新命令，自動清除舊的對話狀態: {old_action}")
            conversation_manager.clear_pending_operation(user_id)
    
    try:
        # 🔥🔥🔥 2025-12 修復：將請假模式命令處理提前到最前面
        # 確保第二層命令（選擇註銷、選擇衝突、選擇請假、全部註銷等）被優先處理
        # 不會被其他 router 攔截
        from modules.handlers.leave_mode_handler import handle_leave_mode_commands
        if handle_leave_mode_commands(message_text, user_id, reply_token):
            logger.info(f"✅ leave_mode_handler 已處理命令: {message_text}")
            return
        
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
        
        # 檢查用戶是否在臨時預約流程中（改用外觀層）
        if is_booking_active(user_id):
            # 處理臨時預約消息
            logger.info(f"用戶 {user_id} 在臨時預約流程中，處理消息: {message_text}")
            response = handle_booking_message(user_id, message_text)
            
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
                        # 使用統一響應處理器
                        sent = ResponseHandler.handle_legacy_format(reply_token, response)
                        if not sent:
                            # If it's a plain flex dict (alt_text/contents),發送 Flex
                            if "alt_text" in response and "contents" in response:
                                try:
                                    reply_flex(reply_token, response.get("alt_text", "預約流程"), response.get("contents"))
                                except Exception as e:
                                    logger.error(f"臨時預約回覆Flex失敗: {e}")
                                    reply_text(reply_token, response.get("text", "處理中..."))
                            else:
                                # 回退文字
                                text_content = response.get("text", "處理中...")
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
        
        # 帳務處理功能入口與流程
        if message_text in ["帳務處理", "help_category_accounting"]:
            from modules.handlers.accounting import show_accounting_menu
            show_accounting_menu(reply_token)
            return
        # 🏥 診所座標/平均車速/到院訊息 相關命令 → 輕路由（不影響其他功能）
        try:
            from modules.handlers.clinic_commands_router import handle_clinic_meta_commands
            chat_id = getattr(event.source, 'group_id', None) or getattr(event.source, 'room_id', None) or getattr(event.source, 'user_id', None)
            if handle_clinic_meta_commands(message_text, chat_id, reply_token):
                return
        except Exception as _router_err:
            logger.error(f"clinic_meta_commands 路由失敗: {_router_err}")
        if message_text == "acct_deposit_start":
            from modules.handlers.accounting import handle_deposit_start
            handle_deposit_start(user_id, reply_token)
            return
        if message_text == "acct_weekly_start":
            from modules.handlers.accounting import handle_weekly_start
            handle_weekly_start(user_id, reply_token)
            return
        if message_text == "acct_ledger_start":
            from modules.handlers.accounting import start_ledger
            start_ledger(reply_token, user_id)
            return
        if message_text.startswith("acct_ledger_next:"):
            # 格式：acct_ledger_next:<last_ts>:<last_id>:<from_date>:<to_date>
            try:
                payload = message_text[len("acct_ledger_next:"):]
                parts = payload.rsplit(":", 3)
                # 可能只有 last_ts:last_id
                if len(parts) == 2:
                    last_ts, last_id = parts[0], int(parts[1])
                    from_date = None
                    to_date = None
                elif len(parts) == 4:
                    last_ts, last_id, from_date, to_date = parts[0], int(parts[1] or 0), (parts[2] or None), (parts[3] or None)
                else:
                    raise ValueError("parts len")
                from modules.handlers.accounting import next_ledger
                next_ledger(reply_token, last_ts, last_id, from_date, to_date, page_no=0)
            except Exception as _:
                reply_text(reply_token, "格式錯誤，請重新操作")
            return

        # 臨時預約命令
        if message_text.startswith("預約叫車"):
            logger.info(f"用戶 {user_id} 請求 預約叫車 (AI流程)")
            response = start_booking(user_id)
            
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
                    # 使用統一響應處理器
                    success = ResponseHandler.handle_legacy_format(reply_token, response)
                    if not success:
                        # 回退處理
                        text_content = response.get("text", "開始臨時預約流程...")
                        reply_text(reply_token, text_content)
            return
        
        # 系統維護命令（使用新路由器）
        from modules.handlers.system_router import handle_system_commands
        if handle_system_commands(message_text, user_id, reply_token):
            return
        
        # 資料庫同步相關命令（委派給輕路由）
        from modules.handlers.sync_router import handle_sync_commands
        handled = handle_sync_commands(message_text, user_id, reply_token)
        if handled:
            return
        
        
        # 班次詳情（委派輕路由）
        elif message_text.startswith("班次詳情"):
            from modules.handlers.view_router import handle_view_commands
            if handle_view_commands(message_text, user_id, reply_token):
                return

        # 查看已完成班次詳情（委派輕路由）
        elif message_text.startswith("查看"):
            from modules.handlers.view_router import handle_view_commands
            if handle_view_commands(message_text, user_id, reply_token):
                return


        
        # 司機指派相關命令（委派給輕路由）
        from modules.handlers.driver_router import handle_driver_commands
        handled = handle_driver_commands(message_text, user_id, reply_token)
        if handled:
            return
            
        # 🔰 幫助系統處理（使用獨立的 HelpHandler）
        from modules.handlers.help_router import handle_help_commands
        handled = handle_help_commands(message_text, user_id, reply_token)
        if handled:
            return
            
            
            
        # 查詢相關命令（委派給輕路由）
        from modules.handlers.query_router import handle_query_commands
        handled = handle_query_commands(message_text, user_id, reply_token)
        if handled:
            return
        
            
        # 帳務處理（委派輕路由）
        from modules.handlers.accounting_router import handle_accounting_commands
        handled = handle_accounting_commands(message_text, user_id, reply_token)
        if handled:
            return

        # 報表相關命令（委派給輕路由）
        from modules.handlers.report_router import handle_report_commands
        handled = handle_report_commands(message_text, user_id, reply_token)
        if handled:
            return
        
        # 修改/記錄/類別 相關（委派）
        from modules.handlers.modification_router import handle_modification_commands
        handled = handle_modification_commands(message_text, user_id, reply_token)
        if handled:
            return

        # 固定班表/固定請假 相關（委派）
        from modules.handlers.fixed_router import handle_fixed_commands
        handled = handle_fixed_commands(message_text, user_id, reply_token)
        if handled:
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
            
        # 分頁命令（委派）
        from modules.handlers.pagination_router import handle_pagination_commands
        handled = handle_pagination_commands(message_text, user_id, reply_token)
        if handled:
            return

        # 已委派：修改/記錄/類別（modification_router）
        
        # --- 移除：記錄車資早期AI攔截，改用後面的雙軌制處理 ---
        
        
        
        # 車資修改相關命令處理（使用新的處理器）
        from modules.handlers.fare_modification_handler import handle_fare_modification_commands
        if handle_fare_modification_commands(message_text, user_id, reply_token):
            return
        
        # --- AI修改確認和取消處理已移至 fare_modification_handler ---
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
        
        # 🔥 leave_mode_handler 已移至 try 塊開頭，確保第二層命令優先處理

        # 🔥 傳統過去態命令處理（在AI之前，作為穩定的後備機制）
        
        
        # 查已完成/完成記錄（委派歷史路由）
        from modules.handlers.history_router import handle_history_commands
        handled = handle_history_commands(message_text, user_id, reply_token)
        if handled:
            return
        
        # 完成記錄已委派

        # 優先嘗試智能助手處理
        try:
            logger.info(f"🤖 智能助手處理用戶訊息: {message_text}")
            smart_result = process_with_smart_assistant(message_text, user_id)
            
            # 🔥 新增：處理 Function Calling 結果（請假、車資修改等）
            if smart_result["type"] == "function_call":
                logger.info(f"🔧 Function Calling: {smart_result['function_name']}")
                try:
                    from modules.core.intent_executor import IntentExecutor
                    executor = IntentExecutor()
                    
                    # 構建意圖結構
                    intent = {
                        "action": smart_result["function_name"],
                        "params": smart_result["parameters"],
                        "confidence": smart_result.get("confidence", 0.9)
                    }
                    
                    # 執行意圖
                    execute_result = executor.execute(intent, user_id, reply_token)
                    
                    # IntentExecutor 已經處理了回覆，直接返回
                    if execute_result.get("success"):
                        return
                    
                    # 如果執行失敗且有錯誤消息，發送給用戶
                    if execute_result.get("message"):
                        reply_text(reply_token, execute_result.get("message"))
                        return
                
                except Exception as e:
                    logger.error(f"Function Calling 執行失敗: {e}", exc_info=True)
                    # FC 失敗，降級到傳統處理（不發送錯誤消息，讓後續邏輯處理）
                    pass
            
            elif smart_result["type"] == "execute_command":
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
                
                # 🚕 新增：車資試算（AI產生標準命令的情況下也支援）
                elif command.startswith("車資試算"):
                    try:
                        from modules.handlers.fare_calc_handler import handle_fare_calc
                        reply_text(reply_token, handle_fare_calc(command))
                        return
                    except Exception as e:
                        logger.error(f"車資試算(來自AI)處理失敗: {e}")
                        reply_text(reply_token, "❌ 車資試算失敗，請稍後再試\n用法：車資試算 <公里> [停等分鐘] [日間|夜間]")
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
                
                # 🔥 新增：智能助手路由的跨日期範圍查詢（支援翻頁 + Quick Reply）
                elif command.startswith("查已完成範圍"):
                    try:
                        logger.info(f"🎯 智能助手路由查已完成範圍命令: {command}")
                        from modules.services.date_range_query_service import handle_query_completed_trips_range
                        from linebot.v3.messaging import TextMessage
                        result = handle_query_completed_trips_range(command, user_id)
                        
                        if isinstance(result, dict):
                            # 有 Quick Reply 的結果
                            text_msg = TextMessage(text=result['message'], quick_reply=result.get('quick_reply'))
                            reply_message(reply_token, [text_msg])
                        else:
                            # 純文字結果
                            reply_text(reply_token, result)
                        return
                    except Exception as e:
                        logger.error(f"❌ 查已完成範圍處理失敗: {e}")
                        reply_text(reply_token, f"查詢失敗: {str(e)}")
                        return
                        
                elif command.startswith("查班次範圍"):
                    try:
                        logger.info(f"🎯 智能助手路由查班次範圍命令: {command}")
                        from modules.services.date_range_query_service import handle_query_current_trips_range
                        from linebot.v3.messaging import TextMessage
                        result = handle_query_current_trips_range(command, user_id)
                        
                        if isinstance(result, dict):
                            # 有 Quick Reply 的結果
                            text_msg = TextMessage(text=result['message'], quick_reply=result.get('quick_reply'))
                            reply_message(reply_token, [text_msg])
                        else:
                            # 純文字結果
                            reply_text(reply_token, result)
                        return
                    except Exception as e:
                        logger.error(f"❌ 查班次範圍處理失敗: {e}")
                        reply_text(reply_token, f"查詢失敗: {str(e)}")
                        return

                elif command.startswith("查已完成"):
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    # 🔥 CRITICAL修復：傳遞parsed_command，避免確認對話中parsed_command為None
                    result = handle_smart_fare_query(command, user_id, use_flex=True, parsed_command=command)
                    handle_ai_fare_result(result, reply_token)
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
                        conversation_manager.clear_leave_mode(user_id)
                        
                        reply_text(reply_token, result)
                        return
                    except Exception as e:
                        logger.error(f"乘客請假執行失敗: {e}")
                        reply_text(reply_token, f"❌ 請假執行失敗：{str(e)}")
                        return
                
                # 🔥 2025-12 修復：修改班次狀態命令的處理（AI生成格式：修改班次 xxx 狀態=yyy）
                elif command.startswith("修改班次") and "狀態=" in command:
                    try:
                        import re
                        match = re.match(r'修改班次\s+(\d+)\s+狀態=(.+)', command.strip())
                        if match:
                            trip_id = match.group(1)
                            new_status = match.group(2).strip()
                            
                            logger.info(f"🔧 執行狀態修改：班次 #{trip_id} → {new_status}")
                            
                            # 轉換為標準命令格式並調用處理器
                            from modules.handlers.trip_status_handler import handle_update_trip_status
                            standard_command = f"修改狀態 {trip_id} {new_status}"
                            result = handle_update_trip_status(standard_command, user_id)
                            
                            # 清除相關對話狀態
                            conversation_manager.clear_pending_operation(user_id)
                            
                            reply_text(reply_token, result)
                            return
                        else:
                            reply_text(reply_token, f"❌ 命令格式錯誤：{command}")
                            return
                    except Exception as e:
                        logger.error(f"修改班次狀態執行失敗: {e}")
                        reply_text(reply_token, f"❌ 修改狀態失敗：{str(e)}")
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
                    # 🔥 修復：其他命令需要繼續處理，而不是直接return
                    reply_text(reply_token, f"🤖 AI理解您的需求：{command}\n正在處理...")
                    # 🔥 關鍵修復：將解析出的command設為用戶輸入，繼續在主處理邏輯中執行
                    text = command  # 將AI解析的命令替換為用戶輸入，繼續執行後續邏輯
                    # 不要return，讓程序繼續執行主處理邏輯
                
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


