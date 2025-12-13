"""
請假模式處理器
處理所有請假相關的邏輯，包括：
- 請假模式管理
- 簡單請假格式處理
- 乘客請假對話流程
"""
import logging
import re
from modules.utils.conversation_context import conversation_manager
from modules.utils.line_bot import reply_text

logger = logging.getLogger(__name__)


def handle_leave_mode_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    處理請假模式相關命令
    返回 True 表示已處理，False 表示未處理
    """
    msg = message_text.strip()
    
    # 處理「放棄操作」命令
    if msg == "放棄操作":
        if conversation_manager.is_in_leave_mode(user_id):
            conversation_manager.clear_leave_mode(user_id)
            reply_text(reply_token, "❌ 已取消請假操作")
            return True
        elif conversation_manager.get_pending_operation(user_id):
            conversation_manager.clear_pending_operation(user_id)
            reply_text(reply_token, "❌ 已取消操作")
            return True
        else:
            reply_text(reply_token, "❌ 目前沒有進行中的操作可以取消")
            return True
    
    # 🔥 第二層：處理「選擇請假」- 顯示全部/單個選項
    # 單個班次：直接跳轉班次詳情，利用已有的操作按鈕
    if msg == "選擇請假":
        logger.info(f"🔍 處理「選擇請假」命令，用戶: {user_id}")
        pending = conversation_manager.get_pending_operation(user_id)
        logger.info(f"🔍 pending_operation: {pending}")
        if pending:
            trips_info = pending.get("trips", [])
            trip_ids = [t.get("id") for t in trips_info if t.get("id")]
            
            if trip_ids:
                # 🔥 2025-12 優化：只有一個班次時，直接跳轉班次詳情
                if len(trip_ids) == 1:
                    single_tid = trip_ids[0]
                    logger.info(f"🎯 只有一個班次 #{single_tid}，直接跳轉班次詳情")
                    from modules.handlers.view_router import handle_view_commands
                    return handle_view_commands(f"班次詳情 {single_tid}", user_id, reply_token)
                
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                items = [QuickReplyItem(action=MessageAction(label="🏥 全部請假", text="全部請假"))]
                # 🔥 單個班次：跳轉班次詳情，利用已有的操作按鈕
                for t in trips_info[:3]:
                    tid = t.get("id")
                    items.append(QuickReplyItem(action=MessageAction(label=f"📋 #{tid}詳情", text=f"班次詳情 {tid}")))
                items.append(QuickReplyItem(action=MessageAction(label="❌ 放棄", text="放棄操作")))
                
                quick_reply = QuickReply(items=items[:13])
                trip_list = "\n".join([f"• #{t.get('id')} {t.get('route', '')}" for t in trips_info[:5]])
                
                from modules.utils.line_bot import reply_message_with_quick_reply
                reply_message_with_quick_reply(
                    reply_token,
                    f"🏥 請假模式\n\n"
                    f"📍 以下班次可設定為請假：\n{trip_list}\n\n"
                    f"❓ 請選擇：\n• 全部請假：批量操作\n• 單個詳情：查看後在詳情頁操作",
                    quick_reply
                )
                return True
        
        reply_text(reply_token, "❌ 沒有待操作的班次\n\n請先查詢班次再操作")
        return True
    
    # 🔥 第二層：處理「選擇註銷」- 顯示全部/單個選項
    # 單個班次：直接跳轉班次詳情，利用已有的操作按鈕
    if msg == "選擇註銷":
        logger.info(f"🔍 處理「選擇註銷」命令，用戶: {user_id}")
        pending = conversation_manager.get_pending_operation(user_id)
        logger.info(f"🔍 pending_operation: {pending}")
        if pending:
            trips_info = pending.get("trips", [])
            trip_ids = [t.get("id") for t in trips_info if t.get("id")]
            
            if trip_ids:
                # 🔥 2025-12 優化：只有一個班次時，直接跳轉班次詳情
                if len(trip_ids) == 1:
                    single_tid = trip_ids[0]
                    logger.info(f"🎯 只有一個班次 #{single_tid}，直接跳轉班次詳情")
                    from modules.handlers.view_router import handle_view_commands
                    return handle_view_commands(f"班次詳情 {single_tid}", user_id, reply_token)
                
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                items = [QuickReplyItem(action=MessageAction(label="🚫 全部註銷", text="全部註銷"))]
                # 🔥 單個班次：跳轉班次詳情，利用已有的操作按鈕
                for t in trips_info[:3]:
                    tid = t.get("id")
                    items.append(QuickReplyItem(action=MessageAction(label=f"📋 #{tid}詳情", text=f"班次詳情 {tid}")))
                items.append(QuickReplyItem(action=MessageAction(label="❌ 放棄", text="放棄操作")))
                
                quick_reply = QuickReply(items=items[:13])
                trip_list = "\n".join([f"• #{t.get('id')} {t.get('route', '')}" for t in trips_info[:5]])
                
                from modules.utils.line_bot import reply_message_with_quick_reply
                reply_message_with_quick_reply(
                    reply_token,
                    f"🚫 註銷模式\n\n"
                    f"📍 以下班次可設定為註銷：\n{trip_list}\n\n"
                    f"❓ 請選擇：\n• 全部註銷：批量操作\n• 單個詳情：查看後在詳情頁操作",
                    quick_reply
                )
                return True
        
        reply_text(reply_token, "❌ 沒有待操作的班次\n\n請先查詢班次再操作")
        return True
    
    # 🔥 第二層：處理「選擇衝突」- 顯示全部/單個選項
    # 單個班次：直接跳轉班次詳情，利用已有的操作按鈕
    if msg == "選擇衝突":
        logger.info(f"🔍 處理「選擇衝突」命令，用戶: {user_id}")
        pending = conversation_manager.get_pending_operation(user_id)
        logger.info(f"🔍 pending_operation: {pending}")
        if pending:
            trips_info = pending.get("trips", [])
            trip_ids = [t.get("id") for t in trips_info if t.get("id")]
            
            if trip_ids:
                # 🔥 2025-12 優化：只有一個班次時，直接跳轉班次詳情
                if len(trip_ids) == 1:
                    single_tid = trip_ids[0]
                    logger.info(f"🎯 只有一個班次 #{single_tid}，直接跳轉班次詳情")
                    from modules.handlers.view_router import handle_view_commands
                    return handle_view_commands(f"班次詳情 {single_tid}", user_id, reply_token)
                
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                items = [QuickReplyItem(action=MessageAction(label="⚠️ 全部衝突", text="全部衝突"))]
                # 🔥 單個班次：跳轉班次詳情，利用已有的操作按鈕
                for t in trips_info[:3]:
                    tid = t.get("id")
                    items.append(QuickReplyItem(action=MessageAction(label=f"📋 #{tid}詳情", text=f"班次詳情 {tid}")))
                items.append(QuickReplyItem(action=MessageAction(label="❌ 放棄", text="放棄操作")))
                
                quick_reply = QuickReply(items=items[:13])
                trip_list = "\n".join([f"• #{t.get('id')} {t.get('route', '')}" for t in trips_info[:5]])
                
                from modules.utils.line_bot import reply_message_with_quick_reply
                reply_message_with_quick_reply(
                    reply_token,
                    f"⚠️ 衝突模式\n\n"
                    f"📍 以下班次可設定為衝突：\n{trip_list}\n\n"
                    f"❓ 請選擇：\n• 全部衝突：批量操作\n• 單個詳情：查看後在詳情頁操作",
                    quick_reply
                )
                return True
        
        reply_text(reply_token, "❌ 沒有待操作的班次\n\n請先查詢班次再操作")
        return True
    
    # 🔥 第三層：處理「全部請假」命令 - 確認進入批量請假模式
    if msg == "全部請假":
        # 🔥 修復：優先檢查 leave_mode（因為 intent_executor 已經設置了）
        leave_mode = conversation_manager.leave_modes.get(user_id, {})
        trip_ids = leave_mode.get('trip_ids')
        
        if trip_ids and len(trip_ids) > 0:
            # 已經在批量請假模式，提示用戶輸入原因+加成
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="❌ 放棄操作", text="放棄操作"))
            ])
            
            from modules.utils.line_bot import reply_message_with_quick_reply
            reply_message_with_quick_reply(
                reply_token,
                f"📋 批量請假模式（{len(trip_ids)}班）\n\n"
                f"🚕 班次：{', '.join([f'#{tid}' for tid in trip_ids])}\n\n"
                f"請輸入：[請假原因] [加成金額]\n"
                f"例如：出國 -50",
                quick_reply
            )
            return True
        
        # 備用：檢查 pending_operation
        pending = conversation_manager.get_pending_operation(user_id)
        if pending:
            trips_info = pending.get("trips", [])
            pending_trip_ids = pending.get("trip_ids") or pending.get("ready_trip_ids") or [t.get("id") for t in trips_info if t.get("id")]
            
            if pending_trip_ids:
                # 進入批量請假模式
                conversation_manager.set_leave_mode(user_id=user_id, trip_ids=pending_trip_ids)
                conversation_manager.clear_pending_operation(user_id)
                
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                quick_reply = QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label="❌ 放棄操作", text="放棄操作"))
                ])
                
                from modules.utils.line_bot import reply_message_with_quick_reply
                reply_message_with_quick_reply(
                    reply_token,
                    f"📋 批量請假模式（{len(pending_trip_ids)}班）\n\n"
                    f"🚕 班次：{', '.join([f'#{tid}' for tid in pending_trip_ids])}\n\n"
                    f"請輸入：[請假原因] [加成金額]\n"
                    f"例如：出國 -50",
                    quick_reply
                )
                return True
        
        reply_text(reply_token, "❌ 沒有待請假的班次\n\n請先查詢班次再操作")
        return True
    
    # 🔥 處理「全部改回準備」命令
    if msg == "全部改回準備":
        pending = conversation_manager.get_pending_operation(user_id)
        if pending:
            trips_info = pending.get("trips", [])
            trip_ids = pending.get("trip_ids") or [t.get("id") for t in trips_info if t.get("id")]
            
            if trip_ids:
                return handle_batch_restore(trip_ids, user_id, reply_token)
        
        reply_text(reply_token, "❌ 沒有待改回的班次\n\n請先查詢班次再操作")
        return True
    
    # 🔥 處理「全部註銷」命令
    if msg == "全部註銷":
        pending = conversation_manager.get_pending_operation(user_id)
        if pending:
            trips_info = pending.get("trips", [])
            trip_ids = pending.get("trip_ids") or [t.get("id") for t in trips_info if t.get("id")]
            
            if trip_ids:
                return handle_batch_status_change(trip_ids, "註銷", user_id, reply_token)
        
        reply_text(reply_token, "❌ 沒有待註銷的班次\n\n請先查詢班次再操作")
        return True
    
    # 🔥 處理「全部衝突」命令
    if msg == "全部衝突":
        pending = conversation_manager.get_pending_operation(user_id)
        if pending:
            trips_info = pending.get("trips", [])
            trip_ids = pending.get("trip_ids") or [t.get("id") for t in trips_info if t.get("id")]
            
            if trip_ids:
                return handle_batch_status_change(trip_ids, "衝突", user_id, reply_token)
        
        reply_text(reply_token, "❌ 沒有待設定衝突的班次\n\n請先查詢班次再操作")
        return True
    
    # 🔥 處理「#ID請假」或「ID請假」格式 - 單個班次進入請假模式
    # 注意：message_handler 會把 # 當作前綴移除，所以也要匹配不帶 # 的格式
    single_leave_match = re.match(r'^#?(\d+)請假$', msg)
    logger.info(f"🔍 檢查單個請假格式: msg='{msg}', match={single_leave_match}")
    if single_leave_match:
        trip_id = int(single_leave_match.group(1))
        logger.info(f"✅ 匹配單個班次請假: trip_id={trip_id}")
        # 進入單個班次請假模式
        conversation_manager.set_leave_mode(user_id=user_id, trip_id=trip_id)
        conversation_manager.clear_pending_operation(user_id)
        # 🔥 清除之前的批量請假模式（如果有）
        conversation_manager.clear_leave_mode(user_id)
        conversation_manager.set_leave_mode(user_id=user_id, trip_id=trip_id)
        
        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="📋 查看詳情", text=f"班次詳情 {trip_id}")),
            QuickReplyItem(action=MessageAction(label="❌ 放棄操作", text="放棄操作"))
        ])
        
        from modules.utils.line_bot import reply_message_with_quick_reply
        reply_message_with_quick_reply(
            reply_token,
            f"🏥 班次 #{trip_id} 請假模式\n\n"
            f"請輸入：[請假原因] [加成金額]\n"
            f"例如：出國 -50\n\n"
            f"💡 輸入「放棄操作」取消",
            quick_reply
        )
        return True
    
    # 🔥 處理「#ID改回」或「ID改回」格式 - 單個班次改回準備
    # 注意：message_handler 會把 # 當作前綴移除，所以也要匹配不帶 # 的格式
    single_restore_match = re.match(r'^#?(\d+)改回$', msg)
    if single_restore_match:
        trip_id = int(single_restore_match.group(1))
        return handle_batch_restore([trip_id], user_id, reply_token)
    
    # 檢查簡單請假格式（原因 加成）
    if conversation_manager.is_in_leave_mode(user_id):
        return check_and_handle_simple_leave_format(message_text, user_id, reply_token)
    
    return False


def handle_batch_restore(trip_ids: list, user_id: str, reply_token: str) -> bool:
    """批量改回準備狀態"""
    from sqlalchemy.sql import text
    from modules.models.base import db
    
    try:
        success_count = 0
        restored_trips = []
        
        for tid in trip_ids:
            update_query = text("""
                UPDATE trips
                SET passenger_leave_reason = NULL,
                    extra_fare = 0,
                    modification_reason = NULL,
                    status = '準備'
                WHERE trip_id = :trip_id AND status IN ('準備', '待派', '註銷', '衝突')
                RETURNING trip_id, start_point, end_point
            """)
            result = db.session.execute(update_query, {"trip_id": tid})
            updated_row = result.fetchone()
            if updated_row:
                success_count += 1
                restored_trips.append(f"#{tid}")
        
        db.session.commit()
        conversation_manager.clear_pending_operation(user_id)
        
        if success_count > 0:
            message = f"✅ 批量改回準備完成！\n\n🚕 班次：{', '.join(restored_trips)}\n📊 狀態：準備"
            reply_text(reply_token, message)
        else:
            reply_text(reply_token, "❌ 沒有找到可以改回的班次")
        
        return True
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"批量改回準備失敗: {e}", exc_info=True)
        reply_text(reply_token, f"❌ 操作失敗: {str(e)}")
        return True


def handle_batch_status_change(trip_ids: list, new_status: str, user_id: str, reply_token: str) -> bool:
    """批量修改狀態（註銷/衝突）"""
    from modules.handlers.trip_status_handler import handle_update_trip_status
    
    try:
        success_count = 0
        updated_trips = []
        errors = []
        
        for tid in trip_ids:
            command = f"修改狀態 {tid} {new_status}"
            result = handle_update_trip_status(command, user_id)
            
            if "✅" in result or "成功" in result:
                success_count += 1
                updated_trips.append(f"#{tid}")
            else:
                errors.append(f"#{tid}: {result}")
        
        conversation_manager.clear_pending_operation(user_id)
        
        if success_count > 0:
            status_emoji = "🚫" if new_status == "註銷" else "⚠️"
            message = f"✅ 批量{new_status}完成！\n\n🚕 班次：{', '.join(updated_trips)}\n{status_emoji} 狀態：{new_status}"
            
            if errors:
                message += f"\n\n⚠️ 部分失敗：\n" + "\n".join(errors[:3])
            
            reply_text(reply_token, message)
        else:
            reply_text(reply_token, f"❌ 批量{new_status}失敗\n\n" + "\n".join(errors[:5]))
        
        return True
    
    except Exception as e:
        logger.error(f"批量{new_status}失敗: {e}", exc_info=True)
        reply_text(reply_token, f"❌ 操作失敗: {str(e)}")
        return True


def check_and_handle_simple_leave_format(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    檢查並處理簡單請假格式：[原因] [數字]
    支持單一班次和批量班次
    返回 True 表示已處理，False 表示格式不符
    """
    # 嚴格的請假格式檢查：必須是 [原因] [數字] 格式
    parts = message_text.split()
    is_valid_format = False
    
    # 必須恰好2個部分：原因 + 數字
    if len(parts) == 2:
        try:
            # 第二部分必須是數字（加成）
            int(parts[1])
            is_valid_format = True
        except ValueError:
            pass
    
    if not is_valid_format:
        # 🔥 修復：格式不符時，只清除請假模式，但返回 False
        # 這樣消息可以繼續被智能助手處理（例如新的請假命令）
        logger.info(f"⚠️ 用戶 {user_id} 輸入格式不符請假格式，清除請假模式讓消息繼續處理: {message_text}")
        conversation_manager.clear_leave_mode(user_id)
        # 🔥 返回 False，讓消息繼續流向智能助手處理
        return False
    
    # 格式正確，執行請假
    reason = parts[0]
    extra_fare = int(parts[1])
    
    # 🔥 獲取請假模式上下文（支持批量）
    leave_mode = conversation_manager.leave_modes.get(user_id, {})
    trip_ids = leave_mode.get('trip_ids')  # 批量
    recent_trip_id = leave_mode.get('trip_id') or conversation_manager.get_recent_trip_id(user_id)
    recent_fixed_schedule_id = leave_mode.get('fixed_schedule_id') or conversation_manager.get_recent_fixed_schedule_id(user_id)
    
    if not recent_trip_id and not recent_fixed_schedule_id and not trip_ids:
        conversation_manager.clear_leave_mode(user_id)
        reply_text(reply_token, "❌ 請假模式上下文遺失，請重新操作")
        return True
    
    # 執行請假
    try:
        # 🔥 批量請假
        if trip_ids and len(trip_ids) > 1:
            from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
            results = []
            success_count = 0
            for tid in trip_ids:
                full_command = f"乘客請假 {tid} {extra_fare} {reason}"
                result = handle_passenger_leave_command(full_command, user_id)
                if "✅" in result:
                    success_count += 1
                results.append(f"#{tid}")
            
            # 清除請假模式
            conversation_manager.clear_leave_mode(user_id)
            
            summary = f"✅ 批量請假完成！\n\n"
            summary += f"🏥 班次：{', '.join(results)}\n"
            summary += f"📝 原因：{reason}\n"
            summary += f"💰 加成：{extra_fare} 元\n"
            summary += f"📊 成功：{success_count}/{len(trip_ids)} 個"
            
            reply_text(reply_token, summary)
            return True
        
        # 單一班次請假
        if recent_fixed_schedule_id:
            # 固定班次請假
            from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave_command
            full_command = f"固定班次請假 {recent_fixed_schedule_id} {extra_fare} {reason}"
            result = handle_fixed_schedule_leave_command(full_command, user_id)
        elif recent_trip_id:
            # 一般班次請假
            from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
            full_command = f"乘客請假 {recent_trip_id} {extra_fare} {reason}"
            result = handle_passenger_leave_command(full_command, user_id)
        
        # 清除請假模式
        conversation_manager.clear_leave_mode(user_id)
        
        reply_text(reply_token, result)
        return True
        
    except Exception as e:
        logger.error(f"執行請假時出錯: {e}")
        conversation_manager.clear_leave_mode(user_id)
        reply_text(reply_token, f"❌ 執行請假失敗：{str(e)}")
        return True


