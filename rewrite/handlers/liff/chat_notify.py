"""LIFF 表單完成通知共用 helper（chat_text 協議）

背景：prod LINE 頻道免費 push 額度 200 則/月會爆。LIFF 表單提交完成後的
結果通知改成前端 liff.sendMessages()（以用戶身分發進打開 LIFF 的聊天室，
不吃 push 額度）；push 只留作 fallback。

協議：
  1. 前端 payload 帶 client_can_send=True（LINE app 內 + utou/room/group 才 True）
  2. handler 把「原本 push 的那段文字」先組好成 text
  3. client_can_send=True → 不 push，回應 JSON 帶 'chat_text': text，
     由前端 liff.sendMessages() 發進聊天室；sendMessages 失敗時前端顯示
     「複製結果」fallback 區塊
  4. False / 缺省（外部瀏覽器、舊快取頁）→ 照舊 push，行為不變
  5. PUSH_NOTIFY 開關語意照舊 — 只影響剩餘的 push 路徑，不影響 chat_text
"""
import logging

logger = logging.getLogger(__name__)


def push_text(target_id, text, label: str = 'liff') -> None:
    """push 一則純文字到指定目標（fallback 路徑用）。

    PUSH_NOTIFY off / target 空 / text 空 → skip；
    失敗只 log warning，不 raise — push 不該擋住 LIFF 回應。
    """
    if not target_id or not text:
        return
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        from modules.utils.line_bot import get_line_bot_api, push_notify_enabled

        if not push_notify_enabled():
            logger.info(f"[LIFF] push skipped (PUSH_NOTIFY off) [{label}]")
            return
        api = get_line_bot_api()
        api.push_message(PushMessageRequest(
            to=target_id, messages=[TextMessage(text=text)],
        ))
        logger.info(f"[LIFF] pushed {label} to {target_id[:8]}")
    except Exception as e:
        body_attr = getattr(e, 'body', None)
        logger.warning(f"[LIFF] push {label} failed: {e} body={body_attr!r}")


def notify_or_chat_text(*, client_can_send: bool, target_id, text,
                        label: str = 'liff'):
    """chat_text 協議核心分支。

    client_can_send=True  → 不 push，回傳 text（handler 放進回應 JSON 的
                            'chat_text'，讓前端 liff.sendMessages 免費發送）
    client_can_send=False → 照舊 push（外部瀏覽器 / 舊快取頁 fallback），回 None
    """
    if client_can_send:
        logger.info(f"[LIFF] chat_text 由前端 sendMessages 發送（不 push）[{label}]")
        return text
    push_text(target_id, text, label=label)
    return None
