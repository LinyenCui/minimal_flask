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
        elif active_conversation.conversation_type == 'temp_booking':
            # 預約叫車對話
            return handle_temp_booking_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'passenger_leave':
            # 乘客請假對話 - 使用新的處理器
            from modules.handlers.leave_mode_handler import handle_passenger_leave_conversation
            return handle_passenger_leave_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'driver_assign':
            # 司機指派對話
            return handle_driver_assign_conversation(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'accounting_deposit':
            # 記錄入金對話（新帳務處理）
            from modules.handlers.accounting import handle_deposit_input
            return handle_deposit_input(active_conversation, message_text, user_id, reply_token)
        elif active_conversation.conversation_type == 'accounting_weekly_charge':
            # 記錄上週扣款對話（新帳務處理）
            from modules.handlers.accounting import handle_weekly_input
            return handle_weekly_input(active_conversation, message_text, user_id, reply_token)
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
        
        # 序列修復命令
        elif message_text.startswith("fix-sequence"):
            logger.info(f"用戶 {user_id} 請求序列修復")
            try:
                response = handle_sequence_fix_start(user_id)
                
                if response:
                    # 使用統一響應處理器
                    success = ResponseHandler.handle_legacy_format(reply_token, response)
                    if not success:
                        reply_text(reply_token, "❌ 處理序列修復響應時出錯")
                else:
                    reply_text(reply_token, "❌ 無法獲取序列狀態")
            except Exception as e:
                logger.error(f"序列修復命令處理失敗: {e}")
                reply_text(reply_token, f"❌ 序列修復檢查失敗: {str(e)}")
            return
        
        # 資料庫同步相關命令（委派給輕路由）
        from modules.handlers.sync_router import handle_sync_commands
        handled = handle_sync_commands(message_text, user_id, reply_token)
        if handled:
            return
        
        # 批量加成命令
        elif message_text.startswith("batch-allowance") or message_text.startswith("批量加成"):
            logger.info(f"用戶 {user_id} 請求批量加成")
            from modules.handlers.batch_allowance_handler import handle_batch_allowance_start
            response = handle_batch_allowance_start(user_id)
            
            if response:
                reply_text(reply_token, response.get("text", "啟動批量加成中..."))
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
            
        # 查詢相關命令（委派給輕路由）
        from modules.handlers.query_router import handle_query_commands
        handled = handle_query_commands(message_text, user_id, reply_token)
        if handled:
            return
        
        # 更新已完成班次
        elif message_text == "更新已完成班次":
            from modules.services.scheduler_service import update_completed_trips
            result_text = update_completed_trips()
            reply_text(reply_token, result_text)
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
                # 使用新的請假模式處理器設置上下文
                try:
                    from modules.handlers.leave_mode_handler import set_leave_mode_with_context
                    conversation_manager.set_recent_fixed_schedule_id(user_id, int(schedule_id))
                    set_leave_mode_with_context(user_id, fixed_schedule_id=int(schedule_id))
                except Exception as context_error:
                    logger.error(f"❌ 設置請假模式時出錯: {context_error}")
                    logger.error(f"❌ 詳細錯誤: {traceback.format_exc()}")
                
                # 🔥 新增：提供Quick Reply退出機制（參考車資修改和班次請假成功模式）
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                
                # 創建Quick Reply按鈕
                quick_reply_items = [
                    QuickReplyItem(
                        action=MessageAction(
                            label="❌ 放棄操作",
                            text="放棄操作"
                        )
                    )
                ]
                
                quick_reply = QuickReply(items=quick_reply_items)
                message_text = f"固定班次 #{schedule_id} 乘客長期請假\n\n請輸入：[原因] [加成]\n\n例如：\n診所乘客長期住院 -50\n出國一個月 0\n搬家不再需要 -100\n\n💡 提示：先寫原因，最後寫加成金額\n\n🚪 退出方式：點擊下方「放棄操作」按鈕"
                
                # 使用與車資修改相同的Quick Reply發送機制
                reply_message_with_quick_reply(reply_token, message_text, quick_reply)
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
        # 排除特定命令，不交給智能助手處理
        excluded_commands = ["fix-sequence", "batch-allowance", "批量加成"]
        if message_text in excluded_commands:
            logger.info(f"❌ 命令 '{message_text}' 在排除列表中，但沒有被正確處理")
            reply_text(reply_token, f"❌ 未識別的命令: {message_text}\n\n請使用「幫助」查看可用命令")
            return
        
        # 請假模式相關處理（使用新的處理器）
        from modules.handlers.leave_mode_handler import handle_leave_mode_commands
        if handle_leave_mode_commands(message_text, user_id, reply_token):
            return
        
        # 🔥 簡單請假格式檢測已移至 leave_mode_handler
        # 以下代碼將在第三階段清理

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
                
                # 🔥 新增：智能助手路由的跨日期範圍查詢（支援翻頁）
                elif command.startswith("查已完成範圍"):
                    try:
                        logger.info(f"🎯 智能助手路由查已完成範圍命令: {command}")
                        from modules.services.date_range_query_service import handle_query_completed_trips_range
                        result = handle_query_completed_trips_range(command, user_id)
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
                        result = handle_query_current_trips_range(command, user_id)
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
15. 生成月報表 [類別] [YYYY-MM] - 生成月報表 (類別: 診所/東洋/全部, 可選指定月份)

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
    
    # 🔥 修復：導入conversation_manager
    
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
                    # 🔥 CRITICAL修復：傳遞parsed_command，避免確認對話中parsed_command為None
                    result = handle_smart_fare_query(message_text, user_id, use_flex=True, parsed_command=command)
                    handle_ai_fare_result(result, reply_token)
                elif command.startswith("查已完成"):
                    from modules.services.ai_fare_service import handle_smart_fare_query
                    # 🔥 CRITICAL修復：傳遞parsed_command，避免確認對話中parsed_command為None
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
    
    # 🔥 修復：導入conversation_manager
    
    if conversation.current_step == 'waiting_confirmation':
        # 檢查用戶的回覆類型
        confirmation_keywords = ['確認', '對的', '正確', 'yes', '是', '對', 'ok', '好', '確認正確']
        rejection_keywords = ['不對', '錯誤', '不是', 'no', '錯', '不正確', '理解錯誤']
        cancel_keywords = ['放棄', '取消', '退出', '放棄查詢']
        
        message_lower = message_text.lower().strip()
        
        # 🔥 修復：檢查用戶是否要取消操作
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
                    # 🔥 CRITICAL修復：避免無限循環，如果沒有已解析命令，直接使用AdvancedQueryProcessor
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
            # 🔥 新增：用戶行為不可測，輸入其他內容時直接取消對話
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
