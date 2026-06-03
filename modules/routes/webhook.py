# modules/routes/webhook.py
from flask import Blueprint, request, abort, current_app
from linebot.v3.exceptions import InvalidSignatureError
import traceback
import logging

from modules.utils.line_bot import get_parser, reply_text

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
            # 處理 Postback 事件（按鈕點擊）— 全交給 rewrite/router
            if event.type == "postback":
                try:
                    from rewrite.router import try_route_postback as _rew_try_pb
                    if _rew_try_pb(event):
                        logger.info(
                            f"Postback routed to rewrite: "
                            f"{getattr(event.source, 'user_id', '?')}"
                        )
                    else:
                        logger.info(
                            f"Postback not handled by rewrite: "
                            f"{getattr(event.postback, 'data', '?')!r}"
                        )
                except Exception as _rew_pb_err:
                    logger.error(
                        f"Postback dispatch failed: {_rew_pb_err}",
                        exc_info=True,
                    )
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

                # --- PATCH: 藥名查詢 (drug / 藥 / 藥名 前綴) ---
                try:
                    from modules.handlers.drug_handler import is_drug_trigger, handle_drug_message
                    if is_drug_trigger(original_message_text):
                        logger.info(f"Routing to Drug Query: {user_id}")
                        handle_drug_message(event)
                        continue
                except Exception as e:
                    logger.error(f"Drug dispatch failed: {e}", exc_info=True)
                # --- END PATCH: 藥名查詢 ---

                # --- PATCH: 診所座標 / 車速 設定指令（文字）---
                # 在群組閘門前攔（這些是明確設定指令,群組裡常無 / 前綴）
                if getattr(event.message, 'type', None) == "text":
                    try:
                        from modules.handlers.clinic_commands_handler import (
                            handle_clinic_commands, is_waiting_for_location,
                        )
                        from modules.handlers.location_message_handler import _get_chat_id
                        _clinic_chat = _get_chat_id(event)
                        _clinic_msg = (event.message.text or '').strip().lstrip('/').strip()
                        _clinic_head = _clinic_msg.split(' ')[0]
                        # 命中條件:① 明確診所/車速指令 ② 正在「等待設定診所」中(讓打字座標也能接)
                        if (_clinic_head in ('設定診所', '查看診所座標', '清除診所座標',
                                             '設定平均車速', '查看平均車速')
                                or is_waiting_for_location(_clinic_chat)):
                            _resp = handle_clinic_commands(_clinic_msg, _clinic_chat)
                            if _resp:
                                reply_text(event.reply_token, _resp)
                                continue
                            # _resp is None（等待中但非合法座標）→ 不 continue,讓它走原本流程
                    except Exception as e:
                        logger.error(f"診所指令處理失敗: {e}", exc_info=True)
                # --- END PATCH: 診所指令 ---

                # ============================================================
                # Phase B（拆沙盒）：新路由規則
                # ============================================================
                # 私聊（user）→ 不需前綴，所有訊息都認
                # 群組（group/room）→ 必須 / 開頭，或在 rewrite-active state 中
                #   （多輪對話 follow-up / Quick Reply 按鈕回傳值通常無 / 前綴）
                # 處理順序：
                #   1. rewrite/router.try_route — 快速命令（查客戶 / 班次詳情 / etc）
                #   2. rewrite/sandbox_handler.try_handle_sandbox — LIFF / 狀態 picker / AI
                #   3. (過渡) legacy text_message_handler — Phase C 後刪除
                # ============================================================
                is_bot_addressed = False
                if source_type == 'user':
                    # 私聊全收
                    is_bot_addressed = True
                elif source_type in ('group', 'room'):
                    if original_message_text.lstrip().startswith('/'):
                        is_bot_addressed = True
                    else:
                        # 群組無 / 開頭 — 兩個例外都讓過：
                        #   (a) Flex/quickReply 按鈕 callback（如「固定班次恢復 29」、
                        #       「acct_ledger_start」、「查看 1234」）→ looks_like_quick_command
                        #   (b) 用戶剛回應 bot（rewrite-active state，多輪對話 follow-up）
                        try:
                            from rewrite.conversation_state import (
                                get_state as _rew_state_get,
                                get_chat_id_from_event as _rew_get_chat,
                            )
                            from rewrite.handlers.sandbox_handler import (
                                SANDBOX_ACTIVE_STATE_TYPE,
                                TRIP_STATUS_PICKER_STATE_TYPE,
                                TRIP_STATUS_LEAVE_INPUT_STATE_TYPE,
                                ACCT_LEDGER_RANGE_INPUT_STATE_TYPE,
                                looks_like_quick_command,
                            )
                            # (a) 看起來像按鈕 callback / 已知快速命令 → 讓過
                            if looks_like_quick_command(original_message_text):
                                is_bot_addressed = True
                            else:
                                # (b) 多輪對話狀態中 → 讓過（follow-up 通常無 / 前綴）
                                #     但只在「同對話」才算 — 防止私聊 state 跨到群組
                                #     讓所有閒聊被當 bot 訊息
                                _rew_st = _rew_state_get(user_id) if user_id else None
                                _active_types = (
                                    SANDBOX_ACTIVE_STATE_TYPE,
                                    TRIP_STATUS_PICKER_STATE_TYPE,
                                    TRIP_STATUS_LEAVE_INPUT_STATE_TYPE,
                                    ACCT_LEDGER_RANGE_INPUT_STATE_TYPE,
                                )
                                if _rew_st and _rew_st.get('type') in _active_types:
                                    state_chat = _rew_st.get('chat_id')
                                    current_chat = _rew_get_chat(event)
                                    if state_chat and state_chat == current_chat:
                                        is_bot_addressed = True
                                    # state 沒記 chat（舊 state）或不同對話 → 不 bypass
                        except Exception:
                            pass

                if not is_bot_addressed:
                    logger.info(f"Skip {source_type} non-/ message: {original_message_text!r}")
                    continue

                # 1. rewrite/router 快速命令（exact match，cheap dispatch，沒 AI 成本）
                try:
                    from rewrite.router import try_route as _rewrite_try_route
                    if _rewrite_try_route(event):
                        logger.info(f"Routing to rewrite/router: {user_id}")
                        continue
                except Exception as _rew_err:
                    logger.error(f"rewrite/router dispatch failed: {_rew_err}", exc_info=True)

                # 2. rewrite/sandbox_handler（LIFF / 狀態 picker / AI agent / DB 同步橋接）
                # rewrite 是唯一處理路徑：不認得就回友善訊息，不再 fall-through legacy
                try:
                    from rewrite.handlers.sandbox_handler import try_handle_sandbox
                    if try_handle_sandbox(event):
                        logger.info(f"Routing to rewrite/sandbox_handler: {user_id}")
                    else:
                        # rewrite 不認得 — sandbox 已 reply 友善訊息（unknown handler）
                        logger.info(f"Rewrite did not handle: {original_message_text!r}")
                except Exception as _rew_err:
                    logger.error(f"sandbox_handler dispatch failed: {_rew_err}", exc_info=True)
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
