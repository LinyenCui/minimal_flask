import logging
import json
from flask import g
from modules.utils.line_bot import reply_text
from modules.services.customers_ai_service import process_sandbox_message, execute_proposal
from modules.utils.conversation_context import conversation_manager
from modules.models.base import db
from sqlalchemy import text as sql_text

logger = logging.getLogger(__name__)

# Note: We replace SANDBOX_STATES with conversation_manager for flow state,
# BUT for the final "Pending Confirm" of a proposal, we can either:
# 1. Use conversation_manager too (unified)
# 2. Keep local SANDBOX_STATES for the final "Yes/No" step (simpler for now if we just want "Drafting" memory)
# To fully "Unify", we should probably use conversation_manager for everything.
# However, "Pending Confirm" logic is simple. "Drafting" is complex.
# Let's keep SANDBOX_STATES for the final execution confirmation to avoid over-engineering the migration right now,
# but use conversation_manager for the "Missing Info" multi-turn flow.
SANDBOX_STATES = {}

def handle_customers_ai_message(event):
    """
    Entry point for Customers AI Sandbox messages.
    """
    user_id = event.source.user_id
    text = event.message.text.strip()
    reply_token = event.reply_token
    
    # 0. Prepare Context (Recent Trips) for AI "Entity Linking"
    # This enables "Change that one"
    additional_context = ""
    try:
        # Fetch last 5 trips
        sql = "SELECT trip_id, date, time, start_point, end_point, category FROM trips ORDER BY trip_id DESC LIMIT 5"
        trips = db.session.execute(sql_text(sql)).fetchall()
        if trips:
            trip_lines = []
            for t in trips:
                 t_id = t[0]
                 t_date = t[1]
                 t_time = t[2].strftime("%H:%M") if t[2] else "??"
                 t_start = t[3]
                 t_end = t[4]
                 trip_lines.append(f" - Trip #{t_id}: {t_date} {t_time} from {t_start} to {t_end or 'N/A'}")
            additional_context = "Recent Trips (Visible to user):\n" + "\n".join(trip_lines)
    except Exception as e:
        logger.warning(f"Failed to fetch context: {e}")

    logger.info(f"Customers AI Sandbox: User {user_id} says '{text}'")
    
    # 1. Check for Pending Confirmation (Final Step)
    logger.info(f"🔍 檢查 SANDBOX_STATES: user_id={user_id}, in_states={user_id in SANDBOX_STATES}")
    if user_id in SANDBOX_STATES:
        state = SANDBOX_STATES[user_id]
        logger.info(f"🔍 用戶狀態: {state.get('status')}, proposal={state.get('proposal', {}).get('func_name')}")
        if state.get("status") == "PENDING_CONFIRM":
            # Normalize text for checking
            check_text = text.lower()
            if check_text.startswith('/'):
                check_text = check_text[1:]
            
            logger.info(f"🔍 檢查確認文字: check_text='{check_text}', is_confirm={check_text in ['確認', 'ok', 'yes', 'confirm']}")
            if check_text in ['確認', 'ok', 'yes', 'confirm']:
                # Execute
                proposal = state['proposal']
                try:
                    result_json = execute_proposal(proposal['func_name'], proposal['func_args'])
                    result = json.loads(result_json)
                    if result.get('status') == 'success':
                        msg = f"✅ 執行成功\n{result.get('message')}"
                    else:
                        msg = f"❌ 執行失敗\n{result.get('message')}"
                    reply_text(reply_token, msg)
                except Exception as e:
                    logger.error(f"Sandbox execution error: {e}", exc_info=True)
                    reply_text(reply_token, f"💥 系統錯誤: {e}")
                
                # Clear state
                if user_id in SANDBOX_STATES:
                    del SANDBOX_STATES[user_id]
                return
                
            elif check_text in ['取消', 'no', 'cancel']:
                reply_text(reply_token, "已取消操作。")
                if user_id in SANDBOX_STATES:
                    del SANDBOX_STATES[user_id]
                return
            else:
                reply_text(reply_token, f"⚠️ 您有一個待確認的變更。\n\n{state['proposal']['summary_text']}\n\n請回覆「確認」或「取消」。")
                return

    # 2. Check for Active Conversation (Missing Info / Drafting Step)
    # This handles the multi-turn memory
    active_conv = conversation_manager.get_active_conversation(user_id)
    input_text = text
    
    if active_conv and active_conv.conversation_type == 'customer_sandbox':
        # Check cancellation
        if active_conv.can_cancel_with(input_text):
            conversation_manager.end_conversation(user_id, "User cancelled")
            reply_text(reply_token, "已取消操作。")
            return

        # It's a follow-up answer!
        # Context: We have some draft data. User just provided more info.
        # We construct a combined query for the AI.
        draft = active_conv.context_data.get('draft_data', {})
        
        # Heuristic: "Currently creating customer. Known info: {draft}. Update/Amendment: {text}"
        # We rely on Gemini to understand this context injection.
        
        # Prepare the effective query
        # We can simulate the user re-typing everything by combining them, 
        # OR we can explicitly tell the AI "Here is the context".
        # Let's try Context Injection via the prompt text logic in customers_ai_service?
        # No, 'process_sandbox_message' takes just text.
        # So we synthesize the text.
        
        # Turn "Clinic" into "Add customer [Previously known info] + Category: Clinic"
        # Since we don't know exactly how to map 'Clinic' to 'Category' without AI, 
        # we just feed the whole thing.
        
        context_str = ", ".join([f"{k}:{v}" for k,v in draft.items() if v])
        combined_text = f"延續上一次的新增客戶請求。已知資料：{{{context_str}}}。使用者補充：{input_text}。請嘗試完成新增，若仍有缺漏則繼續追問。"
        
        logger.info(f"Sandbox Contextual Query: {combined_text}")
        input_text = combined_text
        # Note: We do NOT end the conversation yet; the RESULT of process() will determine if we finish or continue.
        # However, logic below calls process_sandbox_message which is stateless.
        # If it returns 'proposal', we are done (move to PENDING_CONFIRM).
        # If it returns 'missing_info' again, we UPDATE the conversation.


    # 3. Process Request (New or Contextual)
    clean_text = input_text
    # Remove triggers if present (only for fresh start, but safe to do always)
    # 新前綴：! 或 ！ (支援半角和全角驚嘆號)
    if clean_text.startswith('/!') or clean_text.startswith('/！'):
        clean_text = clean_text[2:].strip()
    elif clean_text.startswith('!') or clean_text.startswith('！'):
        clean_text = clean_text[1:].strip()
    # 兼容舊前綴（過渡期）
    elif clean_text.lower().startswith("/cu"):
        clean_text = clean_text[3:].strip()
    elif clean_text.startswith("/客"):
        clean_text = clean_text[2:].strip()
    elif clean_text.lower().startswith("cu"):
        clean_text = clean_text[2:].strip()
    elif clean_text.startswith("客"):
        clean_text = clean_text[1:].strip()
        
    if not clean_text:
        reply_text(reply_token, "🤖 AI 助手已啟動\n\n可用指令：\n• 查 [客戶/地點]\n• 固定班表 [客戶]\n• 將固定班次#ID的時間改成...\n• 預約 明天下午2點從高鐵站到東洋\n\n群組用 ! 開頭，私聊也需要 !")
        return

    try:
        result = process_sandbox_message(user_id, clean_text, additional_context=additional_context)
        logger.info(f"Sandbox Result Type: {result.get('type')}")
        
        if result['type'] == 'text_response' or result['type'] == 'rest_response':
            # stateless response
            reply_text(reply_token, result['content'])
            # If we were in a conversation and got a plain response, maybe we should end it?
            # E.g. user asked "Lookup X" while in "Create Y" flow?
            # For robustness, if it wasn't a Missing Info loop finding, let's keep conversation active?
            # No, usually text_response means "Done" or "Answered".
            if active_conv and active_conv.conversation_type == 'customer_sandbox':
                 conversation_manager.end_conversation(user_id, "Completed text response")
            
        elif result['type'] == 'proposal':
            # Success! Data complete.
            # 1. End the "Drafting" conversation
            if active_conv and active_conv.conversation_type == 'customer_sandbox':
                 conversation_manager.end_conversation(user_id, "Drafting complete")
            
            # 2. Start "Pending Confirm" State
            proposal = result['content']
            SANDBOX_STATES[user_id] = {
                "status": "PENDING_CONFIRM",
                "proposal": proposal
            }
            msg = f"⚠️ 【變更確認】\nAI 準備執行以下操作，請確認：\n\n{proposal['summary_text']}\n\n回覆「確認」執行，或「取消」中止。"
            reply_text(reply_token, msg)

        elif result['type'] == 'missing_info':
            # Still missing info!
            # Start or Update conversation
            missing = result['missing_fields']
            draft = result['draft_data']
            
            prompt_msg = result['content']
            
            # Start/Update Conversation
            conversation_manager.start_conversation(
                user_id=user_id,
                conversation_type='customer_sandbox',
                current_step='filling_missing_info',
                context_data={'draft_data': draft},
                prompt_message=prompt_msg
            )
            
            reply_text(reply_token, prompt_msg)
            
    except Exception as e:
        logger.error(f"Sandbox Error: {e}", exc_info=True)
        reply_text(reply_token, "機械人當機了 😵‍💫 (請檢查 Log)")
