"""
輕路由：帳務處理
- 提供「帳務處理」餘額查詢與兩個快捷操作入口
- 逐步引導「記錄入金」與「記錄上週扣款」並落庫到 account_ledger

保持既有風格：
- 使用 QuickReplyManager 組裝按鈕
- 使用 ResponseHandler 發送
- 對話狀態使用 conversation_manager
- 資料庫操作使用 db.session.execute(sql_text(...))
"""
import logging
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Dict, Any

from sqlalchemy import text as sql_text

from modules.models.base import db
from modules.utils.quick_reply_manager import QuickReplyManager
from modules.utils.conversation_context import conversation_manager, ActiveConversation
from modules.utils.taiwan_time import get_taiwan_time
from modules.utils.unified_date_parser import parse_date_input

logger = logging.getLogger(__name__)


# === 對外入口：命令輕路由 ===
def handle_accounting_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    """偵測並處理帳務相關命令；若處理則回傳 True"""
    try:
        normalized = message_text.strip()

        # 1) 主入口：帳務處理 → 顯示餘額 + Quick Reply
        if normalized == "帳務處理":
            return _handle_show_balance(reply_token)

        # 2) 快捷入口：記錄入金
        if normalized in ["➕ 記錄入金", "記錄入金"]:
            return _start_deposit_flow(user_id, reply_token)

        # 3) 快捷入口：記錄上週扣款
        if normalized in ["💵 記錄上週扣款", "記錄上週扣款"]:
            return _start_weekly_charge_flow(user_id, reply_token)

        return False
    except Exception as e:
        logger.error(f"[accounting_router] 命令處理失敗: {e}", exc_info=True)
        from modules.utils.line_bot import reply_text
        reply_text(reply_token, "帳務處理暫時不可用，請稍後再試")
        return True