def handle_passenger_leave_conversation(conversation, message_text: str, user_id: str, reply_token: str):
    """
    處理乘客請假對話流程
    這個函數由 text_message_handler.py 在檢測到活躍的 passenger_leave 對話時調用
    """
    logger.info(f"🎯 處理乘客請假對話: 步驟={conversation.current_step}")
    
    # 嚴格的請假格式檢查：必須是 [原因] [數字] 格式
    parts = message_text.split()
    is_valid_format = False
    
    # 必須恰好2個部分：原因 + 數字
    if len(parts) == 2:
        try:
            # 第二部分必須是數字（加成）
            int(parts[1])
            is_valid_format = True
        except ValueError:
            pass
    
    if not is_valid_format:
        # 🔥 修復：格式不符時，結束對話但不回覆錯誤
        # 這樣消息可以繼續被其他處理器處理
        logger.info(f"⚠️ 請假格式不符，結束對話讓消息繼續處理: {message_text}")
        conversation_manager.end_conversation(user_id, "格式不符")
        # 🔥 注意：這裡是 return（無返回值），表示未處理，讓消息繼續流向下一個處理器
        return
    
    # 格式正確，執行請假
    reason = parts[0]
    extra_fare = int(parts[1])
    
    # 獲取對話上下文
    context_data = conversation.context_data or {}
    trip_id = context_data.get('trip_id')
    
    if not trip_id:
        conversation_manager.end_conversation(user_id, "上下文遺失")
        reply_text(reply_token, "❌ 對話上下文遺失，請重新操作")
        return
    
    # 執行請假
    try:
        from modules.handlers.passenger_leave_handler import handle_passenger_leave_command
        result = handle_passenger_leave_command(f"乘客請假 {trip_id} {extra_fare} {reason}", user_id)
        
        # 結束對話
        conversation_manager.end_conversation(user_id, "請假完成")
        
        reply_text(reply_token, result)
        
    except Exception as e:
        logger.error(f"執行請假時出錯: {e}")
        conversation_manager.end_conversation(user_id, "執行失敗")
        reply_text(reply_token, f"❌ 執行請假失敗：{str(e)}")


def set_leave_mode_with_context(user_id: str, fixed_schedule_id: int = None, trip_id: int = None):
    """
    設置請假模式並保存上下文
    """
    context = {}
    
    if fixed_schedule_id:
        context['is_fixed_schedule'] = True
        context['fixed_schedule_id'] = fixed_schedule_id
        conversation_manager.set_leave_mode(user_id=user_id, fixed_schedule_id=fixed_schedule_id)
        logger.info(f"✅ 設置用戶 {user_id} 進入固定班次請假模式，固定班次 #{fixed_schedule_id}")
    elif trip_id:
        context['is_fixed_schedule'] = False
        context['trip_id'] = trip_id
        conversation_manager.set_leave_mode(user_id=user_id, trip_id=trip_id)
        logger.info(f"✅ 設置用戶 {user_id} 進入一般班次請假模式，班次 #{trip_id}")
    
    return context
