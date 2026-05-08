# modules/routes/webhook.py
from flask import Blueprint, request, abort, current_app
from linebot.v3.exceptions import InvalidSignatureError
import traceback
import logging

from modules.utils.line_bot import get_parser, reply_text
from modules.services.postback_service import handle_postback
from modules.handlers.message_handler import should_process

# 創建藍圖
webhook_bp = Blueprint('webhook', __name__)

# 設定日誌
logger = logging.getLogger(__name__)

@webhook_bp.route("/callback", methods=['POST'])
def callback():
    """LINE Webhook 回調處理"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)
    
    try:
        parser = get_parser()
        events = parser.parse(body, signature)
        
        for event in events:
            # 處理 Postback 事件（按鈕點擊）
            if event.type == "postback":
                # --- Rewrite v0.1 postback 早期攔截 ---
                # 命令：trip_detail:NNNN（班次列表卡點擊跳詳情）
                try:
                    from rewrite.router import try_route_postback as _rew_try_pb
                    if _rew_try_pb(event):
                        logger.info(
                            f"Postback routed to Rewrite v0.1: "
                            f"{getattr(event.source, 'user_id', '?')}"
                        )
                        continue
                except Exception as _rew_pb_err:
                    logger.error(
                        f"Rewrite postback dispatch failed: {_rew_pb_err}",
                        exc_info=True,
                    )
                # --- END Rewrite postback ---
                handle_postback(event)
                continue
                
            # 處理文本消息
            if event.type == "message" and event.message.type == "text":
                original_message_text = event.message.text
                source_type = event.source.type
                user_id = event.source.user_id # Restored missing definition
                
                # --- PATCH: 診斷碼查詢 (dx / 碼 前綴) ---
                try:
                    from modules.handlers.diagnosis_handler import is_diagnosis_trigger, handle_diagnosis_message
                    if is_diagnosis_trigger(original_message_text):
                        logger.info(f"Routing to Diagnosis Query: {user_id}")
                        handle_diagnosis_message(event)
                        continue
                except Exception as e:
                    logger.error(f"Diagnosis dispatch failed: {e}", exc_info=True)
                # --- END PATCH: 診斷碼查詢 ---

                # --- PATCH: AI Sandbox Trigger (原 Customers AI Sandbox) ---
                # 觸發方式：
                # - 私聊：需要 ! 前缀
                # - 群組：! 直接觸發（取代 /）
                is_private = source_type == 'user'
                trigger_sandbox = False
                lower_text = original_message_text.lower()
                
                try:
                    from modules.handlers.customers_ai_handler import SANDBOX_STATES, handle_customers_ai_message
                    from modules.utils.conversation_context import conversation_manager
                    
                    # Logic: Determine if we should route to Sandbox
                    
                    # 1. Check strict prefix: ! 或 ！ (支援半角和全角驚嘆號)
                    # 支援: "! xxx", "!xxx", "！xxx", "！ xxx", "/!" (群組兼容)
                    has_sandbox_prefix = (original_message_text.startswith('!') or 
                                          original_message_text.startswith('！') or
                                          original_message_text.startswith('/!') or
                                          original_message_text.startswith('/！'))

                    # 2. Check Active Sandbox Conversation (Multi-turn Memory)
                    is_active_sandbox_conv = False
                    active_conv = conversation_manager.get_active_conversation(user_id)
                    if active_conv and active_conv.conversation_type == 'customer_sandbox':
                         is_active_sandbox_conv = True

                    # 2b. Check rewrite v0.1 sandbox-active state（無前綴多輪續對話）
                    # 但若訊息看起來是「快速命令」（查班次、資料庫同步等）→ 不攔，
                    # 讓用戶在 90 秒對話 window 內仍能做別的事，不會被卡住
                    is_rewrite_sandbox_active = False
                    try:
                        from rewrite.conversation_state import get_state as _rew_state_get
                        from rewrite.handlers.sandbox_handler import (
                            SANDBOX_ACTIVE_STATE_TYPE,
                            TRIP_STATUS_PICKER_STATE_TYPE,
                            TRIP_STATUS_LEAVE_INPUT_STATE_TYPE,
                            looks_like_quick_command,
                        )
                        _rew_st = _rew_state_get(user_id) if user_id else None
                        _rew_active_types = (
                            SANDBOX_ACTIVE_STATE_TYPE,
                            TRIP_STATUS_PICKER_STATE_TYPE,
                            TRIP_STATUS_LEAVE_INPUT_STATE_TYPE,
                        )
                        if _rew_st and _rew_st.get('type') in _rew_active_types:
                            if not looks_like_quick_command(original_message_text):
                                is_rewrite_sandbox_active = True
                    except Exception:
                        pass

                    # --- DECISION TREE ---
                    if has_sandbox_prefix:
                        trigger_sandbox = True
                    # If the user is in the middle of a Sandbox confirmation (Legacy state), intercept.
                    elif user_id in SANDBOX_STATES:
                        trigger_sandbox = True
                    # If user is in a multi-turn flow (e.g. filling missing info), intercept.
                    elif is_active_sandbox_conv:
                        trigger_sandbox = True
                    # rewrite v0.1: 用戶剛跟 rewrite agent 對話完，下一句不需前綴
                    elif is_rewrite_sandbox_active:
                        trigger_sandbox = True
                    
                    # NOTE: We REVERTED the "Smart Router" (Prefix-less for private chat) 
                    # because it conflicted with legacy commands with arguments (e.g. "診所班次 今天").
                    # Safety first -> Require prefix or active context.
                        
                    if trigger_sandbox:
                        # --- Rewrite v0.1 sandbox 早期攔截 ---
                        # 已在 legacy state 的維持 legacy（保多輪流程連續）
                        # 新進 sandbox 的先試 rewrite，unknown / error → fall-through
                        in_legacy_state = (
                            user_id in SANDBOX_STATES or is_active_sandbox_conv
                        )
                        if not in_legacy_state:
                            try:
                                from rewrite.handlers.sandbox_handler import try_handle_sandbox
                                if try_handle_sandbox(event):
                                    logger.info(f"Sandbox routed to Rewrite v0.1: {user_id}")
                                    continue
                            except Exception as _rew_err:
                                logger.error(
                                    f"Rewrite sandbox dispatch failed: {_rew_err}",
                                    exc_info=True,
                                )
                        # --- END Rewrite sandbox ---

                        logger.info(f"Routing to Customers AI Sandbox: {user_id} (Prefix={has_sandbox_prefix}, Active={is_active_sandbox_conv})")
                        handle_customers_ai_message(event)
                        continue
                except Exception as e:
                    logger.error(f"Sandbox dispatch failed: {e}", exc_info=True)
                    # Proceed to normal flow if sandbox fails to load/dispatch?
                    # No, safer to just log.
                # --- END PATCH ---

                # --- PATCH: Rewrite v0.1 路由（早期攔截，繞過 should_process 群組過濾）---
                # 命令：查客戶 / 客戶詳情 / 病歷層 / 查班次 / 班次詳情 / 待派班次 / 診所班次 / 東洋班次
                # router 內部會處理 / # 前綴的剝除（! ！ 留給 sandbox）
                try:
                    from rewrite.router import try_route as _rewrite_try_route
                    if _rewrite_try_route(event):
                        logger.info(f"Routing to Rewrite v0.1: {user_id}")
                        continue
                except Exception as _rew_err:
                    logger.error(f"Rewrite dispatch failed: {_rew_err}", exc_info=True)
                # --- END PATCH ---

                should_handle, processed_text = should_process(original_message_text, source_type, user_id)
                
                if should_handle:
                    # --- 恢復直接修改 event 對象 --- 
                    event.message.text = processed_text 
                    logger.info(f"Passing processed text '{processed_text}' to handler.")
                    # --- 調用原始的處理函數 --- 
                    handle_text_message(event) 
                else:
                    logger.info(f"Skipping message from {source_type} due to handler rules: {original_message_text}")
                    continue 

            # 處理位置消息（LocationMessage）
            if event.type == "message" and getattr(event.message, 'type', None) == "location":
                try:
                    from modules.handlers.location_message_handler import handle_location_message
                    handle_location_message(event)
                except Exception as e:
                    logger.error(f"處理位置消息失敗: {e}")
                    try:
                        reply_text(event.reply_token, "❌ 無法處理位置訊息，請稍後再試")
                    except Exception:
                        pass
                continue
                
    except InvalidSignatureError:
        logger.error("無效的簽名")
        abort(400)
    except Exception as e:
        logger.error(f"處理webhook時出錯: {e}", exc_info=True)
        abort(500)
        
    return 'OK'

# 恢復原始的 handle_text_message 函數 (如果之前被註釋或刪除)
def handle_text_message(event):
    """處理文本消息"""
    from modules.handlers.text_message_handler import process_text_message
    process_text_message(event)