# === 對話處理：記錄入金 ===
def handle_accounting_deposit_conversation(conversation: ActiveConversation, message_text: str, user_id: str, reply_token: str) -> None:
    """處理『記錄入金』逐步對話"""
    from modules.utils.response_handler import ResponseHandler

    step = conversation.current_step
    context = conversation.context_data or {}
    user_input = message_text.strip()

    try:
        if step == 'waiting_date':
            # 預期 YYYY-MM-DD，可容許統一解析器支援的格式
            try:
                parsed_date = parse_date_input(user_input)
                context['occurred_date'] = parsed_date.strftime('%Y-%m-%d')
                conversation_manager.update_conversation(user_id, current_step='waiting_amount', context_data=context,
                                                         prompt_message='請輸入入金金額（整數）')
                response = QuickReplyManager.create_text_response("請輸入入金金額（整數）",
                                                                  QuickReplyManager.create_common_buttons()["abandon_operation"])
                ResponseHandler.send_response(reply_token, response)
                return
            except Exception:
                response = QuickReplyManager.create_text_response("❌ 日期格式不正確，請輸入 YYYY-MM-DD",
                                                                  QuickReplyManager.create_common_buttons()["abandon_operation"])
                ResponseHandler.send_response(reply_token, response)
                return

        if step == 'waiting_amount':
            try:
                amount = int(user_input)
                if amount <= 0:
                    raise ValueError("amount must be positive")
                context['amount'] = amount
                conversation_manager.update_conversation(user_id, current_step='waiting_bank_name', context_data=context,
                                                         prompt_message='請輸入銀行名稱')
                response = QuickReplyManager.create_text_response("請輸入銀行名稱",
                                                                  QuickReplyManager.create_common_buttons()["abandon_operation"])
                ResponseHandler.send_response(reply_token, response)
                return
            except Exception:
                response = QuickReplyManager.create_text_response("❌ 金額需為正整數，請重新輸入",
                                                                  QuickReplyManager.create_common_buttons()["abandon_operation"])
                ResponseHandler.send_response(reply_token, response)
                return

        if step == 'waiting_bank_name':
            if len(user_input) < 1:
                from modules.utils.line_bot import reply_text
                reply_text(reply_token, "❌ 銀行名稱不可為空，請重新輸入")
                return
            context['bank_name'] = user_input
            conversation_manager.update_conversation(user_id, current_step='waiting_last4', context_data=context,
                                                     prompt_message='請輸入銀行末4碼')
            response = QuickReplyManager.create_text_response("請輸入銀行末4碼",
                                                              QuickReplyManager.create_common_buttons()["abandon_operation"])
            ResponseHandler.send_response(reply_token, response)
            return

        if step == 'waiting_last4':
            # 僅允許4位數字
            if not (len(user_input) == 4 and user_input.isdigit()):
                from modules.utils.line_bot import reply_text
                reply_text(reply_token, "❌ 末4碼需為4位數字，請重新輸入")
                return

            context['last4'] = user_input

            # 寫入資料庫
            occurred_at = context.get('occurred_date')  # YYYY-MM-DD
            amount = context.get('amount')
            counterparty = f"{context.get('bank_name')} {context.get('last4')}"

            insert_sql = sql_text(
                """
                INSERT INTO account_ledger (type, counterparty, amount_in, amount_out, occurred_at, memo)
                VALUES (:type, :counterparty, :amount_in, 0, :occurred_at, :memo)
                """
            )
            db.session.execute(insert_sql, {
                'type': 'deposit',
                'counterparty': counterparty,
                'amount_in': amount,
                'occurred_at': f"{occurred_at} 00:00:00",
                'memo': '入金'
            })
            db.session.commit()

            # 結束對話
            conversation_manager.end_conversation(user_id, "記錄入金完成")

            # 回覆成功訊息
            from modules.utils.line_bot import reply_text
            reply_text(reply_token, f"✅ 已記錄入金：NT$ {amount:,}\n🧾 {counterparty} | {occurred_at}")
            return

        # 未知步驟→結束
        conversation_manager.end_conversation(user_id, "未知步驟")
        from modules.utils.line_bot import reply_text
        reply_text(reply_token, "❌ 對話狀態錯誤，請重新開始『帳務處理』")
    except Exception as e:
        db.session.rollback()
        logger.error(f"[accounting_router] 記錄入金對話處理失敗: {e}", exc_info=True)
        from modules.utils.line_bot import reply_text
        reply_text(reply_token, "❌ 紀錄失敗，請稍後再試或聯繫管理員")


# === 對話處理：記錄上週扣款 ===
def handle_accounting_weekly_charge_conversation(conversation: ActiveConversation, message_text: str, user_id: str, reply_token: str) -> None:
    """處理『記錄上週扣款』逐步對話（僅需金額一步）"""
    from modules.utils.response_handler import ResponseHandler

    step = conversation.current_step
    user_input = message_text.strip()

    try:
        if step == 'waiting_amount':
            try:
                amount = int(user_input)
                if amount <= 0:
                    raise ValueError("amount must be positive")
            except Exception:
                # 重新提示
                response = QuickReplyManager.create_text_response("❌ 金額需為正整數，請重新輸入",
                                                                  QuickReplyManager.create_common_buttons()["abandon_operation"])
                ResponseHandler.send_response(reply_token, response)
                return

            # 計算最近週日 23:59（以台灣時區）
            now_tw = get_taiwan_time()
            today_date = now_tw.date()
            # 太陽週：週日為一週第一天
            days_since_sunday = today_date.weekday() + 1 if today_date.weekday() < 6 else 0
            last_sunday = today_date - (timedelta(days=days_since_sunday))
            occurred_at_dt = datetime.combine(last_sunday, dt_time(23, 59))
            occurred_at_str = occurred_at_dt.strftime('%Y-%m-%d %H:%M:%S')

            # 寫入資料庫
            insert_sql = sql_text(
                """
                INSERT INTO account_ledger (type, counterparty, amount_in, amount_out, occurred_at, memo)
                VALUES (:type, :counterparty, 0, :amount_out, :occurred_at, :memo)
                """
            )
            memo_text = f"週末 {last_sunday.strftime('%Y-%m-%d')} 扣款"
            db.session.execute(insert_sql, {
                'type': 'weekly_charge',
                'counterparty': '診所周扣款',
                'amount_out': amount,
                'occurred_at': occurred_at_str,
                'memo': memo_text
            })
            db.session.commit()

            # 結束對話
            conversation_manager.end_conversation(user_id, "記錄上週扣款完成")

            # 回覆成功
            from modules.utils.line_bot import reply_text
            reply_text(reply_token, f"✅ 已記錄上週扣款：NT$ {amount:,}\n🗓️ {memo_text}")
            return

        # 未知步驟
        conversation_manager.end_conversation(user_id, "未知步驟")
        from modules.utils.line_bot import reply_text
        reply_text(reply_token, "❌ 對話狀態錯誤，請重新開始『帳務處理』")
    except Exception as e:
        db.session.rollback()
        logger.error(f"[accounting_router] 記錄上週扣款對話處理失敗: {e}", exc_info=True)
        from modules.utils.line_bot import reply_text
        reply_text(reply_token, "❌ 紀錄失敗，請稍後再試或聯繫管理員")


