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
                        # 命中條件:① 明確地點/車速指令 ② 正在「等待設定地點」中(讓打字座標也能接)
                        # 「設定地點」系列 = 「設定診所」的通用同義詞(每群可自訂目的地並命名,不限診所)
                        if (_clinic_head in ('設定診所', '查看診所座標', '清除診所座標',
                                             '設定地點', '查看地點座標', '清除地點座標',
                                             '設定地點名稱', '查看地點名稱',
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

                # --- PATCH: 到院轉發綁定指令（文字）---
                # 在群組閘門前攔（明確設定指令,群組裡常無 / 前綴）
                try:
                    from modules.handlers.arrival_relay_handler import handle_relay_commands
                    from modules.handlers.location_message_handler import _get_chat_id
                    _relay_chat = _get_chat_id(event)
                    _relay_msg = (event.message.text or '').strip().lstrip('/').strip()
                    _relay_head = _relay_msg.split(' ')[0]
                    if (_relay_head in ('設定到院轉發', '查看到院轉發', '取消到院轉發')
                            or _relay_msg.startswith('綁定到院通知')):
                        _resp = handle_relay_commands(_relay_msg, _relay_chat)
                        if _resp:
                            reply_text(event.reply_token, _resp)
                            continue
                except Exception as e:
                    logger.error(f"到院轉發指令處理失敗: {e}", exc_info=True)
                # --- END PATCH: 到院轉發綁定指令 ---

                # --- PATCH: 接送群靜默 ---
                # 註冊過的接送群只認白名單關鍵字（「收到」→ handle_ack）,
                # 其他文字一律靜默跳過（不進 router/sandbox/AI）。
                # 位置訊息不在此攔（LocationMessage 走下面另一分支照常）。
                try:
                    from modules.services.group_location_meta_service import find_work_by_relay
                    from modules.handlers.arrival_relay_handler import handle_ack
                    from modules.handlers.location_message_handler import _get_chat_id
                    _silence_chat = _get_chat_id(event)
                    if _silence_chat and find_work_by_relay(_silence_chat):
                        if not handle_ack(event.reply_token, _silence_chat,
                                          original_message_text, user_id=user_id):
                            logger.info(
                                f"Skip relay-group message: {original_message_text!r}"
                            )
                        continue
                except Exception as e:
                    logger.error(f"接送群靜默判定失敗: {e}", exc_info=True)
                # --- END PATCH: 接送群靜默 ---

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
                            from rewrite.conversation_state import (
                                PENDING_MUTATION_STATE_TYPE,
                                MUTATION_CONFIRM_TEXT,
                                MUTATION_CANCEL_TEXT,
                            )
                            # (a) 看起來像按鈕 callback / 已知快速命令 → 讓過
                            if looks_like_quick_command(original_message_text):
                                is_bot_addressed = True
                            else:
                                # (b) 多輪對話狀態中 → 讓過（follow-up 通常無 / 前綴）
                                #     但只在「同對話」才算 — 防止私聊 state 跨到群組
                                #     讓所有閒聊被當 bot 訊息
                                _rew_st = _rew_state_get(user_id) if user_id else None
                                _st_type = _rew_st.get('type') if _rew_st else None
                                _active_types = (
                                    SANDBOX_ACTIVE_STATE_TYPE,
                                    TRIP_STATUS_PICKER_STATE_TYPE,
                                    TRIP_STATUS_LEAVE_INPUT_STATE_TYPE,
                                    ACCT_LEDGER_RANGE_INPUT_STATE_TYPE,
                                )
                                _gate_ok = False
                                if _st_type == PENDING_MUTATION_STATE_TYPE:
                                    # AI mutation 機制層確認不是自由對話 state：
                                    # 只放行「確認執行」「取消操作」兩個 exact 文字，
                                    # 其他閒聊照常靜默跳過 — 避免 pending 期間群組
                                    # 閒聊被丟給 AI（成本/隱私外洩），也避免 AI 回覆
                                    # 判定成 follow-up 後 SANDBOX_ACTIVE 覆蓋掉
                                    # pending state（確認按鈕變死）
                                    _gate_ok = original_message_text.strip() in (
                                        MUTATION_CONFIRM_TEXT,
                                        MUTATION_CANCEL_TEXT,
                                    )
                                elif _st_type in _active_types:
                                    _gate_ok = True
                                if _gate_ok:
                                    state_chat = _rew_st.get('chat_id')
                                    current_chat = _rew_get_chat(event)
                                    if state_chat and state_chat == current_chat:
                                        is_bot_addressed = True
                                    # state 沒記 chat（舊 state）或不同對話 → 不 bypass
                        except Exception:
                            pass

                if not is_bot_addressed:
                    # 群組閘門吞掉前的例外：該用戶多輪對話「剛逾時」（grace 期內）
                    # → 提示一次再清掉標記，避免用戶以為 bot 沒反應
                    #（清掉後之後的閒聊照常靜默跳過，只提示這一次）
                    if source_type in ('group', 'room') and user_id:
                        try:
                            from rewrite.conversation_state import (
                                peek_recently_expired as _rew_peek_expired,
                                clear_state as _rew_clear_state,
                                get_chat_id_from_event as _rew_chat_of,
                            )
                            if _rew_peek_expired(user_id, chat_id=_rew_chat_of(event)):
                                _rew_clear_state(user_id)
                                reply_text(
                                    event.reply_token,
                                    "⏰ 對話已逾時，請重新操作（群組指令請加 / 開頭）",
                                )
                                continue
                        except Exception as _exp_err:
                            logger.warning(f"逾時提示處理失敗: {_exp_err}")
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
