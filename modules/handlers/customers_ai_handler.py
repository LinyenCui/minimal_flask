import logging
from flask import g
from modules.utils.line_bot import reply_text
from modules.services.customers_ai_service import process_sandbox_message, execute_proposal
import json

logger = logging.getLogger(__name__)

# Simple in-memory state storage: {user_id: {"status": "PENDING_CONFIRM", "proposal": {...}}}
# Note: In a production multi-worker env, this should be in Redis/DB. 
# For this "Sandbox" feature on a minimal flask app, in-memory global dict 
# is risky if workers restart, but acceptable for a "Sandbox" / MVP.
# However, `modules/utils/conversation_context.py` exists. I should probably use that or similar.
# But "conversation_states" there seems to be for the main flow.
# I will use a separate local dictionary for isolation.
SANDBOX_STATES = {}

def handle_customers_ai_message(event):
    """
    Entry point for Customers AI Sandbox messages.
    """
    user_id = event.source.user_id
    text = event.message.text.strip()
    reply_token = event.reply_token
    
    logger.info(f"Customers AI Sandbox: User {user_id} says '{text}'")
    
    # 1. Check for Pending Confirmation
    if user_id in SANDBOX_STATES:
        state = SANDBOX_STATES[user_id]
        if state.get("status") == "PENDING_CONFIRM":
            # Normalize text for checking: remove / if present
            # Because confirmation might come from group with / prefix
            check_text = text.lower()
            if check_text.startswith('/'):
                check_text = check_text[1:]
                
            if check_text in ['確認', 'ok', 'yes', 'confirm']:
                # Execute
                proposal = state['proposal']
                
                try:
                    # Note: Operations might take time, risking reply token expiry (30s max, usually <10s safe)
                    result_json = execute_proposal(proposal['func_name'], proposal['func_args'])
                    result = json.loads(result_json)
                    
                    if result.get('status') == 'success':
                        msg = f"✅ 執行成功\n{result.get('message')}"
                    else:
                        msg = f"❌ 執行失敗\n{result.get('message')}"
                        
                    reply_text(reply_token, msg)
                except Exception as e:
                    logger.error(f"Sandbox execution error: {e}", exc_info=True)
                    try:
                        reply_text(reply_token, f"💥 系統錯誤: {e}")
                    except:
                        pass
                
                # Clear state finally
                if user_id in SANDBOX_STATES:
                    del SANDBOX_STATES[user_id]
                return
                
            elif check_text in ['取消', 'no', 'cancel']:
                reply_text(reply_token, "已取消操作。")
                if user_id in SANDBOX_STATES:
                    del SANDBOX_STATES[user_id]
                return
            else:
                # User said something else. 
                # Strict flow: "Please answer confirm or cancel."
                # OR Natural flow: Treat as new command?
                # "Trigger rules" say: if 'cu' start.
                # If checking state, we assume we are IN the sandbox context.
                # The user MIGHT have sent a new command "cu check..."
                # If so, we should probably discard the old proposal.
                pass 
                # Let's proceed to process as new message, clearing old state?
                # Or block?
                # Requirement: "Natural language database operations".
                # I'll clear state and process as new if it matches triggers, OR just warn.
                # Simplest: "Pending confirmation. Reply 確認 to proceed or 取消 to cancel."
                reply_text(reply_token, f"⚠️ 您有一個待確認的變更。\n\n{state['proposal']['summary_text']}\n\n請回覆「確認」或「取消」。")
                return

    # 2. Process New Request
    # Remove trigger prefix for cleaner AI processing? 
    # "cu 查..." -> "查..."
    clean_text = text
    if clean_text.lower().startswith("cu"):
        clean_text = clean_text[2:].strip()
    elif clean_text.startswith("客"):
        clean_text = clean_text[1:].strip()
    elif clean_text.lower().startswith("/cu"):
        clean_text = clean_text[3:].strip()
    elif clean_text.startswith("/客"):
        clean_text = clean_text[2:].strip()
        
    if not clean_text:
        reply_text(reply_token, "Customers AI Sandbox 已啟動。\n請輸入指令，例如：\n- 查 文賢路\n- 新增 客戶 王小明...")
        return

    try:
        # Call Service
        # We reply "Computing..."? No, LINE has timeouts but better to just wait 
        # unless we use push message (which costs money/quota).
        # We try to reply within seconds.
        
        result = process_sandbox_message(user_id, clean_text)
        
        if result['type'] == 'text_response' or result['type'] == 'rest_response':
            reply_text(reply_token, result['content'])
            
        elif result['type'] == 'proposal':
            # Store state
            proposal = result['content']
            SANDBOX_STATES[user_id] = {
                "status": "PENDING_CONFIRM",
                "proposal": proposal
            }
            
            msg = f"⚠️ 【變更確認】\nAI 準備執行以下操作，請確認：\n\n{proposal['summary_text']}\n\n回覆「確認」執行，或「取消」中止。"
            reply_text(reply_token, msg)
            
    except Exception as e:
        logger.error(f"Sandbox Error: {e}", exc_info=True)
        reply_text(reply_token, "機械人當機了 😵‍💫 (請檢查 Log)")