# === 內部：顯示餘額 ===
def _handle_show_balance(reply_token: str) -> bool:
    from modules.utils.response_handler import ResponseHandler

    try:
        sql = sql_text(
            """
            SELECT COALESCE(SUM(amount_in),0) AS total_in, COALESCE(SUM(amount_out),0) AS total_out
            FROM account_ledger
            """
        )
        row = db.session.execute(sql).fetchone()
        total_in = (row[0] or 0) if row else 0
        total_out = (row[1] or 0) if row else 0
        balance = int(total_in) - int(total_out)
        balance_text = f"💰 目前帳戶餘額：NT$ {balance:,}"

        # Quick Reply 兩個按鈕
        buttons = [
            {"label": "➕ 記錄入金", "text": "➕ 記錄入金", "type": "message"},
            {"label": "💵 記錄上週扣款", "text": "💵 記錄上週扣款", "type": "message"},
        ]
        response = QuickReplyManager.create_text_response(balance_text, buttons)
        sent = ResponseHandler.send_response(reply_token, response)
        if not sent:
            # 回退文字
            from modules.utils.line_bot import reply_text
            reply_text(reply_token, balance_text)
        return True
    except Exception as e:
        logger.error(f"[accounting_router] 查詢餘額失敗: {e}", exc_info=True)
        from modules.utils.line_bot import reply_text
        reply_text(reply_token, "❌ 查詢餘額失敗，請稍後再試")
        return True


def _start_deposit_flow(user_id: str, reply_token: str) -> bool:
    """啟動『記錄入金』對話流程"""
    from modules.utils.response_handler import ResponseHandler

    conversation_manager.start_conversation(
        user_id=user_id,
        conversation_type='accounting_deposit',
        current_step='waiting_date',
        context_data={},
        prompt_message='請輸入入金日期（YYYY-MM-DD）',
        duration_minutes=5
    )
    response = QuickReplyManager.create_text_response(
        "請輸入入金日期（YYYY-MM-DD）",
        QuickReplyManager.create_common_buttons()["abandon_operation"]
    )
    ResponseHandler.send_response(reply_token, response)
    return True


def _start_weekly_charge_flow(user_id: str, reply_token: str) -> bool:
    """啟動『記錄上週扣款』對話流程"""
    from modules.utils.response_handler import ResponseHandler

    conversation_manager.start_conversation(
        user_id=user_id,
        conversation_type='accounting_weekly_charge',
        current_step='waiting_amount',
        context_data={},
        prompt_message='請輸入上週總扣款金額（整數）',
        duration_minutes=5
    )
    response = QuickReplyManager.create_text_response(
        "請輸入上週總扣款金額（整數）",
        QuickReplyManager.create_common_buttons()["abandon_operation"]
    )
    ResponseHandler.send_response(reply_token, response)
    return True
